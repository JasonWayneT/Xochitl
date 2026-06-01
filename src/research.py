"""Research mission coordination — budgeting, synthesis, adversarial review, conflict detection.

Implements:
  FR-RES-001  — Research Mission Budgeting (configurable time limit)
  FR-RES-002  — Multi-Source Synthesis (LLM-integrated coherent answer)
  FR-RES-003  — Adversarial Sounding Board (devil's advocate prompting)
  FR-RES-004  — Historical Conflict Detection (KB search + LLM verdict)
  FR-RES-009  — synthesize() accepts list[SourceRecord], injects [N] labels
  FR-RES-016  — ExplorerSkill delegates to run_research() (dead-code gap closed)
  FR-RES-017  — Cross-source agreement 1-5 scale → Confidence: HIGH/MEDIUM/LOW
  FR-RES-018  — Content-similarity dedup: >60% overlap → drop lower-trust source
  FR-RES-019  — Query intent classification → targeted synthesis format
  NFR-RES-001 — Budget enforcement (hard stop at time limit)
  NFR-RES-004 — Numbers and stats quoted verbatim from source text
  NFR-RES-005 — LOW confidence + <2 agreeing sources → structured insufficient-evidence block
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import get_research_time_limit
from src.research_types import SourceRecord


# ── FR-RES-001: Research Mission Budgeting ───────────────────────────────────

class ResearchMission:
    """Tracks a bounded research session with a configurable time budget."""

    def __init__(self, topic: str, time_limit_minutes: int | None = None) -> None:
        self.topic = topic
        self.time_limit_seconds = (time_limit_minutes or get_research_time_limit()) * 60
        self._started_at: float | None = None
        self.sources: list[dict] = []

    def start(self) -> None:
        self._started_at = time.monotonic()

    def time_remaining(self) -> float:
        if self._started_at is None:
            return self.time_limit_seconds
        elapsed = time.monotonic() - self._started_at
        return max(0.0, self.time_limit_seconds - elapsed)

    @property
    def is_over_budget(self) -> bool:
        return self.time_remaining() == 0.0

    def add_source(self, content: str, label: str = "") -> None:
        self.sources.append({
            "label": label,
            "content": content,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })

    def budget_summary(self) -> str:
        remaining = self.time_remaining()
        elapsed = self.time_limit_seconds - remaining
        return (
            f"{remaining:.0f}s remaining of {self.time_limit_seconds:.0f}s budget | "
            f"{len(self.sources)} source(s) | {elapsed:.0f}s elapsed"
        )


# ── Query intent classification (FR-RES-019) ─────────────────────────────────

_INTENT_PATTERNS = {
    "definition": (
        r"\bwhat is\b|\bdefine\b|\bmeaning of\b|\bexplain\b|\bwhat does .* mean\b"
    ),
    "steps": (
        r"\bhow to\b|\bhow do\b|\bsteps to\b|\bprocess for\b|\bprocedure\b|\bguide\b"
    ),
    "comparison": (
        r"\bvs\.?\b|\bversus\b|\bcompare\b|\bdifference between\b|\bbetter\b.*\bor\b"
    ),
    "verdict": (
        r"\bshould i\b|\bis it worth\b|\bwould you recommend\b|\bbest\b|\bworst\b|\bsafe\b"
    ),
    "timeline": (
        r"\bwhen did\b|\bhistory of\b|\btimeline\b|\bchronology\b|\bevolution of\b"
    ),
}

import re as _re


def classify_intent(query: str) -> str:
    """Classify query into one of: definition, steps, comparison, verdict, timeline, prose.

    Implements FR-RES-019.

    Args:
        query: User research question.

    Returns:
        Intent label string.
    """
    q = query.lower()
    for intent, pattern in _INTENT_PATTERNS.items():
        if _re.search(pattern, q):
            return intent
    return "prose"


# ── Deduplication (FR-RES-018) ────────────────────────────────────────────────

def _jaccard_similarity(a: str, b: str) -> float:
    """Character n-gram Jaccard similarity on first 500 chars."""
    n = 4
    def ngrams(s: str) -> set[str]:
        return {s[i:i+n] for i in range(len(s) - n + 1)}
    sa = ngrams(a[:500].lower())
    sb = ngrams(b[:500].lower())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def deduplicate_sources(sources: list[SourceRecord]) -> list[SourceRecord]:
    """Drop lower-trust sources that share >60% of their first 500 chars.

    Implements FR-RES-018.

    Args:
        sources: List of SourceRecord sorted by trust_score descending.

    Returns:
        Deduplicated list (highest-trust copy of near-duplicates retained).
    """
    kept: list[SourceRecord] = []
    for candidate in sources:
        is_dupe = False
        for existing in kept:
            sim = _jaccard_similarity(candidate.best_body, existing.best_body)
            if sim > 0.60:
                # Keep whichever has higher trust (sources already sorted by trust desc)
                is_dupe = True
                break
        if not is_dupe:
            kept.append(candidate)
    return kept


# ── FR-RES-009 / FR-RES-017: Multi-Source Synthesis with confidence ──────────

def synthesize(
    sources: list[SourceRecord] | list[str],
    query: str,
    mission: ResearchMission | None = None,
    intent: str = "prose",
) -> str:
    """Synthesize sources into a Perplexity-grade answer with inline [N] citations.

    Implements FR-RES-009, FR-RES-017, NFR-RES-004, NFR-RES-005.

    Args:
        sources: list[SourceRecord] (preferred) or legacy list[str].
        query: The research question.
        mission: Optional ResearchMission for budget enforcement.
        intent: Query intent label from classify_intent().

    Returns:
        Formatted synthesis with Confidence: line, inline citations, and sources block.
        Begins with ``Confidence: LOW — insufficient source agreement.`` when evidence is weak.
    """
    if not sources:
        return "No sources to synthesize."

    if mission and mission.is_over_budget:
        n = len(sources)
        return (
            f"Ay no — research time budget exhausted. "
            f"{n} source(s) collected but not synthesized. "
            f"Increase `research_time_limit_minutes` in config or provide fewer sources."
        )

    # Normalize to SourceRecord list
    records: list[SourceRecord]
    if sources and isinstance(sources[0], str):
        records = [
            SourceRecord(title=f"Source {i+1}", url="", domain="", body=s[:2000])
            for i, s in enumerate(sources)
        ]
    else:
        records = sources  # type: ignore[assignment]

    # FR-RES-018: deduplicate before synthesis
    records = deduplicate_sources(records)

    # Build labeled source block with [N] citations (FR-RES-009)
    source_blocks = []
    for i, rec in enumerate(records, 1):
        body_excerpt = rec.best_body[:2000]
        source_blocks.append(f"[{i}] {rec.title} ({rec.domain}):\n{body_excerpt}")
    combined = "\n\n---\n\n".join(source_blocks)

    # FR-RES-019: format instructions per intent
    format_instruction = {
        "definition": "Provide a clear definition with context.",
        "steps": "Produce a numbered list of steps.",
        "comparison": "Produce a markdown table comparing the options.",
        "verdict": (
            "Begin with a VERDICT: line (one sentence conclusion), "
            "then supporting evidence."
        ),
        "timeline": "Present events in chronological order.",
        "prose": "Write a structured prose answer.",
    }.get(intent, "Write a structured prose answer.")

    prompt = (
        f"You are a research synthesizer. Synthesize the following {len(records)} source(s) "
        f"to answer: {query}\n\n"
        f"{combined}\n\n"
        f"Instructions:\n"
        f"1. {format_instruction}\n"
        f"2. Cite sources inline using [N] labels wherever you use their content.\n"
        f"3. When using any specific number, percentage, or statistic from a source, "
        f"reproduce it EXACTLY — do not round, approximate, or paraphrase it. (NFR-RES-004)\n"
        f"4. On the FIRST line of your response, output: Agreement: N/5 "
        f"(1=strongly disagree, 5=strongly agree across sources).\n"
        f"5. Reconcile any disagreements explicitly."
    )

    from src.router import get_router
    result = get_router().route(
        query=prompt,
        conversation_history=[],
        system_prompt=(
            "You are a research synthesizer. Integrate multiple sources into a "
            "coherent, well-structured answer. Cite sources with [N] labels."
        ),
        force_route="architecture_planning",
    )
    content = result.content if not result.error else ""

    if not content:
        return f"Synthesis error: {result.error}"

    # Parse Agreement: N/5 from first line (FR-RES-017)
    lines = content.splitlines()
    agreement_score = 3  # default MEDIUM
    body_start = 0
    for i, line in enumerate(lines):
        match = _re.match(r"Agreement:\s*(\d)/5", line.strip(), _re.I)
        if match:
            agreement_score = int(match.group(1))
            body_start = i + 1
            break

    synthesis_body = "\n".join(lines[body_start:]).strip()

    # FR-RES-017: map agreement score to confidence label
    if agreement_score >= 4:
        confidence_label = "HIGH"
        confidence_reason = f"Sources broadly agree (agreement {agreement_score}/5)."
    elif agreement_score == 3:
        confidence_label = "MEDIUM"
        confidence_reason = f"Sources partially agree (agreement {agreement_score}/5)."
    else:
        confidence_label = "LOW"
        confidence_reason = f"Sources disagree or are insufficient (agreement {agreement_score}/5)."

    # NFR-RES-005: low confidence + <2 sources → structured insufficient-evidence block
    if confidence_label == "LOW" and len(records) < 2:
        header = (
            f"Confidence: LOW — insufficient source agreement. "
            f"Here is what I found, but treat this with caution."
        )
    else:
        header = f"Confidence: {confidence_label} — {confidence_reason}"

    # Build numbered sources block (FR-RES-010)
    sources_block_lines = ["\n\n**Sources:**"]
    for i, rec in enumerate(records, 1):
        sources_block_lines.append(rec.sources_line(i))
    sources_block = "\n".join(sources_block_lines)

    return f"{header}\n\n{synthesis_body}{sources_block}"


# ── FR-RES-003: Adversarial Sounding Board ────────────────────────────────────

def adversarial_review(claim: str, context: str = "") -> str:
    """Challenge a claim or plan from an adversarial perspective. Implements FR-RES-003."""
    ctx_block = f"\nCONTEXT:\n{context}\n" if context else ""
    prompt = (
        f"You are a rigorous devil's advocate. Challenge the following claim by identifying "
        f"weaknesses, hidden assumptions, edge-case failures, and unstated costs.\n\n"
        f"CLAIM:\n{claim}"
        f"{ctx_block}\n"
        f"Provide exactly 3–5 numbered challenges, then a one-line verdict: "
        f"SOLID / HAS GAPS / FLAWED — with a one-sentence justification."
    )

    from src.router import get_router
    result = get_router().route(
        query=prompt,
        conversation_history=[],
        system_prompt=(
            "You are a critical thinking partner who helps refine ideas through "
            "adversarial review. Be specific, fair, and constructive."
        ),
        force_route="architecture_planning",
    )
    return result.content if not result.error else f"Review error: {result.error}"


# ── FR-RES-004: Historical Conflict Detection ─────────────────────────────────

def detect_conflicts(new_info: str, kb_dir: Optional[Path] = None) -> list[dict]:
    """Cross-reference new information against the KB for contradictions. Implements FR-RES-004."""
    from src.memory import KnowledgeBase
    from src.router import get_router

    candidates = KnowledgeBase(kb_dir).search(new_info, max_results=5)
    if not candidates:
        return []

    router = get_router()
    conflicts: list[dict] = []

    for entry in candidates:
        prompt = (
            f"Does the NEW INFO contradict the EXISTING RECORD?\n"
            f"Reply with exactly one label — CONFLICT, CONSISTENT, or UNRELATED — "
            f"followed by a single sentence of reasoning.\n\n"
            f"NEW INFO:\n{new_info[:500]}\n\n"
            f"EXISTING RECORD:\n{entry['content'][:500]}"
        )
        result = router.route(
            query=prompt,
            conversation_history=[],
            force_route="simple_qa",
        )
        if result.error:
            continue
        verdict = result.content.strip()
        if verdict.upper().startswith("CONFLICT"):
            conflicts.append({
                "source": entry.get("path") or entry.get("title", "?"),
                "existing_snippet": entry["content"][:200],
                "verdict": verdict,
            })

    return conflicts


# ── Convenience: run a full research session (FR-RES-016) ────────────────────

def run_research(
    topic: str,
    sources: list[SourceRecord] | list[str] | None = None,
    adversarial: bool = False,
    check_conflicts: bool = False,
    time_limit_minutes: int | None = None,
    intent: str = "prose",
) -> dict:
    """Run a bounded research session and return a structured result dict.

    Implements FR-RES-016 — ExplorerSkill delegates here instead of its own _synthesize().

    Args:
        topic: Research question / topic.
        sources: Pre-fetched SourceRecord list or bare strings.
        adversarial: If True, run adversarial_review() on the synthesis.
        check_conflicts: If True, detect_conflicts() against KB.
        time_limit_minutes: Override config time limit.
        intent: Query intent label (from classify_intent).

    Returns:
        Dict with keys: topic, budget, synthesis, adversarial, conflicts.
    """
    mission = ResearchMission(topic, time_limit_minutes)
    mission.start()

    all_sources: list[SourceRecord] | list[str] = sources or []

    # Legacy bare-string path: add to mission tracking
    if all_sources and isinstance(all_sources[0], str):
        for s in all_sources:
            if mission.is_over_budget:
                break
            mission.add_source(s)

    result: dict = {
        "topic": topic,
        "budget": mission.budget_summary(),
        "synthesis": "",
        "adversarial": "",
        "conflicts": [],
        "confidence": "LOW",
    }

    if all_sources:
        result["synthesis"] = synthesize(all_sources, topic, mission, intent=intent)
        # Extract confidence label from synthesis header
        first_line = result["synthesis"].splitlines()[0] if result["synthesis"] else ""
        if "HIGH" in first_line:
            result["confidence"] = "HIGH"
        elif "MEDIUM" in first_line:
            result["confidence"] = "MEDIUM"
        else:
            result["confidence"] = "LOW"

    if adversarial and not mission.is_over_budget:
        result["adversarial"] = adversarial_review(result["synthesis"] or topic)

    if check_conflicts and not mission.is_over_budget:
        result["conflicts"] = detect_conflicts(topic)

    return result
