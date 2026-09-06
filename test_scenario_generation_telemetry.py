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


def key_variables():
    return [
        {"variable_text": "Demand", "variable_type": "Bullish", "driver_category": "Core Driver", "confidence": 8.0, "importance": 9.0},
        {"variable_text": "Competition", "variable_type": "Bearish", "driver_category": "Core Driver", "confidence": 4.0, "importance": 7.0},
    ]


class ScenarioGenerationTelemetryTests(unittest.TestCase):
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
