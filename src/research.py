"""Research mission coordination — budgeting, synthesis, adversarial review, conflict detection."""
# Implements FR-RES-001 (Research Mission Budgeting — configurable time limit from config)
# Implements FR-RES-002 (Multi-Source Synthesis — LLM-integrated coherent answer)
# Implements FR-RES-003 (Adversarial Sounding Board — devil's advocate prompting)
# Implements FR-RES-004 (Historical Conflict Detection — KB search + LLM verdict)
# Implements NFR-RES-001 (Budget enforcement — hard stop at time limit)

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import get_research_time_limit


# ── FR-RES-001: Research Mission Budgeting ────────────────────────────────────

class ResearchMission:
    """Tracks a bounded research session with a configurable time budget."""

    def __init__(self, topic: str, time_limit_minutes: int | None = None) -> None:
        # Implements FR-RES-001, NFR-RES-001
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


# ── FR-RES-002: Multi-Source Synthesis ───────────────────────────────────────

def synthesize(
    sources: list[str],
    query: str,
    mission: ResearchMission | None = None,
) -> str:
    """Synthesize multiple sources into a coherent answer. Implements FR-RES-002."""
    if not sources:
        return "No sources to synthesize."

    if mission and mission.is_over_budget:
        n = len(sources)
        return (
            f"Ay no — research time budget exhausted. "
            f"{n} source(s) collected but not synthesized. "
            f"Increase `research_time_limit_minutes` in config or provide fewer sources."
        )

    combined = "\n\n---\n\n".join(
        f"Source {i + 1}:\n{s[:2000]}" for i, s in enumerate(sources)
    )
    prompt = (
        f"Synthesize the following {len(sources)} source(s) to answer: {query}\n\n"
        f"{combined}\n\n"
        f"Provide a coherent, integrated answer that explicitly reconciles any differences between sources."
    )

    from src.router import get_router
    result = get_router().route(
        query=prompt,
        conversation_history=[],
        system_prompt=(
            "You are a research synthesizer. Integrate multiple sources into a "
            "coherent, well-structured answer. Note disagreements explicitly."
        ),
        force_route="architecture_planning",
    )
    return result.content if not result.error else f"Synthesis error: {result.error}"


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


# ── Convenience: run a full research session ──────────────────────────────────

def run_research(
    topic: str,
    sources: list[str] | None = None,
    adversarial: bool = False,
    check_conflicts: bool = False,
    time_limit_minutes: int | None = None,
) -> dict:
    """Run a bounded research session and return a structured result dict."""
    mission = ResearchMission(topic, time_limit_minutes)
    mission.start()

    for s in (sources or []):
        if mission.is_over_budget:
            break
        mission.add_source(s)

    result: dict = {
        "topic": topic,
        "budget": mission.budget_summary(),
        "synthesis": "",
        "adversarial": "",
        "conflicts": [],
    }

    if mission.sources:
        contents = [s["content"] for s in mission.sources]
        result["synthesis"] = synthesize(contents, topic, mission)

    if adversarial and not mission.is_over_budget:
        result["adversarial"] = adversarial_review(result["synthesis"] or topic)

    if check_conflicts and not mission.is_over_budget:
        result["conflicts"] = detect_conflicts(topic)

    return result
