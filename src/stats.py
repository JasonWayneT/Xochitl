"""Observability: usage stats, health checks, and help text."""

from pathlib import Path
from src import database as db
from src import memory as mem


def get_stats(days: int = 7) -> dict:
    with db.get_connection() as conn:
        token_stats = db.get_token_stats(conn, days)
        active_tasks = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status IN ('todo','in_progress')"
        ).fetchone()[0]
        active_projects = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE status='active'"
        ).fetchone()[0]

    return {
        "local_calls": token_stats.get("local_calls") or 0,
        "cloud_calls": token_stats.get("cloud_calls") or 0,
        "total_cost": token_stats.get("total_cost") or 0.0,
        "active_tasks": active_tasks,
        "active_projects": active_projects,
        "vector_memories": mem.vector_db_count(),
    }


def format_stats(days: int = 7) -> str:
    s = get_stats(days)
    return (
        f"\n  Xochitl Usage ({days}d)\n"
        f"  {'─' * 36}\n"
        f"  Local calls:     {s['local_calls']}\n"
        f"  Cloud calls:     {s['cloud_calls']}\n"
        f"  Cloud cost:      ${s['total_cost']:.4f}\n"
        f"  Active tasks:    {s['active_tasks']}\n"
        f"  Active projects: {s['active_projects']}\n"
        f"  Vector memories: {s['vector_memories']}\n"
    )


def health_check() -> dict:
    issues = []

    from src.llm_interface import ping_local
    local_ok = ping_local()
    if not local_ok:
        issues.append("Local Ollama model unreachable")

    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False
        issues.append("SQLite database error")

    vector_ok = mem._get_collection() is not None
    if not vector_ok:
        issues.append("ChromaDB unavailable")

    return {
        "local_model": local_ok,
        "database": db_ok,
        "vector_db": vector_ok,
        "healthy": len(issues) == 0,
        "issues": issues,
    }


def help_text(cwd: Path = None) -> str:
    from src.bmad import detect_bmad_project
    bmad = detect_bmad_project(cwd)

    base = """
  Xochitl Commands
  ────────────────────────────────────────

  Task Management
    xochitl today              Refresh daily queue (top 3 priority tasks)
    xochitl queue              Show current WIP tasks
    xochitl done <num>         Mark task complete, pull next into queue
    xochitl plan "<name>"      Decompose project into tasks via LLM

  Projects
    xochitl projects list      List all active projects
    xochitl projects add "<n>" Create a new local project
      --priority high|medium|low
      --description "<text>"
      --deadline YYYY-MM-DD

  Notion Sync
    xochitl pull               Fetch latest projects & tasks from Notion
    xochitl pull --decompose   Also LLM-decompose any new projects pulled
    xochitl sync               Push completed tasks to Notion

  Background Tasks (Orchestrator)
    xochitl tasks              List all delegated background task workspaces
    xochitl workspace <id>     Inspect progress of a delegated task

  Models
    xochitl models             Show active local/cloud models and server status

  Dashboard & Stats
    xochitl status             Progress dashboard (projects + queue)
    xochitl stats              Token usage and cost report (last 7 days)
    xochitl stats --days 30    Wider reporting window

  Export
    xochitl export             Save last chat session to markdown
    xochitl export --open      Save and open in default editor
    xochitl export --session N Export a specific session by ID

  Chat
    xochitl                    Start chat (default when no command given)
    xochitl chat               Start interactive chat session
    xochitl chat --cloud       Force all queries to cloud model
    xochitl chat --with-orchestrator  Launch background orchestrator on start

  ── In-Chat Phrases ──────────────────────────────────────────────────────────

  Files & Folders
    "read <file>"              Read a file and discuss its contents
    "list files in <path>"     Show directory tree
    "analyze the <folder> project"  Inspect a project folder structure
    "show me what's in <path>" Browse any folder you have access to

  Memory
    "remember that I prefer X" Save a preference to MEMORY.md
    "what did we discuss about Y?" Semantic recall from vector DB

  Projects (BMAD → SDD → Code pipeline)
    "I want to build a <name> app"   Start a new BMAD-SDD project
    "generate specs"                 Turn BMAD artifacts into requirements
    "list requirements"              Show all FR-* for the active project
    "scaffold the backend"           Generate code from specs
    "there's a bug where X"          Analyze issue against specs

  Notion
    "sync"  /  "pull from Notion"    Trigger sync inline
    "delegate it"                    Hand task to background orchestrator
"""

    if bmad:
        base += f"""
  ── BMAD Project Detected: {bmad['root'].name} ──────────────────────────────
    Modules:   {', '.join(bmad['modules'])}
    Workflows: {', '.join(bmad['workflows']) or 'none'}

    "help me plan a feature"    → Feature Planning (cloud)
    "design the architecture"   → Architecture Design (cloud)
    "create sprint stories"     → Sprint Planning (cloud)
    "review this code"          → Code Review (local→cloud)
    "start party mode"          → Multi-Agent (cloud, costs ~$0.50-2)
"""

    return base
