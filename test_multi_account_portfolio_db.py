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


class FakeSummaryItem:
    def __init__(self, account, tag, value, currency="USD"):
        self.account = account
        self.tag = tag
        self.value = value
        self.currency = currency


class FakeContract:
    def __init__(self, symbol, con_id, currency="USD"):
        self.symbol = symbol
        self.conId = con_id
        self.currency = currency


class FakePosition:
    def __init__(self, account, symbol, quantity, avg_cost, con_id):
        self.account = account
        self.contract = FakeContract(symbol, con_id)
        self.position = quantity
        self.avgCost = avg_cost


class FakeTicker:
    def __init__(self, contract, price=100.0, close=95.0):
        self.contract = contract
        self.last = price
        self.close = close
        self.prevClose = close

    def marketPrice(self):
        return self.last


class FakeIB:
    def __init__(self, positions=None, summary_items=None, managed_accounts=None):
        self._positions = positions or []
        self._summary_items = summary_items or []
        self._managed_accounts = managed_accounts or []

    def positions(self):
        return self._positions

    def accountSummary(self):
        return self._summary_items

    def managedAccounts(self):
        return self._managed_accounts

    def qualifyContracts(self, *contracts):
        return list(contracts)


class CapturingPositionsHandler:
    def __init__(self):
        self.response = None

    def _send_json(self, payload, status=200):
        self.response = {"payload": payload, "status": status}


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

    def create_modern_portfolio_state(self, conn, account_id, positions=None, summary=None):
        if positions is not None:
            web_server.save_positions_cache(conn, positions, account_id=account_id)
        if summary is not None:
            web_server.save_portfolio_summary_cache(conn, summary, account_id=account_id)

    def run_fake_positions_refresh(self, db_path, ib, tws_data_enabled=True):
        handler = CapturingPositionsHandler()
        tickers = [FakeTicker(position.contract) for position in ib.positions()]
        with mock.patch.object(web_server, "DB_PATH", db_path), \
             mock.patch.object(web_server, "ensure_event_loop", return_value=None), \
             mock.patch.object(web_server, "get_ib_connection", return_value=ib), \
             mock.patch.object(web_server, "is_tws_data_enabled", return_value=tws_data_enabled), \
             mock.patch.object(web_server, "request_ib_tickers_batched", return_value=(tickers, {})), \
             mock.patch.object(web_server, "list_analysis_symbols", return_value=[]):
            web_server.BakingMoneyHandler.handle_positions_api(handler, refresh=True)
        return handler.response

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

    def test_single_account_summary_filters_rows_to_detected_account(self):
        items = [
            FakeSummaryItem("U1111111", "NetLiquidation", "100000", "USD"),
            FakeSummaryItem("U1111111", "TotalCashValue", "12000", "USD"),
            FakeSummaryItem("U1111111", "SettledCash", "11000", "USD"),
            FakeSummaryItem("U1111111", "CashBalance", "9000", "USD"),
            FakeSummaryItem("", "NetLiquidation", "999999", "USD"),
        ]
        summary = web_server.fetch_ib_portfolio_summary(FakeIB(summary_items=items, managed_accounts=["U1111111"]))
        self.assertEqual(summary["account_id"], "U1111111")
        self.assertEqual(summary["net_liquidation"], 100000.0)
        self.assertEqual(summary["total_cash_value"], 12000.0)
        self.assertEqual(summary["settled_cash"], 11000.0)
        self.assertEqual(summary["ledger_cash_usd"], 9000.0)
        self.assertNotIn("999999", str(summary))

    def test_one_managed_account_allows_multiple_summary_identifiers(self):
        ib = FakeIB(
            positions=[FakePosition("U1111111", "NVDA", 12, 80, 1)],
            summary_items=[
                FakeSummaryItem("U1111111", "NetLiquidation", "120000", "USD"),
                FakeSummaryItem("U1111111", "CashBalance", "5000", "USD"),
                FakeSummaryItem("All", "NetLiquidation", "999999", "USD"),
                FakeSummaryItem("GROUP_SUMMARY", "CashBalance", "888888", "USD"),
            ],
            managed_accounts=["U1111111"],
        )
        summary = web_server.fetch_ib_portfolio_summary(ib)
        self.assertEqual(summary["account_id"], "U1111111")
        self.assertEqual(summary["net_liquidation"], 120000.0)
        self.assertEqual(summary["ledger_cash_usd"], 5000.0)

    def test_zero_managed_multiple_summary_accounts_are_rejected(self):
        items = [
            FakeSummaryItem("U1111111", "NetLiquidation", "100000", "USD"),
            FakeSummaryItem("U2222222", "NetLiquidation", "250000", "USD"),
        ]
        with self.assertRaises(web_server.MultipleIBAccountsDetectedError):
            web_server.fetch_ib_portfolio_summary(FakeIB(summary_items=items))

    def test_live_refresh_rejects_multiple_position_accounts_without_cache_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "multiple-position-accounts.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self.create_modern_portfolio_state(
                        conn,
                        "U1111111",
                        positions=[{"symbol": "NVDA", "position": 100, "avgCost": 50, "marketValue": 10000}],
                        summary={"net_liquidation": 100000, "actual_cash": 10000},
                    )
                finally:
                    conn.close()

            ib = FakeIB(
                positions=[
                    FakePosition("U1111111", "NVDA", 100, 50, 1),
                    FakePosition("U2222222", "MSFT", 20, 200, 2),
                ],
                summary_items=[FakeSummaryItem("U1111111", "NetLiquidation", "100000")],
            )
            response = self.run_fake_positions_refresh(db_path, ib)
            self.assertEqual(response["status"], 409)
            self.assertIn("Multiple Interactive Brokers accounts", response["payload"]["error"])

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                positions = web_server.load_positions_cache(conn, "U1111111")
                self.assertEqual(len(positions), 1)
                self.assertEqual(positions[0]["symbol"], "NVDA")
                self.assertEqual(positions[0]["position"], 100)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache WHERE account_id = 'U2222222'").fetchone()[0], 0)
                self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 100000)
            finally:
                conn.close()

    def test_live_refresh_rejects_managed_position_account_mismatch_without_cache_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "account-mismatch.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self.create_modern_portfolio_state(
                        conn,
                        "U1111111",
                        positions=[{"symbol": "NVDA", "position": 100, "avgCost": 50, "marketValue": 10000}],
                        summary={"net_liquidation": 100000, "actual_cash": 10000},
                    )
                finally:
                    conn.close()

            ib = FakeIB(
                positions=[FakePosition("U2222222", "NVDA", 100, 50, 1)],
                summary_items=[FakeSummaryItem("U1111111", "NetLiquidation", "100000")],
                managed_accounts=["U1111111"],
            )
            response = self.run_fake_positions_refresh(db_path, ib)
            self.assertEqual(response["status"], 409)

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["position"], 100)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache WHERE account_id = 'U2222222'").fetchone()[0], 0)
                self.assertIsNone(web_server.load_portfolio_summary_cache(conn, "U2222222"))
                self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 100000)
            finally:
                conn.close()

    def test_live_refresh_rejects_two_managed_accounts_without_cache_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "two-managed-accounts.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self.create_modern_portfolio_state(
                        conn,
                        "U1111111",
                        positions=[{"symbol": "NVDA", "position": 100, "avgCost": 50, "marketValue": 10000}],
                        summary={"net_liquidation": 100000, "actual_cash": 10000},
                    )
                finally:
                    conn.close()

            ib = FakeIB(
                positions=[FakePosition("U1111111", "NVDA", 100, 50, 1)],
                summary_items=[FakeSummaryItem("U1111111", "NetLiquidation", "100000")],
                managed_accounts=["U1111111", "U2222222"],
            )
            response = self.run_fake_positions_refresh(db_path, ib)
            self.assertEqual(response["status"], 409)

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["position"], 100)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache WHERE account_id = 'U2222222'").fetchone()[0], 0)
                self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 100000)
            finally:
                conn.close()

    def test_live_refresh_rejects_multiple_summary_accounts_without_cache_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "multiple-summary-accounts.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self.create_modern_portfolio_state(
                        conn,
                        "U1111111",
                        positions=[{"symbol": "NVDA", "position": 100, "avgCost": 50, "marketValue": 10000}],
                        summary={"net_liquidation": 100000, "actual_cash": 10000},
                    )
                finally:
                    conn.close()

            ib = FakeIB(
                positions=[FakePosition("U1111111", "NVDA", 100, 50, 1)],
                summary_items=[
                    FakeSummaryItem("U1111111", "NetLiquidation", "100000"),
                    FakeSummaryItem("U2222222", "NetLiquidation", "250000"),
                ],
            )
            response = self.run_fake_positions_refresh(db_path, ib)
            self.assertEqual(response["status"], 409)

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["position"], 100)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache WHERE account_id = 'U2222222'").fetchone()[0], 0)
                self.assertIsNone(web_server.load_portfolio_summary_cache(conn, "U2222222"))
                self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 100000)
            finally:
                conn.close()

    def test_single_account_live_refresh_still_saves_positions_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "single-live-refresh.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()

            ib = FakeIB(
                positions=[FakePosition("U1111111", "NVDA", 12, 80, 1)],
                summary_items=[
                    FakeSummaryItem("U1111111", "NetLiquidation", "120000"),
                    FakeSummaryItem("U1111111", "CashBalance", "5000"),
                ],
                managed_accounts=["U1111111"],
            )
            response = self.run_fake_positions_refresh(db_path, ib)
            self.assertEqual(response["status"], 200)

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                position = web_server.load_positions_cache(conn, "U1111111")[0]
                self.assertEqual(position["symbol"], "NVDA")
                self.assertEqual(position["position"], 12)
                self.assertEqual(position["marketValue"], 1200.0)
                summary = web_server.load_portfolio_summary_cache(conn, "U1111111")
                self.assertEqual(summary["net_liquidation"], 120000.0)
                self.assertEqual(summary["ledger_cash_usd"], 5000.0)
            finally:
                conn.close()

    def test_single_managed_account_refresh_allows_multiple_summary_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "single-managed-summary-groups.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()

            ib = FakeIB(
                positions=[FakePosition("U1111111", "NVDA", 12, 80, 1)],
                summary_items=[
                    FakeSummaryItem("U1111111", "NetLiquidation", "120000"),
                    FakeSummaryItem("U1111111", "CashBalance", "5000"),
                    FakeSummaryItem("All", "NetLiquidation", "999999"),
                    FakeSummaryItem("GROUP_SUMMARY", "CashBalance", "888888"),
                ],
                managed_accounts=["U1111111"],
            )
            response = self.run_fake_positions_refresh(db_path, ib)
            self.assertEqual(response["status"], 200)

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["position"], 12)
                summary = web_server.load_portfolio_summary_cache(conn, "U1111111")
                self.assertEqual(summary["net_liquidation"], 120000.0)
                self.assertEqual(summary["ledger_cash_usd"], 5000.0)
            finally:
                conn.close()

    def test_single_managed_account_refresh_allows_blank_position_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "blank-position-account.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()

            ib = FakeIB(
                positions=[FakePosition("", "NVDA", 12, 80, 1)],
                summary_items=[FakeSummaryItem("U1111111", "NetLiquidation", "120000")],
                managed_accounts=["U1111111"],
            )
            response = self.run_fake_positions_refresh(db_path, ib)
            self.assertEqual(response["status"], 200)

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["symbol"], "NVDA")
            finally:
                conn.close()

    def test_zero_managed_accounts_unambiguous_live_data_falls_back_to_single_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "zero-managed-unambiguous.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()

            ib = FakeIB(
                positions=[FakePosition("U1111111", "NVDA", 12, 80, 1)],
                summary_items=[
                    FakeSummaryItem("U1111111", "NetLiquidation", "120000"),
                    FakeSummaryItem("U1111111", "CashBalance", "5000"),
                ],
                managed_accounts=[],
            )
            response = self.run_fake_positions_refresh(db_path, ib)
            self.assertEqual(response["status"], 200)

            conn = self.open_app_conn(db_path)
            try:
                self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["position"], 12)
                self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 120000)
            finally:
                conn.close()

    def test_zero_managed_accounts_with_no_usable_ids_selects_no_account(self):
        self.assertIsNone(web_server._select_live_ib_account_id([], [], []))

    def test_legacy_account_auto_reconciles_to_first_real_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "legacy-reconcile.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(
                        conn,
                        [
                            {"symbol": "NVDA", "position": 100, "avgCost": 50, "marketValue": 10000},
                            {"symbol": "MSFT", "position": 20, "avgCost": 200, "marketValue": 4000},
                        ],
                        account_id=web_server.LEGACY_IB_ACCOUNT_ID,
                    )
                    web_server.save_portfolio_summary_cache(
                        conn,
                        {"net_liquidation": 100000, "actual_cash": 10000},
                        account_id=web_server.LEGACY_IB_ACCOUNT_ID,
                    )
                    web_server.save_portfolio_summary_cache(
                        conn,
                        {"net_liquidation": 100000, "actual_cash": 10000},
                        account_id="U1111111",
                    )
                    self.assertEqual([row["account_id"] for row in web_server.list_ib_accounts(conn)], ["U1111111"])
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache WHERE account_id = ?", (web_server.LEGACY_IB_ACCOUNT_ID,)).fetchone()[0], 0)
                    rows = conn.execute("SELECT account_id, symbol, position, avg_cost, market_value FROM positions_cache ORDER BY symbol").fetchall()
                    self.assertEqual([(row["account_id"], row["symbol"], row["position"]) for row in rows], [("U1111111", "MSFT", 20), ("U1111111", "NVDA", 100)])
                    self.assertEqual(rows[1]["avg_cost"], 50)
                    self.assertEqual(rows[1]["market_value"], 10000)
                    self.assertIsNone(web_server.load_portfolio_summary_cache(conn, web_server.LEGACY_IB_ACCOUNT_ID))
                    self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["actual_cash"], 10000)
                finally:
                    conn.close()

    def test_legacy_reconciliation_is_idempotent_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "legacy-reconcile-idempotent.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 100}], account_id=web_server.LEGACY_IB_ACCOUNT_ID)
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 100000}, account_id="U1111111")
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 120}], account_id="U1111111")
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 125000}, account_id="U1111111")
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM ib_accounts").fetchone()[0], 1)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache").fetchone()[0], 1)
                    self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["position"], 120)
                    self.assertEqual(web_server.load_portfolio_summary_cache(conn, "U1111111")["net_liquidation"], 125000)
                finally:
                    conn.close()

    def test_legacy_reconciliation_does_not_merge_conflicting_real_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "legacy-conflict.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 100}], account_id=web_server.LEGACY_IB_ACCOUNT_ID)
                    conn.execute(
                        """
                        INSERT INTO positions_cache (
                          account_id, symbol, position, price, avg_cost, change_percent,
                          market_value, unrealized_pnl, daily_pnl, currency, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("U1111111", "MSFT", 20, None, None, None, None, None, None, "USD", web_server.utc_now_iso()),
                    )
                    conn.commit()
                    with self.assertRaisesRegex(RuntimeError, "target account data already exists"):
                        web_server.reconcile_legacy_account_to_real_account(conn, "U1111111")
                    self.assertIsNotNone(web_server.get_ib_account(conn, web_server.LEGACY_IB_ACCOUNT_ID))
                    self.assertIsNone(web_server.get_ib_account(conn, "U1111111"))
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache WHERE account_id = ?", (web_server.LEGACY_IB_ACCOUNT_ID,)).fetchone()[0], 1)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM positions_cache WHERE account_id = 'U1111111'").fetchone()[0], 1)
                finally:
                    conn.close()

    def test_multiple_accounts_do_not_trigger_legacy_auto_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "legacy-multiple-accounts.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "NVDA", "position": 100}], account_id=web_server.LEGACY_IB_ACCOUNT_ID)
                    web_server.upsert_ib_account(conn, "U2222222")
                    conn.execute(
                        """
                        INSERT INTO positions_cache (
                          account_id, symbol, position, price, avg_cost, change_percent,
                          market_value, unrealized_pnl, daily_pnl, currency, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("U2222222", "AMZN", 5, None, None, None, None, None, None, "USD", web_server.utc_now_iso()),
                    )
                    conn.commit()
                    web_server.save_positions_cache(conn, [{"symbol": "MSFT", "position": 20}], account_id="U1111111")
                    accounts = [row["account_id"] for row in web_server.list_ib_accounts(conn)]
                    self.assertEqual(set(accounts), {web_server.LEGACY_IB_ACCOUNT_ID, "U1111111", "U2222222"})
                    self.assertEqual(web_server.load_positions_cache(conn, web_server.LEGACY_IB_ACCOUNT_ID)[0]["symbol"], "NVDA")
                    self.assertEqual(web_server.load_positions_cache(conn, "U1111111")[0]["symbol"], "MSFT")
                    self.assertEqual(web_server.load_positions_cache(conn, "U2222222")[0]["symbol"], "AMZN")
                finally:
                    conn.close()


if __name__ == "__main__":
    unittest.main()
