"""Entry point — routes all xochitl commands and the interactive chat loop."""
# Implements FR-ORCH-003 (Persistent Conversational Loop — `xochitl chat` spawns XochitlChat.start(), non-blocking)

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.spinner import SPINNERS

# Flower blooming sequence — dot → sparkle → bud → full bloom → bud → sparkle
SPINNERS["xochitl"] = {
    "interval": 50,
    "frames": [
        "·  ❁",
        "✦  ❀",
        "✽  ✿",
        "✿  ✽",
        "❀  ✦",
        "❁  ·",
        "❀  ✦",
        "✿  ✽",
        "✽  ✿",
        "✦  ❀",
    ],
}

console = Console()


def _json_mode(ctx) -> bool:
    return bool(getattr(ctx, "obj", None) and ctx.obj.get("json"))


def _emit_json(
    ctx,
    command: str,
    ok: bool,
    data: object = None,
    messages: list[dict[str, str]] | None = None,
) -> None:
    """Emit machine-readable CLI output (FR-UI-010 / CR-039)."""
    from src.terminal_output import cli_payload, print_json

    print_json(cli_payload(command, ok, data, messages))


XOCHITL_BANNER = "[bold cyan]Xochitl[/bold cyan] [dim]— Personal AI System[/dim]"


def _boot() -> None:
    """Initialize DB on first run."""
    from src.database import init_db
    init_db()


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable JSON output.")
@click.pass_context
def cli(ctx, as_json):
    """Xochitl — terminal-native personal AI system."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json
    _boot()
    if ctx.invoked_subcommand is None:
        # Default: launch chat
        ctx.invoke(chat)


# ── today ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def today(ctx):
    """Generate/refresh the daily queue (top 3 priority tasks)."""
    from src import task_manager

    added = task_manager.fill_queue()
    rows = task_manager.get_queue_display()
    if _json_mode(ctx):
        _emit_json(ctx, "today", True, {"queue": rows, "added_count": len(added)})
        return

    console.print(XOCHITL_BANNER)
    if not rows:
        console.print("[yellow]No eligible tasks. Add some with [bold]xochitl plan[/bold].[/yellow]")
        return

    console.print(Panel.fit("[bold]Today's Queue[/bold]", border_style="cyan"))
    for row in rows:
        rolled = f" [dim](rolled {row['days_rolled_over']}d)[/dim]" if row["days_rolled_over"] > 0 else ""
        console.print(
            f"  [[bold]{row['position']}[/bold]] {row['description']} "
            f"[dim]({row['time_estimate_minutes']}m | {row['project_name']})[/dim]{rolled}"
        )

    if added:
        console.print(f"\n[dim]Pulled {len(added)} new task(s) into queue.[/dim]")


# ── queue ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def queue(ctx):
    """Display current WIP tasks."""
    from src import task_manager

    rows = task_manager.get_queue_display()
    if _json_mode(ctx):
        _emit_json(ctx, "queue", True, {"queue": rows})
        return

    if not rows:
        console.print("[yellow]Queue is empty.[/yellow]")
        return

    console.print(Panel.fit("[bold]WIP Queue[/bold]", border_style="cyan"))
    for row in rows:
        rolled = f" [dim](rolled {row['days_rolled_over']}d)[/dim]" if row["days_rolled_over"] > 0 else ""
        console.print(
            f"  [[bold]{row['position']}[/bold]] {row['description']} "
            f"[dim]({row['time_estimate_minutes']}m | {row['project_name']})[/dim]{rolled}"
        )


# ── done ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("num", type=int)
@click.pass_context
def done(ctx, num):
    """Mark task NUM complete and pull the next task into queue."""
    from src import task_manager

    task = task_manager.mark_done(num)
    rows = task_manager.get_queue_display()
    if _json_mode(ctx):
        _emit_json(ctx, "done", task is not None, {"task": task, "queue": rows})
        return

    if not task:
        console.print(f"[red]No task at position {num}.[/red]")
        return

    console.print(f"[green]Done:[/green] {task['description']}")
    if rows:
        console.print("\n[dim]Updated queue:[/dim]")
        for row in rows:
            console.print(f"  [{row['position']}] {row['description']}")
    else:
        console.print("[dim]Queue is now empty.[/dim]")


# ── plan ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("project_name")
@click.pass_context
def plan(ctx, project_name):
    """Decompose a project into tasks via LLM (asks confirmation)."""
    from src import task_manager, database as db
    from src.llm_interface import call_local, call_cloud, DECOMPOSE_PROMPT
    from src.context_loader import build_decompose_context

    if _json_mode(ctx):
        _emit_json(
            ctx,
            "plan",
            False,
            {"error": "interactive_only"},
            [{"status": "warn", "text": "plan requires prompts; run without --json"}],
        )
        return

    console.print(XOCHITL_BANNER)

    # Find project
    with db.get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE name LIKE ?", (f"%{project_name}%",)
        ).fetchall()

    if not rows:
        console.print(f"[red]No project found matching '{project_name}'.[/red]")
        console.print("[dim]Create one with: xochitl projects add \"<name>\"[/dim]")
        return

    if len(rows) > 1:
        console.print("[yellow]Multiple matches:[/yellow]")
        for i, r in enumerate(rows):
            console.print(f"  [{i}] {r['name']}")
        idx = int(Prompt.ask("Which project?", default="0"))
        project = dict(rows[idx])
    else:
        project = dict(rows[0])

    console.print(f"\nDecomposing [bold]{project['name']}[/bold]...")

    global_ctx, project_ctx = build_decompose_context(project["name"])
    prompt = DECOMPOSE_PROMPT.format(
        project_name=project["name"],
        project_description=project.get("description") or "",
        project_priority=project["priority"],
        global_context=global_ctx,
        project_context=project_ctx,
    )

    # Try local first, fall back to cloud
    result = call_local(messages=[{"role": "user", "content": prompt}])
    if result.error or not result.content.strip().startswith("["):
        console.print("[dim]Local model insufficient, routing to cloud...[/dim]")
        result = call_cloud(messages=[{"role": "user", "content": prompt}])

    if result.error:
        console.print(f"[red]LLM error: {result.error}[/red]")
        return

    try:
        raw = result.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        tasks = json.loads(raw)
    except Exception as e:
        console.print(f"[red]Failed to parse LLM response: {e}[/red]")
        console.print(result.content[:500])
        return

    console.print(f"\n[bold]Proposed tasks ({len(tasks)}):[/bold]")
    for i, t in enumerate(tasks):
        console.print(f"  [{i+1}] {t['description']} ({t.get('time_estimate_minutes', 30)}m)")

    confirm = Prompt.ask("\nSave these tasks?", choices=["yes", "no"], default="yes")
    if confirm != "yes":
        console.print("[dim]Cancelled.[/dim]")
        return

    ids = task_manager.create_tasks_bulk(project["id"], tasks)
    console.print(f"[green]Created {len(ids)} tasks.[/green]")
    console.print("[dim]Run 'xochitl today' to load them into your queue.[/dim]")


# ── sync ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def sync(ctx):
    """Push completed tasks to Notion; handles rollover prompts."""
    from src import task_manager, notion_sync

    warnings = task_manager.run_daily_rollover()
    if _json_mode(ctx):
        for task in warnings:
            task_manager.handle_rollover_task(task["id"], "keep")
        try:
            result = notion_sync.sync_completed_to_notion()
            _emit_json(ctx, "sync", True, {"rollovers": warnings, "notion": result})
        except RuntimeError as exc:
            _emit_json(ctx, "sync", False, {"error": str(exc), "rollovers": warnings})
        return

    console.print(XOCHITL_BANNER)

    if warnings:
        console.print(f"\n[yellow]Rollover warning — {len(warnings)} tasks stuck 3+ days:[/yellow]")
        for task in warnings:
            console.print(f"  • {task['description']}")
            action = Prompt.ask(
                "  Action?", choices=["keep", "delete", "reschedule"], default="keep"
            )
            task_manager.handle_rollover_task(task["id"], action)

    # Push to Notion
    console.print("\nPushing completed tasks to Notion...")
    try:
        result = notion_sync.sync_completed_to_notion()
        console.print(f"[green]Pushed {result['pushed']} tasks to Notion.[/green]")
    except RuntimeError as e:
        console.print(f"[yellow]Notion unavailable: {e}[/yellow]")
        console.print("[dim]Tasks queued locally. Will sync when Notion is available.[/dim]")


# ── pull ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--decompose", is_flag=True, help="Decompose new projects via LLM after pulling.")
@click.pass_context
def pull(ctx, decompose):
    """Fetch latest projects from Notion; optionally decompose new ones."""
    from src import notion_sync, task_manager, database as db

    if _json_mode(ctx):

        def _json_conflict(_notion_project, _local_row):
            return "keep"

        try:
            result = notion_sync.pull_and_sync(on_conflict=_json_conflict)
            _emit_json(ctx, "pull", True, {"result": result, "decompose_requested": decompose})
        except RuntimeError as exc:
            _emit_json(ctx, "pull", False, {"error": str(exc)})
        return

    console.print(XOCHITL_BANNER)

    def on_conflict(notion_project, local_row):
        console.print(f"\n[yellow]Conflict for '{notion_project['name']}'[/yellow]")
        console.print(f"  Notion: {notion_project.get('description', '')[:80]}")
        console.print(f"  Local:  {local_row.get('description', '')[:80]}")
        return Prompt.ask("  Decision?", choices=["pull", "keep", "merge"], default="keep")

    try:
        result = notion_sync.pull_and_sync(on_conflict=on_conflict)
        console.print(
            f"[green]Pulled:[/green] "
            f"{result['projects']} projects, "
            f"{result['areas']} areas, "
            f"{result['resources']} resources. "
            f"Conflicts: {result['conflicts']}."
        )
    except RuntimeError as e:
        console.print(f"[red]Notion error: {e}[/red]")
        return

    if decompose:
        with db.get_connection() as conn:
            new_projects = db.get_active_projects(conn)
        for proj in new_projects:
            if Prompt.ask(f"Decompose '{proj['name']}'?", choices=["yes", "no"], default="no") == "yes":
                from click import get_current_context
                ctx = get_current_context()
                ctx.invoke(plan, project_name=proj["name"])


# ── status ────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def status(ctx):
    """Overall progress dashboard."""
    from src import database as db

    with db.get_connection() as conn:
        projects = db.get_active_projects(conn)
        queue_rows = db.get_queue(conn)

    project_stats: list[dict] = []
    for p in projects:
        with db.get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE project_id=?", (p["id"],)
            ).fetchone()[0]
            done_count = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='done'", (p["id"],)
            ).fetchone()[0]
        pct = int(done_count / total * 100) if total else 0
        project_stats.append({
            "id": p["id"],
            "name": p["name"],
            "priority": p["priority"],
            "total_tasks": total,
            "done_tasks": done_count,
            "percent_done": pct,
        })

    if _json_mode(ctx):
        _emit_json(ctx, "status", True, {
            "projects": project_stats,
            "queue": [dict(row) for row in queue_rows],
        })
        return

    console.print(Panel.fit(XOCHITL_BANNER, border_style="cyan"))

    console.print("\n[bold]Active Projects[/bold]")
    for row in project_stats:
        pct = row["percent_done"]
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        console.print(
            f"  [{row['priority'].upper():6}] {row['name']:<30} {bar} {pct:3}% "
            f"({row['done_tasks']}/{row['total_tasks']})"
        )

    if queue_rows:
        console.print("\n[bold]Current Queue[/bold]")
        for row in queue_rows:
            console.print(f"  [{row['position']}] {row['description']}")


# ── stats ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--days", default=7, show_default=True, help="Number of days to report on.")
@click.pass_context
def stats(ctx, days):
    """Token usage and cost report."""
    from src.stats import format_stats, get_stats

    if _json_mode(ctx):
        _emit_json(ctx, "stats", True, get_stats(days))
        return
    console.print(format_stats(days))


# ── export ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--session", default=None, type=int, help="Session ID to export (default: last session).")
@click.option("--open", "open_file", is_flag=True, help="Open the exported file after saving.")
@click.pass_context
def export(ctx, session, open_file):
    """Export the current chat session to a formatted markdown file."""
    import json as _json
    from datetime import datetime
    from pathlib import Path
    from src import database as db

    with db.get_connection() as conn:
        if session:
            row = db.get_session(conn, session)
        else:
            row = conn.execute(
                "SELECT * FROM sessions ORDER BY last_active DESC LIMIT 1"
            ).fetchone()

    if not row:
        if _json_mode(ctx):
            _emit_json(ctx, "export", False, {"error": "no_session"})
        else:
            console.print("[yellow]No session found.[/yellow]")
        return

    try:
        messages = _json.loads(row["conversation_json"])
    except Exception:
        if _json_mode(ctx):
            _emit_json(ctx, "export", False, {"error": "parse_failed"})
        else:
            console.print("[red]Could not parse session data.[/red]")
        return

    if not messages:
        if _json_mode(ctx):
            _emit_json(ctx, "export", False, {"error": "empty_session"})
        else:
            console.print("[yellow]Session is empty.[/yellow]")
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    export_dir = Path(__file__).parent.parent / "data" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / f"session_{timestamp}.md"

    lines = [f"# Xochitl Session — {datetime.now().strftime('%B %d, %Y')}\n"]
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "").strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"---\n\n**You:** {content}\n")
        elif role == "assistant":
            lines.append(f"**Xochitl:**\n\n{content}\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    if _json_mode(ctx):
        _emit_json(ctx, "export", True, {"path": str(out_path), "message_count": len(messages)})
        return

    console.print(f"[green]Exported:[/green] {out_path}")

    if open_file:
        import subprocess, sys
        if sys.platform == "win32":
            subprocess.Popen(["start", "", str(out_path)], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(out_path)])
        else:
            subprocess.Popen(["xdg-open", str(out_path)])


# ── projects subgroup ─────────────────────────────────────────────────────────

@cli.group()
def projects():
    """Manage local projects."""
    pass


@projects.command("add")
@click.argument("name")
@click.option("--priority", type=click.Choice(["high", "medium", "low"]), default="medium")
@click.option("--description", default="")
@click.option("--deadline", default=None)
@click.pass_context
def projects_add(ctx, name, priority, description, deadline):
    """Create a new local project."""
    from src import task_manager
    pid = task_manager.create_project(name, priority, description, deadline)
    if _json_mode(ctx):
        _emit_json(ctx, "projects-add", True, {"project_id": pid, "name": name})
        return
    console.print(f"[green]Project created:[/green] {name} ({pid})")


@projects.command("list")
@click.pass_context
def projects_list(ctx):
    """List all active projects."""
    from src import task_manager
    projs = task_manager.list_projects()
    if _json_mode(ctx):
        _emit_json(ctx, "projects-list", True, {"projects": projs})
        return
    if not projs:
        console.print("[yellow]No projects.[/yellow]")
        return
    for p in projs:
        console.print(f"  [{p['priority'].upper()}] {p['name']} — {p.get('description','')[:60]}")


# ── secrets ───────────────────────────────────────────────────────────────────

@cli.group()
def secrets():
    """Manage secrets stored in the local DB (API keys, tokens, config)."""
    pass


@secrets.command("set")
@click.argument("key")
@click.argument("value")
def secrets_set(key, value):
    """Store a secret: xochitl secrets set KEY VALUE"""
    from src.secrets import set_secret
    set_secret(key, value)
    console.print(f"[green]Set:[/green] {key}")


@secrets.command("get")
@click.argument("key")
def secrets_get(key):
    """Print the value of a stored secret."""
    from src.secrets import get_secret
    val = get_secret(key)
    if val:
        console.print(val)
    else:
        console.print(f"[yellow]No secret found for '{key}'.[/yellow]")


@secrets.command("list")
def secrets_list():
    """List all stored secret keys (values are hidden)."""
    from src.secrets import list_secrets
    rows = list_secrets()
    if not rows:
        console.print("[yellow]No secrets stored. Run 'xochitl secrets migrate' to import from .env[/yellow]")
        return
    console.print(Panel.fit("[bold]Stored Secrets[/bold]", border_style="cyan"))
    for r in rows:
        console.print(f"  {r['key']:<35} [dim]updated {r['updated_at']}[/dim]")


@secrets.command("delete")
@click.argument("key")
def secrets_delete(key):
    """Remove a secret from the DB."""
    from src.secrets import delete_secret
    if delete_secret(key):
        console.print(f"[green]Deleted:[/green] {key}")
    else:
        console.print(f"[yellow]Not found:[/yellow] {key}")


@secrets.command("migrate")
@click.option("--env-file", default=".env", show_default=True, help="Path to .env file to import.")
def secrets_migrate(env_file):
    """Import all KEY=VALUE pairs from a .env file into the DB."""
    from pathlib import Path
    from src.secrets import migrate_from_env
    path = Path(env_file)
    migrated = migrate_from_env(path)
    if not migrated:
        console.print(f"[yellow]Nothing imported — '{env_file}' not found or empty.[/yellow]")
        return
    console.print(f"[green]Migrated {len(migrated)} secrets from {env_file}:[/green]")
    for k in migrated:
        console.print(f"  {k}")
    console.print("\n[dim]You can now delete your .env file — secrets live in the DB.[/dim]")


# ── models ───────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def models(ctx):
    """List available local models and show current config."""
    from src.llm_interface import (
        list_local_models, ping_local, ping_lmstudio, ping_ollama,
        LOCAL_PROVIDER, LOCAL_MODEL, LM_STUDIO_URL, OLLAMA_URL,
        CLOUD_PROVIDER, CLOUD_MODEL,
    )

    if LOCAL_PROVIDER == "lmstudio":
        ok = ping_lmstudio()
    else:
        ok = ping_ollama()
    found = list_local_models() if ok else []

    if _json_mode(ctx):
        _emit_json(ctx, "models", True, {
            "local_provider": LOCAL_PROVIDER,
            "local_model": LOCAL_MODEL,
            "local_online": ok,
            "local_models": found,
            "cloud_provider": CLOUD_PROVIDER,
            "cloud_model": CLOUD_MODEL,
        })
        return

    console.print(Panel.fit("[bold]Model Configuration[/bold]", border_style="cyan"))

    console.print(f"\n[bold]Local provider:[/bold] {LOCAL_PROVIDER}")
    if LOCAL_PROVIDER == "lmstudio":
        console.print(f"  Server: {LM_STUDIO_URL}")
        status = "[green]online[/green]" if ok else "[red]offline[/red] — is LM Studio's local server running?"
        console.print(f"  Status: {status}")
    else:
        console.print(f"  Server: {OLLAMA_URL}")
        status = "[green]online[/green]" if ok else "[red]offline[/red] — is Ollama running?"
        console.print(f"  Status: {status}")

    if ok:
        if found:
            console.print(f"\n  [bold]Available models:[/bold]")
            for m in found:
                marker = " [cyan]<-- active[/cyan]" if LOCAL_MODEL and m == LOCAL_MODEL else ""
                console.print(f"    {m}{marker}")
            if not LOCAL_MODEL:
                console.print(f"\n  [yellow]LOCAL_MODEL not set — will auto-use: {found[0]}[/yellow]")
                console.print(f"  [dim]Run: xochitl secrets set LOCAL_MODEL {found[0]}[/dim]")
        else:
            console.print("  [yellow]No models found. Load a model in LM Studio first.[/yellow]")

    console.print(f"\n[bold]Cloud provider:[/bold] {CLOUD_PROVIDER}  model: {CLOUD_MODEL}")


# ── chat ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--cloud", is_flag=True, help="Force all queries to cloud model.")
@click.option("--with-orchestrator", "with_orchestrator", is_flag=True,
              help="Start background orchestrator on launch.")
@click.option("--no-rich", "no_rich", is_flag=True,
              help="Disable Rich markup (plain text output — useful for TERM=dumb or screen readers).")
@click.pass_context
def chat(ctx, cloud, with_orchestrator, no_rich):
    """Interactive conversational session with Xochitl."""
    if _json_mode(ctx):
        _emit_json(
            ctx,
            "chat",
            False,
            {"error": "interactive_only"},
            [{"status": "warn", "text": "chat is interactive; run without --json"}],
        )
        return
    # Implements FR-UX-001 (--no-rich flag, TERM=dumb fallback)
    from src.chat import XochitlChat
    XochitlChat(force_cloud=cloud, with_orchestrator=with_orchestrator, no_rich=no_rich).start()


# ── tasks ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.pass_context
def tasks(ctx):
    """List active background tasks managed by the orchestrator."""
    from src.skills.orchestrator_skill import _WORKSPACE_ROOT

    entries: list[dict] = []
    if _WORKSPACE_ROOT.exists():
        for ws in sorted(p for p in _WORKSPACE_ROOT.iterdir() if p.is_dir()):
            progress_file = ws / "task-artifacts" / "progress.json"
            entry = {"workspace": ws.name, "path": str(ws)}
            if progress_file.exists():
                try:
                    progress = json.loads(progress_file.read_text(encoding="utf-8"))
                    entry.update({
                        "state": progress.get("state", "unknown"),
                        "description": progress.get("description", ws.name),
                        "completed_steps": len(progress.get("completed_steps", [])),
                        "next_steps": len(progress.get("next_steps", [])),
                    })
                except Exception:
                    entry["state"] = "unreadable"
            entries.append(entry)

    if _json_mode(ctx):
        _emit_json(ctx, "tasks", True, {"workspaces": entries})
        return

    console.print(Panel.fit("[bold]Background Tasks[/bold]", border_style="cyan"))

    if not entries:
        console.print("[dim]No active workspaces.[/dim]")
        return

    for entry in entries:
        ws_name = entry["workspace"]
        state = entry.get("state")
        if state and state != "unreadable":
            done = entry.get("completed_steps", 0)
            total = done + entry.get("next_steps", 0)
            pct = int(done / max(total, 1) * 100)
            console.print(f"  [bold]{ws_name}[/bold] — {state} ({pct}%)")
            console.print(f"    {entry.get('description', ws_name)}")
        else:
            console.print(f"  [bold]{ws_name}[/bold]")


# ── workspace ─────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("task_id")
@click.pass_context
def workspace(ctx, task_id):
    """Jump into a delegated task workspace."""
    from src.skills.orchestrator_skill import _WORKSPACE_ROOT

    ws = _WORKSPACE_ROOT / f"task-{task_id}"
    if not ws.exists():
        # Try matching by partial name
        matches = [p for p in _WORKSPACE_ROOT.iterdir() if task_id in p.name] if _WORKSPACE_ROOT.exists() else []
        if not matches:
            if _json_mode(ctx):
                _emit_json(ctx, "workspace", False, {"error": "not_found", "task_id": task_id})
            else:
                console.print(f"[red]No workspace found for task '{task_id}'.[/red]")
                console.print("[dim]Use 'xochitl tasks' to see active workspaces.[/dim]")
            return
        ws = matches[0]

    progress_data: dict = {"path": str(ws)}
    progress_file = ws / "task-artifacts" / "progress.json"
    if progress_file.exists():
        try:
            progress_data["progress"] = json.loads(progress_file.read_text(encoding="utf-8"))
        except Exception as exc:
            progress_data["progress_error"] = str(exc)

    if _json_mode(ctx):
        _emit_json(ctx, "workspace", True, progress_data)
        return

    console.print(f"[green]Workspace:[/green] {ws}")
    console.print(f"[dim]cd \"{ws}\"[/dim]")

    if progress_file.exists():
        try:
            progress = progress_data.get("progress") or json.loads(progress_file.read_text(encoding="utf-8"))
            console.print(f"\n[bold]State:[/bold] {progress.get('state', 'unknown')}")
            completed = progress.get("completed_steps", [])
            if completed:
                console.print("\n[bold]Completed:[/bold]")
                for step in completed:
                    console.print(f"  ✓ {step}")
            next_steps = progress.get("next_steps", [])
            if next_steps:
                console.print("\n[bold]Next steps:[/bold]")
                for step in next_steps:
                    console.print(f"  • {step}")
        except Exception:
            pass


def _handle_tool_calls(content: str) -> str:
    """Extract and dispatch any tool calls embedded in the LLM response."""
    import json as _json
    from src.tools import dispatch

    results = []
    try:
        data = _json.loads(content)
    except Exception:
        return content

    # Ollama tool_calls format
    if "tool_calls" in data:
        for call in data["tool_calls"]:
            fn = call.get("function", {})
            name = fn.get("name")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = _json.loads(args)
                except Exception:
                    args = {}
            result = dispatch(name, args)
            results.append(f"**{name}**\n{result}")
        return "\n\n".join(results)

    # Anthropic tool_use format
    if "tool_use" in data:
        tu = data["tool_use"]
        result = dispatch(tu["name"], tu.get("input", {}))
        return f"**{tu['name']}**\n{result}"

    return content


if __name__ == "__main__":
    cli()
