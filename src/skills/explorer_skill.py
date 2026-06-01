"""Bounded Explorer skill — multi-step investigation loop.

Implements:
  FR-ORCH-039  — can_handle scoring
  FR-ORCH-040  — bounded execute loop
  FR-ORCH-041  — registration in _builtin_skills
  NFR-ORCH-014 — step budget + convergence detection
  NFR-ORCH-015 — heuristic confidence, routed sub-questions
  NFR-RES-002  — evidence cap raised to 3,000 chars per step (CR-053 Phase 1)
  FR-RES-013   — decompose_query() at step 1; parallel _gather() for multi-part
  FR-RES-016   — delegate to research.run_research() instead of inline _synthesize()
  FR-ROUTE-004 — context-aware follow-up boost (CR-054 Phase 2)

Design constraints (from docs/planning/exploration-2026-05.md #15):
- Hard step budget: _MAX_STEPS = 6 (not a magic number)
- Convergence detection: action hash per step; repeat → stop immediately
- Confidence: heuristic only — no LLM call per step (NFR-ORCH-015)
- Sub-questions: force_route="simple_qa" (local model)
- Synthesis: delegated to research.run_research() (FR-RES-016)
- Budget exhaustion emits structured notes string (NFR-ORCH-014)
"""
from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from src.research_types import SourceRecord
from src.skills.base import Skill

# NFR-ORCH-014: hard step budget as a named constant (never a magic number).
_MAX_STEPS: int = 6

# NFR-ORCH-015: confidence thresholds for stop/escalate decisions.
_CONFIDENCE_HIGH: float = 0.85   # stop early and synthesize
_CONFIDENCE_LOW: float = 0.30    # escalate to user if below this at _EARLY_CHECK_STEP
_EARLY_CHECK_STEP: int = 3       # first step where low-confidence triggers escalation

# FR-ORCH-039: investigative intent keywords.
_INVESTIGATIVE_KEYWORDS: tuple[str, ...] = (
    "investigate",
    "research",
    "explore",
    "analyze",
    "analyse",
    "dig into",
    "look into",
    "deep dive",
    "find out more",
    "what's the relationship",
    "what is the relationship",
    "how does",
    "why is",
    "why does",
    "what causes",
    "what are the implications",
    "what are the effects",
)

# FR-ORCH-039: multi-hop indicators → lower score than investigative keywords.
_MULTI_HOP_INDICATORS: tuple[str, ...] = (
    " and also ",
    "furthermore",
    "as well as",
    "in addition to",
    "related to",
    "in the context of",
)

# NFR-ORCH-015: evidence quality — low-signal phrases detected in gathered text.
_LOW_SIGNAL_PHRASES: tuple[str, ...] = (
    "couldn't find",
    "no results",
    "couldn't search",
    "found links, but",
    "couldn't read",
)

# FR-ROUTE-004: follow-up phrases for context-aware boost (CR-054 Phase 2)
_FOLLOWUP_PHRASES: tuple[str, ...] = (
    "what about",
    "and in",
    "how about",
    "same for",
    "what about in",
)

# NFR-RES-002: evidence cap per step raised from 500 to 3,000 chars
_EVIDENCE_CAP: int = 3_000


class ExplorerSkill(Skill):
    """Multi-step bounded investigation loop.

    Implements FR-ORCH-039 (can_handle), FR-ORCH-040 (execute loop),
    FR-ORCH-041 (registration in XochitlChat._builtin_skills).

    The loop per step:
      1. Form subquestion (step 1 = original query; steps 2+ = LLM-derived)
      2. Convergence check: repeat action-hash → stop (NFR-ORCH-014)
      3. Gather evidence via WebLookupSkill (SSRF already protected)
      4. Score heuristic confidence (no LLM call — NFR-ORCH-015)
      5. confidence > 0.85 → synthesize and return
      6. confidence < 0.30 at step ≥ 3 → escalate to user
    After _MAX_STEPS without stopping: synthesize with budget-exhausted note.
    """

    def __init__(self) -> None:
        self._cancelled: bool = False

    def cleanup(self) -> None:
        """Signal the investigation loop to stop on next iteration. FR-RELY-004."""
        self._cancelled = True

    def can_handle(self, user_input: str, context: dict) -> float:
        """Score investigative queries for skill routing.

        Implements FR-ORCH-039, FR-ROUTE-004 (context-aware follow-up boost).

        Args:
            user_input: The user's raw message.
            context: Current session context dict.

        Returns:
            0.85 for investigative keywords, 0.75 for context-aware follow-up,
            0.70 for multi-hop indicators, 0.0 otherwise.
        """
        q = user_input.lower()
        # FR-ROUTE-004: context-aware follow-up boost
        if (
            len(user_input.split()) <= 8
            and any(phrase in q for phrase in _FOLLOWUP_PHRASES)
            and context.get("last_skill_fired") == "ExplorerSkill"
        ):
            return 0.75
        if any(k in q for k in _INVESTIGATIVE_KEYWORDS):
            return 0.85
        if any(k in q for k in _MULTI_HOP_INDICATORS):
            return 0.70
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        """Return the suggestion shown to the user before execution.

        Args:
            user_input: The user's raw message.
            context: Current session context dict.

        Returns:
            A natural-language suggestion string.
        """
        return (
            "This looks like a multi-step investigation. "
            "Want me to dig into it systematically?"
        )

    def tool_definition(self) -> dict:
        """Return the skill descriptor for LLM system-prompt injection.

        Implements FR-ORCH-005.

        Returns:
            Dict with name, description, when, and params keys.
        """
        return {
            "name": "ExplorerSkill",
            "description": (
                "Runs a bounded multi-step investigation loop to answer complex queries "
                "that require evidence from multiple sources."
            ),
            "when": (
                "user asks to investigate, research, explore, or analyze something; "
                "or the question requires multiple steps or sources to answer fully"
            ),
            "params": {
                "query": "The research question or topic to investigate",
            },
            "timeout_secs": 120,
            "examples": [
                "investigate the causes of tech layoffs in 2024",
                "research the best approaches to microservices",
                "deep dive into Python async patterns",
                "explore how LLMs handle context windows",
                "analyze the relationship between diet and productivity",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Run the bounded investigation loop.

        Implements FR-ORCH-040, NFR-ORCH-014, NFR-ORCH-015, FR-RES-013, FR-RES-016.

        Loop body per step:
          1. Decompose query at step 1 via decompose_query() (FR-RES-013)
          2. Form subquestion (_form_subquestion) for step ≥ 2
          3. Hash subquestion; repeat hash = cycle → synthesize with loop note
          4. Gather evidence (_gather via WebLookupSkill) — capped at 3,000 chars (NFR-RES-002)
          5. Heuristic confidence (_score_confidence — no LLM call)
          6. confidence > _CONFIDENCE_HIGH → synthesize via research.run_research()
          7. step ≥ _EARLY_CHECK_STEP and confidence < _CONFIDENCE_LOW → _escalate
        After _MAX_STEPS: synthesize what we have via research.run_research().

        Args:
            user_input: Raw user message (fallback if params["query"] missing).
            context: Current session context dict.
            params: Parsed skill params; expects {"query": "..."}.

        Returns:
            Synthesized investigation result, escalation message, or
            loop-detection summary.
        """
        query = (params.get("query") or user_input).strip()
        if not query:
            return "I need a topic to investigate."

        # FR-RES-013: decompose multi-part query at step 1
        try:
            from src.query_planner import decompose_query
            sub_queries = decompose_query(query)
        except Exception:
            sub_queries = [query]

        from src.research import classify_intent
        intent = classify_intent(query)

        all_sources: list[SourceRecord] = []
        evidence: list[str] = []
        seen_hashes: set[str] = set()

        # FR-RES-013: if multi-part, gather each sub-query in parallel at step 1
        if len(sub_queries) > 1:
            def _gather_sub(sq: str) -> tuple[str, list[SourceRecord]]:
                return self._gather(sq, context)

            with ThreadPoolExecutor(max_workers=min(len(sub_queries), 4)) as pool:
                futs = {pool.submit(_gather_sub, sq): sq for sq in sub_queries}
                for fut in as_completed(futs):
                    try:
                        snippet, recs = fut.result(timeout=30)
                    except Exception:
                        continue
                    if snippet:
                        evidence.append(f"[Step 1] {snippet}")
                    all_sources.extend(recs)
            step_start = 2
        else:
            step_start = 1

        for step in range(step_start, _MAX_STEPS + 1):
            if self._cancelled:
                return self._finish(query, evidence, all_sources, intent, notes="Investigation cancelled.")

            subquestion = self._form_subquestion(query, step, evidence)
            action_hash = hashlib.md5(subquestion.lower().encode()).hexdigest()[:8]
            if action_hash in seen_hashes:
                return self._finish(
                    query, evidence, all_sources, intent,
                    notes=f"Investigation loop detected at step {step} — stopping early.",
                )
            seen_hashes.add(action_hash)

            snippet, recs = self._gather(subquestion, context)
            if snippet:
                evidence.append(f"[Step {step}] {snippet}")
            all_sources.extend(recs)

            confidence = self._score_confidence(evidence)

            if confidence > _CONFIDENCE_HIGH:
                return self._finish(query, evidence, all_sources, intent)

            if step >= _EARLY_CHECK_STEP and confidence < _CONFIDENCE_LOW:
                return self._escalate(query, evidence, step)

        return self._finish(
            query, evidence, all_sources, intent,
            notes=f"Step budget exhausted ({_MAX_STEPS} steps).",
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _form_subquestion(
        self, query: str, step: int, evidence: list[str]
    ) -> str:
        """Derive the next investigation subquestion.

        Step 1 returns the original query directly.
        Steps 2+ call the local router to derive a follow-up question from
        the remaining gaps in evidence (NFR-ORCH-015: force_route="simple_qa").

        Args:
            query: The original investigation question.
            step: Current step number (1-indexed).
            evidence: Evidence snippets gathered so far.

        Returns:
            A subquestion string. Falls back to original query on any error.
        """
        if step == 1:
            return query
        try:
            evidence_tail = "\n".join(evidence[-2:])
            prompt = (
                f"I am researching: {query}\n"
                f"Evidence so far:\n{evidence_tail}\n"
                f"What is the single most important follow-up question to answer "
                f"next? Reply with only the question, no preamble."
            )
            from src.router import get_router
            result = get_router().route(prompt, force_route="simple_qa", session_id=None)
            return (result or query).strip()
        except Exception:
            return query

    def _gather(self, subquestion: str, context: dict) -> tuple[str, list[SourceRecord]]:
        """Gather evidence for the subquestion via WebLookupSkill.

        Implements NFR-ORCH-015 (WebLookupSkill evidence source),
        NFR-RES-002 (evidence cap raised to 3,000 chars).
        SSRF protection is inherited from WebLookupSkill / fetch_bytes.

        Args:
            subquestion: The question to look up.
            context: Current session context dict (passed through).

        Returns:
            Tuple of (evidence_snippet, list[SourceRecord]).
            snippet is up to _EVIDENCE_CAP chars; sources may be empty on failure.
        """
        try:
            from src.skills.web_lookup_skill import WebLookupSkill
            ctx_copy = context.copy()
            raw = WebLookupSkill().execute(
                subquestion, ctx_copy, {"query": subquestion}
            )
            sources: list[SourceRecord] = ctx_copy.get("research_sources", [])
            # Strip the stock preamble
            if "\n" in raw:
                raw = raw[raw.index("\n") + 1:].strip()
            return raw[:_EVIDENCE_CAP], sources
        except Exception:
            return "", []

    def _score_confidence(self, evidence: list[str]) -> float:
        """Heuristic confidence from gathered evidence (no LLM call).

        Implements NFR-ORCH-015.

        Formula:
            depth_score  = min(len(evidence) * 0.15, 0.45)
            quality_score based on latest snippet length:
              len > 100 → +0.20, len > 250 → +0.15, len > 400 → +0.15
            penalty: any low-signal phrase in total evidence → −0.20
            result = max(0.0, min(1.0, depth + quality))

        With this formula:
            3 rich snippets (>400 chars each)  → ~0.95 → early stop
            6 medium snippets (~120 chars each) → ~0.65 → budget exhaustion
            3 failure snippets ("couldn't find") → ~0.25 → escalation

        Args:
            evidence: List of evidence snippets gathered so far.

        Returns:
            Confidence score in [0.0, 1.0].
        """
        if not evidence:
            return 0.0
        latest = evidence[-1]
        total = " ".join(evidence)

        depth_score = min(len(evidence) * 0.15, 0.45)

        quality_score = 0.0
        if len(latest) > 100:
            quality_score += 0.20
        if len(latest) > 250:
            quality_score += 0.15
        if len(latest) > 400:
            quality_score += 0.15

        if any(phrase in total.lower() for phrase in _LOW_SIGNAL_PHRASES):
            quality_score -= 0.20

        return max(0.0, min(1.0, depth_score + quality_score))

    def _finish(
        self,
        query: str,
        evidence: list[str],
        sources: list[SourceRecord],
        intent: str = "prose",
        notes: str = "",
    ) -> str:
        """Synthesize gathered evidence via research.run_research() (FR-RES-016).

        Delegates to the shared synthesis pipeline so ExplorerSkill output
        has the same Confidence/citation/sources-block format as ResearchSkill.

        Args:
            query: The original investigation question.
            evidence: Evidence snippets (used as fallback when no SourceRecords).
            sources: SourceRecord list from _gather() calls.
            intent: Query intent label from classify_intent().
            notes: Optional notes to prepend (e.g., "budget exhausted").

        Returns:
            Synthesized Perplexity-grade answer string.
        """
        if not sources and not evidence:
            return "I wasn't able to gather enough information to answer that question."

        if sources:
            from src.research import run_research
            result = run_research(topic=query, sources=sources, intent=intent)
            synthesis = result["synthesis"]
        else:
            # Fallback: synthesize bare evidence strings
            from src.research import run_research, SourceRecord as _SR  # noqa: F811
            bare = [
                SourceRecord(title=f"Step {i+1}", url="", domain="", body=ev)
                for i, ev in enumerate(evidence)
            ]
            result = run_research(topic=query, sources=bare, intent=intent)
            synthesis = result["synthesis"]

        if notes:
            synthesis = f"Note: {notes}\n\n{synthesis}"
        return synthesis

    def _escalate(
        self, query: str, evidence: list[str], step: int
    ) -> str:
        """Surface low-confidence investigation to the user for guidance.

        Args:
            query: The original investigation question.
            evidence: Evidence gathered so far.
            step: Current step number where escalation was triggered.

        Returns:
            Escalation message asking the user to refine or continue.
        """
        summary = "\n".join(evidence) if evidence else "(nothing gathered yet)"
        return (
            f"I've investigated for {step} steps but my confidence is low. "
            f"Here's what I found so far:\n\n{summary}\n\n"
            f"Want me to keep digging, or would you like to refine the question?"
        )
