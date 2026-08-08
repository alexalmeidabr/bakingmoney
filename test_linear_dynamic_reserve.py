import json
import math
import sqlite3
import unittest

import web_server


def scenario_for_cagr(cagr, probability=1.0, current_price=100.0, name="Base"):
    target = current_price * ((1.0 + cagr / 100.0) ** 5)
    return {
        "scenario_name": name,
        "price_low": target,
        "price_high": target,
        "probability": probability,
    }


def reserve_settings(**overrides):
    settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
    settings.update({
        "action_min_cash_unallocated_target": 5.0,
        "linear_max_reserve_pct": 40.0,
        "linear_reserve_benchmark_yield_pct": 4.0,
        "linear_min_equity_excess_cagr_pct": 2.0,
        "linear_full_attractiveness_equity_excess_cagr_pct": 7.0,
        **overrides,
    })
    return settings


class LinearExpectedCagrTests(unittest.TestCase):
    def test_midpoints_and_probabilities_drive_expected_cagr(self):
        scenarios = [
            {"price_low": 90.0, "price_high": 110.0, "probability": 20.0},
            {"price_low": 140.0, "price_high": 160.0, "probability": 55.0},
            {"price_low": 220.0, "price_high": 260.0, "probability": 25.0},
        ]
        actual, diagnostic = web_server.calculate_probability_weighted_expected_cagr(scenarios, 100.0)
        expected = sum(
            probability * web_server.compute_scenario_cagr(midpoint, 100.0)
            for midpoint, probability in ((100.0, 0.20), (150.0, 0.55), (240.0, 0.25))
        )
        self.assertIsNone(diagnostic)
        self.assertAlmostEqual(actual, expected)

    def test_current_price_changes_expected_cagr_without_scenario_changes(self):
        scenarios = [{"price_low": 150.0, "price_high": 170.0, "probability": 1.0}]
        lower_price_cagr, _ = web_server.calculate_probability_weighted_expected_cagr(scenarios, 80.0)
        higher_price_cagr, _ = web_server.calculate_probability_weighted_expected_cagr(scenarios, 120.0)
        self.assertGreater(lower_price_cagr, higher_price_cagr)

    def test_missing_price_and_invalid_scenarios_are_conservative(self):
        value, diagnostic = web_server.calculate_probability_weighted_expected_cagr([], None)
        self.assertIsNone(value)
        self.assertIn("current price", diagnostic)

        invalid_sets = [
            [],
            [{"price_low": -1.0, "price_high": 100.0, "probability": 1.0}],
            [{"price_low": 110.0, "price_high": 100.0, "probability": 1.0}],
            [{"price_low": 100.0, "price_high": 110.0, "probability": -0.1}],
            [{"price_low": 100.0, "price_high": 110.0, "probability": 0.0}],
        ]
        for scenarios in invalid_sets:
            with self.subTest(scenarios=scenarios):
                value, diagnostic = web_server.calculate_probability_weighted_expected_cagr(scenarios, 100.0)
                self.assertIsNone(value)
                self.assertTrue(diagnostic)

    def test_active_external_overlay_is_the_effective_scenario_source(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE analysis_version_scenarios (
                analysis_version_id INTEGER, scenario_name TEXT, price_low REAL,
                price_high REAL, probability REAL
            );
            CREATE TABLE analysis_final_scenario_overlays (
                analysis_version_id INTEGER, final_scenarios_json TEXT, is_stale INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO analysis_version_scenarios VALUES (1, 'Base', 120, 120, 1.0)"
        )
        overlay_scenarios = [scenario_for_cagr(15.0)]
        conn.execute(
            "INSERT INTO analysis_final_scenario_overlays VALUES (1, ?, 0)",
            (json.dumps(overlay_scenarios),),
        )
        scenarios, source = web_server.get_effective_analysis_scenarios(conn, 1)
        expected_cagr, diagnostic = web_server.calculate_probability_weighted_expected_cagr(scenarios, 100.0)
        self.assertEqual(source, "final_scenario_overlay")
        self.assertIsNone(diagnostic)
        self.assertAlmostEqual(expected_cagr, 15.0)

    def test_linear_rows_expose_dynamic_reserve_expected_cagr(self):
        settings = reserve_settings(
            action_min_cash_unallocated_target=0.0,
            linear_max_reserve_pct=0.0,
            linear_min_score_threshold=0.0,
            linear_max_single_stock_pct=100.0,
            action_min_executable_trade_amount=0.0,
        )
        candidate = {
            "symbol": "CAGR",
            "rating": "Buy",
            "expected_cagr": 99.0,
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
            "effective_scenarios": [
                scenario_for_cagr(10.0, probability=0.25, name="Bear"),
                scenario_for_cagr(20.0, probability=0.75, name="Bull"),
            ],
        }
        row = web_server.compute_linear_action_plan([candidate], 100_000.0, 100_000.0, settings)["rows"][0]
        self.assertIn("expected_equity_cagr", row)
        self.assertAlmostEqual(row["expected_equity_cagr"], 17.5)
        self.assertNotEqual(row["expected_equity_cagr"], row["expected_cagr"])
        self.assertEqual(row["effective_scenarios"], candidate["effective_scenarios"])

    def test_linear_rows_leave_dynamic_reserve_expected_cagr_missing_when_inputs_invalid(self):
        settings = reserve_settings(
            action_min_cash_unallocated_target=0.0,
            linear_max_reserve_pct=0.0,
            linear_min_score_threshold=0.0,
            action_min_executable_trade_amount=0.0,
        )
        base = {
            "rating": "Buy",
            "expected_cagr": 10.0,
            "upside": 50.0,
            "core_confidence_diff": 2.0,
            "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0,
            "core_bearish_confidence": 1.0,
            "potential_bullish_confidence": 7.0,
            "potential_bearish_confidence": 1.0,
            "current_position_weight": 0.0,
            "current_position_market_value": 0.0,
            "expected_price": 150.0,
        }
        missing_price = {**base, "symbol": "NO_PRICE", "current_price": None, "effective_scenarios": [scenario_for_cagr(10.0)]}
        missing_scenarios = {**base, "symbol": "NO_SCENARIOS", "current_price": 100.0, "effective_scenarios": []}
        rows = {
            row["symbol"]: row
            for row in web_server.compute_linear_action_plan([missing_price, missing_scenarios], 100_000.0, 100_000.0, settings)["rows"]
        }
        self.assertIsNone(rows["NO_PRICE"]["expected_equity_cagr"])
        self.assertIsNone(rows["NO_SCENARIOS"]["expected_equity_cagr"])


class LinearAbsoluteOpportunityTests(unittest.TestCase):
    def test_absolute_attractiveness_interpolates_and_clamps(self):
        expected = {
            5.0: 0.0,
            6.0: 0.0,
            7.0: 0.2,
            8.5: 0.5,
            10.0: 0.8,
            11.0: 1.0,
            15.0: 1.0,
            6.125: 0.025,
        }
        for expected_cagr, attractiveness in expected.items():
            with self.subTest(expected_cagr=expected_cagr):
                actual = web_server._linear_absolute_attractiveness(expected_cagr, 4.0, 2.0, 7.0)
                self.assertAlmostEqual(actual, attractiveness)

    def test_equal_threshold_compatibility_fallback_and_invalid_order(self):
        self.assertEqual(web_server._linear_absolute_attractiveness(6.9, 4.0, 3.0, 3.0), 0.0)
        self.assertEqual(web_server._linear_absolute_attractiveness(7.0, 4.0, 3.0, 3.0), 1.0)
        self.assertEqual(web_server._linear_absolute_attractiveness(20.0, 4.0, 7.0, 2.0), 0.0)

    def test_confidence_does_not_change_absolute_attractiveness(self):
        rows = []
        for symbol, bullish, bearish in (("HIGH", 10.0, 0.0), ("LOW", 1.0, 9.0)):
            rows.append({
                "symbol": symbol,
                "current_price": 100.0,
                "effective_scenarios": [scenario_for_cagr(8.5)],
                "pre_reserve_target_mid": 10.0,
                "core_bullish_confidence": bullish,
                "core_bearish_confidence": bearish,
            })
        web_server._linear_portfolio_opportunity_score(rows, reserve_settings())
        self.assertAlmostEqual(rows[0]["absolute_attractiveness"], 0.5)
        self.assertAlmostEqual(rows[1]["absolute_attractiveness"], 0.5)

    def test_weighted_opportunity_score_respects_target_midpoints(self):
        def row(symbol, weight, attractiveness_cagr):
            return {
                "symbol": symbol,
                "current_price": 100.0,
                "effective_scenarios": [scenario_for_cagr(attractiveness_cagr)],
                "pre_reserve_target_mid": weight,
            }

        equal = [row("A", 10.0, 6.0), row("B", 10.0, 8.5), row("C", 10.0, 11.0)]
        self.assertAlmostEqual(web_server._linear_portfolio_opportunity_score(equal, reserve_settings()), 0.5)

        unequal = [row("A", 5.0, 6.0), row("B", 10.0, 8.5), row("C", 20.0, 11.0)]
        self.assertAlmostEqual(web_server._linear_portfolio_opportunity_score(unequal, reserve_settings()), 25.0 / 35.0)

    def test_zero_weight_and_missing_cagr_handling(self):
        rows = [
            {
                "symbol": "VALID",
                "current_price": 100.0,
                "effective_scenarios": [scenario_for_cagr(11.0)],
                "pre_reserve_target_mid": 10.0,
            },
            {"symbol": "MISSING", "current_price": None, "effective_scenarios": [], "pre_reserve_target_mid": 10.0},
            {
                "symbol": "ZERO",
                "current_price": 100.0,
                "effective_scenarios": [scenario_for_cagr(6.0)],
                "pre_reserve_target_mid": 0.0,
            },
        ]
        score = web_server._linear_portfolio_opportunity_score(rows, reserve_settings())
        self.assertAlmostEqual(score, 0.5)
        self.assertEqual(rows[1]["absolute_attractiveness"], 0.0)
        self.assertTrue(rows[1]["absolute_attractiveness_diagnostic"])
        self.assertEqual(rows[2]["opportunity_weight"], 0.0)
        self.assertEqual(web_server._linear_portfolio_opportunity_score([], reserve_settings()), 0.0)


class LinearReserveAndScalingTests(unittest.TestCase):
    def test_dynamic_reserve_interpolation_and_clamping(self):
        expected = {1.0: 5.0, 0.8: 12.0, 0.5: 22.5, 0.0: 40.0}
        for score, reserve in expected.items():
            with self.subTest(score=score):
                self.assertAlmostEqual(web_server._linear_dynamic_reserve(score, 5.0, 40.0), reserve)
        self.assertEqual(web_server._linear_dynamic_reserve(2.0, 5.0, 40.0), 5.0)
        self.assertEqual(web_server._linear_dynamic_reserve(-1.0, 5.0, 40.0), 40.0)
        self.assertEqual(web_server._linear_dynamic_reserve(0.5, 50.0, 40.0), 50.0)

    def test_target_bands_scale_down_together_and_never_up(self):
        rows = [{
            "current_price": 100.0,
            "effective_scenarios": [scenario_for_cagr(11.0)],
            "pre_reserve_target_low": 80.0,
            "pre_reserve_target_mid": 100.0,
            "pre_reserve_target_high": 120.0,
        }]
        details = web_server._apply_linear_dynamic_reserve(
            rows,
            reserve_settings(action_min_cash_unallocated_target=30.0, linear_max_reserve_pct=30.0),
        )
        self.assertAlmostEqual(details["reserve_scale_factor"], 0.7)
        self.assertAlmostEqual(rows[0]["final_target_low"], 56.0)
        self.assertAlmostEqual(rows[0]["final_target_mid"], 70.0)
        self.assertAlmostEqual(rows[0]["final_target_high"], 84.0)

        unscaled = [{
            "current_price": 100.0,
            "effective_scenarios": [scenario_for_cagr(6.0)],
            "pre_reserve_target_low": 56.0,
            "pre_reserve_target_mid": 70.0,
            "pre_reserve_target_high": 84.0,
        }]
        details = web_server._apply_linear_dynamic_reserve(
            unscaled,
            reserve_settings(action_min_cash_unallocated_target=10.0, linear_max_reserve_pct=10.0),
        )
        self.assertEqual(details["reserve_scale_factor"], 1.0)
        self.assertEqual(unscaled[0]["final_target_mid"], 70.0)

    def test_relative_allocations_and_company_cap_survive_global_scaling(self):
        rows = [
            {
                "symbol": "A", "current_price": 100.0, "effective_scenarios": [scenario_for_cagr(8.5)],
                "pre_reserve_target_low": 32.0, "pre_reserve_target_mid": 40.0, "pre_reserve_target_high": 52.0,
            },
            {
                "symbol": "B", "current_price": 100.0, "effective_scenarios": [scenario_for_cagr(8.5)],
                "pre_reserve_target_low": 48.0, "pre_reserve_target_mid": 60.0, "pre_reserve_target_high": 78.0,
            },
        ]
        web_server._apply_linear_dynamic_reserve(
            rows,
            reserve_settings(action_min_cash_unallocated_target=30.0, linear_max_reserve_pct=30.0),
        )
        self.assertAlmostEqual(rows[1]["final_target_mid"] / rows[0]["final_target_mid"], 1.5)

        settings = reserve_settings(
            action_min_cash_unallocated_target=96.0,
            linear_max_reserve_pct=96.0,
            linear_allocated_target_total_pct=10.0,
            linear_min_score_threshold=0.0,
            linear_score_allocation_power=1.0,
            linear_max_single_stock_pct=100.0,
            linear_rating_bonus_enabled=False,
            hold_rating_penalty_enabled=False,
            core_confidence_penalty=0.0,
            upside_penalty=0.0,
            potential_confidence_penalty=0.0,
            action_min_executable_trade_amount=0.0,
        )
        candidate = {
            "symbol": "CAPPED", "rating": "Strong Buy", "expected_cagr": 20.0, "upside": 50.0,
            "core_confidence_diff": 2.0, "potential_confidence_diff": 1.5,
            "core_bullish_confidence": 8.0, "core_bearish_confidence": 8.0,
            "potential_bullish_confidence": 7.0, "potential_bearish_confidence": 1.0,
            "current_position_weight": 0.0, "current_position_market_value": 0.0,
            "current_price": 100.0, "expected_price": 150.0,
            "effective_scenarios": [scenario_for_cagr(20.0)],
        }
        row = web_server.compute_linear_action_plan([candidate], 100_000.0, 100_000.0, settings)["rows"][0]
        self.assertAlmostEqual(row["pre_reserve_target_mid"], 5.0)
        self.assertTrue(row["bearish_cap_applied"])
        self.assertAlmostEqual(row["reserve_scale_factor"], 0.8)
        self.assertAlmostEqual(row["final_target_mid"], 4.0)
        self.assertAlmostEqual(row["position_gap_to_mid"], 4.0)
        self.assertAlmostEqual(row["target_gap_amount"], 4_000.0)

    def test_configuration_validation(self):
        with self.assertRaisesRegex(ValueError, "linear_max_reserve_pct"):
            web_server.validate_action_plan_settings(reserve_settings(
                action_min_cash_unallocated_target=50.0,
                linear_max_reserve_pct=40.0,
            ))
        with self.assertRaisesRegex(ValueError, "greater than"):
            web_server.validate_action_plan_settings(reserve_settings(
                linear_min_equity_excess_cagr_pct=7.0,
                linear_full_attractiveness_equity_excess_cagr_pct=7.0,
            ))
        with self.assertRaisesRegex(ValueError, "finite"):
            web_server.validate_action_plan_settings(reserve_settings(
                linear_reserve_benchmark_yield_pct=math.nan,
            ))


class LinearReserveFundingTests(unittest.TestCase):
    @staticmethod
    def row(action, raw_amount, price, direction, **extra):
        return {
            "symbol": extra.pop("symbol", action),
            "action": action,
            "raw_action_amount": raw_amount,
            "target_gap_amount": raw_amount,
            "action_amount": raw_amount,
            "action_amount_direction": direction,
            "current_price": price,
            "current_position_market_value": extra.pop("current_position_market_value", 30_000.0),
            "owned_share_quantity": extra.pop("owned_share_quantity", 100),
            "linear_allocation_score": extra.pop("linear_allocation_score", 0.8),
            "linear_expected_cagr_score": extra.pop("linear_expected_cagr_score", 0.8),
            "linear_core_net_score": extra.pop("linear_core_net_score", 0.8),
            **extra,
        }

    def test_trim_proceeds_fill_reserve_before_whole_share_add_funding(self):
        trim = self.row("Trim", 15_550.0, 300.0, "trim", symbol="TRIM")
        add = self.row("Add", 20_000.0, 100.0, "add", symbol="ADD")
        summary = web_server._apply_linear_cash_constrained_execution_layer(
            [trim, add],
            100_000.0,
            20_000.0,
            reserve_settings(action_min_cash_unallocated_target=5.0),
            dynamic_reserve_pct=25.0,
        )
        self.assertEqual(summary["executable_sell_trim_proceeds"], 15_300.0)
        self.assertEqual(summary["target_reserve_amount"], 25_000.0)
        self.assertEqual(summary["cash_available_for_linear_buys"], 10_300.0)
        self.assertEqual(add["suggested_share_count"], 103)
        self.assertEqual(add["executable_action_amount"], 10_300.0)
        self.assertAlmostEqual(summary["total_add_demand"], summary["funded_add_amount"] + summary["unfunded_add_demand"])

    def test_reserve_shortfall_blocks_adds(self):
        trim = self.row("Trim", 15_550.0, 300.0, "trim", symbol="TRIM")
        add = self.row("Add", 5_000.0, 100.0, "add", symbol="ADD")
        summary = web_server._apply_linear_cash_constrained_execution_layer(
            [trim, add],
            100_000.0,
            5_000.0,
            reserve_settings(),
            dynamic_reserve_pct=25.0,
        )
        self.assertEqual(summary["available_buy_budget"], 0.0)
        self.assertEqual(summary["reserve_shortfall"], 4_700.0)
        self.assertEqual(add["action"], "Watch")
        self.assertEqual(add["desired_action"], "Add")
        self.assertEqual(add["executable_action"], "Watch")
        self.assertEqual(add["suggested_share_count"], 0)
        self.assertEqual(add["action_amount"], 0.0)
        self.assertEqual(add["action_amount_label"], "—")
        self.assertEqual(add["action_amount_direction"], "none")
        self.assertEqual(add["funding_status"], "Unfunded / Watch")

    def test_bucket_calculation_is_unchanged_by_linear_reserve_settings(self):
        raw_targets = {"Strong Buy": 35.0, "Buy": 30.0, "Speculative Buy": 15.0, "Hold": 10.0}
        baseline = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        with_reserve = reserve_settings(linear_max_reserve_pct=75.0)
        baseline_result = web_server._compress_action_plan_bucket_targets(raw_targets, baseline)
        reserve_result = web_server._compress_action_plan_bucket_targets(raw_targets, with_reserve)
        self.assertEqual(baseline_result, reserve_result)


if __name__ == "__main__":
    unittest.main()
