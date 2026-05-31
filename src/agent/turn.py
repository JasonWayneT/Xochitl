"""AgentTurnInput and TurnResult — the I/O contract for the agent pipeline.

Every field in AgentTurnInput maps to a self.* access that _agent_loop()
previously read directly from XochitlChat. The dataclass makes the dependency
graph explicit and allows the pipeline stages to be tested without the full
chat session object.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.skills.base import Skill


@dataclass
class AgentTurnInput:
    """All inputs the pipeline needs for one agent turn.

    Args:
        user_input: Raw user message for this turn.
        system_prompt: Fully assembled system prompt (ContextManager output).
        messages: Conversation history slice formatted for the LLM.
        skills: Live skill list for scoring and dispatch.
        current_project: Active project ID, or None.
        force_cloud: When True, always route to cloud LLM.
        stream: When True, emit tokens live to the terminal.
        context: Mutable session context dict; skills write into it in place.
        skill_score_cache: Optional (skill_name, score) tuple cached from a
            prior scoring pass on the same input. None forces a fresh score.
        score_cache_key: Hash key that was used to produce skill_score_cache.
    """
    user_input: str
    system_prompt: str
    messages: list[dict]
    skills: list[Skill]
    current_project: str | None
    force_cloud: bool
    stream: bool
    context: dict = field(default_factory=dict)
    session_history: list[dict] = field(default_factory=list)
    skill_score_cache: tuple[str, float] | None = None
    score_cache_key: tuple | None = None
    governor_force: str | None = None  # FR-ORCH-025: force_route from SessionGovernor


@dataclass
class TurnResult:
    """Output of one agent turn returned to the session loop.

    Args:
        response: Final text response to display (skill output already appended).
        was_streamed: True when tokens were emitted live during this turn.
        skill_fired: Name of the skill that executed, or None.
        new_score_cache: Score cache entry to persist on XochitlChat for reuse.
        new_score_cache_key: The key paired with new_score_cache.
        last_mutating_skill: Skill name if a mutating skill ran (drives CM cache
            invalidation); empty string otherwise.
    """
    response: str
    was_streamed: bool = False
    skill_fired: str | None = None
    new_score_cache: tuple[str, float] | None = None
    new_score_cache_key: tuple | None = None
    last_mutating_skill: str = ""
