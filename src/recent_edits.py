"""Session-scoped ring buffer of recent file edits.

Implements FR-MEM-015 (CR-052) — lets the assistant answer "what did I just
change?" without re-reading files. Thread-safe, bounded, RAM-only (never
persisted between sessions).
"""
from __future__ import annotations

import os
import threading
from collections import deque
from datetime import datetime

# Maximum edits retained. Override with XCH_RECENT_EDITS_MAX.
_MAX_EDITS: int = int(os.getenv("XCH_RECENT_EDITS_MAX", "10"))

_lock = threading.Lock()
_edits: deque[dict] = deque(maxlen=_MAX_EDITS)


def record_edit(path: str, op: str, line_delta: int = 0) -> None:
    """Record a completed file edit.

    Args:
        path: The file path that was edited.
        op: Operation type — "write", "overwrite", or "delete".
        line_delta: Net change in line count (new − old); 0 for deletes.
    """
    with _lock:
        _edits.append({
            "path": str(path),
            "op": str(op),
            "line_delta": int(line_delta),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })


def get_recent_edits(n: int | None = None) -> list[dict]:
    """Return recent edits, oldest first.

    Args:
        n: Maximum number to return (most recent). None returns all.

    Returns:
        List of edit dicts (copies); empty when nothing recorded.
    """
    with _lock:
        items = list(_edits)
    return items[-n:] if n else items


def render_recent_edits_block(n: int | None = None) -> str:
    """Render recent edits as a plain-text block for SYSTEM_FACTS injection.

    Args:
        n: Maximum edits to render. None uses all retained.

    Returns:
        A "Recent edits:" block, or an empty string when none recorded.
    """
    items = get_recent_edits(n)
    if not items:
        return ""
    lines = ["Recent edits (this session):"]
    for e in items:
        delta = e["line_delta"]
        sign = f"+{delta}" if delta > 0 else str(delta)
        ts = e["timestamp"][11:19]  # HH:MM:SS
        lines.append(f"  [{ts}] {e['op']}: {e['path']} ({sign} lines)")
    return "\n".join(lines)


def clear() -> None:
    """Reset the buffer. Called at session end and in tests."""
    with _lock:
        _edits.clear()
