import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import web_server


NOW = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


def verified_row(**overrides):
    row = {
        "symbol": "NVDA",
        "action": "Add",
        "current_price": 100.0,
        "owned_share_quantity": 50,
        "position_price_status": "tws_received",
        "price_source": "marketPrice",
        "price_sizing_source": "position_quote",
        "price_last_successful_at": "2026-01-01T09:59:00+00:00",
        "target_weight_mid": 10.0,
        "manual_trigger_status": "waiting",
    }
    row.update(overrides)
    if "manual_quote_proof" not in overrides:
        quote_at = row.get("price_last_successful_at")
        price = row.get("current_price")
        row["manual_quote_proof"] = {
            "source": "live_bid_ask", "bid": price - 1 if isinstance(price, (int, float)) else None,
            "ask": price, "bid_tick_at": quote_at, "ask_tick_at": quote_at,
            "refresh_at": quote_at,
        }
    return row


class ManualExecutionEvaluationTests(unittest.TestCase):
    def test_buy_threshold_is_inclusive_and_rechecked_at_current_price(self):
        preference = {"buy_trigger_price": 80}
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(), preference, NOW)["status"], "waiting")
        for action in ("Starter Buy", "Add", "Strong Add"):
            for price in (80, 75):
                with self.subTest(action=action, price=price):
                    result = web_server.evaluate_manual_execution_trigger(verified_row(action=action, current_price=price), preference, NOW)
                    self.assertEqual(result["status"], "eligible")
                    self.assertEqual(result["verified_price"], price)

    def test_sell_and_trim_share_one_threshold_and_direction(self):
        above = {"sell_trigger_price": 120, "sell_trigger_direction": "at_or_above"}
        below = {"sell_trigger_price": 90, "sell_trigger_direction": "at_or_below"}
        for action in ("Trim", "Strong Trim", "Sell", "Strong Sell"):
            with self.subTest(action=action):
                self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action=action), above, NOW)["status"], "waiting")
                self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action=action, current_price=125), above, NOW)["status"], "eligible")
                self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action=action, current_price=85), below, NOW)["status"], "eligible")

    def test_no_relevant_trigger_keeps_existing_execution(self):
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(), {}, NOW)["status"], "no_manual_trigger")
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action="Hold"), {"buy_trigger_price": 80}, NOW)["status"], "no_manual_trigger")
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(action="Sell"), {"buy_trigger_price": 80}, NOW)["status"], "no_manual_trigger")

    def test_stale_cached_delayed_and_unowned_prices_require_confirmation(self):
        preference = {"buy_trigger_price": 120}
        cases = (
            {"position_price_status": "cached_stale"},
            {"price_sizing_source": "analysis_price_fallback"},
            {"price_source": "close"},
            {"price_source": "delayed_market_data"},
            {"price_last_successful_at": "2026-01-01T09:54:00+00:00"},
            {"price_last_successful_at": None},
            {"owned_share_quantity": 0},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                result = web_server.evaluate_manual_execution_trigger(verified_row(**changes), preference, NOW)
                self.assertEqual(result["status"], "price_confirmation_required")
                self.assertIsNone(result["verified_price"])
        boundary = web_server.evaluate_manual_execution_trigger(
            verified_row(current_price=120, price_last_successful_at="2026-01-01T09:55:00+00:00"), preference, NOW,
        )
        self.assertEqual(boundary["status"], "eligible")

    def test_delayed_position_quote_is_marked_unverified_for_manual_triggers(self):
        contract = SimpleNamespace(symbol="NVDA", secType="STK", currency="USD", exchange="SMART", conId=123)
        ticks = [
            SimpleNamespace(tickType=1, price=99.0, time=NOW),
            SimpleNamespace(tickType=2, price=101.0, time=NOW),
        ]
        ticker = SimpleNamespace(contract=contract, marketPrice=lambda: 100.0, last=100.0, close=95.0,
                                 prevClose=95.0, bid=99.0, ask=101.0, bidSize=1, askSize=1,
                                 marketDataType=1, ticks=ticks)
        position = SimpleNamespace(contract=contract, position=1.0, avgCost=80.0)
        contract_key = web_server.market_data_contract_key(contract)
        rows = web_server._build_live_position_rows(
            [position], {contract_key: ticker}, quote_success_at="2026-01-01T09:59:00+00:00",
        )
        self.assertEqual(rows[0]["price_source"], "marketPrice")
        proof = web_server._manual_quote_proof_from_ticker(
            ticker, contract_key, "2026-01-01T10:00:00+00:00", {"delayed": True}, now=NOW,
        )
        self.assertIsNone(proof)
        result = web_server.evaluate_manual_execution_trigger(verified_row(manual_quote_proof=proof),
                                                               {"buy_trigger_price": 120}, NOW)
        self.assertEqual(result["status"], "price_confirmation_required")

    def test_fresh_bid_and_ask_ticks_create_proof_but_old_ticks_do_not(self):
        contract = SimpleNamespace(symbol="NVDA", secType="STK", currency="USD", exchange="SMART", conId=123)
        now = datetime.now(timezone.utc)
        ticker = SimpleNamespace(
            contract=contract, marketPrice=lambda: 100.0, last=100.0, bid=99.0, ask=101.0,
            bidSize=1, askSize=1, marketDataType=1,
            ticks=[SimpleNamespace(tickType=1, price=99.0, size=1, time=now),
                   SimpleNamespace(tickType=2, price=101.0, size=1, time=now)],
        )
        key = web_server.market_data_contract_key(contract)
        observations = web_server._ManualQuoteObservations()
        observations.register(ticker, contract)
        observations.observe([ticker])
        proof = web_server._manual_quote_proof_from_ticker(ticker, key, now.isoformat(), {}, observations=observations, now=now)
        self.assertEqual(proof["bid"], 99)
        self.assertEqual(proof["ask"], 101)
        ticker.marketDataType = 2
        self.assertIsNone(web_server._manual_quote_proof_from_ticker(ticker, key, now.isoformat(), {}, observations=observations, now=now))
        ticker.marketDataType = 1
        ticker.ticks[1].time = now - timedelta(minutes=10)
        stale_observations = web_server._ManualQuoteObservations()
        stale_observations.register(ticker, contract)
        stale_observations.observe([ticker])
        self.assertIsNone(web_server._manual_quote_proof_from_ticker(ticker, key, now.isoformat(), {}, observations=stale_observations, now=now))

    def test_trigger_compares_buy_to_ask_and_sell_to_bid(self):
        buy = verified_row(current_price=75, manual_quote_proof={
            "source": "live_bid_ask", "bid": 84, "ask": 85,
            "bid_tick_at": "2026-01-01T09:59:00+00:00", "ask_tick_at": "2026-01-01T09:59:00+00:00",
            "refresh_at": "2026-01-01T09:59:00+00:00",
        })
        sell = verified_row(action="Sell", current_price=125, manual_quote_proof={
            "source": "live_bid_ask", "bid": 115, "ask": 116,
            "bid_tick_at": "2026-01-01T09:59:00+00:00", "ask_tick_at": "2026-01-01T09:59:00+00:00",
            "refresh_at": "2026-01-01T09:59:00+00:00",
        })
        self.assertEqual(web_server.evaluate_manual_execution_trigger(buy, {"buy_trigger_price": 80}, NOW)["status"], "waiting")
        self.assertEqual(web_server.evaluate_manual_execution_trigger(sell, {"sell_trigger_price": 120}, NOW)["status"], "waiting")

    def test_reservation_uses_additional_whole_shares_at_trigger_price(self):
        preference = {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 60}
        result = web_server.calculate_manual_reservation(verified_row(), preference, 100_000, 0)
        self.assertEqual(result["planned_purchase_shares_at_trigger"], 75)
        self.assertEqual(result["planned_purchase_amount_at_trigger"], 6_000)
        self.assertEqual(result["requested_reservation"], 3_600)
        full = web_server.calculate_manual_reservation(verified_row(), {**preference, "reserve_percentage": 100}, 100_000, 0)
        self.assertEqual(full["requested_reservation"], 6_000)

    def test_reservation_is_inactive_when_disabled_satisfied_or_not_a_buy(self):
        preference = {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 60}
        cases = (
            (verified_row(manual_trigger_status="eligible"), preference),
            (verified_row(action="Sell"), preference),
            (verified_row(), {**preference, "reserve_enabled": False}),
            (verified_row(), {**preference, "reserve_percentage": 0}),
            (verified_row(), {**preference, "buy_trigger_price": None}),
        )
        for row, settings in cases:
            with self.subTest(row=row, settings=settings):
                self.assertEqual(web_server.calculate_manual_reservation(row, settings, 100_000, 0)["requested_reservation"], 0)
        self.assertEqual(web_server.calculate_manual_reservation(verified_row(), preference, 100_000, 6_001)["requested_reservation"], 0)


def linear_settings(**overrides):
    settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
    settings.update({
        "linear_allocated_target_total_pct": 20.0,
        "linear_min_score_threshold": 0.0,
        "linear_score_allocation_power": 1.0,
        "linear_max_single_stock_pct": 100.0,
        "linear_enable_risk_caps": False,
        "linear_rating_bonus_enabled": False,
        "hold_rating_penalty_enabled": False,
        "core_confidence_penalty": 0.0,
        "upside_penalty": 0.0,
        "potential_confidence_penalty": 0.0,
        "action_min_cash_unallocated_target": 5.0,
        "linear_max_reserve_pct": 5.0,
        "linear_min_equity_excess_cagr_pct": 0.0,
        "linear_full_attractiveness_equity_excess_cagr_pct": 10.0,
        "linear_add_band_tolerance_pct": 0.0,
        "linear_trim_band_tolerance_pct": 0.0,
        "action_min_executable_trade_amount": 0.0,
        "linear_high_extension_guardrail_enabled": False,
    })
    settings.update(overrides)
    return settings


def linear_candidate(symbol, **overrides):
    candidate = {
        "symbol": symbol,
        "rating": "Buy",
        "expected_cagr": 18.0,
        "upside": 60.0,
        "core_confidence_diff": 6.0,
        "core_bullish_confidence": 8.0,
        "core_bearish_confidence": 2.0,
        "potential_confidence_diff": 4.0,
        "potential_bullish_confidence": 7.0,
        "potential_bearish_confidence": 1.0,
        "current_position_weight": 0.1,
        "current_position_market_value": 100.0,
        "owned_share_quantity": 1.0,
        "current_price": 100.0,
        "expected_price": 160.0,
        "price_sizing_source": "position_quote",
        "position_price_status": "tws_received",
        "price_source": "marketPrice",
        "price_last_successful_at": web_server.utc_now_iso(),
        "extension_risk": 1.0,
    }
    candidate.update(overrides)
    if "manual_quote_proof" not in overrides and candidate["owned_share_quantity"]:
        quote_at = candidate["price_last_successful_at"]
        price = candidate["current_price"]
        candidate["manual_quote_proof"] = {
            "source": "live_bid_ask", "bid": price - 1, "ask": price,
            "bid_tick_at": quote_at, "ask_tick_at": quote_at, "refresh_at": quote_at,
        }
    return candidate


def rows_by_symbol(payload):
    return {row["symbol"]: row for row in payload["rows"]}


class ManualExecutionFundingTests(unittest.TestCase):
    def test_opt_in_keeps_baseline_rows_and_summary_byte_equivalent(self):
        candidates = [linear_candidate("AAA"), linear_candidate("BBB")]
        original_inputs = deepcopy(candidates)
        baseline = web_server.compute_linear_action_plan(candidates, 100_000, 20_000, linear_settings())
        combined = web_server.compute_linear_action_plan(candidates, 100_000, 20_000, linear_settings(), manual_triggers={"AAA": {"buy_trigger_price": 80}})
        self.assertEqual(combined["rows"], baseline["rows"])
        self.assertEqual(combined["summary"], baseline["summary"])
        self.assertEqual(candidates, original_inputs)
        self.assertEqual(rows_by_symbol(combined["manual_execution"])["AAA"]["recommended_action"], "Add")

    def test_blocked_buy_reserves_only_additional_purchase_and_reallocates_remaining_cash(self):
        candidates = [linear_candidate("AAA"), linear_candidate("BBB")]
        payload = web_server.compute_linear_action_plan(candidates, 100_000, 20_000, linear_settings(), manual_triggers={
            "AAA": {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 60},
        })
        baseline = rows_by_symbol(payload)
        manual = rows_by_symbol(payload["manual_execution"])
        summary = payload["manual_execution"]["summary"]
        self.assertEqual(manual["AAA"]["manual_trigger_status"], "waiting")
        self.assertEqual(manual["AAA"]["recommended_action"], "Add")
        self.assertEqual(manual["AAA"]["suggested_share_count"], 0)
        self.assertEqual(manual["AAA"]["executable_action_amount"], 0)
        self.assertEqual(manual["AAA"]["planned_purchase_amount_at_trigger"], 9_920)
        self.assertEqual(manual["AAA"]["requested_reservation"], 5_952)
        self.assertEqual(manual["AAA"]["fulfilled_reservation"], 5_952)
        self.assertGreater(manual["BBB"]["executable_action_amount"], baseline["BBB"]["executable_action_amount"])
        self.assertLessEqual(summary["funded_add_amount"] + summary["fulfilled_reservations"], summary["available_buy_budget_before_manual_reservations"] + 1e-6)
        self.assertGreaterEqual(summary["remaining_buy_budget"], 0)

    def test_reservations_are_partial_by_existing_priority_and_do_not_consume_dynamic_reserve(self):
        payload = web_server.compute_linear_action_plan(
            [linear_candidate("AAA"), linear_candidate("BBB")], 100_000, 10_000, linear_settings(),
            manual_triggers={symbol: {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 100} for symbol in ("AAA", "BBB")},
        )["manual_execution"]
        rows = rows_by_symbol(payload)
        summary = payload["summary"]
        self.assertEqual(summary["target_reserve_amount"], 5_000)
        self.assertEqual(summary["available_buy_budget_before_manual_reservations"], 5_000)
        self.assertEqual(summary["fulfilled_reservations"], 5_000)
        self.assertGreater(rows["AAA"]["fulfilled_reservation"], 0)
        self.assertEqual(rows["BBB"]["fulfilled_reservation"], 0)
        self.assertEqual(rows["AAA"]["fulfilled_reservation_from_current_cash_like"], 5_000)
        self.assertEqual(rows["AAA"]["fulfilled_reservation_from_projected_proceeds"], 0)
        self.assertEqual(summary["available_buy_budget"], 0)

    def test_higher_linear_priority_reservation_precedes_alphabetical_order(self):
        candidates = [
            linear_candidate("AAA", expected_cagr=12.0, upside=30.0),
            linear_candidate("ZZZ", expected_cagr=30.0, upside=80.0),
        ]
        payload = web_server.compute_linear_action_plan(
            candidates, 100_000, 3_000,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={symbol: {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 100}
                             for symbol in ("AAA", "ZZZ")},
        )["manual_execution"]
        rows = rows_by_symbol(payload)
        self.assertGreater(rows["ZZZ"]["linear_action_priority"], rows["AAA"]["linear_action_priority"])
        self.assertEqual(rows["ZZZ"]["fulfilled_reservation"], 3_000)
        self.assertEqual(rows["AAA"]["fulfilled_reservation"], 0)

    def test_disabling_reservation_releases_budget_to_other_buy(self):
        candidates = [linear_candidate("AAA"), linear_candidate("BBB")]
        settings = linear_settings()
        enabled = web_server.compute_linear_action_plan(candidates, 100_000, 20_000, settings,
            manual_triggers={"AAA": {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 100}})["manual_execution"]
        disabled = web_server.compute_linear_action_plan(candidates, 100_000, 20_000, settings,
            manual_triggers={"AAA": {"buy_trigger_price": 80, "reserve_enabled": False, "reserve_percentage": 100}})["manual_execution"]
        self.assertEqual(disabled["summary"]["fulfilled_reservations"], 0)
        self.assertGreater(disabled["summary"]["available_buy_budget"], enabled["summary"]["available_buy_budget"])
        self.assertGreater(rows_by_symbol(disabled)["BBB"]["executable_action_amount"],
                           rows_by_symbol(enabled)["BBB"]["executable_action_amount"])

    def test_blocked_sell_has_no_projected_proceeds_and_eligible_sell_does(self):
        candidates = [
            linear_candidate("AAA", rating="Sell", current_position_weight=1.0,
                             current_position_market_value=1_000.0, owned_share_quantity=10.0),
            linear_candidate("BBB", current_position_weight=0.0,
                             current_position_market_value=0.0, owned_share_quantity=0.0,
                             price_sizing_source="analysis_price_fallback"),
        ]
        blocked = web_server.compute_linear_action_plan(candidates, 100_000, 0, linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0), manual_triggers={
            "AAA": {"sell_trigger_price": 120, "sell_trigger_direction": "at_or_above"},
        })["manual_execution"]
        self.assertGreater(web_server.compute_linear_action_plan(candidates, 100_000, 0, linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0))["summary"]["executable_sell_trim_proceeds"], 0)
        self.assertEqual(blocked["summary"]["executable_sell_trim_proceeds"], 0)
        self.assertEqual(rows_by_symbol(blocked)["AAA"]["recommended_action"], "Sell")
        self.assertEqual(rows_by_symbol(blocked)["AAA"]["executable_action_amount"], 0)
        eligible = web_server.compute_linear_action_plan(candidates, 100_000, 0, linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0), manual_triggers={
            "AAA": {"sell_trigger_price": 90, "sell_trigger_direction": "at_or_above"},
        })["manual_execution"]
        self.assertGreater(eligible["summary"]["executable_sell_trim_proceeds"], 0)

    def test_blocked_buy_cannot_be_bootstrapped(self):
        candidate = linear_candidate("AAA", current_position_weight=0.0, current_position_market_value=0.0,
                                     owned_share_quantity=0.0, price_sizing_source="analysis_price_fallback")
        settings = linear_settings(linear_allocated_target_total_pct=0.01,
                                   action_min_cash_unallocated_target=0.0, linear_max_reserve_pct=0.0)
        baseline = web_server.compute_linear_action_plan([candidate], 100_000, 100, settings)
        manual = web_server.compute_linear_action_plan([candidate], 100_000, 100, settings,
                                                       manual_triggers={"AAA": {"buy_trigger_price": 80}})["manual_execution"]
        self.assertTrue(baseline["summary"]["bootstrap_execution_active"])
        self.assertEqual(manual["summary"]["bootstrap_candidate_count"], 0)
        self.assertEqual(manual["rows"][0]["suggested_share_count"], 0)
        self.assertEqual(manual["rows"][0]["manual_trigger_status"], "price_confirmation_required")

    def test_eligible_buy_releases_reservation_and_uses_verified_current_price(self):
        candidate = linear_candidate("AAA", current_price=75.0, current_position_market_value=75.0,
                                     current_position_weight=0.075)
        quote_at = candidate["price_last_successful_at"]
        candidate["manual_quote_proof"] = {
            "source": "live_bid_ask", "bid": 74.0, "ask": 79.0,
            "bid_tick_at": quote_at, "ask_tick_at": quote_at, "refresh_at": quote_at,
        }
        payload = web_server.compute_linear_action_plan(
            [candidate], 100_000, 10_000,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"AAA": {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 100}},
        )["manual_execution"]
        row = payload["rows"][0]
        self.assertEqual(row["manual_trigger_status"], "eligible")
        self.assertEqual(row["manual_verified_price"], 79)
        self.assertEqual(row["current_price"], 79)
        self.assertEqual(row["requested_reservation"], 0)
        self.assertGreater(row["suggested_share_count"], 0)
        self.assertEqual(row["executable_action_amount"], row["suggested_share_count"] * 79)

    def test_eligible_sell_sizes_proceeds_at_verified_bid(self):
        candidate = linear_candidate("AAA", rating="Sell", current_price=125.0,
                                     current_position_market_value=1_250.0,
                                     current_position_weight=1.25, owned_share_quantity=10.0)
        quote_at = candidate["price_last_successful_at"]
        candidate["manual_quote_proof"] = {
            "source": "live_bid_ask", "bid": 121.0, "ask": 126.0,
            "bid_tick_at": quote_at, "ask_tick_at": quote_at, "refresh_at": quote_at,
        }
        payload = web_server.compute_linear_action_plan(
            [candidate], 100_000, 0,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"AAA": {"sell_trigger_price": 120, "sell_trigger_direction": "at_or_above"}},
        )
        baseline = payload["rows"][0]
        row = payload["manual_execution"]["rows"][0]
        self.assertEqual(row["manual_trigger_status"], "eligible")
        self.assertEqual(row["manual_verified_price"], 121)
        self.assertEqual(row["current_price"], 121)
        self.assertEqual(row["executable_action_amount"], row["suggested_share_count"] * 121)
        self.assertEqual(baseline["current_price"], 125)

    def test_eligible_buy_recomputes_gap_for_owned_shares_at_verified_ask(self):
        candidate = linear_candidate("AAA", current_price=100.0,
                                     current_position_market_value=10_000.0,
                                     current_position_weight=10.0, owned_share_quantity=100.0)
        quote_at = candidate["price_last_successful_at"]
        candidate["manual_quote_proof"] = {
            "source": "live_bid_ask", "bid": 79.0, "ask": 80.0,
            "bid_tick_at": quote_at, "ask_tick_at": quote_at, "refresh_at": quote_at,
        }
        payload = web_server.compute_linear_action_plan(
            [candidate], 100_000, 100_000,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"AAA": {"buy_trigger_price": 85}},
        )
        base = payload["rows"][0]
        row = payload["manual_execution"]["rows"][0]
        expected_shares = int((row["target_weight_mid"] / 100 * 100_000 - 100 * 80) // 80)
        self.assertEqual(row["manual_trigger_status"], "eligible")
        self.assertEqual(row["desired_share_count"], expected_shares)
        self.assertEqual(row["suggested_share_count"], expected_shares)
        self.assertEqual(row["executable_action_amount"], expected_shares * 80)
        self.assertEqual(base["current_position_market_value"], 10_000)

    def test_eligible_trim_recomputes_gap_for_owned_shares_at_verified_bid(self):
        candidate = linear_candidate("AAA", current_price=125.0,
                                     current_position_market_value=12_500.0,
                                     current_position_weight=12.5, owned_share_quantity=100.0)
        quote_at = candidate["price_last_successful_at"]
        candidate["manual_quote_proof"] = {
            "source": "live_bid_ask", "bid": 80.0, "ask": 81.0,
            "bid_tick_at": quote_at, "ask_tick_at": quote_at, "refresh_at": quote_at,
        }
        payload = web_server.compute_linear_action_plan(
            [candidate], 100_000, 0,
            linear_settings(linear_allocated_target_total_pct=5.0,
                            action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"AAA": {"sell_trigger_price": 90, "sell_trigger_direction": "at_or_below"}},
        )
        base = payload["rows"][0]
        row = payload["manual_execution"]["rows"][0]
        expected_shares = int((100 * 80 - row["target_weight_high"] / 100 * 100_000) // 80)
        self.assertEqual(row["recommended_action"], "Trim")
        self.assertEqual(row["manual_trigger_status"], "eligible")
        self.assertEqual(row["suggested_share_count"], expected_shares)
        self.assertEqual(row["executable_action_amount"], expected_shares * 80)
        self.assertEqual(base["current_position_market_value"], 12_500)

    def test_eligible_buy_with_quote_above_target_has_no_executable_gap(self):
        candidate = linear_candidate("AAA", current_price=100.0,
                                     current_position_market_value=10_000.0,
                                     current_position_weight=10.0, owned_share_quantity=100.0)
        quote_at = candidate["price_last_successful_at"]
        candidate["manual_quote_proof"] = {
            "source": "live_bid_ask", "bid": 249.0, "ask": 250.0,
            "bid_tick_at": quote_at, "ask_tick_at": quote_at, "refresh_at": quote_at,
        }
        payload = web_server.compute_linear_action_plan(
            [candidate], 100_000, 100_000,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"AAA": {"buy_trigger_price": 300}},
        )
        row = payload["manual_execution"]["rows"][0]
        self.assertEqual(row["recommended_action"], "Add")
        self.assertEqual(row["manual_trigger_status"], "eligible")
        self.assertEqual(row["current_position_weight"], 25)
        self.assertEqual(row["position_status"], "ABOVE_TARGET")
        self.assertEqual(row["target_gap_amount"], 0)
        self.assertEqual(row["executable_action_amount"], 0)
        self.assertIn("no additional executable gap", row["linear_explanation"])
        self.assertEqual(payload["manual_execution"]["summary"]["current_equity_allocation"], 25)
        self.assertEqual(payload["summary"]["current_equity_allocation"], 10)

    def test_projected_sell_proceeds_reservation_is_identified_separately_from_cash(self):
        candidates = [
            linear_candidate("SELL", rating="Sell", current_position_weight=1.0,
                             current_position_market_value=1_000.0, owned_share_quantity=10.0),
            linear_candidate("BUY", current_position_weight=0.1,
                             current_position_market_value=100.0, owned_share_quantity=1.0),
        ]
        payload = web_server.compute_linear_action_plan(
            candidates, 100_000, 0,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"BUY": {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 100}},
        )["manual_execution"]
        row = rows_by_symbol(payload)["BUY"]
        self.assertEqual(payload["summary"]["current_cash_unallocated"], 0)
        self.assertEqual(payload["summary"]["executable_sell_trim_proceeds"], 1_000)
        self.assertEqual(row["fulfilled_reservation"], 1_000)
        self.assertEqual(row["fulfilled_reservation_from_current_cash_like"], 0)
        self.assertEqual(row["fulfilled_reservation_from_projected_proceeds"], 1_000)
        self.assertEqual(payload["summary"]["funded_add_amount"], 0)

    def test_no_trigger_mode_has_the_same_executed_amounts_as_baseline(self):
        candidates = [linear_candidate("AAA"), linear_candidate("BBB")]
        payload = web_server.compute_linear_action_plan(candidates, 100_000, 12_000, linear_settings(), manual_triggers={})
        base = rows_by_symbol(payload)
        manual = rows_by_symbol(payload["manual_execution"])
        for symbol in base:
            for field in ("rating", "action", "target_weight_mid", "target_weight_low", "target_weight_high",
                          "linear_allocation_score", "suggested_share_count", "executable_action_amount", "funding_status"):
                self.assertEqual(manual[symbol][field], base[symbol][field], (symbol, field))
        for field in ("available_buy_budget", "funded_add_amount", "target_reserve_amount", "bootstrap_execution_active"):
            self.assertEqual(payload["manual_execution"]["summary"][field], payload["summary"][field], field)

    def test_no_trigger_mode_preserves_bootstrap_execution(self):
        candidate = linear_candidate("AAA", current_position_weight=0.0, current_position_market_value=0.0,
                                     owned_share_quantity=0.0, price_sizing_source="analysis_price_fallback")
        settings = linear_settings(linear_allocated_target_total_pct=0.01,
                                   action_min_cash_unallocated_target=0.0, linear_max_reserve_pct=0.0)
        payload = web_server.compute_linear_action_plan([candidate], 100_000, 100, settings, manual_triggers={})
        self.assertTrue(payload["summary"]["bootstrap_execution_active"])
        self.assertEqual(payload["manual_execution"]["summary"]["bootstrap_amount_funded"], payload["summary"]["bootstrap_amount_funded"])
        self.assertEqual(payload["manual_execution"]["rows"][0]["suggested_share_count"], payload["rows"][0]["suggested_share_count"])


if __name__ == "__main__":
    unittest.main()
