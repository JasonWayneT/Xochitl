"""Base class for all Xochitl conversational skills."""

from abc import ABC, abstractmethod


class Skill(ABC):
    """
    A skill is a conversational tool Xochitl can suggest and execute.

    Xochitl scores every skill on each user message. If the top score
    exceeds 0.6 she surfaces a suggestion. The user then chooses whether
    to proceed, and only then does execute() run.
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
