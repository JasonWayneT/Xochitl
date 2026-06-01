"""Bounded project source indexing into vector memory.

Implements FR-MEM-016 (CR-052). Walks a project's source files (extension
allowlist, file cap), and stores a summary entry per file in vector memory so
later semantic recall can surface relevant code. Resilient: an embedding failure
on one file is skipped, not fatal.
"""
from __future__ import annotations

import os
from pathlib import Path

_INDEX_MAX_FILES: int = int(os.getenv("XCH_INDEX_MAX_FILES", "300"))
_INDEX_CHUNK_CHARS: int = int(os.getenv("XCH_INDEX_CHUNK_CHARS", "2000"))

_INDEX_EXTENSIONS = frozenset({".py", ".md", ".js", ".ts", ".tsx", ".jsx", ".toml", ".yaml", ".yml"})

_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    ".xochitl", ".idea", ".vscode",
})


def index_project(root: Path, memory, project: str | None = None) -> tuple[int, int, bool]:
    """Index a project's source files into vector memory.

    Args:
        root: Project root directory to walk.
        memory: An object exposing ``memorize(topic, summary, tags, project) -> bool``
            (e.g. ``VectorMemory``).
        project: Optional project tag stored with each entry.

    Returns:
        Tuple of (indexed, scanned, capped): number of files successfully stored,
        number of eligible files seen, and whether the file cap was hit.
    """
    root = Path(root)
    indexed = 0
    scanned = 0
    capped = False

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for fn in filenames:
            if Path(fn).suffix not in _INDEX_EXTENSIONS:
                continue
            if scanned >= _INDEX_MAX_FILES:
                capped = True
                return indexed, scanned, capped
            scanned += 1
            path = Path(dirpath) / fn
            try:
                content = path.read_text(encoding="utf-8", errors="replace")[:_INDEX_CHUNK_CHARS]
            except OSError:
                continue
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            try:
                ok = memory.memorize(
                    topic=f"source:{rel}",
                    summary=content,
                    tags=["code", "index"],
                    project=project,
                )
            except Exception:
                ok = False
            if ok:
                indexed += 1

    return indexed, scanned, capped


def format_index_result(indexed: int, scanned: int, capped: bool) -> str:
    """Format an index_project() result for the user.

    Args:
        indexed: Files successfully stored.
        scanned: Eligible files seen.
        capped: Whether the cap was hit.

    Returns:
        A short status line.
    """
    if scanned == 0:
        return "Fíjate — no indexable source files found here."
    msg = f"Indexed {indexed}/{scanned} file(s) into vector memory."
    if indexed < scanned:
        msg += " (some files were skipped — embedding may be offline.)"
    if capped:
        msg += f" Stopped at the {_INDEX_MAX_FILES}-file cap."
    return msg
