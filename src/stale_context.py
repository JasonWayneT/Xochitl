"""Stale-context detection for injected file content.

Implements FR-EXEC-007 (CR-052). When file content is injected into a prompt,
its content hash is recorded. If the same file is consulted again and its
on-disk hash differs, the context is stale and a warning can be surfaced so the
assistant does not reason from outdated content.

Thread-safe, session-scoped (RAM only).
"""
from __future__ import annotations

import hashlib
import threading

_lock = threading.Lock()
_hashes: dict[str, str] = {}


def _hash(content: str) -> str:
    """Return a short content hash.

    Args:
        content: File content.

    Returns:
        First 16 hex chars of the SHA-256 digest.
    """
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


def record_injection(path: str, content: str) -> None:
    """Record the hash of content injected for a path.

    Args:
        path: File path key.
        content: The exact content injected.
    """
    with _lock:
        _hashes[str(path)] = _hash(content)


def is_stale(path: str, current_content: str) -> bool:
    """Return True if current content differs from what was last injected.

    Args:
        path: File path key.
        current_content: The current on-disk content.

    Returns:
        True when the path was previously injected and its hash has changed;
        False when unseen or unchanged.
    """
    with _lock:
        prev = _hashes.get(str(path))
    if prev is None:
        return False
    return prev != _hash(current_content)


def clear() -> None:
    """Reset the hash store. Called at session end and in tests."""
    with _lock:
        _hashes.clear()
