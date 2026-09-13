import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
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

    def test_extract_price_accepts_previous_close_as_last_fallback(self):
        ticker = types.SimpleNamespace(marketPrice=lambda: -1, last=None, close=0, prevClose=119.5)
        self.assertEqual(web_server.extract_price(ticker), 119.5)

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
        self.assertEqual(warnings["MSFT"], "No valid market price returned before timeout")
        self.assertEqual(warnings["NVDA"], "No valid market price returned before timeout")

    def test_fetch_ib_prices_waits_for_delayed_warning_and_reports_diagnostics(self):
        class FakeEvent:
            def __init__(self):
                self.handlers = []

            def __iadd__(self, handler):
                self.handlers.append(handler)
                return self

            def __isub__(self, handler):
                self.handlers.remove(handler)
                return self

            def emit(self, *args):
                for handler in list(self.handlers):
                    handler(*args)

        class FakeContract:
            def __init__(self, symbol, conid):
                self.symbol = symbol
                self.conId = conid

        class FakeTicker:
            def __init__(self, contract, ticker_id):
                self.contract = contract
                self.tickerId = ticker_id
                self.last = None
                self.close = None
                self.prevClose = None

            def marketPrice(self):
                return None

        class FakeIB:
            def __init__(self):
                self.errorEvent = FakeEvent()
                self.tickers = []
                self.cancelled = []
                self.sleep_calls = 0

            def positions(self):
                return []

            def portfolio(self):
                return []

            def qualifyContracts(self, *contracts):
                return list(contracts)

            def reqMktData(self, contract, *_args):
                ticker = FakeTicker(contract, len(self.tickers) + 1)
                self.tickers.append(ticker)
                return ticker

            def cancelMktData(self, contract):
                self.cancelled.append(contract.conId)

            def sleep(self, _seconds):
                self.sleep_calls += 1
                if self.tickers and self.sleep_calls == 1:
                    self.errorEvent.emit(self.tickers[0].tickerId, 10167, "Requested market data is not subscribed. Displaying delayed market data.", self.tickers[0].contract)
                    self.tickers[0].last = 123.45

        fake_ib = FakeIB()
        fake_module = types.SimpleNamespace(Stock=lambda symbol, *_args: FakeContract(symbol, 42))
        with mock.patch.dict(sys.modules, {"ib_insync": fake_module}), \
             mock.patch.object(web_server, "get_ib_connection", return_value=fake_ib), \
             mock.patch.object(web_server, "is_tws_data_enabled", return_value=True), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0.5), \
             mock.patch.object(web_server, "get_ib_delayed_price_extra_wait_seconds", return_value=1.0):
            result = web_server.fetch_ib_prices(["MSFT"], return_details=True)

        self.assertEqual(result["prices"]["MSFT"], 123.45)
        self.assertEqual(result["price_sources"]["MSFT"], "delayed_market_data")
        self.assertEqual(result["skipped_symbols"], [])
        self.assertEqual(fake_ib.cancelled, [42])

    def test_fetch_ib_prices_reports_subscription_failures_and_portfolio_fallback(self):
        class FakeEvent:
            def __init__(self):
                self.handlers = []

            def __iadd__(self, handler):
                self.handlers.append(handler)
                return self

            def __isub__(self, handler):
                self.handlers.remove(handler)
                return self

            def emit(self, *args):
                for handler in list(self.handlers):
                    handler(*args)

        class FakeContract:
            def __init__(self, symbol, conid):
                self.symbol = symbol
                self.conId = conid

        class FakeTicker:
            def __init__(self, contract, ticker_id):
                self.contract = contract
                self.tickerId = ticker_id

            def marketPrice(self):
                return None

        class FakeIB:
            def __init__(self):
                self.errorEvent = FakeEvent()
                self.tickers = []

            def positions(self):
                return []

            def portfolio(self):
                return [types.SimpleNamespace(contract=FakeContract("HELD", 8), marketPrice=77.0, position=0.0)]

            def qualifyContracts(self, *contracts):
                return list(contracts)

            def reqMktData(self, contract, *_args):
                ticker = FakeTicker(contract, len(self.tickers) + 1)
                self.tickers.append(ticker)
                return ticker

            def cancelMktData(self, _contract):
                return None

            def sleep(self, _seconds):
                for ticker in self.tickers:
                    if ticker.contract.symbol in {"MISS", "HELD"}:
                        self.errorEvent.emit(ticker.tickerId, 10089, "Requested market data requires additional subscription for API", ticker.contract)

        conids = {"MISS": 1, "HELD": 2}
        fake_ib = FakeIB()
        fake_module = types.SimpleNamespace(Stock=lambda symbol, *_args: FakeContract(symbol, conids[symbol]))
        with mock.patch.dict(sys.modules, {"ib_insync": fake_module}), \
             mock.patch.object(web_server, "get_ib_connection", return_value=fake_ib), \
             mock.patch.object(web_server, "is_tws_data_enabled", return_value=True), \
             mock.patch.object(web_server, "get_ib_price_wait_seconds", return_value=0.01), \
             mock.patch.object(web_server, "get_ib_delayed_price_extra_wait_seconds", return_value=0):
            result = web_server.fetch_ib_prices(["MISS", "HELD"], return_details=True)

        self.assertIsNone(result["prices"]["MISS"])
        self.assertEqual(result["prices"]["HELD"], 77.0)
        self.assertEqual(result["price_sources"]["HELD"], "portfolio_market_price_fallback")
        self.assertEqual(result["diagnostics"]["HELD"]["error_code"], 10089)
        self.assertEqual(result["skipped_symbols"][0]["symbol"], "MISS")
        self.assertEqual(result["skipped_symbols"][0]["error_code"], 10089)
        self.assertEqual(result["skipped_symbols"][0]["reason"], "Market data subscription/API permission issue")

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
                    self.assertEqual(result["skipped"], 0)
                    self.assertEqual(result["kept_previous"], 1)
                    self.assertEqual(result["kept_previous_symbols"][0]["symbol"], "MSFT")
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
                    self.assertEqual(result["skipped_symbols"][0]["symbol"], "NVDA")
                finally:
                    conn.close()

    def test_refresh_latest_analysis_market_prices_uses_historical_close_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = web_server.utc_now_iso()
                    conn.execute("INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)", ("HIST", now, now))
                    root_id = conn.execute("SELECT id FROM analysis_roots WHERE symbol = 'HIST'").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO analysis_versions (
                            analysis_root_id, version_number, symbol, company_name, current_price, expected_price,
                            upside, confidence_level, assumptions_text, business_model_text, business_summary_text,
                            raw_ai_response, source_trigger, created_at
                        ) VALUES (?, 1, 'HIST', 'Historical Fallback', NULL, 120.0, NULL, 6.0, 'a', 'b', 'c', '{}', 'test', ?)
                        """,
                        (root_id, now),
                    )
                    conn.commit()
                    direct_failure = {
                        "symbol": "HIST",
                        "reason": "Market data subscription/API permission issue",
                        "error_code": 10089,
                        "message": "Requested market data requires additional subscription for API",
                    }
                    with mock.patch.object(
                        web_server,
                        "fetch_ib_prices",
                        return_value={
                            "prices": {"HIST": None},
                            "warnings": {"HIST": direct_failure},
                            "diagnostics": {"HIST": direct_failure},
                            "price_sources": {"HIST": None},
                            "skipped_symbols": [direct_failure],
                        },
                    ), mock.patch.object(web_server, "fetch_latest_historical_close", return_value=(99.0, None)):
                        result = web_server.refresh_latest_analysis_market_prices(conn)

                    self.assertEqual(result["updated"], 1)
                    self.assertEqual(result["skipped"], 0)
                    self.assertEqual(result["fallback_symbols"][0]["symbol"], "HIST")
                    self.assertEqual(result["fallback_symbols"][0]["source"], "historical_daily_close_fallback")
                    self.assertIn("10089", result["fallback_symbols"][0]["warning"])
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
        with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8") as handle:
            html = handle.read()
        with open(os.path.join(os.path.dirname(__file__), "static", "app.js"), encoding="utf-8") as handle:
            js = handle.read()
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
        self.assertIn("CORE VS POTENTIAL DRIVERS", prompt)
        self.assertIn("Core Drivers:", prompt)
        self.assertIn("- Must dominate the Base case and normal execution assumptions.", prompt)
        self.assertIn("Potential Drivers:", prompt)
        self.assertIn("- Should primarily affect Bull/Bear optionality and scenario range.", prompt)
        self.assertIn("CORE EVIDENCE PACK AND FRESH INFORMATION", prompt)
        self.assertIn("EVIDENCE WEIGHTING", prompt)
        self.assertIn("Use the Core Evidence Pack to establish factual context, not as a vote-counting mechanism.", prompt)
        self.assertIn("Core Evidence Pack:\n$CoreEvidencePack", prompt)
        self.assertIn("The assumptions field must be a concise 5-year thesis summary", prompt)


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
        css = Path('static/styles.css').read_text(encoding='utf-8')
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
        self.assertIn('id="analysis-copy-key-vars-btn"', html)
        self.assertIn('id="analysis-copy-review-prompt-btn"', html)
        self.assertIn('Copy Key Variables JSON', html)
        self.assertIn('Copy Review Prompt', html)
        self.assertNotIn('Download Key Variables JSON', html)
        self.assertIn('id="analysis-key-variable-import-modal"', html)
        self.assertIn('id="analysis-key-variable-import-template-btn"', html)
        self.assertIn('id="analysis-key-variable-import-save-btn"', html)
        self.assertIn('data-sort-key="core_confidence_diff" class="sortable">Confidence</th>', html)
        self.assertIn('data-sort-key="potential_confidence_diff" class="sortable">Potential Confidence</th>', html)
        js = Path('static/app.js').read_text(encoding='utf-8')
        css = Path('static/styles.css').read_text(encoding='utf-8')
        self.assertIn('<td>${formatPotentialConfidenceDisplay(item)}</td>', js)
        self.assertIn('const potentialConfidenceValue = formatPotentialConfidenceDisplay(position);', js)
        self.assertIn('function parseKeyVariableImportPayload()', js)
        self.assertIn('function buildKeyVariablesCopyPayload()', js)
        self.assertIn('function buildReviewPromptText()', js)
        self.assertIn('function copyTextToClipboard(text)', js)
        self.assertIn('navigator.clipboard?.writeText', js)
        self.assertIn('document.execCommand', js)
        self.assertIn('Copied key variables JSON to clipboard.', js)
        self.assertIn('Copied review prompt to clipboard.', js)
        self.assertIn('Review this company for BakingMoney.', js)
        self.assertIn('Company data:', js)
        self.assertIn('analysisCopyKeyVarsBtn.addEventListener', js)
        self.assertIn('analysisCopyReviewPromptBtn.addEventListener', js)
        self.assertNotIn('download-key-variables', js)
        self.assertIn('/key-variables/import', js)
        self.assertIn('This will replace the current key variables for this analysis version. Continue?', js)
        self.assertIn('data-sort-key="last_activity_at" class="sortable">Last Scenario/Event</th>', html)
        self.assertIn('data-sort-key="costBasis" class="sortable">Cost Value</th>', html)
        self.assertIn('id="tws-data-toggle"', html)
        self.assertIn('Data from TWS', html)
        self.assertIn('data-view="action-plan"', html)
        self.assertIn('id="action-plan-linear-actions-table"', html)
        self.assertIn('action-plan-actions-table', html)
        self.assertIn('Linear Score', html)
        self.assertIn('class="linear-score-column sortable" data-sort-key="linear_allocation_score"', html)
        self.assertIn('class="linear-score-column sortable" data-sort-key="linear_allocation_score">Linear Score</th>', html)
        linear_actions_markup = html.split('id="action-plan-linear-actions-table"', 1)[1].split('</table>', 1)[0]
        self.assertIn('class="market-value-column sortable" data-sort-key="current_position_market_value"', linear_actions_markup)
        self.assertLess(linear_actions_markup.index('class="action-column"'), linear_actions_markup.index('class="market-value-column sortable"'))
        self.assertLess(linear_actions_markup.index('class="market-value-column sortable"'), linear_actions_markup.index('class="target-gap-column"'))
        self.assertNotIn('trigger-price-column', linear_actions_markup)
        self.assertNotIn('distance-column', linear_actions_markup)
        self.assertIn('current-price-column', linear_actions_markup)
        self.assertIn('class="release-date-column sortable" data-sort-key="release_date"', linear_actions_markup)
        self.assertIn('class="momentum-column sortable" data-sort-key="momentum_score"', linear_actions_markup)
        self.assertLess(linear_actions_markup.index('class="rating-column"'), linear_actions_markup.index('class="release-date-column sortable"'))
        self.assertLess(linear_actions_markup.index('class="release-date-column sortable"'), linear_actions_markup.index('class="upside-column sortable"'))
        self.assertLess(linear_actions_markup.index('class="potential-confidence-column sortable"'), linear_actions_markup.index('class="momentum-column sortable"'))
        self.assertLess(linear_actions_markup.index('class="momentum-column sortable"'), linear_actions_markup.index('class="current-weight-column sortable"'))
        self.assertNotIn('reason-column', linear_actions_markup)
        self.assertNotIn('id="action-plan-table"', html)
        self.assertNotIn('id="action-plan-tab-buckets"', html)
        self.assertNotIn('id="action-plan-buckets-panel"', html)
        self.assertNotIn('Bucket Allocation', html)
        self.assertIn('Action Amount', html)
        self.assertIn('Cash-like Available', js)
        self.assertIn('Unallocated Target Capacity', js)
        self.assertIn('id="positions-portfolio-summary"', html)
        self.assertIn('id="config-action-cash-equivalent-symbols"', html)
        self.assertIn('id="config-action-treat-cash-equivalents-as-cash"', html)
        self.assertIn('id="config-action-min-executable-trade-amount"', html)
        self.assertIn('id="config-help-modal"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn('id="config-help-close-btn"', html)
        self.assertIn('id="action-plan-detail-view"', html)
        self.assertIn('id="action-plan-open-analysis-btn"', html)
        self.assertIn('#action-plan-summary .status', css)
        self.assertIn('#action-plan-actions-panel .table-wrap', css)
        self.assertIn('overflow-x: auto;', css)
        self.assertIn('min-width: 1980px;', css)
        self.assertIn('table-layout: fixed;', css)
        self.assertIn('.action-plan-actions-table .target-gap-column', css)
        self.assertIn('.action-plan-actions-table .funding-column', css)
        self.assertIn('min-width: 160px;', css)
        self.assertIn('min-width: 280px;', css)
        self.assertIn('max-width: 420px;', css)
        self.assertIn('class="current-price-column"', html)
        self.assertIn('class="target-band-column sortable" data-sort-key="target_band"', html)
        self.assertNotIn('class="distance-column sortable" data-sort-key="distance_to_trigger_percent"', linear_actions_markup)
        self.assertIn('class="upside-column sortable" data-sort-key="upside"', html)
        self.assertIn('class="core-confidence-column sortable" data-sort-key="core_confidence_diff"', html)
        self.assertIn('class="potential-confidence-column sortable" data-sort-key="potential_confidence_diff"', html)
        self.assertIn('class="current-weight-column sortable" data-sort-key="current_position_weight"', html)
        self.assertIn('class="gap-column sortable" data-sort-key="position_gap_to_mid"', html)
        self.assertIn('current-price-cell', js)
        self.assertIn('market-value-cell', js)
        self.assertIn("if (key === 'current_position_market_value')", js)
        self.assertIn("formatCurrencyValue(item.current_position_market_value ?? 0, 'USD')", js)
        self.assertIn('function formatLinearReleaseDate(item)', js)
        self.assertIn('function getLinearReleaseDateSortValue(item)', js)
        self.assertIn('function formatLinearMomentum(item)', js)
        self.assertIn("if (key === 'release_date') return getLinearReleaseDateSortValue(item);", js)
        self.assertNotIn('distance-cell', linear_actions_markup)
        self.assertIn('target-band-cell', js)
        self.assertIn('target-band-range', js)
        self.assertIn('.action-plan-actions-table .current-price-column', css)
        self.assertIn('.action-plan-actions-table .market-value-column', css)
        self.assertIn('.action-plan-actions-table .distance-column', css)
        self.assertIn('.action-plan-actions-table .target-band-column', css)
        self.assertIn('.action-plan-actions-table .target-band-range', css)
        self.assertIn('min-width: 150px;', css)
        self.assertIn('#action-plan-linear-actions-table { min-width: 1690px;', css)
        self.assertIn('#action-plan-linear-actions-table .release-date-column', css)
        self.assertIn('#action-plan-linear-actions-table .momentum-column', css)
        self.assertIn('Open Full Analysis', html)
        self.assertIn('id="action-plan-rating-filter"', html)
        self.assertIn('id="action-plan-action-filter"', html)
        self.assertIn('Action Filter', html)
        action_filter_markup = html.split('id="action-plan-action-filter-panel"', 1)[1].split('id="action-plan-linear-actions-panel"', 1)[0]
        for label in ('Add', 'Trim', 'Sell', 'Hold', 'Watch', 'Watch / Extended', 'Watch / Rating Guardrail'):
            self.assertIn(f'>{label}</span>', action_filter_markup)
        for label in ('Strong Add', 'Starter Buy', 'Strong Trim', 'Re-evaluate'):
            self.assertNotIn(f'>{label}</span>', action_filter_markup)
        self.assertIn("{ key: 'watch_extended', label: 'Watch / Extended' }", js)
        self.assertIn("{ key: 'watch_rating_guardrail', label: 'Watch / Rating Guardrail' }", js)
        self.assertIn("if (label === 'Watch / Extended') return 'watch_extended';", js)
        self.assertIn("if (label === 'Watch / Rating Guardrail') return 'watch_rating_guardrail';", js)
        self.assertIn("if (label === 'Watch') return 'watch';", js)
        self.assertIn('id="config-ib-delayed-price-extra-wait-seconds"', html)
        self.assertIn('ib_delayed_price_extra_wait_seconds', js)
        self.assertIn('formatSkippedPriceSymbols', js)
        self.assertIn('logSkippedPriceDetails', js)
        self.assertIn('logFallbackPriceDetails', js)
        self.assertIn('fallback used for', js)
        self.assertIn('kept previous price for', js)
        self.assertIn('.rating-filter-panel.is-floating', css)
        self.assertIn('function positionFloatingFilterPanel', js)
        self.assertIn('function repositionOpenFloatingFilters', js)
        self.assertIn("window.addEventListener('resize', repositionOpenFloatingFilters)", js)
        self.assertIn("window.addEventListener('scroll', repositionOpenFloatingFilters, true)", js)
        self.assertNotIn('data-action-plan-setting="action_bucket_buy_target"', html.split('<template', 1)[0])
        self.assertIn('async function loadActionPlan()', js)
        self.assertIn('/api/action-plan', js)
        self.assertIn('function getActionPlanNumericSortValue(item, key)', js)
        self.assertIn("if (key === 'target_band') return window.ActionPlanSorting.getTargetBandMidpoint(item);", js)
        self.assertIn('updateActionPlanSortHeaderState(); renderActionPlan();', js)
        self.assertIn('window.ActionPlanSorting.sortRowsByNumericValue(items', js)
        self.assertIn('class="target-band-column sortable" data-sort-key="target_band">Target Band</th>', html)
        self.assertIn('id="linear-cap-explanation-modal"', html)
        self.assertIn('id="linear-cap-explanation-content"', html)
        self.assertIn('id="linear-cap-explanation-close-btn"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn('function hasLinearTargetCap(item)', js)
        self.assertIn('amount != null && amount > 0.0001', js)
        self.assertIn("warningButton.className = 'cap-warning-button'", js)
        self.assertIn('View target cap explanation for', js)
        self.assertIn('event.stopPropagation()', js)
        self.assertIn('function openLinearCapExplanationModal(item)', js)
        self.assertIn("['Target before cap'", js)
        self.assertIn("['Target after cap'", js)
        self.assertIn("['Cap impact'", js)
        self.assertIn("['Effective cap'", js)
        self.assertIn('closeLinearCapExplanationModal();', js)
        self.assertIn('.cap-warning-button', css)
        self.assertIn('.cap-explanation-modal', css)
        self.assertLess(html.index('/static/action_plan_sorting.js'), html.index('/static/app.js'))
        self.assertIn('Weighted Count Used', js)
        self.assertIn('Total Weighted Eligible Count', js)
        self.assertNotIn('weighted_eligible_count_in_bucket', js)
        self.assertIn('Bucket Weight / Effective Stock', js)
        self.assertIn('Uncapped Bucket Target', js)
        self.assertIn('effective_weighted_count_used', js)
        self.assertIn('Max Effective Count', js)
        self.assertIn('action-plan-bucket-diagnostic', css)
        self.assertIn('function renderActionPlanBuckets()', js)
        self.assertIn('function renderActionPlanBucketPanel(bucket)', js)
        self.assertIn('function renderActionPlanBucketCompanyTable(rows, bucket)', js)
        self.assertIn('function setActionPlanTab(tab)', js)
        self.assertIn('function setActionPlanActionMode(mode)', js)
        self.assertIn("'linear_min_core_net', 'linear_min_potential_net'", js)
        self.assertIn("linear_full_core_net must be greater than linear_min_core_net", js)
        self.assertIn("linear_full_potential_net must be greater than linear_min_potential_net", js)
        self.assertIn('data-action-plan-setting="core_confidence_penalty_threshold"', html)
        self.assertIn('data-action-plan-setting="upside_penalty"', html)
        self.assertIn('data-action-plan-setting="potential_confidence_penalty"', html)
        self.assertIn('data-action-plan-setting="hold_rating_penalty_enabled"', html)
        self.assertIn('data-action-plan-setting="linear_score_allocation_power"', html)
        self.assertIn('data-action-plan-setting="linear_add_band_tolerance_pct"', html)
        self.assertIn('data-action-plan-setting="linear_trim_band_tolerance_pct"', html)
        self.assertIn('data-action-plan-setting="linear_release_date_warning_days"', html)
        self.assertIn('Linear release date warning days', html)
        self.assertIn('Set to 0 to disable.', html)
        self.assertNotIn('data-action-plan-setting="linear_target_band_tolerance_pct" type="number"', html)
        self.assertIn('data-action-plan-setting="linear_rating_bonus_enabled"', html)
        self.assertIn('data-action-plan-setting="linear_strong_buy_rating_bonus"', html)
        self.assertIn('data-action-plan-setting="linear_buy_rating_bonus"', html)
        self.assertIn('data-action-plan-setting="linear_frontier_optionality_max_boost_pct"', html)
        self.assertIn('Maximum Frontier Optionality Boost %', html)
        self.assertIn('data-action-plan-setting="linear_block_buy_actions_for_hold_rating"', html)
        self.assertIn("'core_confidence_penalty', 'upside_penalty', 'potential_confidence_penalty', 'hold_rating_penalty', 'linear_strong_buy_rating_bonus', 'linear_buy_rating_bonus'", js)
        self.assertIn('linear_frontier_optionality_max_boost_pct', js)
        self.assertIn('function renderLinearAllocationRows()', js)
        self.assertIn('function getLinearReleaseDateWarning(item)', js)
        self.assertIn('function renderLinearReleaseDateWarning(item)', js)
        self.assertIn('class="release-date-warning-icon"', js)
        self.assertIn('Release date is within ${warningDays} days', js)
        self.assertIn('renderLinearReleaseDateWarning(item)', js)
        self.assertIn('.release-date-warning-icon', css)
        self.assertIn('actionPlanLinearActionsTableBody', js)
        self.assertIn('getFilteredLinearActionPlanItems', js)
        self.assertIn('sortLinearActionPlanItems', js)
        self.assertIn("let actionPlanLinearSort = { key: 'linear_allocation_score', direction: 'desc' }", js)
        self.assertIn("{ key: 'target_gap_amount', direction: 'desc' }", js)
        self.assertIn('Cash / Unallocated', js)
        self.assertIn('Bucket Reconciliation', js)
        self.assertIn('Allocation Score', js)
        self.assertIn('Allocation Risk Modifier', js)
        self.assertNotIn('Allocation Upside Weight Used', js)
        self.assertNotIn('Allocation Core Weight Used', js)
        self.assertNotIn('Allocation Potential Weight Used', js)
        self.assertNotIn('Allocation Risk Penalty Strength', js)
        self.assertIn('const CONFIG_HELP = {};', js)
        self.assertIn('function initializeConfigHelpIcons()', js)
        self.assertIn('function openConfigHelpModal(key, label, triggerEl)', js)
        self.assertIn('function closeConfigHelpModal()', js)
        self.assertIn('Show help for ${label}', js)
        self.assertIn('Weighted Count = clamp((Bucket Sizing Score - Min Score) / (Full Score - Min Score), 0, Max Contribution)', js)
        self.assertIn('Uncapped Bucket Target = Weighted Count Used × Weight / Effective Stock', js)
        linear_help_keys = [
            'linear_allocated_target_total_pct',
            'linear_min_expected_cagr',
            'linear_full_expected_cagr',
            'linear_min_upside',
            'linear_full_upside',
            'linear_min_core_net',
            'linear_full_core_net',
            'linear_min_potential_net',
            'linear_full_potential_net',
            'linear_expected_cagr_weight',
            'linear_upside_weight',
            'linear_core_confidence_weight',
            'linear_potential_confidence_weight',
            'linear_confidence_quality_weight',
            'linear_min_score_threshold',
            'linear_score_allocation_power',
            'linear_zero_target_if_expected_cagr_negative',
            'linear_zero_target_if_upside_negative',
            'linear_max_single_stock_pct',
            'linear_add_band_tolerance_pct',
            'linear_trim_band_tolerance_pct',
            'linear_enable_risk_caps',
            'linear_negative_core_net_cap_pct',
            'linear_low_core_net_threshold',
            'linear_low_core_net_cap_pct',
            'linear_high_bearish_confidence_min_threshold',
            'linear_high_bearish_confidence_max_threshold',
            'linear_high_bearish_confidence_cap_pct',
            'linear_high_extension_guardrail_enabled',
            'linear_high_extension_risk_threshold',
        ]
        for key in linear_help_keys:
            self.assertIn(f"'{key}'", js)
        self.assertNotIn('data-action-plan-setting="linear_high_bearish_confidence_threshold"', html)
        self.assertIn('Linear high bearish confidence min threshold (raw score)', html)
        self.assertIn('Linear high bearish confidence max threshold (raw score)', html)
        self.assertIn('This is a raw confidence score, not a percentage.', js)
        self.assertIn('Total percentage of the portfolio the Linear Allocation model is allowed to allocate to stocks.', js)
        self.assertIn('Negative values are valid.', js)
        self.assertIn('Core Net confidence level that receives zero score contribution', js)
        self.assertIn('Potential Net confidence level that receives zero score contribution', js)
        penalty_help_keys = [
            'core_confidence_penalty_threshold',
            'core_confidence_penalty',
            'upside_penalty_threshold',
            'upside_penalty',
            'potential_confidence_penalty_threshold',
            'potential_confidence_penalty',
            'hold_rating_penalty_enabled',
            'hold_rating_penalty',
            'linear_rating_bonus_enabled',
            'linear_strong_buy_rating_bonus',
            'linear_buy_rating_bonus',
            'linear_block_buy_actions_for_hold_rating',
            'linear_high_extension_guardrail_enabled',
            'linear_high_extension_risk_threshold',
        ]
        for key in penalty_help_keys:
            self.assertIn(f"addConfigHelp('{key}'", js)
        self.assertIn('Multiplicative penalty applied to the Linear Score', js)
        self.assertIn('score factor *= (1 - core_confidence_penalty)', js)
        self.assertIn('keeps 85% of its pre-penalty Linear Score', js)
        self.assertIn('keeps 80% of its pre-penalty Linear Score', js)
        self.assertIn('Multiple triggered penalties compound multiplicatively', js)
        self.assertIn('0.85 × 0.80 = 0.68', js)
        self.assertIn('Final Linear Score = Penalty-adjusted Linear Score × Rating Bonus Factor', js)
        self.assertIn('A value of 0.05 means a Strong Buy stock keeps 105%', js)
        self.assertIn('A value of 0.02 means a Buy-rated stock keeps 102%', js)
        self.assertIn('Watch / Rating Guardrail', js)
        self.assertIn('Rating blocks add', js)
        self.assertIn('data-action-plan-setting="linear_high_extension_guardrail_enabled"', html)
        self.assertIn('data-action-plan-setting="linear_high_extension_risk_threshold"', html)
        self.assertIn('Watch / Extended', js)
        self.assertIn('Extension Risk at or above this 0–5 threshold', js)
        self.assertIn('Allocation Weight = max(0, Linear Score - Min Score Threshold) ^ Allocation Power', js)
        self.assertIn('Target Low = Linear Target Mid × (1 - Add Band Tolerance %)', js)
        self.assertIn('Target High = Linear Target Mid × (1 + Trim Band Tolerance %)', js)
        self.assertIn('.config-help-button', css)
        self.assertIn('.config-help-modal-content', css)
        self.assertIn('.config-help-related', css)
        self.assertIn("{ label: 'Symbol', sortable: false }", js)
        self.assertIn("{ label: 'Action', sortable: false }", js)
        self.assertIn('class="sortable action-plan-bucket-sortable"', js)
        self.assertIn("{ label: 'Current Weight', key: 'current_weight', sortable: true }", js)
        self.assertIn("{ label: 'Target Mid', key: 'target_mid', sortable: true }", js)
        self.assertIn("{ label: 'Target Band', key: 'target_band', sortable: true }", js)
        self.assertIn("{ label: 'Gap to Mid', key: 'gap_to_mid', sortable: true }", js)
        self.assertIn("{ label: 'Target Gap', key: 'target_gap_amount', sortable: true }", js)
        self.assertIn("{ label: 'Market Value', key: 'market_value', sortable: true }", js)
        self.assertIn("{ label: 'Core Confidence', key: 'core_confidence_diff', sortable: true }", js)
        self.assertIn("{ label: 'Potential Confidence', key: 'potential_confidence_diff', sortable: true }", js)
        self.assertIn("{ label: 'Allocation Score', key: 'allocation_score', sortable: true }", js)
        self.assertIn("{ label: 'Bucket Sizing Score', key: 'bucket_sizing_score', sortable: true }", js)
        self.assertIn("{ label: 'Target Mid Before Caps', key: 'target_mid_before_caps', sortable: true }", js)
        self.assertIn('function sortActionPlanBucketRows(bucket, rows)', js)
        self.assertIn('function getActionPlanBucketSortValue(item, key)', js)
        self.assertIn("actionPlanBucketsContentEl.querySelectorAll('.action-plan-bucket-sortable')", js)
        self.assertNotIn('<th>Company Name</th><th>Action</th>', js)
        self.assertNotIn('<th>Bucket Sizing Score</th><th>Weighted Count</th><th>Target Mid Before Caps</th>', js)
        self.assertIn('Available Buy Budget', js)
        self.assertIn('Total Add Demand', js)
        self.assertIn('Funded Add Amount', js)
        self.assertIn('Funding Status', js)
        self.assertIn('Target Market Value', js)
        self.assertIn('function getLinearTargetMarketValue(item)', js)
        self.assertIn('target_gap_amount', js)
        self.assertIn('Bucket Sizing Score', js)
        self.assertIn('Target Mid Before Caps', js)
        self.assertNotIn('<th>Target Mid Before Caps</th><th>Target Mid After Caps</th><th>Cap Reason</th>', js)
        self.assertIn('function openActionPlanDetail(symbol)', js)
        self.assertIn('/api/action-plan/${encodeURIComponent(symbol)}', js)
        self.assertIn('function renderActionPlanDetail(item)', js)
        self.assertIn('function formatLinearPositionStatus(status)', js)
        self.assertIn('function formatLinearGuardrailState(value)', js)
        self.assertIn('function formatFrontierOptionalityApplied(score)', js)
        self.assertIn('function formatLinearThresholdApplied(score)', js)
        self.assertIn("<h4>Linear Target Calculation</h4>", js)
        self.assertIn('Linear Score Before Penalty', js)
        self.assertIn('Linear Score After Penalty', js)
        self.assertIn('Linear Score Before Min Threshold', js)
        self.assertIn('Minimum Score Threshold', js)
        self.assertIn('Minimum Threshold Applied', js)
        self.assertIn('Frontier Score', js)
        self.assertIn('Frontier Boost Factor', js)
        self.assertIn('Frontier Boost Applied', js)
        self.assertIn('Linear Score Before Frontier Boost', js)
        self.assertIn('Linear Score After Boost', js)
        self.assertNotIn('Frontier Boost Reason', js)
        self.assertNotIn('Frontier Optionality Reason', js)
        self.assertNotIn('Frontier Optionality Score', js)
        self.assertIn("<h4>Target Band Calculation</h4>", js)
        self.assertNotIn("<h4>Linear Score Breakdown</h4>", js)
        self.assertNotIn('function formatTriggerDistanceLabel(item)', js)
        self.assertNotIn('function isHoldInsideTargetWithoutActiveTrigger(item)', js)
        self.assertNotIn('function formatRelevantTriggerPrice(item)', js)
        self.assertNotIn('function formatDynamicRequiredUpside(item)', js)
        self.assertNotIn("['Trigger Price', formatRelevantTriggerPrice(item)]", js)
        self.assertNotIn("['Distance to Trigger', formatTriggerDistanceLabel(item)]", js)
        self.assertNotIn("['Relevant Trigger', formatRelevantTriggerPrice(item)]", js)
        self.assertNotIn("['Dynamic Required Upside', formatDynamicRequiredUpside(item)]", js)
        self.assertIn('action_amount_label', js)
        self.assertIn('setSelectedActionPlanRatings(getAllRatingFilterKeys())', js)
        self.assertIn('setSelectedActionPlanActions(getAllActionPlanActionFilterKeys())', js)
        self.assertIn('selectedActions.has(getActionPlanActionFilterKey(item.action))', js)
        self.assertIn('openActionPlanDetail(btn.dataset.symbol)', js)
        self.assertIn("openAnalysisDetailForSymbol(selectedActionPlanDetail.symbol, { origin: 'action_plan' })", js)
        self.assertIn("analysisDetailOrigin === 'action_plan'", js)
        self.assertIn('← Back to Action Plan', js)
        self.assertIn("setView('action-plan', { skipLoad: true })", js)
        self.assertIn('.action-plan-bucket-table', css)
        self.assertIn('.action-plan-tabs', css)

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
        self.assertIn('id="earnings-review-tab-workflow" class="earnings-review-tab"', html)
        self.assertIn('id="earnings-review-tab-calendar" class="earnings-review-tab active"', html)
        self.assertIn('id="earnings-review-workflow-panel" class="hidden"', html)
        self.assertIn('id="earnings-review-calendar-panel" class="analysis-screen"', html)
        self.assertIn('id="earnings-calendar-table"', html)
        self.assertIn('id="earnings-calendar-status"', html)
        self.assertIn('id="earnings-calendar-fiscal-year-filter"', html)
        self.assertIn('id="earnings-calendar-fiscal-quarter-filter"', html)
        self.assertIn('Fiscal Year Filter', html)
        self.assertIn('Fiscal Quarter Filter', html)
        self.assertIn('value="Q1" /> <span class="rating-filter-option-label">Q1</span>', html)
        self.assertIn('value="Q4" /> <span class="rating-filter-option-label">Q4</span>', html)
        self.assertIn('value="past" /> <span class="rating-filter-option-label">Past</span>', html)
        self.assertIn('value="yesterday" /> <span class="rating-filter-option-label">Yesterday</span>', html)
        self.assertIn('value="today" /> <span class="rating-filter-option-label">Today</span>', html)
        self.assertIn('value="tomorrow" /> <span class="rating-filter-option-label">Tomorrow</span>', html)
        self.assertIn('value="current_week" /> <span class="rating-filter-option-label">Current Week</span>', html)
        self.assertIn('value="next_week" /> <span class="rating-filter-option-label">Next Week</span>', html)
        self.assertIn('value="future" /> <span class="rating-filter-option-label">Future</span>', html)
        self.assertLess(html.index('value="past"'), html.index('value="yesterday"'))
        self.assertLess(html.index('value="yesterday"'), html.index('value="today"'))
        self.assertLess(html.index('value="today"'), html.index('value="tomorrow"'))
        self.assertLess(html.index('value="tomorrow"'), html.index('value="current_week"'))
        self.assertLess(html.index('value="current_week"'), html.index('value="next_week"'))
        self.assertLess(html.index('value="next_week"'), html.index('value="future"'))
        css = Path('static/styles.css').read_text(encoding='utf-8')
        self.assertIn('#earnings-calendar-date-filter .rating-filter-panel', css)
        self.assertIn('width: min(280px, calc(100vw - 48px));', css)
        self.assertIn('min-width: min(260px, calc(100vw - 48px));', css)
        self.assertIn('width: min(430px, calc(100vw - 16px));', css)
        self.assertIn('min-width: min(430px, calc(100vw - 16px));', css)
        self.assertIn('overflow-x: hidden;', css)
        self.assertIn('overflow-y: auto;', css)
        self.assertIn('padding: 12px;', css)
        self.assertIn('#earnings-calendar-date-filter .rating-filter-option,', css)
        self.assertIn('.earnings-calendar-multiselect .rating-filter-option {', css)
        self.assertIn('display: flex;', css)
        self.assertIn('justify-content: flex-start;', css)
        self.assertIn('gap: 10px;', css)
        self.assertIn('white-space: nowrap;', css)
        self.assertIn('#earnings-calendar-date-filter .rating-filter-option-label', css)
        js = Path('static/app.js').read_text(encoding='utf-8')
        date_filter_js = Path('static/earnings_calendar_date_filters.js').read_text(encoding='utf-8')
        self.assertIn("{ key: 'yesterday', label: 'Yesterday' }", js)
        self.assertIn("{ key: 'tomorrow', label: 'Tomorrow' }", js)
        self.assertIn("{ key: 'current_week', label: 'Current Week' }", js)
        self.assertIn("{ key: 'next_week', label: 'Next Week' }", js)
        self.assertLess(html.index('/static/earnings_calendar_date_filters.js'), html.index('/static/app.js'))
        self.assertIn("let earningsReviewActiveTab = 'calendar';", js)
        self.assertIn("setEarningsReviewTab('calendar');\n    loadEarningsReview();", js)
        self.assertIn("setEarningsReviewTab('calendar');\nsetPositionsRatingFilterOpen(false);", js)
        self.assertIn('function releaseDateMatchesEarningsCalendarDateFilters(releaseDateValue, today, selectedDateFilters)', js)
        self.assertIn('function getAvailableEarningsCalendarFiscalYears()', js)
        self.assertIn('function getCurrentCalendarYear()', js)
        self.assertIn('function getCurrentCalendarQuarter()', js)
        self.assertIn('let earningsCalendarAddFormDefaultsApplied = false;', js)
        self.assertIn('function resetEarningsCalendarAddFormDefaults()', js)
        self.assertIn('function applyEarningsCalendarEntryDefaults({ force = false } = {})', js)
        self.assertIn('Math.floor(month / 3) + 1', js)
        self.assertIn('resetEarningsCalendarAddFormDefaults();', js)
        self.assertIn('earningsCalendarAddFormDefaultsApplied = true;', js)
        self.assertIn('applyEarningsCalendarEntryDefaults({ force: true });', js)
        self.assertIn('applyEarningsCalendarEntryDefaults();', js)
        self.assertIn('getSelectedEarningsCalendarFiscalYears()', js)
        self.assertIn('getSelectedEarningsCalendarFiscalQuarters()', js)
        self.assertIn('window.EarningsCalendarDateFilters.earningsCalendarItemMatchesFilters', js)
        self.assertIn('window.EarningsCalendarDateFilters.compareEarningsCalendarItems', js)
        self.assertIn('syncEarningsCalendarFiscalYearFilterOptions();', js)
        self.assertIn('function getMondayWeekRange(referenceDate, weekOffset = 0)', date_filter_js)
        self.assertIn("selectedDateFilters.has('current_week')", date_filter_js)
        self.assertIn("selectedDateFilters.has('next_week')", date_filter_js)
        self.assertIn('function earningsReleaseTimingPriority(value)', date_filter_js)
        self.assertIn('function compareEarningsCalendarItems(leftItem, rightItem, dateDirection = \'asc\')', date_filter_js)
        self.assertIn("if (selectedDateFilters.has('past') && releaseTime < todayTime) return true;", date_filter_js)
        self.assertIn("if (selectedDateFilters.has('yesterday') && releaseTime === yesterday.getTime()) return true;", date_filter_js)
        self.assertIn("if (selectedDateFilters.has('tomorrow') && releaseTime === tomorrow.getTime()) return true;", date_filter_js)
        self.assertIn("if (selectedDateFilters.has('future') && releaseTime > todayTime) return true;", date_filter_js)
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

    def test_company_detail_displays_frontier_score_dropdown(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn('function renderFrontierOptionalitySection()', js)
        self.assertIn('Frontier Score', js)
        self.assertIn('const FRONTIER_SCORE_OPTIONS = [0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5];', js)
        self.assertIn('id="analysis-frontier-score-select"', js)
        self.assertIn('frontier-score-field', js)
        self.assertIn('<select id="analysis-frontier-score-select" class="earnings-calendar-select"', js)
        self.assertIn("analysisSummary.addEventListener('change'", js)
        self.assertIn('saveFrontierScore(target.value)', js)
        self.assertIn('/frontier-optionality', js)
        self.assertIn('frontier_optionality_score: score', js)
        self.assertNotIn('Frontier Optionality Score', js)
        self.assertNotIn('Frontier Optionality Notes', js)
        self.assertNotIn('Edit Frontier Optionality', js)
        self.assertNotIn('id="analysis-frontier-optionality-score-input"', js)
        self.assertNotIn('id="analysis-frontier-optionality-notes-input"', js)
        self.assertNotIn('frontier_optionality_notes: notes', js)

    def test_earnings_review_navigation_uses_internal_view_state_without_hash(self):
        from pathlib import Path
        js = Path('static/app.js').read_text(encoding='utf-8')
        self.assertIn('function showEarningsReviewList()', js)
        self.assertIn('function showEarningsReviewDetail()', js)
        self.assertNotIn('function setEarningsReviewHash(symbol, reviewId = null)', js)
        self.assertNotIn('window.location.hash', js)
        self.assertNotIn("window.addEventListener('hashchange'", js)
        self.assertNotIn("'#earnings-review'", js)
        self.assertNotIn('"#earnings-review"', js)
        self.assertIn('function openEarningsReviewSymbolHistory(symbol)', js)
        self.assertIn('function openEarningsReviewRecordDetail(symbol, reviewId)', js)
        self.assertIn('function addEarningsReviewSymbol()', js)
        self.assertIn('function loadEarningsCalendar()', js)
        self.assertIn('function renderEarningsCalendarTable()', js)
        self.assertIn('function openAnalysisDetailFromPositions(symbol)', js)
        self.assertIn("openAnalysisDetailForSymbol(btn.dataset.symbol, { origin: 'earnings_review' })", js)
        self.assertIn("['positions', 'action_plan', 'earnings_review'].includes(options.origin)", js)
        self.assertIn("analysisDetailOrigin === 'earnings_review'", js)
        self.assertIn('← Back to Earnings Review', js)
        self.assertIn("setView('earnings-review', { skipLoad: true })", js)
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
    @staticmethod
    def _progressive_bearish_settings(**overrides):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_high_bearish_confidence_min_threshold": 4.0,
            "linear_high_bearish_confidence_max_threshold": 8.0,
            "linear_high_bearish_confidence_cap_pct": 5.0,
            **overrides,
        })
        return settings

    def test_progressive_linear_bearish_cap_interpolates_and_clamps(self):
        settings = self._progressive_bearish_settings()
        expected = {
            3.0: (0.0, 10.0),
            4.0: (0.0, 10.0),
            5.0: (0.25, 8.75),
            6.0: (0.50, 7.50),
            7.0: (0.75, 6.25),
            8.0: (1.0, 5.00),
            9.0: (1.0, 5.00),
        }
        for confidence, (expected_progress, expected_midpoint) in expected.items():
            with self.subTest(confidence=confidence):
                details = web_server._linear_progressive_bearish_cap_details(
                    {"core_bearish_confidence": confidence}, 10.0, settings
                )
                self.assertAlmostEqual(details["bearish_cap_progress"], expected_progress)
                self.assertAlmostEqual(details["bearish_cap_candidate_mid"], expected_midpoint)
                self.assertGreaterEqual(details["bearish_cap_progress"], 0.0)
                self.assertLessEqual(details["bearish_cap_progress"], 1.0)

    def test_progressive_linear_bearish_cap_never_increases_midpoint_at_or_below_cap(self):
        settings = self._progressive_bearish_settings()
        for midpoint in (4.0, 5.0):
            with self.subTest(midpoint=midpoint):
                details = web_server._linear_progressive_bearish_cap_details(
                    {"core_bearish_confidence": 8.0}, midpoint, settings
                )
                self.assertEqual(details["bearish_cap_progress"], 1.0)
                self.assertEqual(details["bearish_cap_candidate_mid"], midpoint)

    def test_progressive_linear_bearish_cap_handles_decimal_raw_confidence(self):
        settings = self._progressive_bearish_settings()
        details = web_server._linear_progressive_bearish_cap_details(
            {"core_bearish_confidence": 6.875}, 10.0, settings
        )
        self.assertAlmostEqual(details["bearish_cap_progress"], 0.71875)
        self.assertAlmostEqual(details["bearish_cap_candidate_mid"], 6.40625)
        raw_score_details = web_server._linear_progressive_bearish_cap_details(
            {"core_bearish_confidence": 0.06875}, 10.0, settings
        )
        self.assertEqual(raw_score_details["bearish_cap_progress"], 0.0)
        self.assertEqual(raw_score_details["bearish_cap_candidate_mid"], 10.0)

    def test_progressive_linear_bearish_cap_slightly_above_limit(self):
        settings = self._progressive_bearish_settings()
        details = web_server._linear_progressive_bearish_cap_details(
            {"core_bearish_confidence": 6.0}, 6.0, settings
        )
        self.assertAlmostEqual(details["bearish_cap_candidate_mid"], 5.5)

    def test_equal_progressive_bearish_thresholds_reproduce_binary_behavior(self):
        settings = self._progressive_bearish_settings(
            linear_high_bearish_confidence_min_threshold=8.0,
            linear_high_bearish_confidence_max_threshold=8.0,
        )
        below = web_server._linear_progressive_bearish_cap_details(
            {"core_bearish_confidence": 7.999}, 10.0, settings
        )
        at_threshold = web_server._linear_progressive_bearish_cap_details(
            {"core_bearish_confidence": 8.0}, 10.0, settings
        )
        self.assertEqual(below["bearish_cap_progress"], 0.0)
        self.assertEqual(below["bearish_cap_candidate_mid"], 10.0)
        self.assertEqual(at_threshold["bearish_cap_progress"], 1.0)
        self.assertEqual(at_threshold["bearish_cap_candidate_mid"], 5.0)

    def test_invalid_progressive_bearish_settings_are_safe_and_rejected_on_save(self):
        invalid_settings = self._progressive_bearish_settings(
            linear_high_bearish_confidence_min_threshold=8.0,
            linear_high_bearish_confidence_max_threshold=4.0,
        )
        details = web_server._linear_progressive_bearish_cap_details(
            {"core_bearish_confidence": 6.0}, 10.0, invalid_settings
        )
        self.assertFalse(details["bearish_cap_configuration_valid"])
        self.assertIn("Minimum bearish threshold exceeds maximum", details["bearish_cap_diagnostic"])
        self.assertEqual(details["bearish_cap_candidate_mid"], 10.0)
        with self.assertRaisesRegex(ValueError, "max_threshold must be greater"):
            web_server.validate_action_plan_settings(invalid_settings)

        missing_settings = self._progressive_bearish_settings()
        missing_settings["linear_high_bearish_confidence_min_threshold"] = None
        missing = web_server._linear_progressive_bearish_cap_details(
            {"core_bearish_confidence": None}, 10.0, missing_settings
        )
        self.assertFalse(missing["bearish_cap_configuration_valid"])
        self.assertIn("Invalid or missing progressive bearish-cap setting", missing["bearish_cap_diagnostic"])
        self.assertEqual(missing["bearish_cap_candidate_mid"], 10.0)

    def test_legacy_linear_bearish_threshold_migrates_to_equal_min_and_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "test.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    conn.execute(
                        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                        ("linear_high_bearish_confidence_threshold", "6.5", web_server.utc_now_iso()),
                    )
                    conn.commit()
                    settings = web_server.get_action_plan_settings(conn)
                    self.assertEqual(settings["linear_high_bearish_confidence_min_threshold"], 6.5)
                    self.assertEqual(settings["linear_high_bearish_confidence_max_threshold"], 6.5)
                    stored = conn.execute(
                        "SELECT value FROM app_settings WHERE key = ?",
                        ("linear_high_bearish_confidence_threshold",),
                    ).fetchone()
                    self.assertEqual(stored["value"], "6.5")

                    conn.executemany(
                        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)",
                        [
                            ("linear_high_bearish_confidence_min_threshold", "invalid", web_server.utc_now_iso()),
                            ("linear_high_bearish_confidence_max_threshold", "inf", web_server.utc_now_iso()),
                        ],
                    )
                    conn.commit()
                    with self.assertLogs(web_server.logger, level="WARNING") as captured:
                        fallback = web_server.get_action_plan_settings(conn)
                    self.assertEqual(fallback["linear_high_bearish_confidence_min_threshold"], 4.0)
                    self.assertEqual(fallback["linear_high_bearish_confidence_max_threshold"], 8.0)
                    self.assertTrue(any("safe default" in message for message in captured.output))
                finally:
                    conn.close()

        legacy_payload = {"linear_high_bearish_confidence_threshold": 6.5}
        effective = web_server.validate_action_plan_settings(legacy_payload)
        self.assertEqual(effective["linear_high_bearish_confidence_min_threshold"], 6.5)
        self.assertEqual(effective["linear_high_bearish_confidence_max_threshold"], 6.5)

    def test_progressive_bearish_cap_keeps_linear_band_and_diagnostics_consistent(self):
        settings = self._progressive_bearish_settings(
            linear_allocated_target_total_pct=10.0,
            linear_min_score_threshold=0.0,
            linear_score_allocation_power=1.0,
            linear_max_single_stock_pct=100.0,
            linear_rating_bonus_enabled=False,
            hold_rating_penalty_enabled=False,
            core_confidence_penalty=0.0,
            upside_penalty=0.0,
            potential_confidence_penalty=0.0,
            action_min_cash_unallocated_target=0.0,
            action_min_executable_trade_amount=0.0,
        )
        candidate = {
            "symbol": "PROGRESS",
            "rating": "Strong Buy",
            "expected_cagr": 20.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 6.0,
            "potential_confidence_diff": 1.5,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "current_position_weight": 0.0,
            "current_position_market_value": 0.0,
            "current_price": 100.0,
            "expected_price": 150.0,
        }
        result = web_server.compute_linear_action_plan([candidate], 100000.0, 100000.0, settings)
        row = result["rows"][0]
        self.assertAlmostEqual(row["uncapped_target_mid"], 10.0)
        self.assertAlmostEqual(row["adjusted_target_mid"], 7.5)
        self.assertAlmostEqual(row["adjusted_target_low"], 7.5 * 0.85)
        self.assertAlmostEqual(row["adjusted_target_high"], 7.5 * 1.30)
        self.assertAlmostEqual(row["uncapped_target_low"], 10.0 * 0.85)
        self.assertAlmostEqual(row["uncapped_target_high"], 10.0 * 1.30)
        self.assertEqual(row["bearish_confidence"], 6.0)
        self.assertEqual(row["bearish_confidence_min_threshold"], 4.0)
        self.assertEqual(row["bearish_confidence_max_threshold"], 8.0)
        self.assertEqual(row["bearish_cap_progress"], 0.5)
        self.assertEqual(row["bearish_cap_full_limit"], 5.0)
        self.assertTrue(row["bearish_cap_applied"])
        self.assertIn("Progressive high bearish confidence cap (50%)", row["cap_reason"])
        self.assertAlmostEqual(result["summary"]["linear_allocated_target_total"], 7.5)
        self.assertEqual(row["suggested_share_count"], 75)
        self.assertAlmostEqual(row["executable_action_amount"], 7500.0)

        full_cap_candidate = dict(candidate, core_bearish_confidence=8.0)
        full_cap_row = web_server.compute_linear_action_plan(
            [full_cap_candidate], 100000.0, 100000.0, settings
        )["rows"][0]
        self.assertAlmostEqual(full_cap_row["adjusted_target_mid"], 5.0)
        self.assertAlmostEqual(full_cap_row["adjusted_target_low"], 5.0 * 0.85)
        self.assertAlmostEqual(full_cap_row["adjusted_target_high"], 5.0 * 1.30)

        no_cap_candidate = dict(candidate, core_bearish_confidence=4.0)
        no_cap_row = web_server.compute_linear_action_plan(
            [no_cap_candidate], 100000.0, 100000.0, settings
        )["rows"][0]
        self.assertAlmostEqual(no_cap_row["adjusted_target_mid"], 10.0)
        self.assertAlmostEqual(no_cap_row["adjusted_target_low"], no_cap_row["uncapped_target_low"])
        self.assertAlmostEqual(no_cap_row["adjusted_target_high"], no_cap_row["uncapped_target_high"])
        self.assertFalse(no_cap_row["bearish_cap_applied"])

        below_cap_settings = dict(settings, linear_allocated_target_total_pct=4.0)
        below_cap_row = web_server.compute_linear_action_plan(
            [full_cap_candidate], 100000.0, 100000.0, below_cap_settings
        )["rows"][0]
        self.assertAlmostEqual(below_cap_row["adjusted_target_mid"], 4.0)
        self.assertFalse(below_cap_row["bearish_cap_applied"])

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
                            "current_price": 10.0,
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
                    positions = [{"symbol": "SELL", "position": 50, "marketValue": 1000.0}]
                    with mock.patch.object(web_server, "list_analysis_symbols", return_value=analysis), \
                         mock.patch.object(web_server, "load_positions_cache", return_value=positions):
                        payload = web_server.build_action_plan(conn)
                    rows = {row["symbol"]: row for row in payload["action_plan"]}
                    self.assertEqual(rows["BUY"]["action"], "Strong Add")
                    self.assertEqual(rows["BUY"]["current_position_weight"], 0.0)
                    self.assertGreater(rows["BUY"]["target_weight_mid"], 0)
                    self.assertLess(rows["BUY"]["target_weight_low"], rows["BUY"]["target_weight_mid"])
                    self.assertGreater(rows["BUY"]["target_weight_high"], rows["BUY"]["target_weight_mid"])
                    self.assertAlmostEqual(rows["BUY"]["target_weight_low"], rows["BUY"]["target_weight_mid"] * 0.8)
                    self.assertAlmostEqual(rows["BUY"]["target_weight_high"], rows["BUY"]["target_weight_mid"] * 1.2)
                    self.assertEqual(rows["BUY"]["action_amount_direction"], "add")
                    self.assertIn("target_gap_amount", rows["BUY"])
                    self.assertIn("executable_action_amount", rows["BUY"])
                    self.assertIn("funding_status", rows["BUY"])
                    self.assertLessEqual(rows["BUY"]["executable_action_amount"], rows["BUY"]["target_gap_amount"])
                    self.assertIn("target_weight_breakdown", rows["BUY"])
                    self.assertIn("weighted_eligible_count_in_bucket", rows["BUY"]["target_weight_breakdown"])
                    self.assertIn("company_allocation_score", rows["BUY"])
                    self.assertIn("weighted_count", rows["BUY"])
                    self.assertIn("bucket_sizing_score", rows["BUY"])
                    self.assertIn("bucket_sizing_risk_modifier", rows["BUY"])
                    self.assertNotEqual(rows["BUY"]["weighted_count"], rows["BUY"]["company_allocation_score"])
                    self.assertNotEqual(rows["BUY"]["bucket_sizing_score"], rows["BUY"]["company_allocation_score"])
                    self.assertAlmostEqual(rows["BUY"]["allocation_upside_weight_used"], 0.6)
                    self.assertAlmostEqual(rows["BUY"]["allocation_core_weight_used"], 0.3)
                    self.assertAlmostEqual(rows["BUY"]["allocation_potential_weight_used"], 0.1)
                    self.assertAlmostEqual(rows["BUY"]["allocation_risk_penalty_strength"], 0.6)
                    self.assertAlmostEqual(rows["BUY"]["allocation_risk_modifier"], 1.0)
                    expected_allocation_score = (
                        rows["BUY"]["upside_score"] * 0.6
                        + rows["BUY"]["core_conviction_score"] * 0.3
                        + rows["BUY"]["potential_conviction_score"] * 0.1
                    ) * rows["BUY"]["allocation_risk_modifier"]
                    self.assertAlmostEqual(rows["BUY"]["company_allocation_score"], expected_allocation_score)
                    self.assertAlmostEqual(
                        rows["BUY"]["target_weight_breakdown"]["weighted_eligible_count_in_bucket"],
                        buy_weighted_count := rows["BUY"]["weighted_count"],
                    )
                    self.assertGreater(buy_weighted_count, 0)
                    self.assertEqual(rows["BUY"]["potential_bonus_weight"], 0.0)
                    self.assertGreater(rows["BUY"]["potential_score_component"], 0)
                    self.assertIn("allocation_risk_modifier", rows["BUY"]["score_breakdown"])
                    self.assertIn("allocation_upside_weight_used", rows["BUY"]["score_breakdown"])
                    self.assertIn("bucket_sizing_score", rows["BUY"]["score_breakdown"])
                    self.assertIn("allocation_risk_modifier", rows["BUY"]["target_weight_breakdown"])
                    self.assertIn("bucket_sizing_score", rows["BUY"]["target_weight_breakdown"])
                    buy_target_breakdown = rows["BUY"]["target_weight_breakdown"]
                    self.assertEqual(
                        buy_target_breakdown["bucket_weight_per_effective_stock"],
                        web_server.ACTION_PLAN_DEFAULT_SETTINGS["action_buy_weight_per_effective_stock"],
                    )
                    self.assertEqual(
                        buy_target_breakdown["max_effective_count"],
                        web_server.ACTION_PLAN_DEFAULT_SETTINGS["action_buy_max_effective_count"],
                    )
                    self.assertEqual(
                        buy_target_breakdown["max_bucket_target"],
                        web_server.ACTION_PLAN_DEFAULT_SETTINGS["action_buy_max_bucket_target"],
                    )
                    self.assertAlmostEqual(
                        buy_target_breakdown["effective_weighted_count_used"],
                        min(
                            buy_target_breakdown["weighted_eligible_count_in_bucket"],
                            buy_target_breakdown["max_effective_count"],
                        ),
                    )
                    self.assertIn("trigger_breakdown", rows["BUY"])
                    buy_triggers = rows["BUY"]["trigger_breakdown"]
                    self.assertEqual(rows["BUY"].get("position_status"), "BELOW_TARGET")
                    self.assertEqual(buy_triggers["relevant_trigger_type"], "strong_add")
                    self.assertIn("allocation-based Strong Add trigger", rows["BUY"]["reason"])
                    self.assertEqual(buy_triggers["strong_add_trigger_price"], buy_triggers["add_trigger_price"])
                    self.assertIsNotNone(buy_triggers["base_trigger_price"])
                    self.assertEqual(buy_triggers["trigger_anchor"], "Target Low")
                    self.assertIn("Price is", buy_triggers["distance_to_relevant_trigger_label"])
                    self.assertIn("decision_path", rows["BUY"])
                    self.assertEqual(rows["SELL"]["action"], "Sell")
                    self.assertEqual(rows["SELL"]["current_position_weight"], 100.0)
                    self.assertEqual(rows["SELL"]["action_amount_direction"], "sell")
                    self.assertEqual(rows["SELL"]["executable_action_amount"], 1000.0)
                    self.assertEqual(rows["SELL"]["action_amount"], 1000.0)
                    self.assertEqual(rows["SELL"]["funding_status"], "Generates proceeds")
                    self.assertIn("Sell about", rows["SELL"]["action_amount_label"])
                    self.assertIn("linear_action_plan", payload)
                    linear_rows = {row["symbol"]: row for row in payload["linear_action_plan"]}
                    self.assertIn("BUY", linear_rows)
                    self.assertIn("linear_allocation_score", linear_rows["BUY"])
                    self.assertIn("linear_target_weight_mid", linear_rows["BUY"])
                    self.assertEqual(linear_rows["BUY"].get("mode"), "linear")
                    linear_summary = payload["summary"].get("linear_summary")
                    self.assertIsInstance(linear_summary, dict)
                    self.assertIn("linear_allocated_target_total", linear_summary)
                    self.assertLessEqual(
                        sum(row["executable_action_amount"] for row in payload["linear_action_plan"] if row.get("action_amount_direction") == "add"),
                        linear_summary["available_buy_budget"] + 1e-6,
                    )
                    self.assertEqual(payload["summary"]["total_portfolio_value"], 1000.0)
                    buy_bucket = next(item for item in payload["summary"]["bucket_summary"] if item["bucket"] == "Buy")
                    self.assertIn("weighted_eligible_count", buy_bucket)
                    self.assertIn("weighted_count_used", buy_bucket)
                    self.assertIn("max_effective_count", buy_bucket)
                    self.assertIn("bucket_weight_per_effective_stock", buy_bucket)
                    self.assertIn("uncapped_bucket_target", buy_bucket)
                    self.assertIn("bucket_max_target", buy_bucket)
                    self.assertGreater(buy_bucket["weighted_eligible_count"], 0)
                    self.assertAlmostEqual(
                        buy_bucket["weighted_count_used"],
                        min(buy_bucket["weighted_eligible_count"], buy_bucket["max_effective_count"]),
                    )
                    self.assertAlmostEqual(
                        buy_bucket["uncapped_bucket_target"],
                        buy_bucket["weighted_count_used"] * buy_bucket["bucket_weight_per_effective_stock"],
                    )
                    self.assertIn("raw_target", buy_bucket)
                    self.assertIn("effective_target", buy_bucket)
                    self.assertIn("allocated_before_caps", buy_bucket)
                    self.assertIn("allocated_after_caps", buy_bucket)
                    self.assertIn("post_cap_unallocated", buy_bucket)
                    self.assertIn("status", buy_bucket)
                    self.assertIn("available_buy_budget", payload["summary"])
                    self.assertIn("total_add_demand", payload["summary"])
                    self.assertIn("funded_add_amount", payload["summary"])
                    self.assertIn("unfunded_add_demand", payload["summary"])
                    self.assertIn("executable_sell_trim_proceeds", payload["summary"])
                    self.assertIn("minimum_cash_reserve_amount", payload["summary"])
                    funded_add_total = sum(row["executable_action_amount"] for row in rows.values() if row["action_amount_direction"] == "add")
                    self.assertLessEqual(funded_add_total, payload["summary"]["available_buy_budget"] + 1e-6)
                    self.assertIn("raw_equity_target", payload["summary"])
                    self.assertIn("effective_equity_target", payload["summary"])
                    self.assertIn("cash_unallocated_target", payload["summary"])
                    self.assertIn("final_allocated_stock_target", payload["summary"])
                    self.assertIn("total_effective_bucket_target", payload["summary"])
                    self.assertAlmostEqual(payload["summary"]["total_effective_bucket_target"], 100.0)
                    self.assertTrue(payload["summary"]["dynamic_bucket_sizing_enabled"])
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


    def test_cash_constrained_execution_caps_adds_to_available_budget(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        rows = [
            {
                "symbol": "AAA",
                "rating": "Strong Buy",
                "action": "Strong Add",
                "action_amount": 1500.0,
                "action_amount_direction": "add",
                "current_price": 100.0,
                "allocation_score": 0.9,
                "bucket_sizing_score": 0.8,
                "trigger_quality_score": 0.9,
                "upside": 90.0,
            },
            {
                "symbol": "BBB",
                "rating": "Buy",
                "action": "Add",
                "action_amount": 800.0,
                "action_amount_direction": "add",
                "current_price": 100.0,
                "allocation_score": 0.6,
                "bucket_sizing_score": 0.6,
                "trigger_quality_score": 0.6,
                "upside": 50.0,
            },
            {
                "symbol": "CCC",
                "rating": "Hold",
                "action": "Hold / Overweight",
                "action_amount": 500.0,
                "action_amount_direction": "none",
                "allocation_score": 0.5,
                "bucket_sizing_score": 0.5,
                "trigger_quality_score": 0.5,
                "upside": 30.0,
            },
        ]
        summary = web_server._apply_cash_constrained_execution_layer(rows, 10000.0, 2000.0, settings)
        executable_add_total = sum(row["executable_action_amount"] for row in rows if row["action_amount_direction"] == "add")
        self.assertEqual(summary["available_buy_budget"], 1000.0)
        self.assertEqual(summary["total_add_demand"], 2300.0)
        self.assertLessEqual(executable_add_total, summary["available_buy_budget"] + 1e-6)
        self.assertEqual(rows[0]["executable_action_amount"], 1000.0)
        self.assertEqual(rows[0]["funding_status"], "Partially funded")
        self.assertEqual(rows[1]["executable_action_amount"], 0.0)
        self.assertEqual(rows[1]["funding_status"], "Unfunded / Watch")
        self.assertEqual(rows[2]["funding_status"], "No funding needed")

    def test_action_plan_settings_reject_bucket_total_above_100_in_fixed_mode(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_use_dynamic_bucket_sizing"] = False
        settings["action_bucket_buy_target"] = 90.0
        with self.assertRaisesRegex(ValueError, "bucket targets"):
            web_server.validate_action_plan_settings(settings)

    def test_dynamic_action_plan_settings_allow_legacy_bucket_targets_above_100(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_bucket_buy_target"] = 90.0
        effective = web_server.validate_action_plan_settings(settings)
        self.assertTrue(effective["action_use_dynamic_bucket_sizing"])


    def test_dynamic_action_plan_settings_reject_zero_allocation_weights(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_allocation_upside_weight"] = 0.0
        settings["action_allocation_core_weight"] = 0.0
        settings["action_allocation_potential_weight"] = 0.0
        with self.assertRaisesRegex(ValueError, "Allocation weights"):
            web_server.validate_action_plan_settings(settings)

    def test_dynamic_action_plan_settings_reject_allocation_risk_strength_above_one(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_allocation_risk_penalty_strength"] = 1.5
        with self.assertRaisesRegex(ValueError, "action_allocation_risk_penalty_strength"):
            web_server.validate_action_plan_settings(settings)

    def test_dynamic_action_plan_settings_reject_zero_bucket_sizing_weights(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_bucket_sizing_upside_weight"] = 0.0
        settings["action_bucket_sizing_core_weight"] = 0.0
        settings["action_bucket_sizing_potential_weight"] = 0.0
        with self.assertRaisesRegex(ValueError, "Bucket sizing weights"):
            web_server.validate_action_plan_settings(settings)


    def test_linear_action_plan_applies_stock_level_penalties(self):
        candidate = {
            "symbol": "LOW",
            "rating": "Hold",
            "expected_cagr": 10.0,
            "upside": 30.0,
            "core_confidence_diff": 0.2,
            "potential_confidence_diff": -0.2,
            "core_bullish_confidence": 5.0,
            "core_bearish_confidence": 4.0,
            "potential_bullish_confidence": 3.0,
            "potential_bearish_confidence": 4.0,
            "current_position_weight": 0.0,
            "current_position_market_value": 0.0,
            "current_price": 100.0,
            "expected_price": 130.0,
        }
        base_settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        base_settings["linear_min_score_threshold"] = 0.0
        for key in ("core_confidence_penalty", "upside_penalty", "potential_confidence_penalty", "hold_rating_penalty"):
            base_settings[key] = 0.0
        base_settings["hold_rating_penalty_enabled"] = False
        base_score = web_server.compute_linear_action_plan([candidate], 100000.0, 0.0, base_settings)["rows"][0]["linear_allocation_score"]

        penalized_settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        penalized_settings["linear_min_score_threshold"] = 0.0
        row = web_server.compute_linear_action_plan([candidate], 100000.0, 0.0, penalized_settings)["rows"][0]

        expected_factor = 0.85 * 0.80 * 0.95 * 0.90
        self.assertAlmostEqual(row["linear_penalty_factor"], expected_factor)
        self.assertAlmostEqual(row["linear_allocation_score"], base_score * expected_factor)
        self.assertEqual(
            [penalty["key"] for penalty in row["linear_penalties_applied"]],
            ["core_confidence_penalty", "upside_penalty", "potential_confidence_penalty", "hold_rating_penalty"],
        )



    def test_linear_score_allocation_power_concentrates_target_weights(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_allocated_target_total_pct": 100.0,
            "linear_min_score_threshold": 0.0,
            "linear_score_allocation_power": 1.0,
            "linear_expected_cagr_weight": 1.0,
            "linear_upside_weight": 0.0,
            "linear_core_confidence_weight": 0.0,
            "linear_potential_confidence_weight": 0.0,
            "linear_confidence_quality_weight": 0.0,
            "linear_min_expected_cagr": 0.0,
            "linear_full_expected_cagr": 100.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
            "linear_zero_target_if_expected_cagr_negative": False,
            "linear_zero_target_if_upside_negative": False,
            "hold_rating_penalty_enabled": False,
            "action_min_cash_unallocated_target": 0.0,
            "linear_max_reserve_pct": 0.0,
        })
        for key in ("core_confidence_penalty", "upside_penalty", "potential_confidence_penalty", "hold_rating_penalty"):
            settings[key] = 0.0
        candidates = [
            {"symbol": "HIGH", "rating": "Hold", "expected_cagr": 70.0, "upside": 10.0, "core_confidence_diff": 0.0, "potential_confidence_diff": 0.0, "current_position_weight": 0.0, "current_position_market_value": 0.0},
            {"symbol": "LOW", "rating": "Hold", "expected_cagr": 35.0, "upside": 10.0, "core_confidence_diff": 0.0, "potential_confidence_diff": 0.0, "current_position_weight": 0.0, "current_position_market_value": 0.0},
        ]
        proportional = {row["symbol"]: row for row in web_server.compute_linear_action_plan(candidates, 100000.0, 0.0, settings)["rows"]}
        proportional_ratio = proportional["HIGH"]["linear_target_weight_mid"] / proportional["LOW"]["linear_target_weight_mid"]
        self.assertAlmostEqual(proportional_ratio, 2.0)
        self.assertAlmostEqual(sum(row["linear_target_weight_mid"] for row in proportional.values()), 100.0)
        self.assertAlmostEqual(proportional["HIGH"]["linear_allocation_score"], 0.70)

        settings["linear_score_allocation_power"] = 2.0
        powered = {row["symbol"]: row for row in web_server.compute_linear_action_plan(candidates, 100000.0, 0.0, settings)["rows"]}
        powered_ratio = powered["HIGH"]["linear_target_weight_mid"] / powered["LOW"]["linear_target_weight_mid"]
        self.assertAlmostEqual(powered_ratio, 4.0)
        self.assertGreater(powered["HIGH"]["linear_target_weight_mid"], proportional["HIGH"]["linear_target_weight_mid"])
        self.assertAlmostEqual(powered["HIGH"]["linear_allocation_score"], proportional["HIGH"]["linear_allocation_score"])
        self.assertAlmostEqual(sum(row["linear_target_weight_mid"] for row in powered.values()), 100.0)

    def test_linear_split_band_tolerances_drive_add_and_trim_actions(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_allocated_target_total_pct": 10.0,
            "linear_min_score_threshold": 0.0,
            "linear_score_allocation_power": 1.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_add_band_tolerance_pct": 15.0,
            "linear_trim_band_tolerance_pct": 30.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
        })
        base_candidate = {
            "symbol": "BAND",
            "rating": "Strong Buy",
            "expected_cagr": 20.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 1.0,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "current_price": 100.0,
            "expected_price": 150.0,
        }
        above_old_band = dict(base_candidate, current_position_weight=12.0, current_position_market_value=12000.0)
        row = web_server.compute_linear_action_plan([above_old_band], 100000.0, 0.0, settings)["rows"][0]
        self.assertAlmostEqual(row["linear_target_weight_mid"], 10.0)
        self.assertAlmostEqual(row["linear_target_weight_low"], 8.5)
        self.assertAlmostEqual(row["linear_target_weight_high"], 13.0)
        self.assertEqual(row["action"], "Hold")

        below_add_band = dict(base_candidate, current_position_weight=8.0, current_position_market_value=8000.0)
        add_row = web_server.compute_linear_action_plan([below_add_band], 100000.0, 0.0, settings)["rows"][0]
        self.assertEqual(add_row["desired_action"], "Add")
        self.assertEqual(add_row["action"], "Watch")
        self.assertEqual(add_row["funding_status"], "Unfunded / Watch")

        above_trim_band = dict(base_candidate, current_position_weight=13.5, current_position_market_value=13500.0, current_price=150.0)
        trim_row = web_server.compute_linear_action_plan([above_trim_band], 100000.0, 0.0, settings)["rows"][0]
        self.assertEqual(trim_row["action"], "Trim")
        self.assertAlmostEqual(trim_row["target_gap_amount"], 500.0)

    def test_linear_action_plan_applies_small_multiplicative_rating_bonus(self):
        candidate = {
            "symbol": "BONUS",
            "rating": "Strong Buy",
            "expected_cagr": 7.5,
            "upside": 40.0,
            "core_confidence_diff": 0.5,
            "potential_confidence_diff": 0.25,
            "core_bullish_confidence": 5.0,
            "core_bearish_confidence": 3.0,
            "potential_bullish_confidence": 4.0,
            "potential_bearish_confidence": 3.0,
            "current_position_weight": 0.0,
            "current_position_market_value": 0.0,
            "current_price": 100.0,
            "expected_price": 140.0,
        }
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_min_score_threshold"] = 0.0
        settings["linear_strong_buy_rating_bonus"] = 0.05
        settings["linear_buy_rating_bonus"] = 0.02
        for key in ("core_confidence_penalty", "upside_penalty", "potential_confidence_penalty", "hold_rating_penalty"):
            settings[key] = 0.0
        settings["hold_rating_penalty_enabled"] = False

        disabled_settings = dict(settings)
        disabled_settings["linear_rating_bonus_enabled"] = False
        base_score = web_server.compute_linear_action_plan([candidate], 100000.0, 0.0, disabled_settings)["rows"][0]["linear_allocation_score"]

        strong_buy = web_server.compute_linear_action_plan([candidate], 100000.0, 0.0, settings)["rows"][0]
        self.assertAlmostEqual(strong_buy["linear_rating_bonus_factor"], 1.05)
        self.assertEqual(strong_buy["linear_rating_bonus_reason"], "Strong Buy rating bonus")
        self.assertAlmostEqual(strong_buy["linear_allocation_score"], base_score * 1.05)

        buy_candidate = dict(candidate, rating="Buy")
        buy_base = web_server.compute_linear_action_plan([buy_candidate], 100000.0, 0.0, disabled_settings)["rows"][0]["linear_allocation_score"]
        buy = web_server.compute_linear_action_plan([buy_candidate], 100000.0, 0.0, settings)["rows"][0]
        self.assertAlmostEqual(buy["linear_rating_bonus_factor"], 1.02)
        self.assertAlmostEqual(buy["linear_allocation_score"], buy_base * 1.02)

        hold_candidate = dict(candidate, rating="Hold")
        hold_base = web_server.compute_linear_action_plan([hold_candidate], 100000.0, 0.0, disabled_settings)["rows"][0]["linear_allocation_score"]
        hold = web_server.compute_linear_action_plan([hold_candidate], 100000.0, 0.0, settings)["rows"][0]
        self.assertAlmostEqual(hold["linear_rating_bonus_factor"], 1.0)
        self.assertAlmostEqual(hold["linear_allocation_score"], hold_base)

        disabled_row = web_server.compute_linear_action_plan([candidate], 100000.0, 0.0, disabled_settings)["rows"][0]
        self.assertAlmostEqual(disabled_row["linear_rating_bonus_factor"], 1.0)
        self.assertAlmostEqual(disabled_row["linear_allocation_score"], base_score)


    def test_linear_target_bands_drive_actions_without_trigger_gating(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_allocated_target_total_pct": 10.0,
            "linear_min_score_threshold": 0.0,
            "linear_score_allocation_power": 1.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_add_band_tolerance_pct": 15.0,
            "linear_trim_band_tolerance_pct": 30.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
            "action_min_cash_unallocated_target": 0.0,
            "action_min_executable_trade_amount": 0.0,
        })
        base = {
            "rating": "Strong Buy",
            "expected_cagr": 20.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 1.0,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "expected_price": 150.0,
        }
        candidates = [
            dict(base, symbol="ADD_OK", current_position_weight=0.0, current_position_market_value=0.0, current_price=100.0),
            dict(base, symbol="ADD_WAIT", current_position_weight=0.0, current_position_market_value=0.0, current_price=145.0, momentum_score=1.5, extension_risk=2.0),
            dict(base, symbol="TRIM_OK", current_position_weight=13.5, current_position_market_value=13500.0, current_price=140.0),
            dict(base, symbol="TRIM_WAIT", current_position_weight=13.5, current_position_market_value=13500.0, current_price=100.0, momentum_score=5.0, extension_risk=0.0),
            dict(base, symbol="SELL", rating="Sell", current_position_weight=13.5, current_position_market_value=13500.0, current_price=100.0),
        ]
        rows = {row["symbol"]: row for row in web_server.compute_linear_action_plan(candidates, 100000.0, 100000.0, settings)["rows"]}

        self.assertEqual(rows["ADD_OK"]["action"], "Add")
        self.assertGreater(rows["ADD_OK"]["executable_action_amount"], 0.0)
        self.assertEqual(rows["ADD_WAIT"]["action"], "Add")
        self.assertGreater(rows["ADD_WAIT"]["target_gap_amount"], 0.0)
        self.assertGreater(rows["ADD_WAIT"]["executable_action_amount"], 0.0)
        self.assertIsNone(rows["ADD_WAIT"]["trigger_price"])
        self.assertIsNone(rows["ADD_WAIT"]["distance_to_trigger_percent"])

        self.assertEqual(rows["TRIM_OK"]["action"], "Trim")
        self.assertEqual(rows["TRIM_OK"]["funding_status"], "Generates proceeds")
        self.assertGreater(rows["TRIM_OK"]["executable_action_amount"], 0.0)
        self.assertEqual(rows["TRIM_WAIT"]["action"], "Trim")
        self.assertGreater(rows["TRIM_WAIT"]["target_gap_amount"], 0.0)
        self.assertEqual(rows["TRIM_WAIT"]["funding_status"], "Generates proceeds")
        self.assertGreater(rows["TRIM_WAIT"]["executable_action_amount"], 0.0)
        self.assertIsNone(rows["TRIM_WAIT"]["trigger_price"])
        self.assertIsNone(rows["TRIM_WAIT"]["distance_to_trigger_percent"])

        self.assertEqual(rows["SELL"]["action"], "Sell")
        self.assertEqual(rows["SELL"]["funding_status"], "Generates proceeds")
        self.assertGreater(rows["SELL"]["executable_action_amount"], 0.0)
        self.assertAlmostEqual(
            rows["ADD_OK"]["total_add_demand"],
            rows["ADD_OK"]["desired_whole_share_amount"] + rows["ADD_WAIT"]["desired_whole_share_amount"],
        )
        self.assertAlmostEqual(
            rows["TRIM_WAIT"]["executable_sell_trim_proceeds"],
            rows["TRIM_OK"]["action_amount"] + rows["TRIM_WAIT"]["action_amount"] + rows["SELL"]["action_amount"],
        )

    def test_linear_action_plan_populates_action_columns_and_summary(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_min_score_threshold"] = 0.0
        settings["action_min_cash_unallocated_target"] = 0.0
        settings["linear_max_reserve_pct"] = 0.0
        settings["action_min_executable_trade_amount"] = 0.0
        candidates = [
            {
                "symbol": "ADD",
                "rating": "Buy",
                "expected_cagr": 20.0,
                "upside": 50.0,
                "core_confidence_diff": 2.0,
                "potential_confidence_diff": 1.5,
                "core_bullish_confidence": 8.0,
                "core_bearish_confidence": 1.0,
                "potential_bullish_confidence": 7.0,
                "potential_bearish_confidence": 1.0,
                "current_position_weight": 0.0,
                "current_position_market_value": 0.0,
                "current_price": 100.0,
                "expected_price": 150.0,
            },
            {
                "symbol": "TRIM",
                "rating": "Hold",
                "expected_cagr": 8.0,
                "upside": 20.0,
                "core_confidence_diff": 0.5,
                "potential_confidence_diff": 0.5,
                "core_bullish_confidence": 5.0,
                "core_bearish_confidence": 2.0,
                "potential_bullish_confidence": 5.0,
                "potential_bearish_confidence": 2.0,
                "current_position_weight": 50.0,
                "current_position_market_value": 50000.0,
                "current_price": 120.0,
                "expected_price": 120.0,
            },
        ]
        payload = web_server.compute_linear_action_plan(candidates, 100000.0, 1000.0, settings)
        rows = {row["symbol"]: row for row in payload["rows"]}
        add = rows["ADD"]
        self.assertEqual(add["action"], "Add")
        self.assertGreater(add["target_gap_amount"], 0.0)
        self.assertGreater(add["total_add_demand"], 0.0)
        self.assertEqual(payload["summary"]["total_add_demand"], add["total_add_demand"])
        self.assertIn(add["funding_status"], {"Fully funded", "Partially funded"})
        self.assertGreater(add["executable_action_amount"], 0.0)
        self.assertLessEqual(add["executable_action_amount"], add["target_gap_amount"] + 1e-6)
        self.assertIn("Add about", add["action_amount_label"])
        self.assertIsNone(add["trigger_price"])
        self.assertIsNone(add["relevant_trigger_price"])
        self.assertIsNone(add["distance_to_trigger_percent"])
        self.assertIsNone(add["trigger_breakdown"])
        self.assertNotIn("trigger", " ".join(step["text"].lower() for step in add["decision_path"]))
        trim = rows["TRIM"]
        self.assertEqual(trim["action"], "Trim")
        self.assertGreater(trim["target_gap_amount"], 0.0)
        self.assertEqual(trim["funding_status"], "Generates proceeds")
        self.assertIn("Trim about", trim["action_amount_label"])
        self.assertIsNone(trim["trigger_price"])

    def test_linear_zero_target_owned_position_becomes_sell_without_trigger_fields(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_min_score_threshold": 0.0,
            "linear_max_reserve_pct": 0.0,
            "action_min_cash_unallocated_target": 0.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
        })
        candidate = {
            "symbol": "ZERO",
            "rating": "Buy",
            "expected_cagr": -1.0,
            "upside": -1.0,
            "core_confidence_diff": 1.0,
            "potential_confidence_diff": 1.0,
            "core_bullish_confidence": 1.0,
            "core_bearish_confidence": 0.0,
            "potential_bullish_confidence": 1.0,
            "potential_bearish_confidence": 0.0,
            "current_position_weight": 3.0,
            "current_position_market_value": 3_000.0,
            "owned_share_quantity": 30,
            "current_price": 100.0,
            "expected_price": 90.0,
        }
        row = web_server.compute_linear_action_plan([candidate], 100_000.0, 0.0, settings)["rows"][0]
        self.assertEqual(row["linear_target_weight_mid"], 0.0)
        self.assertEqual(row["action"], "Sell")
        self.assertEqual(row["funding_status"], "Generates proceeds")
        self.assertIsNone(row["trigger_price"])
        self.assertIn("Final target is zero", " ".join(step["text"] for step in row["decision_path"]))

    def test_linear_high_extension_guardrail_defers_adds_without_funding_demand(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_allocated_target_total_pct": 10.0,
            "linear_min_score_threshold": 0.0,
            "linear_score_allocation_power": 1.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
            "linear_max_reserve_pct": 0.0,
            "action_min_cash_unallocated_target": 0.0,
            "action_min_executable_trade_amount": 0.0,
            "linear_high_extension_guardrail_enabled": True,
            "linear_high_extension_risk_threshold": 4.0,
        })
        base = {
            "rating": "Buy",
            "expected_cagr": 20.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 1.0,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "current_position_weight": 0.0,
            "current_position_market_value": 0.0,
            "current_price": 100.0,
            "expected_price": 150.0,
        }

        def linear_row(symbol, extension_risk, **overrides):
            candidate = dict(base, symbol=symbol, extension_risk=extension_risk, **overrides)
            return web_server.compute_linear_action_plan([candidate], 100_000.0, 100_000.0, settings)["rows"][0]

        healthy = linear_row("HEALTHY", 3.9)
        threshold = linear_row("THRESHOLD", 4.0)
        extended = linear_row("EXTENDED", 4.3)
        missing = linear_row("MISSING", None)
        overweight = linear_row("OVERWEIGHT", 4.5, current_position_weight=20.0, current_position_market_value=20_000.0)
        inside_band = linear_row("INSIDE", 4.5, current_position_weight=10.0, current_position_market_value=10_000.0)

        self.assertEqual(healthy["action"], "Add")
        self.assertEqual(missing["action"], "Add")
        self.assertEqual(missing["extension_guardrail_diagnostic"], "Extension Risk unavailable; guardrail not applied.")
        for row in (threshold, extended):
            with self.subTest(symbol=row["symbol"]):
                self.assertEqual(row["desired_action"], "Add")
                self.assertEqual(row["action"], "Watch / Extended")
                self.assertEqual(row["executable_action"], "Watch / Extended")
                self.assertTrue(row["extension_guardrail_applied"])
                self.assertEqual(row["extension_guardrail_threshold"], 4.0)
                self.assertEqual(row["funding_status"], "Extension guardrail")
                self.assertEqual(row["suggested_share_count"], 0)
                self.assertEqual(row["action_amount"], 0.0)
                self.assertEqual(row["action_amount_label"], "—")
                self.assertEqual(row["action_amount_direction"], "none")
                self.assertEqual(row["total_add_demand"], 0.0)
                self.assertEqual(row["funded_add_amount"], 0.0)
                self.assertEqual(row["unfunded_add_demand"], 0.0)
                self.assertEqual(row["available_buy_budget"], 100_000.0)
                self.assertIn("Extension Risk is", " ".join(step["text"] for step in row["decision_path"]))
        self.assertEqual(overweight["action"], "Trim")
        self.assertEqual(inside_band["action"], "Hold")

    def test_linear_high_extension_guardrail_can_be_disabled(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_min_score_threshold": 0.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
            "linear_max_reserve_pct": 0.0,
            "action_min_cash_unallocated_target": 0.0,
            "action_min_executable_trade_amount": 0.0,
            "linear_high_extension_guardrail_enabled": False,
            "linear_high_extension_risk_threshold": 4.0,
        })
        candidate = {
            "symbol": "DISABLED",
            "rating": "Buy",
            "expected_cagr": 20.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 1.0,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "current_position_weight": 0.0,
            "current_position_market_value": 0.0,
            "current_price": 100.0,
            "expected_price": 150.0,
            "extension_risk": 5.0,
        }
        row = web_server.compute_linear_action_plan([candidate], 100_000.0, 100_000.0, settings)["rows"][0]
        self.assertEqual(row["action"], "Add")
        self.assertFalse(row["extension_guardrail_applied"])

    def test_linear_rows_include_release_date_and_momentum_context(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({"linear_min_score_threshold": 0.0, "linear_max_single_stock_pct": 100.0, "linear_enable_risk_caps": False, "linear_rating_bonus_enabled": False, "linear_max_reserve_pct": 0.0, "action_min_cash_unallocated_target": 0.0})
        base = {"rating": "Buy", "expected_cagr": 20.0, "upside": 50.0, "core_confidence_diff": 2.0, "potential_confidence_diff": 1.5, "core_bullish_confidence": 8.0, "core_bearish_confidence": 1.0, "potential_bullish_confidence": 7.0, "potential_bearish_confidence": 1.0, "current_position_weight": 0.0, "current_position_market_value": 0.0, "current_price": 100.0, "expected_price": 150.0}
        populated = web_server.compute_linear_action_plan([dict(base, symbol="DATED", release_date="2026-08-14", release_timing="Before Open", momentum_score=3.8, momentum_label="Positive", momentum_updated_at="2026-08-08T12:00:00+00:00")], 100_000.0, 100_000.0, settings)["rows"][0]
        missing = web_server.compute_linear_action_plan([dict(base, symbol="MISSING")], 100_000.0, 100_000.0, settings)["rows"][0]
        self.assertEqual(populated["release_date"], "2026-08-14")
        self.assertEqual(populated["release_timing"], "Before Open")
        self.assertEqual(populated["momentum_score"], 3.8)
        self.assertEqual(populated["momentum_label"], "Positive")
        self.assertIsNone(missing["release_date"])
        self.assertIsNone(missing["momentum_score"])

    def test_linear_release_date_warning_uses_inclusive_calendar_day_window(self):
        today = web_server.date(2026, 8, 9)
        self.assertEqual(web_server.ACTION_PLAN_DEFAULT_SETTINGS["linear_release_date_warning_days"], 30)
        self.assertTrue(web_server._linear_release_date_warning_details("2026-08-09", 30, today)["release_date_warning"])
        self.assertTrue(web_server._linear_release_date_warning_details("2026-09-08", 30, today)["release_date_warning"])
        self.assertEqual(web_server._linear_release_date_warning_details("2026-09-08", 30, today)["release_date_days_until"], 30)
        self.assertFalse(web_server._linear_release_date_warning_details("2026-09-09", 30, today)["release_date_warning"])
        self.assertFalse(web_server._linear_release_date_warning_details("2026-08-08", 30, today)["release_date_warning"])
        self.assertFalse(web_server._linear_release_date_warning_details(None, 30, today)["release_date_warning"])
        self.assertFalse(web_server._linear_release_date_warning_details("invalid", 30, today)["release_date_warning"])
        self.assertFalse(web_server._linear_release_date_warning_details("2026-08-09", 0, today)["release_date_warning"])

    def test_linear_release_date_warning_setting_validation(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_release_date_warning_days"] = 365
        self.assertEqual(web_server.validate_action_plan_settings(settings)["linear_release_date_warning_days"], 365.0)
        for value in (-1, 366, 1.5):
            invalid_settings = dict(settings)
            invalid_settings["linear_release_date_warning_days"] = value
            with self.assertRaisesRegex(ValueError, "linear_release_date_warning_days"):
                web_server.validate_action_plan_settings(invalid_settings)

    def test_linear_hold_rating_buy_guardrail_blocks_adds_without_consuming_budget(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_allocated_target_total_pct": 10.0,
            "linear_min_score_threshold": 0.0,
            "linear_score_allocation_power": 1.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_add_band_tolerance_pct": 15.0,
            "linear_trim_band_tolerance_pct": 30.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
            "action_min_cash_unallocated_target": 0.0,
            "action_min_executable_trade_amount": 0.0,
        })
        base = {
            "expected_cagr": 20.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 1.0,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "current_position_weight": 0.0,
            "current_position_market_value": 0.0,
            "current_price": 100.0,
            "expected_price": 150.0,
            "momentum_score": 3.0,
            "extension_risk": 4.5,
        }
        candidates = [
            dict(base, symbol="HOLDADD", rating="Hold"),
            dict(base, symbol="BUYADD", rating="Buy", extension_risk=1.0),
        ]
        payload = web_server.compute_linear_action_plan(candidates, 100000.0, 100000.0, settings)
        rows = {row["symbol"]: row for row in payload["rows"]}

        hold_row = rows["HOLDADD"]
        buy_row = rows["BUYADD"]
        self.assertEqual(hold_row["action"], "Watch / Rating Guardrail")
        self.assertEqual(hold_row["desired_action"], "Add")
        self.assertEqual(hold_row["action_amount_label"], "—")
        self.assertEqual(hold_row["funding_status"], "Rating blocks add")
        self.assertTrue(hold_row["rating_guardrail_applied"])
        self.assertFalse(hold_row["extension_guardrail_applied"])
        self.assertEqual(hold_row["rating_guardrail_reason"], "Hold rating blocks buy-side action.")
        self.assertGreater(hold_row["target_gap_amount"], 0.0)
        self.assertEqual(hold_row["executable_action_amount"], 0.0)
        self.assertEqual(buy_row["action"], "Add")
        self.assertGreater(buy_row["executable_action_amount"], 0.0)
        self.assertAlmostEqual(payload["summary"]["total_add_demand"], buy_row["desired_whole_share_amount"])
        self.assertAlmostEqual(payload["summary"]["funded_add_amount"], buy_row["desired_whole_share_amount"])
        self.assertAlmostEqual(payload["summary"]["unfunded_add_demand"], 0.0)
        self.assertAlmostEqual(hold_row["total_add_demand"], buy_row["desired_whole_share_amount"])

    def test_linear_buy_guardrail_allows_eligible_ratings_and_blocks_missing_rating(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_allocated_target_total_pct": 10.0,
            "linear_min_score_threshold": 0.0,
            "linear_score_allocation_power": 1.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
            "action_min_cash_unallocated_target": 0.0,
            "action_min_executable_trade_amount": 0.0,
        })
        base = {
            "expected_cagr": 20.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 1.0,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "current_position_weight": 0.0,
            "current_position_market_value": 0.0,
            "current_price": 100.0,
            "expected_price": 150.0,
            "momentum_score": 3.0,
            "extension_risk": 1.0,
        }
        candidates = [
            dict(base, symbol="STRONG", rating="Strong Buy"),
            dict(base, symbol="BUY", rating="Buy"),
            dict(base, symbol="SPEC", rating="Speculative Buy"),
            dict(base, symbol="MISSING", rating=None),
        ]
        rows = {row["symbol"]: row for row in web_server.compute_linear_action_plan(candidates, 100000.0, 100000.0, settings)["rows"]}

        self.assertEqual(rows["STRONG"]["action"], "Add")
        self.assertEqual(rows["BUY"]["action"], "Add")
        self.assertEqual(rows["SPEC"]["action"], "Add")
        self.assertEqual(rows["MISSING"]["action"], "Watch / Rating Guardrail")
        self.assertEqual(rows["MISSING"]["funding_status"], "Rating blocks add")

    def test_linear_hold_guardrail_does_not_block_trim_or_sell_and_can_be_disabled(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.update({
            "linear_allocated_target_total_pct": 10.0,
            "linear_min_score_threshold": 0.0,
            "linear_score_allocation_power": 1.0,
            "linear_max_single_stock_pct": 100.0,
            "linear_enable_risk_caps": False,
            "linear_rating_bonus_enabled": False,
            "action_min_cash_unallocated_target": 0.0,
            "action_min_executable_trade_amount": 0.0,
        })
        base = {
            "expected_cagr": 20.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 1.0,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "expected_price": 150.0,
            "momentum_score": 3.0,
            "extension_risk": 1.0,
        }
        trim_candidate = dict(base, symbol="HOLDTRIM", rating="Hold", current_position_weight=20.0, current_position_market_value=20000.0, current_price=200.0)
        sell_candidate = dict(base, symbol="SELL", rating="Sell", current_position_weight=20.0, current_position_market_value=20000.0, current_price=100.0)
        rows = {row["symbol"]: row for row in web_server.compute_linear_action_plan([trim_candidate, sell_candidate], 100000.0, 0.0, settings)["rows"]}
        self.assertEqual(rows["HOLDTRIM"]["action"], "Trim")
        self.assertEqual(rows["HOLDTRIM"]["funding_status"], "Generates proceeds")
        self.assertEqual(rows["SELL"]["action"], "Sell")
        self.assertEqual(rows["SELL"]["funding_status"], "Generates proceeds")

        disabled_settings = dict(settings)
        disabled_settings["linear_block_buy_actions_for_hold_rating"] = False
        hold_add = dict(base, symbol="HOLDADD", rating="Hold", current_position_weight=0.0, current_position_market_value=0.0, current_price=100.0)
        disabled_row = web_server.compute_linear_action_plan([hold_add], 100000.0, 100000.0, disabled_settings)["rows"][0]
        self.assertEqual(disabled_row["action"], "Add")
        self.assertGreater(disabled_row["executable_action_amount"], 0.0)

    def test_linear_action_plan_settings_reject_invalid_stock_level_penalties(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["upside_penalty"] = 1.5
        with self.assertRaisesRegex(ValueError, "upside_penalty must be between 0 and 1"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_score_allocation_power"] = 5.1
        with self.assertRaisesRegex(ValueError, "linear_score_allocation_power must be between 0.5 and 5.0"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_add_band_tolerance_pct"] = 101.0
        with self.assertRaisesRegex(ValueError, "linear_add_band_tolerance_pct must be between 0 and 100"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_trim_band_tolerance_pct"] = -0.1
        with self.assertRaisesRegex(ValueError, "linear_trim_band_tolerance_pct must be between 0 and 100"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_strong_buy_rating_bonus"] = 1.5
        with self.assertRaisesRegex(ValueError, "linear_strong_buy_rating_bonus must be between 0 and 1"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_buy_rating_bonus"] = -0.01
        with self.assertRaisesRegex(ValueError, "linear_buy_rating_bonus must be between 0 and 1"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_rating_bonus_enabled"] = "yes"
        with self.assertRaisesRegex(ValueError, "linear_rating_bonus_enabled must be boolean"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_block_buy_actions_for_hold_rating"] = "yes"
        with self.assertRaisesRegex(ValueError, "linear_block_buy_actions_for_hold_rating must be boolean"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_high_extension_guardrail_enabled"] = "yes"
        with self.assertRaisesRegex(ValueError, "linear_high_extension_guardrail_enabled must be boolean"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_high_extension_risk_threshold"] = 5.1
        with self.assertRaisesRegex(ValueError, "linear_high_extension_risk_threshold must be between 0 and 5"):
            web_server.validate_action_plan_settings(settings)



    def test_linear_split_band_tolerances_fall_back_to_legacy_saved_tolerance(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings.pop("linear_add_band_tolerance_pct")
        settings.pop("linear_trim_band_tolerance_pct")
        settings["linear_target_band_tolerance_pct"] = 20.0
        effective = web_server.validate_action_plan_settings(settings)
        self.assertEqual(effective["linear_add_band_tolerance_pct"], 20.0)
        self.assertEqual(effective["linear_trim_band_tolerance_pct"], 30.0)

    def test_linear_action_plan_settings_allow_negative_net_confidence_minimums(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_min_core_net"] = -1.0
        settings["linear_full_core_net"] = 2.0
        settings["linear_min_potential_net"] = -1.0
        settings["linear_full_potential_net"] = 1.5
        effective = web_server.validate_action_plan_settings(settings)
        self.assertEqual(effective["linear_min_core_net"], -1.0)
        self.assertEqual(effective["linear_min_potential_net"], -1.0)

    def test_linear_action_plan_settings_reject_invalid_net_confidence_ranges(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_min_core_net"] = 2.0
        settings["linear_full_core_net"] = 2.0
        with self.assertRaisesRegex(ValueError, "linear_full_core_net must be greater than linear_min_core_net"):
            web_server.validate_action_plan_settings(settings)

        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["linear_min_potential_net"] = 1.5
        settings["linear_full_potential_net"] = 1.5
        with self.assertRaisesRegex(ValueError, "linear_full_potential_net must be greater than linear_min_potential_net"):
            web_server.validate_action_plan_settings(settings)


    def test_action_plan_bucket_sizing_details_show_effective_count_used(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_buy_weight_per_effective_stock"] = 5.0
        settings["action_buy_max_effective_count"] = 12.0
        settings["action_buy_max_bucket_target"] = 45.0

        capped = web_server._action_plan_bucket_sizing_details("Buy", 15.0, 0.0, settings, dynamic_mode=True)
        self.assertEqual(capped["weighted_eligible_count"], 15.0)
        self.assertEqual(capped["max_effective_count"], 12.0)
        self.assertEqual(capped["weighted_count_used"], 12.0)
        self.assertEqual(capped["uncapped_bucket_target"], 60.0)
        self.assertEqual(capped["raw_bucket_target"], 45.0)
        self.assertEqual(capped["bucket_max_target"], 45.0)

        uncapped = web_server._action_plan_bucket_sizing_details("Buy", 6.13, 0.0, settings, dynamic_mode=True)
        self.assertEqual(uncapped["weighted_count_used"], 6.13)
        self.assertAlmostEqual(uncapped["uncapped_bucket_target"], 30.65)
        self.assertAlmostEqual(uncapped["raw_bucket_target"], 30.65)

    def test_action_plan_target_band_wraps_target_mid_with_tolerance(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        low, high = web_server._target_band(7.84, "Strong Buy", settings)
        self.assertAlmostEqual(low, 6.272)
        self.assertAlmostEqual(high, 9.408)
        zero_low, zero_high = web_server._target_band(0.0, "Buy", settings)
        self.assertEqual((zero_low, zero_high), (0.0, 0.0))


    def test_action_plan_inside_target_hold_has_no_active_trigger(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        row = {
            "rating": "Strong Buy",
            "current_position_weight": 6.70,
            "target_weight_low": 6.27,
            "target_weight_mid": 7.84,
            "target_weight_high": 9.41,
            "current_price": 366.40,
            "expected_price": 604.93,
            "upside": 65.10,
            "allocation_score": 0.74,
            "bucket_sizing_score": 0.78,
            "weighted_count": 1.0,
            "core_conviction_score": 0.8,
        }
        action, trigger_price, _, distance, reason = web_server._choose_action_plan_decision(row, settings)
        self.assertEqual(action, "Hold")
        self.assertEqual(row["position_status"], "INSIDE_TARGET")
        self.assertIsNone(trigger_price)
        self.assertIsNone(distance)
        self.assertEqual(row["relevant_trigger_type"], "hold")
        self.assertIsNone(row["relevant_trigger_price"])
        self.assertIsNone(row["dynamic_required_upside"])
        self.assertIn("inside target band", reason)

    def test_action_plan_overweight_high_upside_holds_until_trim_trigger(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        row = {
            "rating": "Strong Buy",
            "current_position_weight": 7.0,
            "target_weight_low": 4.0,
            "target_weight_mid": 5.0,
            "target_weight_high": 6.0,
            "current_price": 300.0,
            "expected_price": 600.0,
            "upside": 100.0,
            "allocation_score": 0.8,
            "bucket_sizing_score": 0.8,
            "weighted_count": 1.0,
            "core_conviction_score": 0.8,
            "current_position_market_value": 7000.0,
            "total_portfolio_value": 100000.0,
        }
        action, trigger_price, _, _, reason = web_server._choose_action_plan_decision(row, settings)
        self.assertIn(action, {"Trim", "Strong Trim"})
        self.assertEqual(row["position_status"], "ABOVE_TARGET")
        self.assertEqual(row["relevant_trigger_type"], "trim")
        self.assertLess(trigger_price, row["current_price"])
        self.assertEqual(row["trigger_anchor"], "Target High")
        self.assertIn("Trim trigger", reason)

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


class MomentumFeatureTests(unittest.TestCase):
    def _bars(self, start=100.0, days=260, step=0.4, volume=1_000_000):
        rows = []
        price = start
        for idx in range(days):
            price += step
            rows.append({
                "date": f"2025-01-{(idx % 28) + 1:02d}",
                "open": price - 0.5,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price,
                "volume": volume + idx * 1000,
            })
        return rows

    def test_deterministic_momentum_snapshot_scores_and_labels(self):
        import momentum_service

        stock_rows = self._bars(start=100.0, step=0.5)
        benchmark_rows = self._bars(start=100.0, step=0.2)
        snapshot = momentum_service.calculate_momentum_snapshot(stock_rows, benchmark_rows)
        self.assertGreaterEqual(snapshot["momentum_score"], 0.0)
        self.assertLessEqual(snapshot["momentum_score"], 5.0)
        self.assertGreaterEqual(snapshot["extension_risk"], 0.0)
        self.assertLessEqual(snapshot["extension_risk"], 5.0)
        self.assertIn(snapshot["momentum_label"], {"Very weak", "Weak", "Mixed / neutral", "Positive", "Strong"})
        self.assertIn(snapshot["extension_label"], {"Low extension", "Normal", "Extended", "Very extended"})
        self.assertEqual(snapshot["momentum_status"], "OK")
        self.assertIn("trend_score", snapshot["components"])
        self.assertIn("rel_60", snapshot["metrics"])

    def test_init_db_and_analysis_payload_include_stored_momentum(self):
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
                            analysis_root_id, version_number, symbol, current_price, expected_price,
                            expected_cagr, upside, confidence_level, created_at
                        ) VALUES (?, 1, 'NVDA', 100, 150, 15, 50, 8, ?)
                        """,
                        (root_id, now),
                    )
                    web_server.save_momentum_snapshot(
                        conn,
                        "NVDA",
                        "QQQ",
                        "1 Y",
                        {
                            "momentum_score": 3.61,
                            "momentum_label": "Positive",
                            "extension_risk": 1.42,
                            "extension_label": "Normal",
                            "momentum_status": "OK",
                            "warning": None,
                            "metrics": {"bars": 252, "first_date": "2025-01-01", "last_date": "2025-12-31", "latest_close": 123.45},
                            "components": {"trend_score": 0.7, "relative_strength_score": 0.6, "volume_score": 0.5, "price_structure_score": 0.8},
                        },
                    )
                    conn.commit()
                    row = web_server.list_analysis_symbols(conn)[0]
                    self.assertEqual(row["momentum_label"], "Positive")
                    self.assertAlmostEqual(row["momentum_score"], 3.61)
                    self.assertEqual(row["extension_label"], "Normal")
                    self.assertIn("momentum_updated_at", row)
                    detail = web_server.get_analysis_detail(conn, "NVDA")
                    self.assertEqual(detail["momentum"]["momentum_label"], "Positive")
                    self.assertAlmostEqual(detail["version"]["extension_risk"], 1.42)
                finally:
                    conn.close()

    def test_analysis_ui_contains_momentum_button_columns_and_endpoint(self):
        with open(os.path.join(os.path.dirname(__file__), "static", "index.html"), encoding="utf-8") as handle:
            html = handle.read()
        with open(os.path.join(os.path.dirname(__file__), "static", "app.js"), encoding="utf-8") as handle:
            js = handle.read()
        self.assertIn('id="analysis-update-momentum-btn"', html)
        self.assertNotIn('id="analysis-detail-momentum"', html)
        self.assertIn('data-sort-key="momentum_score"', html)
        self.assertIn('data-sort-key="extension_risk"', html)
        self.assertIn('data-sort-key="momentum_updated_at"', html)
        self.assertIn("/api/analysis/momentum/update", js)
        self.assertIn("formatMomentumListLabel(item.momentum_score, item.momentum_label, item.momentum_status)", js)
        self.assertIn("formatMomentumListLabel(item.extension_risk, item.extension_label, item.momentum_status)", js)
        self.assertIn("formatMomentumSummaryValue(item.momentum_score, item.momentum_label)", js)
        self.assertIn("formatMomentumSummaryValue(item.extension_risk, item.extension_label)", js)
        self.assertIn("Short-term technical momentum calculated from TWS historical price and volume data.", js)


class AllocationBasedTriggerTests(unittest.TestCase):
    def _decision_row(self, **overrides):
        row = {
            "symbol": "ALLOC",
            "rating": "Buy",
            "current_position_weight": 4.0,
            "target_weight_low": 5.0,
            "target_weight_mid": 6.0,
            "target_weight_high": 7.0,
            "current_price": 100.0,
            "expected_price": 150.0,
            "upside": 50.0,
            "current_position_market_value": 4_000.0,
            "total_portfolio_value": 100_000.0,
            "allocation_score": 0.8,
            "bucket_sizing_score": 0.8,
            "weighted_count": 1.0,
            "momentum_score": 2.5,
            "extension_risk": 2.0,
        }
        row.update(overrides)
        return row

    def test_allocation_trigger_price_formula_for_existing_position(self):
        trigger = web_server._allocation_trigger_price(
            current_price=100.0,
            current_market_value=10_000.0,
            portfolio_value=100_000.0,
            target_weight_pct=5.0,
        )
        expected = (0.05 * 90_000.0) / (100.0 * (1.0 - 0.05))
        self.assertAlmostEqual(trigger, expected)

    def test_momentum_and_extension_adjust_allocation_triggers(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        base_row = {
            "current_position_weight": 4.0,
            "target_weight_low": 5.0,
            "target_weight_mid": 6.0,
            "target_weight_high": 7.0,
            "current_price": 100.0,
            "expected_price": 150.0,
            "upside": 50.0,
            "current_position_market_value": 4_000.0,
            "total_portfolio_value": 100_000.0,
            "allocation_score": 0.8,
            "bucket_sizing_score": 0.8,
            "weighted_count": 1.0,
        }
        neutral = web_server._action_plan_trigger_context(dict(base_row, momentum_score=2.5, extension_risk=2.0), settings)
        strong_healthy = web_server._action_plan_trigger_context(dict(base_row, momentum_score=5.0, extension_risk=0.0), settings)
        extended = web_server._action_plan_trigger_context(dict(base_row, momentum_score=5.0, extension_risk=5.0), settings)
        weak = web_server._action_plan_trigger_context(dict(base_row, momentum_score=0.0, extension_risk=2.0), settings)
        self.assertEqual(neutral["trigger_anchor"], "Target Low")
        self.assertGreater(strong_healthy["add_trigger_price"], neutral["add_trigger_price"])
        self.assertLess(extended["add_trigger_price"], strong_healthy["add_trigger_price"])
        self.assertLess(weak["add_trigger_price"], neutral["add_trigger_price"])

        overweight_row = dict(base_row, current_position_weight=8.0, target_weight_low=5.0, target_weight_mid=6.0, target_weight_high=7.0, current_position_market_value=8_000.0)
        neutral_trim = web_server._action_plan_trigger_context(dict(overweight_row, momentum_score=2.5, extension_risk=2.0), settings)
        strong_trim = web_server._action_plan_trigger_context(dict(overweight_row, momentum_score=5.0, extension_risk=0.0), settings)
        extended_trim = web_server._action_plan_trigger_context(dict(overweight_row, momentum_score=5.0, extension_risk=5.0), settings)
        weak_trim = web_server._action_plan_trigger_context(dict(overweight_row, momentum_score=0.0, extension_risk=2.0), settings)
        self.assertEqual(neutral_trim["trigger_anchor"], "Target High")
        self.assertGreater(strong_trim["trim_trigger_price"], neutral_trim["trim_trigger_price"])
        self.assertLess(extended_trim["trim_trigger_price"], strong_trim["trim_trigger_price"])
        self.assertLess(weak_trim["trim_trigger_price"], neutral_trim["trim_trigger_price"])

    def test_allocation_trigger_gates_actions_and_uses_target_mid_for_amount(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        add_row = self._decision_row(current_position_market_value=4_000.0, current_position_weight=4.0, momentum_score=5.0, extension_risk=0.0)
        action, trigger_price, _, _, _ = web_server._choose_action_plan_decision(add_row, settings)
        amount_fields = web_server._action_amount_fields(action, add_row["current_position_weight"], add_row["target_weight_mid"], 100_000.0, add_row["current_position_market_value"])
        self.assertIn(action, {"Add", "Strong Add"})
        self.assertEqual(add_row["trigger_anchor"], "Target Low")
        self.assertLessEqual(add_row["current_price"], trigger_price)
        self.assertAlmostEqual(amount_fields["action_amount"], 2_000.0)

        wait_row = self._decision_row(current_position_weight=4.9, current_position_market_value=4_900.0, momentum_score=0.0, extension_risk=5.0)
        action, trigger_price, _, _, _ = web_server._choose_action_plan_decision(wait_row, settings)
        self.assertEqual(action, "Watch")
        self.assertEqual(wait_row["trigger_anchor"], "Target Low")
        self.assertGreater(wait_row["current_price"], trigger_price)

        trim_wait_row = self._decision_row(current_position_weight=7.2, current_position_market_value=7_200.0, momentum_score=5.0, extension_risk=0.0)
        action, trigger_price, _, _, _ = web_server._choose_action_plan_decision(trim_wait_row, settings)
        self.assertEqual(action, "Hold / Overweight")
        self.assertEqual(trim_wait_row["trigger_anchor"], "Target High")
        self.assertLess(trim_wait_row["current_price"], trigger_price)

        trim_row = self._decision_row(current_position_weight=8.0, current_position_market_value=8_000.0, momentum_score=0.0, extension_risk=5.0)
        action, trigger_price, _, _, _ = web_server._choose_action_plan_decision(trim_row, settings)
        amount_fields = web_server._action_amount_fields(action, trim_row["current_position_weight"], trim_row["target_weight_mid"], 100_000.0, trim_row["current_position_market_value"])
        self.assertIn(action, {"Trim", "Strong Trim"})
        self.assertEqual(trim_row["trigger_anchor"], "Target High")
        self.assertGreaterEqual(trim_row["current_price"], trigger_price)
        self.assertAlmostEqual(amount_fields["action_amount"], 2_000.0)

    def test_sell_override_and_non_owned_fallback(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        sell_row = self._decision_row(rating="Sell", current_position_weight=8.0, current_position_market_value=8_000.0, current_price=80.0, momentum_score=5.0, extension_risk=0.0)
        action, _, _, _, _ = web_server._choose_action_plan_decision(sell_row, settings)
        self.assertEqual(action, "Sell")
        self.assertEqual(sell_row["trigger_anchor"], "Sell Override")

        fallback_row = self._decision_row(current_position_weight=0.0, current_position_market_value=0.0, momentum_score=1.5, extension_risk=2.0)
        action, trigger_price, _, _, reason = web_server._choose_action_plan_decision(fallback_row, settings)
        self.assertEqual(action, "Watch")
        self.assertEqual(trigger_price, fallback_row["current_price"])
        self.assertIn("Momentum is weak", reason)

    def test_legacy_remaining_upside_settings_do_not_change_allocation_triggers(self):
        row = self._decision_row()
        base_settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        legacy_settings = dict(base_settings)
        legacy_settings.update({
            "action_add_required_upside": 99.0,
            "action_strong_add_required_upside": 120.0,
            "action_starter_buy_required_upside": 150.0,
            "action_trigger_min_required_upside": 80.0,
            "action_trigger_max_required_upside": 200.0,
            "action_underweight_discount_max": 0.0,
            "action_quality_discount_max": 0.0,
        })
        base_context = web_server._action_plan_trigger_context(dict(row), base_settings)
        legacy_context = web_server._action_plan_trigger_context(dict(row), legacy_settings)
        self.assertAlmostEqual(base_context["add_trigger_price"], legacy_context["add_trigger_price"])
        self.assertEqual(legacy_context["trigger_anchor"], "Target Low")

    def test_allocation_trigger_settings_validation(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_momentum_add_max_raise"] = 1.5
        with self.assertRaisesRegex(ValueError, "action_momentum_add_max_raise must be between 0 and 1"):
            web_server.validate_action_plan_settings(settings)
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_min_trigger_multiplier"] = 1.1
        with self.assertRaisesRegex(ValueError, "action_min_trigger_multiplier"):
            web_server.validate_action_plan_settings(settings)
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_min_trigger_multiplier"] = 1.0
        settings["action_max_trigger_multiplier"] = 1.0
        with self.assertRaisesRegex(ValueError, "action_max_trigger_multiplier must be greater"):
            web_server.validate_action_plan_settings(settings)


class WholeShareActionPlanTests(unittest.TestCase):
    def _settings(self):
        settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        settings["action_min_cash_unallocated_target"] = 0.0
        settings["action_min_executable_trade_amount"] = 0.0
        return settings

    def _row(self, action, amount, price, direction, **overrides):
        row = {
            "symbol": overrides.pop("symbol", "TEST"),
            "rating": overrides.pop("rating", "Buy"),
            "action": action,
            "action_amount": amount,
            "raw_action_amount": amount,
            "action_amount_direction": direction,
            "current_price": price,
            "current_position_market_value": 0.0,
            "allocation_score": 0.8,
            "bucket_sizing_score": 0.8,
            "trigger_quality_score": 0.8,
            "upside": 50.0,
        }
        row.update(overrides)
        return row

    def _execute(self, rows, cash=100_000.0):
        return web_server._apply_cash_constrained_execution_layer(rows, 100_000.0, cash, self._settings())

    def test_add_uses_floor_and_recomputes_whole_share_amount(self):
        row = self._row("Add", 5_778.0, 377.24, "add")
        summary = self._execute([row])
        self.assertEqual(row["raw_action_amount"], 5_778.0)
        self.assertEqual(row["desired_share_count"], 15)
        self.assertAlmostEqual(row["desired_whole_share_amount"], 5_658.60)
        self.assertEqual(row["action"], "Add")
        self.assertEqual(row["suggested_share_count"], 15)
        self.assertAlmostEqual(row["action_amount"], 5_658.60)
        self.assertEqual(row["action_amount_label"], "Add about $5,658.60")
        self.assertAlmostEqual(summary["total_add_demand"], 5_658.60)
        self.assertAlmostEqual(summary["funded_add_amount"], 5_658.60)

    def test_add_below_one_share_becomes_watch_and_contributes_zero_demand(self):
        row = self._row("Add", 339.0, 444.49, "add")
        summary = self._execute([row])
        self.assertEqual(row["action"], "Watch")
        self.assertEqual(row["desired_share_count"], 0)
        self.assertEqual(row["suggested_share_count"], 0)
        self.assertEqual(row["action_amount"], 0.0)
        self.assertEqual(row["action_amount_label"], "—")
        self.assertEqual(row["funding_status"], "Below one-share minimum")
        self.assertTrue(row["minimum_trade_size_blocked"])
        self.assertEqual(row["minimum_trade_size_reason"], "Calculated add amount is below the price of one whole share.")
        self.assertEqual(summary["total_add_demand"], 0.0)
        self.assertEqual(summary["funded_add_amount"], 0.0)
        self.assertEqual(summary["unfunded_add_demand"], 0.0)

    def test_trim_uses_whole_shares_and_below_minimum_becomes_hold(self):
        trim = self._row(
            "Trim",
            1_360.65,
            96.20,
            "trim",
            owned_share_quantity=50,
            current_position_market_value=4_810.0,
        )
        blocked = self._row(
            "Strong Trim",
            80.0,
            125.0,
            "trim",
            symbol="BLOCKED",
            owned_share_quantity=10,
            current_position_market_value=1_250.0,
        )
        summary = self._execute([trim, blocked], cash=0.0)
        self.assertEqual(trim["desired_share_count"], 14)
        self.assertEqual(trim["suggested_share_count"], 14)
        self.assertAlmostEqual(trim["action_amount"], 1_346.80)
        self.assertEqual(trim["action_amount_label"], "Trim about $1,346.80")
        self.assertEqual(blocked["action"], "Hold")
        self.assertEqual(blocked["suggested_share_count"], 0)
        self.assertEqual(blocked["funding_status"], "Below one-share minimum")
        self.assertTrue(blocked["minimum_trade_size_blocked"])
        self.assertAlmostEqual(summary["executable_sell_trim_proceeds"], 1_346.80)

    def test_full_sell_uses_actual_owned_whole_shares(self):
        row = self._row(
            "Sell",
            850.0,
            50.0,
            "sell",
            rating="Sell",
            owned_share_quantity=17,
            current_position_market_value=850.0,
        )
        summary = self._execute([row], cash=0.0)
        self.assertEqual(row["desired_share_count"], 17)
        self.assertEqual(row["suggested_share_count"], 17)
        self.assertEqual(row["action_amount"], 850.0)
        self.assertEqual(row["action_amount_label"], "Sell about $850.00")
        self.assertEqual(summary["executable_sell_trim_proceeds"], 850.0)

    def test_trim_cap_and_fractional_ownership_never_round_up(self):
        row = self._row(
            "Strong Trim",
            1_000.0,
            100.0,
            "trim",
            owned_share_quantity=3.6,
            current_position_market_value=360.0,
        )
        self._execute([row], cash=0.0)
        self.assertEqual(row["desired_share_count"], 10)
        self.assertEqual(row["owned_whole_share_count"], 3)
        self.assertEqual(row["suggested_share_count"], 3)
        self.assertEqual(row["action_amount"], 300.0)
        self.assertIn("fractional", row["whole_share_diagnostic_warning"])
        self.assertEqual(web_server._whole_shares_from_quantity(16.9999999999), 17)

    def test_invalid_prices_are_non_executable_without_crashing(self):
        add = self._row("Strong Add", 1_000.0, 0.0, "add")
        trim = self._row("Trim", 1_000.0, None, "trim", owned_share_quantity=20)
        sell = self._row("Strong Sell", 1_000.0, "invalid", "sell", owned_share_quantity=20)
        self._execute([add, trim, sell], cash=10_000.0)
        self.assertEqual(add["action"], "Watch")
        self.assertEqual(trim["action"], "Hold")
        self.assertEqual(sell["action"], "Re-evaluate")
        for row in (add, trim, sell):
            self.assertEqual(row["suggested_share_count"], 0)
            self.assertEqual(row["action_amount"], 0.0)
            self.assertEqual(row["action_amount_label"], "—")
            self.assertEqual(row["whole_share_diagnostic_reason"], "Cannot calculate whole-share action because current price is unavailable.")

    def test_strong_add_and_starter_buy_follow_whole_share_rules(self):
        rows = [
            self._row("Strong Add", 1_050.0, 200.0, "add", symbol="STRONG", rating="Strong Buy"),
            self._row("Starter Buy", 650.0, 200.0, "add", symbol="STARTER", rating="Speculative Buy"),
        ]
        self._execute(rows)
        self.assertEqual(rows[0]["suggested_share_count"], 5)
        self.assertEqual(rows[0]["action_amount"], 1_000.0)
        self.assertEqual(rows[1]["suggested_share_count"], 3)
        self.assertEqual(rows[1]["action_amount"], 600.0)

    def test_cash_funding_allocates_only_whole_shares(self):
        partial = self._row("Add", 1_500.0, 300.0, "add")
        summary = self._execute([partial], cash=1_000.0)
        self.assertEqual(partial["action"], "Add")
        self.assertEqual(partial["desired_share_count"], 5)
        self.assertEqual(partial["suggested_share_count"], 3)
        self.assertEqual(partial["action_amount"], 900.0)
        self.assertEqual(partial["unfunded_share_count"], 2)
        self.assertEqual(partial["unfunded_action_amount"], 600.0)
        self.assertEqual(partial["funding_status"], "Partially funded")
        self.assertEqual(summary["funded_add_amount"], 900.0)
        self.assertEqual(summary["unfunded_add_demand"], 600.0)

        unfunded = self._row("Add", 1_500.0, 300.0, "add")
        summary = self._execute([unfunded], cash=250.0)
        self.assertEqual(unfunded["action"], "Watch")
        self.assertEqual(unfunded["desired_action"], "Add")
        self.assertEqual(unfunded["executable_action"], "Watch")
        self.assertEqual(unfunded["suggested_share_count"], 0)
        self.assertEqual(unfunded["action_amount"], 0.0)
        self.assertEqual(unfunded["action_amount_label"], "—")
        self.assertEqual(unfunded["action_amount_direction"], "none")
        self.assertEqual(unfunded["funding_status"], "Unfunded / Watch")
        self.assertEqual(summary["funded_add_amount"], 0.0)
        self.assertEqual(summary["unfunded_add_demand"], 1_500.0)

    def test_unfunded_add_types_become_watch_without_changing_funding_totals(self):
        for action, rating in (("Strong Add", "Strong Buy"), ("Add", "Buy"), ("Starter Buy", "Speculative Buy")):
            with self.subTest(action=action):
                row = self._row(action, 1_500.0, 300.0, "add", rating=rating)
                summary = self._execute([row], cash=0.0)
                self.assertEqual(row["action"], "Watch")
                self.assertEqual(row["desired_action"], action)
                self.assertEqual(row["executable_action"], "Watch")
                self.assertEqual(row["suggested_share_count"], 0)
                self.assertEqual(row["action_amount"], 0.0)
                self.assertEqual(row["action_amount_label"], "—")
                self.assertEqual(row["action_amount_direction"], "none")
                self.assertEqual(row["funding_status"], "Unfunded / Watch")
                self.assertEqual(summary["funded_add_amount"], 0.0)
                self.assertEqual(summary["unfunded_add_demand"], 1_500.0)

    def test_linear_execution_uses_the_same_whole_share_layer(self):
        add = self._row("Add", 5_778.0, 377.24, "add")
        add["target_gap_amount"] = 5_778.0
        add["linear_allocation_score"] = 0.9
        add["expected_cagr"] = 20.0
        summary = web_server._apply_linear_cash_constrained_execution_layer(
            [add], 100_000.0, 10_000.0, self._settings()
        )
        self.assertEqual(add["suggested_share_count"], 15)
        self.assertAlmostEqual(add["action_amount"], 5_658.60)
        self.assertAlmostEqual(summary["total_add_demand"], 5_658.60)

    def test_safe_floor_tolerance_and_ui_shares_columns(self):
        self.assertEqual(web_server.whole_shares_for_amount(1_499.9999999, 100.0), 15)
        self.assertEqual(web_server.whole_shares_for_amount(1_499.90, 100.0), 14)
        html = Path("static/index.html").read_text(encoding="utf-8")
        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertEqual(html.count('data-sort-key="suggested_share_count"'), 1)
        self.assertIn("function formatSuggestedShareCount(item)", js)
        self.assertIn('<td class="shares-cell">${formatSuggestedShareCount(item)}</td>', js)
