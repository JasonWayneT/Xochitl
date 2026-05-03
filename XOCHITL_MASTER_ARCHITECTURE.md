# Xochitl Master Architecture

**Version:** 4.0  
**Updated:** 2026-04-30  
**Status:** Authoritative — supersedes all prior architecture documents

---

## 1. What Xochitl Is

Xochitl is a terminal-native AI Chief of Staff. The primary interface is conversational — natural back-and-forth, like talking to Claude in the terminal. She manages tasks via PARA/Notion integration, detects BMAD projects and runs planning workflows, and can optionally delegate work to a background orchestrator when the user asks for it.

**Core design principles:**
- Talk to Xochitl, not at her. She asks before acting.
- The orchestrator is a tool she uses — not the default mode.
- File operations follow a permission model: reads are automatic, overwrites/deletes require confirmation.
- Local-first: the local model (gemma4-e4b via Ollama/LM Studio) handles most work; cloud escalates when needed.

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ |
| CLI | `click` |
| Terminal UI | `rich` |
| Local LLM | LM Studio (primary) / Ollama (fallback) — model: `gemma4-e4b` at `http://localhost:11434` |
| Cloud LLM | Gemini / Anthropic (Claude) — for complex code and heavy BMAD |
| Database | SQLite via `data/tasks.db` |
| Notion | `notion-client` — source of truth for projects |
| Vector DB | ChromaDB — long-term semantic memory (Tier 3) |

---

## 3. Project Structure

```
./
├── src/
│   ├── cli.py                    # Click entry point; all commands
│   ├── chat.py                   # XochitlChat — primary conversational loop
│   ├── router.py                 # TieredRouter — local/cloud routing
│   ├── context_loader.py         # Builds system prompts from memory + context
│   ├── memory.py                 # MEMORY.md read/write
│   ├── database.py               # SQLite schema and queries
│   ├── task_manager.py           # Task CRUD, queue management, rollover
│   ├── llm_interface.py          # Ollama HTTP calls
│   ├── notion_sync.py            # Notion read/write with conflict detection
│   ├── bmad.py                   # BMAD project detection and context loading
│   ├── security.py               # Path sandboxing (allowed roots)
│   ├── file_tools.py             # FileTools — conversational permission model
│   ├── tools.py                  # Tool registry and dispatcher
│   ├── stats.py                  # Health check, help text, stats dashboard
│   └── skills/
│       ├── __init__.py
│       ├── base.py               # Skill ABC: can_handle / suggest / execute
│       ├── bmad_skill.py         # BMADSkill
│       ├── notion_skill.py       # NotionSkill
│       └── orchestrator_skill.py # OrchestratorSkill + daemon + workspace mgmt
├── config/
│   ├── global.md                 # Universal LLM context (PARA, WIP rules)
│   └── projects/                 # Per-project context files
├── data/
│   ├── tasks.db                  # SQLite database
│   └── queue.md                  # Human-readable WIP queue
├── .xochitl/
│   ├── workspaces/               # Background task workspaces
│   │   └── task-<id>/
│   │       └── task-artifacts/
│   │           └── progress.json
│   └── orchestrator.pid          # PID file for background daemon
├── MEMORY.md                     # Active context (Tier 1 memory)
├── SOUL.md                       # Persona definition
├── CLAUDE.md                     # Claude Code instructions
├── XOCHITL_MASTER_ARCHITECTURE.md  # This file
└── archive/                      # Superseded design documents
```

---

## 4. The Two-Layer Architecture

```
┌──────────────────────────────────────────────────────────┐
│  CONVERSATIONAL LAYER  (you interact with this daily)    │
│                                                          │
│  $ xochitl                                               │
│  > what's on my plate today?                             │
│                                                          │
│  XochitlChat: natural chat, asks before acting,          │
│  suggests skills, routes to handlers, persists session   │
└──────────────────────────────────────────────────────────┘
                           │
                           │  (Xochitl uses this when you delegate)
                           ↓
┌──────────────────────────────────────────────────────────┐
│  ORCHESTRATOR LAYER  (background, optional)              │
│                                                          │
│  OrchestratorSkill: daemon process, workspace creation,  │
│  progress.json tracking, agent restart on crash          │
│                                                          │
│  Only active when: "delegate it" / "handle it for me"   │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Memory Architecture (3 Tiers)

### Tier 1: Active Context (`MEMORY.md`)
Injected directly into every system prompt. Structured with `user:` and `project:` prefixes.

### Tier 2: Working Memory (SQLite `sessions` table)
Conversation history for the current session. Persisted via `db.update_session_conversation()` after every response. Cleared when session ends.

### Tier 3: Long-Term Memory (ChromaDB)
Semantic vector store. Background summarization commits key decisions and project context after sessions. Accessible via `recall(query)` in `src/memory.py`.

---

## 6. Conversational Layer (`src/chat.py`)

`XochitlChat` is the primary class. Entry point is `start()` which runs the REPL. Single-turn usage is `process_message(user_input)`.

### Message processing pipeline

```
process_message(user_input)
  1. Check pending_file_operation (yes/no response to file permission)
  2. Check pending_action (yes/no to sync/delegate confirmation)
  3. Refresh BMAD context (detect_bmad_project on cwd)
  4. Classify intent → type
  5. Score skills (can_handle) → suggest if score > 0.6
  6. Route to handler
  7. _record() → append to history + persist session
```

### Intent types

| Type | Triggers | Handler |
|------|----------|---------|
| `task_query` | task/queue/blocked/today | `_handle_task_query` → TieredRouter with `task_management` route |
| `action_request` | sync/notion/delegate/work on | `_handle_action_request` → sets `pending_action`, shows preview |
| `file_operation` | read/write/delete + extension or path | `_handle_file_operation` → FileTools |
| `orchestrator_query` | background/delegated/how is the agent | `_handle_orchestrator_query` → OrchestratorSkill status |
| `bmad_workflow` | plan/design/architect + BMAD project detected | `_handle_bmad_workflow` → TieredRouter with `bmad_complex` route |
| `simple_question` | ≤ 6 words | `_general_conversation` |
| `general` | fallback | `_general_conversation` |

### Confirmation model

Pending state is tracked in `self.current_context`:

- `current_context["pending_file_operation"]` — operation_id from FileTools; cleared on yes/no
- `current_context["pending_action"]` — `"sync_notion"` or `"push_notion"`; cleared on yes/no

Confirmation sets: `{"yes", "y", "ok", "sure", "yeah", "yep", "do it", "go ahead"}` / `{"no", "n", "nope", "cancel", "nevermind", "stop", "don't"}`

---

## 7. Skills System (`src/skills/`)

Skills are conversational tools — suggested when relevant, executed only after user confirmation.

### `Skill` ABC (`base.py`)
```python
can_handle(user_input, context) -> float   # 0.0–1.0 confidence
suggest(user_input, context) -> str        # message to show user
execute(user_input, context, params) -> str
```

Xochitl scores all skills per message; if `max(scores) > 0.6` and intent type isn't `general/simple_question/task_query`, the suggestion is returned instead of normal routing.

### Skills

| Skill | Trigger score | Key behavior |
|-------|---------------|-------------|
| `BMADSkill` | 0.8 if planning keywords + bmad_project in context | Offers guided vs draft workflow |
| `NotionSkill` | 0.7 if notion/sync/pull/push keywords | Shows pending changes, asks to confirm |
| `OrchestratorSkill` | 0.75 if delegate/background/status keywords | Starts daemon, creates workspace, reports progress |

---

## 8. TieredRouter (`src/router.py`)

Routes queries to local or cloud model based on complexity classification.

- **Local (gemma4-e4b):** Task management, simple QA, file reads, memory recall
- **Cloud (Gemini/Claude):** Complex code generation, architecture planning, heavy BMAD workflows

`route()` signature accepts `query`, `conversation_history`, `system_prompt`, optional `force_route`, optional `bmad_context`.

Helper functions used by `XochitlChat`:
- `_live_db_context()` — formats current queue from SQLite for task-related prompts
- `_resolve_file_context(user_input)` — extracts and reads file content mentioned in message

---

## 9. File Tools (`src/file_tools.py`)

Permission model:
- **Read:** automatic, no confirmation
- **Write (new file):** automatic
- **Write (existing file):** returns `{"status": "pending_permission", "operation_id": "..."}` → user must confirm
- **Delete:** always pending_permission

`confirm_operation(op_id)` / `cancel_operation(op_id)` finalize or discard.

Path validation via `src/security.py` — all paths must resolve within configured allowed roots.

---

## 10. SQLite Schema

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    priority TEXT NOT NULL,        -- 'high', 'medium', 'low'
    status TEXT DEFAULT 'active',
    description TEXT,
    deadline DATE,
    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    description TEXT NOT NULL,
    time_estimate_minutes INTEGER,
    status TEXT DEFAULT 'todo',    -- 'todo', 'in_progress', 'done', 'blocked'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    notion_task_id TEXT,
    blocked_by TEXT,
    days_rolled_over INTEGER DEFAULT 0,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE queue (
    task_id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,     -- 1, 2, or 3 (WIP limit enforced)
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversation JSON
);

CREATE TABLE sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tasks_completed INTEGER,
    projects_updated INTEGER,
    notes TEXT
);
```

**WIP invariant:** `queue` holds exactly 0–3 rows. `task_manager.py` enforces this on every mutation.

---

## 11. BMAD Integration (`src/bmad.py`)

`detect_bmad_project(cwd)` walks up the directory tree looking for `.clinerules/`. Returns a dict with `root`, `version`, `modules`, `workflows` or `None` if not in a BMAD project.

`build_bmad_context(bmad_project)` loads relevant BMAD workflow content for injection into the LLM system prompt.

Artifact save locations (when Xochitl generates BMAD artifacts):
- PRDs, brainstorms → `planning-artifacts/`
- Sprint stories, code → `implementation-artifacts/`

---

## 12. CLI Commands (`src/cli.py`)

```bash
xochitl                    # Start conversational chat (primary)
xochitl --with-orchestrator # Start chat with orchestrator daemon running
xochitl --cloud            # Force cloud routing

xochitl today              # Generate/refresh daily queue (top 3 tasks)
xochitl done <num>         # Mark task complete, pull next into queue
xochitl queue              # Display current WIP tasks
xochitl plan "<name>"      # Decompose project into tasks via LLM
xochitl sync               # Push completed tasks to Notion
xochitl pull               # Fetch latest from Notion
xochitl status             # Overall progress dashboard

xochitl tasks              # List all background task workspaces
xochitl workspace <id>     # Show progress for a specific workspace
```

---

## 13. Orchestrator & Workspace Management (`src/skills/orchestrator_skill.py`)

When the user delegates a task:

1. `OrchestratorSkill.start_daemon()` — spawns `src.orchestrator_daemon` subprocess or falls back to in-process mode. PID written to `.xochitl/orchestrator.pid`.
2. `delegate_task(task_id)` — creates `.xochitl/workspaces/task-<id>/task-artifacts/progress.json` with initial state.
3. `get_status()` / `_format_status()` — reads `progress.json` from all active workspaces, formats for conversational display.

**`progress.json` schema:**
```json
{
  "description": "task description",
  "state": "initializing | in_progress | review | done | blocked",
  "completed_steps": [],
  "next_steps": ["gather context", "implement", "test", "submit for review"],
  "started_at": "ISO timestamp"
}
```

---

## 14. Notion Sync (`src/notion_sync.py`)

- `pull_and_sync()` — fetches projects/tasks from Notion, compares `last_edited_time` vs local `last_synced`, surfaces diffs on conflict, returns `{projects, areas, resources, conflicts}`.
- `sync_completed_to_notion()` — pushes completed tasks, returns `{pushed}`.

Conflict handling: on `pull`, if Notion record is newer than local, user sees a diff and chooses: pull / keep local / merge.

---

## 15. Persona (`SOUL.md`)

- **Role:** Senior Product Strategist / Chief of Staff
- **Frameworks:** JTBD, First Principles, 80/20 Pareto
- **Tone:** Professional, direct, slightly cynical, warm
- **Language:** Light Spanish for strategic emphasis (claro, bueno, mira — natural, not forced)
- **Pushback:** Level 3 — actively corrects objectively wrong positions, offers Devil's Advocate + Safety Net on ideas
- **Prohibited:** "Innovative," "Passionate," "As an AI," excessive apologies

---

## 16. Phase Roadmap

### Completed (Phases 1–3)
- Full CLI with all commands
- SQLite schema and task management with WIP limit
- Notion read/write sync with conflict detection
- TieredRouter (local + cloud)
- 3-tier memory (MEMORY.md + SQLite sessions + ChromaDB)
- BMAD project detection and workflow loading
- Security sandboxing (`src/security.py`)
- `XochitlChat` conversational loop with intent classification
- `FileTools` permission model
- Skills system (`BMADSkill`, `NotionSkill`, `OrchestratorSkill`)
- Workspace creation and `progress.json` tracking
- Session persistence

### Planned (Phase 4 — Harness Engineering)
These are not yet implemented. The design is in the archive.

**`AGENTS.md` guide layer** — Constraints injected into every agent context: architecture rules (no raw SQL outside `database.py`, all LLM calls via `router.py`), file organization rules, coding standards, BMAD artifact conventions.

**`src/sensors/linter.py`** — `XochitlLinter` class. Detects architectural violations (raw SQL, direct API calls), file organization issues, missing type hints, functions over 50 lines. Error messages include self-correction instructions for agent feedback loops.

**`src/sensors/llm_judge.py`** — `LLMJudge` class. Uses local model to validate responses before delivery: completeness, brevity, actionability, file path format. Detects Ralph loops (same error 3+ times → mark task blocked).

**`src/mistake_registry.py`** — `MistakeRegistry` class. Logs every agent failure with type, what sensor caught it, what guide was missing, proposed fix. `analyze_patterns()` surfaces recurring gaps. `propose_harness_improvements()` generates AGENTS.md and linter rule additions.

**`xochitl harness-report`** — CLI command showing mistake patterns and recommendations.

**`xochitl harness-improve`** — CLI command generating improvement PR from mistake registry.

**Full orchestrator daemon** — `src/orchestrator_daemon.py` with git worktree per task, agent restart on crash, retry limit before marking blocked, Notion queue polling loop.

**`xochitl update`** — `git pull` + `pip install -e .` + skill sync + DB migrations.

**`xochitl doctor`** — Connectivity checks: LM Studio/Ollama, Notion API, ChromaDB, local model benchmark.

---

## 17. Configuration

Environment variables (via `.env` at project root):
```
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
```

File access allowed roots (configured in `src/security.py`):
- `~/Desktop/Jason/Resource/Code Projects/`
- `~/Documents/`

---

## Archive

Superseded documents are in `archive/`:
- `XOCHITL_PROJECT_SPEC.md` — original spec (pre-implementation)
- `XOCHITL_OPENCLAW_ARCHITECTURE.md` — v1/v2 OpenClaw-based design

The following root-level docs are now superseded by this file and can be deleted:
- `XOCHITL_CONVERSATIONAL_HARNESS.md` — implemented; design captured in §6–9 above
- `XOCHITL_HARNESS_ENGINEERING_IMPLEMENTATION.md` — Phase 4 design captured in §16 above
- `REFERENCE_CODE_SNIPPETS.md` — superseded by actual implementation in `src/`
