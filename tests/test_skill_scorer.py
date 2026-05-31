"""Unit tests for src.agent.skill_scorer.SkillScorer.

All tests are deterministic and require no LLM calls, HTTP, or filesystem I/O.
Each test would fail if the logic under test were removed or broken.
"""
import time
import unittest
from unittest.mock import MagicMock

from src.agent.skill_scorer import SkillScorer


def _make_skill(name: str, score: float) -> MagicMock:
    skill = MagicMock()
    type(skill).__name__ = name
    skill.can_handle.return_value = score
    skill.tool_definition.return_value = {"name": name}
    return skill


class TestSkillScorer(unittest.TestCase):

    def test_highest_score_wins(self):
        """Scorer returns the skill with the highest can_handle score."""
        low = _make_skill("LowSkill", 0.3)
        high = _make_skill("HighSkill", 0.9)
        scorer = SkillScorer([low, high], threshold=0.65)
        skill, score, _ = scorer.score("test input", {})
        self.assertEqual(type(skill).__name__, "HighSkill")
        self.assertAlmostEqual(score, 0.9)

    def test_below_threshold_returns_none_skill(self):
        """When best score is below threshold, skill is None but score is preserved."""
        low = _make_skill("LowSkill", 0.4)
        scorer = SkillScorer([low], threshold=0.65)
        skill, score, _ = scorer.score("test input", {})
        self.assertIsNone(skill)
        self.assertAlmostEqual(score, 0.4)

    def test_exactly_at_threshold_returns_skill(self):
        """Score equal to threshold is included (≥ not >)."""
        s = _make_skill("EdgeSkill", 0.65)
        scorer = SkillScorer([s], threshold=0.65)
        skill, score, _ = scorer.score("edge case", {})
        self.assertIsNotNone(skill)
        self.assertAlmostEqual(score, 0.65)

    def test_slow_skill_timeout_does_not_crash(self):
        """A skill whose can_handle blocks past the timeout is skipped gracefully."""
        def _slow_handle(user_input, context):
            time.sleep(5.0)  # far exceeds 100ms window
            return 0.99

        slow = MagicMock()
        type(slow).__name__ = "SlowSkill"
        slow.can_handle.side_effect = _slow_handle
        slow.tool_definition.return_value = {"name": "SlowSkill"}

        fast = _make_skill("FastSkill", 0.8)
        scorer = SkillScorer([slow, fast], threshold=0.65)
        # Must complete in reasonable time (2s) and not raise.
        skill, score, _ = scorer.score("anything", {})
        # FastSkill should win; SlowSkill timed out.
        self.assertIsNotNone(skill)
        self.assertEqual(type(skill).__name__, "FastSkill")

    def test_cache_hit_returns_same_result(self):
        """Second call with the same input and key uses the cache."""
        s = _make_skill("CachedSkill", 0.9)
        scorer = SkillScorer([s], threshold=0.65)
        skill1, score1, key = scorer.score("repeated", {})
        # Mutate the skill to return 0.0 — cache should shield us from this.
        s.can_handle.return_value = 0.0
        skill2, score2, _ = scorer.score("repeated", {}, score_key=key)
        self.assertAlmostEqual(score1, score2)

    def test_clear_cache_forces_rescore(self):
        """After clear_cache(), the next call re-scores even for the same input."""
        s = _make_skill("FlipSkill", 0.9)
        scorer = SkillScorer([s], threshold=0.65)
        _, _, key = scorer.score("same input", {})
        s.can_handle.return_value = 0.1  # flip to below threshold
        scorer.clear_cache()
        skill, score, _ = scorer.score("same input", {})
        self.assertIsNone(skill)  # re-scored to 0.1, below threshold
        self.assertAlmostEqual(score, 0.1)

    def test_empty_skill_list_returns_none(self):
        """No skills → (None, 0.0)."""
        scorer = SkillScorer([], threshold=0.65)
        skill, score, _ = scorer.score("anything", {})
        self.assertIsNone(skill)
        self.assertEqual(score, 0.0)

    def test_can_handle_exception_skips_skill(self):
        """A skill whose can_handle raises is scored 0.0 and not raised to caller."""
        bad = MagicMock()
        type(bad).__name__ = "BrokenSkill"
        bad.can_handle.side_effect = RuntimeError("boom")
        bad.tool_definition.return_value = {"name": "BrokenSkill"}

        good = _make_skill("GoodSkill", 0.8)
        scorer = SkillScorer([bad, good], threshold=0.65)
        skill, score, _ = scorer.score("test", {})
        self.assertEqual(type(skill).__name__, "GoodSkill")


if __name__ == "__main__":
    unittest.main()
