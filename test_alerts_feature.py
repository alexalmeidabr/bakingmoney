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


if __name__ == "__main__":
    unittest.main()
