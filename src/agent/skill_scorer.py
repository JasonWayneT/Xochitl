"""SkillScorer — concurrent can_handle() scoring, extracted from chat._agent_loop.

Runs all skills concurrently via ThreadPoolExecutor with a 100ms total timeout.
Results are cached per input hash to avoid re-scoring the same input twice in
one session turn (e.g. staged messages).

FR-PERF-003 (CR-050 B3): concurrent scoring with per-turn cache.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.skills.base import Skill

_log = logging.getLogger("xochitl.skill_scorer")

# Maximum seconds to wait for ALL skill scores.  Mirrors the hard-coded value
# that previously lived in _agent_loop.
_SCORE_TIMEOUT_SECS = 0.10


class SkillScorer:
    """Scores a list of skills concurrently and caches the result per input.

    The scorer is created once per session (in XochitlChat.__init__) so the
    cache persists across staged-message re-entries within the same turn.
    """

    def __init__(self, skills: list[Skill], threshold: float = 0.65) -> None:
        """
        Args:
            skills: Ordered skill list to score on each call.
            threshold: Minimum score to consider a skill matched.
        """
        self._skills = skills
        self._threshold = threshold
        self._cache: dict[str, tuple[Skill | None, float]] = {}
        self._cache_key: dict[str, tuple] = {}

    def score(
        self,
        user_input: str,
        context: dict,
        score_key: tuple | None = None,
    ) -> tuple[Skill | None, float, tuple]:
        """Score all skills and return the best match.

        Args:
            user_input: Raw user message.
            context: Mutable session context dict forwarded to can_handle().
            score_key: Optional tuple key from the caller (e.g. (hash, len)).
                When provided and matching the cache, the cached result is
                returned without re-scoring.  When None, a key is derived
                from user_input + skill count.

        Returns:
            Tuple of (best_skill_or_None, top_score, cache_key).
            best_skill_or_None is None when top_score < threshold.
            cache_key should be persisted by the caller for the next call.
        """
        if score_key is None:
            score_key = (hash(user_input), len(self._skills))

        cache_hash = hashlib.md5(user_input.encode()).hexdigest()
        if cache_hash in self._cache and self._cache_key.get(cache_hash) == score_key:
            skill, sc = self._cache[cache_hash]
            return skill, sc, score_key

        top_skill: Skill | None = None
        top_score: float = 0.0

        def _score_one(skill: Skill) -> tuple[Skill, float]:
            try:
                return skill, skill.can_handle(user_input, context)
            except Exception:
                return skill, 0.0

        max_workers = min(len(self._skills), 8) if self._skills else 1
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
                futs = {pool.submit(_score_one, sk): sk for sk in self._skills}
                for fut in concurrent.futures.as_completed(futs, timeout=_SCORE_TIMEOUT_SECS):
                    try:
                        sk, sc = fut.result(timeout=0)
                    except Exception:
                        continue
                    if sc > top_score:
                        top_score = sc
                        top_skill = sk
        except concurrent.futures.TimeoutError:
            pass  # partial results — use whatever scored within the window

        result_skill = top_skill if top_score >= self._threshold else None
        self._cache[cache_hash] = (result_skill, top_score)
        self._cache_key[cache_hash] = score_key
        return result_skill, top_score, score_key

    def update_skills(self, skills: list[Skill]) -> None:
        """Replace the skill list (called after reload_dynamic).

        Args:
            skills: New ordered skill list.
        """
        self._skills = skills
        self._cache.clear()
        self._cache_key.clear()

    def clear_cache(self) -> None:
        """Invalidate all cached scores."""
        self._cache.clear()
        self._cache_key.clear()
