import unittest
from unittest import mock

import web_server


class LinearActionPlanDetailTests(unittest.TestCase):
    def setUp(self):
        self.settings = dict(web_server.ACTION_PLAN_DEFAULT_SETTINGS)
        self.settings.update({
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
        self.base_candidate = {
            "symbol": "NU_FIXTURE",
            "company_name": "Linear Fixture",
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
            "owned_share_quantity": 0,
            "current_price": 100.0,
            "expected_price": 150.0,
            "extension_risk": 1.0,
            "effective_scenarios": [
                {"scenario_name": "Base", "price_low": 140.0, "price_high": 160.0, "probability": 1.0},
            ],
        }

    def calculate(self, **overrides):
        candidate = dict(self.base_candidate)
        candidate.update(overrides)
        return web_server.compute_linear_action_plan(
            [candidate], 100_000.0, 100_000.0, self.settings,
        )

    def detail_for(self, calculated, symbol="NU_FIXTURE"):
        payload = {
            "linear_action_plan": calculated["rows"],
            "action_plan": [{"symbol": symbol, "action": "Strong Trim", "target_weight_mid": 2.0}],
            "summary": {"linear_summary": calculated["summary"]},
        }
        return web_server.build_linear_action_plan_detail(payload, symbol)

    def test_detail_uses_exact_linear_row_not_legacy_bucket_row(self):
        calculated = self.calculate()
        table_row = calculated["rows"][0]
        detail = self.detail_for(calculated)

        self.assertEqual(table_row["action"], "Add")
        self.assertEqual(detail["detail_source"], "linear_action_plan")
        for key in (
            "action",
            "target_weight_low",
            "target_weight_mid",
            "target_weight_high",
            "current_position_weight",
            "target_gap_amount",
            "action_amount",
            "executable_action_amount",
            "suggested_share_count",
            "funding_status",
            "linear_allocation_score",
        ):
            with self.subTest(key=key):
                self.assertEqual(detail[key], table_row[key])
        self.assertNotIn(detail["action"], {"Strong Add", "Starter Buy", "Strong Trim", "Trim"})

    def test_detail_endpoint_selects_the_linear_collection(self):
        calculated = self.calculate()
        payload = {
            "linear_action_plan": calculated["rows"],
            "action_plan": [{"symbol": "NU_FIXTURE", "action": "Strong Trim"}],
            "summary": {"linear_summary": calculated["summary"]},
        }
        with (
            mock.patch.object(web_server, "build_action_plan", return_value=payload),
            mock.patch.object(web_server, "get_analysis_detail", return_value=None),
        ):
            detail = web_server.get_action_plan_detail(object(), "nu_fixture")
        self.assertEqual(detail["action"], calculated["rows"][0]["action"])
        self.assertEqual(detail["detail_source"], "linear_action_plan")

    def test_linear_detail_covers_base_actions_and_guardrails(self):
        cases = (
            ("Add", {}, "Add"),
            ("Hold", {"current_position_weight": 10.0, "current_position_market_value": 10_000.0, "owned_share_quantity": 100}, "Hold"),
            ("Trim", {"current_position_weight": 20.0, "current_position_market_value": 20_000.0, "owned_share_quantity": 200}, "Trim"),
            ("Sell", {"rating": "Sell", "current_position_weight": 10.0, "current_position_market_value": 10_000.0, "owned_share_quantity": 100}, "Sell"),
            ("Watch / Rating Guardrail", {"rating": "Hold"}, "Watch / Rating Guardrail"),
            ("Watch / Extended", {"extension_risk": 4.5}, "Watch / Extended"),
        )
        for label, overrides, expected in cases:
            with self.subTest(label=label):
                calculated = self.calculate(**overrides)
                row = calculated["rows"][0]
                detail = self.detail_for(calculated)
                self.assertEqual(row["action"], expected)
                self.assertEqual(detail["action"], expected)
                self.assertEqual(detail["linear_explanation"], row["linear_explanation"])

    def test_unfunded_add_is_same_watch_result_in_row_and_detail(self):
        calculated = web_server.compute_linear_action_plan(
            [dict(self.base_candidate)], 100_000.0, 0.0, self.settings,
        )
        row = calculated["rows"][0]
        detail = self.detail_for(calculated)
        self.assertEqual(row["desired_action"], "Add")
        self.assertEqual(row["action"], "Watch")
        self.assertEqual(detail["action"], "Watch")
        self.assertEqual(detail["funding_status"], "Unfunded / Watch")
        self.assertIn("no executable Add", detail["linear_explanation"])

    def test_detail_payload_excludes_legacy_trigger_and_bucket_diagnostics(self):
        detail = self.detail_for(self.calculate())
        obsolete_trigger_keys = {
            "trigger_price",
            "trigger_direction",
            "relevant_trigger_price",
            "relevant_trigger_type",
            "distance_to_trigger_percent",
            "distance_to_relevant_trigger_percent",
            "distance_to_relevant_trigger_label",
            "trigger_breakdown",
        }
        self.assertTrue(obsolete_trigger_keys.isdisjoint(detail))

        def all_keys(value):
            if isinstance(value, dict):
                for key, nested in value.items():
                    yield key
                    yield from all_keys(nested)
            elif isinstance(value, list):
                for nested in value:
                    yield from all_keys(nested)

        for key in all_keys(detail):
            normalized = key.casefold()
            self.assertNotIn("bucket", normalized)
            self.assertNotIn("weighted_count", normalized)
            self.assertNotIn("bucket_sizing", normalized)

    def test_detail_exposes_current_score_target_cap_reserve_and_execution_diagnostics(self):
        calculated = self.calculate()
        row = calculated["rows"][0]
        detail = self.detail_for(calculated)
        target = detail["linear_target_breakdown"]
        score = detail["linear_score_breakdown"]

        self.assertEqual(target["linear_score"], row["linear_allocation_score"])
        self.assertEqual(target["target_before_caps"], row["linear_target_mid_before_caps"])
        self.assertEqual(target["target_after_cap_mid"], row["pre_reserve_target_mid"])
        self.assertEqual(target["reserve_scale_factor"], row["reserve_scale_factor"])
        self.assertEqual(target["final_target_mid"], row["target_weight_mid"])
        self.assertEqual(detail["linear_add_band_tolerance_pct"], row["linear_add_band_tolerance_pct"])
        self.assertEqual(detail["linear_trim_band_tolerance_pct"], row["linear_trim_band_tolerance_pct"])
        self.assertFalse(target["cap_applied"])
        self.assertEqual(target["cap_reason"], "—")
        self.assertEqual(score["linear_score"], row["linear_allocation_score"])
        self.assertEqual(score["upside_score"], row["linear_upside_score"])
        self.assertEqual(score["weights_used"], row["linear_weights_used"])
        self.assertIn("whole_share_minimum", detail["guardrails"])

    def test_current_linear_cap_diagnostics_flow_into_detail(self):
        self.settings.update({
            "linear_enable_risk_caps": True,
            "linear_max_single_stock_pct": 5.0,
        })
        calculated = self.calculate()
        row = calculated["rows"][0]
        detail = self.detail_for(calculated)
        target = detail["linear_target_breakdown"]
        self.assertGreater(row["linear_cap_applied"], 0.0)
        self.assertTrue(target["cap_applied"])
        self.assertEqual(target["cap_amount"], row["linear_cap_applied"])
        self.assertEqual(target["cap_reason"], row["linear_cap_reason"])
        self.assertEqual(target["target_after_cap_mid"], row["pre_reserve_target_mid"])
        self.assertEqual(target["final_target_mid"], row["target_weight_mid"])


if __name__ == "__main__":
    unittest.main()
