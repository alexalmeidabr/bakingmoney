import os
import inspect
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
            web_server.BakingMoneyHandler.handle_earnings_review_get(handler)
        return handler.response

    def run_calendar_request(self, db_path, account_id=None):
        handler = CapturingHandler()
        with mock.patch.object(web_server, "DB_PATH", db_path):
            web_server.BakingMoneyHandler.handle_earnings_review_calendar_get(handler)
        return handler.response

    def assert_no_ownership_fields(self, payload):
        self.assertNotIn("portfolio_data_available", payload)
        for item in payload["items"]:
            self.assertNotIn("in_portfolio", item)
            self.assertNotIn("inPortfolio", item)

    def test_earnings_calendar_is_global_with_multiple_accounts_and_no_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "calendar-global-no-selection.db")
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
            self.assertEqual([item["symbol"] for item in response["payload"]["items"]], ["AMZN", "MSFT", "NVDA"])
            self.assert_no_ownership_fields(response["payload"])

    def test_earnings_calendar_and_review_handlers_do_not_accept_account_scope(self):
        self.assertNotIn("account_id", inspect.signature(web_server.BakingMoneyHandler.handle_earnings_review_get).parameters)
        self.assertNotIn("account_id", inspect.signature(web_server.BakingMoneyHandler.handle_earnings_review_calendar_get).parameters)

    def test_step6_dead_portfolio_ownership_context_helper_is_removed(self):
        self.assertFalse(hasattr(web_server, "_get_portfolio_ownership_context"))

    def test_earnings_review_is_global_with_multiple_accounts_and_no_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "review-global-no-selection.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
                self.seed_account(conn, ACCOUNT_B, positions=[{"symbol": "MSFT", "position": 25}], summary={"net_liquidation": 250_000})
            finally:
                conn.close()

            response = self.run_earnings_review_request(db_path)

            self.assertEqual(response["status"], 200)
            self.assertEqual([item["symbol"] for item in response["payload"]["items"]], ["AMZN", "MSFT", "NVDA"])
            self.assert_no_ownership_fields(response["payload"])

    def test_calendar_and_review_payloads_are_identical_for_different_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "global-payloads-ignore-account.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
                self.seed_account(conn, ACCOUNT_B, positions=[{"symbol": "MSFT", "position": 25}], summary={"net_liquidation": 250_000})
            finally:
                conn.close()

            calendar_a = self.run_calendar_request(db_path, account_id=ACCOUNT_A)
            calendar_b = self.run_calendar_request(db_path, account_id=ACCOUNT_B)
            review_a = self.run_earnings_review_request(db_path, account_id=ACCOUNT_A)
            review_b = self.run_earnings_review_request(db_path, account_id=ACCOUNT_B)

            self.assertEqual(calendar_a["status"], 200)
            self.assertEqual(calendar_b["status"], 200)
            self.assertEqual(review_a["status"], 200)
            self.assertEqual(review_b["status"], 200)
            self.assertEqual(calendar_a["payload"], calendar_b["payload"])
            self.assertEqual(review_a["payload"], review_b["payload"])
            self.assert_no_ownership_fields(calendar_a["payload"])
            self.assert_no_ownership_fields(review_a["payload"])

    def test_changing_positions_does_not_change_calendar_or_review_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "global-payloads-ignore-position-changes.db")
            self.init_db(db_path)
            conn = self.open_conn(db_path)
            try:
                self.seed_earnings_content(conn)
                self.seed_account(conn, ACCOUNT_A, positions=[{"symbol": "NVDA", "position": 100}], summary={"net_liquidation": 100_000})
                self.seed_account(conn, ACCOUNT_B, positions=[{"symbol": "MSFT", "position": 25}], summary={"net_liquidation": 250_000})
            finally:
                conn.close()

            calendar_before = self.run_calendar_request(db_path, account_id=ACCOUNT_A)["payload"]
            review_before = self.run_earnings_review_request(db_path, account_id=ACCOUNT_A)["payload"]
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
            calendar_after = self.run_calendar_request(db_path, account_id=ACCOUNT_A)["payload"]
            review_after = self.run_earnings_review_request(db_path, account_id=ACCOUNT_A)["payload"]

            self.assertEqual(calendar_after, calendar_before)
            self.assertEqual(review_after, review_before)
            self.assert_no_ownership_fields(calendar_after)
            self.assert_no_ownership_fields(review_after)

    def test_unknown_pending_accounts_are_irrelevant_to_global_calendar_and_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "global-pending-account.db")
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
            self.assert_no_ownership_fields(calendar["payload"])
            self.assert_no_ownership_fields(review["payload"])


if __name__ == "__main__":
    unittest.main()
