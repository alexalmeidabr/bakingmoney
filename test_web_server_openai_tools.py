import unittest
from unittest import mock

import web_server


class OpenAIToolsTests(unittest.TestCase):
    def test_build_openai_tools_includes_web_search(self):
        tools = web_server.build_openai_tools()
        self.assertIsInstance(tools, list)
        self.assertGreaterEqual(len(tools), 1)
        self.assertEqual(tools[0].get("type"), "web_search")

    def test_build_openai_request_body_includes_tools(self):
        schema = {"name": "x", "schema": {"type": "object", "properties": {}, "required": []}}
        body = web_server.build_openai_request_body(
            prompt_text="hello",
            json_schema=schema,
            reasoning_effort="medium",
            supports_temperature=True,
            temperature=0.2,
        )
        self.assertIn("tools", body)
        self.assertEqual(body["tools"][0]["type"], "web_search")

    def test_unsupported_web_tool_detector(self):
        self.assertTrue(web_server._looks_like_unsupported_web_tool_error("Invalid tool type web_search_preview"))
        self.assertFalse(web_server._looks_like_unsupported_web_tool_error("Rate limit exceeded"))


if __name__ == "__main__":
    unittest.main()


class ScenarioPromptRenderingTests(unittest.TestCase):
    def test_render_scenario_prompt_substitutes_supported_placeholders_without_injecting_summary(self):
        template = """Symbol: $Symbol\nCompany: $CompanyName\nPrice: $Price\nBusiness: $BusinessModel\nKey Variables: $KeyVariables"""
        rendered = web_server.render_scenario_prompt(
            template,
            {
                "$Symbol": "NBIS",
                "$CompanyName": "Nebius",
                "$Price": "50.25",
                "$BusinessModel": "Cloud infrastructure",
                "$KeyVariables": "[{\"variable\":\"Demand\"}]",
                "$Summary": "Should not be injected",
            },
        )

        self.assertIn("Symbol: NBIS", rendered)
        self.assertIn("Company: Nebius", rendered)
        self.assertIn("Price: 50.25", rendered)
        self.assertIn("Business: Cloud infrastructure", rendered)
        self.assertIn('Key Variables: [{"variable":"Demand"}]', rendered)
        self.assertNotIn("Summary:", rendered)

    @mock.patch.object(web_server, "OPENAI_API_KEY", "test-key")
    def test_request_ai_analysis_exposes_exact_scenario_prompt_used_for_generation(self):
        templates = {
            web_server.ANALYSIS_PROMPT_SETTING_KEY_BUSINESS_MODEL: "BM prompt for $Symbol",
            web_server.ANALYSIS_PROMPT_SETTING_KEY_KEY_VARIABLES: "KV prompt $BusinessModel",
            web_server.ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS: "Scenario prompt\nSymbol:$Symbol\nBusiness:$BusinessModel\nVars:$KeyVariables",
        }
        sources = {k: "saved" for k in templates.keys()}
        key_variables = [
            {"variable": "Demand", "type": "Bullish", "confidence": 8, "importance": 9},
            {"variable": "Pricing", "type": "Bullish", "confidence": 7, "importance": 8},
            {"variable": "Margins", "type": "Bullish", "confidence": 6, "importance": 7},
            {"variable": "Competition", "type": "Bearish", "confidence": 5, "importance": 6},
            {"variable": "Capex", "type": "Bearish", "confidence": 4, "importance": 5},
            {"variable": "Execution", "type": "Bearish", "confidence": 3, "importance": 4},
        ]

        captured = {}

        def fake_request_ai_step(step_name, prompt_text, _schema):
            if step_name == "business_model":
                return {
                    "symbol": "NBIS",
                    "company_name": "Nebius",
                    "business_model": "Core business model",
                    "business_summary": "This summary must not be auto-injected",
                }
            if step_name == "key_variables":
                return {"symbol": "NBIS", "key_variables": key_variables}
            raise AssertionError(f"Unexpected step: {step_name}")

        def fake_generate_scenarios_multi_pass(**kwargs):
            captured["prompt_text"] = kwargs["prompt_text"]
            return (
                {
                    "assumptions": "assume",
                    "scenarios": [
                        {"scenario_name": "Bear", "price_low": 10, "price_high": 20, "cagr_low": -5, "cagr_high": 0, "probability": 0.2},
                        {"scenario_name": "Base", "price_low": 20, "price_high": 30, "cagr_low": 0, "cagr_high": 5, "probability": 0.6},
                        {"scenario_name": "Bull", "price_low": 30, "price_high": 40, "cagr_low": 5, "cagr_high": 10, "probability": 0.2},
                    ],
                },
                [
                    {
                        "pass_index": 1,
                        "raw_response_text": "{}",
                        "parsed_json": {},
                        "validation_status": "accepted",
                        "rejection_reason": None,
                        "quality_score": 1.0,
                        "is_outlier": False,
                        "created_at": "2025-01-01T00:00:00Z",
                    }
                ],
            )

        class DummyConn:
            def close(self):
                return None

        with mock.patch.object(web_server, "resolve_company_profile_from_tws", return_value={"company_name": "Nebius"}), \
             mock.patch.object(web_server, "get_db_connection", return_value=DummyConn()), \
             mock.patch.object(web_server, "get_all_prompt_templates", return_value=(templates, sources)), \
             mock.patch.object(web_server, "get_scenario_generation_config", return_value={"scenario_multi_pass_enabled": False, "scenario_pass_count": 1, "scenario_outlier_filter_enabled": True}), \
             mock.patch.object(web_server, "request_ai_step", side_effect=fake_request_ai_step), \
             mock.patch.object(web_server, "generate_scenarios_multi_pass", side_effect=fake_generate_scenarios_multi_pass), \
             mock.patch.object(web_server, "validate_step3_scenarios", side_effect=lambda payload, symbol, kv: {
                 "symbol": symbol,
                 "assumptions": payload["assumptions"],
                 "scenarios": [
                     {"scenario_name": s["name"], "price_low": s["price_low"], "price_high": s["price_high"], "cagr_low": s["cagr_low"], "cagr_high": s["cagr_high"], "probability": s["probability"]}
                     for s in payload["scenarios"]
                 ],
                 "key_variables": kv,
             }), \
             mock.patch.object(web_server, "get_scenario_probability_settings", return_value={
                 "probability_source_mode": "hybrid",
                 "hybrid_ai_weight": 0.7,
                 "hybrid_backend_weight": 0.3,
                 "backend_base_max_probability": 60.0,
                 "backend_base_min_probability": 35.0,
             }):
            result = web_server.request_ai_analysis("NBIS", current_price=50.25)

        expected_prompt = web_server.build_scenario_generation_prompt(
            "NBIS",
            50.25,
            template=templates[web_server.ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS],
            company_name="Nebius",
            business_model="Core business model",
            key_variables=result["key_variables"],
        )

        self.assertEqual(expected_prompt, captured["prompt_text"])
        self.assertEqual(expected_prompt, result["raw"]["step3_prompt"])
        self.assertNotIn("Summary:", captured["prompt_text"])
