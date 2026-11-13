import os
import tempfile
import unittest
from unittest import mock

import web_server


class PerformanceStage1Tests(unittest.TestCase):
    def test_init_db_adds_history_indexes_without_removing_existing_records(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(web_server, "DB_PATH", os.path.join(directory, "test.db")):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    for index in ("idx_kv_version_type_category", "idx_scenario_passes_version", "idx_event_checks_symbol_date"):
                        conn.execute(f"DROP INDEX {index}")
                    conn.execute("INSERT INTO recent_event_checks (symbol, checked_at) VALUES ('AAPL', '2026-01-01')")
                    conn.commit()
                finally:
                    conn.close()
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    expected = {
                        "idx_kv_version_type_category": "analysis_version_key_variables",
                        "idx_scenario_passes_version": "analysis_version_scenario_passes",
                        "idx_event_checks_symbol_date": "recent_event_checks",
                    }
                    for name, table in expected.items():
                        self.assertIn(name, [row["name"] for row in conn.execute(f"PRAGMA index_list({table})")])
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM recent_event_checks").fetchone()[0], 1)
                    for sql, index in (
                        ("SELECT AVG(confidence) FROM analysis_version_key_variables WHERE analysis_version_id = 1 AND variable_type = 'Bullish' AND driver_category = 'Core Driver'", "idx_kv_version_type_category"),
                        ("SELECT COUNT(*) FROM analysis_version_scenario_passes WHERE analysis_version_id = 1", "idx_scenario_passes_version"),
                        ("SELECT MAX(checked_at) FROM recent_event_checks WHERE symbol = 'AAPL'", "idx_event_checks_symbol_date"),
                    ):
                        plan = " ".join(row["detail"] for row in conn.execute("EXPLAIN QUERY PLAN " + sql))
                        self.assertIn(index, plan)
                finally:
                    conn.close()

    def test_ownership_only_positions_do_not_calculate_analysis_list(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(web_server, "DB_PATH", os.path.join(directory, "test.db")):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_positions_cache(conn, [{"symbol": "AAPL", "position": 4, "avgCost": 90, "price": 100, "marketValue": 400}], account_id="U_TEST_A")
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 1000, "actual_cash": 600}, account_id="U_TEST_A")
                    web_server.save_positions_cache(conn, [{"symbol": "MSFT", "position": 9, "avgCost": 50, "price": 60, "marketValue": 540}], account_id="U_TEST_B")
                    web_server.save_portfolio_summary_cache(conn, {"net_liquidation": 2000, "actual_cash": 1460}, account_id="U_TEST_B")
                finally:
                    conn.close()
                class Handler:
                    def _send_json(self, payload, status=200):
                        self.payload = payload
                        self.status = status
                handler = Handler()
                with mock.patch.object(web_server, "list_analysis_symbols", side_effect=AssertionError("redundant analysis")):
                    web_server.BakingMoneyHandler.handle_positions_api(handler, account_id="U_TEST_A", ownership_only=True)
                self.assertEqual(handler.payload["positions"], [{"symbol": "AAPL", "position": 4}])
                self.assertTrue(handler.payload["portfolio_data_available"])
                with mock.patch.object(web_server, "list_analysis_symbols", side_effect=AssertionError("redundant analysis")):
                    web_server.BakingMoneyHandler.handle_positions_api(handler, account_id="U_TEST_B", ownership_only=True)
                self.assertEqual(handler.payload["positions"], [{"symbol": "MSFT", "position": 9}])

    def test_backup_snapshot_keeps_history_and_new_indexes(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = os.path.join(directory, "source.db")
            backup_path = os.path.join(directory, "backup.db")
            with mock.patch.object(web_server, "DB_PATH", source_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    conn.execute("INSERT INTO recent_event_checks (symbol, checked_at) VALUES ('AAPL', '2026-01-01')")
                    conn.commit()
                finally:
                    conn.close()
            web_server._create_db_backup_snapshot(source_path, backup_path)
            web_server._validate_backup_db_file(backup_path)
            with mock.patch.object(web_server, "DB_PATH", backup_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM recent_event_checks WHERE symbol = 'AAPL'").fetchone()[0], 1)
                    for name, table in (
                        ("idx_kv_version_type_category", "analysis_version_key_variables"),
                        ("idx_scenario_passes_version", "analysis_version_scenario_passes"),
                        ("idx_event_checks_symbol_date", "recent_event_checks"),
                    ):
                        self.assertIn(name, [row["name"] for row in conn.execute(f"PRAGMA index_list({table})")])
                finally:
                    conn.close()

    def test_synthetic_benchmark_reports_median_and_counts(self):
        from benchmark_stage1 import run
        result = run(symbols=2, versions=2, iterations=3)
        self.assertEqual(result["counts"]["analysis_versions"], 4)
        self.assertEqual(result["counts"]["analysis_version_key_variables"], 16)
        self.assertEqual(result["counts"]["positions_cache"], 2)
        self.assertGreaterEqual(result["analysis_list_ms"], 0)
        self.assertEqual(len(result["event_query_plan"]), 1)

    def test_screen_endpoints_calculate_analysis_once_per_full_response(self):
        from benchmark_stage1 import seed

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(web_server, "DB_PATH", os.path.join(directory, "test.db")):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    seed(conn, symbols=1, versions=1)
                finally:
                    conn.close()

                class Handler:
                    def _send_json(self, payload, status=200):
                        self.payload = payload
                        self.status = status

                handler = Handler()
                original = web_server.list_analysis_symbols
                with mock.patch.object(web_server, "list_analysis_symbols", wraps=original) as analysis_list:
                    web_server.BakingMoneyHandler.handle_analysis_get(handler)
                    self.assertEqual(analysis_list.call_count, 1)
                    self.assertEqual([row["symbol"] for row in handler.payload["analysis"]], ["S00000"])

                    web_server.BakingMoneyHandler.handle_positions_api(handler, account_id="U_BENCHMARK", ownership_only=True)
                    self.assertEqual(analysis_list.call_count, 1)
                    self.assertEqual(handler.payload["positions"], [{"symbol": "S00000", "position": 1.0}])

                    web_server.BakingMoneyHandler.handle_positions_api(handler, account_id="U_BENCHMARK")
                    self.assertEqual(analysis_list.call_count, 2)
                    self.assertEqual(handler.payload["positions"][0]["symbol"], "S00000")
                    self.assertEqual(handler.payload["positions"][0]["marketValue"], 100.0)


if __name__ == "__main__":
    unittest.main()
