"""Unit tests for src.agent.skill_parser.

All tests are pure — no LLM calls, no I/O, fully deterministic.
Each test would fail if the parsing logic were removed or broken.
"""
import unittest

from src.agent.skill_parser import parse_skill_calls, parse_skill_call, strip_skill_calls


class TestParseSkillCalls(unittest.TestCase):

    def test_single_valid_skill_call(self):
        """Parses a single well-formed skill_call block."""
        response = '<skill_call name="WeatherSkill">{"location": "Escondido, CA"}</skill_call>'
        calls = parse_skill_calls(response)
        self.assertEqual(len(calls), 1)
        name, params = calls[0]
        self.assertEqual(name, "WeatherSkill")
        self.assertEqual(params["location"], "Escondido, CA")

    def test_multiple_skill_calls_in_one_response(self):
        """Parses multiple skill_call blocks in order."""
        response = (
            '<skill_call name="SkillA">{"x": 1}</skill_call> some text '
            '<skill_call name="SkillB">{"y": 2}</skill_call>'
        )
        calls = parse_skill_calls(response)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "SkillA")
        self.assertEqual(calls[1][0], "SkillB")
        self.assertEqual(calls[0][1]["x"], 1)
        self.assertEqual(calls[1][1]["y"], 2)

    def test_malformed_json_returns_empty_params(self):
        """Bad JSON in the body yields empty params dict rather than raising."""
        response = '<skill_call name="WeatherSkill">NOT_JSON</skill_call>'
        calls = parse_skill_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], {})

    def test_empty_body_returns_empty_params(self):
        """Empty body yields empty params dict."""
        response = '<skill_call name="WeatherSkill"></skill_call>'
        calls = parse_skill_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], {})

    def test_no_skill_calls_returns_empty_list(self):
        """Plain text with no skill_call tags returns an empty list."""
        response = "This is a normal response with no skill calls."
        calls = parse_skill_calls(response)
        self.assertEqual(calls, [])

    def test_partial_tag_without_closing_is_not_matched(self):
        """An unclosed <skill_call> tag does not match."""
        response = '<skill_call name="WeatherSkill">{"location": "NYC"}'
        calls = parse_skill_calls(response)
        self.assertEqual(calls, [])

    def test_single_quoted_name_attribute(self):
        """Both single and double quotes around name= are accepted."""
        response = "<skill_call name='WeatherSkill'>{\"location\": \"NYC\"}</skill_call>"
        calls = parse_skill_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], "WeatherSkill")

    def test_case_insensitive_tag(self):
        """Tag name matching is case-insensitive."""
        response = '<SKILL_CALL name="WeatherSkill">{"q": 1}</SKILL_CALL>'
        calls = parse_skill_calls(response)
        self.assertEqual(len(calls), 1)

    def test_multiline_json_body(self):
        """JSON body spanning multiple lines is parsed correctly."""
        response = (
            '<skill_call name="CodeSkill">{\n'
            '  "action": "scaffold",\n'
            '  "project": "my-app"\n'
            '}</skill_call>'
        )
        calls = parse_skill_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["action"], "scaffold")


class TestParseSkillCall(unittest.TestCase):

    def test_returns_first_call(self):
        response = (
            '<skill_call name="First">{"a": 1}</skill_call>'
            '<skill_call name="Second">{"b": 2}</skill_call>'
        )
        result = parse_skill_call(response)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "First")

    def test_returns_none_when_no_calls(self):
        result = parse_skill_call("no skill here")
        self.assertIsNone(result)


class TestStripSkillCalls(unittest.TestCase):

    def test_strips_skill_call_block(self):
        response = 'Here is the answer. <skill_call name="X">{"y": 1}</skill_call>'
        clean = strip_skill_calls(response)
        self.assertNotIn("<skill_call", clean)
        self.assertIn("Here is the answer", clean)

    def test_strips_multiple_blocks(self):
        response = (
            '<skill_call name="A">{"x": 1}</skill_call> text '
            '<skill_call name="B">{"y": 2}</skill_call>'
        )
        clean = strip_skill_calls(response)
        self.assertNotIn("<skill_call", clean)
        self.assertIn("text", clean)

    def test_no_op_on_plain_text(self):
        text = "Just a normal response."
        self.assertEqual(strip_skill_calls(text), text)


if __name__ == "__main__":
    unittest.main()
