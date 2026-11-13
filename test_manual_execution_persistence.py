import os
import tempfile
import unittest
from unittest import mock

import web_server


class ManualExecutionPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = os.path.join(self.temp.name, "manual.db")
        patch = mock.patch.object(web_server, "DB_PATH", self.db_path)
        patch.start()
        self.addCleanup(patch.stop)
        web_server.init_db()
        self.conn = web_server.get_db_connection()
        self.addCleanup(lambda: self.conn.close())
        for account in ("U_ACCOUNT_A", "U_ACCOUNT_B"):
            web_server.upsert_ib_account(self.conn, account)
        self.conn.commit()

    def test_preferences_persist_independently_for_two_accounts_and_survive_reinitialization(self):
        self.assertIn("manual_execution_triggers", {
            row["name"] for row in self.conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        })
        a = web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "nvda", {
            "buy_trigger_price": 80,
            "sell_trigger_price": 120,
            "sell_trigger_direction": "at_or_below",
            "reserve_enabled": True,
            "reserve_percentage": 60,
        })
        b = web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_B", "NVDA", {
            "buy_trigger_price": 75,
            "reserve_enabled": False,
            "reserve_percentage": 0,
        })
        self.assertEqual(a["symbol"], "NVDA")
        self.assertEqual(a["buy_trigger_price"], 80)
        self.assertEqual(a["sell_trigger_direction"], "at_or_below")
        self.assertTrue(a["reserve_enabled"])
        self.assertEqual(b["buy_trigger_price"], 75)
        self.assertEqual(b["sell_trigger_direction"], "at_or_above")
        self.assertEqual(len(web_server.list_manual_execution_triggers(self.conn, "U_ACCOUNT_A")), 1)
        self.assertEqual(len(web_server.list_manual_execution_triggers(self.conn, "U_ACCOUNT_B")), 1)
        now = web_server.utc_now_iso()
        root_id = self.conn.execute(
            "INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES ('NVDA', ?, ?)", (now, now),
        ).lastrowid
        for version in (1, 2):
            self.conn.execute(
                "INSERT INTO analysis_versions (analysis_root_id, version_number, symbol, expected_price, created_at) VALUES (?, ?, 'NVDA', 150, ?)",
                (root_id, version, now),
            )
        self.conn.commit()
        self.assertEqual(web_server.get_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "NVDA")["buy_trigger_price"], 80)

        self.conn.close()
        web_server.init_db()
        self.conn = web_server.get_db_connection()
        saved = web_server.get_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "NVDA")
        self.assertEqual(saved["buy_trigger_price"], 80)
        self.assertEqual(saved["reserve_percentage"], 60)
        self.assertEqual(web_server.get_manual_execution_trigger(self.conn, "U_ACCOUNT_B", "NVDA")["buy_trigger_price"], 75)
        self.assertFalse(web_server.delete_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "MSFT"))
        self.assertTrue(web_server.delete_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "NVDA"))
        self.assertIsNone(web_server.get_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "NVDA"))
        self.assertIsNotNone(web_server.get_manual_execution_trigger(self.conn, "U_ACCOUNT_B", "NVDA"))

    def test_old_database_and_backup_gain_table_without_losing_analysis(self):
        now = web_server.utc_now_iso()
        self.conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES ('AAPL', ?, ?)", (now, now))
        self.conn.execute("DROP TABLE manual_execution_triggers")
        self.conn.commit()
        backup_path = os.path.join(self.temp.name, "old-backup.db")
        web_server._create_db_backup_snapshot(self.db_path, backup_path)
        web_server._validate_backup_db_file(backup_path)
        with mock.patch.object(web_server, "DB_PATH", backup_path):
            web_server.init_db()
            restored = web_server.get_db_connection()
            try:
                self.assertEqual(restored.execute("SELECT COUNT(*) FROM analysis_roots WHERE symbol = 'AAPL'").fetchone()[0], 1)
                self.assertIn("manual_execution_triggers", {
                    row["name"] for row in restored.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                })
            finally:
                restored.close()

    def test_new_backup_restores_saved_account_preferences(self):
        web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "NVDA", {
            "buy_trigger_price": 80, "sell_trigger_price": 120,
            "reserve_enabled": True, "reserve_percentage": 60,
        })
        backup_path = os.path.join(self.temp.name, "new-backup.db")
        web_server._create_db_backup_snapshot(self.db_path, backup_path)
        web_server._validate_backup_db_file(backup_path)
        with mock.patch.object(web_server, "DB_PATH", backup_path):
            web_server.init_db()
            restored = web_server.get_db_connection()
            try:
                saved = web_server.get_manual_execution_trigger(restored, "U_ACCOUNT_A", "NVDA")
                self.assertEqual(saved["buy_trigger_price"], 80)
                self.assertEqual(saved["sell_trigger_price"], 120)
                self.assertEqual(saved["reserve_percentage"], 60)
                self.assertIsNone(web_server.get_manual_execution_trigger(restored, "U_ACCOUNT_B", "NVDA"))
            finally:
                restored.close()

    def test_validation_rejects_invalid_values_and_allows_inactive_reserve_preference(self):
        for symbol, payload in (
            ("", {}),
            ("BAD SYMBOL", {}),
            ("AAPL/../../", {}),
            ("AAPL", {"buy_trigger_price": 0}),
            ("AAPL", {"sell_trigger_price": -1}),
            ("AAPL", {"buy_trigger_price": float("nan")}),
            ("AAPL", {"sell_trigger_price": float("inf")}),
            ("AAPL", {"sell_trigger_direction": "sideways"}),
            ("AAPL", {"sell_trigger_direction": ["at_or_above"]}),
            ("AAPL", {"reserve_percentage": -1}),
            ("AAPL", {"reserve_percentage": 101}),
            ("AAPL", {"reserve_enabled": "yes"}),
        ):
            with self.subTest(symbol=symbol, payload=payload), self.assertRaises(ValueError):
                web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", symbol, payload)
        saved = web_server.save_manual_execution_trigger(self.conn, "U_ACCOUNT_A", "BRK.B", {
            "buy_trigger_price": None, "reserve_enabled": True, "reserve_percentage": 60,
        })
        self.assertIsNone(saved["buy_trigger_price"])
        self.assertTrue(saved["reserve_enabled"])

    def test_account_resolution_rejects_missing_unknown_and_ambiguous_selection(self):
        with self.assertRaises(web_server.PortfolioAccountResolutionError) as ambiguous:
            web_server.resolve_portfolio_account(self.conn, allow_none_when_empty=False)
        self.assertEqual(ambiguous.exception.status, 409)
        with self.assertRaises(web_server.PortfolioAccountResolutionError) as unknown:
            web_server.resolve_portfolio_account(self.conn, "U_MISSING", allow_none_when_empty=False)
        self.assertEqual(unknown.exception.status, 404)

    def test_crud_handlers_return_account_scoped_payloads_and_validation_errors(self):
        class Capture(web_server.BakingMoneyHandler):
            body = None

            def _read_json_body(self):
                return self.body

            def _send_json(self, payload, status=200):
                self.payload = payload
                self.status = status

        capture = Capture.__new__(Capture)
        capture.body = {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 60}
        with mock.patch.object(web_server, "DB_PATH", self.db_path):
            web_server.BakingMoneyHandler.handle_manual_execution_trigger_put(capture, "AAPL", account_id="U_ACCOUNT_A")
            self.assertEqual(capture.status, 200)
            self.assertEqual(capture.payload["trigger"]["buy_trigger_price"], 80)
            web_server.BakingMoneyHandler.handle_manual_execution_triggers_get(capture, account_id="U_ACCOUNT_B")
            self.assertEqual(capture.payload["triggers"], [])
            web_server.BakingMoneyHandler.handle_manual_execution_trigger_get(capture, "AAPL", account_id="U_ACCOUNT_A")
            self.assertEqual(capture.payload["trigger"]["reserve_percentage"], 60)
            web_server.BakingMoneyHandler.handle_manual_execution_trigger_get(capture, "AAPL", account_id="U_ACCOUNT_B")
            self.assertEqual(capture.status, 404)
            capture.body = {"buy_trigger_price": -5}
            web_server.BakingMoneyHandler.handle_manual_execution_trigger_put(capture, "AAPL", account_id="U_ACCOUNT_A")
            self.assertEqual(capture.status, 400)
            web_server.BakingMoneyHandler.handle_manual_execution_triggers_get(capture)
            self.assertEqual(capture.status, 409)
            web_server.BakingMoneyHandler.handle_manual_execution_trigger_delete(capture, "AAPL", account_id="U_ACCOUNT_A")
            self.assertEqual(capture.payload, {"deleted": True})

    def test_crud_handler_returns_json_error_if_database_is_unavailable(self):
        class Capture(web_server.BakingMoneyHandler):
            def _send_json(self, payload, status=200):
                self.payload = payload
                self.status = status

        capture = Capture.__new__(Capture)
        with mock.patch.object(web_server, "get_db_connection", side_effect=RuntimeError("database unavailable")):
            web_server.BakingMoneyHandler.handle_manual_execution_triggers_get(capture, account_id="U_ACCOUNT_A")
        self.assertEqual(capture.status, 500)
        self.assertIn("error", capture.payload)


if __name__ == "__main__":
    unittest.main()
