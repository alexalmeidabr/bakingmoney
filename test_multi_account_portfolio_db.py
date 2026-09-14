import os
import tempfile
import unittest
from unittest import mock

import web_server


LEGACY_POSITION_COLUMNS = """
  symbol TEXT PRIMARY KEY,
  position REAL,
  price REAL,
  avg_cost REAL,
  change_percent REAL,
  market_value REAL,
  unrealized_pnl REAL,
  daily_pnl REAL,
  currency TEXT,
  updated_at TEXT NOT NULL
"""


LEGACY_SUMMARY_COLUMNS = """
  id INTEGER PRIMARY KEY CHECK (id = 1),
  account_id TEXT,
  base_currency TEXT,
  net_liquidation REAL,
  total_cash_value REAL,
  settled_cash REAL,
  available_funds REAL,
  buying_power REAL,
  excess_liquidity REAL,
  ledger_cash_usd REAL,
  actual_cash REAL,
  updated_at TEXT NOT NULL
"""


def pk_columns(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row["name"] for row in sorted([row for row in rows if row["pk"]], key=lambda row: row["pk"])]


def table_columns(conn, table):
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


class MultiAccountPortfolioDatabaseTests(unittest.TestCase):
    def init_temp_db(self, db_path):
        with mock.patch.object(web_server, "DB_PATH", db_path):
            web_server.init_db()
        return web_server.sqlite3.connect(db_path)

    def open_app_conn(self, db_path):
        conn = web_server.sqlite3.connect(db_path)
        conn.row_factory = web_server.sqlite3.Row
        return conn

    def create_legacy_portfolio_tables(self, db_path, include_summary_account_id=True):
        conn = self.open_app_conn(db_path)
        try:
            conn.execute(f"CREATE TABLE positions_cache ({LEGACY_POSITION_COLUMNS})")
            summary_columns = LEGACY_SUMMARY_COLUMNS
            if not include_summary_account_id:
                summary_columns = summary_columns.replace("  account_id TEXT,\n", "")
            conn.execute(f"CREATE TABLE portfolio_summary_cache ({summary_columns})")
            conn.commit()
        finally:
            conn.close()

    def insert_legacy_position(self, conn, symbol, position, avg_cost=80.0, market_value=1000.0):
        conn.execute(
            """
            INSERT INTO positions_cache (
              symbol, position, price, avg_cost, change_percent, market_value,
              unrealized_pnl, daily_pnl, currency, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, position, 100.0, avg_cost, 1.5, market_value, 123.0, 12.0, "USD", "2026-01-01T00:00:00+00:00"),
        )

    def insert_legacy_summary(self, conn, account_id="U1111111"):
        conn.execute(
            """
            INSERT INTO portfolio_summary_cache (
              id, account_id, base_currency, net_liquidation, total_cash_value, settled_cash,
              available_funds, buying_power, excess_liquidity, ledger_cash_usd, actual_cash, updated_at
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (account_id, "USD", 100000.0, 12000.0, 11000.0, 9000.0, 50000.0, 8000.0, 7000.0, 7000.0, "2026-01-01T00:00:00+00:00"),
        )

    def test_legacy_migration_with_real_account_id_preserves_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "legacy-real.db")
            self.create_legacy_portfolio_tables(db_path)
            conn = self.open_app_conn(db_path)
            try:
                self.insert_legacy_position(conn, "NVDA", 100, avg_cost=50.0, market_value=10000.0)
                self.insert_legacy_position(conn, "MSFT", 25, avg_cost=200.0, market_value=5000.0)
                self.insert_legacy_summary(conn, "U1111111")
                conn.commit()
            finally:
                conn.close()

            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual(pk_columns(conn, "positions_cache"), ["account_id", "symbol"])
                self.assertEqual(pk_columns(conn, "portfolio_summary_cache"), ["account_id"])
                self.assertNotIn("id", table_columns(conn, "portfolio_summary_cache"))
                accounts = web_server.list_ib_accounts(conn)
                self.assertEqual([row["account_id"] for row in accounts], ["U1111111"])
                rows = conn.execute(
                    "SELECT account_id, symbol, position, avg_cost, market_value FROM positions_cache ORDER BY symbol"
                ).fetchall()
                self.assertEqual([(row["account_id"], row["symbol"]) for row in rows], [("U1111111", "MSFT"), ("U1111111", "NVDA")])
                self.assertEqual(rows[1]["position"], 100)
                self.assertEqual(rows[1]["avg_cost"], 50.0)
                summary = web_server.load_portfolio_summary_cache(conn, "U1111111")
                self.assertEqual(summary["account_id"], "U1111111")
                self.assertEqual(summary["net_liquidation"], 100000.0)
                self.assertEqual(summary["actual_cash"], 7000.0)
            finally:
                conn.close()

    def test_legacy_migration_without_account_id_uses_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "legacy-placeholder.db")
            self.create_legacy_portfolio_tables(db_path, include_summary_account_id=False)
            conn = self.open_app_conn(db_path)
            try:
                self.insert_legacy_position(conn, "NVDA", 12)
                conn.commit()
            finally:
                conn.close()

            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()

            conn = self.open_app_conn(db_path)
            try:
                account = web_server.get_ib_account(conn, web_server.LEGACY_IB_ACCOUNT_ID)
                self.assertIsNotNone(account)
                self.assertEqual(account["display_name"], "Legacy Account")
                rows = conn.execute("SELECT account_id, symbol FROM positions_cache").fetchall()
                self.assertEqual([(row["account_id"], row["symbol"]) for row in rows], [(web_server.LEGACY_IB_ACCOUNT_ID, "NVDA")])
            finally:
                conn.close()

    def test_empty_legacy_database_does_not_create_placeholder_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "empty-legacy.db")
            self.create_legacy_portfolio_tables(db_path)

            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual(web_server.list_ib_accounts(conn), [])
                self.assertEqual(pk_columns(conn, "positions_cache"), ["account_id", "symbol"])
                self.assertEqual(pk_columns(conn, "portfolio_summary_cache"), ["account_id"])
            finally:
                conn.close()

    def test_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "idempotent.db")
            self.create_legacy_portfolio_tables(db_path)
            conn = self.open_app_conn(db_path)
            try:
                self.insert_legacy_position(conn, "NVDA", 100)
                self.insert_legacy_summary(conn, "U1111111")
                conn.commit()
            finally:
                conn.close()

            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                web_server.init_db()

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM ib_accounts").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM portfolio_summary_cache").fetchone()[0], 1)
                self.assertEqual(pk_columns(conn, "positions_cache"), ["account_id", "symbol"])
            finally:
                conn.close()

    def test_same_symbol_can_exist_in_multiple_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "multi.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 100, "avgCost": 50, "marketValue": 10000}], account_id="U1111111")
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 25, "avgCost": 400, "marketValue": 2500}], account_id="U2222222")
                    u1 = web_server.load_positions_cache(conn, "U1111111")
                    u2 = web_server.load_positions_cache(conn, "U2222222")
                    self.assertEqual(u1[0]["position"], 100)
                    self.assertEqual(u1[0]["avgCost"], 50)
                    self.assertEqual(u2[0]["position"], 25)
                    self.assertEqual(u2[0]["avgCost"], 400)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache WHERE symbol = 'NVDA'").fetchone()[0], 2)
                finally:
                    conn.close()

    def test_position_cleanup_is_account_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "cleanup.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 10}, {"symbol": "MSFT", "position": 5}], account_id="U1111111")
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 25}, {"symbol": "AMZN", "position": 4}], account_id="U2222222")
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 10}], account_id="U1111111")
                    rows = conn.execute("SELECT account_id, symbol FROM positions_cache ORDER BY account_id, symbol").fetchall()
                    self.assertEqual(
                        [(row["account_id"], row["symbol"]) for row in rows],
                        [("U1111111", "NVDA"), ("U2222222", "AMZN"), ("U2222222", "NVDA")],
                    )
                    web_server.save_positions_cache(conn, [], account_id="U1111111")
                    rows = conn.execute("SELECT account_id, symbol FROM positions_cache ORDER BY account_id, symbol").fetchall()
                    self.assertEqual([(row["account_id"], row["symbol"]) for row in rows], [("U2222222", "AMZN"), ("U2222222", "NVDA")])
                finally:
                    conn.close()

    def test_portfolio_summary_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "summary.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 100000, "actual_cash": 10000, "base_currency": "USD"}, account_id="U1111111")
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 250000, "actual_cash": 50000, "base_currency": "USD"}, account_id="U2222222")
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 125000, "actual_cash": 15000, "base_currency": "USD"}, account_id="U1111111")
                    self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 125000)
                    self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U2222222")["net_liquidation"], 250000)
                    self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U2222222")["actual_cash"], 50000)
                finally:
                    conn.close()

    def test_single_account_helpers_remain_backward_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "single.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "MSFT", "position": 7, "marketValue": 700}], account_id="U1111111")
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 7000, "actual_cash": 700}, account_id="U1111111")
                    self.assertEqual(web_server.load_positions_cache(conn)[0]["symbol"], "MSFT")
                    self.assertEqual(web_server.load_portfolio_summary_cache(conn)["net_liquidation"], 7000)
                finally:
                    conn.close()

    def test_ambiguous_multiple_accounts_require_account_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ambiguous.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "MSFT", "position": 7}], account_id="U1111111")
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 3}], account_id="U2222222")
                    with self.assertRaisesRegex(ValueError, "account_id is required"):
                        web_server.load_positions_cache(conn)
                    with self.assertRaisesRegex(ValueError, "account_id is required"):
                        web_server.load_portfolio_summary_cache(conn)
                finally:
                    conn.close()

    def test_primary_keys_are_account_keyed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "schema.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual(pk_columns(conn, "ib_accounts"), ["account_id"])
                self.assertEqual(pk_columns(conn, "positions_cache"), ["account_id", "symbol"])
                self.assertEqual(pk_columns(conn, "portfolio_summary_cache"), ["account_id"])
            finally:
                conn.close()

    def test_old_backup_without_ib_accounts_validates_and_migrates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "old-backup.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
            conn = self.open_app_conn(db_path)
            try:
                conn.execute("DROP TABLE positions_cache")
                conn.execute("DROP TABLE portfolio_summary_cache")
                conn.execute("DROP TABLE ib_accounts")
                conn.execute(f"CREATE TABLE positions_cache ({LEGACY_POSITION_COLUMNS})")
                conn.execute(f"CREATE TABLE portfolio_summary_cache ({LEGACY_SUMMARY_COLUMNS})")
                self.insert_legacy_position(conn, "NVDA", 100)
                self.insert_legacy_summary(conn, "U1111111")
                conn.commit()
            finally:
                conn.close()

            web_server._validate_backup_db_file(db_path)
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()

            conn = self.open_app_conn(db_path)
            try:
                self.assertIsNotNone(web_server.get_ib_account(conn, "U1111111"))
                self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["symbol"], "NVDA")
                self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 100000.0)
            finally:
                conn.close()

    def test_new_backup_preserves_multiple_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "source.db")
            snapshot_path = os.path.join(tmp, "snapshot.db")
            restored_path = os.path.join(tmp, "restored.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 100}], account_id="U1111111")
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 25}], account_id="U2222222")
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 100000}, account_id="U1111111")
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 250000}, account_id="U2222222")
                finally:
                    conn.close()

            web_server._create_db_backup_snapshot(db_path, snapshot_path)
            web_server._validate_backup_db_file(snapshot_path)
            os.replace(snapshot_path, restored_path)
            with mock.patch.object(web_server, "DB_PATH", restored_path):
                web_server.init_db()

            conn = self.open_app_conn(restored_path)
            try:
                accounts = [row["account_id"] for row in web_server.list_ib_accounts(conn)]
                self.assertEqual(accounts, ["U1111111", "U2222222"])
                self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["position"], 100)
                self.assertEqual(web_server.load_positions_cache(conn, "U2222222")[0]["position"], 25)
                self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 100000)
                self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U2222222")["net_liquidation"], 250000)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
