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
                "expected_price": 125.5,
                "expected_cagr": 4.5,
                "upside_original": 20.0,
                "expected_price_original": 120.0,
                "expected_cagr_original": 3.5,
                "uses_final_scenario_overlay": True,
                "final_scenario_stale": False,
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
        self.assertEqual(nvda["expected_price"], 125.5)
        self.assertEqual(nvda["expected_cagr"], 4.5)
        self.assertEqual(nvda["upside_original"], 20.0)
        self.assertTrue(nvda["uses_final_scenario_overlay"])
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
        self.assertIn("portfolio_summary", payload)
        self.assertEqual(payload["portfolio_summary"]["portfolio_value_source"], "positions_only")

    def test_build_positions_payload_with_empty_cache_returns_empty_positions(self):
        class DummyConn:
            pass

        with mock.patch.object(web_server, "list_analysis_symbols", return_value=[]):
            payload = web_server.build_positions_payload(DummyConn(), [], data_source="empty", warning="none")

        self.assertEqual(payload["positions"], [])
        self.assertIn("portfolio_summary", payload)

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

    def test_extract_price_accepts_positive_fallback_when_market_price_is_invalid(self):
        ticker = types.SimpleNamespace(marketPrice=lambda: -1, last=125.5, close=120.0)
        self.assertEqual(web_server.extract_price(ticker), 125.5)

    def test_extract_price_rejects_non_positive_values(self):
        ticker = types.SimpleNamespace(marketPrice=lambda: 0, last=-1, close=0)
        self.assertIsNone(web_server.extract_price(ticker))

    def test_fetch_ib_prices_ignores_invalid_non_positive_prices(self):
        class FakeContract:
            def __init__(self, symbol, conid):
                self.symbol = symbol
                self.conId = conid

        class FakeTicker:
            def __init__(self, contract, market_price, last, close):
                self.contract = contract
                self._market_price = market_price
                self.last = last
                self.close = close

            def marketPrice(self):
                return self._market_price

        class FakeIB:
            def positions(self):
                return []

            def qualifyContracts(self, *contracts):
                return list(contracts)

            def reqTickers(self, *contracts):
                return [
                    FakeTicker(contracts[0], 101.25, None, None),
                    FakeTicker(contracts[1], 0, -1, 0),
                    FakeTicker(contracts[2], -1, -1, -1),
                ]

            def cancelMktData(self, _contract):
                return None

            def sleep(self, _seconds):
                return None

        symbols = ["AAPL", "MSFT", "NVDA"]
        conids = {symbol: idx + 1 for idx, symbol in enumerate(symbols)}
        fake_module = types.SimpleNamespace(Stock=lambda symbol, *_args: FakeContract(symbol, conids[symbol]))
        fake_ib = FakeIB()

        with mock.patch.dict(sys.modules, {"ib_insync": fake_module}), \
             mock.patch.object(web_server, "get_ib_connection", return_value=fake_ib), \
             mock.patch.object(web_server, "is_tws_data_enabled", return_value=True), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0):
            prices, warnings = web_server.fetch_ib_prices(symbols)

        self.assertEqual(prices["AAPL"], 101.25)
        self.assertEqual(prices["MSFT"], None)
        self.assertEqual(prices["NVDA"], None)
        self.assertEqual(warnings["AAPL"], None)
        self.assertEqual(warnings["MSFT"], web_server.NO_PRICE_WARNING)
        self.assertEqual(warnings["NVDA"], web_server.NO_PRICE_WARNING)

    def test_refresh_latest_analysis_market_prices_preserves_previous_valid_price_on_invalid_tws_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = web_server.utc_now_iso()
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("MSFT", now, now))
                    root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = 'MSFT'").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
                            raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 1, 'MSFT', 'Microsoft', 250.0, 300.0, 20.0, 6.0, 'a', 'b', 'c', '{}', 'test', ?)
                        """,
                        (root_id, now),
                    )
                    conn.commit()

                    with mock.patch.object(
                        web_server,
                        "fetch_ib_prices",
                        return_value=({"MSFT": None}, {"MSFT": web_server.NO_PRICE_WARNING}),
                    ):
                        result = web_server.refresh_latest_analysis_market_prices(conn)

                    row = conn.execute(
                        "SELECT current_price FROM analysis_versions WHERE analysis_root_id = ? AND version_number = 1",
                        (root_id,),
                    ).fetchone()
                    self.assertEqual(row["current_price"], 250.0)
                    self.assertEqual(result["updated"], 0)
                    self.assertEqual(result["skipped"], 1)
                finally:
                    conn.close()

    def test_refresh_latest_analysis_market_prices_with_no_prior_valid_price_keeps_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = web_server.utc_now_iso()
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("NVDA", now, now))
                    root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = 'NVDA'").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
                            raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 1, 'NVDA', 'NVIDIA', NULL, 400.0, NULL, 6.0, 'a', 'b', 'c', '{}', 'test', ?)
                        """,
                        (root_id, now),
                    )
                    conn.commit()

                    with mock.patch.object(
                        web_server,
                        "fetch_ib_prices",
                        return_value=({"NVDA": None}, {"NVDA": web_server.NO_PRICE_WARNING}),
                    ):
                        result = web_server.refresh_latest_analysis_market_prices(conn)

                    row = conn.execute(
                        "SELECT current_price FROM analysis_versions WHERE analysis_root_id = ? AND version_number = 1",
                        (root_id,),
                    ).fetchone()
                    self.assertIsNone(row["current_price"])
                    self.assertEqual(result["updated"], 0)
                    self.assertEqual(result["skipped"], 1)
                finally:
                    conn.close()

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


class RatingCorePotentialConfidenceTests(unittest.TestCase):
    def _settings(self):
        return dict(web_server.DEFAULT_RATING_SETTINGS)

    def test_strong_buy_and_buy_use_core_confidence(self):
        settings = self._settings()
        rating, _ = web_server.calculate_rating(
            65,
            bullish_confidence=2.0,
            bearish_confidence=2.0,
            rating_settings=settings,
            confidence_context={"core_bullish_confidence": 7.5, "core_bearish_confidence": 5.7},
        )
        self.assertEqual(rating, "Strong Buy")

        rating, _ = web_server.calculate_rating(
            35,
            bullish_confidence=8.0,
            bearish_confidence=4.0,
            rating_settings=settings,
            confidence_context={"core_bullish_confidence": 6.0, "core_bearish_confidence": 5.2},
        )
        self.assertEqual(rating, "Buy")

        rating, _ = web_server.calculate_rating(
            35,
            bullish_confidence=8.0,
            bearish_confidence=4.0,
            rating_settings=settings,
            confidence_context={"core_bullish_confidence": 4.0, "core_bearish_confidence": 4.0},
        )
        self.assertEqual(rating, "Hold")

    def test_sell_ratings_use_core_confidence(self):
        settings = self._settings()
        rating, _ = web_server.calculate_rating(
            -5,
            bullish_confidence=8.0,
            bearish_confidence=4.0,
            rating_settings=settings,
            confidence_context={"core_bullish_confidence": 4.0, "core_bearish_confidence": 7.0},
        )
        self.assertEqual(rating, "Strong Sell")

        rating, _ = web_server.calculate_rating(
            5,
            bullish_confidence=8.0,
            bearish_confidence=4.0,
            rating_settings=settings,
            confidence_context={"core_bullish_confidence": 5.2, "core_bearish_confidence": 6.0},
        )
        self.assertEqual(rating, "Sell")

    def test_speculative_buy_core_and_potential_paths_with_core_floor(self):
        settings = self._settings()
        rating, _ = web_server.calculate_rating(
            90,
            bullish_confidence=4.0,
            bearish_confidence=4.0,
            rating_settings=settings,
            confidence_context={"core_bullish_confidence": 4.8, "core_bearish_confidence": 4.6},
        )
        self.assertEqual(rating, "Speculative Buy")

        rating, _ = web_server.calculate_rating(
            110,
            bullish_confidence=4.0,
            bearish_confidence=4.2,
            rating_settings=settings,
            confidence_context={
                "core_bullish_confidence": 4.0,
                "core_bearish_confidence": 4.2,
                "potential_bullish_confidence": 5.5,
                "potential_bearish_confidence": 4.3,
            },
        )
        self.assertEqual(rating, "Speculative Buy")

        rating, _ = web_server.calculate_rating(
            110,
            bullish_confidence=4.0,
            bearish_confidence=5.2,
            rating_settings=settings,
            confidence_context={
                "core_bullish_confidence": 4.0,
                "core_bearish_confidence": 5.2,
                "potential_bullish_confidence": 5.5,
                "potential_bearish_confidence": 4.3,
            },
        )
        self.assertEqual(rating, "Hold")

    def test_speculative_buy_guardrail_and_combined_fallback(self):
        settings = self._settings()
        rating, _ = web_server.calculate_rating(
            100,
            bullish_confidence=1.0,
            bearish_confidence=1.0,
            rating_settings=settings,
            confidence_context={
                "core_bullish_confidence": 1.0,
                "core_bearish_confidence": 1.0,
                "potential_bullish_confidence": 4.6,
                "potential_bearish_confidence": 4.4,
            },
        )
        self.assertEqual(rating, "Speculative Buy")

        rating, _ = web_server.calculate_rating(35, 6.0, 5.2, settings)
        self.assertEqual(rating, "Buy")

    def test_speculative_buy_core_floor_default_and_filter_ui(self):
        self.assertEqual(
            web_server.DEFAULT_RATING_SETTINGS[web_server.RATING_SETTING_SPECULATIVE_BUY_MIN_CORE_DIFF_FLOOR],
            -0.5,
        )
        html = open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8").read()
        js = open(os.path.join(os.path.dirname(__file__), "static", "app.js"), encoding="utf-8").read()
        self.assertIn("config-rating-speculative-buy-min-core-diff-floor", html)
        self.assertIn('value="speculative_buy"', html)
        self.assertIn("Speculative Buy", js)


class ScenarioProbabilityDriverWeightTests(unittest.TestCase):
    def test_effective_potential_driver_weight_formula_and_cap(self):
        weight_meta = web_server.calculate_effective_potential_driver_probability_weight([
            {"variable_type": "Bullish", "driver_category": "Potential Driver", "confidence": 5, "importance": 8},
        ])
        self.assertAlmostEqual(weight_meta["effective_potential_driver_probability_weight"], 0.10)
        self.assertEqual(weight_meta["median_potential_confidence"], 5)
        self.assertEqual(weight_meta["median_potential_importance"], 8)

        capped = web_server.calculate_effective_potential_driver_probability_weight([
            {"variable_type": "Bullish", "driver_category": "Potential Driver", "confidence": 10, "importance": 10},
        ])
        self.assertAlmostEqual(capped["effective_potential_driver_probability_weight"], 0.25)

        low_confidence = web_server.calculate_effective_potential_driver_probability_weight([
            {"variable_type": "Bullish", "driver_category": "Potential Driver", "confidence": 2.9, "importance": 10},
        ])
        self.assertEqual(low_confidence["effective_potential_driver_probability_weight"], 0.0)

    def test_backend_probabilities_with_only_core_match_legacy_shape(self):
        variables = [
            {"variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8, "importance": 10},
            {"variable_type": "Bearish", "driver_category": "Core Driver", "confidence": 4, "importance": 10},
        ]
        details = web_server.compute_backend_probability_details(variables, 60.0, 35.0)
        self.assertEqual(details["meta"]["effective_potential_driver_probability_weight"], 0.0)
        self.assertEqual(details["meta"]["core_bull_score"], 80.0)
        self.assertEqual(details["meta"]["core_bear_score"], 40.0)
        self.assertAlmostEqual(details["probabilities"]["Bull"], 32.22)
        self.assertAlmostEqual(details["probabilities"]["Bear"], 16.11)
        self.assertAlmostEqual(details["probabilities"]["Base"], 51.67)

    def test_missing_category_defaults_to_core_for_backend_probabilities(self):
        categorized = web_server.compute_backend_probabilities([
            {"variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8, "importance": 10},
            {"variable_type": "Bearish", "driver_category": "Core Driver", "confidence": 4, "importance": 10},
        ], 60.0, 35.0)
        legacy = web_server.compute_backend_probabilities([
            {"variable_type": "Bullish", "confidence": 8, "importance": 10},
            {"variable_type": "Bearish", "driver_category": "Invalid", "confidence": 4, "importance": 10},
        ], 60.0, 35.0)
        self.assertEqual(legacy, categorized)

    def test_potential_drivers_apply_adaptive_backend_weight(self):
        details = web_server.compute_backend_probability_details([
            {"variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8, "importance": 10},
            {"variable_type": "Bearish", "driver_category": "Core Driver", "confidence": 4, "importance": 10},
            {"variable_type": "Bullish", "driver_category": "Potential Driver", "confidence": 5, "importance": 8},
            {"variable_type": "Bullish", "driver_category": "Potential Driver", "confidence": 5, "importance": 8},
        ], 60.0, 35.0)
        self.assertAlmostEqual(details["meta"]["effective_potential_driver_probability_weight"], 0.10)
        self.assertAlmostEqual(details["meta"]["potential_bull_raw_score"], 80.0)
        self.assertAlmostEqual(details["meta"]["potential_bull_weighted_score"], 8.0)
        self.assertAlmostEqual(details["meta"]["bull_score"], 88.0)
        core_only = web_server.compute_backend_probabilities([
            {"variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8, "importance": 10},
            {"variable_type": "Bearish", "driver_category": "Core Driver", "confidence": 4, "importance": 10},
        ], 60.0, 35.0)
        self.assertGreater(details["probabilities"]["Bull"], core_only["Bull"])

    def test_hybrid_mode_blends_ai_with_weighted_backend_probabilities(self):
        backend = web_server.compute_backend_probabilities([
            {"variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8, "importance": 10},
            {"variable_type": "Bearish", "driver_category": "Core Driver", "confidence": 4, "importance": 10},
        ], 60.0, 35.0)
        result = web_server.choose_final_probabilities(
            {"Bear": 30.0, "Base": 40.0, "Bull": 30.0},
            backend,
            {"probability_source_mode": "hybrid", "hybrid_ai_weight": 0.7, "hybrid_backend_weight": 0.3},
        )
        expected = web_server.blend_probabilities({"Bear": 30.0, "Base": 40.0, "Bull": 30.0}, backend, 0.7, 0.3)
        self.assertEqual(result["final_scenario_probabilities"], expected)

    def test_default_build_scenarios_prompt_contains_phase3_guidance(self):
        prompt = web_server.DEFAULT_PROMPT_SCENARIOS
        self.assertIn("Core vs Potential Driver scenario treatment:", prompt)
        self.assertIn("Core Drivers should dominate the Base case, normal execution assumptions, and the central business trajectory.", prompt)
        self.assertIn("Potential Drivers should mainly affect Bull/Bear optionality and scenario range.", prompt)
        self.assertIn("assumptions should be concise and reflect the 5-year business thesis behind the scenarios", prompt)


class KeyVariableDriverCategoryTests(unittest.TestCase):
    def test_save_key_variable_edits_preserves_driver_category_and_defaults_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = "2026-05-01T00:00:00+00:00"
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("NVDA", now, now))
                    root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = 'NVDA'").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            expected_cagr, upside, confidence_level, assumptions_text, business_model_text,
                            business_summary_text, raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 1, 'NVDA', 'NVIDIA', 100, 130, 5, 30, 6, 'assume', 'model', 'summary', '{}', 'test', ?)
                        """,
                        (root_id, now),
                    )
                    version_id = conn.execute("SELECT id FROM analysis_versions WHERE analysis_root_id = ?", (root_id,)).fetchone()["id"]
                    conn.commit()

                    detail = web_server.save_key_variable_edits(
                        conn,
                        "NVDA",
                        version_id,
                        [
                            {"variable_text": "AI accelerator demand", "variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8, "importance": 9},
                            {"variable_text": "New robotics optionality", "variable_type": "Bullish", "driver_category": "Potential Driver", "confidence": 4, "importance": 8},
                            {"variable_text": "Export controls", "variable_type": "Bearish", "confidence": 5, "importance": 7},
                        ],
                    )

                    saved = detail["saved_key_variable_edits"]["key_variables"]
                    self.assertEqual(saved[0]["driver_category"], "Core Driver")
                    self.assertEqual(saved[1]["driver_category"], "Potential Driver")
                    self.assertEqual(saved[2]["driver_category"], "Core Driver")
                finally:
                    conn.close()

    def test_import_key_variable_edits_replaces_saved_variables_with_strict_json_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = "2026-05-01T00:00:00+00:00"
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("NVDA", now, now))
                    root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = 'NVDA'").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            expected_cagr, upside, confidence_level, assumptions_text, business_model_text,
                            business_summary_text, raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 1, 'NVDA', 'NVIDIA', 100, 130, 5, 30, 6, 'assume', 'model', 'summary', '{}', 'test', ?)
                        """,
                        (root_id, now),
                    )
                    version_id = conn.execute("SELECT id FROM analysis_versions WHERE analysis_root_id = ?", (root_id,)).fetchone()["id"]
                    conn.commit()

                    web_server.save_key_variable_edits(
                        conn,
                        "NVDA",
                        version_id,
                        [{"variable_text": "Old driver", "variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 5, "importance": 5}],
                    )
                    detail = web_server.import_key_variable_edits(
                        conn,
                        "NVDA",
                        version_id,
                        {
                            "symbol": "NVDA",
                            "key_variables": [
                                {"variable": "Imported core demand", "type": "Bullish", "driver_category": "Core Driver", "confidence": 8, "importance": 9},
                                {"variable": "Imported optional risk", "type": "Bearish", "driver_category": "Potential Driver", "confidence": 4, "importance": 7},
                            ],
                        },
                    )
                    saved = detail["saved_key_variable_edits"]["key_variables"]
                    self.assertEqual([item["variable_text"] for item in saved], ["Imported core demand", "Imported optional risk"])
                    self.assertEqual(saved[1]["driver_category"], "Potential Driver")
                    self.assertEqual(saved[1]["variable_type"], "Bearish")
                finally:
                    conn.close()

    def test_import_key_variable_edits_allows_more_than_twenty_variables(self):
        payload = {
            "key_variables": [
                {
                    "variable": f"Imported driver {index}",
                    "type": "Bullish" if index % 2 == 0 else "Bearish",
                    "driver_category": "Core Driver" if index % 3 else "Potential Driver",
                    "confidence": index % 11,
                    "importance": (index + 1) % 11,
                }
                for index in range(25)
            ]
        }

        normalized = web_server._normalize_imported_key_variables_payload(payload)

        self.assertEqual(len(normalized), 25)
        self.assertEqual(normalized[0]["variable_text"], "Imported driver 0")
        self.assertEqual(normalized[0]["driver_category"], "Potential Driver")
        self.assertEqual(normalized[-1]["variable_text"], "Imported driver 24")

    def test_import_key_variable_edits_rejects_invalid_rows(self):
        with self.assertRaisesRegex(web_server.AnalysisValidationError, "key_variables must be an array"):
            web_server.import_key_variable_edits(None, "NVDA", 1, {"key_variables": "bad"})
        with self.assertRaisesRegex(web_server.AnalysisValidationError, "key_variables must contain at least 1 item"):
            web_server._normalize_imported_key_variables_payload({"key_variables": []})
        with self.assertRaisesRegex(web_server.AnalysisValidationError, "Row 1: type must be Bullish or Bearish"):
            web_server._normalize_imported_key_variables_payload({"key_variables": [{"variable": "Driver", "type": "bullish", "driver_category": "Core Driver", "confidence": 5, "importance": 5}]})
        with self.assertRaisesRegex(web_server.AnalysisValidationError, "Row 1: driver_category must be Core Driver or Potential Driver"):
            web_server._normalize_imported_key_variables_payload({"key_variables": [{"variable": "Driver", "type": "Bullish", "driver_category": "core driver", "confidence": 5, "importance": 5}]})
        with self.assertRaisesRegex(web_server.AnalysisValidationError, "Row 1: confidence must be an integer from 0 to 10"):
            web_server._normalize_imported_key_variables_payload({"key_variables": [{"variable": "Driver", "type": "Bullish", "driver_category": "Core Driver", "confidence": 5.5, "importance": 5}]})

    def test_save_key_variable_edits_rejects_invalid_driver_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    with self.assertRaises(web_server.AnalysisValidationError):
                        web_server.save_key_variable_edits(
                            conn,
                            "NVDA",
                            1,
                            [{"variable_text": "Driver", "variable_type": "Bullish", "driver_category": "Speculative", "confidence": 5, "importance": 5}],
                        )
                finally:
                    conn.close()

    def test_analysis_payloads_include_core_and_potential_confidence_breakdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = "2026-05-01T00:00:00+00:00"
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("NVDA", now, now))
                    root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = 'NVDA'").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            expected_cagr, upside, confidence_level, assumptions_text, business_model_text,
                            business_summary_text, raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 1, 'NVDA', 'NVIDIA', 100, 130, 5, 30, 6, 'assume', 'model', 'summary', '{}', 'test', ?)
                        """,
                        (root_id, now),
                    )
                    version_id = conn.execute("SELECT id FROM analysis_versions WHERE analysis_root_id = ?", (root_id,)).fetchone()["id"]
                    conn.executemany(
                        """
                        INSERT INTO analysis_version_key_variables (
                            analysis_version_id, variable_text, variable_type, driver_category, confidence, importance, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (version_id, "Core demand", "Bullish", "Core Driver", 8.0, 3.0, now),
                            (version_id, "Core competition", "Bearish", "Core Driver", 6.0, 2.0, now),
                            (version_id, "Emerging platform", "Bullish", "Potential Driver", 4.0, 4.0, now),
                            (version_id, "Emerging risk", "Bearish", "Potential Driver", 3.0, 1.0, now),
                        ],
                    )
                    conn.commit()

                    analysis_row = web_server.list_analysis_symbols(conn)[0]
                    self.assertEqual(analysis_row["core_bullish_confidence"], 8.0)
                    self.assertEqual(analysis_row["core_bearish_confidence"], 6.0)
                    self.assertEqual(analysis_row["core_confidence_diff"], 2.0)
                    self.assertEqual(analysis_row["potential_bullish_confidence"], 4.0)
                    self.assertEqual(analysis_row["potential_bearish_confidence"], 3.0)
                    self.assertEqual(analysis_row["potential_confidence_diff"], 1.0)
                    self.assertIn("confidence_diff", analysis_row)

                    detail = web_server.get_analysis_detail(conn, "NVDA")
                    version = detail["version"]
                    self.assertEqual(version["core_confidence_diff"], 2.0)
                    self.assertEqual(version["potential_confidence_diff"], 1.0)

                    merged = web_server.merge_positions_with_latest_analysis(
                        [{"symbol": "NVDA", "position": 1}],
                        [analysis_row],
                    )[0]
                    self.assertEqual(merged["core_confidence_diff"], 2.0)
                    self.assertEqual(merged["potential_confidence_diff"], 1.0)
                finally:
                    conn.close()

    def test_old_key_variables_without_driver_category_are_treated_as_core_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = "2026-05-01T00:00:00+00:00"
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("MSFT", now, now))
                    root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = 'MSFT'").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            expected_cagr, upside, confidence_level, assumptions_text, business_model_text,
                            business_summary_text, raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 1, 'MSFT', 'Microsoft', 100, 120, 4, 20, 6, 'assume', 'model', 'summary', '{}', 'test', ?)
                        """,
                        (root_id, now),
                    )
                    version_id = conn.execute("SELECT id FROM analysis_versions WHERE analysis_root_id = ?", (root_id,)).fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_version_key_variables (
                            analysis_version_id, variable_text, variable_type, confidence, importance, created_at
                        ) VALUES (?, 'Legacy demand', 'Bullish', 7.0, 2.0, ?)
                        """,
                        (version_id, now),
                    )
                    conn.commit()

                    analysis_row = web_server.list_analysis_symbols(conn)[0]
                    self.assertEqual(analysis_row["core_bullish_confidence"], 7.0)
                    self.assertIsNone(analysis_row["potential_bullish_confidence"])
                    self.assertIsNone(analysis_row["potential_confidence_diff"])
                finally:
                    conn.close()


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
        self.assertIn('id="alert-detail-open-analysis-btn"', html)
        self.assertIn('id="alert-detail-edit-vars-btn"', html)
        self.assertIn('id="alert-detail-rerun-btn"', html)
        self.assertIn('id="analysis-import-variables-btn"', html)
        self.assertIn('id="analysis-key-variable-import-modal"', html)
        self.assertIn('id="analysis-key-variable-import-template-btn"', html)
        self.assertIn('id="analysis-key-variable-import-save-btn"', html)
        self.assertIn('data-sort-key="core_confidence_diff" class="sortable">Confidence</th>', html)
        self.assertIn('data-sort-key="potential_confidence_diff" class="sortable">Potential Confidence</th>', html)
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn('<td>${formatPotentialConfidenceDisplay(item)}</td>', js)
        self.assertIn('const potentialConfidenceValue = formatPotentialConfidenceDisplay(position);', js)
        self.assertIn('function parseKeyVariableImportPayload()', js)
        self.assertIn('/key-variables/import', js)
        self.assertIn('This will replace the current key variables for this analysis version. Continue?', js)
        self.assertIn('data-sort-key="last_activity_at" class="sortable">Last Scenario/Event</th>', html)
        self.assertIn('data-sort-key="costBasis" class="sortable">Cost Value</th>', html)
        self.assertIn('id="tws-data-toggle"', html)
        self.assertIn('Data from TWS', html)
        self.assertIn('data-view="action-plan"', html)
        self.assertIn('id="action-plan-table"', html)
        self.assertIn('Action Amount', html)
        self.assertIn('Cash-like Available', js)
        self.assertIn('Unallocated Target Capacity', js)
        self.assertIn('id="positions-portfolio-summary"', html)
        self.assertIn('id="config-action-cash-equivalent-symbols"', html)
        self.assertIn('id="config-action-treat-cash-equivalents-as-cash"', html)
        self.assertIn('id="action-plan-detail-view"', html)
        self.assertIn('id="action-plan-open-analysis-btn"', html)
        self.assertIn('Open Full Analysis', html)
        self.assertIn('id="action-plan-rating-filter"', html)
        self.assertIn('id="action-plan-action-filter"', html)
        self.assertIn('Action Filter', html)
        self.assertIn('Starter Buy', html)
        self.assertIn('data-action-plan-setting="action_bucket_buy_target"', html)
        self.assertIn('async function loadActionPlan()', js)
        self.assertIn('/api/action-plan', js)
        self.assertIn('function getFilteredActionPlanItems()', js)
        self.assertIn('function openActionPlanDetail(symbol)', js)
        self.assertIn('/api/action-plan/${encodeURIComponent(symbol)}', js)
        self.assertIn('function renderActionPlanDetail(item)', js)
        self.assertIn('action_amount_label', js)
        self.assertIn('setSelectedActionPlanRatings(getAllRatingFilterKeys())', js)
        self.assertIn('setSelectedActionPlanActions(getAllActionPlanActionFilterKeys())', js)
        self.assertIn('selectedActions.has(ACTION_PLAN_ACTION_FILTER_KEY_BY_LABEL[item.action', js)
        self.assertIn('openActionPlanDetail(btn.dataset.symbol)', js)
        self.assertIn("openAnalysisDetailForSymbol(selectedActionPlanDetail.symbol, { origin: 'action_plan' })", js)
        self.assertIn("analysisDetailOrigin === 'action_plan'", js)
        self.assertIn('← Back to Action Plan', js)
        self.assertIn("setView('action-plan', { skipLoad: true })", js)

    def test_tws_data_toggle_is_wired_in_frontend(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn("const twsDataToggleEl = document.getElementById('tws-data-toggle');", js)
        self.assertIn('async function updateTwsDataToggle(enabled)', js)
        self.assertIn("twsDataToggleEl.addEventListener('change'", js)
        self.assertIn('function shouldRetryTwsPositionsRefresh(payload)', js)
        self.assertIn('function shouldRetryTwsAnalysisPriceRefresh(payload)', js)
        self.assertIn("Connecting to TWS… retrying refresh once.", js)
        self.assertIn("Connecting to TWS… retrying price refresh once.", js)
        self.assertIn('refreshBtn.disabled = true;', js)
        self.assertIn('analysisRefreshPricesBtn.disabled = true;', js)
        self.assertIn("alertDetailOpenAnalysisBtn.addEventListener('click'", js)

    def test_alerts_affected_variables_column_has_wrap_style(self):
        from pathlib import Path
        css = Path('static/styles.css').read_text(encoding='utf-8')
        self.assertIn('#alerts-table th:nth-child(5)', css)
        self.assertIn('white-space: normal;', css)
        self.assertIn('.business-model-editor .table-actions button', css)
        self.assertIn('min-width: 170px;', css)
        self.assertIn('.alert-var-text', css)
        self.assertIn('min-width: 420px;', css)

    def test_positions_column_sequence_matches_expected_order(self):
        from pathlib import Path
        html = Path('static/index.html').read_text(encoding='utf-8')
        expected = [
            'data-sort-key="symbol" class="sortable">Symbol</th>',
            'data-sort-key="rating" class="sortable">Rating</th>',
            'data-sort-key="upside" class="sortable">Upside</th>',
            'data-sort-key="core_confidence_diff" class="sortable">Confidence</th>',
            'data-sort-key="potential_confidence_diff" class="sortable">Potential Confidence</th>',
            'data-sort-key="marketValue" class="sortable">Market Value</th>',
            'data-sort-key="costBasis" class="sortable">Cost Value</th>',
            'data-sort-key="unrealizedPnL" class="sortable">Unrealized P&amp;L</th>',
            'data-sort-key="unrealizedPnLPercent" class="sortable">Unrealized P&amp;L %</th>',
            'data-sort-key="price" class="sortable">Price</th>',
            'data-sort-key="avgCost" class="sortable">Avg Cost</th>',
            'data-sort-key="dailyPnL" class="sortable">Daily P&amp;L</th>',
            'data-sort-key="changePercent" class="sortable">Change %</th>',
        ]
        positions = [html.index(fragment) for fragment in expected]
        self.assertEqual(positions, sorted(positions))

    def test_earnings_review_has_separate_list_and_detail_views(self):
        from pathlib import Path
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('id="earnings-review-list-view"', html)
        self.assertIn('id="earnings-review-symbol-view"', html)
        self.assertIn('id="earnings-review-detail-view"', html)
        self.assertIn('id="earnings-review-back-btn"', html)
        self.assertIn('id="earnings-review-symbol-back-btn"', html)
        self.assertIn('id="earnings-review-detail-header"', html)
        self.assertIn('id="earnings-review-add-symbol"', html)
        self.assertIn('id="earnings-review-add-btn"', html)
        self.assertIn('id="earnings-review-tab-workflow"', html)
        self.assertIn('id="earnings-review-tab-calendar"', html)
        self.assertIn('id="earnings-calendar-table"', html)
        self.assertIn('id="earnings-calendar-status"', html)
        self.assertIn('value="past" /> <span class="rating-filter-option-label">Past</span>', html)
        self.assertIn('value="yesterday" /> <span class="rating-filter-option-label">Yesterday</span>', html)
        self.assertIn('value="today" /> <span class="rating-filter-option-label">Today</span>', html)
        self.assertIn('value="tomorrow" /> <span class="rating-filter-option-label">Tomorrow</span>', html)
        self.assertIn('value="future" /> <span class="rating-filter-option-label">Future</span>', html)
        self.assertLess(html.index('value="past"'), html.index('value="yesterday"'))
        self.assertLess(html.index('value="yesterday"'), html.index('value="today"'))
        self.assertLess(html.index('value="today"'), html.index('value="tomorrow"'))
        self.assertLess(html.index('value="tomorrow"'), html.index('value="future"'))
        css = Path('static/styles.css').read_text(encoding='utf-8')
        self.assertIn('#earnings-calendar-date-filter .rating-filter-panel', css)
        self.assertIn('width: min(280px, calc(100vw - 48px));', css)
        self.assertIn('min-width: min(260px, calc(100vw - 48px));', css)
        self.assertIn('padding: 12px;', css)
        self.assertIn('#earnings-calendar-date-filter .rating-filter-option {', css)
        self.assertIn('display: flex;', css)
        self.assertIn('justify-content: flex-start;', css)
        self.assertIn('gap: 10px;', css)
        self.assertIn('#earnings-calendar-date-filter .rating-filter-option-label', css)
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn("{ key: 'yesterday', label: 'Yesterday' }", js)
        self.assertIn("{ key: 'tomorrow', label: 'Tomorrow' }", js)
        self.assertIn('function releaseDateMatchesEarningsCalendarDateFilters(releaseDateValue, today, selectedDateFilters)', js)
        self.assertIn("if (selectedDateFilters.has('past') && releaseTime < todayTime) return true;", js)
        self.assertIn("if (selectedDateFilters.has('yesterday') && releaseTime === yesterday.getTime()) return true;", js)
        self.assertIn("if (selectedDateFilters.has('tomorrow') && releaseTime === tomorrow.getTime()) return true;", js)
        self.assertIn("if (selectedDateFilters.has('future') && releaseTime > todayTime) return true;", js)
        self.assertIn('<th>Portfolio</th>', html)
        self.assertIn('<th>Latest Quarter</th>', html)
        self.assertIn('id="earnings-review-document-type"', html)
        self.assertIn('id="earnings-review-document-file"', html)
        self.assertIn('id="earnings-review-document-choose-btn"', html)
        self.assertIn('id="earnings-review-document-file-name"', html)
        self.assertIn('id="earnings-review-analyse-btn"', html)
        self.assertIn('id="earnings-review-document-upload-btn"', html)
        self.assertIn('id="earnings-review-documents-table"', html)
        self.assertIn('<th>Delete</th>', html)
        self.assertLess(html.index('<h4>Earnings Documents</h4>'), html.index('<h4>Key Variables Snapshot</h4>'))
        self.assertIn('id="prompt-earnings-watchpoint-analysis"', html)

    def test_external_scenario_create_prefills_notes_with_local_date_without_overwriting_edits(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn('function formatLocalDateForExternalScenarioNotes(dateValue = new Date())', js)
        self.assertIn(
            "analysisExternalScenarioNotesEl.value = item ? (item.source_notes || '') : formatLocalDateForExternalScenarioNotes();",
            js,
        )
        self.assertIn("{ name: 'Bear', price_low: 80, price_high: 100, probability: 25 }", js)
        self.assertNotIn("{ name: 'Bear', price_low: 80, price_high: 100, cagr_low", js)

    def test_external_scenario_bakingmoney_tab_is_not_forced_back_to_final(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        html = Path('static/index.html').read_text(encoding='utf-8')
        self.assertIn('data-scenario-tab="bakingmoney"', html)
        self.assertIn("button.addEventListener('click', () => setScenarioOverlayTab(button.dataset.scenarioTab));", js)
        self.assertIn("analysisBakingMoneyScenarioPanelEl.classList.toggle('hidden', hasExternal && activeScenarioOverlayTab !== 'bakingmoney');", js)
        self.assertNotIn("activeScenarioOverlayTab === 'bakingmoney') activeScenarioOverlayTab = 'final'", js)

    def test_earnings_review_navigation_uses_view_state_and_hash(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn('function showEarningsReviewList()', js)
        self.assertIn('function showEarningsReviewDetail()', js)
        self.assertIn('function setEarningsReviewHash(symbol, reviewId = null)', js)
        self.assertIn('function openEarningsReviewSymbolHistory(symbol)', js)
        self.assertIn('function openEarningsReviewRecordDetail(symbol, reviewId)', js)
        self.assertIn('function addEarningsReviewSymbol()', js)
        self.assertIn('function loadEarningsCalendar()', js)
        self.assertIn('function renderEarningsCalendarTable()', js)
        self.assertIn('function openAnalysisDetailFromPositions(symbol)', js)
        self.assertIn('function uploadEarningsReviewDocument()', js)
        self.assertIn('function deleteEarningsReviewDocument(', js)
        self.assertIn('function renderEarningsReviewDocuments(', js)
        self.assertIn('function analyseEarningsWatchpoints()', js)
        self.assertIn('earningsReviewDocumentChooseBtn.addEventListener(\'click\'', js)
        self.assertIn('earningsReviewDocumentFileEl.addEventListener(\'change\'', js)
        self.assertIn('earningsReviewAnalyseBtn.addEventListener(\'click\', analyseEarningsWatchpoints);', js)
        self.assertIn('earningsReviewAddBtn.addEventListener(\'click\', addEarningsReviewSymbol);', js)
        self.assertIn('earningsReviewTabCalendarBtn.addEventListener(\'click\'', js)
        self.assertIn('function deleteEarningsReviewRecord(', js)
        self.assertIn('earnings-record-delete-btn', js)
        self.assertIn('window.addEventListener(\'hashchange\'', js)


class EarningsReviewTests(unittest.TestCase):
    def _seed_analysis(self, conn, symbol="MSFT"):
        now = web_server.utc_now_iso()
        conn.execute(
            "INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)",
            (symbol, now, now),
        )
        root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO analysis_versions (
                analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
                raw_ai_response, source_trigger, created_at
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (root_id, symbol, f"{symbol} Inc.", 100.0, 120.0, 20.0, 6.0, "assume", "business model", "business summary", "{}", "test", now),
        )
        version_id = conn.execute(
            "SELECT id FROM analysis_versions WHERE analysis_root_id = ? ORDER BY version_number DESC LIMIT 1",
            (root_id,),
        ).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO analysis_version_key_variables (
                analysis_version_id, variable_text, variable_type, confidence, importance, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (version_id, "Cloud demand growth", "Bullish", 7.0, 8.0, now),
        )
        conn.execute(
            """
            INSERT INTO analysis_version_key_variables (
                analysis_version_id, variable_text, variable_type, confidence, importance, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (version_id, "Gross margin pressure", "Bearish", 5.0, 7.0, now),
        )
        conn.commit()

    def test_earnings_prompt_template_requires_key_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    invalid = "Earnings review for $Symbol only"
                    with self.assertRaises(ValueError):
                        web_server.save_prompt_template(conn, web_server.ANALYSIS_PROMPT_SETTING_KEY_EARNINGS_WATCHPOINTS, invalid)
                finally:
                    conn.close()

    def test_generate_earnings_watchpoints_persists_and_replaces_symbol_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="MSFT")
                    self._seed_analysis(conn, symbol="AAPL")
                    web_server.add_earnings_review_symbol(conn, "MSFT")
                    created = web_server.create_earnings_review_record(conn, "MSFT", fiscal_year=2026, fiscal_quarter="Q1")
                    review_id = created["id"]
                    first_response = {
                        "watchpoints_by_variable": [
                            {
                                "key_variable": "Cloud demand growth",
                                "type": "Bullish",
                                "watchpoints": ["Azure bookings growth vs guidance", "Enterprise seat expansion commentary"],
                            }
                        ]
                    }
                    second_response = {
                        "watchpoints_by_variable": [
                            {
                                "key_variable": "Gross margin pressure",
                                "type": "Bearish",
                                "watchpoints": ["AI infrastructure cost intensity", "Gross margin guide progression"],
                            }
                        ]
                    }

                    with mock.patch.object(web_server, "OPENAI_API_KEY", "test"), \
                         mock.patch.object(web_server, "request_ai_step", side_effect=[first_response, second_response]):
                        detail_first = web_server.generate_earnings_watchpoints_for_review(conn, "MSFT", review_id)
                        detail_second = web_server.generate_earnings_watchpoints_for_review(conn, "MSFT", review_id)

                    self.assertEqual(detail_first["status"], web_server.EARNINGS_REVIEW_STATUS_WATCHPOINTS_GENERATED)
                    self.assertEqual(detail_second["status"], web_server.EARNINGS_REVIEW_STATUS_WATCHPOINTS_GENERATED)
                    self.assertEqual(len(detail_second["watchpoints_by_variable"]), 1)
                    self.assertEqual(detail_second["watchpoints_by_variable"][0]["key_variable"], "Gross margin pressure")

                    rows = conn.execute(
                        "SELECT key_variable_text FROM earnings_review_watchpoints WHERE earnings_review_id = ? ORDER BY id ASC",
                        (review_id,),
                    ).fetchall()
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(rows[0]["key_variable_text"], "Gross margin pressure")

                    list_items = web_server.list_earnings_review_symbols(conn)
                    self.assertEqual(len(list_items), 1)
                    msft_row = list_items[0]
                    self.assertEqual(msft_row["symbol"], "MSFT")
                    self.assertEqual(msft_row["latest_review_status"], web_server.EARNINGS_REVIEW_STATUS_WATCHPOINTS_GENERATED)
                    self.assertEqual(msft_row["latest_quarter"], "FY2026 Q1")
                    self.assertFalse(msft_row["in_portfolio"])
                finally:
                    conn.close()

    def test_add_earnings_review_symbol_requires_analysis_and_prevents_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="TSLA")
                    added = web_server.add_earnings_review_symbol(conn, "tsla")
                    self.assertEqual(added, "TSLA")
                    with self.assertRaisesRegex(ValueError, "already exists"):
                        web_server.add_earnings_review_symbol(conn, "TSLA")
                    with self.assertRaisesRegex(ValueError, "not found in Analysis"):
                        web_server.add_earnings_review_symbol(conn, "ABCD")
                finally:
                    conn.close()

    def test_init_db_seeds_earnings_review_symbols_from_existing_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="CRM")
                    web_server.create_earnings_review_record(conn, "CRM", fiscal_year=2025, fiscal_quarter="Q4")
                    conn.execute("DELETE FROM earnings_review_symbols WHERE symbol = ?", ("CRM",))
                    conn.commit()
                finally:
                    conn.close()
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    seeded = conn.execute(
                        "SELECT COUNT(*) AS c FROM earnings_review_symbols WHERE symbol = ?",
                        ("CRM",),
                    ).fetchone()["c"]
                    self.assertEqual(seeded, 1)
                finally:
                    conn.close()

    def test_document_upload_status_and_delete_recalculate(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            uploads_dir = Path(tmp) / "uploads"
            with mock.patch.object(web_server, "DB_PATH", db_path), \
                 mock.patch.object(web_server, "UPLOADS_DIR", uploads_dir):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="AMD")
                    web_server.add_earnings_review_symbol(conn, "AMD")
                    created = web_server.create_earnings_review_record(conn, "AMD", fiscal_year=2026, fiscal_quarter="Q1")
                    review_id = created["id"]
                    doc = web_server.save_earnings_review_document(
                        conn=conn,
                        symbol="AMD",
                        review_id=review_id,
                        document_type="Transcript",
                        original_file_name="q1-transcript.pdf",
                        payload=b"pdf-content",
                        mime_type="application/pdf",
                    )
                    detail = web_server.get_earnings_review_record_detail(conn, "AMD", review_id)
                    self.assertEqual(detail["status"], web_server.EARNINGS_REVIEW_STATUS_DOCUMENTS_UPLOADED)
                    self.assertEqual(len(detail["documents"]), 1)
                    self.assertEqual(len(list((uploads_dir / "earnings_reviews" / str(review_id)).glob("*"))), 1)

                    web_server.delete_earnings_review_document(conn, "AMD", review_id, doc["id"])
                    detail_after_delete = web_server.get_earnings_review_record_detail(conn, "AMD", review_id)
                    self.assertEqual(detail_after_delete["status"], web_server.EARNINGS_REVIEW_STATUS_DRAFT)
                    self.assertEqual(len(detail_after_delete["documents"]), 0)
                finally:
                    conn.close()

    def test_earnings_release_calendar_uses_standalone_entries_with_analysis_enrichment(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="MSFT")
                    conn.execute(
                        """
                        INSERT INTO positions_cache (
                          symbol, position, price, avg_cost, change_percent, market_value,
                          unrealized_pnl, daily_pnl, currency, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("MSFT", 5, 110, 100, 1.0, 550, 50, 5, "USD", web_server.utc_now_iso()),
                    )
                    conn.commit()
                    self.assertEqual(web_server.list_earnings_release_calendar(conn), [])

                    first = web_server.create_earnings_calendar_entry(
                        conn,
                        "MSFT",
                        fiscal_year=2026,
                        fiscal_quarter="Q1",
                        release_date="2026-05-07",
                        release_timing="After Close",
                    )
                    second = web_server.create_earnings_calendar_entry(
                        conn,
                        "MSFT",
                        fiscal_year=2026,
                        fiscal_quarter="Q2",
                        release_date="2026-08-06",
                        release_timing="Before Open",
                    )

                    self.assertNotEqual(first["id"], second["id"])
                    after = web_server.list_earnings_release_calendar(conn)
                    self.assertEqual(len(after), 2)
                    self.assertEqual({(item["symbol"], item["fiscal_year"], item["fiscal_quarter"]) for item in after}, {("MSFT", 2026, "Q1"), ("MSFT", 2026, "Q2")})
                    q1 = next(item for item in after if item["fiscal_quarter"] == "Q1")
                    self.assertTrue(q1["has_analysis"])
                    self.assertTrue(q1["in_portfolio"])
                    self.assertTrue(q1["inPortfolio"])
                    self.assertEqual(q1["release_date"], "2026-05-07")
                    self.assertEqual(q1["release_timing"], "After Close")
                    self.assertIsNotNone(q1["rating"])
                finally:
                    conn.close()

    def test_init_db_backfills_legacy_calendar_rows_as_2026_q1_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="MSFT")
                    self._seed_analysis(conn, symbol="NVDA")
                    self._seed_analysis(conn, symbol="SHOP")
                    now = web_server.utc_now_iso()
                    conn.execute(
                        """
                        INSERT INTO earnings_release_schedule (symbol, release_date, release_timing, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        ("MSFT", "2026-05-07", "After Close", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"),
                    )
                    conn.execute(
                        """
                        INSERT INTO earnings_release_calendar_exclusions (symbol, created_at)
                        VALUES (?, ?)
                        """,
                        ("SHOP", now),
                    )
                    conn.commit()
                finally:
                    conn.close()

                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    rows = web_server.list_earnings_release_calendar(conn)
                    self.assertEqual({item["symbol"] for item in rows}, {"MSFT", "NVDA"})
                    self.assertTrue(all(item["fiscal_year"] == 2026 for item in rows))
                    self.assertTrue(all(item["fiscal_quarter"] == "Q1" for item in rows))
                    msft = next(item for item in rows if item["symbol"] == "MSFT")
                    nvda = next(item for item in rows if item["symbol"] == "NVDA")
                    self.assertEqual(msft["release_date"], "2026-05-07")
                    self.assertEqual(msft["release_timing"], "After Close")
                    self.assertIsNone(nvda["release_date"])
                    self.assertIsNone(nvda["release_timing"])

                    web_server.init_db()
                    duplicate_count = conn.execute(
                        """
                        SELECT COUNT(*) AS c
                        FROM earnings_calendar_entries
                        WHERE fiscal_year = 2026 AND fiscal_quarter = 'Q1'
                        """
                    ).fetchone()["c"]
                    self.assertEqual(duplicate_count, 2)
                finally:
                    conn.close()

    def test_analysis_and_positions_payload_include_latest_release_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="MSFT")
                    web_server.create_earnings_calendar_entry(
                        conn,
                        "MSFT",
                        fiscal_year=2026,
                        fiscal_quarter="Q1",
                        release_date="2026-04-20",
                    )
                    web_server.create_earnings_calendar_entry(
                        conn,
                        "MSFT",
                        fiscal_year=2026,
                        fiscal_quarter="Q2",
                        release_date="2026-07-25",
                    )

                    analysis_row = next(item for item in web_server.list_analysis_symbols(conn) if item["symbol"] == "MSFT")
                    self.assertEqual(analysis_row["latest_release_date"], "2026-07-25")

                    payload = web_server.build_positions_payload(
                        conn,
                        [{"symbol": "MSFT", "position": 5, "avgCost": 100}],
                        data_source="test",
                    )
                    self.assertEqual(payload["positions"][0]["latest_release_date"], "2026-07-25")
                finally:
                    conn.close()

    def test_analysis_detail_includes_sorted_earnings_release_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="MSFT")
                    older = web_server.create_earnings_calendar_entry(
                        conn,
                        "MSFT",
                        fiscal_year=2026,
                        fiscal_quarter="Q1",
                        release_date="2026-04-20",
                        release_timing="After Close",
                    )
                    latest = web_server.create_earnings_calendar_entry(
                        conn,
                        "MSFT",
                        fiscal_year=2026,
                        fiscal_quarter="Q2",
                        release_date="2026-07-25",
                        release_timing="Before Open",
                    )
                    no_date = web_server.create_earnings_calendar_entry(
                        conn,
                        "MSFT",
                        fiscal_year=2026,
                        fiscal_quarter="Q3",
                    )

                    detail = web_server.get_analysis_detail(conn, "MSFT")
                    history = detail["release_history"]
                    self.assertEqual([entry["id"] for entry in history], [latest["id"], older["id"], no_date["id"]])
                    self.assertEqual(history[0]["release_date"], "2026-07-25")
                    self.assertEqual(history[0]["fiscal_quarter"], "Q2")
                    self.assertEqual(history[0]["release_timing"], "Before Open")
                finally:
                    conn.close()

    def test_earnings_release_calendar_entry_can_exist_without_analysis_and_be_updated_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    created = web_server.create_earnings_calendar_entry(
                        conn,
                        "ABCD",
                        fiscal_year=2027,
                        fiscal_quarter="Q3",
                    )
                    item = web_server.list_earnings_release_calendar(conn)[0]
                    self.assertEqual(item["symbol"], "ABCD")
                    self.assertIsNone(item["company_name"])
                    self.assertFalse(item["has_analysis"])
                    self.assertFalse(item["in_portfolio"])

                    updated = web_server.update_earnings_calendar_entry(
                        conn,
                        created["id"],
                        fiscal_year=2027,
                        fiscal_quarter="Q4",
                        release_date="2027-11-01",
                        release_timing="Before Open",
                    )
                    self.assertEqual(updated["fiscal_quarter"], "Q4")
                    self.assertEqual(updated["release_date"], "2027-11-01")

                    result = web_server.delete_earnings_calendar_entry(conn, created["id"])
                    self.assertTrue(result["removed"])
                    self.assertEqual(web_server.list_earnings_release_calendar(conn), [])
                finally:
                    conn.close()

    def test_document_delete_reverts_to_watchpoints_generated_when_watchpoints_exist(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            uploads_dir = Path(tmp) / "uploads"
            with mock.patch.object(web_server, "DB_PATH", db_path), \
                 mock.patch.object(web_server, "UPLOADS_DIR", uploads_dir):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="NFLX")
                    web_server.add_earnings_review_symbol(conn, "NFLX")
                    created = web_server.create_earnings_review_record(conn, "NFLX", fiscal_year=2026, fiscal_quarter="Q2")
                    review_id = created["id"]
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoints (
                          earnings_review_id, key_variable_text, key_variable_type, watchpoints_json,
                          display_order, generated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                        """,
                        (review_id, "Subscriber growth", "Bullish", '["net adds"]', web_server.utc_now_iso(), web_server.utc_now_iso(), web_server.utc_now_iso()),
                    )
                    conn.commit()
                    web_server.recalculate_earnings_review_status(conn, review_id)
                    uploaded = web_server.save_earnings_review_document(
                        conn=conn,
                        symbol="NFLX",
                        review_id=review_id,
                        document_type="Earnings Release",
                        original_file_name="release.pdf",
                        payload=b"x",
                        mime_type="application/pdf",
                    )
                    self.assertEqual(
                        web_server.get_earnings_review_record_detail(conn, "NFLX", review_id)["status"],
                        web_server.EARNINGS_REVIEW_STATUS_DOCUMENTS_UPLOADED,
                    )
                    web_server.delete_earnings_review_document(conn, "NFLX", review_id, uploaded["id"])
                    self.assertEqual(
                        web_server.get_earnings_review_record_detail(conn, "NFLX", review_id)["status"],
                        web_server.EARNINGS_REVIEW_STATUS_WATCHPOINTS_GENERATED,
                    )
                finally:
                    conn.close()

    def test_analyse_watchpoints_persists_results_and_updates_status(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            uploads_dir = Path(tmp) / "uploads"
            with mock.patch.object(web_server, "DB_PATH", db_path), \
                 mock.patch.object(web_server, "UPLOADS_DIR", uploads_dir):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="INTC")
                    web_server.add_earnings_review_symbol(conn, "INTC")
                    created = web_server.create_earnings_review_record(conn, "INTC", fiscal_year=2026, fiscal_quarter="Q1")
                    review_id = created["id"]
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoints (
                          earnings_review_id, key_variable_text, key_variable_type, watchpoints_json,
                          display_order, generated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                        """,
                        (review_id, "PC demand", "Bullish", json.dumps(["OEM channel restocking"]), web_server.utc_now_iso(), web_server.utc_now_iso(), web_server.utc_now_iso()),
                    )
                    conn.commit()
                    web_server.recalculate_earnings_review_status(conn, review_id)
                    web_server.save_earnings_review_document(
                        conn=conn,
                        symbol="INTC",
                        review_id=review_id,
                        document_type="Transcript",
                        original_file_name="call.txt",
                        payload=b"Management discussed OEM channel restocking.",
                        mime_type="text/plain",
                    )
                    watchpoint_id = web_server.get_earnings_review_record_detail(conn, "INTC", review_id)["watchpoints_by_variable"][0]["watchpoint_ids"][0]
                    ai_response = {
                        "watchpoint_results": [
                            {
                                "watchpoint_id": watchpoint_id,
                                "key_variable": "PC demand",
                                "watchpoint": "OEM channel restocking",
                                "status": "Confirmed",
                                "result_text": "Management commentary indicates ongoing restocking in OEM channels.",
                            }
                        ]
                    }
                    with mock.patch.object(web_server, "OPENAI_API_KEY", "x"), \
                         mock.patch.object(web_server, "request_ai_step", return_value=ai_response):
                        detail = web_server.analyze_earnings_watchpoints_for_review(conn, "INTC", review_id)
                    self.assertEqual(detail["status"], web_server.EARNINGS_REVIEW_STATUS_WATCHPOINTS_ANALYSED)
                    self.assertEqual(len(detail["watchpoint_results"]), 1)
                    self.assertEqual(detail["watchpoint_results"][0]["status"], "Confirmed")
                finally:
                    conn.close()

    def test_generate_watchpoints_clears_existing_analysis_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="ORCL")
                    web_server.add_earnings_review_symbol(conn, "ORCL")
                    created = web_server.create_earnings_review_record(conn, "ORCL", fiscal_year=2026, fiscal_quarter="Q3")
                    review_id = created["id"]
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoints (
                          earnings_review_id, key_variable_text, key_variable_type, watchpoints_json,
                          display_order, generated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                        """,
                        (review_id, "Cloud growth", "Bullish", json.dumps(["Consumption trend"]), web_server.utc_now_iso(), web_server.utc_now_iso(), web_server.utc_now_iso()),
                    )
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoint_results (
                          earnings_review_id, key_variable_text, watchpoint_text, status, result_text, analysed_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (review_id, "Cloud growth", "Consumption trend", "Unclear", "Mixed signal", web_server.utc_now_iso(), web_server.utc_now_iso(), web_server.utc_now_iso()),
                    )
                    conn.commit()
                    with mock.patch.object(web_server, "OPENAI_API_KEY", "test"), \
                         mock.patch.object(web_server, "request_ai_step", return_value={
                             "watchpoints_by_variable": [
                                 {"key_variable": "Cloud growth", "type": "Bullish", "watchpoints": ["Bookings momentum"]}
                             ]
                         }):
                        web_server.generate_earnings_watchpoints_for_review(conn, "ORCL", review_id)
                    count = conn.execute(
                        "SELECT COUNT(*) AS c FROM earnings_review_watchpoint_results WHERE earnings_review_id = ?",
                        (review_id,),
                    ).fetchone()["c"]
                    self.assertEqual(count, 0)
                finally:
                    conn.close()

    def test_analyse_watchpoints_fails_when_no_readable_document_text_and_keeps_previous_results(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            uploads_dir = Path(tmp) / "uploads"
            with mock.patch.object(web_server, "DB_PATH", db_path), \
                 mock.patch.object(web_server, "UPLOADS_DIR", uploads_dir):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="SHOP")
                    web_server.add_earnings_review_symbol(conn, "SHOP")
                    created = web_server.create_earnings_review_record(conn, "SHOP", fiscal_year=2026, fiscal_quarter="Q4")
                    review_id = created["id"]
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoints (
                          earnings_review_id, key_variable_text, key_variable_type, watchpoints_json,
                          display_order, generated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                        """,
                        (review_id, "GMV growth", "Bullish", json.dumps(["Merchant growth"]), web_server.utc_now_iso(), web_server.utc_now_iso(), web_server.utc_now_iso()),
                    )
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoint_results (
                          earnings_review_id, key_variable_text, watchpoint_text, status, result_text, analysed_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (review_id, "GMV growth", "Merchant growth", "Confirmed", "Prior valid result", web_server.utc_now_iso(), web_server.utc_now_iso(), web_server.utc_now_iso()),
                    )
                    conn.commit()
                    web_server.save_earnings_review_document(
                        conn=conn,
                        symbol="SHOP",
                        review_id=review_id,
                        document_type="Presentation",
                        original_file_name="deck.pdf",
                        payload=b"%PDF-1.4 \x00\x01\x02",
                        mime_type="application/pdf",
                    )
                    with mock.patch.object(web_server, "OPENAI_API_KEY", "x"), \
                         mock.patch.object(web_server, "request_ai_step", return_value={"watchpoint_results": []}):
                        with self.assertRaisesRegex(ValueError, "no readable text"):
                            web_server.analyze_earnings_watchpoints_for_review(conn, "SHOP", review_id)
                    row = conn.execute(
                        "SELECT result_text FROM earnings_review_watchpoint_results WHERE earnings_review_id = ? AND watchpoint_text = ?",
                        (review_id, "Merchant growth"),
                    ).fetchone()
                    self.assertEqual(row["result_text"], "Prior valid result")
                finally:
                    conn.close()

    def test_ai_step_timeout_override_for_earnings_watchpoint_analysis(self):
        self.assertEqual(web_server.get_ai_step_timeout("business_model", attempt=1), max(10.0, web_server.OPENAI_REQUEST_TIMEOUT_SECONDS))
        self.assertEqual(web_server.get_ai_step_timeout("earnings_watchpoint_analysis", attempt=1), 120.0)
        self.assertEqual(web_server.get_ai_step_timeout("earnings_watchpoint_analysis", attempt=2), 180.0)

    def test_analyse_watchpoints_batches_by_four(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            uploads_dir = Path(tmp) / "uploads"
            with mock.patch.object(web_server, "DB_PATH", db_path), \
                 mock.patch.object(web_server, "UPLOADS_DIR", uploads_dir):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="AMZN")
                    web_server.add_earnings_review_symbol(conn, "AMZN")
                    created = web_server.create_earnings_review_record(conn, "AMZN", fiscal_year=2026, fiscal_quarter="Q1")
                    review_id = created["id"]
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoints (
                          earnings_review_id, key_variable_text, key_variable_type, watchpoints_json,
                          display_order, generated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                        """,
                        (
                            review_id,
                            "Retail margin",
                            "Bullish",
                            json.dumps(["wp1", "wp2", "wp3", "wp4", "wp5"]),
                            web_server.utc_now_iso(),
                            web_server.utc_now_iso(),
                            web_server.utc_now_iso(),
                        ),
                    )
                    conn.commit()
                    web_server.save_earnings_review_document(
                        conn=conn,
                        symbol="AMZN",
                        review_id=review_id,
                        document_type="Transcript",
                        original_file_name="call.txt",
                        payload=b"wp1 wp2 wp3 wp4 wp5 discussed in detail across sections.",
                        mime_type="text/plain",
                    )
                    wp_ids = web_server.get_earnings_review_record_detail(conn, "AMZN", review_id)["watchpoints_by_variable"][0]["watchpoint_ids"]
                    responses = [
                        {"watchpoint_results": [
                            {"watchpoint_id": wp_ids[0], "key_variable": "Retail margin", "watchpoint": "wp1", "status": "Confirmed", "result_text": "ok"},
                            {"watchpoint_id": wp_ids[1], "key_variable": "Retail margin", "watchpoint": "wp2", "status": "Not addressed", "result_text": "ok"},
                            {"watchpoint_id": wp_ids[2], "key_variable": "Retail margin", "watchpoint": "wp3", "status": "Unclear", "result_text": "ok"},
                            {"watchpoint_id": wp_ids[3], "key_variable": "Retail margin", "watchpoint": "wp4", "status": "Contradicted", "result_text": "ok"},
                        ]},
                        {"watchpoint_results": [
                            {"watchpoint_id": wp_ids[4], "key_variable": "Retail margin", "watchpoint": "wp5", "status": "Partially confirmed", "result_text": "ok"},
                        ]},
                    ]
                    with mock.patch.object(web_server, "OPENAI_API_KEY", "x"), \
                         mock.patch.object(web_server, "request_ai_step", side_effect=responses) as mocked_step:
                        detail = web_server.analyze_earnings_watchpoints_for_review(conn, "AMZN", review_id)
                    self.assertEqual(mocked_step.call_count, 2)
                    self.assertEqual(len(detail["watchpoint_results"]), 5)
                finally:
                    conn.close()

    def test_analyse_watchpoints_retries_once_on_incomplete_batch_output(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            uploads_dir = Path(tmp) / "uploads"
            with mock.patch.object(web_server, "DB_PATH", db_path), \
                 mock.patch.object(web_server, "UPLOADS_DIR", uploads_dir):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="META")
                    web_server.add_earnings_review_symbol(conn, "META")
                    created = web_server.create_earnings_review_record(conn, "META", fiscal_year=2026, fiscal_quarter="Q2")
                    review_id = created["id"]
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoints (
                          earnings_review_id, key_variable_text, key_variable_type, watchpoints_json,
                          display_order, generated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                        """,
                        (review_id, "Ad pricing", "Bullish", json.dumps(["Reels monetization", "Ad load"]), web_server.utc_now_iso(), web_server.utc_now_iso(), web_server.utc_now_iso()),
                    )
                    conn.commit()
                    web_server.save_earnings_review_document(
                        conn=conn,
                        symbol="META",
                        review_id=review_id,
                        document_type="Transcript",
                        original_file_name="call.txt",
                        payload=b"Reels monetization and ad load commentary were provided.",
                        mime_type="text/plain",
                    )
                    ids = web_server.get_earnings_review_record_detail(conn, "META", review_id)["watchpoints_by_variable"][0]["watchpoint_ids"]
                    first_invalid = {
                        "watchpoint_results": [
                            {"watchpoint_id": ids[0], "key_variable": "Ad pricing", "watchpoint": "Reels monetization", "status": "Confirmed", "result_text": "ok"},
                        ]
                    }
                    second_valid = {
                        "watchpoint_results": [
                            {"watchpoint_id": ids[0], "key_variable": "Ad pricing", "watchpoint": "Reels monetization", "status": "Confirmed", "result_text": "ok"},
                            {"watchpoint_id": ids[1], "key_variable": "Ad pricing", "watchpoint": "Ad load", "status": "Unclear", "result_text": "mixed"},
                        ]
                    }
                    with mock.patch.object(web_server, "OPENAI_API_KEY", "x"), \
                         mock.patch.object(web_server, "request_ai_step", side_effect=[first_invalid, second_valid]) as mocked:
                        detail = web_server.analyze_earnings_watchpoints_for_review(conn, "META", review_id)
                    self.assertEqual(mocked.call_count, 2)
                    self.assertEqual(len(detail["watchpoint_results"]), 2)
                finally:
                    conn.close()

    def test_created_review_snapshot_normalizes_key_variable_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="NOW")
                    created = web_server.create_earnings_review_record(conn, "NOW", fiscal_year=2026, fiscal_quarter="Q2")
                    key_variables = created["key_variables_snapshot"]
                    self.assertTrue(key_variables)
                    self.assertTrue(all("variable" in item for item in key_variables))
                    self.assertTrue(all("type" in item for item in key_variables))
                    self.assertTrue(any(item["variable"] == "Cloud demand growth" for item in key_variables))
                    self.assertTrue(any(item["type"] == "Bullish" for item in key_variables))
                finally:
                    conn.close()

    def test_record_detail_maps_legacy_snapshot_variable_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = web_server.utc_now_iso()
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("ABC", now, now))
                    legacy_snapshot = {
                        "symbol": "ABC",
                        "company_name": "ABC Inc.",
                        "key_variables": [
                            {"variable_text": "Legacy Variable", "variable_type": "Bearish", "confidence": 6, "importance": 8}
                        ],
                    }
                    conn.execute(
                        """
                        INSERT INTO earnings_reviews (
                          symbol, company_name_snapshot, fiscal_year, fiscal_quarter, release_date, status,
                          thesis_snapshot_json, watchpoints_generated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        ("ABC", "ABC Inc.", 2026, "Q1", None, web_server.EARNINGS_REVIEW_STATUS_DRAFT, json.dumps(legacy_snapshot), None, now, now),
                    )
                    review_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
                    conn.commit()
                    detail = web_server.get_earnings_review_record_detail(conn, "ABC", review_id)
                    self.assertEqual(detail["key_variables_snapshot"][0]["variable"], "Legacy Variable")
                    self.assertEqual(detail["key_variables_snapshot"][0]["type"], "Bearish")
                finally:
                    conn.close()

    def test_delete_earnings_review_record_removes_associated_watchpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    self._seed_analysis(conn, symbol="DEL")
                    created = web_server.create_earnings_review_record(conn, "DEL", fiscal_year=2026, fiscal_quarter="Q3")
                    review_id = created["id"]
                    conn.execute(
                        """
                        INSERT INTO earnings_review_watchpoints (
                          earnings_review_id, key_variable_text, key_variable_type, watchpoints_json,
                          display_order, generated_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (review_id, "x", "Bullish", json.dumps(["w1"]), 0, web_server.utc_now_iso(), web_server.utc_now_iso(), web_server.utc_now_iso()),
                    )
                    conn.commit()

                    conn.execute("DELETE FROM earnings_reviews WHERE id = ? AND symbol = ?", (review_id, "DEL"))
                    conn.commit()

                    count_reviews = conn.execute("SELECT COUNT(*) AS c FROM earnings_reviews WHERE id = ?", (review_id,)).fetchone()["c"]
                    count_watchpoints = conn.execute(
                        "SELECT COUNT(*) AS c FROM earnings_review_watchpoints WHERE earnings_review_id = ?",
                        (review_id,),
                    ).fetchone()["c"]
                    self.assertEqual(count_reviews, 0)
                    self.assertEqual(count_watchpoints, 0)
                finally:
                    conn.close()


if __name__ == "__main__":
    unittest.main()



class ActionPlanFeatureTests(unittest.TestCase):
    def test_build_action_plan_uses_effective_analysis_and_cached_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    analysis = [
                        {
                            "symbol": "BUY",
                            "company_name": "Buy Co",
                            "rating": "Buy",
                            "current_price": 50.0,
                            "expected_price": 100.0,
                            "expected_cagr": 14.9,
                            "upside": 100.0,
                            "core_confidence_diff": 1.5,
                            "core_bullish_confidence": 7.0,
                            "core_bearish_confidence": 3.0,
                            "potential_confidence_diff": 0.5,
                            "potential_bullish_confidence": 5.0,
                            "potential_bearish_confidence": 4.5,
                            "uses_final_scenario_overlay": True,
                            "final_scenario_stale": False,
                        },
                        {
                            "symbol": "SELL",
                            "company_name": "Sell Co",
                            "rating": "Sell",
                            "current_price": 20.0,
                            "expected_price": 18.0,
                            "expected_cagr": -2.0,
                            "upside": -10.0,
                            "core_confidence_diff": -1.0,
                            "core_bullish_confidence": 3.0,
                            "core_bearish_confidence": 6.0,
                            "potential_confidence_diff": None,
                            "potential_bullish_confidence": None,
                            "potential_bearish_confidence": None,
                            "final_scenario_stale": False,
                        },
                    ]
                    positions = [{"symbol": "SELL", "position": 10, "marketValue": 1000.0}]
                    with mock.patch.object(web_server, "list_analysis_symbols", return_value=analysis), \
                         mock.patch.object(web_server, "load_positions_cache", return_value=positions):
                        payload = web_server.build_action_plan(conn)
                    rows = {row["symbol"]: row for row in payload["action_plan"]}
                    self.assertEqual(rows["BUY"]["action"], "Strong Add")
                    self.assertEqual(rows["BUY"]["current_position_weight"], 0.0)
                    self.assertGreater(rows["BUY"]["target_weight_mid"], 0)
                    self.assertEqual(rows["BUY"]["action_amount_direction"], "add")
                    self.assertGreater(rows["BUY"]["action_amount"], 0)
                    self.assertIn("Add about", rows["BUY"]["action_amount_label"])
                    self.assertIn("target_weight_breakdown", rows["BUY"])
                    self.assertIn("trigger_breakdown", rows["BUY"])
                    self.assertIn("decision_path", rows["BUY"])
                    self.assertEqual(rows["SELL"]["action"], "Sell")
                    self.assertEqual(rows["SELL"]["current_position_weight"], 100.0)
                    self.assertEqual(rows["SELL"]["action_amount_direction"], "sell")
                    self.assertEqual(rows["SELL"]["action_amount"], 1000.0)
                    self.assertIn("Sell about", rows["SELL"]["action_amount_label"])
                    self.assertEqual(payload["summary"]["total_portfolio_value"], 1000.0)
                finally:
                    conn.close()

    def test_ibkr_account_summary_prefers_usd_ledger_cash(self):
        summary_items = [
            types.SimpleNamespace(tag="NetLiquidation", value="122917.74", currency="USD", account="DU123"),
            types.SimpleNamespace(tag="SettledCash", value="1043.88", currency="USD", account="DU123"),
            types.SimpleNamespace(tag="TotalCashValue", value="900.00", currency="USD", account="DU123"),
            types.SimpleNamespace(tag="CashBalance", value="1043.88", currency="USD", account="DU123"),
            types.SimpleNamespace(tag="TotalCashBalance", value="1043.88", currency="USD", account="DU123"),
            types.SimpleNamespace(tag="AvailableFunds", value="5000", currency="USD", account="DU123"),
        ]
        ib = types.SimpleNamespace(accountSummary=lambda: summary_items)

        summary = web_server.fetch_ib_portfolio_summary(ib)

        self.assertEqual(summary["account_id"], "DU123")
        self.assertEqual(summary["net_liquidation"], 122917.74)
        self.assertEqual(summary["ledger_cash_usd"], 1043.88)
        self.assertEqual(summary["actual_cash"], 1043.88)
        self.assertEqual(summary["actual_cash_source"], "ibkr_ledger_cash_balance")
        self.assertIn("CashBalance:USD", summary["available_tags"])

    def test_action_plan_uses_cached_cash_and_excludes_cash_equivalents(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_portfolio_summary_cache(conn, {
                        "account_id": "DU123",
                        "base_currency": "USD",
                        "net_liquidation": 2000.0,
                        "settled_cash": 100.0,
                    })
                    analysis = [
                        {
                            "symbol": "BUY",
                            "company_name": "Buy Co",
                            "rating": "Buy",
                            "current_price": 50.0,
                            "expected_price": 100.0,
                            "expected_cagr": 14.9,
                            "upside": 100.0,
                            "core_confidence_diff": 1.5,
                            "core_bullish_confidence": 7.0,
                            "core_bearish_confidence": 3.0,
                            "potential_confidence_diff": 0.5,
                            "potential_bullish_confidence": 6.0,
                            "potential_bearish_confidence": 5.5,
                            "final_scenario_stale": False,
                        },
                        {
                            "symbol": "SGOV",
                            "company_name": "Cash ETF",
                            "rating": "Buy",
                            "current_price": 100.0,
                            "expected_price": 101.0,
                            "expected_cagr": 1.0,
                            "upside": 1.0,
                            "core_confidence_diff": 0.0,
                            "core_bullish_confidence": 5.0,
                            "core_bearish_confidence": 5.0,
                            "final_scenario_stale": False,
                        },
                    ]
                    positions = [
                        {"symbol": "BUY", "position": 10, "marketValue": 500.0, "price": 50.0},
                        {"symbol": "SGOV", "position": 10, "marketValue": 1000.0, "price": 100.0},
                    ]
                    with mock.patch.object(web_server, "list_analysis_symbols", return_value=analysis), \
                         mock.patch.object(web_server, "load_positions_cache", return_value=positions):
                        payload = web_server.build_action_plan(conn)
                    symbols = {row["symbol"] for row in payload["action_plan"]}
                    self.assertIn("BUY", symbols)
                    self.assertNotIn("SGOV", symbols)
                    summary = payload["summary"]
                    self.assertEqual(summary["portfolio_value_used"], 2000.0)
                    self.assertEqual(summary["portfolio_value_source"], "ibkr_net_liquidation")
                    self.assertEqual(summary["actual_cash"], 100.0)
                    self.assertEqual(summary["cash_equivalent_value"], 1000.0)
                    self.assertEqual(summary["cash_like_available"], 1100.0)
                    self.assertEqual(summary["cash_equivalent_symbols"], ["SGOV"])
                    row = next(item for item in payload["action_plan"] if item["symbol"] == "BUY")
                    self.assertAlmostEqual(row["current_position_weight"], 25.0)
                    self.assertIn(row["action_amount_cash_covered"], {True, False, None})
                finally:
                    conn.close()

    def test_action_plan_settings_persist_bucket_values_outside_generic_float_clamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    action_settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
                    action_settings.update({
                        "action_bucket_strong_buy_target": 40.0,
                        "action_bucket_buy_target": 20.0,
                        "action_bucket_speculative_buy_target": 10.0,
                        "action_bucket_hold_target": 5.0,
                        "action_bucket_cash_target": 25.0,
                        "action_bucket_sell_target": 0.0,
                        "action_bucket_strong_sell_target": 0.0,
                    })
                    web_server.save_general_configuration(conn, {"action_plan_settings": action_settings})
                    loaded = web_server.get_general_configuration(conn)["action_plan_settings"]
                    self.assertEqual(loaded["action_bucket_strong_buy_target"], 40.0)
                    self.assertEqual(loaded["action_bucket_sell_target"], 0.0)
                    self.assertEqual(loaded["action_bucket_strong_sell_target"], 0.0)
                finally:
                    conn.close()

    def test_action_plan_settings_reject_bucket_total_above_100(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_bucket_buy_target"] = 90.0
        with self.assertRaisesRegex(ValueError, "bucket targets"):
            web_server.validate_action_plan_settings(settings)

class ExternalScenarioOverlayTests(unittest.TestCase):
    def _seed_version_with_scenarios(self, conn, symbol="EXT"):
        now = web_server.utc_now_iso()
        conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", (symbol, now, now))
        root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = ?", (symbol,)).fetchone()["id"]
        conn.execute(
            """
            INSERT INTO analysis_versions (
                analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                expected_cagr, upside, confidence_level, assumptions_text, business_model_text,
                business_summary_text, raw_ai_response, source_trigger, created_at
            ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (root_id, symbol, f"{symbol} Inc.", 100.0, 140.0, 7.0, 40.0, 6.0, "assume", "model", "summary", "{}", "test", now),
        )
        version_id = conn.execute("SELECT id FROM analysis_versions WHERE analysis_root_id = ?", (root_id,)).fetchone()["id"]
        scenarios = [
            ("Bear", 80.0, 90.0, -4.0, -2.0, 0.20),
            ("Base", 120.0, 140.0, 4.0, 7.0, 0.50),
            ("Bull", 180.0, 220.0, 12.0, 17.0, 0.30),
        ]
        for name, low, high, cagr_low, cagr_high, probability in scenarios:
            conn.execute(
                """
                INSERT INTO analysis_version_scenarios (
                    analysis_version_id, scenario_name, price_low, price_mid, price_high,
                    cagr_low, cagr_mid, cagr_high, probability, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (version_id, name, low, (low + high) / 2, high, cagr_low, (cagr_low + cagr_high) / 2, cagr_high, probability, now),
            )
        conn.commit()
        return root_id, version_id

    def _external_payload(self, weight=30, title="External"):
        return {
            "title": title,
            "external_weight": weight,
            "source_notes": "analyst model",
            "scenario_json": json.dumps({
                "scenarios": [
                    {"name": "Bear", "price_low": 70, "price_high": 85, "cagr_low": -7, "cagr_high": -3, "probability": 30},
                    {"name": "Base", "price_low": 130, "price_high": 150, "cagr_low": 5, "cagr_high": 8, "probability": 45},
                    {"name": "Bull", "price_low": 240, "price_high": 280, "cagr_low": 19, "cagr_high": 23, "probability": 25},
                ]
            }),
        }

    def test_external_scenario_crud_validation_and_stale_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    _, version_id = self._seed_version_with_scenarios(conn)
                    payload_without_cagr = self._external_payload(weight=30)
                    scenario_payload = json.loads(payload_without_cagr["scenario_json"])
                    for scenario in scenario_payload["scenarios"]:
                        scenario.pop("cagr_low", None)
                        scenario.pop("cagr_high", None)
                    payload_without_cagr["scenario_json"] = json.dumps(scenario_payload)
                    item = web_server.create_external_scenario(conn, version_id, payload_without_cagr)
                    self.assertEqual(item["title"], "External")
                    self.assertAlmostEqual(item["external_weight"], 0.30)
                    self.assertEqual([s["scenario_name"] for s in item["scenarios"]], ["Bear", "Base", "Bull"])

                    updated = web_server.update_external_scenario(conn, version_id, item["id"], self._external_payload(weight=0.4, title="Updated"))
                    self.assertEqual(updated["title"], "Updated")
                    self.assertAlmostEqual(updated["external_weight"], 0.40)

                    overlay = web_server.recalculate_final_scenario_overlay(conn, version_id)
                    self.assertFalse(overlay["is_stale"])
                    web_server.update_external_scenario(conn, version_id, item["id"], self._external_payload(weight=50, title="Updated again"))
                    stale = web_server.get_final_scenario_overlay(conn, version_id)
                    self.assertTrue(stale["is_stale"])

                    deleted = web_server.delete_external_scenario(conn, version_id, item["id"])
                    self.assertTrue(deleted["deleted_final_overlay"])
                    self.assertEqual(web_server.list_external_scenarios(conn, version_id), [])
                    self.assertIsNone(web_server.get_final_scenario_overlay(conn, version_id))
                finally:
                    conn.close()

    def test_external_scenario_recalculation_blends_and_blocks_overweight(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    _, version_id = self._seed_version_with_scenarios(conn)
                    web_server.create_external_scenario(conn, version_id, self._external_payload(weight=30))
                    overlay = web_server.recalculate_final_scenario_overlay(conn, version_id)
                    self.assertAlmostEqual(overlay["bakingmoney_weight"], 0.70)
                    self.assertAlmostEqual(overlay["external_total_weight"], 0.30)
                    bear = overlay["scenarios"][0]
                    self.assertEqual(bear["scenario_name"], "Bear")
                    self.assertAlmostEqual(bear["price_low"], 77.0)
                    self.assertAlmostEqual(bear["price_high"], 88.5)
                    self.assertAlmostEqual(bear["cagr_low"], web_server.compute_scenario_cagr(bear["price_low"], 100.0))
                    self.assertAlmostEqual(bear["cagr_high"], web_server.compute_scenario_cagr(bear["price_high"], 100.0))
                    self.assertAlmostEqual(bear["cagr_mid"], web_server.compute_scenario_cagr(bear["price_mid"], 100.0))
                    self.assertAlmostEqual(sum(s["probability"] for s in overlay["scenarios"]), 1.0)
                    self.assertIsNotNone(overlay["expected_price"])
                    self.assertAlmostEqual(overlay["expected_cagr"], web_server.calculate_expected_cagr_from_price(overlay["expected_price"], 100.0))
                    edit_payload = json.loads(web_server.list_external_scenarios(conn, version_id)[0]["scenario_json"])
                    self.assertNotIn("cagr_low", edit_payload["scenarios"][0])
                    self.assertNotIn("cagr_high", edit_payload["scenarios"][0])

                    first = web_server.list_external_scenarios(conn, version_id)[0]
                    web_server.update_external_scenario(conn, version_id, first["id"], self._external_payload(weight=80, title="High weight"))
                    web_server.create_external_scenario(conn, version_id, self._external_payload(weight=30, title="Second"))
                    with self.assertRaisesRegex(ValueError, "more than 100%"):
                        web_server.recalculate_final_scenario_overlay(conn, version_id)
                finally:
                    conn.close()

    def test_price_refresh_recalculates_dynamic_cagr_without_changing_scenario_prices(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    _, version_id = self._seed_version_with_scenarios(conn)
                    web_server.create_external_scenario(conn, version_id, self._external_payload(weight=30))
                    overlay_before = web_server.recalculate_final_scenario_overlay(conn, version_id)
                    original_bear = conn.execute(
                        "SELECT price_low, price_high FROM analysis_version_scenarios WHERE analysis_version_id = ? AND scenario_name = 'Bear'",
                        (version_id,),
                    ).fetchone()

                    with mock.patch.object(web_server, "fetch_ib_prices", return_value=({"EXT": 200.0}, [])):
                        result = web_server.refresh_latest_analysis_market_prices(conn)

                    self.assertEqual(result["updated"], 1)
                    version_row = conn.execute("SELECT current_price, expected_price, expected_cagr, upside FROM analysis_versions WHERE id = ?", (version_id,)).fetchone()
                    self.assertEqual(version_row["current_price"], 200.0)
                    self.assertAlmostEqual(version_row["expected_cagr"], web_server.calculate_expected_cagr_from_price(version_row["expected_price"], 200.0))
                    self.assertAlmostEqual(version_row["upside"], web_server.calculate_upside(version_row["expected_price"], 200.0))
                    refreshed_bear = conn.execute(
                        "SELECT price_low, price_high, cagr_low FROM analysis_version_scenarios WHERE analysis_version_id = ? AND scenario_name = 'Bear'",
                        (version_id,),
                    ).fetchone()
                    self.assertEqual(refreshed_bear["price_low"], original_bear["price_low"])
                    self.assertEqual(refreshed_bear["price_high"], original_bear["price_high"])
                    self.assertAlmostEqual(refreshed_bear["cagr_low"], web_server.compute_scenario_cagr(original_bear["price_low"], 200.0))
                    overlay_after = web_server.get_final_scenario_overlay(conn, version_id)
                    self.assertAlmostEqual(overlay_after["expected_price"], overlay_before["expected_price"])
                    self.assertAlmostEqual(overlay_after["expected_cagr"], web_server.calculate_expected_cagr_from_price(overlay_after["expected_price"], 200.0))
                finally:
                    conn.close()

    def test_non_stale_final_overlay_provides_effective_metrics_for_detail_list_and_positions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    _, version_id = self._seed_version_with_scenarios(conn, symbol="EFF")
                    web_server.create_external_scenario(conn, version_id, self._external_payload(weight=30))
                    overlay = web_server.recalculate_final_scenario_overlay(conn, version_id)

                    detail_version = web_server.get_analysis_detail(conn, "EFF")["version"]
                    self.assertTrue(detail_version["uses_final_scenario_overlay"])
                    self.assertFalse(detail_version["final_scenario_stale"])
                    self.assertEqual(detail_version["expected_price_original"], 140.0)
                    self.assertEqual(detail_version["expected_cagr_original"], 7.0)
                    self.assertEqual(detail_version["upside_original"], 40.0)
                    self.assertAlmostEqual(detail_version["expected_price"], overlay["expected_price"])
                    self.assertAlmostEqual(detail_version["expected_cagr"], overlay["expected_cagr"])
                    self.assertAlmostEqual(detail_version["upside"], overlay["upside"])

                    analysis_row = web_server.list_analysis_symbols(conn)[0]
                    self.assertTrue(analysis_row["uses_final_scenario_overlay"])
                    self.assertAlmostEqual(analysis_row["expected_price"], overlay["expected_price"])
                    self.assertAlmostEqual(analysis_row["expected_cagr"], overlay["expected_cagr"])
                    self.assertAlmostEqual(analysis_row["upside"], overlay["upside"])

                    merged = web_server.merge_positions_with_latest_analysis([{"symbol": "EFF", "position": 1}], [analysis_row])[0]
                    self.assertTrue(merged["uses_final_scenario_overlay"])
                    self.assertAlmostEqual(merged["expected_price"], overlay["expected_price"])
                    self.assertAlmostEqual(merged["expected_cagr"], overlay["expected_cagr"])
                    self.assertAlmostEqual(merged["upside"], overlay["upside"])

                    original_scenario_rows = conn.execute(
                        "SELECT scenario_name, price_low, price_high FROM analysis_version_scenarios WHERE analysis_version_id = ? ORDER BY scenario_name",
                        (version_id,),
                    ).fetchall()
                    self.assertEqual(len(original_scenario_rows), 3)
                    self.assertEqual({row["scenario_name"]: row["price_high"] for row in original_scenario_rows}["Bull"], 220.0)
                finally:
                    conn.close()

    def test_stale_final_overlay_is_ignored_for_effective_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    _, version_id = self._seed_version_with_scenarios(conn, symbol="STALE")
                    item = web_server.create_external_scenario(conn, version_id, self._external_payload(weight=30))
                    web_server.recalculate_final_scenario_overlay(conn, version_id)
                    web_server.update_external_scenario(conn, version_id, item["id"], self._external_payload(weight=40, title="Changed"))

                    detail_version = web_server.get_analysis_detail(conn, "STALE")["version"]
                    self.assertFalse(detail_version["uses_final_scenario_overlay"])
                    self.assertTrue(detail_version["final_scenario_stale"])
                    self.assertEqual(detail_version["expected_price"], 140.0)
                    self.assertEqual(detail_version["expected_cagr"], 7.0)
                    self.assertEqual(detail_version["upside"], 40.0)

                    analysis_row = web_server.list_analysis_symbols(conn)[0]
                    self.assertFalse(analysis_row["uses_final_scenario_overlay"])
                    self.assertTrue(analysis_row["final_scenario_stale"])
                    self.assertEqual(analysis_row["expected_price"], 140.0)
                finally:
                    conn.close()

    def test_external_scenarios_are_version_scoped_and_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    root_id, version_one = self._seed_version_with_scenarios(conn, symbol="VERS")
                    now = web_server.utc_now_iso()
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            expected_cagr, upside, confidence_level, assumptions_text, business_model_text,
                            business_summary_text, raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 2, 'VERS', 'VERS Inc.', 100, 130, 5, 30, 6, 'assume2', 'model2', 'summary2', '{}', 'rerun', ?)
                        """,
                        (root_id, now),
                    )
                    version_two = conn.execute("SELECT id FROM analysis_versions WHERE analysis_root_id = ? AND version_number = 2", (root_id,)).fetchone()["id"]
                    conn.commit()
                    web_server.create_external_scenario(conn, version_one, self._external_payload(weight=25))
                    self.assertEqual(len(web_server.list_external_scenarios(conn, version_one)), 1)
                    self.assertEqual(len(web_server.list_external_scenarios(conn, version_two)), 0)

                    invalid = self._external_payload()
                    invalid["scenario_json"] = json.dumps({"scenarios": [{"name": "Bear"}]})
                    with self.assertRaisesRegex(ValueError, "exactly 3"):
                        web_server.create_external_scenario(conn, version_one, invalid)
                finally:
                    conn.close()
