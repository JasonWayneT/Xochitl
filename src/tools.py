"""Tool registry — all callable tools exposed to the LLM and CLI."""

import json
from pathlib import Path
from typing import Optional

from src import task_manager, database as db
from src import memory as mem
from src import security
from src import notion_sync
from src import bmad as bmad_module


# ── Tool definitions (for Ollama/Anthropic tool-use API) ─────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_queue",
        "description": "Show the current WIP task queue (up to 3 tasks).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "mark_task_done",
        "description": "Mark the task at a queue position as done and pull in the next task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "position": {"type": "integer", "description": "Queue position 1, 2, or 3"}
            },
            "required": ["position"],
        },
    },
    {
        "name": "add_task",
        "description": "Create a new task for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "description": {"type": "string"},
                "time_estimate_minutes": {"type": "integer", "enum": [30, 60]},
            },
            "required": ["project_id", "description"],
        },
    },
    {
        "name": "list_projects",
        "description": "List all active projects with priority and status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "update_core_memory",
        "description": "Update a section of MEMORY.md with new content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {"type": "string", "description": "Section header in MEMORY.md"},
                "content": {"type": "string", "description": "New content for the section"},
            },
            "required": ["section", "content"],
        },
    },
    {
        "name": "memorize",
        "description": "Save a memory to the long-term vector database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "summary": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "project": {"type": "string"},
            },
            "required": ["topic", "summary"],
        },
    },
    {
        "name": "recall",
        "description": "Semantic search over long-term memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "project": {"type": "string"},
                "n_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Read a file from the filesystem (sandboxed).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file (requires confirmation if file exists).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List contents of a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "save_artifact",
        "description": "Save a generated artifact (PRD, architecture doc, etc.) to the correct BMAD folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "artifact_type": {
                    "type": "string",
                    "enum": ["planning", "implementation", "architecture", "tests", "docs", "sprint", "ux", "prd"],
                },
                "filename": {"type": "string"},
            },
            "required": ["content", "artifact_type"],
        },
    },
    {
        "name": "sync_notion",
        "description": "Pull latest projects from Notion into local database.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "push_to_notion",
        "description": "Push locally completed tasks to Notion.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "xochitl_help",
        "description": "Show Xochitl capabilities and available commands.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # ── Phase 1: Project init & BMAD artifacts ────────────────────────────────
    {
        "name": "init_project",
        "description": "Initialize a new BMAD-SDD project with directory structure and metadata.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "kebab-case identifier, e.g. diet-tracker"},
                "name": {"type": "string", "description": "Human-readable project name"},
                "description": {"type": "string", "description": "Brief description"},
            },
            "required": ["project_id", "name"],
        },
    },
    {
        "name": "save_bmad_artifact",
        "description": "Save a BMAD artifact (business-model, architecture, design-specs, or constraints) for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "artifact_type": {
                    "type": "string",
                    "enum": ["business-model", "architecture", "design-specs", "constraints"],
                },
                "content": {"type": "string", "description": "Full markdown content of the artifact"},
            },
            "required": ["project_id", "artifact_type", "content"],
        },
    },
    {
        "name": "list_projects_sdd",
        "description": "List all SDD projects managed by Xochitl.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # ── Phase 2: SDD spec generation & requirement CRUD ───────────────────────
    {
        "name": "generate_specs",
        "description": "Generate SDD requirements from completed BMAD artifacts for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "list_requirements",
        "description": "List all FR-* requirements for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "get_requirement",
        "description": "Get full details of a specific requirement by ID (e.g. FR-CORE-001).",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "requirement_id": {"type": "string"},
            },
            "required": ["project_id", "requirement_id"],
        },
    },
    {
        "name": "create_requirement",
        "description": "Create a new requirement in a project's spec file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "req_type": {"type": "string", "description": "Area code: CORE, API, UI, DATA, AUTH"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
            },
            "required": ["project_id", "title", "description"],
        },
    },
    # ── Phase 3: Issue tracking & requirement updates ─────────────────────────
    {
        "name": "create_issue",
        "description": "Create a bug or feature issue for a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "issue_type": {"type": "string", "enum": ["bug", "feature", "enhancement"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["project_id", "title", "description"],
        },
    },
    {
        "name": "analyze_issue",
        "description": "Analyze a bug or issue description against project specs to identify spec gaps or implementation bugs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "issue_id_or_description": {"type": "string", "description": "BUG-NNN or free-text description"},
            },
            "required": ["project_id", "issue_id_or_description"],
        },
    },
    {
        "name": "update_requirement",
        "description": "Update fields of an existing requirement (status, priority, description, add acceptance criterion).",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "requirement_id": {"type": "string"},
                "updates": {
                    "type": "object",
                    "description": "Fields to update: status, priority, description, add_acceptance_criterion, implementation",
                },
            },
            "required": ["project_id", "requirement_id", "updates"],
        },
    },
    {
        "name": "close_issue",
        "description": "Mark an issue as resolved and move it to issues/closed/.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "issue_id": {"type": "string", "description": "e.g. BUG-001"},
                "resolution": {"type": "string"},
            },
            "required": ["project_id", "issue_id", "resolution"],
        },
    },
    # ── Phase 4: Code generation ──────────────────────────────────────────────
    {
        "name": "scaffold_project",
        "description": "Scaffold initial application code structure from SDD specs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "component": {"type": "string", "description": "e.g. backend, frontend, api, models, full"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "implement_requirement",
        "description": "Generate code to implement a specific requirement.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "requirement_id": {"type": "string"},
            },
            "required": ["project_id", "requirement_id"],
        },
    },
    {
        "name": "fix_issue_code",
        "description": "Generate a code fix for an open issue, referencing its spec analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "issue_id": {"type": "string"},
            },
            "required": ["project_id", "issue_id"],
        },
    },
    {
        "name": "generate_tests",
        "description": "Generate pytest test cases from a requirement's acceptance criteria.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "requirement_id": {"type": "string"},
            },
            "required": ["project_id", "requirement_id"],
        },
    },
    # ── Zettelkasten ──────────────────────────────────────────────────────────
    {
        "name": "enter_zettel_mode",
        "description": "Enter zettelkasten mode. Scans vault, scaffolds any unformatted permanent notes, reports status.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "exit_zettel_mode",
        "description": "Exit zettelkasten mode and return to normal Xochitl operation.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "zettel_status",
        "description": "Show current vault status: fleeting note count, permanent note count, parked questions.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "scaffold_vault",
        "description": "Create a fresh Zettelkasten vault structure (Fleeting/, Literature/, Permanent/, _System/) in the given directory, including Obsidian graph config.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the folder to scaffold. Defaults to VAULT_PATH in .env."},
            },
            "required": [],
        },
    },
    {
        "name": "new_literature_note",
        "description": "Create a new literature note file for a source (book, article, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Full source name, e.g. 'Value Proposition Design — Osterwalder'"},
            },
            "required": ["source"],
        },
    },
    {
        "name": "new_permanent_note",
        "description": "Create a new scaffolded permanent note from a claim title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string", "description": "The claim as a full sentence — this becomes the note title and filename."},
            },
            "required": ["claim"],
        },
    },
    {
        "name": "process_note",
        "description": "Run the full processing pipeline on a permanent note: word count, atomicity check, tag and link suggestions, serendipity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename in Permanent/ to process. Omit to process the most recently modified note."},
            },
            "required": [],
        },
    },
    {
        "name": "process_fleeting",
        "description": "Light triage of all notes in Fleeting/ — keep, discard, or promote to permanent.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "zettel_serendipity",
        "description": "Scan recent permanent notes for non-obvious cross-domain connections and surface them.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "clarity_check",
        "description": "Optional coaching pass on a permanent note — suggests 2-3 ways the writing could be sharper.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename in Permanent/ to check."},
            },
            "required": ["filename"],
        },
    },
]


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch(tool_name: str, tool_input: dict) -> str:
    """Execute a tool by name and return a string result."""
    handlers = {
        "get_queue": _handle_get_queue,
        "mark_task_done": _handle_mark_done,
        "add_task": _handle_add_task,
        "list_projects": _handle_list_projects,
        "update_core_memory": _handle_update_memory,
        "memorize": _handle_memorize,
        "recall": _handle_recall,
        "read_file": _handle_read_file,
        "write_file": _handle_write_file,
        "list_directory": _handle_list_directory,
        "save_artifact": _handle_save_artifact,
        "sync_notion": _handle_sync_notion,
        "push_to_notion": _handle_push_notion,
        "xochitl_help": _handle_help,
        # Phase 1
        "init_project": _handle_init_project,
        "save_bmad_artifact": _handle_save_bmad_artifact,
        "list_projects_sdd": _handle_list_projects_sdd,
        # Phase 2
        "generate_specs": _handle_generate_specs,
        "list_requirements": _handle_list_requirements,
        "get_requirement": _handle_get_requirement,
        "create_requirement": _handle_create_requirement,
        # Phase 3
        "create_issue": _handle_create_issue,
        "analyze_issue": _handle_analyze_issue,
        "update_requirement": _handle_update_requirement,
        "close_issue": _handle_close_issue,
        # Phase 4
        "scaffold_project": _handle_scaffold_project,
        "implement_requirement": _handle_implement_requirement,
        "fix_issue_code": _handle_fix_issue_code,
        "generate_tests": _handle_generate_tests,
        # Zettelkasten
        "enter_zettel_mode": _handle_enter_zettel,
        "exit_zettel_mode": _handle_exit_zettel,
        "zettel_status": _handle_zettel_status,
        "scaffold_vault": _handle_scaffold_vault,
        "new_literature_note": _handle_new_literature_note,
        "new_permanent_note": _handle_new_permanent_note,
        "process_note": _handle_process_note,
        "process_fleeting": _handle_process_fleeting,
        "zettel_serendipity": _handle_zettel_serendipity,
        "clarity_check": _handle_clarity_check,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return f"Unknown tool: {tool_name}"

    try:
        return handler(tool_input)
    except security.RequiresConfirmation as e:
        confirmed = security.confirm_in_terminal(e.prompt)
        if confirmed:
            tool_input["_confirmed"] = True
            return handler(tool_input)
        return "Action cancelled."
    except Exception as e:
        return f"Tool error ({tool_name}): {e}"


def _handle_get_queue(_: dict) -> str:
    rows = task_manager.get_queue_display()
    if not rows:
        return "Queue is empty."
    lines = []
    for r in rows:
        rolled = f" [rolled {r['days_rolled_over']}d]" if r["days_rolled_over"] > 0 else ""
        lines.append(
            f"  [{r['position']}] {r['description']} "
            f"({r['time_estimate_minutes']}m | {r['project_name']}){rolled}"
        )
    return "\n".join(lines)


def _handle_mark_done(inp: dict) -> str:
    task = task_manager.mark_done(inp["position"])
    if not task:
        return f"No task at position {inp['position']}."
    return f"Done: {task['description']}"


def _handle_add_task(inp: dict) -> str:
    task_id = task_manager.create_task(
        project_id=inp["project_id"],
        description=inp["description"],
        time_estimate_minutes=inp.get("time_estimate_minutes", 30),
    )
    return f"Task created: {task_id}"


def _handle_list_projects(_: dict) -> str:
    projects = task_manager.list_projects()
    if not projects:
        return "No active projects."
    lines = [f"  [{p['priority'].upper()}] {p['name']} — {p['description'] or 'no description'}" for p in projects]
    return "\n".join(lines)


def _handle_update_memory(inp: dict) -> str:
    conflict = mem.detect_preference_conflict(inp["section"], inp["content"])
    if conflict:
        confirmed = security.confirm_in_terminal(
            f"Conflict in '{inp['section']}':\n  Old: {conflict}\n  New: {inp['content']}"
        )
        if not confirmed:
            return "Memory update cancelled."
    mem.update_memory_section(inp["section"], inp["content"])
    return f"Memory updated: {inp['section']}"


def _handle_memorize(inp: dict) -> str:
    ok = mem.memorize(
        topic=inp["topic"],
        summary=inp["summary"],
        tags=inp.get("tags", []),
        project=inp.get("project"),
    )
    return "Memorized." if ok else "Vector DB unavailable — memory not saved."


def _handle_recall(inp: dict) -> str:
    results = mem.recall(
        query=inp["query"],
        n_results=inp.get("n_results", 5),
        project=inp.get("project"),
    )
    if not results:
        return "Nothing found in memory."
    lines = []
    for r in results:
        lines.append(f"  [{r['topic']}] {r['summary'][:120]}")
    return "\n".join(lines)


def _handle_read_file(inp: dict) -> str:
    content = security.read_file(Path(inp["path"]))
    return content[:8000]


def _handle_write_file(inp: dict) -> str:
    confirmed = inp.get("_confirmed", False)
    security.write_file(Path(inp["path"]), inp["content"], confirmed=confirmed)
    return f"Written: {inp['path']}"


def _handle_list_directory(inp: dict) -> str:
    entries = security.list_directory(Path(inp["path"]))
    return "\n".join(entries[:100])


def _handle_save_artifact(inp: dict) -> str:
    filepath = bmad_module.save_artifact(
        content=inp["content"],
        artifact_type=inp["artifact_type"],
        filename=inp.get("filename"),
    )
    link = bmad_module.clickable_path(filepath)
    return f"Saved: {filepath}\n{link}"


def _handle_sync_notion(_: dict) -> str:
    result = notion_sync.pull_and_sync()
    return (
        f"Pulled {result['projects']} projects, {result['areas']} areas, "
        f"{result['resources']} resources. Conflicts: {result['conflicts']}."
    )


def _handle_push_notion(_: dict) -> str:
    result = notion_sync.sync_completed_to_notion()
    return f"Pushed {result['pushed']} completed tasks to Notion."


def _handle_help(_: dict) -> str:
    from src.stats import help_text
    return help_text()


# ── Phase 1: Project init & BMAD ─────────────────────────────────────────────

def _handle_init_project(inp: dict) -> str:
    from src.skills.bmad_skill import BMADSkill
    skill = BMADSkill()
    result = skill.init_project(
        project_id=inp["project_id"],
        name=inp["name"],
        description=inp.get("description", ""),
    )
    return f"Created project '{result['name']}' at projects/{result['project_id']}/"


def _handle_save_bmad_artifact(inp: dict) -> str:
    from src.skills.bmad_skill import BMADSkill
    skill = BMADSkill()
    path = skill.save_bmad_artifact(
        project_id=inp["project_id"],
        artifact_type=inp["artifact_type"],
        content=inp["content"],
    )
    complete = skill.is_bmad_complete(inp["project_id"])
    suffix = " — BMAD complete! Ready to generate specs." if complete else ""
    return f"Saved: {path}{suffix}"


def _handle_list_projects_sdd(_: dict) -> str:
    from src.skills.bmad_skill import BMADSkill
    skill = BMADSkill()
    projects = skill.list_projects()
    if not projects:
        return "No SDD projects. Say 'I want to build X' to start one."
    lines = []
    for p in projects:
        stats = p.get("stats", {})
        lines.append(
            f"  [{p.get('status', '?').upper()}] {p.get('name', p['project_id'])} "
            f"— {stats.get('total_requirements', 0)} reqs, "
            f"{stats.get('open_issues', 0)} open issues"
        )
    return "SDD projects:\n" + "\n".join(lines)


# ── Phase 2: SDD spec generation & requirement CRUD ──────────────────────────

def _handle_generate_specs(inp: dict) -> str:
    from src.skills.sdd_skill import SDDSkill
    return SDDSkill().generate_specs_from_bmad(inp["project_id"])


def _handle_list_requirements(inp: dict) -> str:
    from src.skills.sdd_skill import SDDSkill
    reqs = SDDSkill().list_requirements(inp["project_id"])
    if not reqs:
        return "No requirements found. Run generate_specs first."
    lines = [f"  {r['id']}: {r['description'][:80]} [{r['status']}]" for r in reqs]
    return f"{len(reqs)} requirements:\n" + "\n".join(lines)


def _handle_get_requirement(inp: dict) -> str:
    import json
    from src.skills.sdd_skill import SDDSkill
    req = SDDSkill().get_requirement(inp["project_id"], inp["requirement_id"])
    if not req:
        return f"Requirement {inp['requirement_id']} not found."
    return json.dumps(req, indent=2)


def _handle_create_requirement(inp: dict) -> str:
    from src.skills.sdd_skill import SDDSkill
    return SDDSkill().create_requirement(
        project_id=inp["project_id"],
        req_type=inp.get("req_type", "CORE"),
        content={
            "title": inp.get("title", ""),
            "description": inp.get("description", ""),
            "priority": inp.get("priority", "P2"),
        },
    )


# ── Phase 3: Issue tracking ───────────────────────────────────────────────────

def _handle_create_issue(inp: dict) -> str:
    from src.skills.sdd_skill import SDDSkill
    return SDDSkill().create_issue(
        project_id=inp["project_id"],
        issue_type=inp.get("issue_type", "bug"),
        title=inp.get("title", ""),
        description=inp["description"],
    )


def _handle_analyze_issue(inp: dict) -> str:
    import json
    from src.skills.sdd_skill import SDDSkill
    result = SDDSkill().analyze_issue(inp["project_id"], inp["issue_id_or_description"])
    if "error" in result:
        return f"Analysis failed: {result['error']}"
    confidence = result.get("confidence", 0)
    warning = "\n\n⚠ Confidence below 0.75 — review before applying." if confidence < 0.75 else ""
    return json.dumps(result, indent=2) + warning


def _handle_update_requirement(inp: dict) -> str:
    from src.skills.sdd_skill import SDDSkill
    return SDDSkill().update_requirement(
        project_id=inp["project_id"],
        requirement_id=inp["requirement_id"],
        updates=inp["updates"],
    )


def _handle_close_issue(inp: dict) -> str:
    from src.skills.sdd_skill import SDDSkill
    return SDDSkill().close_issue(inp["project_id"], inp["issue_id"], inp["resolution"])


# ── Phase 4: Code generation ──────────────────────────────────────────────────

def _handle_scaffold_project(inp: dict) -> str:
    from src.skills.code_skill import CodeSkill
    return CodeSkill().scaffold_from_specs(inp["project_id"], inp.get("component", "backend"))


def _handle_implement_requirement(inp: dict) -> str:
    from src.skills.code_skill import CodeSkill
    return CodeSkill().generate_code_for_requirement(inp["project_id"], inp["requirement_id"])


def _handle_fix_issue_code(inp: dict) -> str:
    from src.skills.code_skill import CodeSkill
    return CodeSkill().fix_issue(inp["project_id"], inp["issue_id"])


def _handle_generate_tests(inp: dict) -> str:
    from src.skills.code_skill import CodeSkill
    return CodeSkill().generate_tests(inp["project_id"], inp["requirement_id"])


# ── Zettelkasten handlers ─────────────────────────────────────────────────────

def _handle_enter_zettel(_: dict) -> str:
    from src.skills.zettelkasten_skill import enter_mode
    return enter_mode()


def _handle_exit_zettel(_: dict) -> str:
    from src.skills.zettelkasten_skill import exit_mode
    return exit_mode()


def _handle_zettel_status(_: dict) -> str:
    from src.skills.zettelkasten_skill import vault_status
    return vault_status()


def _handle_scaffold_vault(inp: dict) -> str:
    from src.skills.zettelkasten_scaffold import scaffold_vault
    return scaffold_vault(inp.get("path"))


def _handle_new_literature_note(inp: dict) -> str:
    from src.skills.zettelkasten_skill import new_literature_note
    return new_literature_note(inp["source"])


def _handle_new_permanent_note(inp: dict) -> str:
    from src.skills.zettelkasten_skill import new_permanent_note
    return new_permanent_note(inp["claim"])


def _handle_process_note(inp: dict) -> str:
    from src.skills.zettelkasten_process import process_note
    return process_note(inp.get("filename"))


def _handle_process_fleeting(_: dict) -> str:
    from src.skills.zettelkasten_process import process_fleeting
    return process_fleeting()


def _handle_zettel_serendipity(_: dict) -> str:
    from src.skills.zettelkasten_process import serendipity_scan
    return serendipity_scan()


def _handle_clarity_check(inp: dict) -> str:
    from src.skills.zettelkasten_process import clarity_check
    return clarity_check(inp["filename"])
