"""Slash command dispatch — decoupled from XochitlChat via SlashContext.

Separates the slash command routing table from the session lifecycle. Handlers
receive a ``SlashContext`` (a plain data object) rather than a reference to the
full chat session, so this module has no runtime dependency on ``XochitlChat``
and its internal attribute layout (TASK-DEV-051-b).

Implements FR-SEC-001, FR-SEC-003, FR-SEC-004, FR-ORCH-041, FR-CONV-003.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from src.constants import _FYI, _SKILL_INJECT_THRESHOLD, _OPEN_ENDED_SCORE_THRESHOLD


@dataclass
class SlashContext:
    """The session state a slash command may read or write.

    Built by XochitlChat and passed to ``handle_slash_command``. The two scalar
    fields ``staged_message`` and ``last_cancelled`` are mutated by /next and
    /retry; the caller reads them back after dispatch to apply the changes.

    Attributes:
        staged_message: Message queued to run after the current response (mutable).
        last_cancelled: Last cancelled message, resendable via /retry (mutable).
        current_project: Active project ID, or None.
        router: TieredRouter for /plan.
        governor: SessionGovernor for /budget and /status.
        context: Mutable session context dict.
        session_history: Mutable session history list.
        skills: Live skill list.
        last_user_message: Callable returning the most recent user message text.
        initiative: Optional InitiativeEngine (for /dismiss and /status).
        background_review: Optional BackgroundReview daemon (for /status).
    """
    staged_message: Optional[str]
    last_cancelled: Optional[str]
    current_project: Optional[str]
    router: Any
    governor: Any
    context: dict
    session_history: list
    skills: list
    last_user_message: Callable[[], str]
    initiative: Any = None
    background_review: Any = None


def handle_slash_command(raw: str, ctx: SlashContext) -> str:
    """Dispatch a /command [args] string without going through the LLM.

    Args:
        raw: Raw slash command string from the user (e.g. "/budget").
        ctx: Session state the command may read/write.

    Returns:
        Formatted response string for console display.
    """
    from src.security import cmd_authorize, cmd_revoke, cmd_list_registry, cmd_audit

    parts = raw.split(maxsplit=1)
    verb = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # ── Staged / retry messages ───────────────────────────────────────────────
    if verb == "/next":
        if not arg:
            if ctx.staged_message:
                ctx.staged_message = None
                return "[dim]Staged message cleared.[/dim]"
            return "Usage: /next <message to send after this response>"
        ctx.staged_message = arg
        return f"[dim]✓ Staged: '{arg}' — will run after current response.[/dim]"

    if verb == "/retry":
        if not ctx.last_cancelled:
            return "[dim]Nothing to retry — no message was cancelled.[/dim]"
        ctx.staged_message = ctx.last_cancelled
        ctx.last_cancelled = None
        return f"[dim]✓ Re-queued: '{ctx.staged_message}'[/dim]"

    # ── Security commands ─────────────────────────────────────────────────────
    if verb == "/authorize":
        return cmd_authorize(arg)
    if verb == "/revoke":
        return cmd_revoke(arg)
    if verb == "/registry":
        return cmd_list_registry()
    if verb == "/audit":
        n = int(arg) if arg.isdigit() else 20
        return cmd_audit(n)

    # ── SDD traceability review ───────────────────────────────────────────────
    if verb == "/review":
        from src.skills.sdd_skill import SDDSkill
        project_id = arg or ctx.current_project or ""
        return SDDSkill().review_code_traceability(project_id)

    # ── Research commands ─────────────────────────────────────────────────────
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

    # ── Plan-first mode (FR-ORCH-044, CR-052) ─────────────────────────────────
    if verb == "/plan":
        if not arg:
            return "Usage: /plan <task to plan> — generates a numbered plan; runs nothing."
        from src.planning import generate_plan
        return generate_plan(arg, ctx.router)

    # ── Project index (FR-MEM-016, CR-052) ────────────────────────────────────
    if verb == "/index":
        from pathlib import Path as _P
        from src.project_index import index_project, format_index_result
        try:
            from src.memory import VectorMemory
            mem = VectorMemory()
        except Exception as exc:
            return f"[dim]{_FYI} — vector memory unavailable: {exc}[/dim]"
        root = _P(arg).expanduser() if arg else _P.cwd()
        if not root.is_dir():
            return f"[dim]{_FYI} — not a directory: {root}[/dim]"
        indexed, scanned, capped = index_project(root, mem, project=ctx.current_project)
        return format_index_result(indexed, scanned, capped)

    # ── Session budget ────────────────────────────────────────────────────────
    if verb == "/budget":
        return ctx.governor.budget_detail()

    # ── System status ─────────────────────────────────────────────────────────
    if verb == "/status":
        return _handle_status(ctx)

    # ── Session history ───────────────────────────────────────────────────────
    if verb == "/history":
        return _handle_history(ctx, int(arg) if arg.isdigit() else 5)

    # ── Initiative dismiss ────────────────────────────────────────────────────
    if verb == "/dismiss":
        try:
            from src.initiative import InitiativeCategory
            engine = ctx.initiative
            if engine is None:
                return "[dim]Initiative engine not active.[/dim]"
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

    # ── Workflow commands ─────────────────────────────────────────────────────
    if verb == "/workflows":
        from src.workflows import list_workflows_formatted
        return list_workflows_formatted(project=ctx.current_project)

    if verb == "/workflow":
        return _handle_workflow(ctx, arg)

    # ── Daily brief ───────────────────────────────────────────────────────────
    if verb == "/brief":
        try:
            from src.brief import build_structured_brief
            from src import database as _db
            with _db.get_connection() as conn:
                _queue = _db.get_queue(conn)
            return build_structured_brief(_queue, notion_pending=[])
        except Exception as exc:
            return f"[dim]{_FYI} — couldn't build brief: {exc}[/dim]"

    # ── Debug: skill scoring ──────────────────────────────────────────────────
    if verb == "/debug" and arg.lower().startswith("skill"):
        return _handle_debug_skill(ctx)

    available = (
        "/next <msg>  /retry  /authorize  /revoke  "
        "/registry  /audit  /review  /research  /adversarial  "
        "/plan <task>  /index [dir]  /budget  /status  /history [N]  /brief  "
        "/dismiss  /workflows  /workflow save <name>  /workflow run <name>  "
        "/debug skill"
    )
    return f"[dim]{_FYI} — unknown command: {verb}\nAvailable: {available}[/dim]"


# ── Sub-handlers ──────────────────────────────────────────────────────────────

def _handle_workflow(ctx: SlashContext, arg: str) -> str:
    from src.workflows import (
        execute_workflow,
        get_workflow_by_name,
        list_workflows_formatted,
        save_workflow_from_session,
    )
    if not arg:
        return (
            "Usage: /workflow save <name>  |  /workflow run <name>  |  /workflows\n"
            + list_workflows_formatted(project=ctx.current_project)
        )
    if arg.lower().startswith("save "):
        wf_name = arg[5:].strip()
        if not wf_name:
            return "Usage: /workflow save <name>"
        trigger = ctx.last_user_message() or wf_name
        try:
            wf_id = save_workflow_from_session(
                wf_name,
                trigger[:240],
                ctx.session_history,
                project=ctx.current_project,
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
        ctx.context["_chat_skills"] = ctx.skills
        return execute_workflow(
            wf,
            ctx.last_user_message() or wf_name,
            ctx.skills,
            ctx.context,
        )
    return "[dim]Unknown /workflow subcommand. Use: save or run[/dim]"


def _handle_status(ctx: SlashContext) -> str:
    """Return a system health table for /status. Implements FR-JARV-011."""
    from src import database as _db

    lines = ["[bold]System Status[/bold]", ""]

    try:
        from src.stats import health_check
        health = health_check()
        local_ok = health.get("local_model", False)
        lines.append(f"  Local model   : {'[green]online[/green]' if local_ok else '[red]offline[/red]'}")
    except Exception:
        lines.append("  Local model   : [dim]unknown[/dim]")

    cloud_ok = bool(
        os.getenv("ANTHROPIC_API_KEY") or
        os.getenv("GOOGLE_API_KEY") or
        os.getenv("GEMINI_API_KEY")
    )
    lines.append(f"  Cloud route   : {'[green]available[/green]' if cloud_ok else '[dim]no key set[/dim]'}")

    notion_ok = bool(os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY"))
    lines.append(f"  Notion        : {'[green]token set[/green]' if notion_ok else '[dim]no token[/dim]'}")

    gmail_path = Path.home() / ".xochitl" / "gmail_token.json"
    lines.append(f"  Gmail         : {'[green]token found[/green]' if gmail_path.exists() else '[dim]not configured[/dim]'}")
    lines.append(f"  Budget        : {ctx.governor.status_line()}")

    try:
        with _db.get_connection() as _conn:
            _q = _db.get_queue(_conn)
        lines.append(f"  WIP Queue     : {len(_q)}/3 items")
    except Exception:
        lines.append("  WIP Queue     : [dim]unavailable[/dim]")

    try:
        with _db.get_connection() as _conn:
            _mf_count = _conn.execute("SELECT COUNT(*) FROM memory_facts").fetchone()[0]
            _wf_count = _conn.execute(
                "SELECT COUNT(*) FROM workflows WHERE superseded_by IS NULL"
            ).fetchone()[0]
        lines.append(f"  Memory facts  : {_mf_count} rows")
        lines.append(f"  Workflows     : {_wf_count} saved")
    except Exception:
        lines.append("  Memory facts  : [dim]unavailable[/dim]")

    _br = ctx.background_review
    _br_status = "[green]active[/green]" if (_br and _br.is_alive()) else "[yellow]stopped[/yellow]"
    lines.append(f"  Background    : {_br_status}")

    try:
        _ini = ctx.initiative
        if _ini is not None:
            lines.append(f"  Initiative    : {_ini.mode.value}")
        else:
            lines.append("  Initiative    : [dim]not loaded[/dim]")
    except Exception:
        lines.append("  Initiative    : [dim]unknown[/dim]")

    lines.append("")
    lines.append("[dim]Use /budget for full token breakdown.[/dim]")
    return "\n".join(lines)


def _handle_history(ctx: SlashContext, n: int) -> str:
    """Return a table of recent session context summaries. FR-HARD-008."""
    from src import database as _db

    try:
        with _db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, started_at, last_active, context_summary "
                "FROM sessions WHERE context_summary IS NOT NULL "
                "AND context_summary != '' "
                "ORDER BY id DESC LIMIT ?",
                (n,),
            ).fetchall()
    except Exception as exc:
        return f"[dim]Could not load session history: {exc}[/dim]"

    if not rows:
        return "[dim]No session history yet — context summaries are saved as you chat.[/dim]"

    lines = [f"[bold]Last {min(n, len(rows))} sessions[/bold]", ""]
    for row in rows:
        started = str(row[1] or "")[:16]
        summary = (str(row[3] or ""))[:90]
        lines.append(f"  [dim]{started}[/dim]  {summary}")
    lines.append("")
    lines.append("[dim]Tip: /history 10 shows the last 10 sessions.[/dim]")
    return "\n".join(lines)


def _handle_debug_skill(ctx: SlashContext) -> str:
    """Show per-skill can_handle() scores for the last user message. AC-CR047-006."""
    last_input = ctx.context.get("_last_debug_input", "")
    if not last_input:
        for msg in reversed(ctx.session_history):
            if msg.get("role") == "user":
                last_input = msg.get("content", "")
                break
    if not last_input:
        return "[dim]No recent message to score against — say something first.[/dim]"

    lines = [f"[bold]can_handle scores[/bold] for: {last_input[:80]}"]
    rows = []
    for skill in ctx.skills:
        try:
            score = skill.can_handle(last_input, ctx.context)
        except Exception:
            score = -1.0
        name = type(skill).__name__
        marker = " ← injected" if score >= _SKILL_INJECT_THRESHOLD else (
            " ← near-miss" if score >= _OPEN_ENDED_SCORE_THRESHOLD else ""
        )
        rows.append((score, f"  {score:.2f}  {name}{marker}"))
    rows.sort(key=lambda r: r[0], reverse=True)
    lines.extend(r[1] for r in rows)
    lines.append(
        f"\n  inject threshold: {_SKILL_INJECT_THRESHOLD}  "
        f"near-miss threshold: {_OPEN_ENDED_SCORE_THRESHOLD}"
    )
    return "\n".join(lines)
