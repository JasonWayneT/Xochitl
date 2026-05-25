# Xochitl

Terminal-native personal AI system. Manages personal tasks via Notion, runs a BMAD → SDD → Code Generation pipeline for building new applications, and maintains persistent memory across sessions. Primary inference runs locally via Ollama; cloud models (Gemini, Claude) are called selectively for high-complexity tasks.

- **[CAPABILITIES.md](CAPABILITIES.md)** — verified feature manifest  
- **[XOCHITL_EXPLAINED.md](XOCHITL_EXPLAINED.md)** — conceptual guide (why/how, not a command manual)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| CLI | Click |
| Terminal UI | Rich |
| Local inference | Ollama |
| Primary local model | `phi4:14b-q4_K_M` |
| Router / fast model | `gemma2:2b` |
| Coding model | `qwen2.5-coder:14b-instruct-q4_K_M` |
| Embeddings | `nomic-embed-text` (default), `bge-m3` (recommended) |
| Cloud fallback | Gemini 2.0 Flash / Claude (optional, API key required) |
| Relational DB | SQLite |
| Vector DB | LanceDB (`~/.xochitl/lancedb/`) — `memories` + `workflow_intents` tables |
| Task integration | Notion API (`notion-client`) |

---

## Architecture

### Tiered Router (`src/router.py`)

All LLM calls go through `TieredRouter`. On each turn:

1. `gemma2:2b` classifies the query into a category (file_operation, coding, creative, simple_qa, etc.)
2. Category + confidence score determine the route: local, cloud, or specialist local
3. `_route_local()` trims history to the 10 most recent messages (heuristic summary of older history prepended) before calling the primary model
4. `_route_cloud()` compresses context and calls the configured cloud provider

Categories in `_FORCE_LOCAL_CATEGORIES` never escalate to cloud. Categories in `_LOCAL_SPECIALIZED_CATEGORIES` use specialist models (e.g., qwen2.5-coder for coding tasks).

### Context Assembly (`src/context_manager.py`)

System prompt assembled from five layers before every LLM call:

| Priority | Layer | Compactable |
|---|---|---|
| 1 | Identity Guard — SOUL.md persona + hardcoded language/behavior rules | Never |
| 2 | Preflight facts — CWD, active project, WIP queue count, platform | Never |
| 3 | Preferences — active user preferences from `preferences` table | Yes |
| 4 | Semantic memories — top-k LanceDB recall (HyDE) | Yes |
| 5 | Active skill schema — injected when skill scores ≥ 0.65 for this turn | Yes |

When total token count exceeds 75% of the model limit, layers 3–5 are compacted proportionally. Layers 1–2 are never modified.

### Memory Architecture

**SQLite tables (`src/database.py`):**

| Table | Purpose |
|---|---|
| `queue` | WIP task queue, max 3 rows |
| `session_history` | Full conversation transcripts |
| `preferences` | Structured user preferences (`preference_key`, `preference_value`, context) |
| `memory_facts` | Structured background facts — category, confidence (0–1), source, project, superseded_by |
| `workflows` | Procedural memory — reusable step sequences (CR-041) |

**LanceDB (`src/memory.py`, `src/workflow_vector.py`):**

- Table `memories` — semantic personal recall (HyDE: hypothetical answer embedded before search; falls back to direct query embedding)
- Table `workflow_intents` — separate embedding index for procedural workflow triggers (CR-042); not mixed with semantic facts
- Stored under `~/.xochitl/lancedb/`

**Procedural workflows (`src/workflows.py`, `src/skills/workflow_skill.py`):**

- `search_workflows_by_intent()` — hybrid keyword + embedding match (threshold 0.50)
- `_agent_loop()` injects `[PROCEDURAL WORKFLOW]` block when a workflow matches
- `/workflow save <name>` — LLM-distilled steps from session; `/workflow run <name>` — execute via skills

**BackgroundReview daemon (`src/background_review.py`):**

- Runs in a daemon thread; drops silently when the queue (maxsize=20) is full
- Min write interval: 30 seconds (`_MIN_WRITE_INTERVAL_SECS`)
- Per qualifying turn: (1) free-text observation → KB markdown file in `~/.xochitl/kb/`; (2) structured JSON extraction → `memory_facts` row (written only when `confidence ≥ 0.4`)
- Near-duplicate detection via 80-character prefix match at write time (no vector call)

### Event Bus (`src/events.py`)

`XochitlEventEmitter` — module-level singleton, thread-safe. Events fired during `_agent_loop`:

| Event | Payload |
|---|---|
| `routing_started` | `{"query": str}` |
| `skill_matched` | `{"skill": str, "score": float}` |
| `skill_started` | `{"skill": str, "params": list[str]}` |
| `skill_complete` | `{"skill": str, "success": bool}` |
| `llm_complete` | `{"route": str, "tokens_out": int}` |
| `hitl_required` | `{"action": str, "risk": str}` |

Terminal UI calls `_status.update()` directly for low latency. The event bus is the subscription channel for the future web SSE layer.

### Security Model (`src/security.py`)

- Reads: automatic within authorized roots
- Writes / deletes / mutating shell commands: require explicit user approval via HITL gate in `_agent_loop`
- Authorized roots configured via `xochitl authorize <path>`
- No access to paths outside authorized roots regardless of LLM instruction

### Staged Message Guard

`XochitlChat.start()` tracks `_consecutive_staged`. If 6 or more staged messages fire without a real `Prompt.ask()` turn, the staged queue is cleared and a warning is printed. Counter resets on real user input. Prevents runaway skill-chain loops.

### Terminal output (`src/terminal_output.py`, CR-039)

Semantic line prefixes (`done`, `action`, `warn`, `fail`), 80-column wrap, and `format_step(i, n, label)` for multi-step progress. Skill results can use compact action+body pairing via `src/action_disclosure.py` (CR-040).

### Runtime governance

| Module | Role |
|---|---|
| `src/governor.py` | Session token budget (`SessionGovernor`) — progressive local-only routing |
| `src/executor.py` | Action permission (`ActionGovernor`, `SafeExecutor`) — read auto, write/exec gated |
| `src/initiative.py` | Proactive alerts by category (CR-038) |

---

## Functional Breakdown

### Commands

| Command | Description |
|---|---|
| `xochitl chat` | Interactive conversational session (default) |
| `xochitl today` | Refresh and display WIP queue (top 3) |
| `xochitl done <num>` | Mark task complete, remove from queue |
| `xochitl plan "<name>"` | Decompose project into task queue |
| `xochitl sync` | Push completed tasks to Notion |
| `xochitl pull` | Fetch latest from Notion |
| `xochitl authorize <path>` | Grant file access to a directory |
| `xochitl --json <cmd>` | JSON output for `today`, `status`, `queue`, `sync`, `pull`, `tasks`, etc. |

**In-chat (selection):** `/workflows`, `/workflow save <name>`, `/workflow run <name>`, `/brief`, `/budget`, `/dismiss`

### Skills

| Skill | Match phrases | Description |
|---|---|---|
| `ZettelkastenSkill` | "open my vault", "add a note", "zettelkasten" | Note-taking with 4-tag budget, similarity-gated tag quarantine (60% overlap threshold), auto-promotion after 3 uses |
| `BMADSkill` | "I want to build…", "new project" | Business Model / Architecture / Design intake; scaffolds `projects/<id>/` |
| `SDDSkill` | SDD pipeline context | Generates requirements docs, manages `FR-*` IDs, traceability |
| `CodeSkill` | Code generation context | Scaffolds and generates code citing requirement IDs |
| `WeatherSkill` | Weather queries | Open-Meteo geocoding + forecast; no API key required |
| `WebLookupSkill` | Live information queries | DuckDuckGo search + page fetch; URL normalization for redirect handling |
| `NotionSkill` | "sync tasks", "pull from notion" | Notion PARA sync |
| `ExplorerSkill` | Investigative / research phrasing | Bounded read-only file exploration |
| `OrchestratorSkill` | Multi-step coordination | Delegates across skills |
| `WorkflowSkill` | `/workflow run`, strong workflow match | Executes saved procedural workflows |
| `DynamicSkill` | Any `.xochitl/skills/` directory | User-defined skills; auto-proposed after repeating multi-step patterns |

---

## Model Configuration

Set via environment variables or `xochitl config set KEY VALUE`:

```env
LOCAL_MODEL=phi4:14b-q4_K_M
ROUTER_MODEL=gemma2:2b
LOCAL_THINKING_MODEL=phi4:14b-q4_K_M
LOCAL_CODING_MODEL=qwen2.5-coder:14b-instruct-q4_K_M
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_URL=http://localhost:11434

CLOUD_PROVIDER=gemini
CLOUD_MODEL=gemini-2.0-flash
GEMINI_API_KEY=
ANTHROPIC_API_KEY=
```

**Ollama performance settings** — run `scripts/start_ollama.ps1` once to set permanently as Windows user environment variables:

```env
OLLAMA_KEEP_ALIVE=30m
OLLAMA_NUM_PARALLEL=2
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_MAX_LOADED_MODELS=2
```

---

## BMAD → SDD → Code Pipeline

1. `xochitl chat` → "I want to build X" → `BMADSkill` creates `projects/<id>/bmad/`
2. BMAD walks Business Model, Architecture, and Design artifacts
3. `SDDSkill` generates `projects/<id>/specs/core-features.md` with `FR-*` requirement IDs
4. `CodeSkill` scaffolds `projects/<id>/src/` with code that cites requirement IDs in comments
5. Bugs are diagnosed against specs; fixes reference the originating requirement

---

## Project Structure

```
./
├── src/
│   ├── cli.py                   # Entry point
│   ├── chat.py                  # Conversational loop, skill dispatch, event emission
│   ├── router.py                # TieredRouter — classification and routing
│   ├── context_manager.py       # System prompt assembly (5-layer stack)
│   ├── context_loader.py        # History trim, compression, prompt building
│   ├── database.py              # SQLite schema, helpers, memory_facts
│   ├── memory.py                # LanceDB semantic memory, HyDE recall
│   ├── workflows.py             # Procedural memory search, distill, execute
│   ├── workflow_vector.py       # LanceDB workflow_intents index
│   ├── terminal_output.py       # Terminal visual grammar (CR-039)
│   ├── action_disclosure.py     # Compact reasoning disclosure (CR-040)
│   ├── governor.py              # Session token budget
│   ├── executor.py              # ActionGovernor / SafeExecutor
│   ├── initiative.py            # Controlled proactive alerts
│   ├── background_review.py     # BackgroundReview daemon
│   ├── events.py                # XochitlEventEmitter — web SSE groundwork
│   ├── security.py              # Path sandboxing
│   ├── llm_interface.py         # Provider abstraction (local / cloud)
│   ├── model_manager.py         # Model selection logic
│   └── skills/
│       ├── bmad_skill.py
│       ├── sdd_skill.py
│       ├── code_skill.py
│       ├── zettelkasten_skill.py
│       ├── zettelkasten_process.py
│       ├── zettelkasten_scaffold.py
│       ├── weather_skill.py
│       ├── web_lookup_skill.py
│       ├── notion_skill.py
│       ├── explorer_skill.py
│       ├── orchestrator_skill.py
│       ├── workflow_skill.py
│       └── dynamic_skill.py
├── CAPABILITIES.md              # Capability manifest (user-facing)
├── XOCHITL_EXPLAINED.md         # Conceptual learning guide
├── docs/spec/                   # Requirements registry, CRs, traceability matrix
│   ├── 02-requirements-registry.md
│   ├── 05-change-requests/
│   └── 06-traceability/traceability-matrix.md
├── scripts/
│   └── start_ollama.ps1         # One-time Ollama env var setup (run once, permanent)
├── prompts/
│   └── system_xochitl.txt       # System prompt template (fallback path for context_manager)
├── .env.example                 # All configurable env vars with inline comments
├── SOUL.md.example              # Persona template
├── conversation.config.example.yaml
├── smoke_test.py                # Unit/regression suite (146 tests, May 2026)
└── end_to_end_test.py           # Mocked full pipeline flow
```

---

## Testing

```powershell
python smoke_test.py        # Expected: 146 passed, 0 failed
python end_to_end_test.py   # Mocked full pipeline flow
```

Compile check:

```powershell
python -m py_compile src/events.py src/database.py src/context_loader.py src/memory.py src/background_review.py src/router.py src/chat.py
```

---

## Key Invariants

- WIP queue holds exactly 0–3 rows at all times
- All LLM calls route through `TieredRouter` — no direct model calls from skills or chat
- All file operations gate through `src/security.py`
- Every generated code file cites at least one `# Implements <FR-ID>` comment
- SOUL.md content is never compacted out of the system prompt
- BackgroundReview never blocks the main thread
