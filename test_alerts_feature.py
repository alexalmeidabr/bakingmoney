import json
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


class RecentEventAlertEnhancementTests(unittest.TestCase):
    def _seed_analysis(self, conn, symbol='NVDA', created_at='2026-03-01T00:00:00+00:00'):
        now = created_at
        conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", (symbol, now, now))
        root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO analysis_versions (
                analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
                raw_ai_response, source_trigger, created_at
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (root_id, symbol, f"{symbol} Inc.", 100.0, 130.0, 30.0, 6.0, "assume", "model", "summary", "{}", "test", now),
        )
        version_id = conn.execute("SELECT id FROM analysis_versions WHERE analysis_root_id = ?", (root_id,)).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO analysis_version_key_variables (analysis_version_id, variable_text, variable_type, confidence, importance, created_at)
            VALUES (?, 'Demand', 'Growth', 6.0, 7.0, ?)
            """,
            (version_id, now),
        )
        conn.commit()

    def test_recent_event_check_stores_event_date_sources_and_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn)
                    conn.execute(
                        "INSERT INTO recent_event_checks (symbol, checked_at, cutoff_used, alerts_created_count, events_found_count) VALUES (?, ?, ?, 0, 0)",
                        ("NVDA", "2026-03-02T00:00:00+00:00", None),
                    )
                    conn.commit()

                    ai_response = {
                        "symbol": "NVDA",
                        "alerts": [
                            {
                                "alert_type": "Weakens existing variable",
                                "event_date": "2026-03-05",
                                "event_summary": "Large customer delayed rollout",
                                "impact_summary": "Demand ramp could slip",
                                "affected_variables": ["Demand"],
                                "suggested_action": "Review confidence",
                                "event_sources": [
                                    {"title": "Delay report", "url": "https://a.com/x", "source_name": "A", "published_at": "2026-03-04"},
                                    {"title": "Delay report", "url": "https://a.com/x", "source_name": "A", "published_at": "2026-03-04"},
                                    {"title": "Supplier note", "url": "https://b.com/y", "source_name": "B", "published_at": "2026-03-03"},
                                ],
                            },
                            {
                                "alert_type": "Weakens existing variable",
                                "event_date": "2026-03-05",
                                "event_summary": "Large customer delayed rollout",
                                "impact_summary": "Demand ramp could slip",
                                "affected_variables": ["Demand"],
                                "suggested_action": "Review confidence",
                                "event_sources": [
                                    {"title": "Alt source", "url": "https://c.com/z", "source_name": "C", "published_at": "2026-03-06"}
                                ],
                            },
                        ],
                    }
                    with mock.patch.object(web_server, "request_ai_step", return_value=ai_response):
                        summary = web_server.run_recent_event_check(conn, ["NVDA"])

                    self.assertEqual(summary["alerts_created"], 1)
                    alert = conn.execute("SELECT event_date, event_sources_json, search_cutoff_used FROM thesis_review_alerts WHERE symbol = 'NVDA'").fetchone()
                    self.assertEqual(alert["search_cutoff_used"], "2026-03-02T00:00:00+00:00")
                    self.assertEqual(alert["event_date"], "2026-03-03")
                    sources = json.loads(alert["event_sources_json"])
                    self.assertEqual(len(sources), 3)
                finally:
                    conn.close()

    def test_recent_event_check_uses_later_of_last_check_and_latest_scenario_build_for_cutoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, created_at='2026-03-10T00:00:00+00:00')
                    conn.execute(
                        "INSERT INTO recent_event_checks (symbol, checked_at, cutoff_used, alerts_created_count, events_found_count) VALUES (?, ?, ?, 0, 0)",
                        ("NVDA", "2026-03-05T00:00:00+00:00", None),
                    )
                    conn.commit()

                    ai_response = {
                        "symbol": "NVDA",
                        "alerts": [
                            {
                                "alert_type": "Potential new variable",
                                "event_date": "2026-03-09",
                                "event_summary": "Old event",
                                "impact_summary": "Should be filtered",
                                "affected_variables": [],
                                "suggested_action": "None",
                                "event_sources": [{"title": "Old", "url": "https://old", "source_name": "Old", "published_at": "2026-03-09"}],
                            },
                            {
                                "alert_type": "Potential new variable",
                                "event_date": "2026-03-11",
                                "event_summary": "New event",
                                "impact_summary": "Should be kept",
                                "affected_variables": [],
                                "suggested_action": "None",
                                "event_sources": [{"title": "New", "url": "https://new", "source_name": "New", "published_at": "2026-03-11"}],
                            },
                        ],
                    }
                    with mock.patch.object(web_server, "request_ai_step", return_value=ai_response):
                        summary = web_server.run_recent_event_check(conn, ["NVDA"])

                    self.assertEqual(summary["alerts_created"], 1)
                    saved = conn.execute("SELECT event_summary, search_cutoff_used FROM thesis_review_alerts").fetchall()
                    self.assertEqual(saved[0]["event_summary"], "New event")
                    self.assertEqual(saved[0]["search_cutoff_used"], "2026-03-10T00:00:00+00:00")
                finally:
                    conn.close()


class AlertsUiStructureTests(unittest.TestCase):
    def test_alerts_list_headers_are_compact(self):
        from pathlib import Path
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('Event Date', html)
        self.assertNotIn('<th>Event</th>', html)

    def test_alert_detail_view_elements_exist(self):
        from pathlib import Path
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('id="alert-detail-view"', html)
        self.assertIn('id="alert-detail-sources"', html)


if __name__ == "__main__":
    unittest.main()
