"""Structured observability for Xochitl agent turns.

Implements FR-ORCH-035, FR-ORCH-036, NFR-ORCH-010, NFR-ORCH-011 (CR-021).

``ObservabilityLogger`` subscribes to the ``src.events`` bus and assembles a
structured trace for each conversation turn. On turn completion (``llm_complete``
event) the trace is:

1. Appended to a JSONL ring buffer at ``~/.xochitl/agent_traces.jsonl``
   (capped at 10 MB — rotated to ``.jsonl.bak`` when exceeded, NFR-ORCH-010).
2. Inserted into the ``agent_traces`` SQLite table in a background daemon
   thread (NFR-ORCH-011 — never blocks the main chat loop).

JSONL record (OTel GenAI Semantic Conventions 2025)::

    {
      "trace_id":                   "abc123def456",
      "ts":                         "2026-05-24T10:00:00.123456+00:00",
      "gen_ai.system":              "xochitl",
      "gen_ai.request.model":       "local",
      "gen_ai.usage.prompt_tokens": 1200,
      "gen_ai.usage.completion_tokens": 87,
      "cost_usd":                   0.0,
      "latency_ms":                 734,
      "top_skill":                  "WeatherSkill",
      "top_score":                  0.82,
      "tool_calls":                 [{"name": "weather", "success": true, "duration_ms": 210}],
      "failure_reason":             null
    }

Usage::

    logger = ObservabilityLogger()
    logger.start()      # subscribes to event bus
    # ... session runs ...
    logger.stop()       # unsubscribes (optional — daemon thread cleans up)
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.events import get_emitter

# ── Storage paths ─────────────────────────────────────────────────────────────

_CONFIG_DIR = Path.home() / ".xochitl"
_JSONL_PATH = _CONFIG_DIR / "agent_traces.jsonl"
_JSONL_BAK_PATH = _CONFIG_DIR / "agent_traces.jsonl.bak"
_MAX_JSONL_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

# ── Turn trace dataclass ──────────────────────────────────────────────────────


@dataclass
class _TurnTrace:
    """Mutable accumulator for one conversation turn's observability data."""

    trace_id: str = ""
    started_at: float = 0.0          # monotonic clock at routing_started
    route: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    top_skill: Optional[str] = None
    top_score: float = 0.0
    tool_calls: list[dict] = field(default_factory=list)
    failure_reason: Optional[str] = None
    _skill_started_at: float = 0.0   # monotonic clock for active tool call

    def to_record(self) -> dict:
        """Serialise to OTel-aligned JSONL record."""
        return {
            "trace_id": self.trace_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "gen_ai.system": "xochitl",
            "gen_ai.request.model": self.route,
            "gen_ai.usage.prompt_tokens": self.tokens_in,
            "gen_ai.usage.completion_tokens": self.tokens_out,
            "cost_usd": round(self.cost_usd, 8),
            "latency_ms": self.latency_ms,
            "top_skill": self.top_skill,
            "top_score": round(self.top_score, 4),
            "tool_calls": self.tool_calls,
            "failure_reason": self.failure_reason,
        }


# ── ObservabilityLogger ───────────────────────────────────────────────────────


class ObservabilityLogger:
    """Subscribes to the Xochitl event bus and records per-turn traces.

    Implements FR-ORCH-035 (CR-021). Thread-safe: the event bus delivers
    callbacks on the caller's thread; SQLite writes are dispatched to a
    background daemon thread.

    Args:
        None — uses module-level JSONL path and the global event emitter.
    """

    def __init__(self) -> None:
        self._current: Optional[_TurnTrace] = None
        self._lock = threading.Lock()
        self._subscribed = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Subscribe to the event bus. Safe to call multiple times."""
        if self._subscribed:
            return
        get_emitter().subscribe(self.on_event)
        self._subscribed = True

    def stop(self) -> None:
        """Unsubscribe from the event bus."""
        if not self._subscribed:
            return
        get_emitter().unsubscribe(self.on_event)
        self._subscribed = False

    # ── Event handler ─────────────────────────────────────────────────────────

    def on_event(self, event: str, payload: dict) -> None:
        """Handle a single event from the bus.

        Args:
            event:   Event name (e.g. ``"routing_started"``).
            payload: Arbitrary key/value dict emitted with the event.
        """
        try:
            if event == "routing_started":
                self._handle_routing_started(payload)
            elif event == "skill_matched":
                self._handle_skill_matched(payload)
            elif event == "skill_started":
                self._handle_skill_started(payload)
            elif event == "skill_complete":
                self._handle_skill_complete(payload)
            elif event == "llm_complete":
                self._handle_llm_complete(payload)
        except Exception:
            pass  # observability must never crash the main thread

    # ── Private handlers ──────────────────────────────────────────────────────

    def _handle_routing_started(self, payload: dict) -> None:
        with self._lock:
            self._current = _TurnTrace(
                trace_id=payload.get("trace_id", secrets.token_hex(6)),
                started_at=time.monotonic(),
            )

    def _handle_skill_matched(self, payload: dict) -> None:
        with self._lock:
            if self._current is None:
                return
            self._current.top_skill = payload.get("skill", "")
            self._current.top_score = float(payload.get("score", 0.0))

    def _handle_skill_started(self, payload: dict) -> None:
        with self._lock:
            if self._current is None:
                return
            self._current._skill_started_at = time.monotonic()

    def _handle_skill_complete(self, payload: dict) -> None:
        with self._lock:
            if self._current is None:
                return
            elapsed = time.monotonic() - self._current._skill_started_at
            self._current.tool_calls.append({
                "name": payload.get("skill", ""),
                "success": bool(payload.get("success", True)),
                "duration_ms": int(elapsed * 1000),
            })

    def _handle_llm_complete(self, payload: dict) -> None:
        with self._lock:
            trace = self._current
            self._current = None  # reset for next turn

        if trace is None:
            return

        # Fill in LLM-level metrics from event payload
        trace.route = str(payload.get("route", ""))
        trace.tokens_in = int(payload.get("tokens_in", 0))
        trace.tokens_out = int(payload.get("tokens_out", 0))
        trace.cost_usd = float(payload.get("cost_usd", 0.0))
        elapsed_s = time.monotonic() - trace.started_at
        trace.latency_ms = int(elapsed_s * 1000)

        record = trace.to_record()

        # JSONL write — synchronous, append-only (fast)
        self._write_jsonl(record)

        # SQLite write — background thread (NFR-ORCH-011)
        threading.Thread(
            target=self._write_db,
            args=(record,),
            daemon=True,
            name="xochitl-obs-db",
        ).start()

    # ── Storage ───────────────────────────────────────────────────────────────

    def _write_jsonl(self, record: dict) -> None:
        """Append one JSON line to the ring buffer; rotate if > 10 MB (NFR-ORCH-010)."""
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

            # Rotate when the file exceeds the cap
            if _JSONL_PATH.exists() and _JSONL_PATH.stat().st_size > _MAX_JSONL_SIZE_BYTES:
                _JSONL_BAK_PATH.unlink(missing_ok=True)
                _JSONL_PATH.rename(_JSONL_BAK_PATH)

            with _JSONL_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass  # JSONL write is best-effort — never fail the caller

    def _write_db(self, record: dict) -> None:
        """Insert trace into the agent_traces SQLite table (background thread)."""
        try:
            from src import database as _db
            with _db.get_connection() as conn:
                _db.insert_agent_trace(conn, record)
        except Exception:
            pass  # DB write is best-effort — never fail the caller
