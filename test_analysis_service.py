import unittest

from analysis_service import (
    AnalysisValidationError,
    calculate_confidence_breakdown,
    calculate_expected_price,
    calculate_overall_confidence,
    calculate_upside,
    parse_analysis_payload,
)


def build_valid_payload():
    return {
        "symbol": "nbis",
        "assumptions": "Concise assumptions.",
        "scenarios": [
            {"name": "Bear", "price_low": 40, "price_high": 80, "cagr_low": -10, "cagr_high": -2, "probability": 25},
            {"name": "Base", "price_low": 200, "price_high": 350, "cagr_low": 10, "cagr_high": 20, "probability": 50},
            {"name": "Bull", "price_low": 500, "price_high": 900, "cagr_low": 30, "cagr_high": 50, "probability": 25},
        ],
        "key_variables": [
            {"variable": "Demand", "type": "Bullish", "confidence": 9, "importance": 10},
            {"variable": "Pricing", "type": "Bullish", "confidence": 8, "importance": 9},
            {"variable": "Competition", "type": "Bearish", "confidence": 6, "importance": 8},
            {"variable": "Capex", "type": "Bearish", "confidence": 7, "importance": 7},
            {"variable": "Margins", "type": "Bullish", "confidence": 8, "importance": 8},
            {"variable": "Regulation", "type": "Bearish", "confidence": 5, "importance": 6},
        ],
    }


class AnalysisServiceTests(unittest.TestCase):
    def test_parse_payload_and_probability_normalization(self):
        payload = build_valid_payload()
        parsed = parse_analysis_payload(payload)
        self.assertEqual(parsed["symbol"], "NBIS")
        self.assertAlmostEqual(parsed["scenarios"][0]["probability"], 0.25)
        self.assertNotIn("cagr_low", parsed["scenarios"][0])
        self.assertNotIn("cagr_high", parsed["scenarios"][0])


    def test_parse_payload_accepts_scenarios_without_cagr_fields(self):
        payload = build_valid_payload()
        for scenario in payload["scenarios"]:
            scenario.pop("cagr_low", None)
            scenario.pop("cagr_high", None)
        parsed = parse_analysis_payload(payload)
        self.assertEqual([s["scenario_name"] for s in parsed["scenarios"]], ["Bear", "Base", "Bull"])
        self.assertNotIn("cagr_low", parsed["scenarios"][0])

    def test_parse_payload_invalid_scenarios(self):
        payload = build_valid_payload()
        payload["scenarios"] = [
            {"name": "Bear", "price_low": 1, "price_high": 2, "cagr_low": 1, "cagr_high": 2, "probability": 100}
        ]
        with self.assertRaises(AnalysisValidationError):
            parse_analysis_payload(payload)

    def test_expected_price(self):
        scenarios = [
            {"price_low": 40, "price_high": 80, "probability": 0.25},
            {"price_low": 200, "price_high": 350, "probability": 0.50},
            {"price_low": 500, "price_high": 900, "probability": 0.25},
        ]
        expected_price = calculate_expected_price(scenarios)
        self.assertAlmostEqual(expected_price, 327.5)

    def test_upside(self):
        self.assertAlmostEqual(calculate_upside(120, 100), 20.0)
        self.assertIsNone(calculate_upside(120, None))

    def test_overall_confidence(self):
        key_variables = [
            {"confidence": 9, "importance": 10},
            {"confidence": 4, "importance": 5},
        ]
        self.assertAlmostEqual(calculate_overall_confidence(key_variables), (9 * 10 + 4 * 5) / 15)
        self.assertIsNone(calculate_overall_confidence([]))


    def test_confidence_breakdown_separates_core_and_potential_drivers(self):
        key_variables = [
            {"variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8, "importance": 3},
            {"variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 6, "importance": 1},
            {"variable_type": "Bearish", "driver_category": "Core Driver", "confidence": 5, "importance": 2},
            {"variable_type": "Bullish", "driver_category": "Potential Driver", "confidence": 4, "importance": 4},
            {"variable_type": "Bearish", "driver_category": "Potential Driver", "confidence": 3, "importance": 2},
        ]
        breakdown = calculate_confidence_breakdown(key_variables)
        self.assertAlmostEqual(breakdown["core_bullish_confidence"], 7.5)
        self.assertAlmostEqual(breakdown["core_bearish_confidence"], 5.0)
        self.assertAlmostEqual(breakdown["core_confidence_diff"], 2.5)
        self.assertAlmostEqual(breakdown["potential_bullish_confidence"], 4.0)
        self.assertAlmostEqual(breakdown["potential_bearish_confidence"], 3.0)
        self.assertAlmostEqual(breakdown["potential_confidence_diff"], 1.0)

    def test_confidence_breakdown_defaults_missing_or_invalid_category_to_core(self):
        key_variables = [
            {"variable_type": "Bullish", "confidence": 8, "importance": 2},
            {"variable_type": "Bearish", "driver_category": "Invalid", "confidence": 5, "importance": 3},
        ]
        breakdown = calculate_confidence_breakdown(key_variables)
        self.assertEqual(breakdown["core_bullish_confidence"], 8)
        self.assertEqual(breakdown["core_bearish_confidence"], 5)
        self.assertIsNone(breakdown["potential_bullish_confidence"])
        self.assertIsNone(breakdown["potential_bearish_confidence"])
        self.assertIsNone(breakdown["potential_confidence_diff"])

    def test_key_variables_default_missing_driver_category_to_core_driver(self):
        payload = build_valid_payload()
        parsed = parse_analysis_payload(payload)
        self.assertTrue(parsed["key_variables"])
        self.assertTrue(all(item["driver_category"] == "Core Driver" for item in parsed["key_variables"]))

    def test_key_variables_accept_potential_driver_category(self):
        payload = build_valid_payload()
        payload["key_variables"][0]["driver_category"] = "Potential Driver"
        parsed = parse_analysis_payload(payload)
        self.assertEqual(parsed["key_variables"][0]["driver_category"], "Potential Driver")

    def test_key_variables_reject_invalid_driver_category(self):
        payload = build_valid_payload()
        payload["key_variables"][0]["driver_category"] = "Emerging"
        with self.assertRaises(AnalysisValidationError):
            parse_analysis_payload(payload)

    def test_key_variables_more_than_previous_max_allowed(self):
        payload = build_valid_payload()
        payload["key_variables"].extend([
            {"variable": "Execution", "type": "Bullish", "confidence": 7, "importance": 6},
            {"variable": "Retention", "type": "Bullish", "confidence": 8, "importance": 7},
            {"variable": "Supply chain", "type": "Bearish", "confidence": 5, "importance": 5},
        ])
        parsed = parse_analysis_payload(payload)
        self.assertEqual(len(parsed["key_variables"]), 9)
    def test_key_variables_minimum_count_enforced(self):
        payload = build_valid_payload()
        payload["key_variables"] = payload["key_variables"][:5]
        with self.assertRaises(AnalysisValidationError):
            parse_analysis_payload(payload)

    def test_confidence_and_importance_must_be_integers(self):
        payload = build_valid_payload()
        payload["key_variables"][0]["confidence"] = 9.5
        with self.assertRaises(AnalysisValidationError):
            parse_analysis_payload(payload)

        payload = build_valid_payload()
        payload["key_variables"][0]["importance"] = 4.2
        with self.assertRaises(AnalysisValidationError):
            parse_analysis_payload(payload)


if __name__ == "__main__":
    unittest.main()
