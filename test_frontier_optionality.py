import os
import tempfile
import unittest
from unittest import mock

import web_server


def seed_analysis(conn, symbol="NU"):
    now = web_server.utc_now_iso()
    cur = conn.execute(
        "INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)",
        (symbol, now, now),
    )
    conn.execute(
        """
        INSERT INTO analysis_versions (
            analysis_root_id, version_number, symbol, company_name, current_price,
            expected_price, expected_cagr, upside, confidence_level, assumptions_text,
            business_model_text, business_summary_text, raw_ai_response, source_trigger, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cur.lastrowid,
            1,
            symbol,
            "Nu Holdings",
            10.0,
            15.0,
            12.0,
            50.0,
            7.0,
            "Assumptions",
            "Business model",
            "Business summary",
            "{}",
            "test",
            now,
        ),
    )
    conn.commit()


class FrontierOptionalityStorageTests(unittest.TestCase):
    def test_default_frontier_optionality_score_is_zero_in_company_detail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "frontier.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    seed_analysis(conn)
                    detail = web_server.get_analysis_detail(conn, "NU")
                    listed = web_server.list_analysis_symbols(conn)[0]
                finally:
                    conn.close()

        self.assertEqual(detail["frontier_optionality"]["frontier_optionality_score"], 0.0)
        self.assertEqual(detail["frontier_optionality"]["frontier_optionality_notes"], "")
        self.assertEqual(detail["version"]["frontier_optionality_score"], 0.0)
        self.assertEqual(listed["frontier_optionality_score"], 0.0)

    def test_save_frontier_optionality_score_and_notes_persists(self):
        notes = "Fintech platform expansion and product cross-sell."
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "frontier.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    seed_analysis(conn)
                    saved = web_server.save_frontier_optionality(conn, "NU", "2.5", notes)
                    reloaded = web_server.get_frontier_optionality(conn, "NU")
                    stored = conn.execute(
                        "SELECT frontier_optionality_score, frontier_optionality_notes FROM analysis_frontier_optionality WHERE symbol = 'NU'"
                    ).fetchone()
                finally:
                    conn.close()

        self.assertEqual(saved["frontier_optionality"]["frontier_optionality_score"], 2.5)
        self.assertEqual(saved["frontier_optionality"]["frontier_optionality_notes"], notes)
        self.assertEqual(reloaded["frontier_optionality_score"], 2.5)
        self.assertEqual(reloaded["frontier_optionality_notes"], notes)
        self.assertEqual(stored["frontier_optionality_score"], 2.5)
        self.assertEqual(stored["frontier_optionality_notes"], notes)

    def test_blank_frontier_optionality_score_saves_as_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "frontier.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    seed_analysis(conn)
                    saved = web_server.save_frontier_optionality(conn, "NU", "", "")
                finally:
                    conn.close()
        self.assertEqual(saved["frontier_optionality"]["frontier_optionality_score"], 0.0)

    def test_frontier_optionality_setting_default_and_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "settings.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    settings = web_server.get_action_plan_settings(conn)
                finally:
                    conn.close()

        self.assertEqual(settings["linear_frontier_optionality_max_boost_pct"], 10.0)
        self.assertEqual(
            web_server.validate_action_plan_settings({"linear_frontier_optionality_max_boost_pct": 20.0})[
                "linear_frontier_optionality_max_boost_pct"
            ],
            20.0,
        )
        with self.assertRaisesRegex(ValueError, "between 0 and 20"):
            web_server.validate_action_plan_settings({"linear_frontier_optionality_max_boost_pct": -0.1})
        with self.assertRaisesRegex(ValueError, "between 0 and 20"):
            web_server.validate_action_plan_settings({"linear_frontier_optionality_max_boost_pct": 20.1})


if __name__ == "__main__":
    unittest.main()
