"""Anticipation gate for Xochitl session startup.

Implements FR-CONV-002 (A2 — anticipation gate). Part of CR-028.

``AnticipationGate`` evaluates contextual signals and returns a one-line
informational hint when **≥2 signals converge**. It is displayed at session
boot and never fires unsolicited mid-session.

Signal types:
  wip      — WIP queue is non-empty (user has active tasks)
  recency  — last session was ≥ ``_SESSION_GAP_HOURS`` ago
  morning  — current hour is in the morning window (06–10)
  evening  — current hour is in the evening window (17–21)

Surfacing is informational only — it never takes action (NFR-CONV-001).

Usage::

    gate = AnticipationGate()
    hint = gate.check_from_db()   # reads DB itself
    if hint:
        console.print(f"[dim]{hint}[/dim]")
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# ── Gate constants ────────────────────────────────────────────────────────────

_MIN_SIGNALS: int = 2                    # minimum converging signals to fire
_SESSION_GAP_HOURS: float = 4.0         # hours gap that counts as "returning after a break"
_MORNING_START: int = 6                  # 06:00 inclusive
_MORNING_END: int = 10                   # 10:00 exclusive
_EVENING_START: int = 17                 # 17:00 inclusive
_EVENING_END: int = 21                   # 21:00 exclusive


class AnticipationGate:
    """Evaluates contextual signals and surfaces a hint when ≥2 converge.

    Implements FR-CONV-002 (A2 anticipation gate). Informational only —
    never takes action, never fires mid-session.
    """

    def check(
        self,
        wip_count: int,
        last_session_age_hours: Optional[float] = None,
    ) -> Optional[str]:
        """Evaluate signals and return a surfacing hint, or ``None``.

        Args:
            wip_count:              Active tasks in the WIP queue (0–3).
            last_session_age_hours: Hours since the most recent ``agent_traces``
                                    entry, or ``None`` if no prior session.

        Returns:
            A one-line informational string if ≥2 signals converge, else ``None``.
        """
        signals: list[str] = []
        hour = datetime.now(timezone.utc).hour

        if wip_count > 0:
            signals.append("wip")

        if (
            last_session_age_hours is not None
            and last_session_age_hours >= _SESSION_GAP_HOURS
        ):
            signals.append("recency")

        if _MORNING_START <= hour < _MORNING_END:
            signals.append("morning")
        elif _EVENING_START <= hour < _EVENING_END:
            signals.append("evening")

        if len(signals) < _MIN_SIGNALS:
            return None

        return self._build_hint(signals, wip_count, last_session_age_hours)

    def check_from_db(self) -> Optional[str]:
        """Convenience wrapper: reads wip_count and last session age from DB.

        Silently returns ``None`` on any DB error so startup is never blocked.

        Returns:
            One-line hint string, or ``None`` if signals don't converge or
            on any error.
        """
        try:
            from src import database as _db
            with _db.get_connection() as conn:
                queue = _db.get_queue(conn)
                wip_count = len(queue)
                last_age = _last_session_age_hours(conn)
        except Exception:
            return None
        return self.check(wip_count=wip_count, last_session_age_hours=last_age)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_hint(
        self,
        signals: list[str],
        wip_count: int,
        last_session_age_hours: Optional[float],
    ) -> str:
        """Compose the anticipation hint from converging signals."""
        parts: list[str] = []

        if "morning" in signals:
            parts.append("Good morning.")
        elif "evening" in signals:
            parts.append("Winding down?")

        if "wip" in signals and wip_count > 0:
            task_word = "task" if wip_count == 1 else "tasks"
            parts.append(f"You have {wip_count} {task_word} in queue.")

        if "recency" in signals and last_session_age_hours is not None:
            hours = int(last_session_age_hours)
            if hours < 24:
                parts.append(f"Last session was {hours}h ago.")
            else:
                days = max(1, round(last_session_age_hours / 24))
                day_word = "day" if days == 1 else "days"
                parts.append(f"Last session was {days} {day_word} ago.")

        hint = " ".join(parts)
        if "wip" in signals and wip_count > 0:
            hint += " Run `xochitl today` for priorities."
        return hint


# ── DB helper ─────────────────────────────────────────────────────────────────


def _last_session_age_hours(conn: object) -> Optional[float]:
    """Return hours since the most recent agent_traces entry, or None.

    Args:
        conn: Active SQLite connection.

    Returns:
        Float hours, or ``None`` if the table is empty or doesn't exist.
    """
    try:
        row = conn.execute(  # type: ignore[union-attr]
            "SELECT ts FROM agent_traces ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        from datetime import datetime, timezone
        last_ts = datetime.fromisoformat(row["ts"])
        now = datetime.now(timezone.utc)
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        return (now - last_ts).total_seconds() / 3600
    except Exception:
        return None
