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

# Implements FR-UX-002 — Spanish vocabulary constants mirroring SOUL.md palette
_OK  = "Claro"    # success / acknowledged
_FYI = "Fíjate"  # informational flag — "look here"
_ERR = "Ay no"   # error / blocked

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


_CONFIRM_YES = {"yes", "y", "ok", "sure", "yeah", "yep", "do it", "go ahead"}
_CONFIRM_NO  = {"no", "n", "nope", "cancel", "nevermind", "stop", "don't"}

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

_SKILL_CALL_RE = re.compile(
    r'<skill_call\s+name=["\'](\w+)["\']>(.*?)</skill_call>',
    re.DOTALL | re.IGNORECASE,
)


def _parse_skill_call(response: str) -> Optional[tuple[str, dict]]:
    """Extract <skill_call name="X">{...}</skill_call> from an LLM response.

    Implements FR-ORCH-008. Returns (skill_name, params) or None.
    Tolerant of missing/malformed JSON in the body.
    """
    m = _SKILL_CALL_RE.search(response)
    if not m:
        return None
    skill_name = m.group(1)
    body = m.group(2).strip()
    try:
        params = json.loads(body) if body else {}
    except json.JSONDecodeError:
        params = {}
    return skill_name, params


_MUTATING_SKILL_ACTIONS = {
    "BMADSkill": {"init_project", "save_bmad_artifact"},
    "SDDSkill": {"generate_specs", "create_requirement", "create_issue", "update_requirement", "close_issue"},
    "CodeSkill": {"scaffold", "implement", "fix", "tests", "test"},
}

# Phase 2: minimum can_handle() score to inject a skill into the system prompt.
# Matches the 0.6 suggestion threshold from Skill base docstring with a small buffer.
_SKILL_INJECT_THRESHOLD = 0.65

# CR-032: skill-score threshold below which intent is considered open-ended.
# When top_score < this, _agent_loop injects a [TURN CONTEXT] note reminding the
# model to apply calibrated [UNCERTAINTY TIERS] vocabulary for this turn.
_OPEN_ENDED_SCORE_THRESHOLD = 0.2

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
    if examples:
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

        self._builtin_skills: Optional[list[Skill]] = None
        self._skills: Optional[list[Skill]] = None  # Backward-compatible test hook.

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
        try:
            from src.initiative import InitiativeEngine
            self._initiative = InitiativeEngine()
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

    @property
    def skills(self) -> list[Skill]:
        if getattr(self, "_skills", None) is not None:
            return self._skills or []

        if getattr(self, "_builtin_skills", None) is None:
            from src.skills.bmad_skill import BMADSkill
            from src.skills.sdd_skill import SDDSkill
            from src.skills.code_skill import CodeSkill
            from src.skills.notion_skill import NotionSkill
            from src.skills.orchestrator_skill import OrchestratorSkill
            from src.skills.weather_skill import WeatherSkill
            from src.skills.web_lookup_skill import WebLookupSkill
            from src.skills.zettelkasten_skill import ZettelkastenSkill
            from src.skills.explorer_skill import ExplorerSkill  # FR-ORCH-041
            from src.skills.workflow_skill import WorkflowSkill  # FR-MEM-014 / CR-042
            from src.skills.maps_skill import MapsSkill          # FR-MAPS-001 / CR-045
            from src.skills.gmail_skill import GmailSkill        # FR-GMAIL-001 / CR-046a
            self._builtin_skills = [
                BMADSkill(), SDDSkill(), CodeSkill(), NotionSkill(), OrchestratorSkill(),
                WeatherSkill(), WebLookupSkill(), ZettelkastenSkill(), ExplorerSkill(),
                WorkflowSkill(), MapsSkill(), GmailSkill(),
            ]

        from src.skills.dynamic_skill import load_dynamic_skills
        return (self._builtin_skills or []) + load_dynamic_skills(self.current_project)

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
        # CR-035: pass milestone block so assemble_system_prompt() can inject it (FR-PREF-005)
        cm = ContextManager(
            route=route,
            skills=self.skills,
            milestone_block=getattr(self, "_milestone_block", ""),
        )
        cm.ingest(
            query=user_input,
            history=self._clean_history(),
            project=self.current_project,
            local_mode=(route == "local"),
        )
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
                _at_result = _at_skill.execute(
                    _at_payload or user_input, self.current_context, {}
                )
                response = _at_result or f"[dim]{_at_name} returned no output.[/dim]"
                response = self._maybe_offer_skill_creation(user_input, response)
                response = self._maybe_offer_workflow_save(user_input, response)
                return self._record(response)
            # Unrecognised @name — fall through to normal routing with a hint
            user_input = user_input  # keep original; skill not found is non-fatal

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
        """LLM-controlled turn: deterministic skill scoring + LLM response.

        Implements FR-ORCH-008. Flow:
          1. Score every skill via can_handle() — O(N) keyword/heuristic, <5ms
          2. Top scorer above threshold gets its tool_definition() injected into
             the system prompt for THIS TURN ONLY (not stored, not global)
          3. Route to LLM — model now has the exact <skill_call> schema in front
             of it for the one relevant skill, so it can invoke correctly
          4. Parse response for <skill_call name="X">{...}</skill_call>
          5. If found: execute skill, record in history, append result to response
          6. Strip any stray <skill_call> tags from visible output
        """
        # CR-021: generate per-turn trace_id for observability correlation (FR-ORCH-036)
        import secrets as _secrets
        _trace_id = _secrets.token_hex(6)
        _events.emit("routing_started", {"query": user_input[:100], "trace_id": _trace_id})

        # CR-025: infer response mode and announce transitions (FR-ORCH-032, NFR-ORCH-007)
        try:
            from src.response_mode import infer_mode as _infer_mode, MODE_CONVERSATIONAL
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

        system_prompt = cm.assemble_system_prompt(mode=_new_mode)
        messages = cm.assemble_messages(self._clean_history(), user_input, tag_provenance=True)

        # CR-033: inject identity reminder when BackgroundReview detected persona drift
        # (FR-ORCH-043). Appended after assemble_system_prompt() so it appears at the
        # end of the prompt — transformer recency bias amplifies the effect.
        if getattr(self, "_background_review", None) and self._background_review.drift_detected:
            system_prompt += _DRIFT_IDENTITY_REMINDER
            self._background_review.clear_drift()

        # CR-038: drain pending proactive signals and inject as system hint (FR-INIT-001)
        try:
            if getattr(self, "_initiative", None):
                signals = self._initiative.drain()
                if signals:
                    sig = signals[0]  # surface one signal per turn maximum
                    system_prompt += (
                        "\n\n---\n"
                        "[PROACTIVE ALERT]\n"
                        f"{sig.message}\n"
                        f"{sig.action_hint}\n"
                        "---"
                    )
        except Exception:
            pass

        # CR-041: recall procedural workflow by intent (FR-MEM-010)
        self.current_context.pop("active_workflow_id", None)
        self.current_context.pop("active_workflow_name", None)
        try:
            from src.workflows import format_workflow_block, search_workflows_by_intent

            _wf = search_workflows_by_intent(
                user_input,
                project=self.current_project,
            )
            if _wf:
                system_prompt += (
                    "\n\n---\n"
                    + format_workflow_block(_wf)
                    + "\n---"
                )
                self.current_context["active_workflow_id"] = _wf["id"]
                self.current_context["active_workflow_name"] = _wf["name"]
                if _status:
                    _status.update(f"workflow: {_wf['name']}")
        except Exception:
            pass

        # ── Phase 2: deterministic skill scoring pre-turn ─────────────────────
        # Score every loaded skill against the user's message BEFORE the LLM
        # call. The top scorer above threshold gets its full schema injected into
        # the system prompt so the model has the invocation format in front of it.
        # This is deterministic (no LLM call) and replaces the old approach where
        # the model had to guess the <skill_call> format from the global manifest.
        top_skill = None
        top_score = 0.0
        for skill in self.skills:
            try:
                score = skill.can_handle(user_input, self.current_context)
            except Exception:
                score = 0.0
            if score > top_score:
                top_score = score
                top_skill = skill

        if top_skill is not None and top_score >= _SKILL_INJECT_THRESHOLD:
            defn = top_skill.tool_definition()
            system_prompt = system_prompt + "\n\n---\n\n" + _format_active_skill_block(defn)
            _events.emit("skill_matched", {"skill": defn.get("name", ""), "score": top_score})
            if _status:
                _status.update(f"skill ready: {defn.get('name', type(top_skill).__name__)}")

        # ── CR-032 + CR-036: Per-turn capability context (FR-ORCH-026, FR-ORCH-034) ──
        # Three scoring zones determine what [TURN CONTEXT] is injected:
        #
        #  ≥ 0.65  SKILL MATCHED   — skill schema already injected; no [TURN CONTEXT]
        #  0.20–0.65  NEAR-MISS    — skill partially matched; inject near-miss note
        #  < 0.20  COMPLETE MISS   — no skill matched; inject capability boundary note
        #
        # All non-skill turns retain the [UNCERTAINTY TIERS] reminder (CR-032).
        if top_skill is not None and top_score >= _SKILL_INJECT_THRESHOLD:
            pass  # skill schema handles context — no extra [TURN CONTEXT] needed

        elif top_skill is not None and top_score >= _OPEN_ENDED_SCORE_THRESHOLD:
            # Near-miss: a skill partially matched but didn't cross the inject threshold.
            # Tell the model which skill came closest so it can reason about partial coverage.
            # Implements FR-ORCH-034 (CR-036).
            skill_label = type(top_skill).__name__.replace("Skill", "").strip() or "Unknown"
            system_prompt = (
                system_prompt
                + f"\n\n[TURN CONTEXT: Near-match — '{skill_label}' skill scored "
                f"{top_score:.2f} (below injection threshold of {_SKILL_INJECT_THRESHOLD}). "
                "State clearly what this skill can and cannot cover for the current request. "
                "Do NOT silently deliver a reduced version — if partial handling is possible, "
                "say so explicitly. Apply [UNCERTAINTY TIERS] vocabulary as appropriate.]\n"
            )

        else:
            # Complete miss: no skill scored above the open-ended threshold.
            # Direct the model to consult [CAPABILITY BOUNDARY] and offer a specific forward path.
            # Implements FR-ORCH-026 (CR-032) and FR-ORCH-034 (CR-036).
            system_prompt = (
                system_prompt
                + "\n\n[TURN CONTEXT: No specific skill matched this request "
                f"(top score {top_score:.2f}, threshold {_OPEN_ENDED_SCORE_THRESHOLD}). "
                "If this request falls outside Xochitl's capabilities, state specifically "
                "what is missing and offer the nearest available forward path — see [CAPABILITY BOUNDARY]. "
                "Apply [UNCERTAINTY TIERS] vocabulary as appropriate.]\n"
            )

        force = "code_generation" if self.force_cloud else None

        # FR-ORCH-025: apply governor routing constraint when LOCAL_ONLY or HARD_STOP.
        # Governor force_route only overrides when no other force is already set
        # (e.g., force_cloud / code_generation always wins).
        if force is None:
            _gov_force = self._governor.force_route()
            if _gov_force:
                force = _gov_force

        # ── FR-UI-005: Real LLM token streaming (CR-031) ─────────────────────
        # Stream when: _stream is True, no skill schema was injected (because
        # skill-call parsing requires the full response), and we're not in
        # force_cloud mode (which targets code generation, always non-streaming).
        use_streaming = (
            _stream
            and not self.force_cloud
            and (top_skill is None or top_score < _SKILL_INJECT_THRESHOLD)
        )

        if use_streaming:
            # Stop the Live refresh context before printing streaming tokens to
            # avoid Rich display conflicts. The main thread's with-status_ctx
            # block will see _live=None and skip its own cleanup.
            if _status is not None:
                _status._stop_event.set()
                if _status._refresh_thread:
                    _status._refresh_thread.join(timeout=0.3)
                    _status._refresh_thread = None
                live = _status._live
                _status._live = None  # prevent double-exit in _StatusContext.__exit__
                if live:
                    try:
                        live.stop()
                    except Exception:
                        pass

            buffer: list[str] = []
            printed_header = False
            for token in self.router.route_stream(
                query=user_input,
                conversation_history=messages,
                system_prompt=system_prompt,
                force_route=force,
            ):
                if not printed_header:
                    console.print(f"\n[bold]Xochitl[/bold]: ", end="")
                    printed_header = True
                console.print(token, end="")
                buffer.append(token)

            if buffer:
                console.print()  # trailing newline after stream
                self._last_response_streamed = True
                _events.emit("llm_complete", {  # FR-ORCH-036 (CR-021)
                    "route": "stream",
                    "tokens_in": 0,
                    "tokens_out": len(buffer),
                    "cost_usd": 0.0,
                })
                response_text = "".join(buffer)
                # Skill calls are not expected on streaming turns (no schema injected),
                # but guard anyway: strip any stray XML and return clean text.
                return _SKILL_CALL_RE.sub("", response_text).strip() or response_text
            # Empty stream → fall through to non-streaming path below
        # ── Non-streaming path (skill calls, special routes, streaming fallback) ──

        result = self.router.route(
            query=user_input,
            conversation_history=messages,
            system_prompt=system_prompt,
            force_route=force,
        )

        if result.error:
            return f"{_ERR} — {result.error}"

        _events.emit("llm_complete", {  # FR-ORCH-036 (CR-021)
            "route": str(result.route),
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "cost_usd": result.cost_usd,
        })

        response_text = result.content or ""

        # Parse for skill call (NFR-PERF-006 — regex only, <10ms)
        skill_call = _parse_skill_call(response_text)

        # Strip <skill_call> XML from the visible part of the response
        visible = _SKILL_CALL_RE.sub("", response_text).strip()

        # CR-019: track whether a skill executed this turn (FR-ORCH-037 trigger)
        _tool_calls_made = False

        if skill_call:
            skill_name, params = skill_call
            skill = self._find_skill_by_name(skill_name)
            if skill:
                if self._skill_call_requires_approval(skill, params):
                    _events.emit("hitl_required", {
                        "action": str(params.get("action", skill_name)),
                        "risk": self._risk_label_for_skill(type(skill).__name__, params),
                    })
                    # Staged for approval — no critique (action hasn't run yet)
                    return self._stage_skill_call_plan(skill, params, user_input, visible)

                _events.emit("skill_started", {"skill": skill_name, "params": list(params.keys())})
                if _status:
                    _status.update(f"running skill: {skill_name}")
                self._emit_action_line(infer_action_label(user_input, skill_name))
                tool_result = skill.execute(user_input, self.current_context, params)
                _events.emit("skill_complete", {"skill": skill_name, "success": True})
                _tool_calls_made = True
                formatted = format_skill_output(tool_result)
                self.current_context["last_skill_name"] = skill_name
                self.current_context["last_action_summary"] = infer_action_label(user_input, skill_name)
                # CR-041: record procedural workflow usage (FR-MEM-008)
                _wf_id = self.current_context.get("active_workflow_id")
                if _wf_id:
                    try:
                        from src.workflows import record_match_usage
                        record_match_usage(int(_wf_id), success=True)
                    except Exception:
                        pass

                # Implements FR-ORCH-009 — persist tool turn in session history
                self.session_history.append({
                    "role": "tool",
                    "skill": skill_name,
                    "content": tool_result,
                    "timestamp": datetime.now().isoformat(),
                })

                body = formatted or tool_result
                if visible:
                    _final = f"{visible}\n\n{format_compact_result(self.current_context['last_action_summary'], body)}"
                else:
                    _final = format_compact_result(self.current_context['last_action_summary'], body)
            else:
                _final = visible or response_text
        else:
            _final = visible or response_text

        # CR-019: post-execution reflection/critique on non-streaming turns (FR-ORCH-037)
        return self._maybe_critique(
            _final, user_input, top_score, _tool_calls_made, messages, system_prompt, force
        )

    def _skill_call_requires_approval(self, skill: Skill, params: dict) -> bool:
        """Return True when a skill call can mutate files, state, or services.

        Implements FR-ORCH-011 / AC-CR004-003: LLM-selected tools still pass
        through a plan and approval gate before side effects.
        """
        name = type(skill).__name__
        action = str(params.get("action", "")).strip()

        if name == "NotionSkill":
            return True
        if name == "OrchestratorSkill":
            return bool(params.get("task_id"))
        if action and action in _MUTATING_SKILL_ACTIONS.get(name, set()):
            return True
        if name == "CodeSkill":
            return True
        return False

    def _stage_skill_call_plan(self, skill: Skill, params: dict, user_input: str, visible: str) -> str:
        name = type(skill).__name__
        risk = self._risk_label_for_skill(name, params)
        action = params.get("action") or params.get("direction") or "execute"
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
        return "state change"

    def _execute_pending_skill_call(self) -> str:
        pending = self.current_context.pop("pending_skill_call", None)
        if not pending:
            return f"{_FYI} - I do not have a pending skill call to run."

        skill_name = pending.get("skill_name", "")
        skill = self._find_skill_by_name(skill_name)
        if not skill:
            return f"{_ERR} - I could not find `{skill_name}` anymore, so I did not run it."

        tool_result = skill.execute(
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
        """Look up a skill by its class name or tool_definition name."""
        for skill in self.skills:
            defn = skill.tool_definition()
            if defn.get("name", "").lower() == name.lower():
                return skill
            if type(skill).__name__.lower() == name.lower():
                return skill
        return None

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
        # Legacy method — no longer called from process_message() (Phase 1 refactor
        # replaced the triple-classification system with direct keyword dispatch).
        # Retained for test compatibility. Uses a local import to avoid a top-level
        # dependency on intent.py from the main chat flow.
        from src.intent import classify_conversation_intent
        return classify_conversation_intent(
            user_input,
            current_project=self.current_project,
        ).to_dict()

        q = user_input.lower()

        has_extension = any(ext in q for ext in _FILE_EXTENSIONS)
        has_path = "\\" in user_input or (
            "/" in user_input and any(c.isalpha() for c in user_input.split("/")[0])
        )
        has_file_kw = any(kw in q for kw in _FILE_READ_KW + _FILE_WRITE_KW + _FILE_DELETE_KW)
        has_file_verb = any(kw in q for kw in _FILE_VERB_KW)
        has_path_indicator = has_extension or has_path or any(kw in q for kw in _PATH_INDICATOR_KW)

        # BUG-CHAT-001 fix: file_operation checked FIRST — explicit path/extension wins
        if has_extension or has_path or has_file_kw or (has_file_verb and has_path_indicator):
            if any(kw in q for kw in _FILE_DELETE_KW):
                op = "delete"
            elif any(kw in q for kw in _FILE_WRITE_KW):
                op = "write"
            else:
                op = "read"
            return {"type": "file_operation", "operation": op}

        # Research checked before task keywords
        if any(kw in q for kw in _RESEARCH_KEYWORDS):
            adversarial = any(kw in q for kw in ["devil", "adversarial", "challenge", "poke holes", "stress test", "steelman"])
            return {"type": "research", "adversarial": adversarial}

        if any(kw in q for kw in _TASK_KEYWORDS):
            return {"type": "task_query"}

        # Everything else goes to the agent loop — the LLM handles it
        return {"type": "general"}

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
        q = user_input.lower().strip()
        op_id = self.current_context.get("pending_file_operation")
        if not op_id:
            return None

        if q in _CONFIRM_YES:
            result = self.file_tools.confirm_operation(op_id)
            del self.current_context["pending_file_operation"]
            return result["message"]

        if q in _CONFIRM_NO:
            result = self.file_tools.cancel_operation(op_id)
            del self.current_context["pending_file_operation"]
            return result["message"]

        return None

    def _handle_action_confirmation(self, user_input: str) -> Optional[str]:
        # Implements FR-ORCH-007 — LLM fallback when exact-match fails
        q = user_input.lower().strip()
        action = self.current_context.get("pending_action")
        if not action:
            return None

        # Fast path: exact-match sets
        if q in _CONFIRM_YES:
            verdict = "yes"
        elif q in _CONFIRM_NO:
            verdict = "no"
        else:
            # FR-ORCH-007: LLM micro-call to interpret natural confirmation
            verdict = self._llm_classify_confirm(action, user_input)
            if verdict == "unclear":
                return None  # fall through to normal conversation

        if verdict == "yes":
            del self.current_context["pending_action"]

            if action == "execute_skill_call":
                return self._execute_pending_skill_call()

            if action == "sync_notion":
                from src.skills.notion_skill import NotionSkill
                return NotionSkill().execute(user_input, self.current_context, {"direction": "pull"})

            if action == "push_notion":
                from src.skills.notion_skill import NotionSkill
                return NotionSkill().execute(user_input, self.current_context, {"direction": "push"})

            if action == "init_project":
                from src.skills.bmad_skill import BMADSkill
                skill = BMADSkill()
                project_id = self.current_context.pop("pending_project_id", "new-project")
                name = self.current_context.pop("pending_project_name", project_id)
                desc = self.current_context.pop("pending_project_description", "")
                skill.init_project(project_id, name, desc)

                # BUG-ORCH-002 fix: seed Business Model from spec if one was mentioned
                from src.router import _resolve_file_context
                file_ctx = _resolve_file_context("", self.session_history)
                if file_ctx:
                    prompt = (
                        f"I have just initialized the project '{name}'.\n"
                        f"Based on the following product specification, please draft a "
                        "Business Model (BMM) summary including: Core Value Prop, "
                        "Target Users, and Key Features.\n\n"
                        f"{file_ctx}"
                    )
                    result = self.router.route(
                        query=prompt,
                        conversation_history=[],
                        system_prompt="You are a Product Manager drafting a Business Model (BMM) artifact.",
                        force_route="general",
                    )
                    if not result.error:
                        skill.save_bmad_artifact(project_id, "business-model", result.content)
                        return (
                            f"{_OK} — Created **{name}**.\n\n"
                            "I've read the spec and drafted the **Business Model** for you:\n\n"
                            f"{result.content}\n\n"
                            "Shall we move to **Architecture**?"
                        )

                return (
                    f"{_OK} — Created **{name}** at `projects/{project_id}/`.\n\n"
                    "Let's start with the Business Model. "
                    "What's the core struggle this app solves? "
                    "Who's experiencing it, and what do they do today instead?"
                )

            if action == "generate_specs":
                from src.skills.sdd_skill import SDDSkill
                project_id = self.current_project or self.current_context.get("pending_project_id", "")
                return SDDSkill().generate_specs_from_bmad(project_id)

            if action == "analyze_issue":
                from src.skills.sdd_skill import SDDSkill
                project_id = self.current_project or ""
                issue_desc = self.current_context.pop("pending_issue_description", "")
                sdd = SDDSkill()
                result = sdd.analyze_issue(project_id, issue_desc)
                if "error" in result:
                    return f"Analysis failed: {result['error']}"
                confidence = result.get("confidence", 0)
                summary = result.get("summary", "")
                changes = result.get("spec_changes_needed", [])
                guidance = result.get("implementation_guidance", [])

                lines = [f"**Analysis:** {result.get('analysis_type', '?')}"]
                if summary:
                    lines.append(f"\n{summary}")
                if changes:
                    lines.append("\n**Spec changes needed:**")
                    for c in changes:
                        lines.append(f"- `{c.get('requirement_id', '?')}`: {c.get('rationale', '')}")
                if guidance:
                    lines.append("\n**Implementation guidance:**")
                    for g in guidance:
                        lines.append(f"- {g}")
                if confidence < 0.75:
                    lines.append(f"\n⚠ Confidence {confidence:.0%} — review before applying changes.")
                if changes:
                    self.current_context["pending_spec_changes"] = changes
                    lines.append("\nWant me to apply the spec changes and create an issue?")
                return "\n".join(lines)

            if action == "scaffold_code":
                from src.skills.code_skill import CodeSkill
                project_id = self.current_project or ""
                component = self.current_context.pop("pending_component", "backend")
                return CodeSkill().scaffold_from_specs(project_id, component)

        if verdict == "no":
            del self.current_context["pending_action"]
            self.current_context.pop("pending_project_id", None)
            self.current_context.pop("pending_project_name", None)
            self.current_context.pop("pending_project_description", None)
            self.current_context.pop("pending_issue_description", None)
            self.current_context.pop("pending_component", None)
            self.current_context.pop("pending_skill_call", None)
            return f"{_OK}, no problem."

        return None

    def _llm_classify_confirm(self, pending_action: str, user_input: str) -> str:
        """LLM micro-call to interpret a natural-language yes/no response.

        Implements FR-ORCH-007. Returns 'yes' | 'no' | 'unclear'.
        Uses force_route='simple_qa' to keep it local and fast.
        """
        prompt = (
            f"Pending action: {pending_action}\n"
            f"User says: \"{user_input}\"\n\n"
            "Does the user want to confirm (yes), cancel (no), or is it unclear?\n"
            "Reply with exactly one word: yes | no | unclear"
        )
        result = self.router.route(
            query=prompt,
            conversation_history=[],
            system_prompt="Classify user intent as: yes, no, or unclear. Reply with one word only.",
            force_route="simple_qa",
        )
        if result.error:
            return "unclear"
        raw = (result.content or "").strip().lower()
        first = raw.split()[0] if raw.split() else "unclear"
        if first in {"yes", "y", "confirm", "sure", "ok", "okay", "yep", "yeah", "do", "go", "proceed"}:
            return "yes"
        if first in {"no", "n", "cancel", "stop", "don't", "nope", "never", "abort"}:
            return "no"
        return "unclear"

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
        """Dispatch /command [args] without going through the LLM."""
        from src.security import cmd_authorize, cmd_revoke, cmd_list_registry, cmd_audit

        parts = raw.split(maxsplit=1)
        verb = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        # FR-UI-007: Stage next message to run after current response finishes
        if verb == "/next":
            if not arg:
                if self._staged_message:
                    return f"[dim]Staged message cleared.[/dim]"
                return "Usage: /next <message to send after this response>"
            self._staged_message = arg
            return f"[dim]✓ Staged: '{arg}' — will run after current response.[/dim]"

        # FR-UI-006: Retry the last cancelled message
        if verb == "/retry":
            if not self._last_cancelled:
                return "[dim]Nothing to retry — no message was cancelled.[/dim]"
            self._staged_message = self._last_cancelled
            self._last_cancelled = None
            return f"[dim]✓ Re-queued: '{self._staged_message}'[/dim]"

        if verb == "/authorize":
            return cmd_authorize(arg)
        if verb == "/revoke":
            return cmd_revoke(arg)
        if verb == "/registry":
            return cmd_list_registry()
        if verb == "/audit":
            n = int(arg) if arg.isdigit() else 20
            return cmd_audit(n)

        # FR-BMAD-003: SDD traceability review
        if verb == "/review":
            from src.skills.sdd_skill import SDDSkill
            project_id = arg or self.current_project or ""
            return SDDSkill().review_code_traceability(project_id)

        if verb == "/research":
            if not arg:
                return "Usage: /research <topic>"
            from src.research import run_research
            result = run_research(arg, adversarial=False, check_conflicts=True)
            parts_out = [f"**Research: {result['topic']}**", f"_{result['budget']}_\n"]
            if result["synthesis"]:
                parts_out.append(result["synthesis"])
            if result["conflicts"]:
                parts_out.append(f"\n**Conflicts detected ({len(result['conflicts'])}):**")
                for c in result["conflicts"]:
                    parts_out.append(f"- {c['source']}: {c['verdict'][:120]}")
            return "\n".join(parts_out)

        if verb == "/adversarial":
            if not arg:
                return "Usage: /adversarial <claim to challenge>"
            from src.research import adversarial_review
            return adversarial_review(arg)

        # FR-ORCH-025: show session token budget status (AC-CR026-006)
        if verb == "/budget":
            return self._governor.budget_detail()

        # CR-038: dismiss a proactive signal category (FR-INIT-002)
        if verb == "/dismiss":
            try:
                from src.initiative import InitiativeCategory
                engine = getattr(self, "_initiative", None)
                if engine is None:
                    return "[dim]Initiative engine not active.[/dim]"
                # Default: dismiss SYSTEM_FAILURE if no arg; otherwise parse arg
                cat_str = arg.lower() if arg else "system_failure"
                try:
                    cat = InitiativeCategory(cat_str)
                except ValueError:
                    valid = ", ".join(c.value for c in InitiativeCategory)
                    return f"[dim]Unknown category '{cat_str}'. Valid: {valid}[/dim]"
                engine.dismiss(cat)
                return f"[dim]Dismissed '{cat.value}' alerts. Repeated dismissals auto-suppress.[/dim]"
            except Exception as exc:
                return f"[dim]Dismiss failed: {exc}[/dim]"

        # CR-041: procedural memory slash commands (FR-MEM-011)
        if verb == "/workflows":
            from src.workflows import list_workflows_formatted
            return list_workflows_formatted(project=self.current_project)

        if verb == "/workflow":
            from src.workflows import (
                execute_workflow,
                get_workflow_by_name,
                list_workflows_formatted,
                save_workflow_from_session,
            )
            if not arg:
                return (
                    "Usage: /workflow save <name>  |  /workflow run <name>  |  /workflows\n"
                    + list_workflows_formatted(project=self.current_project)
                )
            if arg.lower().startswith("save "):
                wf_name = arg[5:].strip()
                if not wf_name:
                    return "Usage: /workflow save <name>"
                trigger = self._last_user_message() or wf_name
                try:
                    wf_id = save_workflow_from_session(
                        wf_name,
                        trigger[:240],
                        self.session_history,
                        project=self.current_project,
                        source="distilled",
                        use_llm_distill=True,
                    )
                    return (
                        f"Saved workflow **{wf_name}** (id {wf_id}, LLM-distilled). "
                        f"Recall: mention '{trigger[:80]}' or `/workflow run {wf_name}`"
                    )
                except ValueError as exc:
                    return f"[dim]Could not save workflow: {exc}[/dim]"
                except Exception as exc:
                    return f"[dim]Save failed: {exc}[/dim]"
            if arg.lower().startswith("run "):
                wf_name = arg[4:].strip()
                if not wf_name:
                    return "Usage: /workflow run <name>"
                wf = get_workflow_by_name(wf_name)
                if not wf:
                    return f"No workflow named '{wf_name}'. Use `/workflows` to list."
                self.current_context["_chat_skills"] = self.skills
                return execute_workflow(
                    wf,
                    self._last_user_message() or wf_name,
                    self.skills,
                    self.current_context,
                )
            return f"[dim]Unknown /workflow subcommand. Use: save or run[/dim]"

        # A3 — structured daily brief (FR-CONV-003).
        # Pull-only: never surfaced unsolicited (alert-fatigue risk).
        if verb == "/brief":
            try:
                from src.brief import build_structured_brief
                from src import database as _db
                with _db.get_connection() as conn:
                    _queue = _db.get_queue(conn)
                return build_structured_brief(_queue, notion_pending=[])
            except Exception as exc:
                return f"[dim]{_FYI} — couldn't build brief: {exc}[/dim]"

        # FR-ORCH-041: /debug skill — show per-skill can_handle() scores (AC-CR047-006)
        if verb == "/debug" and arg.lower().startswith("skill"):
            last_input = self.current_context.get("_last_debug_input", "")
            if not last_input:
                # Fall back to last session history user message
                for msg in reversed(self.session_history):
                    if msg.get("role") == "user":
                        last_input = msg.get("content", "")
                        break
            if not last_input:
                return "[dim]No recent message to score against — say something first.[/dim]"
            lines = [f"[bold]can_handle scores[/bold] for: {last_input[:80]}"]
            rows = []
            for skill in self.skills:
                try:
                    score = skill.can_handle(last_input, self.current_context)
                except Exception:
                    score = -1.0
                name = type(skill).__name__
                marker = " ← injected" if score >= _SKILL_INJECT_THRESHOLD else (
                    " ← near-miss" if score >= _OPEN_ENDED_SCORE_THRESHOLD else ""
                )
                rows.append((score, f"  {score:.2f}  {name}{marker}"))
            rows.sort(key=lambda r: r[0], reverse=True)
            lines.extend(r[1] for r in rows)
            lines.append(f"\n  inject threshold: {_SKILL_INJECT_THRESHOLD}  "
                         f"near-miss threshold: {_OPEN_ENDED_SCORE_THRESHOLD}")
            return "\n".join(lines)

        available = (
            "/next <msg>  /retry  /authorize  /revoke  "
            "/registry  /audit  /review  /research  /adversarial  /budget  /brief  "
            "/dismiss  /workflows  /workflow save <name>  /workflow run <name>  "
            "/debug skill"
        )
        return f"[dim]{_FYI} — unknown command: {verb}\nAvailable: {available}[/dim]"

    # ── Helpers ───────────────────────────────────────────────────────────────

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
        return response

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
