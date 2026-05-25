"""Post-execution reflection critic for Xochitl agent turns.

Implements FR-ORCH-037, FR-ORCH-038, NFR-ORCH-012, NFR-ORCH-013 (CR-019).

``TurnCritic`` provides lightweight self-critique for non-streaming turns.
It issues a structured critique prompt to the local LLM and categorises the
response as ``OK`` / ``CORRECTABLE`` / ``AMBIGUOUS``.

Trigger conditions (any one suffices):
- A skill was executed during the turn (``tool_calls_made=True``)
- Skill routing score was in the near-miss zone (0.20–0.65)
- Response contains hedging language (``_HEDGING_PATTERNS``)

Critique never runs on streaming turns (NFR-ORCH-013).  The entire critique
path in ``chat.py`` is wrapped in ``try/except`` — it must never crash the
main chat loop.

Usage::

    critic = TurnCritic()
    if critic.should_critique(top_score, tool_calls_made, response_text):
        result = critic.critique(goal=user_input, response=response_text, router=router)
        if result.verdict == "correctable":
            # retry with result.note injected into system prompt ...
        elif result.verdict == "ambiguous":
            # append caveat ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.router import TieredRouter

# ── Constants ─────────────────────────────────────────────────────────────────

# Thresholds — mirrors src/chat.py (kept local to avoid circular import)
_NEAR_MISS_LOW: float = 0.20    # _OPEN_ENDED_SCORE_THRESHOLD
_NEAR_MISS_HIGH: float = 0.65   # _SKILL_INJECT_THRESHOLD

# Maximum correction iterations before escalating to caveat (NFR-ORCH-012)
_MAX_CRITIC_ITERATIONS: int = 2

# Hedging patterns that signal LLM uncertainty (FR-ORCH-037 trigger c)
_HEDGING_PATTERNS: re.Pattern = re.compile(
    r"\b(i think|i believe|i'm not sure|i am not sure|not certain|might be|"
    r"could be|possibly|i'm uncertain|i am uncertain|may be|probably|"
    r"unclear to me|i don't know|i cannot confirm|i can't confirm)\b",
    re.IGNORECASE,
)

# Critic system prompt — instructs the model to reply with one structured line
_CRITIC_SYSTEM: str = (
    "You are a concise response quality critic. "
    "Evaluate the assistant response against the stated goal and reply with "
    "EXACTLY ONE LINE in one of these formats:\n"
    "  OK: <brief reason>\n"
    "  CORRECTABLE: <specific error or missing step, max 20 words>\n"
    "  AMBIGUOUS: <brief reason, max 15 words>\n"
    "No other output. No explanation. One line only."
)

_CRITIC_PROMPT_TMPL: str = (
    "GOAL: {goal}\n\n"
    "RESPONSE: {response}\n\n"
    "Verdict:"
)

# Truncation limits — keep the critic call cheap (NFR-ORCH-012)
_GOAL_LIMIT: int = 300
_RESPONSE_LIMIT: int = 600


# ── CritiqueResult ────────────────────────────────────────────────────────────


@dataclass
class CritiqueResult:
    """Structured output from a single critic evaluation.

    Attributes:
        verdict: One of ``"ok"``, ``"correctable"``, or ``"ambiguous"``.
        note:    Brief explanation from the critic (empty string on OK).
    """

    verdict: str  # "ok" | "correctable" | "ambiguous"
    note: str


# ── TurnCritic ────────────────────────────────────────────────────────────────


class TurnCritic:
    """Post-execution lightweight critic for Xochitl agent turns.

    Implements FR-ORCH-037 (trigger conditions) and FR-ORCH-038 (verdicts).
    Uses the local model (``force_route="simple_qa"``) to keep overhead minimal.
    """

    def should_critique(
        self,
        score: float,
        tool_calls_made: bool,
        response: str,
    ) -> bool:
        """Return True when the turn warrants post-execution reflection.

        Implements FR-ORCH-037 trigger conditions. At least one of:
        - A skill was executed during the turn (``tool_calls_made=True``)
        - Skill score was in the near-miss zone (0.20 ≤ score < 0.65)
        - Response contains hedging language

        Args:
            score:           Top skill ``can_handle()`` score for this turn.
            tool_calls_made: ``True`` if a skill was executed during the turn.
            response:        The LLM response text.

        Returns:
            ``True`` if critique should be run; ``False`` otherwise.
        """
        if tool_calls_made:
            return True
        if _NEAR_MISS_LOW <= score < _NEAR_MISS_HIGH:
            return True
        if _HEDGING_PATTERNS.search(response):
            return True
        return False

    def critique(
        self,
        goal: str,
        response: str,
        router: "TieredRouter",
    ) -> CritiqueResult:
        """Issue a structured critique of the given response against the goal.

        Uses ``force_route="simple_qa"`` (local model) to minimise latency.
        On parse failure or router error, returns ``OK`` conservatively so the
        critic never blocks a turn.

        Args:
            goal:     Original user request (truncated to ``_GOAL_LIMIT`` chars).
            response: The response to evaluate (truncated to ``_RESPONSE_LIMIT``).
            router:   ``TieredRouter`` instance for the LLM call.

        Returns:
            ``CritiqueResult`` with ``verdict`` in ``{"ok", "correctable", "ambiguous"}``.
        """
        prompt = _CRITIC_PROMPT_TMPL.format(
            goal=goal[:_GOAL_LIMIT],
            response=response[:_RESPONSE_LIMIT],
        )
        try:
            result = router.route(
                query=prompt,
                conversation_history=[],
                system_prompt=_CRITIC_SYSTEM,
                force_route="simple_qa",
            )
        except Exception:
            return CritiqueResult(verdict="ok", note="critic call failed")

        if result.error:
            return CritiqueResult(verdict="ok", note="critic call error")

        content = (result.content or "").strip()
        return _parse_critic_response(content)


# ── Parsing helper ────────────────────────────────────────────────────────────


def _parse_critic_response(content: str) -> CritiqueResult:
    """Parse a single-line critic response into a ``CritiqueResult``.

    Conservative: returns ``OK`` on any parse failure to avoid blocking turns.

    Args:
        content: Raw string from the critic LLM call.

    Returns:
        ``CritiqueResult`` with ``verdict`` and ``note``.
    """
    for line in content.splitlines():
        line = line.strip()
        upper = line.upper()
        if upper.startswith("OK:"):
            return CritiqueResult(verdict="ok", note=line[3:].strip())
        if upper.startswith("CORRECTABLE:"):
            return CritiqueResult(
                verdict="correctable",
                note=line[len("CORRECTABLE:"):].strip(),
            )
        if upper.startswith("AMBIGUOUS:"):
            return CritiqueResult(
                verdict="ambiguous",
                note=line[len("AMBIGUOUS:"):].strip(),
            )
    # Bare "OK" with no colon is still a valid pass verdict
    if content.upper().strip().startswith("OK"):
        return CritiqueResult(verdict="ok", note="response evaluated as correct")
    # Default to OK on parse failure — never block a turn
    return CritiqueResult(verdict="ok", note="could not parse critic response")
