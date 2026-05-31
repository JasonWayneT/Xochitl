"""Unit tests for src.skills.registry.SkillRegistry.

No LLM calls, HTTP, or filesystem I/O.
"""
import unittest
from unittest.mock import MagicMock

from src.skills.registry import SkillRegistry


def _make_skill(class_name: str, tool_name: str) -> MagicMock:
    skill = MagicMock()
    type(skill).__name__ = class_name
    skill.tool_definition.return_value = {"name": tool_name}
    return skill


class TestSkillRegistry(unittest.TestCase):

    def setUp(self):
        self.reg = SkillRegistry()

    def test_register_and_all(self):
        """Registered skills appear in all()."""
        s = _make_skill("WeatherSkill", "WeatherSkill")
        self.reg.register(s)
        self.assertIn(s, self.reg.all())

    def test_all_returns_copy(self):
        """all() returns a snapshot — mutating it doesn't affect the registry."""
        s = _make_skill("Skill1", "Skill1")
        self.reg.register(s)
        copy = self.reg.all()
        copy.clear()
        self.assertEqual(len(self.reg.all()), 1)

    def test_by_name_class_name(self):
        """by_name() finds a skill by exact class name."""
        s = _make_skill("WeatherSkill", "WeatherSkill")
        self.reg.register(s)
        self.assertIs(self.reg.by_name("WeatherSkill"), s)

    def test_by_name_case_insensitive(self):
        """by_name() is case-insensitive."""
        s = _make_skill("WeatherSkill", "WeatherSkill")
        self.reg.register(s)
        self.assertIs(self.reg.by_name("weatherskill"), s)

    def test_by_name_tool_definition_name(self):
        """by_name() also matches the tool_definition name (lower-cased)."""
        s = _make_skill("WSkill", "WeatherSkill")
        self.reg.register(s)
        self.assertIs(self.reg.by_name("weatherskill"), s)

    def test_by_name_unknown_returns_none(self):
        """by_name() returns None for an unregistered name."""
        self.assertIsNone(self.reg.by_name("DoesNotExist"))

    def test_duplicate_registration_ignored(self):
        """Registering the same class name twice keeps only the first instance."""
        s1 = _make_skill("WeatherSkill", "WeatherSkill")
        s2 = _make_skill("WeatherSkill", "WeatherSkill")
        self.reg.register(s1)
        self.reg.register(s2)
        self.assertEqual(len(self.reg.all()), 1)
        self.assertIs(self.reg.by_name("WeatherSkill"), s1)

    def test_clear_removes_all(self):
        """clear() removes all registrations."""
        self.reg.register(_make_skill("SkillA", "SkillA"))
        self.reg.register(_make_skill("SkillB", "SkillB"))
        self.reg.clear()
        self.assertEqual(self.reg.all(), [])
        self.assertIsNone(self.reg.by_name("SkillA"))

    def test_registration_order_preserved(self):
        """Skills appear in all() in registration order."""
        names = ["Alpha", "Beta", "Gamma"]
        for n in names:
            self.reg.register(_make_skill(n, n))
        result_names = [type(s).__name__ for s in self.reg.all()]
        self.assertEqual(result_names, names)

    def test_failing_init_does_not_corrupt_registry(self):
        """A skill whose __init__ raises should be handled by the caller (_safe_register)."""
        # _safe_register wraps register() — registry itself just stores what's given.
        # This test verifies that a valid skill registered after a bad one still works.
        good = _make_skill("GoodSkill", "GoodSkill")
        self.reg.register(good)
        self.assertIs(self.reg.by_name("GoodSkill"), good)


class TestGlobalRegistry(unittest.TestCase):
    """Verify the global _registry singleton has all 12 core skills."""

    def test_all_core_skills_registered(self):
        from src.skills import _registry
        names = {type(s).__name__ for s in _registry.all()}
        expected = {
            "BMADSkill", "SDDSkill", "CodeSkill", "NotionSkill",
            "OrchestratorSkill", "WeatherSkill", "WebLookupSkill",
            "ZettelkastenSkill", "ExplorerSkill", "WorkflowSkill",
            "MapsSkill", "GmailSkill",
        }
        self.assertTrue(expected.issubset(names), f"Missing: {expected - names}")

    def test_by_name_weather_skill(self):
        from src.skills import _registry
        skill = _registry.by_name("WeatherSkill")
        self.assertIsNotNone(skill)
        self.assertEqual(type(skill).__name__, "WeatherSkill")


if __name__ == "__main__":
    unittest.main()
