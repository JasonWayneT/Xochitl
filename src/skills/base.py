"""Base class for all Xochitl conversational skills."""
# Implements FR-ORCH-005 (tool_definition — each skill describes itself for the LLM)

from abc import ABC, abstractmethod


class Skill(ABC):
    """
    A skill is a conversational tool Xochitl can suggest and execute.

    Xochitl scores every skill on each user message. If the top score
    exceeds 0.6 she surfaces a suggestion. The user then chooses whether
    to proceed, and only then does execute() run.

    Skills also expose tool_definition() so the LLM knows when and how
    to invoke them via <skill_call> markers (FR-ORCH-005, FR-ORCH-008).
    """

    @abstractmethod
    def can_handle(self, user_input: str, context: dict) -> float:
        """Return confidence (0.0–1.0) that this skill applies to the message."""

    @abstractmethod
    def suggest(self, user_input: str, context: dict) -> str:
        """Return the suggestion message Xochitl shows to the user."""

    @abstractmethod
    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Run the skill after the user confirms. Returns response text."""

    @abstractmethod
    def tool_definition(self) -> dict:
        """Return a descriptor dict for LLM system prompt injection.

        Implements FR-ORCH-005, FR-ORCH-039. Required keys:
          name        — class name matching <skill_call name="...">
          description — one sentence describing what the skill does
          when        — natural language trigger conditions for the LLM
          params      — dict of {param_name: "description | options"}
          examples    — list of ≥3 verbatim user phrases that trigger this skill
                        (injected into active-skill block so LLM has concrete reference)
        """

    def cleanup(self) -> None:
        """Release resources after a timeout or cancellation. FR-RELY-004.

        Called by _execute_skill_safe() in a short-lived thread (5s join max) when
        skill.execute() exceeds its timeout. Default is a no-op; override in skills
        that hold external connections or long-running sub-processes.

        Returns:
            None — any exception is silently suppressed by the caller.
        """

    def health_check(self) -> bool:
        """Return True if this skill is ready to execute. FR-HARD-010, FR-JARV-007.

        Override in skills that depend on external credentials or tokens.
        The default implementation always returns True (no health requirements).
        Called once at session start; False result queues a SKILL_HEALTH signal.

        Returns:
            True if the skill can execute normally; False if credentials are missing
            or the skill is otherwise unavailable.
        """
        return True
