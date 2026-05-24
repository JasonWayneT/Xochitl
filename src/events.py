"""Xochitl event bus — thin observer for agent lifecycle events.

Fires named events during LLM processing so subscribers (terminal status,
future web SSE layer) can react without coupling to chat internals.

Standard events:
  routing_started   {"query": str}
  skill_matched     {"skill": str, "score": float}
  skill_started     {"skill": str, "params": list[str]}
  skill_complete    {"skill": str, "success": bool}
  llm_call_started  {"model": str, "route": str}
  llm_complete      {"route": str, "tokens_out": int}
  node_started      {"node": str, "label": str}
  node_complete     {"node": str}
  hitl_required     {"action": str, "risk": str}
"""
# Implements FR-ORCH-020 (Structured event emission for web SSE layer)
from __future__ import annotations

import threading
from typing import Callable

EventCallback = Callable[[str, dict], None]


class XochitlEventEmitter:
    """Thread-safe, zero-dependency event emitter.

    The terminal status context calls _status.update() directly for low latency.
    This emitter is the channel for the web layer — it subscribes a callback that
    converts events to SSE messages without any coupling to chat.py internals.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[EventCallback] = []

    def subscribe(self, callback: EventCallback) -> None:
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: EventCallback) -> None:
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not callback]

    def emit(self, event: str, payload: dict | None = None) -> None:
        """Fire event to all subscribers. Errors in any subscriber are swallowed."""
        with self._lock:
            subscribers = list(self._subscribers)
        for cb in subscribers:
            try:
                cb(event, payload or {})
            except Exception:
                pass


_emitter = XochitlEventEmitter()


def get_emitter() -> XochitlEventEmitter:
    return _emitter


def emit(event: str, payload: dict | None = None) -> None:
    """Convenience wrapper — emit on the module-level singleton."""
    _emitter.emit(event, payload)
