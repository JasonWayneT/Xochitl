"""Implicit preference learning utilities.

Implements FR-PREF-001 (rephrased-query detection heuristic),
FR-PREF-002 (storage hook for BackgroundReview — see background_review.py),
FR-PREF-003 (confidence decay and pruning on session start),
NFR-PREF-001 (all heuristic — no LLM calls).
"""
from __future__ import annotations

import re
import sqlite3
from typing import Optional

# FR-PREF-003: confidence decay and prune constants.
_CONFIDENCE_DECAY_RATE: float = 0.95   # per-session multiplier for implicit prefs
_PRUNE_THRESHOLD: float = 0.30         # delete implicit prefs below this

# FR-PREF-001: rephrased-query detection thresholds.
_REPHRASE_MIN_SHARED_WORDS: int = 2        # min shared non-stopword tokens
_REPHRASE_SIMILARITY_THRESHOLD: float = 0.30  # min Jaccard on all tokens

# Stopwords for content-word extraction (no external libraries — NFR-PREF-001).
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can",
    "of", "in", "to", "for", "on", "with", "at", "by", "from", "into",
    "and", "or", "but", "not", "so", "yet",
    "i", "me", "my", "you", "your", "we", "our", "they", "their",
    "it", "its", "this", "that", "these", "those",
    "what", "which", "who", "how", "when", "where", "why", "whose",
    "tell", "about", "please", "help", "know",
    "s", "t",  # fragments from contractions (it's → "it", "s")
})


def is_rephrased_query(prev: str, curr: str) -> bool:
    """Detect whether `curr` is a rephrase of `prev` via word-overlap heuristic.

    Implements FR-PREF-001 (pure function — no LLM call, no DB access).

    Algorithm:
      1. Identical strings → False (no new framing signal).
      2. Tokenize both to word sets (\\b\\w+\\b, lowercased).
      3. Remove stopwords to get content word sets.
      4. If shared content words < _REPHRASE_MIN_SHARED_WORDS → False.
      5. Compute Jaccard on full token sets.
      6. Return True if Jaccard ≥ _REPHRASE_SIMILARITY_THRESHOLD.

    Args:
        prev: Previous user input.
        curr: Current user input.

    Returns:
        True if curr appears to rephrase the same intent as prev, else False.
    """
    if not prev or not curr:
        return False
    if prev.strip().lower() == curr.strip().lower():
        return False  # identical — retry, not rephrase

    prev_tokens: set[str] = set(re.findall(r"\b\w+\b", prev.lower()))
    curr_tokens: set[str] = set(re.findall(r"\b\w+\b", curr.lower()))

    prev_content = prev_tokens - _STOPWORDS
    curr_content = curr_tokens - _STOPWORDS
    shared_content = prev_content & curr_content

    if len(shared_content) < _REPHRASE_MIN_SHARED_WORDS:
        return False

    all_union = prev_tokens | curr_tokens
    if not all_union:
        return False
    jaccard = len(prev_tokens & curr_tokens) / len(all_union)
    return jaccard >= _REPHRASE_SIMILARITY_THRESHOLD


def decay_and_prune(conn: sqlite3.Connection) -> tuple[int, int]:
    """Decay confidence of implicit preferences; prune below threshold.

    Implements FR-PREF-003. Called once at session start from XochitlChat.start().
    Only targets rows with source='implicit_preference' — never touches
    user-stated or correction-pattern preferences.

    Args:
        conn: Active SQLite connection to the Xochitl database.

    Returns:
        Tuple (decayed_count, pruned_count).
    """
    from src import database as _db
    _db._ensure_preferences_table(conn)  # type: ignore[attr-defined]

    # Apply confidence decay to implicit preferences still above threshold.
    decay_cursor = conn.execute(
        "UPDATE preferences "
        "SET confidence = confidence * ?, updated_at = CURRENT_TIMESTAMP "
        "WHERE source = 'implicit_preference' AND confidence >= ?",
        (_CONFIDENCE_DECAY_RATE, _PRUNE_THRESHOLD),
    )
    decayed_count: int = decay_cursor.rowcount

    # Prune rows that are now (or were already) below the threshold.
    prune_cursor = conn.execute(
        "DELETE FROM preferences "
        "WHERE source = 'implicit_preference' AND confidence < ?",
        (_PRUNE_THRESHOLD,),
    )
    pruned_count: int = prune_cursor.rowcount

    conn.commit()
    return decayed_count, pruned_count
