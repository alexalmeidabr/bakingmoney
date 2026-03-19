import json
import os
import sys
import tempfile
import types
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
                "$EventSearchCutoff": "2026-03-10T00:00:00+00:00",
                "$EventCandidates": '[{"event_title":"x"}]',
                "$Hidden": "should-not-apply",
            },
        )
        self.assertIn("Symbol: NVDA", rendered)
        self.assertIn("Company: NVIDIA", rendered)
        self.assertIn("Vars: [{\"variable\":\"demand\"}]", rendered)
        self.assertIn("Ignore: $Hidden", rendered)



    def test_recent_event_candidate_prompt_can_be_saved_loaded_and_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    custom = "Candidate prompt for $Symbol / $CompanyName / $Price / $BusinessModel / $KeyVariables after $EventSearchCutoff"
                    web_server.save_prompt_template(conn, web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE, custom)
                    templates, sources = web_server.get_all_prompt_templates(conn)
                    self.assertEqual(templates[web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE], custom)
                    self.assertEqual(sources[web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE], "custom")
                    web_server.reset_prompt_template(conn, web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE)
                    templates, sources = web_server.get_all_prompt_templates(conn)
                    self.assertIn("$EventSearchCutoff", templates[web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE])
                    self.assertIn("$Price", templates[web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE])
                    self.assertIn("$BusinessModel", templates[web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE])
                    self.assertEqual(sources[web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE], "default")
                finally:
                    conn.close()



    def test_recent_event_candidate_prompt_requires_price_and_business_model_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    invalid = "Candidate prompt for $Symbol $CompanyName $KeyVariables after $EventSearchCutoff"
                    with self.assertRaises(ValueError):
                        web_server.save_prompt_template(conn, web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CANDIDATE, invalid)
                finally:
                    conn.close()

    def test_recent_event_check_prompt_requires_price_and_business_model_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    invalid = "Check prompt for $Symbol $CompanyName $KeyVariables and $EventCandidates"
                    with self.assertRaises(ValueError):
                        web_server.save_prompt_template(conn, web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK, invalid)
                finally:
                    conn.close()

    def test_recent_event_workflow_falls_back_to_default_when_custom_check_prompt_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                        (
                            web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK,
                            "Invalid event check prompt for $Symbol $CompanyName $Price $BusinessModel $KeyVariables",
                            web_server.utc_now_iso(),
                        ),
                    )
                    conn.commit()
                    with self.assertLogs(web_server.logger, level="WARNING") as warning_logs:
                        templates, sources = web_server.get_prompt_templates_for_keys(
                            conn,
                            web_server.RECENT_EVENT_WORKFLOW_PROMPT_KEYS,
                            purpose="recent_event_check_test",
                        )
                    self.assertEqual(
                        sources[web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK],
                        "default",
                    )
                    self.assertEqual(
                        templates[web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK],
                        web_server.get_default_prompt_template(web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK),
                    )
                    self.assertIn("Invalid custom prompt template", "\n".join(warning_logs.output))
                finally:
                    conn.close()

    def test_analysis_workflow_prompt_resolution_behavior_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    custom = "Custom business prompt for $Symbol and $CompanyName"
                    web_server.save_prompt_template(
                        conn,
                        web_server.ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL,
                        custom,
                    )
                    templates, sources = web_server.get_prompt_templates_for_keys(
                        conn,
                        web_server.ANALYSIS_WORKFLOW_PROMPT_KEYS,
                        purpose="initial_analysis_test",
                    )
                    self.assertEqual(
                        templates[web_server.ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL],
                        custom,
                    )
                    self.assertEqual(
                        sources[web_server.ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL],
                        "custom",
                    )
                finally:
                    conn.close()

    def test_prompt_configuration_ui_resolves_all_prompts_with_explicit_purpose_logging(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    with self.assertLogs(web_server.logger, level="INFO") as captured_logs:
                        templates, _sources = web_server.get_all_prompt_templates(conn, purpose="prompt_configuration_ui")
                    joined_logs = "\n".join(captured_logs.output)
                    self.assertIn("purpose=prompt_configuration_ui", joined_logs)
                    self.assertIn(web_server.ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL, joined_logs)
                    self.assertIn(web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK, joined_logs)
                    self.assertIn(web_server.ANALYSIS_PROMPT_SETTING_KEY_RECENT_EVENT_CHECK, templates)
                finally:
                    conn.close()


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
        self.assertAlmostEqual(payload["positions"][0]["costBasis"], 800.0)

    def test_build_positions_payload_with_empty_cache_returns_empty_positions(self):
        class DummyConn:
            pass

        with mock.patch.object(web_server, "list_analysis_symbols", return_value=[]):
            payload = web_server.build_positions_payload(DummyConn(), [], data_source="empty", warning="none")

        self.assertEqual(payload["positions"], [])

    def test_compute_cost_basis_uses_abs_quantity_times_avg_cost(self):
        self.assertEqual(web_server.compute_cost_basis({"position": 10, "avgCost": 80}), 800)
        self.assertEqual(web_server.compute_cost_basis({"position": -10, "avgCost": 80}), 800)
        self.assertIsNone(web_server.compute_cost_basis({"position": 10}))

    def test_fetch_ib_prices_batches_requests_and_cancels_market_data(self):
        class FakeContract:
            def __init__(self, symbol, conid):
                self.symbol = symbol
                self.conId = conid

        class FakeTicker:
            def __init__(self, contract, price):
                self.contract = contract
                self._price = price

            def marketPrice(self):
                return self._price

        class FakeIB:
            def __init__(self):
                self.req_batch_sizes = []
                self.cancelled = []

            def positions(self):
                return []

            def qualifyContracts(self, *contracts):
                return list(contracts)

            def reqTickers(self, *contracts):
                self.req_batch_sizes.append(len(contracts))
                return [FakeTicker(c, 100.0 + idx) for idx, c in enumerate(contracts)]

            def cancelMktData(self, contract):
                self.cancelled.append(contract.conId)

            def sleep(self, _seconds):
                return None

        symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
        conids = {symbol: idx + 1 for idx, symbol in enumerate(symbols)}
        fake_module = types.SimpleNamespace(Stock=lambda symbol, *_args: FakeContract(symbol, conids[symbol]))
        fake_ib = FakeIB()

        with mock.patch.dict(sys.modules, {"ib_insync": fake_module}), \
             mock.patch.object(web_server, "get_ib_connection", return_value=fake_ib), \
             mock.patch.object(web_server, "is_tws_data_enabled", return_value=True), \
             mock.patch.object(web_server, "get_ib_market_data_batch_size", return_value=2), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0):
            prices, warnings = web_server.fetch_ib_prices(symbols)

        self.assertEqual(fake_ib.req_batch_sizes, [2, 2, 1])
        self.assertEqual(len(fake_ib.cancelled), len(symbols))
        self.assertTrue(all(prices[symbol] is not None for symbol in symbols))
        self.assertTrue(all(warnings[symbol] in (None, web_server.NO_PRICE_WARNING) for symbol in symbols))

    def test_fetch_ib_prices_skips_ibkr_when_tws_data_is_disabled(self):
        with mock.patch.object(web_server, "is_tws_data_enabled", return_value=False), \
             mock.patch.object(web_server, "get_ib_connection") as mocked_get_ib:
            prices, warnings = web_server.fetch_ib_prices(["AAPL", "MSFT"])
        mocked_get_ib.assert_not_called()
        self.assertEqual(prices["AAPL"], None)
        self.assertEqual(prices["MSFT"], None)
        self.assertEqual(warnings["AAPL"], web_server.NO_PRICE_WARNING)
        self.assertEqual(warnings["MSFT"], web_server.NO_PRICE_WARNING)

    def test_save_general_configuration_auto_turns_off_use_tws_data_when_ib_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    with mock.patch.object(web_server, "get_ib_connection", side_effect=RuntimeError("down")):
                        web_server.save_general_configuration(conn, {"use_tws_data": True})
                    settings = web_server.get_general_configuration(conn)
                    self.assertFalse(settings["use_tws_data"])
                finally:
                    conn.close()

    def test_overlay_cached_market_fields_fills_missing_live_market_values(self):
        live_rows = [
            {
                "symbol": "AAPL",
                "position": 10,
                "avgCost": 120.0,
                "price": None,
                "marketValue": None,
                "unrealizedPnL": None,
                "unrealizedPnLPercent": None,
                "dailyPnL": None,
                "changePercent": None,
                "currency": None,
            }
        ]
        cached_rows = [
            {
                "symbol": "AAPL",
                "position": 10,
                "avgCost": 120.0,
                "price": 150.0,
                "marketValue": 1500.0,
                "unrealizedPnL": 300.0,
                "unrealizedPnLPercent": 25.0,
                "dailyPnL": 10.0,
                "changePercent": 1.5,
                "currency": "USD",
            }
        ]
        merged = web_server.overlay_cached_market_fields(live_rows, cached_rows)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["price"], 150.0)
        self.assertEqual(merged[0]["marketValue"], 1500.0)
        self.assertEqual(merged[0]["unrealizedPnL"], 300.0)
        self.assertEqual(merged[0]["unrealizedPnLPercent"], 25.0)
        self.assertEqual(merged[0]["dailyPnL"], 10.0)
        self.assertEqual(merged[0]["changePercent"], 1.5)
        self.assertEqual(merged[0]["currency"], "USD")


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

                    candidate_response = {
                        "symbol": "NVDA",
                        "event_candidates": [
                            {
                                "event_title": "Customer delay",
                                "event_summary": "Large customer delayed rollout",
                                "event_date": "2026-03-05",
                                "event_sources": [
                                    {"title": "Delay report", "url": "https://a.com/x", "source_name": "A", "published_at": "2026-03-04"},
                                    {"title": "Delay report", "url": "https://a.com/x", "source_name": "A", "published_at": "2026-03-04"},
                                    {"title": "Supplier note", "url": "https://b.com/y", "source_name": "B", "published_at": "2026-03-03"},
                                    {"title": "Alt source", "url": "https://c.com/z", "source_name": "C", "published_at": "2026-03-06"},
                                ],
                            }
                        ],
                    }
                    eval_response = {
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
                                    {"title": "Supplier note", "url": "https://b.com/y", "source_name": "B", "published_at": "2026-03-03"},
                                    {"title": "Alt source", "url": "https://c.com/z", "source_name": "C", "published_at": "2026-03-06"},
                                ],
                            }
                        ],
                    }
                    with mock.patch.object(web_server, "request_ai_step", side_effect=[candidate_response, eval_response]):
                        summary = web_server.run_recent_event_check(conn, ["NVDA"])

                    self.assertEqual(summary["alerts_created"], 1)
                    alert = conn.execute("SELECT event_date, event_sources_json, search_cutoff_used FROM thesis_review_alerts WHERE symbol = 'NVDA'").fetchone()
                    self.assertEqual(alert["search_cutoff_used"], "2026-03-02T00:00:00+00:00")
                    self.assertEqual(alert["event_date"], "2026-03-03")
                    sources = json.loads(alert["event_sources_json"])
                    self.assertEqual(len(sources), 3)
                finally:
                    conn.close()

    def test_list_analysis_symbols_includes_latest_scenario_or_event_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="NVDA", created_at="2026-03-01T00:00:00+00:00")
                    conn.execute(
                        "INSERT INTO recent_event_checks (symbol, checked_at, cutoff_used, alerts_created_count, events_found_count) VALUES (?, ?, ?, 0, 0)",
                        ("NVDA", "2026-03-05T00:00:00+00:00", None),
                    )
                    conn.commit()
                    rows = web_server.list_analysis_symbols(conn)
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["symbol"], "NVDA")
                    self.assertEqual(rows[0]["last_activity_at"], "2026-03-05T00:00:00+00:00")
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

                    candidate_response = {
                        "symbol": "NVDA",
                        "event_candidates": [
                            {
                                "event_title": "Old event",
                                "event_summary": "Old event",
                                "event_date": "2026-03-09",
                                "event_sources": [{"title": "Old", "url": "https://old", "source_name": "Old", "published_at": "2026-03-09"}],
                            },
                            {
                                "event_title": "New event",
                                "event_summary": "New event",
                                "event_date": "2026-03-11",
                                "event_sources": [{"title": "New", "url": "https://new", "source_name": "New", "published_at": "2026-03-11"}],
                            },
                        ],
                    }
                    eval_response = {
                        "symbol": "NVDA",
                        "alerts": [
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
                    with mock.patch.object(web_server, "request_ai_step", side_effect=[candidate_response, eval_response]):
                        summary = web_server.run_recent_event_check(conn, ["NVDA"])

                    self.assertEqual(summary["alerts_created"], 1)
                    saved = conn.execute("SELECT event_summary, search_cutoff_used FROM thesis_review_alerts").fetchall()
                    self.assertEqual(saved[0]["event_summary"], "New event")
                    self.assertEqual(saved[0]["search_cutoff_used"], "2026-03-10T00:00:00+00:00")
                finally:
                    conn.close()

    def test_recent_event_schemas_include_expected_required_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn)
                    captured = {}

                    def fake_request(step, prompt, schema):
                        captured[step] = schema
                        if step == "recent_event_candidates":
                            return {"symbol": "NVDA", "event_candidates": [{"event_title": "X", "event_summary": "X", "event_date": "2026-03-12", "event_sources": []}]}
                        return {"symbol": "NVDA", "alerts": []}

                    with mock.patch.object(web_server, "request_ai_step", side_effect=fake_request):
                        web_server.run_recent_event_check(conn, ["NVDA"])

                    candidate_required = captured["recent_event_candidates"]["schema"]["properties"]["event_candidates"]["items"]["required"]
                    self.assertIn("event_date", candidate_required)
                    eval_required = captured["recent_event_check"]["schema"]["properties"]["alerts"]["items"]["required"]
                    self.assertIn("event_date", eval_required)
                finally:
                    conn.close()

    def test_event_candidates_placeholder_is_passed_to_evaluation_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn)
                    eval_prompts = []

                    def fake_request(step, prompt, schema):
                        if step == "recent_event_candidates":
                            return {"symbol": "NVDA", "event_candidates": [{"event_title": "Fresh", "event_summary": "Fresh", "event_date": "2026-03-12", "event_sources": []}]}
                        eval_prompts.append(prompt)
                        return {"symbol": "NVDA", "alerts": []}

                    with mock.patch.object(web_server, "request_ai_step", side_effect=fake_request):
                        web_server.run_recent_event_check(conn, ["NVDA"])

                    self.assertTrue(eval_prompts)
                    self.assertIn('"event_title":"Fresh"', eval_prompts[0])
                finally:
                    conn.close()


class AlertsUiStructureTests(unittest.TestCase):
    def test_alerts_list_headers_are_compact(self):
        from pathlib import Path
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('Event Date', html)
        self.assertNotIn('<th>Event</th>', html)

    def test_alerts_status_filter_defaults_to_new(self):
        from pathlib import Path
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('id="alerts-status-filter"', html)
        self.assertIn('<option value="New" selected>New</option>', html)

    def test_alerts_status_filter_supports_all_values(self):
        from pathlib import Path
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('<option value="Reviewed">Reviewed</option>', html)
        self.assertIn('<option value="Dismissed">Dismissed</option>', html)
        self.assertIn('<option value="All">All</option>', html)

    def test_alerts_filter_logic_is_frontend_driven(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn("let alertsStatusFilter = 'New';", js)
        self.assertIn('function getFilteredAlerts()', js)
        self.assertIn("alertsStatusFilterEl.addEventListener('change'", js)
        self.assertIn("let positionSort = { key: 'marketValue', direction: 'desc' };", js)

    def test_alert_detail_next_button_is_wired(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn('function openNextAlertDetail()', js)
        self.assertIn("alertDetailNextBtn.addEventListener('click'", js)
        self.assertIn('function openPreviousAlertDetail()', js)
        self.assertIn("alertDetailPrevBtn.addEventListener('click'", js)
        self.assertIn('advanceAfterUpdate: true', js)
        self.assertIn('backToAlertsFromDetail', js)
        self.assertIn('currentAlertNavigationIds', js)

    def test_prompt_candidate_field_is_wired_in_load_save_and_reset(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn("promptRecentEventCandidatesEl.value = templates.analysis_prompt_recent_event_candidate || ''", js)
        self.assertIn("analysis_prompt_recent_event_candidate: promptRecentEventCandidatesEl.value.trim()", js)
        self.assertIn("promptRecentEventCandidatesEl.value = templates.analysis_prompt_recent_event_candidate || ''", js)

    def test_alert_detail_view_elements_exist(self):
        from pathlib import Path
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('id="prompt-recent-event-candidates"', html)
        self.assertIn('id="alert-detail-view"', html)
        self.assertIn('id="alert-detail-sources"', html)
        self.assertIn('id="alert-detail-review-btn"', html)
        self.assertIn('id="alert-detail-dismiss-btn"', html)
        self.assertIn('id="alert-detail-prev-btn"', html)
        self.assertIn('id="alert-detail-next-btn"', html)
        self.assertIn('id="alert-detail-keyvars-status"', html)
        self.assertIn('id="alert-detail-edit-vars-btn"', html)
        self.assertIn('id="alert-detail-rerun-btn"', html)
        self.assertIn('data-sort-key="confidence_diff" class="sortable">Confidence</th>', html)
        self.assertIn('data-sort-key="last_activity_at" class="sortable">Last Scenario/Event</th>', html)
        self.assertIn('data-sort-key="costBasis" class="sortable">Cost Value</th>', html)
        self.assertIn('id="tws-data-toggle"', html)
        self.assertIn('Data from TWS', html)

    def test_tws_data_toggle_is_wired_in_frontend(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn("const twsDataToggleEl = document.getElementById('tws-data-toggle');", js)
        self.assertIn('async function updateTwsDataToggle(enabled)', js)
        self.assertIn("twsDataToggleEl.addEventListener('change'", js)

    def test_alerts_affected_variables_column_has_wrap_style(self):
        from pathlib import Path
        css = Path('static/styles.css').read_text(encoding='utf-8')
        self.assertIn('#alerts-table th:nth-child(5)', css)
        self.assertIn('white-space: normal;', css)
        self.assertIn('.business-model-editor .table-actions button', css)
        self.assertIn('min-width: 170px;', css)


if __name__ == "__main__":
    unittest.main()
