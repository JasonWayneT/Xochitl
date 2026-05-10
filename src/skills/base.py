"""Base class for all Xochitl conversational skills."""
# Implements FR-ORCH-005 (tool_definition — each skill describes itself for the LLM)

from abc import ABC, abstractmethod


class Skill(ABC):
    """
    A skill is a conversational tool Xochitl can invoke.

    The LLM sees each skill's tool_definition() in the system prompt
    (via SkillManifestEngine) and may invoke it by emitting a
    <skill_call name="X">{}</skill_call> marker. The agent loop in
    chat.py parses that marker and calls execute() (FR-ORCH-005, FR-ORCH-008).

    can_handle() and suggest() are preserved for future use but are not
    called by the current agent loop.
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
