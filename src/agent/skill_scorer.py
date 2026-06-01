"""SkillScorer — concurrent can_handle() scoring, extracted from chat._agent_loop.

Runs all skills concurrently via ThreadPoolExecutor with a 100ms total timeout.
Results are cached per input hash to avoid re-scoring the same input twice in
one session turn (e.g. staged messages).

FR-PERF-003 (CR-050 B3): concurrent scoring with per-turn cache.
FR-ROUTE-008 (CR-054 Phase 3): vector fallback when keyword scoring misses.
FR-ROUTE-013 (CR-054 Phase 4): load learned examples from skill_examples table.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.skills.base import Skill

_log = logging.getLogger("xochitl.skill_scorer")

# Maximum seconds to wait for ALL skill scores.
_SCORE_TIMEOUT_SECS = 0.10

# FR-ROUTE-008: vector fallback minimum similarity threshold
_VECTOR_FALLBACK_THRESHOLD = 0.80

# FR-ROUTE-009: scale threshold — vector shortlist activates above this count
_VECTOR_SHORTLIST_THRESHOLD = 30

# NFR-ROUTE-002: max milliseconds for vector fallback before timing out silently
_VECTOR_TIMEOUT_SECS = 0.50


class SkillScorer:
    """Scores a list of skills concurrently and caches the result per input.

    The scorer is created once per session (in XochitlChat.__init__) so the
    cache persists across staged-message re-entries within the same turn.

    Hybrid scoring (FR-ROUTE-008, FR-ROUTE-009):
      1. Concurrent keyword scoring (existing path).
      2. If top_score < threshold AND SkillVectorIndex available → vector fallback.
      3. Learned examples (FR-ROUTE-013) are injected into context["learned_examples"].
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
        self._skill_vector: Optional[object] = None  # lazy-loaded SkillVectorIndex
        self._learned_examples: dict[str, list[str]] = {}  # FR-ROUTE-013
        self._examples_loaded = False

    def score(
        self,
        user_input: str,
        context: dict,
        score_key: tuple | None = None,
    ) -> tuple[Skill | None, float, tuple]:
        """Score all skills and return the best match.

        Implements FR-PERF-003 (concurrent scoring), FR-ROUTE-008 (vector fallback),
        FR-ROUTE-013 (learned examples injection).

        Args:
            user_input: Raw user message.
            context: Mutable session context dict forwarded to can_handle().
                Mutated to include context["learned_examples"] (FR-ROUTE-013).
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

        # FR-ROUTE-013: inject learned examples into context on first call or dirty flag
        if not self._examples_loaded or context.get("skill_examples_dirty"):
            self._load_learned_examples()
            context["skill_examples_dirty"] = False
        context["learned_examples"] = self._learned_examples

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

        # FR-ROUTE-008: vector fallback when keyword scoring misses
        if top_score < self._threshold:
            vector_skill, vector_score = self._vector_fallback(user_input)
            if vector_skill is not None and vector_score > top_score:
                top_skill = vector_skill
                top_score = vector_score

        result_skill = top_skill if top_score >= self._threshold else None
        self._cache[cache_hash] = (result_skill, top_score)
        self._cache_key[cache_hash] = score_key
        return result_skill, top_score, score_key

    def _vector_fallback(
        self, user_input: str
    ) -> tuple[Optional["Skill"], float]:
        """Run vector search as a keyword-miss fallback.

        Implements FR-ROUTE-008, NFR-ROUTE-002.

        Returns:
            (matched_skill_or_None, score).  Returns (None, 0.0) when:
            - SkillVectorIndex unavailable
            - embedding exceeds 500ms timeout
            - no result meets _VECTOR_FALLBACK_THRESHOLD
        """
        try:
            idx = self._get_vector_index()
            if idx is None:
                return None, 0.0

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(idx.search, user_input, limit=5)
                try:
                    results = fut.result(timeout=_VECTOR_TIMEOUT_SECS)
                except concurrent.futures.TimeoutError:
                    return None, 0.0

            for hit in results:
                if hit["score"] >= _VECTOR_FALLBACK_THRESHOLD:
                    skill_name = hit["skill_name"]
                    for skill in self._skills:
                        if type(skill).__name__ == skill_name:
                            _log.debug(
                                "vector_fallback skill=%s score=%.3f",
                                skill_name, hit["score"],
                            )
                            return skill, hit["score"]
        except Exception:
            pass
        return None, 0.0

    def _get_vector_index(self) -> Optional[object]:
        """Lazy-load SkillVectorIndex. Returns None on any failure."""
        if self._skill_vector is None:
            try:
                from src.skill_vector import SkillVectorIndex
                self._skill_vector = SkillVectorIndex()
            except Exception:
                return None
        return self._skill_vector

    def _load_learned_examples(self) -> None:
        """Load skill_examples table into in-memory dict (FR-ROUTE-013)."""
        try:
            from src import database as _db
            with _db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT skill_name, phrase FROM skill_examples ORDER BY created_at DESC"
                ).fetchall()
            examples: dict[str, list[str]] = {}
            for row in rows:
                name = row[0]
                phrase = row[1]
                examples.setdefault(name, []).append(phrase)
            self._learned_examples = examples
        except Exception:
            self._learned_examples = {}
        self._examples_loaded = True

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
