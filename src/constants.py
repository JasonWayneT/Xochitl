"""Shared primitive constants for Xochitl.

All modules should import from here rather than redefining.  Centralising
these prevents silent threshold drift when a value is updated in one file
but missed in another.

Re-export note: chat.py imports these with ``from src.constants import ...``
so that ``from src.chat import _SKILL_INJECT_THRESHOLD`` (used by smoke tests
and the session layer) continues to work.  Do NOT remove those re-exports
from chat.py without updating the import sites first.
"""
from __future__ import annotations

import re

# ── Skill scoring thresholds (FR-ORCH-008, FR-PERF-003, CR-032, CR-036) ──────

# Minimum can_handle() score to inject a skill schema into the system prompt.
# Matches the 0.6 suggestion threshold from Skill base docstring with a buffer.
_SKILL_INJECT_THRESHOLD: float = 0.65

# Threshold below which intent is considered open-ended (no skill matched well).
# When top_score < this, the turn context block warns the model about uncertainty.
_OPEN_ENDED_SCORE_THRESHOLD: float = 0.2

# ── Skill-call XML pattern (FR-ORCH-008, FR-PERF-007) ─────────────────────────

# Compiled once at import time; used to parse and strip <skill_call> XML.
_SKILL_CALL_RE: re.Pattern[str] = re.compile(
    r'<skill_call\s+name=["\'](\w+)["\']>(.*?)</skill_call>',
    re.DOTALL | re.IGNORECASE,
)

# ── Response vocabulary (FR-UX-002) ───────────────────────────────────────────
# Spanish vocabulary constants mirroring SOUL.md palette.

_OK  = "Claro"    # success / acknowledged
_FYI = "Fíjate"  # informational flag — "look here"
_ERR = "Ay no"   # error / blocked

# ── Confirmation word sets (FR-ORCH-007) ──────────────────────────────────────

_CONFIRM_YES: frozenset[str] = frozenset({
    "yes", "y", "ok", "sure", "yeah", "yep", "do it", "go ahead",
})
_CONFIRM_NO: frozenset[str] = frozenset({
    "no", "n", "nope", "cancel", "nevermind", "stop", "don't",
})

# ── Mutating skill action sets (FR-ORCH-011, FR-EXEC-001) ─────────────────────
# Actions that require user approval before execution.
# Values are frozensets to prevent accidental mutation.

_MUTATING_SKILL_ACTIONS: dict[str, frozenset[str]] = {
    "BMADSkill": frozenset({"init_project", "save_bmad_artifact"}),
    "SDDSkill":  frozenset({
        "generate_specs", "create_requirement", "create_issue",
        "update_requirement", "close_issue",
    }),
    "CodeSkill": frozenset({"scaffold", "implement", "fix", "tests", "test"}),
}

# Skills that always require approval regardless of action param (FR-ORCH-011).
_ALWAYS_APPROVE: frozenset[str] = frozenset({"NotionSkill", "CodeSkill"})
