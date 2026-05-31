"""Unit tests for src.agent.skill_dispatcher.dispatch.

All tests use mocked skills and a real ActionGovernor.
No LLM calls, HTTP, or filesystem I/O.
Each test would fail if the logic under test were removed or broken.
"""
import time
import unittest
from unittest.mock import MagicMock, patch

from src.agent.skill_dispatcher import dispatch
from src.executor import (
    ActionGovernor,
    ActionTier,
    ConfirmationRequired,
    PolicyViolation,
)


def _make_skill(name: str, result: str = "ok") -> MagicMock:
    skill = MagicMock()
    type(skill).__name__ = name
    skill.execute.return_value = result
    skill.tool_definition.return_value = {"name": name}
    skill.cleanup.return_value = None
    return skill


class TestDispatch(unittest.TestCase):

    def test_auto_tier_executes_skill_and_returns_result(self):
        """AUTO-tier action executes the skill and returns its output string."""
        skill = _make_skill("TestSkill", "weather result")
        # 'fetch' is AUTO in ActionGovernor
        params = {"action": "fetch", "target": "escondido"}
        result = dispatch(skill, params, "what's the weather", {})
        self.assertEqual(result, "weather result")
        skill.execute.assert_called_once()

    def test_confirm_tier_raises_confirmation_required(self):
        """CONFIRM-tier action raises ConfirmationRequired before executing."""
        skill = _make_skill("CodeSkill")
        # 'write' is CONFIRM in ActionGovernor
        params = {"action": "write", "target": "src/foo.py"}
        with self.assertRaises(ConfirmationRequired):
            dispatch(skill, params, "write a file", {})
        skill.execute.assert_not_called()

    def test_deny_tier_raises_policy_violation(self):
        """DENY-tier action raises PolicyViolation before executing."""
        skill = _make_skill("DangerSkill")
        # path traversal triggers DENY
        params = {"action": "write", "target": "../../etc/passwd"}
        with self.assertRaises(PolicyViolation):
            dispatch(skill, params, "bad request", {})
        skill.execute.assert_not_called()

    def test_timeout_calls_cleanup_and_returns_error_string(self):
        """When skill.execute() exceeds timeout, cleanup() is called and error string returned."""
        def _slow(user_input, context, params):
            time.sleep(10.0)
            return "never"

        skill = _make_skill("SlowSkill")
        skill.execute.side_effect = _slow
        params = {"action": "fetch"}
        result = dispatch(skill, params, "anything", {}, timeout_secs=0.05)
        self.assertIn("SlowSkill", result)
        self.assertIn("longer than", result)
        skill.cleanup.assert_called_once()

    def test_skill_exception_returns_error_string(self):
        """Exception inside skill.execute() is caught and returned as an error string."""
        skill = _make_skill("BoomSkill")
        skill.execute.side_effect = ValueError("explosion")
        params = {"action": "fetch"}
        result = dispatch(skill, params, "do it", {})
        self.assertIn("explosion", result)
        self.assertNotIn("ok", result)

    def test_context_mutated_by_skill_is_visible_after(self):
        """Skill can mutate the context dict; caller sees the changes."""
        def _execute(user_input, context, params):
            context["last_skill_success"] = True
            return "done"

        skill = _make_skill("MutatingSkill")
        skill.execute.side_effect = _execute
        ctx = {}
        params = {"action": "fetch"}
        dispatch(skill, params, "go", ctx)
        self.assertTrue(ctx["last_skill_success"])

    def test_timeout_flag_set_in_context(self):
        """On timeout, context['last_skill_timeout'] is set to True."""
        def _slow(user_input, context, params):
            time.sleep(10.0)

        skill = _make_skill("SlowSkill")
        skill.execute.side_effect = _slow
        ctx = {}
        dispatch(skill, {"action": "fetch"}, "x", ctx, timeout_secs=0.05)
        self.assertTrue(ctx.get("last_skill_timeout"))

    def test_success_clears_timeout_flag(self):
        """On success, context['last_skill_timeout'] is set to False."""
        skill = _make_skill("FastSkill", "result")
        ctx = {"last_skill_timeout": True}
        dispatch(skill, {"action": "fetch"}, "x", ctx)
        self.assertFalse(ctx["last_skill_timeout"])

    def test_tool_definition_timeout_overrides_arg(self):
        """timeout_secs from tool_definition() takes precedence over the arg."""
        calls = []

        def _slow(user_input, context, params):
            time.sleep(0.5)
            calls.append("executed")
            return "done"

        skill = MagicMock()
        type(skill).__name__ = "CustomTimeoutSkill"
        skill.execute.side_effect = _slow
        # tool_definition reports a 0.05s timeout
        skill.tool_definition.return_value = {"name": "CustomTimeoutSkill", "timeout_secs": 0.05}
        skill.cleanup.return_value = None

        # Caller passes 30s but tool_definition overrides to 0.05s
        result = dispatch(skill, {"action": "fetch"}, "x", {}, timeout_secs=30.0)
        self.assertIn("longer than", result)
        self.assertEqual(calls, [])  # never reached completion


if __name__ == "__main__":
    unittest.main()
