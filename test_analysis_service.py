import unittest

from analysis_service import (
    AnalysisValidationError,
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
