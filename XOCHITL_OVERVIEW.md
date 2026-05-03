# Xochitl — Project Overview

**For BMAD planning input.** This document describes the current state of Xochitl: what it is, what it does, how it is built, and where the gaps are.

---

## What Is Xochitl?

Xochitl (pronounced "so-CHEEL") is a terminal-native AI Chief of Staff. It runs locally on Windows, surfaces as a CLI tool (`xochitl`), and acts as a strategic partner for personal project management and application development.

The two core jobs it does:

1. **Personal task and project management** — pulls projects and tasks from Notion (PARA methodology), manages a local WIP queue capped at 3 tasks, and pushes completions back to Notion.
2. **Application development pipeline** — guides the user through the BMAD → SDD → Code pipeline: from idea to business model, to spec, to scaffolded code.

---

## Persona

Xochitl has a defined personality (`SOUL.md`):

- **Role:** Senior Product Strategist and Chief of Staff. The "Expert Past Me."
- **Style:** Professional, strategic, direct. Grade 10–12 reading level. Slightly cynical, warm humor.
- **Rules:** No em dashes. No AI filler. No transition fluff. Pushes back when the user is wrong. Applies JTBD / 360 Check / First Principles only on demand, not every response.
- **Spanish flavor:** Drops occasional elementary Spanish phrases (Claro, Bueno, Ay no) when natural.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| CLI framework | `click` |
| Terminal UI | `rich` (panels, markdown, spinners, progress) |
| Local LLM | Ollama or LM Studio (configurable via `.env`) |
| Cloud LLM | Gemini 1.5 Pro/Flash or Claude (Anthropic SDK + OpenAI-compat) |
| Local DB | SQLite (`data/tasks.db`) |
| Vector DB | ChromaDB (`data/chroma/`) |
| Notion sync | `notion-client` |
| Config | `.env` + `MEMORY.md` |

The local model handles task management, simple QA, and file reads. Cloud handles BMAD planning, code generation, and architecture design. Routing is automatic via `TieredRouter`.

---

## Project Structure

```
xochitl/
├── src/
│   ├── cli.py               # All click commands (entry point)
│   ├── chat.py              # Conversational loop, intent classification, handlers
│   ├── router.py            # TieredRouter — local vs. cloud routing logic
│   ├── context_loader.py    # System prompt assembly (SOUL + memory + location)
│   ├── llm_interface.py     # LLM call wrappers, prompts, model constants
│   ├── task_manager.py      # Task CRUD, queue management, rollover logic
│   ├── notion_sync.py       # Notion pull/push integration
│   ├── database.py          # SQLite schema and all raw query helpers
│   ├── memory.py            # 3-tier memory: MEMORY.md, SQLite sessions, ChromaDB
│   ├── security.py          # Path sandboxing (allowed/forbidden roots)
│   ├── file_tools.py        # Confirmed file read/write/delete with permission gates
│   ├── bmad.py              # BMAD project detection (.clinerules/ based)
│   ├── stats.py             # Usage stats, health check, help text
│   ├── tools.py             # Tool dispatch (for LLM tool calls)
│   └── skills/
│       ├── base.py              # Skill ABC
│       ├── bmad_skill.py        # Project init, BMAD artifact management
│       ├── sdd_skill.py         # Spec generation, requirement CRUD
│       ├── code_skill.py        # Code scaffolding from specs
│       ├── notion_skill.py      # Notion sync skill wrapper
│       └── orchestrator_skill.py # Background agent delegation + workspace management
├── projects/                # Apps built WITH Xochitl (each has its own pipeline state)
│   └── <project-id>/
│       ├── .project-meta.yml
│       ├── bmad/            # business-model.md, architecture.md, design-specs.md
│       ├── specs/           # core-features.md, traceability.json
│       ├── issues/          # open/, in-progress/, closed/
│       └── src/             # Generated application code
├── config/
│   └── global.md            # User-level context injected into all prompts
├── data/
│   ├── tasks.db             # SQLite database
│   ├── chroma/              # ChromaDB vector store
│   └── exports/             # Exported chat sessions (markdown)
├── SOUL.md                  # Persona definition
├── MEMORY.md                # Active user preferences and goals (auto-updated)
├── CLAUDE.md                # Instructions for Claude Code
└── requirements.txt
```

---

## Data Model (SQLite)

```
projects     — id, name, priority (high/medium/low), status, description, deadline
tasks        — id, project_id, description, time_estimate_minutes, status, days_rolled_over
queue        — task_id, position (1–3)  ← hard WIP cap of 3 rows
areas        — PARA areas (synced from Notion)
resources    — PARA resources (synced from Notion)
sessions     — chat session history (conversation_json)
token_usage  — per-call local/cloud token + cost tracking
audit_log    — file operation audit trail
sync_log     — Notion sync history
```

---

## CLI Commands

```
xochitl                         Default: launches chat
xochitl chat                    Interactive conversational session
  --cloud                       Force cloud model for all queries
  --with-orchestrator           Start background agent daemon on launch

xochitl today                   Refresh daily queue (top 3 tasks)
xochitl queue                   Show current WIP
xochitl done <num>              Mark task complete, pull next into queue
xochitl plan "<project>"        LLM decompose project into tasks

xochitl projects list           List active projects
xochitl projects add "<name>"   Create project (--priority, --description, --deadline)

xochitl pull                    Fetch projects/tasks from Notion
xochitl pull --decompose        Pull + LLM-decompose new projects
xochitl sync                    Push completed tasks to Notion

xochitl tasks                   List background task workspaces
xochitl workspace <id>          Inspect delegated task progress

xochitl models                  Show active local/cloud model config
xochitl status                  Progress dashboard
xochitl stats [--days N]        Token usage and cost report
xochitl export [--open]         Save chat session to markdown
```

---

## Conversational Layer

Intent is classified in `chat.py::_classify_intent()` by keyword matching across these categories:

| Intent | Triggers |
|---|---|
| `file_operation` | File extensions, path strings, file verbs + path indicators |
| `task_query` | task, queue, today, blocked, in progress |
| `action_request` | sync, pull, push, notion, delegate |
| `new_project` | "I want to build", "let's create", "new app" |
| `bmad_workflow` | plan, design, architect, sprint (when in a BMAD project) |
| `sdd_workflow` | spec, requirement, FR-*, traceability (when project is active) |
| `issue_tracking` | bug, broken, failing, error (when project is active) |
| `code_generation_intent` | scaffold, generate code, implement, build backend |
| `general` / `simple_question` | fallback |

Pending actions use a `current_context` dict — the next message is checked against it before re-classifying. This handles confirm/cancel flows for file writes, Notion sync, project init, spec generation, code scaffolding, and issue analysis.

---

## LLM Routing

`TieredRouter` in `router.py` routes each query based on classification:

| Category | Route |
|---|---|
| simple_qa, task_management, memory_recall, xochitl_help | Local model |
| code_generation, code_review | Local coding model (thinking) |
| architecture_planning, bmad_complex | Local thinking model → cloud fallback |
| creative_writing, data_analysis, bmad_party_mode | Cloud |
| file_operations | Local, with file context injected into system prompt |

If the local model fails twice consecutively, the router auto-escalates to cloud.

---

## Memory System (3 Tiers)

1. **MEMORY.md** (active, always injected): User preferences, active goals, BMAD workflows, context shortcuts. Updated by Xochitl during chat. Git-committed on each write for rollback.
2. **SQLite sessions** (working): Full conversation JSON per session. Used for `xochitl export`.
3. **ChromaDB** (long-term): Semantic vector store. Queried when user asks "what did we discuss about X?". Grows over time.

---

## The BMAD → SDD → Code Pipeline

For building new applications FROM WITHIN Xochitl:

### Stage 1: BMAD (Business Model, Architecture, Design)
- User says "I want to build X"
- Xochitl creates `projects/<id>/` with subdirectories
- Walks user through: Business Model → Architecture → Design Specs
- Artifacts saved to `projects/<id>/bmad/*.md`
- `bmad_complete` flag set in `.project-meta.yml` when business-model + architecture exist

### Stage 2: SDD (Software Design Document / Spec)
- Triggered when BMAD is complete: "generate specs"
- Reads BMAD artifacts, calls cloud LLM to produce `specs/core-features.md`
- Requirements parsed into `traceability.json` as FR-* IDs with acceptance criteria
- Spec status: `pending → approved → implemented`

### Stage 3: Code Generation
- "scaffold the backend/frontend/api"
- Reads specs, generates code with `# Implements FR-*` traceability comments
- Output to `projects/<id>/src/`

### Stage 4: Issue Tracking
- "there's a bug where X"
- Analyzes against specs to classify: spec gap / spec bug / implementation bug
- Proposes spec change + implementation guidance
- Confidence score returned; low confidence flagged to user

---

## Security Model

File operations are sandboxed in `security.py`:

**Allowed roots:**
- `C:\Users\<user>\` (entire home directory)
- `C:\Users\<user>\Desktop\Jason\Resource\Code Projects`
- `C:\Users\<user>\Documents`
- `C:\Users\<user>\Downloads`
- Xochitl's own project root

**Forbidden roots (always blocked regardless of allowed):**
- `~/.ssh`
- `~/.aws`
- `C:\Windows`
- `C:\Program Files`

Read is automatic. Write and delete require user confirmation via the pending-action flow.

---

## Background Orchestrator

`OrchestratorSkill` can spin up a background subprocess to handle long-running tasks autonomously:

- Creates isolated workspaces under `.xochitl/workspaces/task-<id>/`
- Progress tracked in `task-artifacts/progress.json` (state, completed_steps, next_steps)
- `xochitl tasks` lists all workspaces
- `xochitl workspace <id>` shows detailed progress
- Daemon can be launched at startup with `--with-orchestrator` flag

---

## Known Gaps and Open Problems

### Functional
- **No real-time Notion webhook** — sync is pull-on-demand only; changes made in Notion between syncs are invisible until `xochitl pull`
- **Orchestrator is incomplete** — workspace/progress infrastructure exists but the actual autonomous agent execution loop is a stub
- **Code skill output quality** — scaffold generation is functional but produces boilerplate; no feedback loop from generated code back into specs
- **No test suite for chat layer** — smoke tests cover pipeline components but intent classification and handler routing have no automated tests
- **File fuzzy search performance** — `_find_by_name` uses `rglob("*")` which can be slow on large directories

### UX
- **No streaming output** — responses appear all at once; long cloud responses feel laggy
- **No session continuation** — each `xochitl chat` starts fresh; no way to resume a previous session mid-conversation
- **No undo for spec changes** — issue analysis can apply spec changes, but there is no rollback mechanism beyond Git
- **Help text is in-chat only** — `xochitl help` is not a CLI command; help is only accessible by typing `help` inside chat

### Infrastructure
- **No `.env` template** — new users have no reference for required environment variables (API keys, Notion token, model names)
- **No migration system** — SQLite schema changes require manual intervention
- **Single-user only** — no concept of workspaces, teams, or multiple user profiles
- **Windows-only path assumptions** — some path handling in `security.py` and `router.py` has Windows-specific logic

---

## Environment Variables (`.env`)

```
# LLM — Local
LOCAL_PROVIDER=ollama          # or "lmstudio"
LOCAL_MODEL=gemma3:4b
LOCAL_THINKING_MODEL=...
LOCAL_CODING_MODEL=...
OLLAMA_URL=http://localhost:11434
LM_STUDIO_URL=http://localhost:1234

# LLM — Cloud
CLOUD_PROVIDER=anthropic       # or "google"
CLOUD_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Notion
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=...
```

---

## Current Development State

The core loop (chat → classify → route → respond) is solid. Task management, Notion sync, file reading, BMAD project init, and spec generation all work end-to-end. The orchestrator and code generation stages are partially built. The biggest open investment areas are: streaming, session continuity, the orchestrator execution loop, and test coverage for the conversational layer.
