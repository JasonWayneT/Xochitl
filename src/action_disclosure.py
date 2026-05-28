"""Compact reasoning disclosure. Implements FR-ORCH-044, FR-ORCH-045, FR-ORCH-046 (CR-040)."""
from __future__ import annotations
import re
from typing import Optional

from src.terminal_output import TerminalStatus, format_block, format_line, format_step

_WHY_PATTERNS = (
    re.compile(r"^\s*why\??\s*$", re.I),
    re.compile(r"^\s*how did you get that\??\s*$", re.I),
    re.compile(r"^\s*how do you know\??\s*$", re.I),
    re.compile(r"^\s*explain (?:your |the )?reasoning\s*$", re.I),
    re.compile(r"^\s*what did you do\??\s*$", re.I),
)

def is_why_request(text: str) -> bool:
    """Return True if the message is asking Xochitl to explain her last action.

    Implements FR-ORCH-044. Matches short phrasings like "why?", "how do you know",
    "explain your reasoning", etc.

    Args:
        text: Raw user message text.

    Returns:
        True if the message matches a known why-request pattern.
    """
    t = text.strip()
    return any(p.match(t) for p in _WHY_PATTERNS)

def action_summary(label: str) -> str:
    """Format an action label as a terminal ACTION-status line.

    Args:
        label: Short human-readable description of the action being taken.

    Returns:
        Formatted string using the ACTION status style from terminal_output.
    """
    return format_line(TerminalStatus.ACTION, label)

def step_progress(step: int, total: int, label: str, *, done: bool = False) -> str:
    """Format a multi-step progress indicator line.

    Args:
        step: Current step number (1-based).
        total: Total number of steps.
        label: Description of this step.
        done: If True, render as completed; otherwise as in-progress.

    Returns:
        Formatted step-progress string for terminal display.
    """
    return format_step(step, total, label, done=done)

def infer_action_label(user_input: str, skill_name: Optional[str] = None) -> str:
    """Derive a human-readable action label from the user request or skill name.

    Used in the status display shown while Xochitl is working.
    Implements FR-ORCH-045.

    Args:
        user_input: The raw user message text.
        skill_name: If a specific skill was matched, its class name (e.g. 'WeatherSkill').

    Returns:
        Short label string suitable for the action disclosure line.
    """
    q = user_input.strip()
    if skill_name:
        nice = skill_name.replace("Skill", "")
        return f"Running {nice}..."
    low = q.lower()
    if "weather" in low or "forecast" in low:
        return "Checking weather..."
    if any(k in low for k in ("sync", "notion", "pull", "push")):
        return "Syncing with Notion..."
    if any(k in low for k in ("task", "queue", "done", "today")):
        return "Checking your tasks..."
    if len(q) > 60:
        q = q[:57] + "..."
    return f"Working on: {q}"

def format_compact_result(action_label: str, body: str) -> str:
    """Combine an action summary line with a DONE-status result block.

    Implements FR-ORCH-046.

    Args:
        action_label: Label for the action (e.g. "Checked weather").
        body: Result text to display below the action line.

    Returns:
        Combined action + result string, or just the action line if body is empty.
    """
    summary = action_summary(action_label.rstrip("."))
    formatted = format_block(TerminalStatus.DONE, body.strip()) if body.strip() else ""
    if formatted:
        return f"{summary}\n{formatted}"
    return summary

def build_why_expansion(session_history: list, last_skill: Optional[str] = None) -> str:
    """Build a human-readable explanation of what happened in the last turn.

    Implements FR-ORCH-044 — surfaces reasoning on "why?" requests without
    requiring the LLM to re-infer it.

    Args:
        session_history: List of message dicts from the current session.
        last_skill: Class name of the last skill that executed, if any.

    Returns:
        Multi-line markdown explanation string ready for console display.
    """
    lines = ["## What happened last turn"]
    if last_skill:
        lines.append(f"- Skill used: {last_skill}")
    for msg in reversed(session_history[-8:]):
        role = msg.get("role", "")
        if role == "tool":
            skill = msg.get("skill", "tool")
            snippet = (msg.get("content") or "")[:400]
            lines.append(f"- Tool ({skill}): {snippet}")
            break
        if role == "assistant":
            snippet = (msg.get("content") or "")[:300]
            lines.append(f"- Response excerpt: {snippet}")
            break
    for msg in reversed(session_history[-12:]):
        if msg.get("role") == "user":
            lines.append(f"- Your message: {(msg.get('content') or '')[:200]}")
            break
    if len(lines) == 1:
        lines.append("- No detailed trace stored for this session yet.")
    lines.append("")
    lines.append("Ask a follow-up if you need more detail on a specific step.")
    return "\n".join(lines)