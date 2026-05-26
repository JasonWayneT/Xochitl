# Xochitl Capabilities Manifest

Xochitl is a high-intelligence agentic CLI for software engineering, project planning (BMAD), and personal productivity. This document summarizes verified capabilities as of May 2026.

**Spec source of truth**: [docs/spec/02-requirements-registry.md](docs/spec/02-requirements-registry.md) and [docs/spec/06-traceability/traceability-matrix.md](docs/spec/06-traceability/traceability-matrix.md).

---

## 1. Conversational Intelligence

- **Tiered routing** (`src/router.py`): Local router model classifies each turn; local, specialist-local, or cloud execution. Session token budget via `SessionGovernor` (`src/governor.py`).
- **Bounded exploration** (`ExplorerSkill`): Read-only chained file/search steps with loop and budget guards.
- **Capability boundary** (CR-036): Near-miss and complete-miss turns get explicit `[TURN CONTEXT]` so the model does not silently downgrade.
- **Compact reasoning disclosure** (CR-040): One-line action summaries before tools; compact result pairing; explicit "why" expansion on request.
- **Controlled initiative** (CR-038): Proactive alerts by category with OFF / ERRORS_ONLY modes and dismiss-to-suppress.
- **Reflection critic** (CR-019): Optional second pass on low-confidence or risky outputs.
- **Persona & memory**:
  - **Preferences** — `preferences` table (`preference_key`, `preference_value`).
  - **Semantic memory** — LanceDB table `memories` at `~/.xochitl/lancedb/` with HyDE recall (`src/memory.py`).
  - **Procedural memory** — SQLite `workflows` + LanceDB `workflow_intents` for reusable multi-step routines (CR-041/042).
  - **Structured facts** — `memory_facts` with confidence gating.
  - **Cultural voice** — Matriarca persona via SOUL.md and system prompt layers.

---

## 2. SDD Pipeline (Engineer)

- **BMAD intake**: Business Model, Architecture, and Design artifacts → technical specs.
- **Project scaffolding**: `projects/<id>/` with `bmad/`, `specs/`, `src/`, traceability.
- **Traceability**: Generated code cites requirement IDs (e.g. `# Implements FR-CORE-001`).
- **Issue analysis**: Bugs linked to specs; fixes trace back to `FR-*` / `BUG-*`.

---

## 3. Productivity & Workflows

- **Task queue**: SQLite WIP limit of 3; `xochitl today`, `xochitl done`.
- **Notion sync**: PARA-oriented two-way task sync.
- **Procedural workflows** (CR-041/042):
  - Intent recall injects `[PROCEDURAL WORKFLOW]` into the agent loop.
  - After multi-step success, offers `/workflow save <name>` (LLM-distilled steps).
  - `/workflow run <name>` executes stored steps via `WorkflowSkill`.
  - `/workflows` lists saved routines.
- **Dynamic skills**: User-defined skills under `.xochitl/skills/`; optional auto-offer after repeating patterns.

---

## 4. Technical Capabilities

- **LLM routing**: Ollama local + optional Gemini / Claude cloud. GPU-aware model selection (CR-043): auto-detects VRAM at boot and selects the best local models for WORKSTATION / DESKTOP / LAPTOP / MINIMAL profiles.
- **Secrets management** (CR-044): Doppler-first load at boot (`secrets.load()`); falls back to `.env` then `os.environ`. Per-key DB override via `xochitl secrets set`.
- **Terminal visual grammar** (CR-039): Semantic prefixes (`done`, `action`, `warn`, `fail`), 80-column wrap, step progress `n/m` via `src/terminal_output.py`.
- **JSON CLI mode**: `xochitl --json` on data commands (`today`, `status`, `queue`, `sync`, etc.); `chat`/`plan` return `interactive_only`.
- **Safe executor** (CR-037): `ActionGovernor` classifies read/write/exec; path traversal denied; allowlisted shell commands.
- **Security sandbox** (`src/security.py`): Authorized roots only; reads automatic, mutating actions need approval.
- **Context assembly** (`src/context_manager.py`): Five-layer system prompt with proportional compaction.
- **Observability** (CR-021): Event bus + optional JSONL traces for routing and LLM completion.
- **Eval harness** (CR-022): Golden-set skill routing accuracy without live LLM calls.

---

## 5. Google Integration

OAuth 2.0 credentials at `~/.xochitl/google_token.json`. Run `xochitl` and say "check my email" or "directions to X" — auth flow opens in browser on first use.

| Capability | Skill | What you can say |
|---|---|---|
| Gmail inbox | `GmailSkill` | "check my email", "any unread emails?" |
| Gmail search | `GmailSkill` | "find emails from alice", "emails about the project" |
| Gmail send | `GmailSkill` | "send an email to bob@example.com saying..." |
| Gmail mark/archive | `GmailSkill` | "mark email 1 as read", "archive that" |
| Directions | `MapsSkill` | "directions to downtown", "how long to drive to X" |
| Travel time | `MapsSkill` | "how far is it from home to the airport?" |
| Places search | `MapsSkill` | "find a Thai restaurant near me" |

---

## 6. Command Reference

| Command | Description |
|---|---|
| `xochitl chat` | Interactive session (default) |
| `xochitl today` | Daily prioritized task view |
| `xochitl plan "<project>"` | Decompose goals into tasks |
| `xochitl done <id>` | Complete a task |
| `xochitl sync` / `pull` | Notion sync |
| `xochitl authorize <path>` | Grant file access |
| `xochitl --json <cmd>` | Machine-readable output for supported commands |

### In-chat slash commands (selection)

| Command | Description |
|---|---|
| `/workflows` | List saved procedural workflows |
| `/workflow save <name>` | Distill and save current session as a workflow |
| `/workflow run <name>` | Execute a saved workflow step-by-step |
| `/brief` | Structured daily brief |
| `/budget` | Session token budget status |
| `/dismiss` | Suppress initiative alert category |

---

## 7. Skills (built-in)

| Skill | Role |
|---|---|
| `BMADSkill` | New project intake |
| `SDDSkill` | Requirements and traceability |
| `CodeSkill` | Scaffold and generate code |
| `NotionSkill` | Task sync |
| `WeatherSkill` | Open-Meteo forecast |
| `WebLookupSkill` | DuckDuckGo + page fetch |
| `ZettelkastenSkill` | Vault notes and tag taxonomy |
| `ExplorerSkill` | Bounded read-only investigation |
| `OrchestratorSkill` | Multi-skill coordination |
| `WorkflowSkill` | Run saved procedural workflows |
| `MapsSkill` | Directions, travel time, places search (CR-045) |
| `GmailSkill` | Read inbox, search, send, mark read (CR-046a) |
| `DynamicSkill` | Loads `.xochitl/skills/` |

---

## 7. Verification

- **Smoke**: `python smoke_test.py` — 146 passed, 0 failed (May 2026).
- **E2E**: `python end_to_end_test.py` — mocked full pipeline.

---

*For requirement IDs and change history, see `docs/spec/05-change-requests/` (CR-038 through CR-042 cover the latest JARVIS-runtime batch).*
