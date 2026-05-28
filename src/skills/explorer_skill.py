"""Bounded Explorer skill — multi-step investigation loop.

Implements FR-ORCH-039 (can_handle scoring), FR-ORCH-040 (bounded execute loop),
FR-ORCH-041 (registration in _builtin_skills), NFR-ORCH-014 (step budget +
convergence detection), NFR-ORCH-015 (heuristic confidence, routed sub-questions).

Design constraints (from docs/planning/exploration-2026-05.md #15):
- Hard step budget: _MAX_STEPS = 6 (not a magic number)
- Convergence detection: action hash per step; repeat → stop immediately
- Confidence: heuristic only — no LLM call per step (NFR-ORCH-015)
- Sub-questions: force_route="simple_qa" (local model)
- Synthesis: force_route="general" (cloud model)
- Budget exhaustion emits structured notes string (NFR-ORCH-014)
"""
from __future__ import annotations

import hashlib
from typing import Optional

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

    def can_handle(self, user_input: str, context: dict) -> float:
        """Score investigative queries for skill routing.

        Implements FR-ORCH-039.

        Args:
            user_input: The user's raw message.
            context: Current session context dict.

        Returns:
            0.85 for investigative keywords, 0.70 for multi-hop indicators,
            0.0 otherwise.
        """
        q = user_input.lower()
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

        Implements FR-ORCH-040, NFR-ORCH-014, NFR-ORCH-015.

        Loop body per step:
          1. Form subquestion (_form_subquestion)
          2. Hash subquestion; repeat hash = cycle → _synthesize with loop note
          3. Gather evidence (_gather via WebLookupSkill)
          4. Heuristic confidence (_score_confidence — no LLM call)
          5. confidence > _CONFIDENCE_HIGH → _synthesize and return
          6. step ≥ _EARLY_CHECK_STEP and confidence < _CONFIDENCE_LOW → _escalate
        After _MAX_STEPS: _synthesize with "Step budget exhausted" notes.

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

        evidence: list[str] = []
        seen_hashes: set[str] = set()

        for step in range(1, _MAX_STEPS + 1):
            # Phase 1: form subquestion for this step.
            subquestion = self._form_subquestion(query, step, evidence)

            # Phase 2: convergence detection (NFR-ORCH-014).
            action_hash = hashlib.md5(subquestion.lower().encode()).hexdigest()[:8]
            if action_hash in seen_hashes:
                return self._synthesize(
                    query,
                    evidence,
                    notes=f"Investigation loop detected at step {step} — stopping early.",
                )
            seen_hashes.add(action_hash)

            # Phase 3: gather evidence.
            snippet = self._gather(subquestion, context)
            if snippet:
                evidence.append(f"[Step {step}] {snippet}")

            # Phase 4: heuristic confidence (NFR-ORCH-015 — no LLM call).
            confidence = self._score_confidence(evidence)

            # Phase 5: high-confidence early stop.
            if confidence > _CONFIDENCE_HIGH:
                return self._synthesize(query, evidence)

            # Phase 6: low-confidence escalation at the early check step.
            if step >= _EARLY_CHECK_STEP and confidence < _CONFIDENCE_LOW:
                return self._escalate(query, evidence, step)

        # Budget exhausted (NFR-ORCH-014): synthesize what we have.
        return self._synthesize(
            query,
            evidence,
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

    def _gather(self, subquestion: str, context: dict) -> str:
        """Gather evidence for the subquestion via WebLookupSkill.

        Implements NFR-ORCH-015: uses WebLookupSkill as the evidence source.
        SSRF protection is inherited from WebLookupSkill / fetch_bytes
        (FR-SEC-005, FR-API-005).

        Args:
            subquestion: The question to look up.
            context: Current session context dict (passed through).

        Returns:
            Evidence snippet (up to 500 chars), or empty string on any failure.
        """
        try:
            from src.skills.web_lookup_skill import WebLookupSkill
            raw = WebLookupSkill().execute(
                subquestion, context.copy(), {"query": subquestion}
            )
            # Strip the stock "I checked the internet and found:" preamble.
            if "\n" in raw:
                raw = raw[raw.index("\n") + 1:].strip()
            return raw[:500]
        except Exception:
            return ""

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

    def _synthesize(
        self, query: str, evidence: list[str], notes: str = ""
    ) -> str:
        """Synthesize gathered evidence into a final answer.

        Uses force_route="general" for final synthesis (NFR-ORCH-015).
        Falls back to presenting raw evidence on router failure.

        Args:
            query: The original investigation question.
            evidence: All evidence snippets gathered across steps.
            notes: Optional notes to append (e.g., "budget exhausted").

        Returns:
            Synthesized answer string, or raw evidence on failure.
        """
        if not evidence:
            return (
                "I wasn't able to gather enough information to answer that question."
            )
        evidence_block = "\n".join(evidence)
        prompt = (
            f"Based on the following research evidence, answer concisely: {query}\n\n"
            f"Evidence:\n{evidence_block}"
        )
        if notes:
            prompt += f"\n\nNote: {notes}"
        try:
            from src.router import get_router
            return get_router().route(prompt, force_route="general", session_id=None)
        except Exception:
            return f"Here is what I found:\n\n{evidence_block}"

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
