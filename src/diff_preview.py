"""Unified diff rendering for file-edit confirmations.

Implements FR-UI-011 (CR-052) — users must see what a file edit will change
before approving it. Pure functions, no I/O, fully testable.
"""
from __future__ import annotations

import difflib
import os

# Maximum diff lines shown in a confirmation message. Override with XCH_DIFF_MAX_LINES.
_DIFF_MAX_LINES: int = int(os.getenv("XCH_DIFF_MAX_LINES", "40"))

# Maximum preview lines for a brand-new file (no diff — just content).
_PREVIEW_MAX_LINES: int = int(os.getenv("XCH_PREVIEW_MAX_LINES", "20"))


def make_diff_preview(
    old_content: str,
    new_content: str,
    path: str,
    *,
    max_lines: int = _DIFF_MAX_LINES,
) -> str:
    """Render a unified diff between old and new file content.

    Args:
        old_content: Existing file content (empty string for a new file).
        new_content: Proposed new content.
        path: File path, used in the diff header.
        max_lines: Maximum number of diff lines to include; excess is summarized.

    Returns:
        A unified-diff string with ``---``/``+++`` headers and ``+``/``-`` lines,
        truncated with a notice when it exceeds ``max_lines``. Returns a
        "no changes" notice when old and new are identical.
    """
    if old_content == new_content:
        return "[no changes — file content is identical]"

    diff_lines = list(
        difflib.unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )

    if not diff_lines:
        return "[no textual changes]"

    if len(diff_lines) > max_lines:
        shown = diff_lines[:max_lines]
        omitted = len(diff_lines) - max_lines
        shown.append(f"[... {omitted} more diff line(s) omitted ...]")
        diff_lines = shown

    return "\n".join(diff_lines)


def make_new_file_preview(
    content: str,
    path: str,
    *,
    max_lines: int = _PREVIEW_MAX_LINES,
) -> str:
    """Render a short preview of a brand-new file's content.

    Args:
        content: The new file's full content.
        path: File path, shown in the preview header.
        max_lines: Maximum number of content lines to include.

    Returns:
        A header plus the first ``max_lines`` content lines, with a truncation
        notice when the file is longer.
    """
    lines = content.splitlines()
    header = f"New file: {path} ({len(lines)} line(s))"
    if len(lines) > max_lines:
        body = lines[:max_lines]
        body.append(f"[... {len(lines) - max_lines} more line(s) ...]")
    else:
        body = lines
    return header + "\n" + "\n".join(body)


def summarize_file_edits(edits: list[dict]) -> str:
    """Summarize a batch of planned file edits for a multi-file confirmation.

    Args:
        edits: List of dicts each with keys ``path`` and ``op`` (write/overwrite/delete).

    Returns:
        A bullet list of the planned operations, grouped by op type.
    """
    if not edits:
        return "[no file edits planned]"
    lines = ["Planned file changes:"]
    for e in edits:
        op = str(e.get("op", "edit"))
        path = str(e.get("path", "?"))
        lines.append(f"  - {op}: {path}")
    return "\n".join(lines)
