"""ResearchSkill — Perplexity-grade research pipeline entry point (CR-053 Phase 5).

Implements:
  FR-RES-020 — ResearchSkill with 0.90 confidence score on deep-research triggers
  FR-RES-021 — Live streaming progress via context["status_cb"]
  FR-RES-022 — Context-aware follow-ups via context["last_research_topic"]
  FR-RES-023 — Adversarial review for verdict/single-claim answers
  FR-ROUTE-004 — Context-aware follow-up boost (CR-054 Phase 2)
"""
from __future__ import annotations

from src.skills.base import Skill
from src.research_types import SourceRecord

# FR-RES-020: high-confidence trigger phrases for ResearchSkill
_RESEARCH_TRIGGERS = (
    "research",
    "what does the research say",
    "give me a confident answer",
    "deep research on",
    "summarize what's known about",
    "deep dive",
    "thorough analysis",
    "comprehensive review",
)

# FR-ROUTE-004: follow-up phrases for context-aware boost
_FOLLOWUP_PHRASES = (
    "what about",
    "and in",
    "how about",
    "same for",
    "what about in",
)


class ResearchSkill(Skill):
    """Orchestrates a Perplexity-grade multi-source research pipeline.

    Returns a direct answer with inline [N] citations, a Confidence: rating,
    and a numbered sources block.  Registered after ExplorerSkill so it does
    not shadow ExplorerSkill's multi-hop investigation mode.

    Implements FR-RES-020 through FR-RES-023.
    """

    def can_handle(self, user_input: str, context: dict) -> float:
        """Score research intent, with context-aware follow-up boost.

        Implements FR-RES-020, FR-ROUTE-004.

        Args:
            user_input: Raw user message.
            context: Session context dict.

        Returns:
            0.90 for high-confidence trigger phrases, 0.75 for follow-up boost,
            0.0 otherwise.
        """
        q = user_input.lower()
        # FR-ROUTE-004: context-aware follow-up boost
        if (
            len(user_input.split()) <= 8
            and any(phrase in q for phrase in _FOLLOWUP_PHRASES)
            and context.get("last_skill_fired") == "ResearchSkill"
        ):
            return 0.75
        if any(trigger in q for trigger in _RESEARCH_TRIGGERS):
            return 0.90
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        return (
            "I can run a deep research pipeline — multiple sources, "
            "citations, and a confidence rating. Want me to go deep on this?"
        )

    def tool_definition(self) -> dict:
        return {
            "name": "ResearchSkill",
            "description": (
                "Runs a Perplexity-grade research pipeline: fetches 6 sources, "
                "synthesizes with inline citations, rates confidence, and returns "
                "a direct answer with a numbered sources block."
            ),
            "when": (
                "user asks for deep research, wants a confident cited answer, "
                "or explicitly says 'research', 'what does the research say', "
                "'give me a confident answer', 'deep research on', "
                "or 'summarize what's known about'"
            ),
            "domain": "research",
            "params": {
                "query": "The research question or topic",
            },
            "timeout_secs": 120,
            "examples": [
                "research the long-term effects of intermittent fasting",
                "what does the research say about melatonin and sleep?",
                "give me a confident answer on climate change projections",
                "deep research on microplastics in drinking water",
                "summarize what's known about ADHD medication in adults",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Run the full research pipeline and return a cited, confidence-rated answer.

        Implements FR-RES-021, FR-RES-022, FR-RES-023.

        Args:
            user_input: Raw user message.
            context: Session context dict; reads last_research_topic, last_skill_fired.
            params: Skill params; expects {"query": "..."}.

        Returns:
            Synthesis with Confidence:, inline citations, and sources block.
        """
        query = (params.get("query") or user_input).strip()
        if not query:
            return "I need a research question."

        status_cb = context.get("status_cb")

        # FR-RES-022: context-aware follow-up — prepend prior topic when query is short
        prior_topic = context.get("last_research_topic", "")
        if prior_topic and len(query.split()) < 8:
            q_lower = query.lower()
            if not any(q_lower.startswith(t) for t in _RESEARCH_TRIGGERS):
                query = f"{prior_topic} — {query}"

        def _status(msg: str) -> None:
            if status_cb and callable(status_cb):
                try:
                    status_cb(msg)
                except Exception:
                    pass

        _status("Searching...")

        # Phase 1: decompose query
        try:
            from src.query_planner import decompose_query, rewrite_for_search
            sub_queries = decompose_query(query)
        except Exception:
            sub_queries = [query]
            rewrite_for_search = lambda q: q  # noqa: E731

        # Phase 2: gather sources for each sub-query
        from src.skills.web_lookup_skill import WebLookupSkill
        wls = WebLookupSkill()
        all_sources: list[SourceRecord] = []

        for sq in sub_queries:
            _status(f"Searching: {sq[:60]}...")
            ctx_copy = context.copy()
            try:
                wls.execute(sq, ctx_copy, {"query": sq})
                recs: list[SourceRecord] = ctx_copy.get("research_sources", [])
                for rec in recs:
                    _status(f"Reading {rec.domain}...")
                all_sources.extend(recs)
            except Exception:
                continue

        if not all_sources:
            return "I couldn't retrieve any sources for that research question."

        _status(f"Synthesizing {len(all_sources)} sources...")

        # Phase 3: classify intent and synthesize
        from src.research import classify_intent, run_research, adversarial_review
        intent = classify_intent(query)

        result = run_research(
            topic=query,
            sources=all_sources,
            adversarial=False,
            intent=intent,
        )
        synthesis = result["synthesis"]

        # FR-RES-023: adversarial review for verdict/single-claim answers
        if intent in ("verdict",) or result.get("confidence") == "HIGH":
            try:
                adv = adversarial_review(synthesis, context=query)
                if adv and not adv.startswith("Review error"):
                    synthesis += f"\n\n**Note (adversarial check):** {adv.splitlines()[0]}"
            except Exception:
                pass

        # FR-RES-022: persist last research topic for follow-up turns
        context["last_research_topic"] = query

        return synthesis
