"""Structured daily brief for Xochitl sessions.

Implements FR-CONV-003 (A3 — structured brief). Part of CR-028.

``build_structured_brief`` returns a five-section Markdown brief. Each section
is skipped when empty. Called from the ``/brief`` slash command — never pushed
unsolicited (alert-fatigue risk per planning doc).

Sections:
  1. **Temporal context** — day, date, and time
  2. ~~Schedule~~ — skipped (no calendar integration yet)
  3. **Priorities** — top 3 WIP tasks
  4. **Async queue** — Notion items needing decisions / overflow tasks
  5. **Awareness** — last git commit age nudge

Usage::

    from src.brief import build_structured_brief

    with db.get_connection() as conn:
        queue = db.get_queue(conn)
    brief = build_structured_brief(queue, notion_pending=[])
    console.print(brief)
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Any

# Maximum items rendered per section — prevents brief bloat.
_MAX_LINES_PER_SECTION: int = 5

# Minimum commit age (hours) before a nudge appears in the Awareness section.
_COMMIT_NUDGE_THRESHOLD_HOURS: float = 2.0


def build_structured_brief(
    queue: list[dict[str, Any]],
    notion_pending: list[dict[str, Any]],
) -> str:
    """Build a five-section structured daily brief.

    Implements FR-CONV-003 (A3 structured brief). Each section is skipped when
    empty. Sections are separated by ``---`` for visual hierarchy. At most
    ``_MAX_LINES_PER_SECTION`` items are shown per section to keep the brief
    scannable. Never calls an LLM — all data is read from the DB and git
    (NFR-CONV-001).

    Args:
        queue:          WIP task rows from ``database.get_queue()``.
        notion_pending: Notion items needing decisions, or ``[]`` if Notion is
                        not configured or the sync has not run.

    Returns:
        Formatted multi-line Markdown string suitable for terminal display.
    """
    sections: list[str] = []

    # ── 1. Temporal context ────────────────────────────────────────────────
    now = datetime.now()
    # Platform-safe: build day string without %-d / %#d format codes.
    day_str = now.strftime(f"%A, %B {now.day}")   # e.g. "Monday, May 5"
    time_str = now.strftime("%H:%M")
    sections.append(f"**{day_str}** — {time_str}")

    # ── 2. Schedule ────────────────────────────────────────────────────────
    # Intentionally skipped — no calendar integration. Reserved for future
    # CalendarSkill work. Do not add a placeholder.

    # ── 3. Priorities — top 3 WIP tasks ───────────────────────────────────
    if queue:
        lines = ["**Priorities**"]
        for i, task in enumerate(queue[:_MAX_LINES_PER_SECTION], start=1):
            desc = str(task.get("description", "(no description)"))[:72]
            lines.append(f"  {i}. {desc}")
        sections.append("\n".join(lines))

    # ── 4. Async queue — Notion items needing decisions ────────────────────
    if notion_pending:
        lines = ["**Async queue**"]
        for item in notion_pending[:_MAX_LINES_PER_SECTION]:
            title = str(item.get("title", item.get("name", "(no title)")))[:72]
            lines.append(f"  - {title}")
        sections.append("\n".join(lines))

    # ── 5. Awareness — last git commit age ────────────────────────────────
    awareness = _git_commit_nudge()
    if awareness:
        sections.append(f"**Awareness** — {awareness}")

    if not sections:
        return "_(brief is empty — no WIP tasks, no Notion queue, git unavailable)_"

    return "\n\n---\n\n".join(sections)


# ── Git helper ────────────────────────────────────────────────────────────────


def _git_commit_nudge() -> str:
    """Return a contextual nudge about the last git commit age, or empty string.

    Runs ``git log -1 --format=%cI`` in a subprocess (non-blocking, 5 s timeout).
    Returns an empty string if git is unavailable, the repo has no commits, the
    last commit is recent, or any error occurs.

    Returns:
        Short human-readable string when the last commit is stale, else ``""``.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return ""

        last_commit_str = result.stdout.strip()
        last_commit = datetime.fromisoformat(last_commit_str)
        now = datetime.now(tz=last_commit.tzinfo)
        age_hours = (now - last_commit).total_seconds() / 3600

        if age_hours < _COMMIT_NUDGE_THRESHOLD_HOURS:
            return ""

        if age_hours < 24:
            h = int(age_hours)
            return f"Last commit was {h}h ago — push or stash before EOD?"

        days = max(1, round(age_hours / 24))
        day_word = "day" if days == 1 else "days"
        return f"Last commit was {days} {day_word} ago — worth a checkpoint commit?"

    except Exception:
        return ""
