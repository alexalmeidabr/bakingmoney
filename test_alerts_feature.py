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


if __name__ == "__main__":
    unittest.main()
