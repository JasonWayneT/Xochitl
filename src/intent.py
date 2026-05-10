"""Structured conversational intent classification for Xochitl.

Implements FR-ORCH-010 and supports NFR-PERF-007 by deciding the smallest
useful context scope before tool selection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Optional


FILE_EXTENSIONS = (
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv",
    ".env", ".html", ".css", ".js", ".ts", ".tsx", ".jsx", ".pdf",
)
FILE_READ_KEYWORDS = (
    "read", "open", "show", "look at", "inspect", "view", "list",
    "what's in", "whats in", "find", "search",
)
FILE_WRITE_KEYWORDS = (
    "write", "create", "edit", "update", "change", "append", "save",
    "generate", "implement", "fix",
)
FILE_DELETE_KEYWORDS = ("delete", "remove", "rm ", "erase")
TASK_KEYWORDS = (
    "task", "queue", "today", "priority", "priorities", "done",
    "complete", "blocked", "in progress", "what should i do",
)
RESEARCH_KEYWORDS = (
    "research", "look up", "market", "competitor", "deep dive",
    "adversarial", "devil's advocate", "devil advocate",
)
BMAD_SDD_KEYWORDS = (
    "bmad", "sdd", "spec", "requirements", "traceability", "prd",
    "architecture", "design doc", "story", "epic", "sprint",
)
EXPLORATION_KEYWORDS = (
    "understand", "explore", "walk me through", "explain this repo",
    "explain this project", "how does this work", "map out",
    "read through", "codebase",
)
EXECUTION_KEYWORDS = (
    "fix", "implement", "build", "add", "change", "refactor",
    "delete", "remove", "run", "execute", "sync", "push", "pull",
)
PRODUCTIVITY_KEYWORDS = (
    "today", "priority", "priorities", "plan my day", "what should i do",
    "get organized", "focus", "next action", "task", "queue",
)
SOUNDING_BOARD_KEYWORDS = (
    "sounding board", "think through", "help me decide", "should i",
    "am i thinking", "does this make sense", "push back",
)
EMOTIONAL_KEYWORDS = (
    "stuck", "overwhelmed", "anxious", "frustrated", "tired",
    "dragging", "burned out", "burnt out",
)
SKILL_KEYWORDS = (
    "make this a skill", "create a skill", "turn this into a skill",
    "reusable workflow", "do this often",
)
EXTERNAL_SIDE_EFFECT_KEYWORDS = (
    "sync", "push to notion", "pull from notion", "send", "email",
    "publish", "post",
)


@dataclass(frozen=True)
class ConversationIntent:
    """Structured intent used before routing and tool selection."""

    type: str
    intent_type: str
    action_risk: str
    context_scope: str
    requires_bmad_sdd: bool
    confidence: float
    operation: Optional[str] = None
    adversarial: bool = False
    clarifying_question: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def classify_conversation_intent(
    user_input: str,
    *,
    current_project: Optional[str] = None,
) -> ConversationIntent:
    """Classify a user message into structured conversational intent."""
    q = user_input.lower().strip()
    has_file = _has_file_reference(user_input)
    has_bmad = _contains_any(q, BMAD_SDD_KEYWORDS)
    has_project = current_project is not None

    if _contains_any(q, SKILL_KEYWORDS):
        return _intent("general", "skill_learning", "state_change", "global", False, 0.95)

    if has_file or _looks_like_file_operation(q):
        operation, risk = _file_operation_and_risk(q)
        return _intent(
            "file_operation",
            "exploration" if operation == "read" else "execution",
            risk,
            "explicit_files",
            has_bmad,
            0.95,
            operation=operation,
        )

    if _contains_any(q, RESEARCH_KEYWORDS):
        return _intent(
            "research", "exploration", "read_only", "memory_bank", False, 0.9,
            adversarial=_contains_any(q, ("devil", "adversarial", "challenge", "poke holes", "stress test", "steelman")),
        )

    if _contains_any(q, PRODUCTIVITY_KEYWORDS):
        return _intent(
            "task_query" if _contains_any(q, TASK_KEYWORDS) else "general",
            "productivity",
            "state_change" if _is_task_mutation(q) else "read_only",
            "global",
            False,
            0.9,
        )

    if _contains_any(q, SOUNDING_BOARD_KEYWORDS):
        return _intent("general", "sounding_board", "read_only", "global", False, 0.9)

    if has_bmad:
        return _intent(
            "general",
            "planning" if not _contains_any(q, EXECUTION_KEYWORDS) else "execution",
            _risk_for_execution(q),
            "active_project" if has_project else "global",
            True,
            0.9,
        )

    if _contains_any(q, EXPLORATION_KEYWORDS):
        return _intent(
            "general",
            "exploration",
            "read_only",
            "active_project" if has_project or "repo" in q or "codebase" in q or "project" in q else "global",
            False,
            0.85,
        )

    if _contains_any(q, EXECUTION_KEYWORDS):
        return _intent(
            "general",
            "execution",
            _risk_for_execution(q),
            "active_project" if has_project else "global",
            has_bmad or _looks_like_coding_request(q),
            0.82,
            clarifying_question=_mutation_clarifier(q),
        )

    if _contains_any(q, EMOTIONAL_KEYWORDS):
        return _intent("general", "emotional", "read_only", "global", False, 0.85)

    if q in {"hi", "hello", "hey", "hola"}:
        return _intent("general", "casual", "read_only", "global", False, 0.95)

    short = len(q.split()) <= 2
    return _intent(
        "general",
        "clarification" if short else "casual",
        "read_only",
        "global",
        False,
        0.6 if short else 0.75,
        clarifying_question="What would you like me to help with?" if short else None,
    )


def _intent(
    legacy_type: str,
    intent_type: str,
    action_risk: str,
    context_scope: str,
    requires_bmad_sdd: bool,
    confidence: float,
    *,
    operation: Optional[str] = None,
    adversarial: bool = False,
    clarifying_question: Optional[str] = None,
) -> ConversationIntent:
    return ConversationIntent(
        type=legacy_type,
        intent_type=intent_type,
        action_risk=action_risk,
        context_scope=context_scope,
        requires_bmad_sdd=requires_bmad_sdd,
        confidence=confidence,
        operation=operation,
        adversarial=adversarial,
        clarifying_question=clarifying_question,
    )


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _has_file_reference(user_input: str) -> bool:
    q = user_input.lower()
    if any(ext in q for ext in FILE_EXTENSIONS):
        return True
    if "\\" in user_input:
        return True
    if re.search(r"\b[a-z]:[/\\]", q):
        return True
    return bool(re.search(r"\b(?:docs|src|tests|config|projects|archive|prompts)/", q))


def _looks_like_file_operation(q: str) -> bool:
    if not _contains_any(q, FILE_READ_KEYWORDS + FILE_WRITE_KEYWORDS + FILE_DELETE_KEYWORDS):
        return False
    return _contains_any(q, ("file", "folder", "directory", "path", "repo", "codebase"))


def _file_operation_and_risk(q: str) -> tuple[str, str]:
    if _contains_any(q, FILE_DELETE_KEYWORDS):
        return "delete", "file_delete"
    if _contains_any(q, FILE_WRITE_KEYWORDS):
        return "write", "file_write"
    return "read", "read_only"


def _is_task_mutation(q: str) -> bool:
    return _contains_any(q, ("done", "complete", "mark", "add task", "create task", "update task"))


def _risk_for_execution(q: str) -> str:
    if _contains_any(q, FILE_DELETE_KEYWORDS):
        return "file_delete"
    if _contains_any(q, EXTERNAL_SIDE_EFFECT_KEYWORDS):
        return "external_side_effect"
    if _contains_any(q, ("run", "execute", "command", "script")):
        return "command_execution"
    if _contains_any(q, ("fix", "implement", "refactor", "change", "update", "create", "write")):
        return "file_write"
    return "state_change"


def _looks_like_coding_request(q: str) -> bool:
    return _contains_any(q, ("code", "repo", "bug", "function", "class", "test", "auth", "database", "api"))


def _mutation_clarifier(q: str) -> Optional[str]:
    if _looks_like_coding_request(q):
        return None
    return "What should I change, and where should I make that change?"
