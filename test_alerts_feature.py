import os
import tempfile
import unittest
from unittest import mock

import web_server


class RecentEventPromptTests(unittest.TestCase):
    def test_render_recent_event_prompt_only_substitutes_supported_placeholders(self):
        template = """Symbol: $Symbol\nCompany: $CompanyName\nPrice: $Price\nBusiness: $BusinessModel\nVars: $KeyVariables\nIgnore: $Hidden"""
        rendered = web_server.render_recent_event_prompt(
            template,
            {
                "$Symbol": "NVDA",
                "$CompanyName": "NVIDIA",
                "$Price": "100.00",
                "$BusinessModel": "chips",
                "$KeyVariables": '[{"variable":"demand"}]',
                "$Hidden": "should-not-apply",
            },
        )
        self.assertIn("Symbol: NVDA", rendered)
        self.assertIn("Company: NVIDIA", rendered)
        self.assertIn("Vars: [{\"variable\":\"demand\"}]", rendered)
        self.assertIn("Ignore: $Hidden", rendered)


class AlertsDedupTests(unittest.TestCase):
    def test_duplicate_alert_is_not_inserted_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    context = {"symbol": "NVDA", "company_name": "NVIDIA"}
                    alert = {
                        "alert_type": "Weakens existing variable",
                        "event_summary": "Guidance cut",
                        "impact_summary": "Could pressure growth assumptions",
                        "affected_variables": ["Revenue growth"],
                        "suggested_action": "Review importance/confidence",
                    }
                    inserted_first = web_server.insert_recent_event_alert(conn, context, alert, "prompt", {"alerts": []})
                    inserted_second = web_server.insert_recent_event_alert(conn, context, alert, "prompt", {"alerts": []})
                    self.assertTrue(inserted_first)
                    self.assertFalse(inserted_second)
                    count = conn.execute("SELECT COUNT(*) AS c FROM thesis_review_alerts").fetchone()["c"]
                    self.assertEqual(count, 1)
                finally:
                    conn.close()


class BusinessSummaryEditTests(unittest.TestCase):
    def test_save_business_summary_edit_persists_separately_from_business_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = web_server.utc_now_iso()
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("NVDA", now, now))
                    root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", ("NVDA",)).fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
                            raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (root_id, "NVDA", "NVIDIA", 100.0, 120.0, 20.0, 6.0, "assume", "model", "old summary", "{}", "test", now),
                    )
                    version_id = conn.execute("SELECT id FROM analysis_versions WHERE analysis_root_id = ?", (root_id,)).fetchone()["id"]
                    conn.commit()

                    detail = web_server.save_business_summary_edit(conn, "NVDA", version_id, "new summary")
                    self.assertIsNotNone(detail.get("saved_business_summary_edit"))
                    self.assertEqual(detail["saved_business_summary_edit"]["business_summary"], "new summary")
                    self.assertEqual(detail["saved_business_model_edit"], None)
                finally:
                    conn.close()


class PositionsAnalysisMergeTests(unittest.TestCase):
    def test_merge_positions_with_latest_analysis_attaches_rating_upside_confidence(self):
        positions = [{"symbol": "NVDA", "marketValue": 1000}, {"symbol": "MSFT", "marketValue": 2000}]
        analysis_items = [
            {
                "symbol": "NVDA",
                "rating": "Buy",
                "upside": 25.5,
                "bullish_confidence": 6.8,
                "bearish_confidence": 4.1,
                "confidence_diff": 2.7,
            }
        ]

        merged = web_server.merge_positions_with_latest_analysis(positions, analysis_items)
        nvda = next(item for item in merged if item["symbol"] == "NVDA")
        msft = next(item for item in merged if item["symbol"] == "MSFT")

        self.assertEqual(nvda["rating"], "Buy")
        self.assertEqual(nvda["upside"], 25.5)
        self.assertEqual(nvda["confidence_diff"], 2.7)
        self.assertEqual(msft["rating"], None)
        self.assertEqual(msft["upside"], None)
        self.assertEqual(msft["confidence_diff"], None)

    def test_merge_positions_with_latest_analysis_normalizes_symbol_keys(self):
        positions = [{"symbol": " msft "}]
        analysis_items = [
            {
                "symbol": "MSFT",
                "rating": "Strong Buy",
                "upside": 40.0,
                "bullish_confidence": 7.2,
                "bearish_confidence": 3.1,
                "confidence_diff": 4.1,
            }
        ]
        merged = web_server.merge_positions_with_latest_analysis(positions, analysis_items)
        self.assertEqual(merged[0]["rating"], "Strong Buy")
        self.assertEqual(merged[0]["upside"], 40.0)
        self.assertEqual(merged[0]["confidence_diff"], 4.1)


class PositionsOfflineCacheTests(unittest.TestCase):
    def test_save_and_load_positions_cache_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    rows = [{"symbol": "msft", "position": 10, "price": 100, "avgCost": 80, "changePercent": 1.2, "marketValue": 1000, "unrealizedPnL": 200, "dailyPnL": 10, "currency": "USD"}]
                    web_server.save_positions_cache(conn, rows)
                    loaded = web_server.load_positions_cache(conn)
                    self.assertEqual(len(loaded), 1)
                    self.assertEqual(loaded[0]["symbol"], "MSFT")
                    self.assertEqual(loaded[0]["marketValue"], 1000)
                finally:
                    conn.close()

    def test_compute_unrealized_pnl_percent_from_cost_basis(self):
        row = {"position": 10, "avgCost": 80, "unrealizedPnL": 200}
        value = web_server.compute_unrealized_pnl_percent(row)
        self.assertAlmostEqual(value, 25.0)

    def test_compute_unrealized_pnl_percent_uses_absolute_cost_basis_for_shorts(self):
        row = {"position": -10, "avgCost": 80, "unrealizedPnL": 200}
        value = web_server.compute_unrealized_pnl_percent(row)
        self.assertAlmostEqual(value, 25.0)

    def test_build_positions_payload_enriches_cached_rows(self):
        class DummyConn:
            pass

        rows = [{"symbol": "MSFT", "position": 10, "avgCost": 80, "unrealizedPnL": 200}]
        analysis = [{"symbol": "MSFT", "rating": "Buy", "upside": 22.0, "confidence_diff": 1.2, "bullish_confidence": 6.5, "bearish_confidence": 5.3}]
        with mock.patch.object(web_server, "list_analysis_symbols", return_value=analysis):
            payload = web_server.build_positions_payload(DummyConn(), rows, data_source="cached", warning="offline")

        self.assertEqual(payload["data_source"], "cached")
        self.assertEqual(payload["warning"], "offline")
        self.assertEqual(payload["positions"][0]["rating"], "Buy")
        self.assertEqual(payload["positions"][0]["upside"], 22.0)
        self.assertAlmostEqual(payload["positions"][0]["unrealizedPnLPercent"], 25.0)

    def test_build_positions_payload_with_empty_cache_returns_empty_positions(self):
        class DummyConn:
            pass

        with mock.patch.object(web_server, "list_analysis_symbols", return_value=[]):
            payload = web_server.build_positions_payload(DummyConn(), [], data_source="empty", warning="none")

        self.assertEqual(payload["positions"], [])
        self.assertEqual(payload["data_source"], "empty")


if __name__ == "__main__":
    unittest.main()
