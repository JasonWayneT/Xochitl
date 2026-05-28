"""Controlled initiative policy engine.

Implements FR-INIT-001 (signal submission with mode/confidence/suppression
checks), FR-INIT-002 (dismissal tracking and auto-suppression), FR-INIT-003
(drain — returns and clears pending signals), NFR-INIT-001 (never raises).

Policy model (from planning doc #16, arxiv 2509.09309 findings):
  - Unsolicited proactive messages reduce trust unless they follow a strict
    policy: permitted categories only, confidence gate, user-controlled mode,
    auto-suppress after 3 dismissals.
  - Every proactive message must be actionable and dismissable in one command.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Minimum confidence required before a signal is queued (planning doc #16).
_CONFIDENCE_THRESHOLD: float = 0.80

# Number of dismissals before a category is permanently suppressed.
_DISMISS_THRESHOLD: int = 3


# ── Enumerations ──────────────────────────────────────────────────────────────

class ProactiveMode(str, Enum):
    """User-controlled initiative level.

    OFF          — no proactive messages ever (user opted out entirely).
    ERRORS_ONLY  — surface SYSTEM_FAILURE signals only (default).
    FULL         — surface all permitted categories.
    """

    OFF = "off"
    ERRORS_ONLY = "errors_only"
    FULL = "full"


class InitiativeCategory(str, Enum):
    """Permitted categories for proactive surfacing (planning doc #16).

    Implements FR-JARV-004 — expands from two to six permitted categories.

    ERRORS_ONLY mode allows: SYSTEM_FAILURE, DEADLINE, SKILL_HEALTH
    FULL mode allows all categories.
    Everything else (unsolicited tips, personality engagement) is never surfaced.
    """

    SYSTEM_FAILURE = "system_failure"           # e.g. Notion sync failed
    IN_SESSION_FOLLOWUP = "in_session_followup" # e.g. half-finished task
    DEADLINE = "deadline"                       # task deadline within 48h
    FOLLOWUP_SUGGESTION = "followup_suggestion" # natural next step from prior turn
    SKILL_HEALTH = "skill_health"               # skill missing credentials / stale token
    CELEBRATION = "celebration"                 # milestone reached (queue drained, N tasks done)


# Categories permitted through ERRORS_ONLY mode (critical enough to show by default).
_ERRORS_ONLY_CATEGORIES: frozenset[InitiativeCategory] = frozenset({
    InitiativeCategory.SYSTEM_FAILURE,
    InitiativeCategory.DEADLINE,
    InitiativeCategory.SKILL_HEALTH,
})


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ProactiveSignal:
    """A candidate proactive message waiting for policy evaluation.

    Attributes:
        category: The permitted category this signal belongs to.
        message: Short actionable description. Keep under 120 chars.
        confidence: Estimated relevance/urgency (0.0–1.0). Must be >= 0.80
            to pass the submission gate.
        action_hint: One-liner telling the user what to do or type.
            Example: "Run /sync to retry or /dismiss to skip."
    """

    category: InitiativeCategory
    message: str
    confidence: float
    action_hint: str


# ── Engine ────────────────────────────────────────────────────────────────────

class InitiativeEngine:
    """Proactive signal queue with mode, confidence, and dismissal gates.

    Thread-safety: submit() and drain() are called from different threads
    (BackgroundReview daemon vs main loop). Python's GIL protects list.append
    and list clear on CPython, which is sufficient here. If CPython assumptions
    are ever relaxed, add a threading.Lock around _pending mutations.
    """

    def __init__(self, mode: ProactiveMode = ProactiveMode.ERRORS_ONLY) -> None:
        self._mode: ProactiveMode = mode
        self._pending: list[ProactiveSignal] = []
        self._dismissal_counts: dict[InitiativeCategory, int] = {}
        self._suppressed: set[InitiativeCategory] = set()

    # ── Public API ────────────────────────────────────────────────────────────

    def submit(self, signal: ProactiveSignal) -> None:
        """Submit a candidate signal through policy checks (FR-INIT-001).

        Silently discards the signal if:
          (a) mode is OFF,
          (b) mode is ERRORS_ONLY and category is not SYSTEM_FAILURE,
          (c) confidence < _CONFIDENCE_THRESHOLD (0.80),
          (d) category is suppressed (3+ dismissals).

        Never raises to caller (NFR-INIT-001).

        Args:
            signal: The candidate proactive signal to evaluate.
        """
        try:
            if self._mode == ProactiveMode.OFF:
                return
            if self._mode == ProactiveMode.ERRORS_ONLY:
                if signal.category not in _ERRORS_ONLY_CATEGORIES:
                    return
            if signal.category in self._suppressed:
                return
            if signal.confidence < _CONFIDENCE_THRESHOLD:
                logger.debug(
                    "initiative: signal below threshold (%.2f < %.2f), discarded: %s",
                    signal.confidence,
                    _CONFIDENCE_THRESHOLD,
                    signal.message[:60],
                )
                return
            self._pending.append(signal)
            logger.debug(
                "initiative: signal queued [%s, conf=%.2f]: %s",
                signal.category.value,
                signal.confidence,
                signal.message[:60],
            )
        except Exception as exc:
            logger.debug("initiative: submit() error: %s", exc)

    def dismiss(self, category: InitiativeCategory) -> None:
        """Record a user dismissal; suppress the category after 3 (FR-INIT-002).

        Never raises to caller (NFR-INIT-001).

        Args:
            category: The ``InitiativeCategory`` the user dismissed.
        """
        try:
            count = self._dismissal_counts.get(category, 0) + 1
            self._dismissal_counts[category] = count
            if count >= _DISMISS_THRESHOLD:
                self._suppressed.add(category)
                logger.debug(
                    "initiative: category '%s' suppressed after %d dismissals",
                    category.value,
                    count,
                )
        except Exception as exc:
            logger.debug("initiative: dismiss() error: %s", exc)

    def drain(self) -> list[ProactiveSignal]:
        """Return and clear all pending signals (FR-INIT-003).

        Calling drain() twice returns [] on the second call. Thread-safe
        under CPython's GIL.

        Returns:
            List of queued ``ProactiveSignal`` instances (may be empty).
        """
        try:
            out = self._pending[:]
            self._pending.clear()
            return out
        except Exception as exc:
            logger.debug("initiative: drain() error: %s", exc)
            return []

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def mode(self) -> ProactiveMode:
        """Current proactive mode setting."""
        return self._mode

    def set_mode(self, mode: ProactiveMode) -> None:
        """Update the proactive mode (e.g. from user preference).

        Args:
            mode: New ``ProactiveMode`` to apply.
        """
        self._mode = mode
        logger.debug("initiative: mode set to '%s'", mode.value)
