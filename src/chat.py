"""XochitlChat — conversational layer over the tiered router.
# Implements FR-ORCH-004 (Tool Outcome Narrative — tool results are synthesized into Matriarca-voice responses)

Design principles (from XOCHITL_CONVERSATIONAL_HARNESS.md):
- Natural back-and-forth, like Claude.ai in the terminal
- Detect skills, suggest them, only execute after user confirms
- File ops go through FileTools permission model (overwrite/delete need consent)
- Orchestrator is a tool Xochitl uses when user says "delegate it" — not a default
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from src.router import get_router, _live_db_context, _resolve_file_context
from src.context_loader import build_system_prompt
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
    "i want to build", "i want to make", "i want to create",
    "build an app", "create an app", "new app", "new project", "start a project",
    "let's build", "let's make", "let's create",
]
_SDD_KEYWORDS      = ["spec", "requirement", "fr-", "ac-", "ec-", "traceability"]
_ISSUE_KEYWORDS    = ["bug", "issue", "broken", "doesn't work", "failing", "wrong behavior", "error in"]
_CODE_GEN_KEYWORDS = ["scaffold", "generate code", "implement the", "code for", "build the backend", "build the frontend"]
_RESEARCH_KEYWORDS = [
    "research", "devil's advocate", "adversarial", "challenge this", "challenge that",
    "synthesize", "look into", "find out about", "what do we know about",
    "poke holes", "stress test this", "steelman", "play devil",
]


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

        self._skills: Optional[list[Skill]] = None

    @property
    def skills(self) -> list[Skill]:
        if self._skills is None:
            from src.skills.bmad_skill import BMADSkill
            from src.skills.sdd_skill import SDDSkill
            from src.skills.code_skill import CodeSkill
            from src.skills.notion_skill import NotionSkill
            from src.skills.orchestrator_skill import OrchestratorSkill
            self._skills = [BMADSkill(), SDDSkill(), CodeSkill(), NotionSkill(), OrchestratorSkill()]
        return self._skills

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

        console.print("[dim]Type 'quit' or Ctrl+C to exit.[/dim]\n")

        try:
            while True:
                try:
                    user_input = Prompt.ask("[bold cyan]you[/bold cyan]")
                except (EOFError, KeyboardInterrupt):
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

                with console.status("[dim]thinking...[/dim]", spinner="xochitl"):
                    response = self.process_message(user_input)

                console.print(f"\n[bold]Xochitl[/bold]: ", end="")
                try:
                    console.print(Markdown(response))
                except Exception:
                    console.print(response)
                console.print()

        except KeyboardInterrupt:
            pass

        console.print("[dim]Session ended.[/dim]")

    def process_message(self, user_input: str) -> str:
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

        # ── 3. Refresh BMAD context ───────────────────────────────────────────
        from src.bmad import detect_bmad_project
        self.current_context["bmad_project"] = detect_bmad_project(Path.cwd())

        # ── 3b. Refresh SDD project context ──────────────────────────────────
        self.current_project = self._detect_current_project()
        if self.current_project:
            self.current_context["current_project"] = self.current_project
            self.current_context["specs_generated"] = self._check_specs_exist(self.current_project)
            self.current_context["bmad_complete"] = self._check_bmad_complete(self.current_project)
        else:
            self.current_context.pop("current_project", None)
            self.current_context.pop("specs_generated", None)
            self.current_context.pop("bmad_complete", None)

        # ── 4. Classify intent ────────────────────────────────────────────────
        intent = self._classify_intent(user_input)

        # ── 5. Check if a skill applies (suggest first, don't execute) ────────
        skill_suggestion = self._check_skills(user_input, self.current_context)
        if skill_suggestion and intent["type"] not in ("general", "simple_question", "task_query"):
            return self._record(skill_suggestion)

        # ── 6. Route to intent handler ────────────────────────────────────────
        if intent["type"] == "task_query":
            response = self._handle_task_query(user_input)
        elif intent["type"] == "action_request":
            response = self._handle_action_request(user_input, intent)
        elif intent["type"] == "file_operation":
            response = self._handle_file_operation(user_input, intent)
        elif intent["type"] == "orchestrator_query":
            response = self._handle_orchestrator_query()
        elif intent["type"] == "bmad_workflow":
            response = self._handle_bmad_workflow(user_input)
        elif intent["type"] == "new_project":
            response = self._handle_new_project_request(user_input)
        elif intent["type"] == "sdd_workflow":
            response = self._handle_sdd_workflow(user_input)
        elif intent["type"] == "issue_tracking":
            response = self._handle_issue_tracking(user_input)
        elif intent["type"] == "code_generation_intent":
            response = self._handle_code_generation_request(user_input)
        elif intent["type"] == "research":
            response = self._handle_research(user_input, intent)
        else:
            response = self._general_conversation(user_input)

        return self._record(response)

    # ── Intent classification ─────────────────────────────────────────────────

    def _classify_intent(self, user_input: str) -> dict:
        q = user_input.lower()

        has_extension = any(ext in q for ext in _FILE_EXTENSIONS)
        has_path = "\\" in user_input or (
            "/" in user_input and any(c.isalpha() for c in user_input.split("/")[0])
        )
        has_file_kw = any(kw in q for kw in _FILE_READ_KW + _FILE_WRITE_KW + _FILE_DELETE_KW)
        has_file_verb = any(kw in q for kw in _FILE_VERB_KW)
        has_path_indicator = has_extension or has_path or any(kw in q for kw in _PATH_INDICATOR_KW)

        if has_extension or has_path or has_file_kw or (has_file_verb and has_path_indicator):
            if any(kw in q for kw in _FILE_DELETE_KW):
                op = "delete"
            elif any(kw in q for kw in _FILE_WRITE_KW):
                op = "write"
            else:
                op = "read"
            return {"type": "file_operation", "operation": op}

        # Research / adversarial checked before task keywords — "research X for task Y" must route here
        if any(kw in q for kw in _RESEARCH_KEYWORDS):
            adversarial = any(kw in q for kw in ["devil", "adversarial", "challenge", "poke holes", "stress test", "steelman"])
            return {"type": "research", "adversarial": adversarial}

        if any(kw in q for kw in _TASK_KEYWORDS):
            return {"type": "task_query"}

        if any(kw in q for kw in _BG_KEYWORDS):
            return {"type": "orchestrator_query"}

        if any(kw in q for kw in _ACTION_KEYWORDS):
            action = "sync_notion" if ("sync" in q or "pull" in q or "push" in q or "notion" in q) else "start_task"
            return {"type": "action_request", "action": action}

        # New project initialization — check before generic BMAD
        if any(kw in q for kw in _BUILD_KEYWORDS):
            return {"type": "new_project"}

        if any(kw in q for kw in _BMAD_KEYWORDS) and self.current_context.get("bmad_project"):
            return {"type": "bmad_workflow"}

        # SDD / issue / code intents — only when a project is active
        if self.current_project:
            if any(kw in q for kw in _ISSUE_KEYWORDS):
                return {"type": "issue_tracking"}
            if any(kw in q for kw in _CODE_GEN_KEYWORDS):
                return {"type": "code_generation_intent"}
            if any(kw in q for kw in _SDD_KEYWORDS):
                return {"type": "sdd_workflow"}

        if len(user_input.split()) <= 6:
            return {"type": "simple_question"}

        return {"type": "general"}

    # ── Skill detection ───────────────────────────────────────────────────────

    def _check_skills(self, user_input: str, context: dict) -> Optional[str]:
        scored = [(s, s.can_handle(user_input, context)) for s in self.skills]
        best, score = max(scored, key=lambda x: x[1])
        if score > 0.6:
            return best.suggest(user_input, context)
        return None

    # ── Intent handlers ───────────────────────────────────────────────────────

    def _handle_task_query(self, user_input: str) -> str:
        system = build_system_prompt(read_memory()) + "\n\n" + _live_db_context()
        result = self.router.route(
            query=user_input,
            conversation_history=self._clean_history(),
            system_prompt=system,
            force_route="task_management",
        )
        return result.content if not result.error else f"{_ERR} — {result.error}"

    def _handle_action_request(self, user_input: str, intent: dict) -> str:
        action = intent.get("action", "generic")

        if action == "sync_notion":
            self.current_context["pending_action"] = "sync_notion"
            q = user_input.lower()
            if "push" in q:
                self.current_context["pending_action"] = "push_notion"
                return "I can push your completed tasks to Notion. Want me to do that?"
            return (
                "I can pull the latest updates from Notion — projects, deadlines, new tasks. "
                "Want me to run the sync?"
            )

        if action == "start_task":
            return (
                "Two ways to tackle this:\n\n"
                "1. **Work together** — I help you step by step in chat\n"
                "2. **Delegate it** — I spin up a background agent and you check in later\n\n"
                "Which one?"
            )

        return self._general_conversation(user_input)

    def _handle_file_operation(self, user_input: str, intent: dict) -> str:
        op = intent.get("operation", "read")

        if op == "read":
            file_ctx = _resolve_file_context(user_input)
            if file_ctx:
                system = build_system_prompt(read_memory()) + "\n\n" + file_ctx
                result = self.router.route(
                    query=user_input,
                    conversation_history=self._clean_history(),
                    system_prompt=system,
                )
                return result.content if not result.error else f"{_ERR} — {result.error}"
            return f"{_FYI} — I don't see a specific file in that message. Can you give me the full path?"

        return self._general_conversation(user_input)

    def _handle_orchestrator_query(self) -> str:
        from src.skills.orchestrator_skill import OrchestratorSkill
        orch = next((s for s in self.skills if isinstance(s, OrchestratorSkill)), None)
        if orch:
            return orch._format_status()
        return "No background tasks running. Want to delegate something?"

    def _handle_bmad_workflow(self, user_input: str) -> str:
        from src.bmad import build_bmad_context
        bmad_project = self.current_context.get("bmad_project")
        bmad_ctx = build_bmad_context(bmad_project) if bmad_project else ""
        system = build_system_prompt(read_memory())
        result = self.router.route(
            query=user_input,
            conversation_history=self._clean_history(),
            system_prompt=system,
            bmad_context=bmad_ctx,
            force_route="bmad_complex",
        )
        return result.content if not result.error else f"Error: {result.error}"

    def _handle_new_project_request(self, user_input: str) -> str:
        """Ask for confirmation before creating the project structure."""
        project_name = self._extract_project_name(user_input)
        project_id = re.sub(r"[^a-z0-9]+", "-", project_name.lower()).strip("-")

        self.current_context["pending_action"] = "init_project"
        self.current_context["pending_project_id"] = project_id
        self.current_context["pending_project_name"] = project_name
        self.current_context["pending_project_description"] = user_input

        return (
            f"I'll set up **{project_name}** as a new BMAD-SDD project at `projects/{project_id}/`. "
            "I'll then walk you through Business Model → Architecture → Design before we touch any code. "
            "Shall I create the structure?"
        )

    def _handle_sdd_workflow(self, user_input: str) -> str:
        """Route SDD-related requests (specs, requirements, traceability)."""
        project_id = self.current_project
        if not project_id:
            return self._general_conversation(user_input)

        from src.skills.sdd_skill import SDDSkill
        sdd = SDDSkill()
        meta = sdd._read_meta(project_id)

        q = user_input.lower()

        if "generate" in q and "spec" in q:
            self.current_context["pending_action"] = "generate_specs"
            return sdd.suggest(user_input, self.current_context)

        if "list" in q and ("requirement" in q or "spec" in q):
            reqs = sdd.list_requirements(project_id)
            if not reqs:
                return "No requirements yet. Generate specs first."
            lines = [f"- **{r['id']}**: {r['description'][:80]} `[{r['status']}]`" for r in reqs]
            return f"**{len(reqs)} requirements** for {project_id}:\n\n" + "\n".join(lines)

        if re.search(r"\bFR-[A-Z]+-\d+\b", user_input.upper()):
            req_id = re.search(r"\bFR-[A-Z]+-\d+\b", user_input.upper()).group(0)
            req = sdd.get_requirement(project_id, req_id)
            if req:
                acs = "\n".join(f"  - {ac}" for ac in req.get("acceptance_criteria", []))
                return (
                    f"**{req_id}** ({req.get('status', '?')} / {req.get('priority', '?')})\n\n"
                    f"{req.get('description', '')}\n\n"
                    f"**Acceptance Criteria:**\n{acs}\n\n"
                    f"**Implementation:** {req.get('implementation', '_(pending)_')}"
                )
            return f"{req_id} not found in specs."

        # Suggest next step based on project state
        return sdd.get_next_step_suggestion(project_id)

    def _handle_issue_tracking(self, user_input: str) -> str:
        """Handle bug reports and issue analysis requests."""
        project_id = self.current_project
        if not project_id:
            return self._general_conversation(user_input)

        self.current_context["pending_action"] = "analyze_issue"
        self.current_context["pending_issue_description"] = user_input

        return (
            "I can analyze this against your specs — "
            "figure out if it's a spec gap, a spec bug, or an implementation bug — "
            "and suggest the exact requirement update needed. Should I?"
        )

    def _handle_code_generation_request(self, user_input: str) -> str:
        """Handle scaffold/implement/test requests."""
        project_id = self.current_project
        if not project_id:
            return self._general_conversation(user_input)

        if not self.current_context.get("specs_generated"):
            return "Specs aren't generated yet. Want me to do that first?"

        q = user_input.lower()
        component = "backend"
        if "frontend" in q:
            component = "frontend"
        elif "api" in q:
            component = "api"
        elif "model" in q:
            component = "models"

        self.current_context["pending_action"] = "scaffold_code"
        self.current_context["pending_component"] = component

        return (
            f"I can scaffold the **{component}** from your specs. "
            "Every function will reference its FR-* requirement. Want me to go ahead?"
        )

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

    def _general_conversation(self, user_input: str) -> str:
        force = "code_generation" if self.force_cloud else None
        result = self.router.route(
            query=user_input,
            conversation_history=self._clean_history(),
            system_prompt=build_system_prompt(read_memory()),
            force_route=force,
        )
        return result.content if not result.error else f"{_ERR} — {result.error}"

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
        q = user_input.lower().strip()
        action = self.current_context.get("pending_action")
        if not action:
            return None

        if q in _CONFIRM_YES:
            del self.current_context["pending_action"]

            # ── Existing actions ──────────────────────────────────────────
            if action == "sync_notion":
                from src.skills.notion_skill import NotionSkill
                return NotionSkill().execute(user_input, self.current_context, {"direction": "pull"})

            if action == "push_notion":
                from src.skills.notion_skill import NotionSkill
                return NotionSkill().execute(user_input, self.current_context, {"direction": "push"})

            # ── Phase 1: New project init ─────────────────────────────────
            if action == "init_project":
                from src.skills.bmad_skill import BMADSkill
                skill = BMADSkill()
                project_id = self.current_context.pop("pending_project_id", "")
                name = self.current_context.pop("pending_project_name", project_id)
                desc = self.current_context.pop("pending_project_description", "")
                skill.init_project(project_id, name, desc)
                return (
                    f"Created **{name}** at `projects/{project_id}/`.\n\n"
                    "Let's start with the Business Model. "
                    "What's the core struggle this app solves? "
                    "Who's experiencing it, and what do they do today instead?"
                )

            # ── Phase 2: Spec generation ──────────────────────────────────
            if action == "generate_specs":
                from src.skills.sdd_skill import SDDSkill
                project_id = self.current_project or self.current_context.get("pending_project_id", "")
                return SDDSkill().generate_specs_from_bmad(project_id)

            # ── Phase 3: Issue analysis ───────────────────────────────────
            if action == "analyze_issue":
                from src.skills.sdd_skill import SDDSkill
                import json
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

                # Store analysis for follow-up update
                if changes:
                    self.current_context["pending_spec_changes"] = changes
                    lines.append("\nWant me to apply the spec changes and create an issue?")

                return "\n".join(lines)

            # ── Phase 4: Code scaffolding ─────────────────────────────────
            if action == "scaffold_code":
                from src.skills.code_skill import CodeSkill
                project_id = self.current_project or ""
                component = self.current_context.pop("pending_component", "backend")
                return CodeSkill().scaffold_from_specs(project_id, component)

        if q in _CONFIRM_NO:
            del self.current_context["pending_action"]
            self.current_context.pop("pending_project_id", None)
            self.current_context.pop("pending_project_name", None)
            self.current_context.pop("pending_project_description", None)
            self.current_context.pop("pending_issue_description", None)
            self.current_context.pop("pending_component", None)
            return f"{_OK}, no problem."

        return None

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
        # Fallback: take last few words
        words = user_input.strip().split()
        return " ".join(words[-3:]).title() if len(words) >= 3 else user_input.strip().title()

    # ── Slash command dispatch (FR-SEC-001, FR-SEC-003, FR-SEC-004) ──────────

    def _handle_slash_command(self, raw: str) -> str:
        """Dispatch /command [args] without going through the LLM."""
        # Implements FR-SEC-001, FR-SEC-003, FR-SEC-004
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

        # FR-RES: Research slash commands
        if verb == "/research":
            if not arg:
                return f"Usage: /research <topic>"
            from src.research import run_research
            result = run_research(arg, adversarial=False, check_conflicts=True)
            parts = [f"**Research: {result['topic']}**", f"_{result['budget']}_\n"]
            if result["synthesis"]:
                parts.append(result["synthesis"])
            if result["conflicts"]:
                parts.append(f"\n**Conflicts detected ({len(result['conflicts'])}):**")
                for c in result["conflicts"]:
                    parts.append(f"- {c['source']}: {c['verdict'][:120]}")
            return "\n".join(parts)

        if verb == "/adversarial":
            if not arg:
                return "Usage: /adversarial <claim to challenge>"
            from src.research import adversarial_review
            return adversarial_review(arg)

        available = "/authorize  /revoke  /registry  /audit  /review  /research  /adversarial"
        return f"[dim]{_FYI} — unknown command: {verb}\nAvailable: {available}[/dim]"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _record(self, response: str) -> str:
        """Append response to session history and persist."""
        self.session_history.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })
        self._persist_session()
        return response

    def _clean_history(self) -> list[dict]:
        """Strip timestamps for LLM calls."""
        return [{"role": m["role"], "content": m["content"]} for m in self.session_history[:-1]]

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


