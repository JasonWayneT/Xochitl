"""BackgroundReview — passive per-turn learning daemon.

Inspired by Hermes agent/background_review.py. After every completed turn,
a daemon thread fires a lightweight local LLM call to extract new facts about
the user from the exchange. Findings are written to the KnowledgeBase (Tier 2)
so they're immediately searchable in future turns — no "remember that" required.

Design principles:
- Never blocks the main thread (daemon=True, queue-based)
- Never crashes the main thread (all exceptions are swallowed)
- Only writes NEW information (model must say NONE if nothing new)
- Rate-limited to avoid spamming the KB on short exchanges
- Uses the same local router model to keep it cheap and fast
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum seconds between KB writes — prevents noise from rapid-fire short turns
_MIN_WRITE_INTERVAL_SECS = 30

# If the model's extraction is shorter than this it's probably noise
_MIN_OBSERVATION_CHARS = 12

# Sentinel values the model uses to signal "nothing to extract"
_NO_EXTRACT_VALUES = {
    "none", "n/a", "nothing", "nothing new", "no new information",
    "no new facts", "nothing relevant", "nothing to extract",
}

_REVIEW_PROMPT = """\
You are a passive observer reading a single conversation exchange.
Your job is to extract NEW facts about the user that would help personalize future responses.

Look for:
- Explicit corrections ("no, I meant...", "that's wrong", "actually...")
- Preferences revealed by how they asked or how they reacted to the response
- Personal context (role, tools they use, projects, recurring habits)
- Tone signals that reveal working style (impatient, casual, highly technical, etc.)
- Domain knowledge gaps or areas of expertise shown by how they phrased things

Rules:
- If NOTHING clearly new is revealed, reply with the single word: NONE
- If something IS new, reply with ONE compact plain-text sentence (under 200 chars)
- Write as a note ABOUT the user, not TO the user
- Do NOT state the obvious ("user asked about X" is useless)
- Do NOT repeat facts that are implicit from the exchange topic
- Corrections and pushback are the strongest signal — weight them highest

Good examples:
  User corrects model on file path → "User is on Windows and stores projects under D:\\CodeProjects."
  User says "keep it short" twice → "User prefers concise responses without preamble."
  User uses precise SQL terminology → "User is comfortable with relational databases and SQL."

Bad examples:
  "User asked about the weather." (obvious)
  "User wanted help with code." (not a personal fact)

Exchange to review:
USER: {user_input}
XOCHITL: {assistant_response}

Your observation (ONE sentence or NONE):"""


_STRUCTURED_EXTRACT_PROMPT = """\
Extract ONE structured fact about the user from this exchange. Output ONLY valid JSON.

Exchange:
USER: {user_input}
XOCHITL: {assistant_response}

Schema:
{{"fact": "<third-person statement under 180 chars>", "category": "<preference|context|project|skill|constraint|goal>", "confidence": <0.0-1.0>}}

Confidence guide: explicit correction=0.95, stated preference=0.80, revealed by behavior=0.65, implied=0.45
If nothing durable to extract, output: {{"fact": "", "category": "context", "confidence": 0.0}}

JSON only:"""

_VALID_CATEGORIES = {"preference", "context", "project", "skill", "constraint", "goal"}


class _TurnData:
    """A single turn queued for background review."""

    __slots__ = ("user_input", "assistant_response", "project", "queued_at")

    def __init__(self, user_input: str, assistant_response: str, project: Optional[str]) -> None:
        self.user_input = user_input[:2000]           # cap to avoid huge LLM calls
        self.assistant_response = assistant_response[:1500]
        self.project = project
        self.queued_at = time.monotonic()


class BackgroundReview:
    """Daemon that extracts passive user observations after each turn.

    Usage in XochitlChat::

        self._background_review = BackgroundReview()
        self._background_review.start()

        # At end of each main-path turn:
        self._background_review.queue_turn(user_input, response, project=self.current_project)

        # At session end (optional):
        self._background_review.shutdown()
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[Optional[_TurnData]] = queue.Queue(maxsize=20)
        self._thread: Optional[threading.Thread] = None
        self._last_write_at: float = 0.0
        self._running = False

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the daemon thread. Safe to call multiple times."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._worker,
            name="xochitl-background-review",
            daemon=True,
        )
        self._thread.start()

    def queue_turn(
        self,
        user_input: str,
        assistant_response: str,
        project: Optional[str] = None,
    ) -> None:
        """Queue a completed turn for background review. Non-blocking."""
        if not self._running:
            return
        # Skip turns that are too short to carry personality signal
        if len(user_input.strip()) < 8:
            return
        turn = _TurnData(user_input, assistant_response, project)
        try:
            self._queue.put_nowait(turn)
        except queue.Full:
            pass  # queue full — drop silently, never block

    def shutdown(self, timeout: float = 2.0) -> None:
        """Signal the worker to stop and wait briefly for it to drain."""
        if not self._running:
            return
        self._running = False
        try:
            self._queue.put_nowait(None)  # poison pill
        except queue.Full:
            pass
        if self._thread:
            self._thread.join(timeout=timeout)

    # ── Worker ────────────────────────────────────────────────────────────────

    def _worker(self) -> None:
        """Long-running daemon loop — processes queued turns one at a time."""
        while True:
            try:
                turn = self._queue.get(timeout=60)
            except queue.Empty:
                continue

            if turn is None:  # poison pill
                break

            try:
                self._process(turn)
            except Exception as exc:
                logger.debug("background_review: error processing turn: %s", exc)
            finally:
                self._queue.task_done()

    def _process(self, turn: _TurnData) -> None:
        """Run both extraction passes and write findings to KB + structured DB."""
        now = time.monotonic()
        if (now - self._last_write_at) < _MIN_WRITE_INTERVAL_SECS:
            return

        observation = self._extract(turn)
        structured = self._extract_structured(turn)

        if not observation and not structured:
            return

        self._write(observation, structured, turn.project)
        self._last_write_at = time.monotonic()

    def _extract(self, turn: _TurnData) -> Optional[str]:
        """Call the local model and return a cleaned observation, or None."""
        try:
            from src.llm_interface import call_local, ROUTER_MODEL
        except ImportError:
            return None

        prompt = _REVIEW_PROMPT.format(
            user_input=turn.user_input,
            assistant_response=turn.assistant_response,
        )
        try:
            result = call_local(
                messages=[{"role": "user", "content": prompt}],
                model=ROUTER_MODEL,
            )
        except Exception:
            return None

        if result.error:
            return None

        raw = (result.content or "").strip()
        if not raw:
            return None

        # Normalise and filter sentinel values
        cleaned = raw.strip(".").strip()
        if cleaned.lower() in _NO_EXTRACT_VALUES:
            return None
        if len(cleaned) < _MIN_OBSERVATION_CHARS:
            return None
        # Reject multi-sentence dumps — we want one tight fact
        if cleaned.count(". ") > 2:
            cleaned = cleaned.split(". ")[0].strip()

        return cleaned if cleaned else None

    def _extract_structured(self, turn: _TurnData) -> Optional[dict]:
        """Second pass: extract a categorized fact with confidence score for DB storage."""
        try:
            from src.llm_interface import call_local, ROUTER_MODEL
        except ImportError:
            return None

        prompt = _STRUCTURED_EXTRACT_PROMPT.format(
            user_input=turn.user_input,
            assistant_response=turn.assistant_response,
        )
        try:
            result = call_local(
                messages=[{"role": "user", "content": prompt}],
                model=ROUTER_MODEL,
            )
        except Exception:
            return None

        if result.error or not result.content:
            return None

        raw = result.content.strip()
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.MULTILINE).strip()

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None

        fact = (data.get("fact") or "").strip()
        category = str(data.get("category", "context")).strip()
        confidence = float(data.get("confidence", 0.0))

        if not fact or confidence < 0.4 or category not in _VALID_CATEGORIES:
            return None

        return {"fact": fact, "category": category, "confidence": confidence}

    def _write(self, observation: Optional[str], structured: Optional[dict], project: Optional[str]) -> None:
        """Write findings to KB (Tier 2), vector store (Tier 3), and structured DB."""
        try:
            from src.memory import KnowledgeBase, VectorMemory
        except ImportError:
            return

        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        title = f"passive_learning_{date_str}"

        # ── Tier 2: append unstructured observation to today's KB file ────────
        if observation:
            try:
                kb = KnowledgeBase()
                kb_dir = kb.kb_dir
                kb_dir.mkdir(parents=True, exist_ok=True)

                slug = re.sub(r'\W+', '_', title.lower()).strip('_')
                kb_path = kb_dir / f"{slug}.md"

                ts = datetime.now(timezone.utc).strftime("%H:%M UTC")
                entry_line = f"- [{ts}] {observation}"
                if project:
                    entry_line += f" (project: {project})"

                if kb_path.exists():
                    existing = kb_path.read_text(encoding="utf-8")
                    if observation[:60] in existing:
                        pass  # already recorded — skip KB write but continue to DB
                    else:
                        updated = existing.rstrip() + "\n" + entry_line + "\n"
                        tmp = kb_path.with_suffix(".tmp")
                        tmp.write_text(updated, encoding="utf-8")
                        tmp.replace(kb_path)
                else:
                    header = (
                        f"# Passive Learning — {date_str}\n"
                        f"tags: passive_learning, user_facts\n"
                        f"updated: {datetime.now(timezone.utc).isoformat()}\n\n"
                    )
                    updated = header + entry_line + "\n"
                    tmp = kb_path.with_suffix(".tmp")
                    tmp.write_text(updated, encoding="utf-8")
                    tmp.replace(kb_path)
            except Exception as exc:
                logger.debug("background_review: KB write failed: %s", exc)

        # ── Tier 3: best-effort vector store (no-op if Ollama is down) ────────
        if observation:
            try:
                VectorMemory().memorize(
                    topic="passive_learning",
                    summary=observation,
                    tags=["passive_learning", "user_facts"],
                    project=project,
                )
            except Exception:
                pass  # vector store optional — Tier 2 write already succeeded

        # ── Structured DB fact (category + confidence) ─────────────────────────
        if structured:
            try:
                from src import database as _db
                with _db.get_connection() as conn:
                    _db.upsert_memory_fact(
                        conn,
                        fact=structured["fact"],
                        category=structured["category"],
                        confidence=structured["confidence"],
                        source="background_review",
                        project=project,
                    )
            except Exception as exc:
                logger.debug("background_review: structured DB write failed: %s", exc)
