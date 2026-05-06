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

        Implements FR-ORCH-005. Required keys:
          name        — class name matching <skill_call name="...">
          description — one sentence describing what the skill does
          when        — natural language trigger conditions for the LLM
          params      — dict of {param_name: "description | options"}
        """
