"""Progressive personalization milestone engine.

Implements FR-PREF-004 (milestone classification by session count) and
FR-PREF-005 (milestone context block for assemble_system_prompt).

Three tiers gate progressively warmer behavior as the relationship matures:
  M1 (sessions 1-5):  formal, minimal assumptions, no proactive anticipation.
  M2 (sessions 6-20): stored preferences referenced, first name used naturally,
                       in-session follow-ups enabled.
  M3 (sessions 21+):  natural memory reference active, anticipation gate on,
                       milestone-aware brief format.

Transitions are always silent (NFR-PREF-002): logged at DEBUG level only,
never surfaced to the user as text.
"""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)

# Milestone boundaries (inclusive upper bounds for M1 and M2).
_M1_MAX_SESSIONS: int = 5
_M2_MAX_SESSIONS: int = 20


class Milestone(str, Enum):
    """Personalization tier based on total session count."""

    M1 = "M1"  # sessions 1-5
    M2 = "M2"  # sessions 6-20
    M3 = "M3"  # sessions 21+


# Context blocks injected into assemble_system_prompt() for each milestone.
# M1 is intentionally empty — new-user behavior is the default; adding a block
# would risk priming the model toward false familiarity.
_MILESTONE_BLOCKS: dict[Milestone, str] = {
    Milestone.M1: "",
    Milestone.M2: (
        "## Personalization\n"
        "You have been working with this user for several sessions. "
        "Reference stored preferences naturally without announcing that you remember them. "
        "Use the user's first name when it feels conversational. "
        "In-session follow-ups are appropriate."
    ),
    Milestone.M3: (
        "## Personalization\n"
        "You have a well-established working relationship with this user. "
        "Draw on memory facts conversationally — never announce that you remember them. "
        "Proactive anticipation is appropriate: surface relevant context before being asked. "
        "Keep output concise and preference-aligned."
    ),
}


def get_milestone(session_count: int) -> Milestone:
    """Classify the current session into a personalization tier (FR-PREF-004).

    Pure function — no DB access, no side effects.

    Args:
        session_count: Total number of sessions ever started, including the
            current one. Typically the row count of the ``sessions`` table
            after ``create_session()`` is called.

    Returns:
        The appropriate ``Milestone`` enum value for this session count.
    """
    if session_count <= _M1_MAX_SESSIONS:
        return Milestone.M1
    if session_count <= _M2_MAX_SESSIONS:
        return Milestone.M2
    return Milestone.M3


def milestone_context_block(milestone: Milestone) -> str:
    """Return the system-prompt context block for this milestone (FR-PREF-005).

    Pure function — no DB access, no side effects.
    M1 returns an empty string (default behavior, no extra block injected).

    Args:
        milestone: The current ``Milestone`` tier.

    Returns:
        A system-prompt block string (may be empty for M1).
    """
    return _MILESTONE_BLOCKS[milestone]
