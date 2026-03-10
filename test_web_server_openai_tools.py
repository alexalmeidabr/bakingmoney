import unittest

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
