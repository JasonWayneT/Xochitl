"""XochitlChat — conversational layer over the tiered router.
# Implements FR-ORCH-003 (PreFlight Fact Injection via ContextManager)
# Implements FR-ORCH-004 (Provenance Tagging via ContextManager)
# Implements FR-ORCH-005 (Skill Manifest — skills described in every system prompt)
# Implements FR-ORCH-006 (Universal ContextManager — all paths use cm.assemble_system_prompt())
# Implements FR-ORCH-007 (Natural Confirmation — LLM fallback for yes/no)
# Implements FR-ORCH-008 (Agent Loop — <skill_call> parsing and auto-execution)
# Implements FR-ORCH-009 (Skill-Aware History — role=tool turns in session history)
# Implements FR-UI-001 (Status Tiers — Rich Live sub-task feed)
# Implements FR-UI-002 (Smart Ctrl-C — 2-stage: cancel then exit)
# Implements FR-UI-003 (OSC 8 terminal hyperlinks for file paths)

Design principles (from XOCHITL_CONVERSATIONAL_HARNESS.md):
- Natural back-and-forth, like Claude.ai in the terminal
- LLM knows its available skills via SkillManifestEngine and can invoke them
- File ops go through FileTools permission model (overwrite/delete need consent)
- Orchestrator is a tool Xochitl uses when user says "delegate it" — not a default
"""

import concurrent.futures
import json
import os
import re
import signal
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.action_disclosure import (
    build_why_expansion,
    format_compact_result,
    infer_action_label,
    is_why_request,
)
from src.terminal_output import format_skill_output

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.prompt import Prompt
    from rich.spinner import Spinner
    from rich.text import Text
except ModuleNotFoundError:
    class Console:
        def __init__(self, *args, **kwargs):
            pass

        def print(self, *args, **kwargs):
            end = kwargs.get("end", "\n")
            print(*args, end=end)

    class Live:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def update(self, *args, **kwargs):
            return None

    class Markdown(str):
        pass

    class Prompt:
        @staticmethod
        def ask(prompt: str, **kwargs) -> str:
            return input(f"{prompt} ")

    class Spinner:
        pass

    class Text:
        def __init__(self):
            self.parts: list[str] = []

        def append(self, text: str, **kwargs) -> None:
            self.parts.append(text)

        def __str__(self) -> str:
            return "".join(self.parts)

from src.router import get_router, _live_db_context, _resolve_file_context
from src.context_loader import build_system_prompt
from src.context_manager import ContextManager
from src.memory import read_memory
from src.background_review import BackgroundReview
from src import database as db
from src import events as _events
from src.file_tools import FileTools
from src.governor import SessionGovernor, Tier as _GovTier  # FR-ORCH-025
from src.skills.base import Skill

# FR-UX-001: TERM=dumb detection for no-markup fallback
_TERM_DUMB = os.getenv("TERM", "").lower() == "dumb"
console = Console(markup=not _TERM_DUMB, highlight=not _TERM_DUMB)

# FR-UX-002: Spanish vocabulary + shared constants — imported from constants.py.
# Re-exported here so ``from src.chat import _OK`` etc. continues to work for
# any caller (tests, session modules) that imports these names from this module.
# Do NOT remove these imports without updating all downstream import sites.
from src.constants import (
    _OK, _FYI, _ERR,
    _CONFIRM_YES, _CONFIRM_NO,
    _SKILL_CALL_RE,
    _SKILL_INJECT_THRESHOLD,
    _OPEN_ENDED_SCORE_THRESHOLD,
    _MUTATING_SKILL_ACTIONS,
    _ALWAYS_APPROVE,
)

_PROJECT_ROOT = Path(__file__).parent.parent

# ── OSC 8 terminal hyperlink helper (FR-UI-003) ────────────────────────────

def _osc8_link(path: str) -> str:
    """Format a file path as an OSC 8 clickable terminal hyperlink.

    Implements FR-UI-003. Works in Windows Terminal, VS Code integrated terminal.
    Falls back to plain path if TERM=dumb or terminal doesn't support OSC 8.
    """
    if _TERM_DUMB:
        return path
    abs_path = str(Path(path).resolve())
    uri = "file:///" + abs_path.replace("\\", "/")
    # OSC 8 ;; URI ST   text   OSC 8 ;; ST
    return f"\033]8;;{uri}\033\\{path}\033]8;;\033\\"


# ── Status Tier renderer (FR-UI-001) ─────────────────────────────────────────

class _StatusContext:
    """Context manager that shows a live bloom-wave status during LLM calls.

    Implements FR-UI-001 — replaces static 'thinking...' with a Rich Live
    display: a bloom wave that rolls across five flower positions, paired
    with a randomly chosen tip about Xochitl's features. Each query picks
    a different tip so the user learns something new while they wait.
    """

    # Bloom wave — a bloom state rolls left-to-right across 5 positions.
    # 9 frames at 50 ms each = 450 ms full cycle.
    _FLOWERS = [
        "✦ · · · ·",
        "✿ ✦ · · ·",
        "❀ ✿ ✦ · ·",
        "❁ ❀ ✿ ✦ ·",
        "· ❁ ❀ ✿ ✦",
        "· · ❁ ❀ ✿",
        "· · · ❁ ❀",
        "· · · · ❁",
        "· · · · ·",
    ]

    # Loading tips — one is picked at random each time Xochitl starts thinking.
    # Implements FR-JARV-010 — expanded from 18 to 30 JARVIS-style tips.
    _TIPS = [
        "/brief for compact responses  —  /detailed for deep dives",
        "xochitl today fills your queue with your top 3 priority tasks",
        "ask 'why did you do that?' and I'll show you my reasoning",
        "I remember your preferences and style across sessions",
        "xochitl sync pushes your completed tasks up to Notion",
        "mention any file path and I'll read it automatically",
        "xochitl plan 'name' decomposes a project into queued tasks",
        "your queue holds exactly 3 tasks — focused work, not overwhelm",
        "BMAD walks through Business Model → Architecture → Design",
        "xochitl pull fetches the latest tasks from Notion",
        "hedged language means I'm less than 80% confident — take note",
        "xochitl done <n> marks a task complete and refreshes your queue",
        "simple tasks stay on your local GPU — your data never leaves",
        "I detect when you rephrase a question and learn your preference",
        "I stay on local models by default and only go cloud when needed",
        "ask me to 'think through' something for a more deliberate answer",
        "/dismiss clears a proactive alert you've already seen",
        "I track my own persona drift and self-correct in long sessions",
        "@GmailSkill or @MapsSkill bypasses scoring — direct skill routing",
        "/workflow save <name> captures this session as a reusable procedure",
        "say 'new note:' to drop a fleeting thought into your Zettelkasten",
        "/debug skill shows why a skill did or didn't activate",
        "I surface deadline warnings automatically — just keep due dates in Notion",
        "BMAD → SDD → Code is the full pipeline: idea to working app",
        "I run a background drift check to keep my personality on-track",
        "/status shows a live health snapshot of all my systems",
        "the Zettelkasten skill links ideas across your vault automatically",
        "xochitl explorer digs deep into topics with multi-pass research",
        "/budget shows how much of your session token limit is consumed",
        "I save your communication style silently — no preference forms needed",
    ]

    def __init__(self, label: str = ""):
        import random
        self._tip = random.choice(self._TIPS)
        self._note = "starting up"
        self._start = time.monotonic()
        self._live: Optional[Live] = None
        self._frame = 0
        self._stop_event = threading.Event()
        self._refresh_thread: Optional[threading.Thread] = None

    def _render(self) -> Text:
        flower = self._FLOWERS[self._frame % len(self._FLOWERS)]
        self._frame += 1
        t = Text()
        t.append("  ", style="")
        t.append(f"{flower}   ", style="bold magenta")
        t.append("tip  ", style="dim cyan")
        t.append(self._tip, style="dim")
        return t

    def update(self, label: str) -> None:
        # _note tracks pipeline stage internally; not shown visually (tip takes that space)
        self._note = (label or "working").strip().lower()
        if self._live:
            self._live.update(self._render())

    def _tick(self) -> None:
        while not self._stop_event.is_set():
            if self._live:
                self._live.update(self._render())
            time.sleep(0.05)

    def __enter__(self) -> "_StatusContext":
        if not _TERM_DUMB:
            self._live = Live(
                self._render(),
                console=console,
                refresh_per_second=10,
                transient=True,
            )
            self._live.__enter__()
            self._stop_event.clear()
            self._refresh_thread = threading.Thread(target=self._tick, daemon=True)
            self._refresh_thread.start()
        return self

    def __exit__(self, *args) -> None:
        self._stop_event.set()
        if self._refresh_thread:
            self._refresh_thread.join(timeout=0.3)
            self._refresh_thread = None
        if self._live:
            self._live.__exit__(*args)
            self._live = None


def _auto_authorize_decision(cwd: Path, home: Path, enabled: bool) -> tuple[str, str]:
    """Decide whether to auto-authorize the working directory at session start.

    Implements FR-EXEC-006 (CR-052). Pure function — no side effects — so the
    decision logic is unit-testable without touching the security registry.

    Args:
        cwd: The current working directory.
        home: The user's home directory.
        enabled: Whether XCH_AUTO_AUTHORIZE is set.

    Returns:
        Tuple of (action, payload):
          ("disabled", "")        — feature off; do nothing.
          ("skip_home", message)  — CWD is home; too broad, skip with a warning.
          ("authorize", path_str) — authorize this resolved path.
    """
    if not enabled:
        return ("disabled", "")
    cwd_r = cwd.resolve()
    if cwd_r == home.resolve():
        return (
            "skip_home",
            "XCH_AUTO_AUTHORIZE set but the working directory is your home folder "
            "— skipping (too broad). cd into a project first.",
        )
    return ("authorize", str(cwd_r))


def _print_boot_banner(con: Console) -> None:
    # Implements FR-UX-001 (WIP dashboard header in interactive loop)
    con.print()
    con.print("      [bold magenta]✿[/bold magenta] [bold yellow]❀[/bold yellow] [bold magenta]✿[/bold magenta]")
    con.print("    [bold yellow]❀[/bold yellow]   [bold magenta]✿[/bold magenta]   [bold yellow]❀[/bold yellow]    [bold cyan]Xochitl[/bold cyan]")
    con.print("      [bold magenta]✿[/bold magenta] [bold yellow]❀[/bold yellow] [bold magenta]✿[/bold magenta]     [dim]Personal AI System[/dim]")
    con.print()

    # WIP snapshot — 2-line dashboard
    try:
        from src import database as _db
        from src.config import get_wip_limit
        with _db.get_connection() as conn:
            queue = _db.get_queue(conn)
        limit = get_wip_limit()
        if queue:
            count = len(queue)
            first = queue[0]["description"][:48]
            slots = f"[bold]{count}[/bold][dim]/{limit}[/dim]"
            con.print(f"  [dim]WIP[/dim] {slots}  [dim]·[/dim]  {first}{'[dim]…[/dim]' if len(queue[0]['description']) > 48 else ''}")
        else:
            con.print(f"  [dim]WIP 0/{limit} — queue empty. Run[/dim] [bold]xochitl today[/bold] [dim]to fill it.[/dim]")
    except Exception:
        pass  # never crash startup over a dashboard read failure

    # FR-JARV-008: session resume summary — show last session context if < 24h gap.
    # Helps the user immediately recall where they left off without asking.
    try:
        from src import database as _db2
        with _db2.get_connection() as _conn2:
            _row = _conn2.execute(
                "SELECT context_summary, last_active FROM sessions "
                "WHERE context_summary IS NOT NULL AND context_summary != '' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if _row:
            _summary, _last_active = _row[0], _row[1]
            if _summary and _last_active:
                from datetime import datetime as _dt
                try:
                    _la = _dt.fromisoformat(str(_last_active))
                    _gap_h = (_dt.now() - _la).total_seconds() / 3600
                    if _gap_h < 24:
                        _summary_short = str(_summary)[:100]
                        con.print(f"  [dim]↩ last session:[/dim] [dim cyan]{_summary_short}[/dim cyan]")
                except Exception:
                    pass
    except Exception:
        pass  # FR-JARV-008: NFR-JARV-003 — never crash startup over resume query

    # A2 — Anticipation gate: surface a one-line hint when ≥2 signals converge.
    # Implements FR-CONV-002. Informational only — never takes action (NFR-CONV-001).
    try:
        from src.anticipation import AnticipationGate
        _hint = AnticipationGate().check_from_db()
        if _hint:
            con.print(f"  [dim]{_hint}[/dim]")
            con.print()
    except Exception:
        pass  # never crash startup over an anticipation gate failure
    con.print()


# _CONFIRM_YES / _CONFIRM_NO imported from src.constants above.

_TASK_KEYWORDS    = ["task", "queue", "what's on my plate", "what am i working on", "blocked", "in progress", "today"]
_BG_KEYWORDS      = ["background", "orchestrator", "delegated task", "how is the agent", "what are background"]
_ACTION_KEYWORDS  = ["sync", "pull from notion", "push to notion", "notion", "start working", "work on", "delegate"]
_FILE_READ_KW     = ["read", "open", "show me", "what is in", "what's in", "look at"]
_FILE_WRITE_KW    = ["write", "create file", "save to", "overwrite"]
_FILE_DELETE_KW   = ["delete", "remove file"]
_FILE_EXTENSIONS  = [".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv", ".env"]
_FILE_VERB_KW     = ["read", "write", "delete", "show", "list", "analyze",
                     "look at", "check", "view", "open", "see"]
_PATH_INDICATOR_KW = ["file", "folder", "directory", "project", "path"]
_BMAD_KEYWORDS    = ["plan", "design", "architect", "prd", "sprint", "feature", "workflow"]

# SDD / project lifecycle keywords
_BUILD_KEYWORDS   = [
    "i want to build", "i want to make", "i want to create", "i want to rebuild",
    "build an app", "create an app", "new app", "new project", "start a project",
    "let's build", "let's make", "let's create", "rebuild",
]
_SDD_KEYWORDS      = ["spec", "requirement", "fr-", "ac-", "ec-", "traceability"]
_ISSUE_KEYWORDS    = ["bug", "issue", "broken", "doesn't work", "failing", "wrong behavior", "error in"]
_CODE_GEN_KEYWORDS = ["scaffold", "generate code", "implement the", "code for", "build the backend", "build the frontend"]
_RESEARCH_KEYWORDS = [
    "research", "devil's advocate", "adversarial", "challenge this", "challenge that",
    "synthesize", "look into", "find out about", "what do we know about",
    "poke holes", "stress test this", "steelman", "play devil",
]


# ── Skill-call parsing (FR-ORCH-008) ─────────────────────────────────────────

# FR-ORCH-042: @SkillName explicit routing — user bypasses can_handle() scoring.
# Matches "@GmailSkill ...", "@gmail ...", "@maps ..." at start of message.
_AT_SKILL_RE = re.compile(r'^@(\w+)\b', re.IGNORECASE)

# _SKILL_CALL_RE imported from src.constants above.


def _parse_skill_calls(response: str) -> list[tuple[str, dict]]:
    """Extract all <skill_call> blocks from an LLM response. FR-PERF-007 (CR-050 C3).

    Delegates to src.agent.skill_parser for testable pure-function implementation.

    Args:
        response: Full LLM response text.

    Returns:
        Ordered list of (skill_name, params_dict) tuples; empty when none found.
    """
    from src.agent.skill_parser import parse_skill_calls
    return parse_skill_calls(response)


def _parse_skill_call(response: str) -> Optional[tuple[str, dict]]:
    """Extract the first <skill_call> from an LLM response. Backward-compatible shim.

    Implements FR-ORCH-008.
    """
    calls = _parse_skill_calls(response)
    return calls[0] if calls else None


# _MUTATING_SKILL_ACTIONS, _SKILL_INJECT_THRESHOLD, _OPEN_ENDED_SCORE_THRESHOLD
# imported from src.constants above.

# Phase 2: minimum can_handle() score to inject a skill into the system prompt.
# Matches the 0.6 suggestion threshold from Skill base docstring with a small buffer.
# Value: _SKILL_INJECT_THRESHOLD = 0.65  (defined in src/constants.py)

# CR-032: skill-score threshold below which intent is considered open-ended.
# Value: _OPEN_ENDED_SCORE_THRESHOLD = 0.2  (defined in src/constants.py)

# CR-033: identity reminder injected into system prompt when drift is detected.
# Placed at prompt end so transformer recency bias amplifies its effect (FR-ORCH-043).
_DRIFT_IDENTITY_REMINDER: str = (
    "\n\n---\n"
    "[IDENTITY REMINDER]\n"
    "You are Xochitl, not a generic assistant. "
    "Reconnect with your established voice: warm, direct, culturally grounded. "
    "No filler openers. No over-explanation.\n"
    "---"
)


# NOTE: _format_active_skill_block is the test-imported canonical location.
# A copy also exists in src/agent/pipeline.py.  Both must be kept in sync.
# Smoke test AC-CR049-006 imports directly from src.chat — do not move or
# rename without updating that test first.
# TODO: consolidate into src/skill_format.py once a shared utilities module exists.
def _format_active_skill_block(defn: dict) -> str:
    """Format one skill's tool_definition() as a focused per-turn system prompt block.

    Injected only when can_handle() scores above _SKILL_INJECT_THRESHOLD.
    The model sees the full invocation schema for the one relevant skill
    without the noise of the full manifest — fixes the hallucinated-XML problem
    by showing the exact <skill_call> format only when a skill is actually needed.
    """
    # Implements FR-ORCH-039 (examples injection), FR-ORCH-040 (proactive invocation)
    name        = defn.get("name", "")
    description = defn.get("description", "")
    when        = defn.get("when", "")
    params      = defn.get("params", {})
    examples    = defn.get("examples", [])

    lines = [
        "## Active Skill",
        f"The following skill is relevant to this request: **{name}**",
        f"Does: {description}",
        f"Use when: {when}",
        "",
        "To invoke it, output this EXACT format anywhere in your response:",
        "",
        f'  <skill_call name="{name}">{{"param": "value"}}</skill_call>',
        "",
        "Read-only skills execute immediately. "
        "Mutating skills are staged for user approval first.",
        "Invoke proactively when the request falls within this skill's domain — "
        "you do not need exact keyword matches, just clear intent.",
    ]
    if isinstance(examples, list) and examples:  # FR-HARD-006: guard against non-list values
        lines.append("")
        lines.append("Example triggers:")
        for ex in examples[:6]:
            lines.append(f'  · "{ex}"')
    if params:
        lines.append("")
        lines.append(f"Parameters for {name}:")
        for k, v in params.items():
            lines.append(f"  `{k}`: {v}")

    return "\n".join(lines)


class XochitlChat:
    """
    Primary conversational interface.

    Call start() to enter the interactive loop, or process_message() directly
    for single-turn usage (e.g. tests or the --with-orchestrator path).
    """

    def __init__(self, force_cloud: bool = False, with_orchestrator: bool = False, no_rich: bool = False):
        # FR-UX-001: --no-rich or TERM=dumb → plain console
        if no_rich or os.getenv("TERM", "").lower() == "dumb":
            global console
            console = Console(markup=False, highlight=False)

        self.router = get_router()
        self.file_tools = FileTools()
        self.force_cloud = force_cloud
        self.with_orchestrator = with_orchestrator

        self.session_history: list[dict] = []
        self.current_context: dict = {}
        self.session_id: Optional[int] = None
        self.current_project: Optional[str] = None

        # Skills are now managed by SkillRegistry (src/skills/__init__.py).
        # _builtin_skills and _skills retained as Optional stubs for any test
        # shims that set them directly; the skills property ignores them now.
        self._builtin_skills: Optional[list[Skill]] = None
        self._skills: Optional[list[Skill]] = None

        # FR-UI-002: Smart Ctrl-C — track last interrupt time for 2-stage exit
        self._last_interrupt: float = 0.0
        self._active_status: Optional[_StatusContext] = None

        # FR-UI-007: Staged message — queued via /next, runs after current response
        self._staged_message: Optional[str] = None
        # FR-UI-006: Last cancelled message — resendable via /retry
        self._last_cancelled: Optional[str] = None
        # Guard against runaway staged-message chains (e.g. skill → stage → skill → ...)
        self._consecutive_staged: int = 0

        # Phase 3: passive learning daemon — starts immediately, runs for session lifetime
        self._background_review = BackgroundReview()
        self._background_review.start()

        # CR-038: controlled initiative engine (FR-INIT-001)
        # FR-RELY-004 (CR-050 B5): pass db_path so dismissals survive session restarts.
        try:
            from src.initiative import InitiativeEngine
            self._initiative = InitiativeEngine(db_path=str(db.DB_PATH))
            self._background_review._initiative_engine = self._initiative
        except Exception:
            self._initiative = None  # type: ignore[assignment]

        # FR-UI-005: set to True inside _agent_loop when streaming already printed the response
        # so start() knows to skip _stream_response() to avoid double-printing.
        self._last_response_streamed: bool = False

        # CR-025: response mode tracking — tracks mode between turns for transition
        # announcements. Starts as conversational (default). (FR-ORCH-032)
        self._current_mode: str = "conversational"

        # CR-021: structured observability — subscribes to event bus, writes
        # per-turn traces to JSONL + SQLite (FR-ORCH-035).
        try:
            from src.observability import ObservabilityLogger
            self._obs_logger = ObservabilityLogger()
            self._obs_logger.start()
        except Exception:
            self._obs_logger = None  # type: ignore[assignment]

        # FR-ORCH-025: session token budget governor — tracks estimated spend and
        # applies progressive routing restrictions (FULL → PREFER_LOCAL → LOCAL_ONLY → HARD_STOP).
        self._governor = SessionGovernor()

        # FR-RELY-005 (CR-050 B6): decay stale memory facts in a background thread
        # so it never blocks session start.
        def _decay_bg() -> None:
            try:
                with db.get_connection() as _conn:
                    db.decay_memory_facts(_conn)
            except Exception:
                pass
        threading.Thread(target=_decay_bg, daemon=True).start()

        # FR-PERF-002 (CR-050 B2): turn-level ContextManager cache.
        # Static engines (soul, profile, config) are reused across turns.
        # Key: (history_len, last_mutating_skill, route).
        self._cm_cache: Optional[ContextManager] = None
        self._cm_cache_key: Optional[tuple] = None
        self._last_mutating_skill: str = ""

        # SkillScorer: created once per session, caches scores per input hash.
        from src.agent.skill_scorer import SkillScorer
        self._skill_scorer: SkillScorer = SkillScorer(
            self.skills, threshold=_SKILL_INJECT_THRESHOLD
        )

        # ConfirmationHandler: typed FSM replacing dict-key pending_action pattern.
        from src.session.confirmation import ConfirmationHandler
        self._confirmation: ConfirmationHandler = ConfirmationHandler(
            context=self.current_context,
            find_skill=self._find_skill_by_name,
            router=self.router,
            session_history=self.session_history,
            current_project=self.current_project,
            execute_pending_skill_call=self._execute_pending_skill_call,
            file_tools=self.file_tools,
        )

        # AgentPipeline: owns _agent_loop logic (extracted for testability).
        from src.agent.pipeline import AgentPipeline
        self._pipeline: AgentPipeline = AgentPipeline(
            router=self.router,
            skill_scorer=self._skill_scorer,
            find_skill=self._find_skill_by_name,
            execute_skill=self._execute_skill_safe,
            emit_action_line=self._emit_action_line,
            console_print=console.print,
            stage_skill_call=self._stage_skill_call_plan,
            background_review=self._background_review,
            initiative=self._initiative,
            drift_reminder=_DRIFT_IDENTITY_REMINDER,
        )

    @property
    def skills(self) -> list[Skill]:
        # FR-HARD-007: delegate to SkillRegistry; dynamic skills added via reload_dynamic().
        from src.skills import _registry
        _registry.reload_dynamic(self.current_project)
        return _registry.all()

    # ── Public interface ──────────────────────────────────────────────────────

    def _run_with_cancel(
        self,
        user_input: str,
        status_ctx: "_StatusContext",
    ) -> tuple[Optional[str], bool]:
        """Run process_message in a daemon thread so Ctrl-C can cancel cleanly.

        Implements FR-UI-006. Returns (response, was_cancelled).
        The LLM call runs in a daemon thread; the main thread polls with a short
        timeout so KeyboardInterrupt is caught here rather than killing the session.
        The thread is abandoned on cancel — it finishes in the background and is
        discarded when the session exits.
        """
        import queue as _queue
        result_q: _queue.Queue = _queue.Queue()

        def _worker() -> None:
            try:
                resp = self.process_message(user_input, _status=status_ctx)
                result_q.put(("ok", resp))
            except Exception as exc:  # noqa: BLE001
                result_q.put(("err", str(exc)))

        worker_thread = threading.Thread(target=_worker, daemon=True)
        worker_thread.start()

        try:
            while worker_thread.is_alive():
                worker_thread.join(timeout=0.15)
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled.[/dim]")
            return None, True

        try:
            status, value = result_q.get_nowait()
        except _queue.Empty:
            return None, True

        if status == "err":
            return f"{_ERR} — {value}", False
        return value, False  # type: ignore[return-value]

    def start(self) -> None:
        """Launch the interactive chat loop."""
        from src.stats import health_check

        _print_boot_banner(console)

        # FR-EXEC-006 (CR-052): opt-in auto-authorize of the working directory.
        _aa_action, _aa_payload = _auto_authorize_decision(
            Path.cwd(), Path.home(), os.getenv("XCH_AUTO_AUTHORIZE") == "1"
        )
        if _aa_action == "skip_home":
            console.print(f"[dim]⚠ {_aa_payload}[/dim]")
        elif _aa_action == "authorize":
            try:
                from src.security import authorize_directory
                authorize_directory(Path(_aa_payload))
                console.print(f"[dim]✓ Auto-authorized working directory: {_aa_payload}[/dim]")
            except Exception as exc:
                console.print(f"[dim]Auto-authorize skipped: {exc}[/dim]")

        health = health_check()
        if not health["local_model"] and not self.force_cloud:
            console.print("[dim]Local model offline — routing cloud.[/dim]\n")
        for issue in health.get("issues", []):
            console.print(f"[dim]  Warning: {issue}[/dim]")

        if self.with_orchestrator:
            self._start_orchestrator_daemon()

        with db.get_connection() as conn:
            self.session_id = db.create_session(conn)

        # CR-034: decay implicit preferences on session start (FR-PREF-003)
        try:
            from src.preference_learning import decay_and_prune
            with db.get_connection() as conn:
                decay_and_prune(conn)
        except Exception:
            pass  # decay must never crash session start (NFR-PREF-001)

        # CR-035: compute personalization milestone once at session start (FR-PREF-004)
        self._milestone_block: str = ""
        try:
            from src.milestones import get_milestone, milestone_context_block
            import logging as _logging
            _ms_logger = _logging.getLogger(__name__)
            with db.get_connection() as conn:
                session_count = db.get_session_count(conn)
            milestone = get_milestone(session_count)
            _ms_logger.debug(
                "milestone: %s (total sessions: %d)", milestone.value, session_count
            )
            self._milestone_block = milestone_context_block(milestone)
        except Exception:
            pass  # milestone must never crash session start (NFR-PREF-002)

        console.print(
            "[dim]Type 'quit' or Ctrl+C to exit. "
            "Ctrl+C while thinking cancels. "
            "/next <message> to stage your next message.[/dim]\n"
        )

        try:
            while True:
                # ── Determine input source ────────────────────────────────────
                # If a staged message is queued, use it without prompting
                if self._staged_message:
                    self._consecutive_staged += 1
                    if self._consecutive_staged > 5:
                        console.print(
                            "[dim]⚠ Staged message loop detected — clearing queue "
                            "to prevent runaway.[/dim]"
                        )
                        self._staged_message = None
                        self._consecutive_staged = 0
                        continue
                    user_input = self._staged_message
                    self._staged_message = None
                    console.print(f"[dim]▶ staged:[/dim] [cyan]{user_input}[/cyan]")
                else:
                    self._consecutive_staged = 0
                    try:
                        user_input = Prompt.ask("[bold cyan]you[/bold cyan]")
                    except KeyboardInterrupt:
                        # FR-UI-002: Smart Ctrl-C — 2-stage exit (input phase)
                        now = time.monotonic()
                        if now - self._last_interrupt < 1.2:
                            console.print("\n[dim]Hasta luego 👋[/dim]\n")
                            break
                        else:
                            self._last_interrupt = now
                            staged_hint = (
                                f"  staged: '{self._staged_message}'"
                                if self._staged_message else ""
                            )
                            console.print(
                                f"\n[dim]Press Ctrl+C again to exit, or keep typing.{staged_hint}[/dim]"
                            )
                            continue
                    except EOFError:
                        break

                if not user_input.strip():
                    continue

                if user_input.strip().lower() in ("quit", "exit", "q", "bye"):
                    console.print("\n[dim]Hasta luego 👋[/dim]\n")
                    self._background_review.shutdown()
                    break

                if user_input.strip().lower() == "help":
                    from src.stats import help_text
                    console.print(help_text())
                    continue

                # Implements FR-SEC-001, FR-SEC-003, FR-SEC-004
                if user_input.strip().startswith("/"):
                    result = self._handle_slash_command(user_input.strip())
                    console.print(result)
                    console.print()
                    continue

                # ── FR-ORCH-025: Governor — session budget gate ───────────────
                _gov_tier = self._governor.tier()
                if _gov_tier == _GovTier.HARD_STOP:
                    console.print(f"\n[bold]Xochitl[/bold]: {self._governor.budget_message()}")
                    console.print()
                    continue  # skip LLM call entirely
                if _gov_tier == _GovTier.LOCAL_ONLY and self._governor.should_warn(_GovTier.LOCAL_ONLY):
                    console.print(
                        f"[dim yellow]⚠ Session budget limit reached — local model only. "
                        f"{self._governor.status_line()}[/dim yellow]"
                    )
                elif _gov_tier == _GovTier.PREFER_LOCAL and self._governor.should_warn(_GovTier.PREFER_LOCAL):
                    console.print(
                        f"[dim yellow]⚠ Approaching session budget — preferring local model. "
                        f"{self._governor.status_line()}[/dim yellow]"
                    )
                # FR-JARV-005: gradual approach warnings at 75% and 90% of next tier.
                elif _gov_tier == _GovTier.FULL:
                    if self._governor.should_warn_approach(_GovTier.PREFER_LOCAL, 0.90):
                        console.print(
                            f"[dim]Budget: 90% to prefer-local threshold — {self._governor.status_line()}[/dim]"
                        )
                    elif self._governor.should_warn_approach(_GovTier.PREFER_LOCAL, 0.75):
                        console.print(
                            f"[dim]Budget: 75% to prefer-local threshold — {self._governor.status_line()}[/dim]"
                        )
                elif _gov_tier == _GovTier.PREFER_LOCAL:
                    if self._governor.should_warn_approach(_GovTier.LOCAL_ONLY, 0.90):
                        console.print(
                            f"[dim yellow]Budget: 90% to local-only threshold — {self._governor.status_line()}[/dim yellow]"
                        )
                    elif self._governor.should_warn_approach(_GovTier.LOCAL_ONLY, 0.75):
                        console.print(
                            f"[dim]Budget: 75% to local-only threshold — {self._governor.status_line()}[/dim]"
                        )

                # ── LLM turn — FR-UI-001 status + FR-UI-006 cancellable thread ──
                status_ctx = _StatusContext()
                self._active_status = status_ctx
                try:
                    with status_ctx:
                        status_ctx.update("getting oriented")
                        response, was_cancelled = self._run_with_cancel(
                            user_input, status_ctx
                        )
                finally:
                    self._active_status = None

                if was_cancelled:
                    # Offer to re-run the cancelled message or drop it
                    console.print(
                        f"[dim]  ↩ Re-run last message? "
                        f"([cyan]/retry[/cyan] to resend, or just type something new)[/dim]"
                    )
                    self._last_cancelled = user_input
                    continue

                # FR-UI-005: if _agent_loop streamed tokens directly to console
                # (real LLM streaming), skip _stream_response() to avoid double-print.
                if response and not self._last_response_streamed:
                    console.print(f"\n[bold]Xochitl[/bold]: ", end="")
                    self._stream_response(response)
                    console.print()
                self._last_response_streamed = False  # reset for next turn

                # FR-ORCH-025: record turn for governor budget tracking.
                if response and not was_cancelled:
                    self._governor.record_turn(user_input, response)

        except KeyboardInterrupt:
            pass

        console.print("[dim]Session ended.[/dim]")

    def _stream_response(self, response: str) -> None:
        """Render assistant output incrementally instead of as one large blob.

        Keeps UX conversational and avoids the "hung then dump" effect.
        """
        # For markdown-heavy responses, fall back to rich markdown rendering.
        md_markers = ("```", "\n#", "\n- ", "\n1. ", "|---", "</")
        if any(marker in response for marker in md_markers):
            try:
                console.print(Markdown(response))
                return
            except Exception:
                pass

        # Stream plain responses by word to simulate live typing while staying readable.
        words = response.split(" ")
        for i, word in enumerate(words):
            if i > 0:
                console.print(" ", end="")
            console.print(word, end="")
            time.sleep(0.012)

    def _stream_and_buffer(
        self,
        user_input: str,
        messages: list,
        system_prompt: str,
        force: Optional[str],
        _status: Optional["_StatusContext"],
    ) -> tuple[str, str]:
        """Stream tokens live; stop displaying at first <skill_call>; return (displayed, full).

        FR-PERF-008 (CR-050 D2). Unifies pure and skill-injected streaming paths so
        the user always sees real-time output. The full buffer is returned so the
        caller can parse <skill_call> blocks from it after streaming ends.

        Args:
            user_input: Original user query forwarded to route_stream.
            messages: Conversation history for the LLM.
            system_prompt: Assembled system prompt (may include active skill block).
            force: Optional force_route value.
            _status: Live status context (stopped before streaming to avoid Rich conflict).

        Returns:
            Tuple of (displayed_text, full_response). displayed_text is what was printed
            to the terminal (tokens before the first <skill_call> boundary).
            full_response is the complete buffer including any <skill_call> XML.
        """
        if _status is not None:
            _status._stop_event.set()
            if _status._refresh_thread:
                _status._refresh_thread.join(timeout=0.3)
                _status._refresh_thread = None
            live = _status._live
            _status._live = None
            if live:
                try:
                    live.stop()
                except Exception:
                    pass

        buffer: list[str] = []
        displayed: list[str] = []
        printed_header = False
        skill_call_started = False

        for token in self.router.route_stream(
            query=user_input,
            conversation_history=messages,
            system_prompt=system_prompt,
            force_route=force,
        ):
            buffer.append(token)
            if skill_call_started:
                continue
            # Stop displaying once the accumulated text contains a <skill_call opener.
            if "<skill_call" in "".join(buffer):
                skill_call_started = True
                continue
            if not printed_header:
                console.print(f"\n[bold]Xochitl[/bold]: ", end="")
                printed_header = True
            console.print(token, end="")
            displayed.append(token)

        if displayed:
            console.print()  # trailing newline after visible stream

        return "".join(displayed), "".join(buffer)

    def process_message(
        self,
        user_input: str,
        _status: Optional["_StatusContext"] = None,
        _stream: bool = True,
    ) -> str:
        """Process one user message and return Xochitl's response.

        When _stream=True (default), conversational agent-loop turns use real
        LLM token streaming (FR-UI-005). Pass _stream=False in tests to keep
        responses synchronous and avoid console side-effects.
        """
        self.session_history.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat(),
        })
        # FR-ORCH-041: track last user message for /debug skill scoring
        self.current_context["_last_debug_input"] = user_input

        if is_why_request(user_input):
            expansion = build_why_expansion(
                self.session_history,
                self.current_context.get("last_skill_name"),
            )
            return self._record(expansion)

        # ── 1. Handle pending permission response (yes/no for file ops) ──────
        if "pending_file_operation" in self.current_context:
            perm = self._handle_permission_response(user_input)
            if perm is not None:
                return self._record(perm)

        # ── 2. Handle pending action confirmation (sync, delegate, SDD, etc.) ─
        if "pending_action" in self.current_context:
            action_resp = self._handle_action_confirmation(user_input)
            if action_resp is not None:
                return self._record(action_resp)

        # ── 3. Refresh BMAD and SDD context ──────────────────────────────────
        if _status:
            _status.update("refreshing context")
        from src.bmad import detect_bmad_project
        self.current_context["bmad_project"] = detect_bmad_project(Path.cwd())

        self.current_project = self._detect_current_project()
        if self.current_project:
            self.current_context["current_project"] = self.current_project
            self.current_context["specs_generated"] = self._check_specs_exist(self.current_project)
            self.current_context["bmad_complete"] = self._check_bmad_complete(self.current_project)
        else:
            self.current_context.pop("current_project", None)
            self.current_context.pop("specs_generated", None)
            self.current_context.pop("bmad_complete", None)

        # ── 4. Build universal ContextManager with skill manifest ─────────────
        # Implements FR-ORCH-006 (universal CM) + FR-ORCH-005 (skill manifest)
        preference_resp = self._maybe_save_preference(user_input)
        if preference_resp is not None:
            return self._record(preference_resp)

        route = "cloud" if self.force_cloud else "local"
        # FR-PERF-002 (CR-050 B2): turn-level cache for static CM engines.
        # Cache key captures inputs that invalidate the static content.
        _history = self._clean_history()
        _cm_key = (len(_history), getattr(self, "_last_mutating_skill", ""), route)
        if getattr(self, "_cm_cache", None) is not None and getattr(self, "_cm_cache_key", None) == _cm_key:
            cm = self._cm_cache
            # Always refresh query-dependent and per-turn engines.
            cm.memory.ingest(query=user_input, project=self.current_project)
            cm.preferences.ingest(query=user_input, project=self.current_project)
            cm.files.ingest(query=user_input, history=_history)
            # FactsEngine has its own TTL — let it self-skip if still fresh.
            cm.facts.ingest(project=self.current_project, local_mode=(route == "local"))
        else:
            # CR-035: pass milestone block so assemble_system_prompt() can inject it (FR-PREF-005)
            cm = ContextManager(
                route=route,
                skills=self.skills,
                milestone_block=getattr(self, "_milestone_block", ""),
            )
            cm.ingest(
                query=user_input,
                history=_history,
                project=self.current_project,
                local_mode=(route == "local"),
            )
            self._cm_cache = cm
            self._cm_cache_key = _cm_key
        # CR-042: workflow executor needs live skill instances (FR-MEM-014)
        self.current_context["_chat_skills"] = self.skills

        # ── 5. Dispatch: one keyword pass, then agent loop ────────────────────
        # The old triple-classification system (intent.py → _classify_intent →
        # router._fast_classify → router._classify) caused routing conflicts
        # because each layer could disagree. Now: fast keyword check for the
        # two cases that need dedicated handlers (file I/O with security gates,
        # task queue display), everything else goes directly to _agent_loop
        # where the single LLM classifier in router._classify() makes the call.
        if _status:
            _status.update("choosing path")

        # FR-ORCH-042: @SkillName explicit routing — bypass can_handle() scoring.
        # User writes "@gmail check my inbox"; we strip the @prefix, find the skill,
        # and execute directly, short-circuiting the entire agent loop (AC-CR047-007).
        _at_match = _AT_SKILL_RE.match(user_input.strip())
        if _at_match:
            _at_name    = _at_match.group(1)
            _at_payload = user_input[_at_match.end():].strip()
            _at_skill   = self._find_skill_by_name(_at_name)
            if _at_skill:
                self._emit_action_line(f"Running {_at_name} (explicit)...")
                _at_result = self._execute_skill_safe(
                    _at_skill, _at_payload or user_input, self.current_context, {}
                )
                response = _at_result or f"[dim]{_at_name} returned no output.[/dim]"
                response = self._maybe_offer_skill_creation(user_input, response)
                response = self._maybe_offer_workflow_save(user_input, response)
                return self._record(response)
            # FR-JARV-009: @mention fallback — tell the user the name wasn't found.
            console.print(
                f"[dim]No skill named '{_at_name}'. "
                f"Try /debug skill to see available skills.[/dim]"
            )

        q_lower = user_input.lower()

        if "weather" in q_lower or "forecast" in q_lower:
            if _status:
                _status.update("checking weather")
            response = self._handle_weather(user_input)
        elif any(kw in q_lower for kw in _TASK_KEYWORDS):
            response = self._handle_task_query(user_input, cm)
        elif (
            any(ext in user_input for ext in _FILE_EXTENSIONS)
            and any(kw in q_lower for kw in _FILE_READ_KW + _FILE_WRITE_KW + _FILE_DELETE_KW)
        ):
            if _status:
                _status.update("resolving file context")
            response = self._handle_file_operation(user_input, {}, cm)
        else:
            # ── Agent loop: LLM owns routing and skill dispatch ───────────────
            # Implements FR-ORCH-008 — single classification path through
            # router._classify(), covers general, bmad, code, orchestrator,
            # research, sdd, new_project, and all other intents.
            if _status:
                _status.update("drafting response")
            response = self._agent_loop(user_input, cm, _status, _stream=_stream)

        response = self._maybe_offer_skill_creation(user_input, response)
        response = self._maybe_offer_workflow_save(user_input, response)
        final = self._record(response)

        # Phase 3: queue this turn for passive background learning.
        # Fires in a daemon thread — never blocks the response to the user.
        self._background_review.queue_turn(
            user_input,
            final,
            project=self.current_project,
        )

        return final


    def _execute_skill_safe(
        self,
        skill: Skill,
        user_input: str,
        context: dict,
        params: dict,
        timeout: float = 30.0,
    ) -> str:
        """Wrap skill.execute() with a timeout to prevent hung sessions. FR-JARV-006.

        Implements FR-PERF-005 (CR-050 A7): reads ``timeout_secs`` from
        ``skill.tool_definition()`` when the caller does not supply an explicit timeout.

        Args:
            skill: The skill instance to execute.
            user_input: Forwarded to skill.execute().
            context: Session context dict, mutated in place by the skill.
            params: Extracted parameters for the skill.
            timeout: Maximum seconds to wait. Overridden by ``tool_definition()["timeout_secs"]``
                when that key is present and the caller did not set a non-default value.

        Returns:
            Skill output string, or a user-visible timeout error message.
        """
        # Delegates to src.agent.skill_dispatcher for testable execution + timeout logic.
        # FR-PERF-005, FR-RELY-004 (CR-050 A7, D1).
        from src.agent.skill_dispatcher import dispatch as _dispatch
        result = _dispatch(skill, params, user_input, context, timeout_secs=timeout)
        # FR-PERF-002 (CR-050 B2): mark skill as last mutating so CM cache key invalidates.
        self._last_mutating_skill = type(skill).__name__
        return result

    def _emit_action_line(self, label: str) -> None:
        from src.action_disclosure import action_summary
        use_rich = not (os.environ.get("TERM") == "dumb" or getattr(self, "_no_rich", False))
        console.print(action_summary(label), markup=use_rich)

    def _handle_web_lookup(self, user_input: str) -> str:
        """Run read-only web lookup directly without extra confirmation."""
        from src.skills.web_lookup_skill import WebLookupSkill
        result = WebLookupSkill().execute(user_input, self.current_context, {"query": user_input})
        self.current_context["last_skill_name"] = "WebLookupSkill"
        return result

    def _handle_weather(self, user_input: str) -> str:
        """Run structured weather first, then generic web lookup if the API fails."""
        from src.skills.weather_skill import WeatherSkill

        self._emit_action_line(infer_action_label(user_input, "WeatherSkill"))
        result = WeatherSkill().execute(user_input, self.current_context, {"query": user_input})
        self.current_context["last_skill_name"] = "WeatherSkill"
        if self.current_context.get("last_skill_success") is False and self.current_context.get("weather_error_type") == "api":
            fallback = self._handle_web_lookup(user_input)
            return f"{result}\n\nI tried a web fallback too:\n{fallback}"
        return result

    # ── Agent loop (FR-ORCH-008) ──────────────────────────────────────────────

    def _agent_loop(
        self,
        user_input: str,
        cm: ContextManager,
        _status: Optional[_StatusContext] = None,
        _stream: bool = False,
    ) -> str:
        """Delegate to AgentPipeline.run() and integrate TurnResult back into session state.

        Implements FR-ORCH-008. All pipeline logic lives in src/agent/pipeline.py.
        This method owns response-mode announcements, governor force_route
        (restored: computes _gov_force from self._governor.force_route() and
        passes it to the pipeline as AgentTurnInput.governor_force so the
        pipeline applies it as force_route="general" for LOCAL_ONLY/HARD_STOP),
        and session-history updates that require session-level state.

        Pipeline stages (see agent/pipeline.py for full implementation):
          1. BackgroundReview watchdog: restarts dead daemon, emits SYSTEM_FAILURE,
             checks BackgroundReview.is_alive() (FR-RELY-003).
          2. Trace-id: emits routing_started with trace_id, llm_complete with tokens_in
             and cost_usd (FR-ORCH-036).
          3. Skill scoring: ThreadPoolExecutor concurrent can_handle() via concurrent.futures;
             top scorer above _SKILL_INJECT_THRESHOLD gets its schema injected (FR-PERF-003).
          4. [TURN CONTEXT: injection: three-zone logic keyed on top_score:
             - top_score >= _SKILL_INJECT_THRESHOLD (0.65):
               pass  # skill schema handles context — no [TURN CONTEXT: added
             - 0.20–0.65: Near-match note injected; names skill_label, prohibits
               "Do NOT silently deliver a reduced version" (FR-ORCH-034)
             - < 0.20: complete-miss note references [CAPABILITY BOUNDARY] and
               "nearest available forward path" (FR-ORCH-034)
          5. Routing: streaming (pure or skill-injected) or non-streaming fallback.
          6. Skill-call dispatch: parses <skill_call> blocks; tracks _tool_calls_made.
          7. Post-execution critique via _maybe_critique / _MAX_CRITIC_ITERATIONS.
        """
        from src.agent.turn import AgentTurnInput

        # FR-RELY-003: pass current BackgroundReview to pipeline watchdog.
        # Pipeline calls is_alive() and restarts with BackgroundReview() + SYSTEM_FAILURE.
        self._pipeline._background_review = self._background_review
        self._pipeline._initiative = self._initiative

        # FR-ORCH-036 (CR-021): pipeline emits these events with enriched payloads:
        #   routing_started  {"query": ..., "trace_id": ...}
        #   llm_complete     {"route": ..., "tokens_in": ..., "tokens_out": ..., "cost_usd": ...}
        # Emit keys: "trace_id", "tokens_in", "cost_usd" are set in agent/pipeline.py.

        # CR-025: infer response mode and announce transition (FR-ORCH-032).
        # Done here (not in pipeline) because _current_mode is session state.
        try:
            from src.response_mode import infer_mode as _infer_mode
            _new_mode = _infer_mode(user_input)
            if _new_mode != self._current_mode:
                _mode_labels = {
                    "operator": "→ operator mode",
                    "report": "→ report mode",
                    "conversational": "→ conversational mode",
                }
                console.print(
                    f"[dim]{_mode_labels.get(_new_mode, f'→ {_new_mode} mode')}[/dim]"
                )
            self._current_mode = _new_mode
        except ImportError:
            _new_mode = "conversational"

        # Assemble system prompt and messages via ContextManager.
        system_prompt = cm.assemble_system_prompt(mode=_new_mode)
        messages = cm.assemble_messages(self._clean_history(), user_input, tag_provenance=True)

        # FR-ORCH-025: governor routing constraint — local only / hard stop.
        # force_cloud wins over governor; governor only applies when force_cloud is False.
        # governor.force_route() returns "general" (local-routed category) for
        # LOCAL_ONLY and HARD_STOP tiers; None for FULL and PREFER_LOCAL.
        force_cloud = self.force_cloud
        _gov_force = self._governor.force_route() if not force_cloud else None

        turn = AgentTurnInput(
            user_input=user_input,
            system_prompt=system_prompt,
            messages=messages,
            skills=self.skills,
            current_project=self.current_project,
            force_cloud=force_cloud,
            stream=_stream,
            context=self.current_context,
            session_history=self.session_history,
            governor_force=_gov_force,
        )

        result = self._pipeline.run(turn, _status=_status)

        # Sync pipeline's possibly-restarted BackgroundReview back to session.
        if self._pipeline._background_review is not self._background_review:
            self._background_review = self._pipeline._background_review

        # Integrate TurnResult back into session state.
        if result.was_streamed:
            self._last_response_streamed = True
        if result.last_mutating_skill:
            self._last_mutating_skill = result.last_mutating_skill

        return result.response

    # _skill_call_requires_approval was removed: the canonical implementation
    # is the module-level function _skill_call_requires_approval() in
    # src/agent/pipeline.py, which is the live code path used during turn
    # execution.  This method was dead after the pipeline extraction.

    def _stage_skill_call_plan(self, skill: Skill, params: dict, user_input: str, visible: str) -> str:
        name = type(skill).__name__
        risk = self._risk_label_for_skill(name, params)
        # CR-052: show the exact command/action so the user knows what they approve.
        action = (
            params.get("command")
            or params.get("action")
            or params.get("direction")
            or "execute"
        )
        self.current_context["pending_action"] = "execute_skill_call"
        self.current_context["pending_skill_call"] = {
            "skill_name": name,
            "params": params,
            "user_input": user_input,
        }

        lines = []
        if visible:
            lines.append(visible)
            lines.append("")
        lines.extend([
            "**Plan before I touch anything:**",
            f"- Skill: `{name}`",
            f"- Action: `{action}`",
            f"- Risk: `{risk}`",
            "- I will run only this approved skill call, then report the result.",
            "",
            "Reply `yes` to proceed, or `no` to cancel.",
        ])
        return "\n".join(lines)

    def _risk_label_for_skill(self, skill_name: str, params: dict) -> str:
        if skill_name == "NotionSkill":
            return "external side effect with Notion"
        if skill_name == "OrchestratorSkill":
            return "background command/workspace execution"
        if skill_name == "CodeSkill":
            return "file writes in the active project"
        if skill_name in {"BMADSkill", "SDDSkill"}:
            return "project/spec file writes"
        if skill_name == "ShellSkill":
            return "allowlisted shell command execution"
        if skill_name == "GitSkill":
            return "git repository write (add/commit)"
        return "state change"

    def _execute_pending_skill_call(self) -> str:
        pending = self.current_context.pop("pending_skill_call", None)
        if not pending:
            return f"{_FYI} - I do not have a pending skill call to run."

        skill_name = pending.get("skill_name", "")
        skill = self._find_skill_by_name(skill_name)
        if not skill:
            return f"{_ERR} - I could not find `{skill_name}` anymore, so I did not run it."

        tool_result = self._execute_skill_safe(
            skill,
            pending.get("user_input", ""),
            self.current_context,
            pending.get("params", {}),
        )
        self.current_context["last_skill_name"] = skill_name
        if "last_skill_success" not in self.current_context:
            self.current_context["last_skill_success"] = True
        self.session_history.append({
            "role": "tool",
            "skill": skill_name,
            "content": tool_result,
            "timestamp": datetime.now().isoformat(),
        })
        return tool_result

    def _maybe_offer_skill_creation(self, user_input: str, response: str) -> str:
        """Offer skill creation after reusable multi-step work.

        Implements FR-ORCH-013 / AC-CR004-008. The trigger is deliberately
        balanced: explicit reusable-workflow language, or at least two tool
        results in this session. It offers, but never forces, creation.
        """
        if self.current_context.get("skill_creation_offered"):
            return response
        if self.current_context.get("last_skill_success") is False:
            return response
        if self.current_context.get("last_skill_name"):
            # A skill already handled this request; do not suggest creating another.
            return response
        if self.current_context.get("pending_action"):
            return response

        q = user_input.lower()
        explicit = any(phrase in q for phrase in (
            "do this often",
            "reusable workflow",
            "make this a skill",
            "turn this into a skill",
            "next time",
        ))
        tool_turns = sum(1 for msg in self.session_history if msg.get("role") == "tool")
        if not explicit and tool_turns < 2:
            return response

        self.current_context["skill_creation_offered"] = True
        from src.skills.dynamic_skill import build_skill_creation_offer
        return response.rstrip() + build_skill_creation_offer(user_input, self.current_context)

    def _maybe_offer_workflow_save(self, user_input: str, response: str) -> str:
        """Offer saving a procedural workflow after multi-step tool use (FR-MEM-011)."""
        if self.current_context.get("workflow_save_offered"):
            return response
        if self.current_context.get("last_skill_success") is False:
            return response
        tool_turns = sum(1 for msg in self.session_history if msg.get("role") == "tool")
        if tool_turns < 2:
            return response
        self.current_context["workflow_save_offered"] = True
        from src.workflows import build_workflow_save_offer
        return response.rstrip() + build_workflow_save_offer(user_input)

    def _find_skill_by_name(self, name: str) -> Optional[Skill]:
        """Look up a skill by tool_definition name or class name. FR-HARD-007.

        Delegates to SkillRegistry.by_name() for O(1) lookup.

        Args:
            name: Skill name to look up (case-insensitive).

        Returns:
            Matching Skill instance, or None if no skill has that name.
        """
        from src.skills import _registry
        return _registry.by_name(name)

    # ── Post-execution reflection/critic (CR-019) ─────────────────────────────

    def _maybe_critique(
        self,
        response: str,
        goal: str,
        top_score: float,
        tool_calls_made: bool,
        messages: list[dict],
        system_prompt: str,
        force: Optional[str],
    ) -> str:
        """Run post-execution critique if warranted; return (possibly improved) response.

        Implements FR-ORCH-037, FR-ORCH-038 (CR-019). Only fires on non-streaming
        turns when at least one trigger condition is met. Uses the local model
        (force_route="simple_qa") for the critique call (NFR-ORCH-012). The entire
        block is wrapped in try/except — must never crash the main loop (NFR-ORCH-013).

        Args:
            response:        The assembled response text to evaluate.
            goal:            The original user input.
            top_score:       Highest skill can_handle() score for this turn.
            tool_calls_made: True if a skill executed this turn (_tool_calls_made flag).
            messages:        Assembled conversation history (for correction retries).
            system_prompt:   Base system prompt (amended with critic note on retry).
            force:           Optional force_route value (preserved on retries).

        Enforces _MAX_CRITIC_ITERATIONS cap (NFR-ORCH-012) to bound retry depth.

        Args:
            response:        The assembled response text to evaluate.
            goal:            The original user input.
            top_score:       Highest skill can_handle() score for this turn.
            tool_calls_made: True if a skill was executed this turn.
            messages:        Assembled conversation history (for correction retries).
            system_prompt:   Base system prompt (amended with critic note on retry).
            force:           Optional force_route value (preserved on retries).

        Returns:
            The original response, a corrected response, or the original with a
            caveat appended — depending on the critic verdict.
        """
        try:
            from src.critic import TurnCritic, _MAX_CRITIC_ITERATIONS
            _critic = TurnCritic()
            if not _critic.should_critique(top_score, tool_calls_made, response):
                return response

            current_response = response
            current_system = system_prompt

            for _ in range(_MAX_CRITIC_ITERATIONS):
                cresult = _critic.critique(
                    goal=goal,
                    response=current_response,
                    router=self.router,
                )

                if cresult.verdict == "ok":
                    break

                if cresult.verdict == "ambiguous":
                    current_response = (
                        current_response
                        + f"\n\n_{_FYI} — {cresult.note}_"
                    )
                    break

                # CORRECTABLE on a tool-call turn: a retry would discard the skill
                # result because the retry LLM call has no access to the tool output.
                # Downgrade to AMBIGUOUS so we append a caveat instead of losing data.
                if tool_calls_made and cresult.verdict == "correctable":
                    current_response = (
                        current_response
                        + f"\n\n_{_FYI} — {cresult.note}_"
                    )
                    break

                # CORRECTABLE (non-tool turn): retry with critic note injected into system prompt
                current_system = (
                    current_system
                    + f"\n\n[CRITIC NOTE: The previous response had this issue: "
                    f"{cresult.note} — please address it in your next response.]"
                )
                retry = self.router.route(
                    query=goal,
                    conversation_history=messages,
                    system_prompt=current_system,
                    force_route=force,
                )
                if retry.error:
                    break
                new_response = _SKILL_CALL_RE.sub("", retry.content or "").strip()
                if not new_response or new_response == current_response:
                    # No improvement — escalate to caveat and stop (convergence guard)
                    current_response = (
                        current_response
                        + f"\n\n_{_FYI} — {cresult.note}_"
                    )
                    break
                current_response = new_response

            return current_response
        except Exception:
            return response  # critic must never crash the main loop (NFR-ORCH-013)

    # ── Intent classification ─────────────────────────────────────────────────

    def _maybe_save_preference(self, user_input: str) -> Optional[str]:
        """Save explicit stable user preferences.

        Implements DATA-DATA-004 / AC-CR004-006. This is deliberately an
        explicit path, not passive surveillance: the user must say remember,
        prefer, or "for this project".
        """
        extracted = self._extract_preference(user_input)
        if not extracted:
            return None

        value, scope_hint = extracted
        category = self._preference_category(value)
        scope = "project" if scope_hint == "project" and self.current_project else "global"
        project_id = self.current_project if scope == "project" else None
        key = self._preference_key(category, value)
        with db.get_connection() as conn:
            db.upsert_preference(conn, {
                "scope": scope,
                "project_id": project_id,
                "category": category,
                "preference_key": key,
                "preference_value": value,
                "source": "chat",
                "confidence": 1.0,
            })

        scope_label = f" for `{project_id}`" if project_id else ""
        return f"{_OK} - I'll remember that{scope_label}: {value}"

    def _extract_preference(self, user_input: str) -> Optional[tuple[str, str]]:
        q = user_input.strip()
        patterns = [
            r"(?i)\bfor this project, remember that (.+)$",
            r"(?i)\bfor this project, i prefer (.+)$",
            r"(?i)\bremember that (.+)$",
            r"(?i)\bplease remember (.+)$",
            r"(?i)\bi prefer (.+)$",
            r"(?i)\bmy preference is (.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, q)
            if not match:
                continue
            value = match.group(1).strip().rstrip(".")
            if len(value) < 4:
                return None
            scope_hint = "project" if "for this project" in match.group(0).lower() else "global"
            return value, scope_hint
        return None

    def _preference_category(self, value: str) -> str:
        q = value.lower()
        if any(word in q for word in ("concise", "tone", "explain", "detail", "push back", "question")):
            return "communication"
        if any(word in q for word in ("morning", "daily", "task", "priority", "focus", "workflow")):
            return "productivity"
        if any(word in q for word in ("test", "code", "commit", "branch", "architecture", "spec")):
            return "development"
        return "general"

    def _preference_key(self, category: str, value: str) -> str:
        words = re.findall(r"[a-z0-9]+", value.lower())[:8]
        slug = "-".join(words)[:60] or "preference"
        return f"{category}:{slug}"

    def _classify_intent(self, user_input: str) -> dict:
        """Classify user intent for legacy test compatibility only. Not called by the main flow."""
        from src.intent import classify_conversation_intent
        return classify_conversation_intent(
            user_input,
            current_project=self.current_project,
        ).to_dict()

    # ── Intent handlers ───────────────────────────────────────────────────────

    def _handle_task_query(self, user_input: str, cm: ContextManager) -> str:
        # Implements FR-ORCH-006 — uses CM for system prompt assembly
        system = cm.assemble_system_prompt() + "\n\n" + _live_db_context()
        result = self.router.route(
            query=user_input,
            conversation_history=cm.assemble_messages(self._clean_history(), user_input, tag_provenance=True),
            system_prompt=system,
            force_route="task_management",
        )
        return result.content if not result.error else f"{_ERR} — {result.error}"

    def _handle_file_operation(self, user_input: str, intent: dict, cm: ContextManager) -> str:
        op = intent.get("operation", "read")

        if op == "read":
            # BUG-CHAT-002 fix: catch permission errors and surface them clearly
            try:
                file_ctx = _resolve_file_context(user_input, self.session_history)
            except Exception as exc:
                return (
                    f"{_ERR} — couldn't read that path: {exc}\n\n"
                    "If the file is outside my project directory, authorize it first:\n"
                    "`/authorize C:\\Users\\Jason\\Desktop\\Jason\\Resource\\CodeProjects`"
                )
            if file_ctx:
                # Implements FR-ORCH-006 — CM system prompt + file context appended
                system = cm.assemble_system_prompt() + "\n\n" + file_ctx
                result = self.router.route(
                    query=user_input,
                    conversation_history=self._clean_history(),
                    system_prompt=system,
                )
                return result.content if not result.error else f"{_ERR} — {result.error}"
            import re as _re
            paths_found = _re.findall(r'[A-Za-z]:[/\\][\w/\\\-. ]+', user_input)
            quoted_found = [m[0] or m[1] for m in _re.findall(r'"([^"]+)"|\'([^\']+)\'', user_input)]
            hint = (paths_found + quoted_found)
            if hint:
                return (
                    f"{_FYI} — I couldn't find or access `{hint[0].strip()}`.\n\n"
                    "Make sure the path is correct. If it's outside my authorized directories, run:\n"
                    "`/authorize <parent-folder>`"
                )
            return f"{_FYI} — I don't see a specific file in that message. Can you give me the full path?"

        return self._agent_loop(user_input, cm)

    def _handle_repo_exploration(self, user_input: str, cm: ContextManager) -> str:
        """Bounded read-only project exploration for architecture summaries.

        Implements FR-ORCH-011 / AC-CR004-002. This gathers a small, fixed
        amount of local context before asking the router to synthesize.
        """
        project_root = _PROJECT_ROOT
        snippets = [self._project_tree_snapshot(project_root)]
        for rel in (
            "pyproject.toml",
            "requirements.txt",
            "docs/spec/00-project-constitution.md",
            "docs/spec/02-requirements-registry.md",
            "docs/spec/06-traceability/traceability-matrix.md",
        ):
            text = self._read_bounded(project_root / rel, limit=2200)
            if text:
                snippets.append(f"## {rel}\n{text}")

        src_files = sorted((project_root / "src").glob("*.py"))[:12]
        if src_files:
            module_lines = ["## src modules"]
            module_lines.extend(f"- {p.name}" for p in src_files)
            snippets.append("\n".join(module_lines))

        system = cm.assemble_system_prompt() + "\n\n[READ_ONLY_EXPLORATION]\n" + "\n\n".join(snippets)
        result = self.router.route(
            query=user_input,
            conversation_history=cm.assemble_messages(self._clean_history(), user_input, tag_provenance=True),
            system_prompt=system,
            force_route="simple_qa",
        )
        return result.content if not result.error else f"{_ERR} - {result.error}"

    def _project_tree_snapshot(self, root: Path) -> str:
        lines = ["## Project snapshot"]
        for child in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:40]:
            if child.name in {".git", "__pycache__", ".pytest_cache"}:
                continue
            kind = "dir" if child.is_dir() else "file"
            lines.append(f"- {kind}: {child.name}")
        return "\n".join(lines)

    def _read_bounded(self, path: Path, *, limit: int) -> str:
        try:
            if not path.exists() or not path.is_file():
                return ""
            return path.read_text(encoding="utf-8", errors="replace")[:limit]
        except Exception:
            return ""

    def _handle_research(self, user_input: str, intent: dict) -> str:
        """Route to research module for synthesis, adversarial review, or conflict detection."""
        # Implements FR-RES-001, FR-RES-002, FR-RES-003
        from src.research import adversarial_review, run_research

        if intent.get("adversarial"):
            return adversarial_review(user_input)

        result = run_research(
            topic=user_input,
            check_conflicts=True,
        )
        parts = [f"_{result['budget']}_\n"]
        if result["synthesis"]:
            parts.append(result["synthesis"])
        if result["conflicts"]:
            parts.append(f"\n**{_FYI} — {len(result['conflicts'])} conflict(s) with existing KB:**")
            for c in result["conflicts"]:
                parts.append(f"- {c['source']}: {c['verdict'][:100]}")
        return "\n".join(parts)

    # ── Confirmation handlers ─────────────────────────────────────────────────

    def _handle_permission_response(self, user_input: str) -> Optional[str]:
        """Delegate to ConfirmationHandler. Implements FR-ORCH-011."""
        self._confirmation._ctx = self.current_context
        return self._confirmation.handle_permission_response(user_input)

    def _handle_action_confirmation(self, user_input: str) -> Optional[str]:
        """Delegate to ConfirmationHandler. Implements FR-ORCH-007."""
        self._confirmation._ctx = self.current_context
        self._confirmation._project = self.current_project
        self._confirmation._history = self.session_history
        return self._confirmation.handle_action_confirmation(user_input)

    def _llm_classify_confirm(self, pending_action: str, user_input: str) -> str:
        """Delegate to ConfirmationHandler. Implements FR-ORCH-007."""
        return self._confirmation._llm_classify_confirm(pending_action, user_input)

    # ── Project context detection ─────────────────────────────────────────────

    def _detect_current_project(self) -> Optional[str]:
        """Return project_id if CWD is inside projects/<project_id>/ and .project-meta.yml exists."""
        projects_dir = (_PROJECT_ROOT / "projects").resolve()
        cwd = Path.cwd().resolve()
        try:
            relative = cwd.relative_to(projects_dir)
            if relative.parts:
                project_id = relative.parts[0]
                if (projects_dir / project_id / ".project-meta.yml").exists():
                    return project_id
        except ValueError:
            pass
        return None

    def _check_specs_exist(self, project_id: str) -> bool:
        """True if specs/ has at least one *-features.md."""
        specs_dir = _PROJECT_ROOT / "projects" / project_id / "specs"
        return specs_dir.exists() and any(specs_dir.glob("*-features.md"))

    def _check_bmad_complete(self, project_id: str) -> bool:
        """True if .project-meta.yml has bmad_complete=true."""
        from src.skills._yaml_helpers import yaml_load
        meta_path = _PROJECT_ROOT / "projects" / project_id / ".project-meta.yml"
        if not meta_path.exists():
            return False
        try:
            meta = yaml_load(meta_path.read_text(encoding="utf-8"))
            return bool(meta.get("bmad_complete", False))
        except Exception:
            return False

    # ── Project name extraction ───────────────────────────────────────────────

    def _extract_project_name(self, user_input: str) -> str:
        """Extract a project name from a 'I want to build X' type message."""
        patterns = [
            r"(?:i want to (?:build|make|create)|let's (?:build|make|create)|build|make|create)\s+(?:an?\s+)?(.+?)(?:\s+app|\s+application|\s+tool|\s+system|$)",
            r"new (?:project|app)(?:\s+called|\s+named)?\s+['\"]?(.+?)['\"]?$",
        ]
        for pattern in patterns:
            m = re.search(pattern, user_input.lower())
            if m:
                name = m.group(1).strip().title()
                if len(name) < 60:
                    return name
        words = user_input.strip().split()
        return " ".join(words[-3:]).title() if len(words) >= 3 else user_input.strip().title()

    # ── Slash command dispatch (FR-SEC-001, FR-SEC-003, FR-SEC-004) ──────────

    def _handle_slash_command(self, raw: str) -> str:
        """Delegate to session/slash_commands.py. Implements FR-SEC-001."""
        from src.session.slash_commands import handle_slash_command
        return handle_slash_command(raw, self)

    # ── Status / history helpers (kept for backward compat; delegate to module) ─

    def _handle_status_command(self) -> str:
        """Return a system health table for /status. Implements FR-JARV-011.

        Delegates to session/slash_commands._handle_status which queries:
        - memory_facts and workflows row counts (FR-UX-004)
        - _background_review.is_alive() daemon health
        - _initiative engine mode
        """
        from src.session.slash_commands import _handle_status
        return _handle_status(self)

    def _handle_history_command(self, n: int = 5) -> str:
        """Delegate to session/slash_commands._handle_history. Implements FR-HARD-008."""
        from src.session.slash_commands import _handle_history
        return _handle_history(self, n)

    def _last_user_message(self) -> str:
        """Return the most recent user message text in this session."""
        for msg in reversed(self.session_history):
            if msg.get("role") == "user":
                return str(msg.get("content") or "")
        return ""

    def _record(self, response: str) -> str:
        """Append response to session history and persist.

        Implements FR-ORCH-009 (partial) — strips stray <skill_call> tags
        that survived to the visible response (BUG-CHAT-003 coverage) and
        strips other LLM-hallucinated tool-call syntax.
        Also implements FR-CONV-001 (A1 — filler opener stripping): removes
        sycophantic openers ("Certainly!", "Great question!", etc.) before
        the response reaches the user.
        """
        # Strip any <execute_tool>...</execute_tool> blocks (BUG-CHAT-003)
        response = re.sub(
            r'<execute_tool>.*?</execute_tool>',
            '',
            response,
            flags=re.DOTALL,
        ).strip()
        # Strip any stray <skill_call> tags that weren't caught in _agent_loop
        response = _SKILL_CALL_RE.sub("", response).strip()
        # A1 — strip sycophantic filler openers (FR-CONV-001)
        try:
            from src.conversation import strip_filler_opener
            response = strip_filler_opener(response)
        except Exception:
            pass  # filler stripping must never crash the main loop

        self.session_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })
        self._persist_session()
        # FR-JARV-012: save a short context_summary so the next session can show a resume hint.
        self._save_context_summary(response)
        return response

    def _save_context_summary(self, response: str) -> None:
        """Persist a 150-char excerpt of the last reply for session resume. FR-JARV-012.

        Args:
            response: The latest assistant response text.
        """
        if not self.session_id:
            return
        try:
            summary = response.strip()[:150].replace("\n", " ")
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE sessions SET context_summary = ?, last_active = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (summary, self.session_id),
                )
        except Exception:
            pass  # NFR-JARV-003: never crash on summary save

    def _clean_history(self) -> list[dict]:
        """Strip timestamps and serialize tool turns for LLM calls.

        Implements FR-ORCH-009 — role=tool turns become assistant messages
        prefixed [Tool: SkillName] so the LLM has continuity over skill results.
        """
        result = []
        for m in self.session_history[:-1]:
            role = m["role"]
            content = m["content"]
            if role == "tool":
                skill = m.get("skill", "Tool")
                result.append({
                    "role": "assistant",
                    "content": f"[Tool: {skill}]\n{content}",
                })
            else:
                result.append({"role": role, "content": content})
        return result

    def _persist_session(self) -> None:
        if not self.session_id:
            return
        try:
            with db.get_connection() as conn:
                db.update_session_conversation(conn, self.session_id, self._clean_history())
        except Exception:
            pass

    def _start_orchestrator_daemon(self) -> None:
        try:
            from src.skills.orchestrator_skill import OrchestratorSkill
            orch = next((s for s in self.skills if isinstance(s, OrchestratorSkill)), None)
            if orch:
                msg = orch.start_daemon()
                console.print(f"[dim]{msg}[/dim]\n")
        except Exception:
            pass
