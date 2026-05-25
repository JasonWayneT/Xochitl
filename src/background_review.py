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

import hashlib
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

# ── CR-033: Persona drift detection ──────────────────────────────────────────
# Midpoint of 10–15 from planning doc. Every N completed turns a lightweight
# LLM-as-judge call compares recent assistant responses against SOUL.md identity.
_DRIFT_CHECK_INTERVAL: int = 12
# Rolling buffer of recent assistant responses kept for the drift judge.
_DRIFT_RESPONSE_BUFFER: int = 3
# Max chars sent to the drift judge (keeps the prompt ~100 tokens — NFR-ORCH-016).
_DRIFT_PROMPT_MAX_CHARS: int = 800

_DRIFT_JUDGE_PROMPT = """\
Identity: {identity}
Recent responses:{responses}
Does the language in these responses sound like a different, more generic AI \
rather than the defined personality? Answer only: DRIFT or OK."""

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

# ── CR-030: Correction detection ──────────────────────────────────────────────
# Keyword signals that strongly indicate the user is correcting Xochitl.
# Err on the side of sensitivity — false positives have low cost (slightly
# elevated confidence, bypassed rate limit); false negatives miss corrections.
_CORRECTION_SIGNALS: frozenset[str] = frozenset({
    "no,", "no.", "nope", "nah",
    "actually", "that's wrong", "thats wrong", "that is wrong",
    "not right", "not correct", "incorrect", "wrong",
    "i meant", "i mean", "i said", "i asked for",
    "that's not", "thats not", "that is not",
    "you misunderstood", "you got it wrong", "you missed",
    "not what i", "not what i wanted", "not what i asked",
    "let me clarify", "to clarify", "to be clear",
    "correction:", "correction —", "correcting you",
})


def _detect_correction(user_input: str) -> bool:
    """Return True if the user input contains correction-signal keywords.

    Implements FR-ORCH-031 — heuristic detection for CR-030 correction fast-path.
    Case-insensitive; matches on word boundaries using lowercased token check.
    """
    lowered = user_input.lower().strip()
    for signal in _CORRECTION_SIGNALS:
        if signal in lowered:
            return True
    return False


def _correction_preference_key(fact_text: str) -> str:
    """Deterministic preference key derived from the first 80 chars of a correction fact.

    Used by _store_correction_fact() to upsert recurring corrections into the
    preferences table with a stable key. Implements NFR-ORCH-006.
    """
    prefix = fact_text[:80].lower().encode("utf-8", errors="ignore")
    return "correction_" + hashlib.md5(prefix).hexdigest()[:12]


class _TurnData:
    """A single turn queued for background review."""

    __slots__ = ("user_input", "assistant_response", "project", "queued_at", "is_correction")

    def __init__(
        self,
        user_input: str,
        assistant_response: str,
        project: Optional[str],
        is_correction: bool = False,
    ) -> None:
        self.user_input = user_input[:2000]           # cap to avoid huge LLM calls
        self.assistant_response = assistant_response[:1500]
        self.project = project
        self.queued_at = time.monotonic()
        self.is_correction = is_correction


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
        # CR-033: persona drift detection state (FR-ORCH-042, NFR-ORCH-017)
        self._turn_count: int = 0
        self._correction_turns: int = 0
        self._recent_responses: list[str] = []
        self._drift_detected: bool = False
        self._drift_lock: threading.Lock = threading.Lock()
        # CR-034: implicit rephrase detection — previous user input buffer (FR-PREF-002)
        self._prev_user_input: str = ""

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
        """Queue a completed turn for background review. Non-blocking.

        Correction turns (FR-ORCH-031) are flagged so _process() can bypass
        the rate limiter and store with elevated confidence.
        """
        if not self._running:
            return
        # Skip turns that are too short to carry personality signal
        if len(user_input.strip()) < 8:
            return
        is_corr = _detect_correction(user_input)
        turn = _TurnData(user_input, assistant_response, project, is_correction=is_corr)
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

    # ── CR-033: Persona drift public API ─────────────────────────────────────

    @property
    def drift_detected(self) -> bool:
        """True if the last drift check found persona drift (FR-ORCH-042).

        Thread-safe: reads under _drift_lock.
        """
        with self._drift_lock:
            return self._drift_detected

    def clear_drift(self) -> None:
        """Reset the drift flag after the identity reminder has been injected.

        Called by _agent_loop() immediately after appending
        _DRIFT_IDENTITY_REMINDER to the system prompt (FR-ORCH-043).
        Thread-safe: writes under _drift_lock.
        """
        with self._drift_lock:
            self._drift_detected = False

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
        """Run drift check, then both extraction passes, then write to KB + DB.

        CR-030: correction turns bypass _MIN_WRITE_INTERVAL_SECS so they are
        always captured regardless of how recently a fact was last written.
        Implements FR-ORCH-031.

        CR-033: update turn counter and correction tracker; fire drift check
        when interval or correction-pressure conditions are met (FR-ORCH-042).
        """
        # CR-033: update rolling buffers (FR-ORCH-042)
        self._turn_count += 1
        if turn.is_correction:
            self._correction_turns += 1
        self._recent_responses = (
            self._recent_responses + [turn.assistant_response[:200]]
        )[-_DRIFT_RESPONSE_BUFFER:]

        # CR-033: drift check on regular interval or correction pressure
        if self._should_run_drift_check():
            self._correction_turns = 0  # reset correction counter after check
            self._run_drift_check()

        # CR-034: rephrase detection (FR-PREF-002)
        if self._prev_user_input:
            self._maybe_store_rephrase(self._prev_user_input, turn.user_input, turn.project)
        self._prev_user_input = turn.user_input

        now = time.monotonic()
        # Correction turns skip the rate limit — they carry the highest signal.
        if not turn.is_correction and (now - self._last_write_at) < _MIN_WRITE_INTERVAL_SECS:
            return

        observation = self._extract(turn)
        structured = self._extract_structured(turn)

        if not observation and not structured:
            return

        self._write(observation, structured, turn.project, is_correction=turn.is_correction)
        self._last_write_at = time.monotonic()

    # ── CR-033: Persona drift detection helpers ───────────────────────────────

    def _should_run_drift_check(self) -> bool:
        """Return True when drift check trigger conditions are met.

        Implements FR-ORCH-042 trigger logic (named method for testability).
        Two conditions:
          - Regular interval: turn_count is a non-zero multiple of _DRIFT_CHECK_INTERVAL
          - Correction pressure: 2+ correction turns accumulated since last check
        """
        regular = self._turn_count > 0 and (self._turn_count % _DRIFT_CHECK_INTERVAL == 0)
        pressure = self._correction_turns >= 2
        return regular or pressure

    def _run_drift_check(self) -> None:
        """Get identity anchor and run the drift judge (FR-ORCH-042).

        Swallows all exceptions — drift check must never disrupt the thread.
        """
        try:
            identity = self._get_identity_anchor()
            self._check_drift_with_identity(identity)
        except Exception as exc:
            logger.debug("background_review: drift check error: %s", exc)

    def _check_drift_with_identity(self, identity: str) -> None:
        """LLM-judge drift check using the provided identity anchor.

        Separated from _run_drift_check() for testability (NFR-ORCH-016).
        Uses call_local (local model) with a capped prompt (~100 tokens).
        Sets _drift_detected=True when response contains "DRIFT".

        Args:
            identity: The [IDENTITY] anchor text from SOUL.md.
        """
        if not identity or len(self._recent_responses) < 2:
            return
        try:
            from src.llm_interface import call_local, ROUTER_MODEL
        except ImportError:
            return
        excerpts = "\n".join(
            f"\n[R{i + 1}] {r[:150]}"
            for i, r in enumerate(self._recent_responses)
        )
        prompt = _DRIFT_JUDGE_PROMPT.format(
            identity=identity[:200],
            responses=excerpts,
        )[:_DRIFT_PROMPT_MAX_CHARS]
        try:
            result = call_local(
                messages=[{"role": "user", "content": prompt}],
                model=ROUTER_MODEL,
            )
        except Exception as exc:
            logger.debug("background_review: drift LLM call failed: %s", exc)
            return
        if result.error:
            return
        answer = (result.content or "").strip().upper()
        if "DRIFT" in answer:
            with self._drift_lock:
                self._drift_detected = True
            logger.debug("background_review: persona drift detected")

    # ── CR-034: Implicit rephrase detection ──────────────────────────────────

    def _maybe_store_rephrase(self, prev: str, curr: str, project: Optional[str]) -> None:
        """Store a memory fact when curr appears to rephrase prev (FR-PREF-002).

        Wrapped entirely in try/except — must never raise (NFR-PREF-001).

        Args:
            prev: Previous user input from the last processed turn.
            curr: Current user input from this turn.
            project: Active project slug, forwarded to upsert_memory_fact.
        """
        try:
            from src.preference_learning import is_rephrased_query
            if not is_rephrased_query(prev, curr):
                return
            from src import database as _db
            with _db.get_connection() as conn:
                _db.upsert_memory_fact(
                    conn,
                    fact=(
                        f"User rephrased '{prev[:60]}' as '{curr[:60]}'"
                        " — second framing preferred."
                    ),
                    category="preference",
                    confidence=0.65,
                    source="implicit_rephrase_detection",
                    project=project,
                )
        except Exception as exc:
            logger.debug("background_review: rephrase storage failed: %s", exc)

    def _get_identity_anchor(self) -> str:
        """Load the [IDENTITY] section from SOUL.md via SoulEngine.

        Returns empty string on any failure — drift check simply skips
        when no identity anchor is available (NFR-ORCH-017).
        """
        try:
            from src.context_manager import SoulEngine
            soul = SoulEngine()
            soul.ingest()
            return soul.identity_anchor or ""
        except Exception:
            return ""

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

    def _store_correction_fact(
        self,
        conn: object,
        fact_text: str,
        project: Optional[str],
    ) -> None:
        """Store a correction fact as a high-confidence preference; escalate
        to the preferences table if this correction has been seen before.

        Implements FR-ORCH-031 (confidence override) and NFR-ORCH-006 (escalation).
        """
        try:
            from src import database as _db
            import sqlite3
            if not isinstance(conn, sqlite3.Connection):
                return

            _db._ensure_memory_facts_table(conn)  # type: ignore[attr-defined]

            # Pre-check for near-duplicate (recurring correction)
            existing = conn.execute(  # type: ignore[union-attr]
                """SELECT id FROM memory_facts
                   WHERE LOWER(SUBSTR(fact, 1, 80)) = LOWER(SUBSTR(?, 1, 80))
                     AND superseded_by IS NULL
                   LIMIT 1""",
                (fact_text,),
            ).fetchone()

            # Store / update in memory_facts as a preference with high confidence
            _db.upsert_memory_fact(
                conn,
                fact=fact_text,
                category="preference",
                confidence=0.9,
                source="correction_detection",
                project=project,
            )

            # NFR-ORCH-006: recurring correction → escalate to preferences table
            if existing:
                pref_key = _correction_preference_key(fact_text)
                _db.upsert_preference(
                    conn,
                    {
                        "scope": "global",
                        "category": "communication",
                        "preference_key": pref_key,
                        "preference_value": fact_text,
                        "source": "correction_pattern",
                        "confidence": 0.95,
                    },
                )
        except Exception as exc:
            logger.debug("background_review: correction storage failed: %s", exc)

    def _write(
        self,
        observation: Optional[str],
        structured: Optional[dict],
        project: Optional[str],
        is_correction: bool = False,
    ) -> None:
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

        # ── CR-030: Correction fast-path — override category/confidence and
        #    escalate to preferences table if this correction recurs (NFR-ORCH-006) ──
        if is_correction and structured and structured.get("fact"):
            try:
                from src import database as _db
                with _db.get_connection() as conn:
                    self._store_correction_fact(conn, structured["fact"], project)
            except Exception as exc:
                logger.debug("background_review: correction fast-path failed: %s", exc)
