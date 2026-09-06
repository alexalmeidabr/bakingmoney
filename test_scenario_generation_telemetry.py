import json
import os
import tempfile
import unittest
from unittest import mock

import web_server


class FakeOpenAIResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def scenario_payload():
    return {
        "assumptions": "Demand expands while execution risk remains manageable.",
        "scenarios": [
            {"name": "Bear", "price_low": 10, "price_high": 20, "probability": 20},
            {"name": "Base", "price_low": 20, "price_high": 30, "probability": 60},
            {"name": "Bull", "price_low": 30, "price_high": 40, "probability": 20},
        ],
    }


def stored_scenarios():
    return [
        {"scenario_name": "Bear", "price_low": 10, "price_high": 20, "probability": 0.2},
        {"scenario_name": "Base", "price_low": 20, "price_high": 30, "probability": 0.6},
        {"scenario_name": "Bull", "price_low": 30, "price_high": 40, "probability": 0.2},
    ]


def core_evidence_pack():
    return {
        "symbol": "TEST",
        "as_of": "2026-09-06",
        "reporting_context": {
            "latest_reporting_period": "Q2 2026",
            "latest_release_date": "2026-08-01",
            "facts": ["Revenue increased year over year."],
        },
        "guidance": {"facts": ["Management reiterated full-year guidance."]},
        "key_variable_evidence": [
            {
                "key_variable": "Demand",
                "driver_category": "Core Driver",
                "evidence_status": "Confirms",
                "facts": ["Demand remained above prior-year levels."],
            }
        ],
        "other_material_facts": ["The company announced a material customer expansion."],
        "valuation_context": ["Net cash remained positive."],
        "sources": [
            {
                "title": "Q2 2026 earnings release",
                "date": "2026-08-01",
                "source_type": "Company IR",
                "url": "https://example.com/release",
            }
        ],
    }


def key_variables():
    return [
        {"variable_text": "Demand", "variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8.0, "importance": 9.0},
        {"variable_text": "Competition", "variable_type": "Bearish", "driver_category": "Core Driver", "confidence": 4.0, "importance": 7.0},
    ]


class ScenarioGenerationTelemetryTests(unittest.TestCase):
    def test_core_evidence_prompt_is_configured_with_expected_placeholders(self):
        config = web_server.PROMPT_TEMPLATE_CONFIG[web_server.ANALYSIS_PROMPT_SETTING_KEY_CORE_EVIDENCE_PACK]
        self.assertEqual(config["default"], web_server.DEFAULT_PROMPT_CORE_EVIDENCE_PACK)
        self.assertIn("$Symbol", config["required_vars"])
        self.assertIn("$CompanyName", config["required_vars"])
        self.assertIn("$Price", config["default"])
        self.assertIn("$Price", config["required_vars"])
        self.assertIn("$BusinessModel", config["required_vars"])
        self.assertIn("$KeyVariables", config["required_vars"])
        self.assertIn("$CoreEvidencePack", web_server.PROMPT_TEMPLATE_CONFIG[web_server.ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS]["required_vars"])

    def test_core_evidence_schema_is_strict_and_restricts_status_enum(self):
        schema = web_server.build_core_evidence_schema()["schema"]
        self.assertFalse(schema["additionalProperties"])
        evidence_schema = schema["properties"]["key_variable_evidence"]["items"]
        self.assertFalse(evidence_schema["additionalProperties"])
        self.assertEqual(
            evidence_schema["properties"]["evidence_status"]["enum"],
            list(web_server.CORE_EVIDENCE_STATUSES),
        )

    def test_validate_core_evidence_pack_rejects_invalid_status(self):
        payload = core_evidence_pack()
        payload["key_variable_evidence"][0]["evidence_status"] = "Bullish interpretation"
        with self.assertRaises(web_server.AnalysisValidationError):
            web_server.validate_core_evidence_pack(payload, "TEST")

    def test_scenario_prompt_inserts_readable_core_evidence_pack_json(self):
        prompt = web_server.build_scenario_generation_prompt(
            "TEST",
            20,
            template="Symbol $Symbol\nEvidence:\n$CoreEvidencePack",
            company_name="Test Co",
            business_model="Business",
            key_variables=key_variables(),
            core_evidence_pack=core_evidence_pack(),
        )

        self.assertIn('"as_of": "2026-09-06"', prompt)
        self.assertIn('"driver_category": "Core Driver"', prompt)
        self.assertNotIn("None", prompt)
        self.assertNotIn("undefined", prompt)

    def test_all_scenario_passes_receive_identical_core_evidence_content(self):
        pack = core_evidence_pack()
        prompt = web_server.build_scenario_generation_prompt(
            "TEST",
            20,
            template="Evidence:\n$CoreEvidencePack",
            company_name="Test Co",
            business_model="Business",
            key_variables=key_variables(),
            core_evidence_pack=pack,
        )
        prompts = []

        def fake_request(_step_name, prompt_text, _json_schema, attempt=1, model=None, reasoning_effort=None):
            prompts.append(prompt_text)
            return scenario_payload(), {
                "step_name": _step_name,
                "model": model or "gpt-5.6-terra",
                "reasoning_effort": reasoning_effort or "low",
                "status": "completed",
            }

        with mock.patch.object(web_server, "request_ai_step_with_telemetry", side_effect=fake_request):
            web_server.generate_scenarios_multi_pass(
                symbol="TEST",
                key_variables=key_variables(),
                prompt_text=prompt,
                pass_count=3,
                outlier_filter_enabled=False,
                current_price=20,
            )

        self.assertEqual(len(prompts), 3)
        self.assertEqual(prompts[0], prompts[1])
        self.assertEqual(prompts[1], prompts[2])
        self.assertIn('"sources": [', prompts[0])

    def test_missing_core_evidence_pack_is_not_silently_rendered_for_scenarios(self):
        with self.assertRaises(web_server.AnalysisValidationError):
            web_server.serialize_core_evidence_pack_for_prompt(None)

    def test_core_evidence_model_overrides_only_core_evidence_generation(self):
        captured = {}

        def fake_request(step_name, prompt_text, json_schema, attempt=1, model=None, reasoning_effort=None):
            captured["step_name"] = step_name
            captured["model"] = model
            captured["reasoning_effort"] = reasoning_effort
            return core_evidence_pack(), {
                "step_name": step_name,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "status": "completed",
                "input_tokens": 10,
                "cached_input_tokens": 2,
                "cache_write_tokens": 1,
                "output_tokens": 5,
                "reasoning_tokens": 3,
                "total_tokens": 15,
                "web_search_call_count": 1,
                "retry_count": 0,
                "duration_ms": 100,
            }

        with mock.patch.object(web_server, "OPENAI_MODEL", "gpt-5.6-terra"), \
             mock.patch.object(web_server, "OPENAI_REASONING_EFFORT", "low"), \
             mock.patch.object(web_server, "OPENAI_CORE_EVIDENCE_MODEL", "gpt-5.6-luna"), \
             mock.patch.object(web_server, "OPENAI_CORE_EVIDENCE_REASONING_EFFORT", "medium"), \
             mock.patch.object(web_server, "request_ai_step_with_telemetry", side_effect=fake_request):
            result = web_server.generate_core_evidence_pack(
                "TEST",
                20,
                "Test Co",
                "Business",
                "Summary",
                key_variables(),
                web_server.DEFAULT_PROMPT_CORE_EVIDENCE_PACK,
            )

        self.assertEqual(captured["step_name"], "core_evidence_pack")
        self.assertEqual(captured["model"], "gpt-5.6-luna")
        self.assertEqual(captured["reasoning_effort"], "medium")
        self.assertEqual(result["model"], "gpt-5.6-luna")

    def test_core_evidence_model_falls_back_to_scenario_model(self):
        with mock.patch.object(web_server, "OPENAI_MODEL", "gpt-5.6-terra"), \
             mock.patch.object(web_server, "OPENAI_REASONING_EFFORT", "low"), \
             mock.patch.object(web_server, "OPENAI_CORE_EVIDENCE_MODEL", ""), \
             mock.patch.object(web_server, "OPENAI_CORE_EVIDENCE_REASONING_EFFORT", ""):
            self.assertEqual(web_server.resolve_core_evidence_model(), "gpt-5.6-terra")
            self.assertEqual(web_server.resolve_core_evidence_reasoning_effort(), "low")

    def test_extract_openai_usage_telemetry_uses_available_responses_usage_fields(self):
        raw = {
            "usage": {
                "input_tokens": 1200,
                "input_tokens_details": {"cached_tokens": 400, "cache_write_tokens": 125},
                "output_tokens": 300,
                "output_tokens_details": {"reasoning_tokens": 90},
                "total_tokens": 1500,
            }
        }

        self.assertEqual(
            web_server.extract_openai_usage_telemetry(raw),
            {
                "input_tokens": 1200,
                "cached_input_tokens": 400,
                "cache_write_tokens": 125,
                "output_tokens": 300,
                "reasoning_tokens": 90,
                "total_tokens": 1500,
            },
        )

    def test_count_openai_web_search_calls_counts_output_tool_calls_once(self):
        raw = {
            "output": [
                {"type": "message", "content": [{"type": "output_text", "text": "{}"}]},
                {"type": "web_search_call", "id": "ws_1"},
                {"type": "tool_call", "name": "web_search_preview", "id": "ws_2"},
            ]
        }

        self.assertEqual(web_server.count_openai_web_search_calls(raw), 2)

    def test_generate_scenarios_multi_pass_attaches_telemetry_to_each_pass(self):
        telemetry = [
            {"model": "gpt-5-mini", "reasoning_effort": "medium", "input_tokens": 100, "output_tokens": 20, "total_tokens": 120, "duration_ms": 250, "retry_count": 0, "web_search_call_count": 1},
            {"model": "gpt-5-mini", "reasoning_effort": "medium", "input_tokens": 110, "output_tokens": 25, "total_tokens": 135, "duration_ms": 300, "retry_count": 1, "web_search_call_count": 0},
            {"model": "gpt-5-mini", "reasoning_effort": "medium", "input_tokens": 120, "output_tokens": 30, "total_tokens": 150, "duration_ms": 350, "retry_count": 0, "web_search_call_count": 1},
        ]

        with mock.patch.object(
            web_server,
            "request_ai_step_with_telemetry",
            side_effect=[(scenario_payload(), dict(item)) for item in telemetry],
        ):
            _aggregated, runs = web_server.generate_scenarios_multi_pass(
                symbol="TEST",
                key_variables=[],
                prompt_text="Build scenarios",
                pass_count=3,
                outlier_filter_enabled=False,
                current_price=20,
            )

        self.assertEqual(len(runs), 3)
        self.assertEqual([run["telemetry"]["pass_number"] for run in runs], [1, 2, 3])
        self.assertEqual([run["telemetry"]["status"] for run in runs], ["valid", "valid", "valid"])
        self.assertEqual(runs[1]["telemetry"]["retry_count"], 1)

    def test_analysis_version_persists_and_returns_scenario_pass_telemetry(self):
        telemetry = {
            "step_name": "scenarios_pass_1",
            "pass_number": 1,
            "model": "gpt-5-mini",
            "reasoning_effort": "medium",
            "status": "valid",
            "input_tokens": 100,
            "cached_input_tokens": 25,
            "cache_write_tokens": None,
            "output_tokens": 20,
            "reasoning_tokens": 5,
            "total_tokens": 120,
            "web_search_call_count": 1,
            "retry_count": 0,
            "duration_ms": 275,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "telemetry.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = web_server.utc_now_iso()
                    root_id = conn.execute(
                        "INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)",
                        ("TEST", now, now),
                    ).lastrowid
                    web_server._insert_analysis_version(
                        conn=conn,
                        root_id=root_id,
                        symbol="TEST",
                        company_name="Test Co",
                        current_price=20,
                        business_model="Business model",
                        business_summary="Business summary",
                        assumptions="Assumptions",
                        scenarios=stored_scenarios(),
                        key_variables=key_variables(),
                        raw_ai_response=json.dumps({"step3_prompt": "Build scenarios"}),
                        source_trigger="test",
                        scenario_passes=[
                            {
                                "pass_index": 1,
                                "raw_response_text": "{}",
                                "parsed_json": scenario_payload(),
                                "validation_status": "valid",
                                "rejection_reason": None,
                                "quality_score": 8.0,
                                "is_outlier": False,
                                "telemetry": telemetry,
                                "created_at": now,
                            }
                        ],
                    )
                    conn.commit()
                    detail = web_server.get_analysis_detail(conn, "TEST")
                finally:
                    conn.close()

        self.assertEqual(detail["version"]["scenario_passes"][0]["telemetry"], telemetry)

    def test_analysis_version_persists_core_evidence_and_wall_duration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "core-evidence.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    now = web_server.utc_now_iso()
                    root_id = conn.execute(
                        "INSERT INTO analysis_roots (symbol, created_at, updated_at) VALUES (?, ?, ?)",
                        ("TEST", now, now),
                    ).lastrowid
                    web_server._insert_analysis_version(
                        conn=conn,
                        root_id=root_id,
                        symbol="TEST",
                        company_name="Test Co",
                        current_price=20,
                        business_model="Business model",
                        business_summary="Business summary",
                        assumptions="Assumptions",
                        scenarios=stored_scenarios(),
                        key_variables=key_variables(),
                        raw_ai_response=json.dumps({"step3_prompt": "Prompt"}),
                        source_trigger="test",
                        core_evidence_pack=core_evidence_pack(),
                        core_evidence_generated_at=now,
                        core_evidence_model="gpt-5.6-terra",
                        core_evidence_reasoning_effort="low",
                        core_evidence_telemetry={"model": "gpt-5.6-terra", "reasoning_effort": "low", "input_tokens": 10},
                        scenario_generation_wall_duration_ms=1234,
                    )
                    conn.commit()
                    detail = web_server.get_analysis_detail(conn, "TEST")
                finally:
                    conn.close()

        self.assertEqual(detail["version"]["core_evidence_pack"]["symbol"], "TEST")
        self.assertEqual(detail["version"]["core_evidence_model"], "gpt-5.6-terra")
        self.assertEqual(detail["version"]["core_evidence_reasoning_effort"], "low")
        self.assertEqual(detail["version"]["scenario_generation_wall_duration_ms"], 1234)

    def test_prompt_migration_preserves_custom_scenario_prompt(self):
        custom_prompt = "Custom $Symbol $CompanyName $BusinessModel $KeyVariables $CoreEvidencePack"
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "custom-prompt.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    web_server.save_prompt_template(conn, web_server.ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS, custom_prompt)
                    web_server.migrate_legacy_default_prompt_templates(conn)
                    stored = conn.execute(
                        "SELECT value FROM app_settings WHERE key = ?",
                        (web_server.ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS,),
                    ).fetchone()
                finally:
                    conn.close()

        self.assertEqual(stored["value"], custom_prompt)

    def test_prompt_migration_updates_only_exact_legacy_scenario_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "legacy-prompt.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    conn.execute(
                        """
                        INSERT INTO app_settings (key, value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                        """,
                        (
                            web_server.ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS,
                            web_server.LEGACY_DEFAULT_PROMPT_SCENARIOS,
                            web_server.utc_now_iso(),
                        ),
                    )
                    conn.commit()
                    web_server.migrate_legacy_default_prompt_templates(conn)
                    stored = conn.execute(
                        "SELECT value FROM app_settings WHERE key = ?",
                        (web_server.ANALYSIS_PROMPT_SETTING_KEY_SCENARIOS,),
                    ).fetchone()
                finally:
                    conn.close()

        self.assertEqual(stored["value"], web_server.DEFAULT_PROMPT_SCENARIOS)

    def test_logging_configuration_allows_bakingmoney_info_messages(self):
        original_level = web_server.logger.level
        original_propagate = web_server.logger.propagate
        try:
            web_server.configure_bakingmoney_logging(force=False)
            self.assertLessEqual(web_server.logger.getEffectiveLevel(), web_server.logging.INFO)
            self.assertTrue(web_server.logger.propagate)
        finally:
            web_server.logger.setLevel(original_level)
            web_server.logger.propagate = original_propagate

    def test_request_ai_step_logs_start_completion_and_uses_actual_model_without_secrets(self):
        captured_request_bodies = []
        response_payload = {
            "output": [{"content": [{"type": "output_text", "text": json.dumps({"ok": True})}]}],
            "usage": {
                "input_tokens": 12331,
                "input_tokens_details": {"cached_tokens": 7808},
                "output_tokens": 881,
                "output_tokens_details": {"reasoning_tokens": 635},
                "total_tokens": 13212,
            },
        }

        def fake_urlopen(request, timeout):
            captured_request_bodies.append(json.loads(request.data.decode("utf-8")))
            return FakeOpenAIResponse(response_payload)

        with mock.patch.object(web_server, "OPENAI_API_KEY", "super-secret-key"), \
             mock.patch.object(web_server, "OPENAI_MODEL", "gpt-5.6-terra"), \
             mock.patch.object(web_server, "OPENAI_REASONING_EFFORT", "low"), \
             mock.patch.object(web_server, "OPENAI_REQUEST_TIMEOUT_SECONDS", 60.0), \
             mock.patch.object(web_server, "OPENAI_TEMPERATURE_RAW", "0.1"), \
             mock.patch.object(web_server, "urlopen", side_effect=fake_urlopen), \
             mock.patch.object(web_server.time, "monotonic", side_effect=[10.0, 16.9]), \
             self.assertLogs(web_server.logger, level="INFO") as captured_logs:
            payload, telemetry = web_server.request_ai_step_with_telemetry(
                "scenarios_pass_1",
                "prompt",
                {"name": "test", "schema": {"type": "object", "properties": {}, "required": []}},
            )

        joined_logs = "\n".join(captured_logs.output)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(captured_request_bodies[0]["model"], "gpt-5.6-terra")
        self.assertEqual(telemetry["model"], "gpt-5.6-terra")
        self.assertEqual(telemetry["reasoning_effort"], "low")
        self.assertIn("Starting AI step=scenarios_pass_1 model=gpt-5.6-terra temp=omitted reasoning=low", joined_logs)
        self.assertIn("OpenAI web search tool type: web_search", joined_logs)
        self.assertIn("OpenAI request timeout seconds for step=scenarios_pass_1 attempt=1: 60.0", joined_logs)
        self.assertIn("Completed AI step=scenarios_pass_1 model=gpt-5.6-terra duration=6.9s", joined_logs)
        self.assertIn("input_tokens=12331", joined_logs)
        self.assertIn("cached_tokens=7808", joined_logs)
        self.assertIn("output_tokens=881", joined_logs)
        self.assertIn("reasoning_tokens=635", joined_logs)
        self.assertIn("retries=0", joined_logs)
        self.assertNotIn("super-secret-key", joined_logs)
        self.assertNotIn("Authorization", joined_logs)

    def test_request_ai_step_completion_log_handles_missing_optional_telemetry_fields(self):
        response_payload = {
            "output": [{"content": [{"type": "output_text", "text": json.dumps({"ok": True})}]}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }

        with mock.patch.object(web_server, "OPENAI_MODEL", "gpt-5.6-terra"), \
             mock.patch.object(web_server, "OPENAI_REASONING_EFFORT", "low"), \
             mock.patch.object(web_server, "urlopen", return_value=FakeOpenAIResponse(response_payload)), \
             mock.patch.object(web_server.time, "monotonic", side_effect=[1.0, 1.5]), \
             self.assertLogs(web_server.logger, level="INFO") as captured_logs:
            _payload, telemetry = web_server.request_ai_step_with_telemetry(
                "scenarios_pass_1",
                "prompt",
                {"name": "test", "schema": {"type": "object", "properties": {}, "required": []}},
            )

        joined_logs = "\n".join(captured_logs.output)
        self.assertIsNone(telemetry["cached_input_tokens"])
        self.assertIsNone(telemetry["reasoning_tokens"])
        self.assertIn("cached_tokens=-", joined_logs)
        self.assertIn("reasoning_tokens=-", joined_logs)

    def test_request_ai_step_retry_path_logs_retry_and_completion_summary(self):
        unsupported = web_server.HTTPError(
            "https://api.openai.com/v1/responses",
            400,
            "Bad Request",
            hdrs=None,
            fp=web_server.BytesIO(b'{"error":{"message":"Invalid unsupported web_search tool"}}'),
        )
        response_payload = {
            "output": [
                {"type": "web_search_call", "id": "ws_1"},
                {"content": [{"type": "output_text", "text": json.dumps({"ok": True})}]},
            ],
            "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        }

        with mock.patch.object(web_server, "OPENAI_WEB_SEARCH_TOOL_CANDIDATES", ("web_search", "web_search_preview")), \
             mock.patch.object(web_server, "urlopen", side_effect=[unsupported, FakeOpenAIResponse(response_payload)]), \
             mock.patch.object(web_server.time, "monotonic", side_effect=[2.0, 4.0]), \
             self.assertLogs(web_server.logger, level="INFO") as captured_logs:
            _payload, telemetry = web_server.request_ai_step_with_telemetry(
                "scenarios_pass_1",
                "prompt",
                {"name": "test", "schema": {"type": "object", "properties": {}, "required": []}},
            )

        joined_logs = "\n".join(captured_logs.output)
        self.assertEqual(telemetry["retry_count"], 1)
        self.assertEqual(telemetry["web_search_call_count"], 1)
        self.assertIn("Retrying with web_search_preview", joined_logs)
        self.assertIn("OpenAI web search tool type: web_search_preview", joined_logs)
        self.assertIn("web_searches=1", joined_logs)
        self.assertIn("retries=1", joined_logs)


class ScenarioTelemetryMigrationTests(unittest.TestCase):
    def test_init_db_adds_telemetry_column_for_scenario_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "telemetry-column.db")
            with mock.patch.object(web_server, "DB_PATH", db_path):
                web_server.init_db()
                conn = web_server.get_db_connection()
                try:
                    columns = {
                        row["name"]
                        for row in conn.execute("PRAGMA table_info(analysis_version_scenario_passes)").fetchall()
                    }
                finally:
                    conn.close()

        self.assertIn("telemetry_json", columns)


if __name__ == "__main__":
    unittest.main()
