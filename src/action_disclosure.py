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
    t = text.strip()
    return any(p.match(t) for p in _WHY_PATTERNS)

def action_summary(label: str) -> str:
    return format_line(TerminalStatus.ACTION, label)

def step_progress(step: int, total: int, label: str, *, done: bool = False) -> str:
    return format_step(step, total, label, done=done)

def infer_action_label(user_input: str, skill_name: Optional[str] = None) -> str:
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
    summary = action_summary(action_label.rstrip("."))
    formatted = format_block(TerminalStatus.DONE, body.strip()) if body.strip() else ""
    if formatted:
        return f"{summary}\n{formatted}"
    return summary

def build_why_expansion(session_history: list, last_skill: Optional[str] = None) -> str:
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