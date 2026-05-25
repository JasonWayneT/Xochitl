"""Response mode inference and system-prompt block injection.

Implements FR-ORCH-032, FR-ORCH-033 (CR-025).

Three named response modes control how Xochitl formats output:

``conversational`` (default)
    Xochitl's natural voice — warm, exploratory, full persona. No extra
    system-prompt block injected (the default voice is already conversational).

``operator``
    Triggered by short imperative commands ("sync", "build", "run").
    Injects a system-prompt block that directs Xochitl to lead with the
    action, skip preamble, and avoid hedging language.

``report``
    Triggered by structure/summary keywords ("report", "summarize",
    "overview"). Injects a system-prompt block that directs Xochitl to
    use ## headers and bullet points with no personality filler.

Usage::

    from src.response_mode import infer_mode, mode_block, MODE_OPERATOR

    mode = infer_mode(user_input)          # one of the three MODE_* constants
    block = mode_block(mode)               # "" for conversational, else prompt text
    system_prompt += "\\n\\n" + block      # append to assembled system prompt
"""

from __future__ import annotations

import re

__all__ = [
    "MODE_CONVERSATIONAL",
    "MODE_OPERATOR",
    "MODE_REPORT",
    "infer_mode",
    "mode_block",
]

# ── Mode constants ────────────────────────────────────────────────────────────

MODE_CONVERSATIONAL: str = "conversational"
MODE_OPERATOR: str = "operator"
MODE_REPORT: str = "report"

# ── System prompt blocks ──────────────────────────────────────────────────────

_OPERATOR_MODE_BLOCK: str = """\
[RESPONSE MODE: OPERATOR]
You are in operator mode. Lead immediately with the action taken or planned.
Be concise and imperative. No preamble. No hedging. No explanatory filler.
Good: "Done. 3 tasks synced to Notion."
Good: "Created task: Build auth module. Added to queue at position 2."
Bad: "I have successfully completed the synchronization of your tasks to Notion."
Bad: "Sure! I'll help you with that. Let me go ahead and..."
One sentence per result. State what happened, what changed, what's next."""

_REPORT_MODE_BLOCK: str = """\
[RESPONSE MODE: REPORT]
You are in report mode. Use structured output with ## headers and bullet points.
Lead with the most actionable section first.
Use ✓ for completed items, → for actions needed, ⚠ for warnings, ✗ for failures.
No personality filler. No warm-up sentences. Start directly with the first section header.
Keep each bullet under 80 characters for terminal readability."""

# ── Inference patterns ────────────────────────────────────────────────────────

# Command verbs that strongly signal OPERATOR mode when they start an utterance.
# Only matched at the beginning of the input (after optional "!", whitespace, or "please").
_OPERATOR_VERBS: frozenset[str] = frozenset({
    "sync", "run", "do", "execute", "start", "stop",
    "create", "delete", "remove", "add", "update",
    "push", "pull", "mark", "complete", "build",
    "generate", "init", "initialize", "reset", "refresh",
    "check", "fetch", "get", "deploy", "install", "uninstall",
    "enable", "disable", "restart", "reload", "clear",
})

# Compiled pattern: optional "!" / "please" prefix, then a command verb word-boundary
_OPERATOR_LEADING_VERB: re.Pattern[str] = re.compile(
    r"^(?:!|please\s+)?(?P<verb>"
    + "|".join(re.escape(v) for v in sorted(_OPERATOR_VERBS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

# Keywords / phrases that signal REPORT mode anywhere in the utterance.
_REPORT_TERMS: frozenset[str] = frozenset({
    "report",
    "summary",
    "summarize",
    "summarise",
    "overview",
    "breakdown",
    "status report",
    "give me a report",
    "show me a report",
    "give me a summary",
    "show me a summary",
    "give me an overview",
    "list all",
    "list my",
    "list the",
    "what are all",
    "what's the status",
    "whats the status",
})

# Utterance length above which OPERATOR mode is not inferred from a leading verb
# alone (long utterances are more likely conversational requests, not commands).
_MAX_OPERATOR_WORDS: int = 15


def infer_mode(user_input: str) -> str:
    """Infer the response mode for a user utterance.

    Uses lightweight regex/keyword heuristics — no LLM call (NFR-ORCH-008).
    Errs toward ``conversational`` on ambiguous input to avoid disruptive
    mode changes when intent is unclear.

    Args:
        user_input: The raw user message for the current turn.

    Returns:
        One of ``MODE_CONVERSATIONAL``, ``MODE_OPERATOR``, or ``MODE_REPORT``.
    """
    stripped = user_input.strip()
    if not stripped:
        return MODE_CONVERSATIONAL

    lowered = stripped.lower()

    # ── REPORT: keyword match anywhere in the utterance ───────────────────────
    for term in _REPORT_TERMS:
        if term in lowered:
            return MODE_REPORT

    # ── OPERATOR: leading command verb in a short utterance ───────────────────
    word_count = len(stripped.split())
    if word_count <= _MAX_OPERATOR_WORDS:
        if stripped.startswith("!") or _OPERATOR_LEADING_VERB.match(stripped):
            return MODE_OPERATOR

    return MODE_CONVERSATIONAL


def mode_block(mode: str) -> str:
    """Return the system-prompt block for the given mode.

    Args:
        mode: One of the MODE_* constants.

    Returns:
        A non-empty prompt block string for ``operator`` and ``report``;
        an empty string for ``conversational`` (no extra block needed).
    """
    if mode == MODE_OPERATOR:
        return _OPERATOR_MODE_BLOCK
    if mode == MODE_REPORT:
        return _REPORT_MODE_BLOCK
    return ""
