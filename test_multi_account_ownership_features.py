import os
import tempfile
import unittest
from unittest import mock

import web_server


ACCOUNT_A = "U_TEST_A"
ACCOUNT_B = "U_TEST_B"
ACCOUNT_PENDING = "U_TEST_PENDING"


class CapturingHandler:
    def __init__(self):
        self.response = None

    def _send_json(self, payload, status=200):
        self.response = {"payload": payload, "status": status}


class MultiAccountOwnershipFeatureTests(unittest.TestCase):
    def init_db(self, db_path):
        with mock.patch.object(web_server, "DB_PATH", db_path):
            web_server.init_db()

    def open_conn(self, db_path):
        conn = web_server.sqlite3.connect(db_path)
        conn.row_factory = web_server.sqlite3.Row
        return conn

    def seed_analysis(self, conn, *symbols):
        now = web_server.utc_now_iso()
        for symbol in symbols:
            normalized = web_server.normalize_symbol(symbol)
            conn.execute(
                "INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)",
                (normalized, now, now),
            )
            root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (normalized,)).fetchone()["id"]
            conn.execute(
                """
                INSERT INTO analysis_versions (
                  analysis_root_id, version_number, symbol, company_name,
                  current_price, expected_price, upside, created_at
                ) VALUES (?, 1, ?, ?, 100, 125, 25, ?)
                """,
                (root_id, normalized, f"{normalized} Corp", now),
            )
        conn.commit()

    def seed_account(self, conn, account_id, positions=None, summary=None):
        if positions is None and summary is None:
            web_server.upsert_ib_account(conn, account_id)
            conn.commit()
            return
        if positions is not None:
            web_server.save_positions_cache(conn, positions, account_id=account_id)
        if summary is not None:
            web_server.save_portfolio_summary_cache(conn, summary, account_id=account_id)

    def seed_earnings_content(self, conn):
        self.seed_analysis(conn, "NVDA", "MSFT", "AMZN")
        for symbol in ("NVDA", "MSFT", "AMZN"):
            web_server.add_earnings_review_symbol(conn, symbol)
            web_server.create_earnings_calendar_entry(
                conn,
                symbol,
                fiscal_year=2026,
                fiscal_quarter="Q1",
                release_date="2026-05-07",
            )

    def run_earnings_review_request(self, db_path, account_id=None):
        handler = CapturingHandler()
        with mock.patch.object(web_server, "DB_PATH", db_path):
            web_server.BakingMoneyHandler.handle_earnings_review_get(handler, account_id=account_id)
        return handler.response

    def run_calendar_request(self, db_path, account_id=None):
        handler = CapturingHandler()
        with mock.patch.object(web_server, "DB_PATH", db_path):
            web_server.BakingMoneyHandler.handle_earnings_review_calendar_get(handler, account_id=account_id)
        return handler.response

    def ownership_by_symbol(self, items):
        return {item["symbol"]: item["in_portfolio"] for item in items}

    def test_earnings_calendar_ownership_uses_selected_account_without_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "calendar-ownership.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
                self.seed_account(conn, ACCOUNT_B, positions=[{"symbol": "MSFT", "position": 25}], summary={"net_liquidation": 250_000})
            finally:
                conn.close()

            response_a = self.run_calendar_request(db_path, account_id=ACCOUNT_A)
            response_b = self.run_calendar_request(db_path, account_id=ACCOUNT_B)

            self.assertEqual(response_a["status"], 200)
            self.assertEqual(response_b["status"], 200)
            self.assertTrue(response_a["payload"]["portfolio_data_available"])
            self.assertTrue(response_b["payload"]["portfolio_data_available"])
            self.assertEqual(self.ownership_by_symbol(response_a["payload"]["items"]), {"AMZN": False, "MSFT": False, "NVDA": True})
            self.assertEqual(self.ownership_by_symbol(response_b["payload"]["items"]), {"AMZN": False, "MSFT": True, "NVDA": False})

    def test_earnings_review_ownership_uses_selected_account_without_aggregation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "review-ownership.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
                self.seed_account(conn, ACCOUNT_B, positions=[{"symbol": "MSFT", "position": 25}], summary={"net_liquidation": 250_000})
            finally:
                conn.close()

            response_a = self.run_earnings_review_request(db_path, account_id=ACCOUNT_A)
            response_b = self.run_earnings_review_request(db_path, account_id=ACCOUNT_B)

            self.assertEqual(response_a["status"], 200)
            self.assertEqual(response_b["status"], 200)
            self.assertTrue(response_a["payload"]["portfolio_data_available"])
            self.assertTrue(response_b["payload"]["portfolio_data_available"])
            self.assertEqual(self.ownership_by_symbol(response_a["payload"]["items"]), {"AMZN": False, "MSFT": False, "NVDA": True})
            self.assertEqual(self.ownership_by_symbol(response_b["payload"]["items"]), {"AMZN": False, "MSFT": True, "NVDA": False})

    def test_cross_account_mutation_does_not_change_selected_account_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ownership-mutation.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
                self.seed_account(conn, ACCOUNT_B, positions=[{"symbol": "MSFT", "position": 25}], summary={"net_liquidation": 250_000})
            finally:
                conn.close()

            before = self.ownership_by_symbol(self.run_calendar_request(db_path, account_id=ACCOUNT_A)["payload"]["items"])
            conn = self.open_conn(db_path)
            try:
                self.seed_account(
                    conn,
                    ACCOUNT_B,
                    positions=[{"symbol": "MSFT", "position": 2500}, {"symbol": "AMZN", "position": 999}],
                    summary={"net_liquidation": 9_999_999},
                )
            finally:
                conn.close()
            after = self.ownership_by_symbol(self.run_calendar_request(db_path, account_id=ACCOUNT_A)["payload"]["items"])

            self.assertEqual(after, before)

    def test_unready_account_returns_global_content_with_unknown_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ownership-unready.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
                self.seed_account(conn, ACCOUNT_PENDING)
            finally:
                conn.close()

            calendar = self.run_calendar_request(db_path, account_id=ACCOUNT_PENDING)
            review = self.run_earnings_review_request(db_path, account_id=ACCOUNT_PENDING)

            self.assertEqual(calendar["status"], 200)
            self.assertEqual(review["status"], 200)
            self.assertFalse(calendar["payload"]["portfolio_data_available"])
            self.assertFalse(review["payload"]["portfolio_data_available"])
            self.assertEqual(set(self.ownership_by_symbol(calendar["payload"]["items"]).values()), {None})
            self.assertEqual(set(self.ownership_by_symbol(review["payload"]["items"]).values()), {None})

    def test_ready_account_with_zero_positions_returns_known_false_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ownership-zero-positions.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[], summary={"net_liquidation": 100_000})
            finally:
                conn.close()

            response = self.run_calendar_request(db_path, account_id=ACCOUNT_A)

            self.assertEqual(response["status"], 200)
            self.assertTrue(response["payload"]["portfolio_data_available"])
            self.assertEqual(set(self.ownership_by_symbol(response["payload"]["items"]).values()), {False})

    def test_multiple_accounts_without_selection_returns_global_content_with_unknown_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ownership-no-selection.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
                self.seed_account(conn, ACCOUNT_B, positions=[{"symbol": "MSFT", "position": 25}], summary={"net_liquidation": 250_000})
            finally:
                conn.close()

            response = self.run_calendar_request(db_path)

            self.assertEqual(response["status"], 200)
            self.assertFalse(response["payload"]["portfolio_data_available"])
            self.assertEqual(set(self.ownership_by_symbol(response["payload"]["items"]).values()), {None})

    def test_unknown_account_returns_404_without_global_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ownership-unknown.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
            finally:
                conn.close()

            response = self.run_calendar_request(db_path, account_id="U_TEST_UNKNOWN")

            self.assertEqual(response["status"], 404)
            self.assertEqual(response["payload"]["code"], "account_not_found")
            self.assertNotIn("U_TEST_UNKNOWN", str(response["payload"]))

    def test_single_account_without_account_id_preserves_known_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "ownership-single-account.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
            finally:
                conn.close()

            response = self.run_calendar_request(db_path)

            self.assertEqual(response["status"], 200)
            self.assertTrue(response["payload"]["portfolio_data_available"])
            self.assertEqual(self.ownership_by_symbol(response["payload"]["items"]), {"AMZN": False, "MSFT": False, "NVDA": True})


if __name__ == "__main__":
    unittest.main()
