import unittest
from copy import deepcopy
from datetime import datetime, timezone

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
    return row


class ManualExecutionEvaluationTests(unittest.TestCase):
    def test_buy_threshold_is_inclusive_and_rechecked_at_current_price(self):
        preference = {"buy_trigger_price": 80}
        self.assertEqual(web_server.evaluate_manual_execution_trigger(verified_row(), preference, NOW)["status"], "waiting")
        for price in (80, 75):
            with self.subTest(price=price):
                result = web_server.evaluate_manual_execution_trigger(verified_row(current_price=price), preference, NOW)
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
        self.assertEqual(rows["AAA"]["fulfilled_reservation_from_projected_proceeds"], 0)
        self.assertEqual(summary["available_buy_budget"], 0)

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
        payload = web_server.compute_linear_action_plan(
            [candidate], 100_000, 10_000,
            linear_settings(action_min_cash_unallocated_target=0, linear_max_reserve_pct=0),
            manual_triggers={"AAA": {"buy_trigger_price": 80, "reserve_enabled": True, "reserve_percentage": 100}},
        )["manual_execution"]
        row = payload["rows"][0]
        self.assertEqual(row["manual_trigger_status"], "eligible")
        self.assertEqual(row["requested_reservation"], 0)
        self.assertGreater(row["suggested_share_count"], 0)
        self.assertEqual(row["executable_action_amount"], row["suggested_share_count"] * 75)

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
        self.assertEqual(row["fulfilled_reservation_from_existing_cash"], 0)
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


if __name__ == "__main__":
    unittest.main()
