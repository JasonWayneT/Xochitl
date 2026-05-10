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
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

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
from src.intent import classify_conversation_intent
from src.memory import read_memory
from src import database as db
from src.file_tools import FileTools
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
    """Context manager that shows a live flower-animated status during LLM calls.

    Implements FR-UI-001 — replaces static 'thinking...' spinner with a
    Rich Live display showing a cycling flower glyph, the current sub-task,
    and elapsed time. Flower sequence mirrors the Xochitl splash screen.
    """

    # Flower frames — mirrors the ✿ ❀ splash screen pattern
    _FLOWERS = ["✿", "❀", "✿", "❀"]

    def __init__(self, label: str = "Thinking"):
        self._label = label
        self._start = time.monotonic()
        self._live: Optional[Live] = None
        self._frame = 0

    def _render(self) -> Text:
        elapsed = time.monotonic() - self._start
        # Advance flower frame (4 fps via refresh_per_second=4)
        flower = self._FLOWERS[self._frame % len(self._FLOWERS)]
        self._frame += 1
        t = Text()
        t.append("  ", style="")
        t.append(f"{flower} ", style="bold magenta")
        t.append(self._label, style="dim")
        t.append(f"  ({elapsed:.1f}s)", style="dim")
        return t

    def update(self, label: str) -> None:
        self._label = label
        if self._live:
            self._live.update(self._render())

    def __enter__(self) -> "_StatusContext":
        if not _TERM_DUMB:
            self._live = Live(
                self._render(),
                console=console,
                refresh_per_second=4,
                transient=True,
            )
            self._live.__enter__()
        return self

    def __exit__(self, *args) -> None:
        if self._live:
            self._live.__exit__(*args)
            self._live = None


def _print_boot_banner(con: Console) -> None:
    # Implements FR-UX-001 (WIP dashboard header in interactive loop)
    con.print()
    con.print("      [bold magenta]✿[/bold magenta] [bold yellow]❀[/bold yellow] [bold magenta]✿[/bold magenta]")
    con.print("    [bold yellow]❀[/bold yellow]   [bold magenta]✿[/bold magenta]   [bold yellow]❀[/bold yellow]    [bold cyan]Xochitl[/bold cyan]")
    con.print("      [bold magenta]✿[/bold magenta] [bold yellow]❀[/bold yellow] [bold magenta]✿[/bold magenta]     [dim]Chief of Staff[/dim]")
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
            self._builtin_skills = [BMADSkill(), SDDSkill(), CodeSkill(), NotionSkill(), OrchestratorSkill()]

        from src.skills.dynamic_skill import load_dynamic_skills
        return (self._builtin_skills or []) + load_dynamic_skills(self.current_project)

    # ── Public interface ──────────────────────────────────────────────────────

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

        console.print("[dim]Type 'quit' or Ctrl+C to exit. (Ctrl+C twice quickly to force-quit)[/dim]\n")

        try:
            while True:
                try:
                    user_input = Prompt.ask("[bold cyan]you[/bold cyan]")
                except KeyboardInterrupt:
                    # FR-UI-002: Smart Ctrl-C — 2-stage exit
                    now = time.monotonic()
                    if self._active_status is not None:
                        # First press: cancel active LLM call
                        console.print("\n[dim]Cancelled.[/dim]")
                        self._active_status = None
                        continue
                    if now - self._last_interrupt < 1.2:
                        # Second press within 1.2s: exit
                        console.print("\n[dim]Hasta luego 👋[/dim]\n")
                        break
                    else:
                        self._last_interrupt = now
                        console.print(
                            "\n[dim]Press Ctrl+C again to exit, or keep typing.[/dim]"
                        )
                        continue
                except EOFError:
                    break

                if not user_input.strip():
                    continue

                if user_input.strip().lower() in ("quit", "exit", "q", "bye"):
                    console.print("\n[dim]Hasta luego 👋[/dim]\n")
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

                # FR-UI-001: Live status tier — show current sub-task during processing
                status_ctx = _StatusContext("Thinking")
                self._active_status = status_ctx
                try:
                    with status_ctx:
                        status_ctx.update("Classifying intent")
                        response = self.process_message(user_input, _status=status_ctx)
                finally:
                    self._active_status = None

                console.print(f"\n[bold]Xochitl[/bold]: ", end="")
                try:
                    console.print(Markdown(response))
                except Exception:
                    console.print(response)
                console.print()

        except KeyboardInterrupt:
            pass

        console.print("[dim]Session ended.[/dim]")

    def process_message(self, user_input: str, _status: Optional["_StatusContext"] = None) -> str:
        """Process one user message and return Xochitl's response."""
        self.session_history.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat(),
        })

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
            _status.update("Refreshing context")
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
        cm = ContextManager(route=route, skills=self.skills)
        cm.ingest(
            query=user_input,
            history=self._clean_history(),
            project=self.current_project,
            local_mode=(route == "local"),
        )

        # ── 5. Classify intent (fast keyword path for unambiguous cases) ──────
        if _status:
            _status.update("Classifying intent")
        intent = self._classify_intent(user_input)
        self.current_context["last_intent"] = intent

        # ── 6. Route: special handlers for file/task/research; agent loop for rest ──
        if _status:
            _status.update(f"Handling: {intent['type'].replace('_', ' ')}")

        if intent["type"] == "task_query":
            response = self._handle_task_query(user_input, cm)
        elif intent["type"] == "file_operation":
            if _status:
                _status.update("Resolving file context")
            response = self._handle_file_operation(user_input, intent, cm)
        elif intent["type"] == "research":
            if _status:
                _status.update("Researching")
            response = self._handle_research(user_input, intent)
        elif intent.get("intent_type") == "exploration" and intent.get("context_scope") == "active_project":
            if _status:
                _status.update("Exploring project")
            response = self._handle_repo_exploration(user_input, cm)
        else:
            # ── Agent loop: LLM controls routing and skill dispatch ────────────
            # Implements FR-ORCH-008 — covers general, simple_question,
            # bmad_workflow, new_project, sdd_workflow, issue_tracking,
            # code_generation_intent, orchestrator_query, action_request.
            if _status:
                _status.update("Asking model")
            response = self._agent_loop(user_input, cm, _status)

        response = self._maybe_offer_skill_creation(user_input, response)
        return self._record(response)

    # ── Agent loop (FR-ORCH-008) ──────────────────────────────────────────────

    def _agent_loop(
        self,
        user_input: str,
        cm: ContextManager,
        _status: Optional[_StatusContext] = None,
    ) -> str:
        """LLM-controlled turn: model sees skill manifest and may invoke a skill.

        Implements FR-ORCH-008. Flow:
          1. Route to LLM with full context + skill manifest
          2. Parse response for <skill_call name="X">{...}</skill_call>
          3. If found: execute skill, record in history, append result to response
          4. Strip any stray <skill_call> tags from visible output
        """
        system_prompt = cm.assemble_system_prompt()
        messages = cm.assemble_messages(self._clean_history(), user_input, tag_provenance=True)

        force = "code_generation" if self.force_cloud else None
        result = self.router.route(
            query=user_input,
            conversation_history=messages,
            system_prompt=system_prompt,
            force_route=force,
        )

        if result.error:
            return f"{_ERR} — {result.error}"

        response_text = result.content or ""

        # Parse for skill call (NFR-PERF-006 — regex only, <10ms)
        skill_call = _parse_skill_call(response_text)

        # Strip <skill_call> XML from the visible part of the response
        visible = _SKILL_CALL_RE.sub("", response_text).strip()

        if skill_call:
            skill_name, params = skill_call
            skill = self._find_skill_by_name(skill_name)
            if skill:
                if self._skill_call_requires_approval(skill, params):
                    return self._stage_skill_call_plan(skill, params, user_input, visible)

                if _status:
                    _status.update(f"Running {skill_name}")
                tool_result = skill.execute(user_input, self.current_context, params)

                # Implements FR-ORCH-009 — persist tool turn in session history
                self.session_history.append({
                    "role": "tool",
                    "skill": skill_name,
                    "content": tool_result,
                    "timestamp": datetime.now().isoformat(),
                })

                if visible:
                    return f"{visible}\n\n{tool_result}"
                return tool_result

        return visible or response_text

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

    def _find_skill_by_name(self, name: str) -> Optional[Skill]:
        """Look up a skill by its class name or tool_definition name."""
        for skill in self.skills:
            defn = skill.tool_definition()
            if defn.get("name", "").lower() == name.lower():
                return skill
            if type(skill).__name__.lower() == name.lower():
                return skill
        return None

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
        # Implements FR-ORCH-010: structured intent, while preserving the
        # legacy `type` field used by existing handlers.
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

        available = "/authorize  /revoke  /registry  /audit  /review  /research  /adversarial"
        return f"[dim]{_FYI} — unknown command: {verb}\nAvailable: {available}[/dim]"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _record(self, response: str) -> str:
        """Append response to session history and persist.

        Implements FR-ORCH-009 (partial) — strips stray <skill_call> tags
        that survived to the visible response (BUG-CHAT-003 coverage) and
        strips other LLM-hallucinated tool-call syntax.
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
