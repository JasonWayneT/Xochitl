"""Conversation quality utilities for Xochitl.

Implements FR-CONV-001 (A1 — filler opener stripping) and
FR-CONV-005 (A5 — uncertainty hedge utility). Part of CR-028.

Both functions are pure (no LLM calls, no I/O) and must never block
the main chat loop (NFR-CONV-001).

Usage::

    from src.conversation import strip_filler_opener, uncertainty_hedge

    clean = strip_filler_opener("Certainly! Here is the answer.")
    # → "Here is the answer."

    hedged = uncertainty_hedge(0.72, "The meeting is at 3pm.")
    # → "I think the meeting is at 3pm."
"""

from __future__ import annotations

import re

# ── A1: Filler opener stripping ───────────────────────────────────────────────

# Single compiled pattern — matches sycophantic openers at string start.
# One-pass: only the first match is stripped (apply once per response).
_FILLER_RE: re.Pattern = re.compile(
    r"^(?:"
    # Superlatives on "question"
    r"(?:great|excellent|fantastic|brilliant|wonderful|good)\s+question[!.]*\s*"
    # Bare affirmatives (with punctuation — avoids stripping "sure" mid-sentence)
    r"|certainly[!.]\s*"
    r"|of\s+course[!.,]\s*"
    r"|absolutely[!.]\s*"
    r"|sure[!.]\s*"
    r"|indeed[!.]\s*"
    r"|definitely[!.]\s*"
    # Enthusiasm + comma openers
    r"|great[!,]\s*"
    # Helper-role openers
    r"|(?:i(?:'m|'d| am| would)[\s,]+be[\s,]+happy\s+to(?:\s+help)?[!.,]\s*)"
    r")",
    re.IGNORECASE,
)


def strip_filler_opener(response: str) -> str:
    """Remove sycophantic filler phrases from the start of a response.

    Implements FR-CONV-001 (A1 presence cues), FR-UX-002 (CR-050 A2 multi-pass).
    Iterates up to 5 times to strip consecutive openers (e.g. "Certainly! Of course!").
    Re-capitalises the first letter of the remaining text after stripping.

    Args:
        response: Raw LLM response text.

    Returns:
        Response with leading filler phrase(s) removed and first letter
        capitalised, or the original response if no filler was found.
    """
    result = response
    stripped_any = False
    for _ in range(5):
        m = _FILLER_RE.match(result)
        if not m:
            break
        remainder = result[m.end():].lstrip()
        if not remainder:
            return response  # entire remaining text was filler — return original
        result = remainder
        stripped_any = True
    if stripped_any and result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result


# ── A5: Uncertainty hedge utility ─────────────────────────────────────────────

# Tier thresholds — mirrors planning doc #24 / #35 and SOUL.md [UNCERTAINTY TIERS]
_TIER_HIGH: float = 0.85    # state directly — no hedge
_TIER_MID_LOW: float = 0.60  # linguistic hedge

# Prefix phrases per tier
_HEDGE_MID = "I think"
_HEDGE_LOW_PREFIX = "I'm not certain, but"
_HEDGE_LOW_SUFFIX = " — want me to look this up?"


def uncertainty_hedge(confidence: float, text: str) -> str:
    """Apply calibrated uncertainty framing per the three-tier model.

    Implements FR-CONV-005 (A5). Tier boundaries:
    - ``confidence > 0.85``  → text unchanged (direct statement)
    - ``0.60 ≤ confidence ≤ 0.85`` → linguistic hedge (``"I think …"``)
    - ``confidence < 0.60``  → explicit uncertainty + resolution offer

    Args:
        confidence: Confidence score in [0.0, 1.0].
        text:       The statement to potentially hedge.

    Returns:
        Hedged (or unchanged) statement string.

    Raises:
        ValueError: If ``text`` is empty.
    """
    if not text:
        raise ValueError("uncertainty_hedge: text must not be empty")

    if confidence > _TIER_HIGH:
        return text

    # Lowercase the first letter of the payload to merge it cleanly into the prefix
    payload = text[0].lower() + text[1:] if len(text) > 1 else text.lower()

    if confidence >= _TIER_MID_LOW:
        return f"{_HEDGE_MID} {payload}"

    # Low confidence: explicit uncertainty + resolution offer
    return f"{_HEDGE_LOW_PREFIX} {payload}{_HEDGE_LOW_SUFFIX}"
