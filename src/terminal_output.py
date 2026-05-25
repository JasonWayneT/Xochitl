"""Terminal visual grammar. Implements FR-UI-009, FR-UI-010, NFR-UI-009 (CR-039)."""
from __future__ import annotations
import json
import textwrap
from enum import Enum
from typing import Any, Optional

MAX_LINE_WIDTH = 80

class TerminalStatus(Enum):
    DONE = "done"
    ACTION = "action"
    WARN = "warn"
    FAIL = "fail"

_PLAIN = {
    TerminalStatus.DONE: "[ok] ",
    TerminalStatus.ACTION: "-> ",
    TerminalStatus.WARN: "[warn] ",
    TerminalStatus.FAIL: "[fail] ",
}
_RICH = {
    TerminalStatus.DONE: "[green]\u2713[/green] ",
    TerminalStatus.ACTION: "[yellow]\u2192[/yellow] ",
    TerminalStatus.WARN: "[yellow]\u26a0[/yellow] ",
    TerminalStatus.FAIL: "[red]\u2717[/red] ",
}

def wrap_text(text: str, width: int = MAX_LINE_WIDTH) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines() or [""]:
        stripped = raw.lstrip()
        indent = raw[: len(raw) - len(stripped)]
        if not stripped:
            lines.append(indent.rstrip())
            continue
        avail = max(20, width - len(indent))
        wrapped = textwrap.wrap(stripped, width=avail, break_long_words=True, break_on_hyphens=False)
        for i, part in enumerate(wrapped):
            lines.append((indent if i == 0 else indent + "  ") + part)
    return lines or [""]

def format_line(status: TerminalStatus, text: str, indent: int = 0, *, rich: bool = True) -> str:
    pad = "  " * indent
    prefix = (_RICH if rich else _PLAIN)[status]
    body = wrap_text(text, MAX_LINE_WIDTH)[0] if text else ""
    return f"{pad}{prefix}{body}"

def format_block(status: TerminalStatus, text: str, indent: int = 0, *, rich: bool = True) -> str:
    pad = "  " * indent
    prefix = (_RICH if rich else _PLAIN)[status]
    wrapped = wrap_text(text)
    out: list[str] = []
    for i, line in enumerate(wrapped):
        out.append(f"{pad}{prefix}{line}" if i == 0 else f"{pad}  {line}")
    return "\n".join(out)

def format_step(current: int, total: int, label: str, *, done: bool = False, rich: bool = True) -> str:
    head = f"[{current}/{total}] {label}"
    if done:
        return format_line(TerminalStatus.DONE, f"{head} done", rich=rich)
    return format_line(TerminalStatus.ACTION, f"{head}...", rich=rich)

def format_skill_output(text: str, *, rich: bool = True) -> str:
    del rich
    if not text:
        return ""
    lines: list[str] = []
    for raw in text.splitlines():
        for part in wrap_text(raw):
            lines.append(f"  {part}" if lines else part)
    return "\n".join(lines[:50])

def cli_payload(command: str, ok: bool, data: Any = None, messages: Optional[list[dict[str, str]]] = None) -> dict[str, Any]:
    return {"ok": ok, "command": command, "data": data if data is not None else {}, "messages": messages or []}

def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))