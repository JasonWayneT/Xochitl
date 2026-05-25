# Requirements Registry

This is the canonical list of Xochitl requirements. Feature specs, tasks, tests, and code changes must trace back here.

## ID naming convention

Xochitl uses area-scoped IDs: `<PREFIX>-<AREA>-<NNN>`

| Area | Scope |
|---|---|
| `CORE` | Task queue, CLI commands, daily workflow |
| `API` | External integrations (Notion, LLM providers) |
| `UI` | Terminal UI (Rich output, interactive prompts) |
| `DATA` | SQLite schema, migrations, ChromaDB |
| `AUTH` | Security sandboxing, path restrictions |
| `SDD` | BMAD → SDD → Code generation pipeline |
| `ZTK` | Zettelkasten vault management, note pipeline, tag system |
| `ORCH` | Orchestration, routing, intent classification, skill dispatch |

| Prefix | Category | Example |
|---|---|---|
| `FR` | Functional requirement | `FR-CORE-001` |
| `NFR` | Non-functional requirement | `NFR-CORE-001` |
| `ARCH` | Architecture requirement | `ARCH-SDD-001` |
| `DATA` | Data requirement | `DATA-DATA-001` |
| `SEC` | Security/privacy requirement | `SEC-AUTH-001` |
| `INT` | Integration requirement | `INT-API-001` |
| `OPS` | Operations requirement | `OPS-CORE-001` |
| `AC` | Acceptance criterion | `AC-CORE-001` |
| `TASK` | Implementation task | `TASK-CORE-001` |
| `TEST` | Test case | `TEST-CORE-001` |
| `BUG` | Known bug or regression | `BUG-CORE-001` |
| `ADR` | Architecture decision record | `ADR-001` |
| `CR` | Change request | `CR-001` |

## Status values

- `draft`: proposed but not accepted
- `accepted`: approved source of truth
- `implemented`: implemented in code
- `verified`: implemented and validated
- `deprecated`: no longer active
- `superseded`: replaced by another ID

## Requirement records

### Core — Task Queue and CLI Commands

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-CORE-001` | functional | P0 | accepted | `xochitl today` refreshes the daily queue and displays the top 3 prioritized tasks | `AC-CORE-001` | `BMAD-SRC-001` | WIP limit enforced |
| `FR-CORE-002` | functional | P0 | accepted | `xochitl done <num>` marks the numbered task as complete and removes it from the queue | `AC-CORE-002` | `BMAD-SRC-001` | |
| `FR-CORE-003` | functional | P1 | accepted | `xochitl plan "<name>"` decomposes a project name into tasks and inserts them | `AC-CORE-003` | `BMAD-SRC-001` | |
| `FR-CORE-004` | functional | P1 | accepted | `xochitl chat` opens an interactive conversational session with intent classification | `AC-CORE-004` | `BMAD-SRC-001` | Default command |
| `NFR-CORE-001` | non-functional | P0 | accepted | Non-LLM CLI commands (`today`, `done`, `sync`, `pull`) complete in <2 seconds | `AC-CORE-005` | `BMAD-SRC-001` | |
| `NFR-CORE-002` | non-functional | P0 | accepted | The `queue` table holds exactly 0–3 rows at all times (WIP limit) | `AC-CORE-006` | `BMAD-SRC-001` | Hard architectural constraint |

### API — Notion Integration

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-API-001` | functional | P1 | accepted | `xochitl sync` pushes completed tasks to Notion using PARA methodology | `AC-API-001` | `BMAD-SRC-001` | |
| `FR-API-002` | functional | P1 | accepted | `xochitl pull` fetches the latest tasks from Notion and updates the local queue | `AC-API-002` | `BMAD-SRC-001` | |
| `FR-API-003` | functional | P1 | implemented | Xochitl can perform internet lookup through a web-search skill for live external information requests (for example weather), without requiring a dedicated weather API | `AC-CR006-001`, `AC-CR006-002` | `CR-006` | WebLookupSkill |
| `FR-API-004` | functional | P1 | implemented | Xochitl can answer weather requests through a no-key structured weather provider before falling back to generic web lookup | `AC-CR007-001`, `AC-CR007-002`, `AC-CR007-003` | `CR-007` | WeatherSkill / Open-Meteo |
| `INT-API-001` | integration | P0 | accepted | All Notion calls go through `src/notion_sync.py` using the `notion-client` library | `AC-API-003` | `BMAD-SRC-001` | |

### Data — SQLite and ChromaDB

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `DATA-DATA-001` | data | P0 | accepted | All SQLite schema definitions and queries reside exclusively in `src/database.py` | `AC-DATA-001` | `BMAD-SRC-001` | No raw SQL elsewhere |
| `DATA-DATA-002` | data | P1 | accepted | Session history is stored in SQLite and queryable by the conversational loop | `AC-DATA-002` | `BMAD-SRC-001` | |
| `DATA-DATA-003` | data | P2 | accepted | Long-term memory is stored in ChromaDB for vector similarity retrieval | `AC-DATA-003` | `BMAD-SRC-001` | |

### Auth — Security and Sandboxing

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `SEC-AUTH-001` | security | P0 | accepted | All file operations are restricted to allowed roots defined in `src/security.py` | `AC-AUTH-001` | `BMAD-SRC-001` | Path sandboxing |
| `SEC-AUTH-002` | security | P0 | accepted | Overwriting or deleting files requires explicit user confirmation via FileTools | `AC-AUTH-002` | `BMAD-SRC-001` | Reads are automatic |

### Architecture — LLM Routing and SDD Pipeline

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `ARCH-SDD-001` | architecture | P0 | accepted | All LLM calls route through `src/router.py` (TieredRouter); no direct model calls elsewhere | `AC-SDD-001` | `BMAD-SRC-001` | Local vs cloud split |
| `FR-SDD-001` | functional | P1 | accepted | The SDD pipeline initializes a project under `projects/<id>/` with BMAD, specs, and src subdirectories | `AC-SDD-002` | `BMAD-SRC-001` | |
| `FR-SDD-002` | functional | P1 | accepted | The SDD pipeline generates `specs/core-features.md` from BMAD artifacts | `AC-SDD-003` | `BMAD-SRC-001` | |
| `FR-SDD-003` | functional | P1 | accepted | All code generated by the SDD pipeline cites requirement IDs in inline comments | `AC-SDD-004` | `BMAD-SRC-001` | e.g., `# Implements FR-CORE-001` |
| `FR-SDD-004` | functional | P2 | accepted | The issue tracking skill analyzes bugs against specs, updates specs, and generates fix code | `AC-SDD-005` | `BMAD-SRC-001` | |

### UI — Conversation Layer Hardening (CR-002)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-UI-001` | functional | P1 | implemented | TUI status bar shows live sub-task feed with elapsed timer during LLM reasoning | `AC-CR002-003` | `CR-002` | Rich Live display |
| `FR-UI-002` | functional | P1 | implemented | Smart Ctrl-C: first press cancels active tool or clears input; second press within 1.2s exits | `AC-CR002-003` | `CR-002` | 2-stage exit |
| `FR-UI-003` | functional | P2 | implemented | File paths in agent output are formatted as OSC 8 terminal hyperlinks | `AC-CR002-005` | `CR-002` | Windows Terminal / VS Code |
| `FR-UI-004` | functional | P1 | implemented | Chat responses are rendered incrementally for plain-text turns, with markdown-safe full-render fallback | `AC-CR005-002`, `AC-CR005-003` | `CR-005` | Streaming UX |
| `FR-ORCH-003` | functional | P0 | implemented | PreFlight Fact Injection: every system prompt includes [SYSTEM_FACTS] block with CWD, project, WIP, and platform | `AC-CR002-001` | `CR-002` | Prevents LLM hallucination |
| `FR-ORCH-004` | functional | P0 | implemented | Provenance Tagging: history messages tagged [SOURCE: USER] vs [SOURCE: SYSTEM] to prevent role confusion | `AC-CR002-002` | `CR-002` | Via ContextManager |
| `NFR-PERF-004` | non-functional | P1 | implemented | ContextManager enforces token budget at 75% of model limit, triggering compaction before overflow | `AC-CR002-004` | `CR-002` | Local: 6k, Cloud: 28k |
| `NFR-PERF-005` | non-functional | P1 | implemented | TieredRouter tracks rolling latency per provider via exponential moving average | `AC-CR002-005` | `CR-002` | OpenClaude SmartRouter pattern |

### Conversation Layer — LLM-Native Skill Dispatch (CR-003)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-005` | functional | P0 | accepted | Each skill exposes `tool_definition()` descriptor injected into every system prompt so the LLM knows what it can invoke | `AC-CR003-001`, `AC-CR003-002` | `CR-003` | Via SkillManifestEngine |
| `FR-ORCH-006` | functional | P0 | accepted | All response paths assemble the system prompt via `ContextManager` — no ad-hoc `build_system_prompt()` calls outside it | `AC-CR003-004` | `CR-003` | Universal CM |
| `FR-ORCH-007` | functional | P1 | accepted | Natural confirmation: pending-action yes/no detection falls back to an LLM micro-call when exact-match against `_CONFIRM_YES`/`_CONFIRM_NO` fails | `AC-CR003-003` | `CR-003` | |
| `FR-ORCH-008` | functional | P0 | accepted | Agent loop: `process_message()` parses LLM responses for `<skill_call name="X">{}</skill_call>` markers and auto-executes the named skill, appending the result to the response | `AC-CR003-001`, `AC-CR003-002` | `CR-003` | |
| `FR-ORCH-009` | functional | P1 | accepted | Skill-aware history: tool invocations and results are stored as `role=tool` turns and serialized as `[Tool: X]\n{result}` assistant messages for LLM context | `AC-CR003-005` | `CR-003` | |
| `NFR-PERF-006` | non-functional | P1 | accepted | `<skill_call>` regex parsing adds <10ms per turn; re-synthesis LLM call only fires when a skill executes | — | `CR-003` | |

### Conversation Layer - Conversational Intelligence (CR-004)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-010` | functional | P0 | implemented | Xochitl classifies each chat turn into exploration, execution, planning, clarification, productivity, emotional/support, or skill-learning intent before tool selection | `AC-CR004-001` | `CR-004` | Structured intent object |
| `FR-ORCH-011` | functional | P0 | implemented | Xochitl chains read-only exploration actions automatically and requires a plan plus explicit approval before writes, deletes, or mutating commands | `AC-CR004-002`, `AC-CR004-003` | `CR-004` | Claude Code-style exploration with safety gate |
| `FR-ORCH-012` | functional | P0 | implemented | Xochitl loads persona and behavior instructions from project-local overrides, `~/.xochitl/`, repo fallback templates, and a central system prompt template through the existing context assembly path | `AC-CR004-004`, `AC-CR004-013` | `CR-004` | Persona architecture, including Latina/Mexican voice |
| `DATA-DATA-004` | data | P0 | implemented | Xochitl stores structured user preferences separately from semantic memory and recalls relevant preferences at the start of conversations | `AC-CR004-005`, `AC-CR004-006` | `CR-004` | Preference table/tools |
| `DATA-DATA-005` | data | P1 | implemented | Xochitl preloads relevant long-term semantic memories for each turn using meaning-based retrieval while respecting token budgets | `AC-CR004-007` | `CR-004` | Memory bank preload |
| `FR-ORCH-013` | functional | P1 | implemented | Xochitl detects successful reusable multi-step workflows and offers to create a skill after the task completes | `AC-CR004-008` | `CR-004` | Balanced trigger |
| `FR-ORCH-014` | functional | P1 | implemented | Xochitl loads global and project-specific dynamic skills from filesystem skill folders with metadata, examples, and optional assets | `AC-CR004-009` | `CR-004` | Global and project skills |
| `FR-SDD-005` | functional | P0 | implemented | Project initialization creates BMAD artifacts, SDD workflow scaffolding, and project-local agent instructions explaining the BMAD to SDD to code process | `AC-CR004-010` | `CR-004` | Init project caveat |
| `NFR-PERF-007` | non-functional | P0 | proposed | Conversational context assembly prefers selective retrieval and mode-specific context to minimize token use and reduce confusion | `AC-CR004-011` | `CR-004` | Token discipline |
| `ARCH-SDD-002` | architecture | P0 | proposed | Conversational model calls continue to route through `TieredRouter`; no new raw model API calls are introduced | `AC-CR004-012` | `CR-004` | Routing preservation |

### Orchestration — Routing and Intent Classification (CR-008)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-015` | functional | P0 | implemented | Zettelkasten intent is detected in `_fast_classify()` before the bare-path `file_operations` check so a Windows/Unix path in the query cannot hijack routing | `AC-CR008-001` | `CR-008` | `_ZETTEL_RE` guard |

### UI — Output Quality (CR-008)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `NFR-UI-004` | non-functional | P2 | implemented | Model manager routing decisions are written to `logs/model_manager.log` only; no `[Model Manager]` output to stderr or terminal | `AC-CR008-011` | `CR-008` | Removes console noise |
| `NFR-UI-005` | non-functional | P1 | implemented | Xochitl responds in English or Spanish only unless the user explicitly requests another language for that message | `AC-CR008-012` | `CR-008` | System prompt language rule |
| `NFR-UI-006` | non-functional | P2 | implemented | Flower thinking animation runs at ≥10 fps (tick interval ≤0.1s, `refresh_per_second` ≥10) | — | `CR-008` | `_StatusContext` |

### Orchestration — Conversational Intelligence Refactor (CR-009)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-016` | functional | P0 | implemented | SOUL.md content is merged into the Identity Guard block and is never evicted or compacted regardless of token budget pressure | `AC-CR009-001` | `CR-009` | `context_manager.py` guard_text |
| `FR-ORCH-017` | functional | P0 | implemented | Every `_agent_loop()` call scores all loaded skills via `can_handle()` before the LLM call; the highest-scoring skill above 0.65 has its schema injected into the system prompt for that turn only | `AC-CR009-002` | `CR-009` | `_SKILL_INJECT_THRESHOLD = 0.65` |
| `FR-ORCH-018` | functional | P1 | implemented | A daemon thread runs after every completed turn, extracts a single passive observation about the user from the exchange, and writes it to KnowledgeBase Tier 2 without blocking the main thread | `AC-CR009-003`, `AC-CR009-004` | `CR-009` | `src/background_review.py` |
| `FR-ORCH-019` | functional | P0 | implemented | `router.route()` uses a single `_classify()` call for intent; `_fast_classify()` is no longer invoked in the routing path, eliminating dual-classifier disagreement | `AC-CR009-005` | `CR-009` | `src/router.py` |
| `NFR-PERF-008` | non-functional | P1 | implemented | The background review daemon uses a bounded queue (maxsize=20), drops silently when full, and writes at most once per 30 seconds to prevent KB noise | `AC-CR009-004` | `CR-009` | `BackgroundReview._queue` |

### ZTK — Zettelkasten Vault and Note Management (CR-008)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ZTK-001` | functional | P0 | implemented | `ZettelkastenSkill` is registered in `_builtin_skills` and its `tool_definition()` is present in the LLM skill manifest at every chat turn | `AC-CR008-002` | `CR-008` | Enables LLM-driven skill dispatch |
| `FR-ZTK-002` | functional | P1 | implemented | Vault path resolves via a 4-step priority chain: (1) session module state, (2) `VAULT_PATH` env var, (3) `~/.xochitl/vault_config.json`, (4) filesystem scan of well-known locations for vault marker folders | `AC-CR008-003`, `AC-CR008-004` | `CR-008` | Auto-discovery |
| `FR-ZTK-003` | functional | P1 | implemented | `enter_mode()` checks for Fleeting/Permanent/Literature folders before entering; if absent, calls `scaffold_vault()` automatically | `AC-CR008-005` | `CR-008` | One-step vault init |
| `FR-ZTK-004` | functional | P1 | implemented | Natural language path hints are extracted from the user message and passed to `enter_mode()`: absolute path → used directly; "here"/"this folder" → cwd; "in [name]" → scanned against known roots | `AC-CR008-006` | `CR-008` | `_extract_path_hint()` |
| `FR-ZTK-005` | functional | P1 | implemented | Tag suggestions per note are capped at 4 (tag budget); the strongest matching active tags are selected first | `AC-CR008-007` | `CR-008` | `_TAG_BUDGET = 4` |
| `FR-ZTK-006` | functional | P1 | implemented | A similarity gate computes token overlap between a proposed new tag and all active tags; if overlap ≥60% the existing tag is suggested instead | `AC-CR008-008` | `CR-008` | `_find_similar_tag()` |
| `FR-ZTK-007` | functional | P1 | implemented | New tags that pass the similarity gate enter `## Proposed Tags` in `vault-taxonomy.md` with a use counter; they auto-promote to `## Active Tags` after 3 uses and a promotion message is shown to the user | `AC-CR008-009`, `AC-CR008-010` | `CR-008` | Quarantine → Promotion |

## Acceptance criteria

| ID | Parent requirement | Scenario | Given | When | Then | Status |
|---|---|---|---|---|---|---|
| `AC-CORE-001` | `FR-CORE-001` | Queue refresh | The local database has pending tasks | User runs `xochitl today` | The top 3 tasks are displayed and the queue is updated | accepted |
| `AC-CORE-002` | `FR-CORE-002` | Mark complete | A numbered task is in the queue | User runs `xochitl done <num>` | The task is marked complete and removed from queue | accepted |
| `AC-CORE-003` | `FR-CORE-003` | Project decomposition | A project name is provided | User runs `xochitl plan "<name>"` | The project is decomposed into tasks and inserted into the queue | accepted |
| `AC-CORE-004` | `FR-CORE-004` | Chat session | Xochitl is running | User runs `xochitl chat` | An interactive session opens with intent classification routing to the appropriate skill | accepted |
| `AC-CORE-005` | `NFR-CORE-001` | Command latency | A non-LLM command is invoked | The command executes | The response is returned in <2 seconds | accepted |
| `AC-CORE-006` | `NFR-CORE-002` | WIP limit | The queue has 3 items | A new task is inserted | The insert is rejected or the user is prompted to complete an existing task first | accepted |
| `AC-API-001` | `FR-API-001` | Notion sync push | Completed tasks exist locally | User runs `xochitl sync` | Completed tasks are pushed to the Notion workspace under the correct PARA database | accepted |
| `AC-API-002` | `FR-API-002` | Notion pull | Notion has tasks newer than the local state | User runs `xochitl pull` | Local queue is updated with the latest Notion tasks | accepted |
| `AC-API-003` | `INT-API-001` | Notion API isolation | Any component needs Notion data | It calls `src/notion_sync.py` | The call routes through `notion-client` and not any other HTTP mechanism | accepted |
| `AC-DATA-001` | `DATA-DATA-001` | SQL isolation | Any component needs database access | It executes a query | The query is defined in `src/database.py` | accepted |
| `AC-DATA-002` | `DATA-DATA-002` | Session history | A conversational session runs | The session ends | The session transcript is persisted in SQLite | accepted |
| `AC-DATA-003` | `DATA-DATA-003` | Vector retrieval | A memory lookup is requested | ChromaDB is queried | The top-k relevant memories are returned | accepted |
| `AC-AUTH-001` | `SEC-AUTH-001` | Path restriction | A file operation is attempted outside the allowed roots | The operation is executed | `src/security.py` raises an error and the operation is blocked | accepted |
| `AC-AUTH-002` | `SEC-AUTH-002` | Overwrite confirmation | An overwrite is requested | FileTools processes the request | The user is prompted to confirm before the file is overwritten | accepted |
| `AC-SDD-001` | `ARCH-SDD-001` | LLM isolation | Any component needs an LLM response | It calls `src/router.py` | TieredRouter selects local or cloud model and returns the response | accepted |
| `AC-SDD-002` | `FR-SDD-001` | Project init | A new project name is given | The SDD pipeline initializes | `projects/<id>/bmad/`, `projects/<id>/specs/`, and `projects/<id>/src/` directories are created | accepted |
| `AC-SDD-003` | `FR-SDD-002` | Spec generation | BMAD artifacts exist for a project | Spec generation runs | `projects/<id>/specs/core-features.md` is created with requirement IDs | accepted |
| `AC-SDD-004` | `FR-SDD-003` | Code traceability | Code generation produces a file | The file is written | At least one `# Implements <ID>` comment appears per function implementing a requirement | accepted |
| `AC-SDD-005` | `FR-SDD-004` | Issue analysis | A bug report is submitted | The issue skill runs | A JSON analysis is returned classifying the issue and proposing spec and code changes | accepted |
| `AC-CR002-001` | `FR-ORCH-003` | Fact injection | Xochitl starts a chat session | User asks "what folder are you in?" | Response contains the actual Windows path from CWD, not a generic LLM reply | implemented |
| `AC-CR002-002` | `FR-ORCH-004` | Provenance tagging | A chat session is running | System messages are injected into history | LLM receives messages tagged [SOURCE: USER] or [SOURCE: SYSTEM], preventing role confusion | implemented |
| `AC-CR002-003` | `FR-UI-001`, `FR-UI-002` | Smart Ctrl-C | Xochitl chat is running | User presses Ctrl-C once | Input is cleared or active tool is cancelled; a second press within 1.2s exits | implemented |
| `AC-CR002-004` | `NFR-PERF-004` | Token budget | A large file is injected | Token count exceeds 75% of model limit | ContextManager compacts lower-priority sections before sending to LLM | implemented |
| `AC-CR002-005` | `NFR-PERF-005` | Latency tracking | A local or cloud LLM call completes | The result is returned | TieredRouter updates the provider's rolling average latency | implemented |
| `AC-CR003-001` | `FR-ORCH-005`, `FR-ORCH-008` | Direct skill execution | User says "sync my notion tasks" | process_message runs | NotionSkill executes and returns result without a separate confirmation turn | accepted |
| `AC-CR003-002` | `FR-ORCH-005`, `FR-ORCH-008` | Skill from manifest | User says "I want to build a recipe tracking app" | process_message runs | BMADSkill fires via skill manifest, not keyword matching | accepted |
| `AC-CR003-003` | `FR-ORCH-007` | Natural confirmation | User says "go for it" / "sounds good" after a pending action | `_handle_action_confirmation` runs | The LLM micro-call classifies the response as "yes" and the action executes | accepted |
| `AC-CR003-004` | `FR-ORCH-006` | Universal CM | Any `_handle_*` method assembles a system prompt | The method runs | It calls `cm.assemble_system_prompt()` — no direct `build_system_prompt()` call | accepted |
| `AC-CR003-005` | `FR-ORCH-009` | Tool history | A skill executes via `<skill_call>` | `_clean_history()` is called | The tool turn appears as an assistant message prefixed `[Tool: SkillName]` | accepted |
| `AC-CR005-001` | `FR-UI-001` | Non-hanging thinking UI | Chat is waiting on model/tool work | A turn takes more than 1 second | Flower animation continues updating with `thinking...` and a live working note; it does not appear frozen | implemented |
| `AC-CR005-002` | `FR-UI-004` | Incremental response rendering | Assistant returns plain text | Xochitl prints the response | Output appears incrementally rather than as one final blob | implemented |
| `AC-CR005-003` | `FR-UI-004` | Markdown safety | Assistant returns markdown-heavy content | Xochitl prints the response | Renderer falls back to full markdown print so formatting stays intact | implemented |
| `AC-CR006-001` | `FR-API-003` | Weather via internet | User asks for weather in a city | Xochitl routes to web lookup skill | Xochitl returns a summary from public web results without using a dedicated weather API | implemented |
| `AC-CR006-002` | `FR-API-003` | General live lookup | User asks for current online info | Skill runs | Xochitl returns concise source-backed snippets from fetched pages | implemented |
| `AC-BUG-API-001` | `FR-API-003` | Weather result redirect regression | DuckDuckGo returns weather links as HTML-escaped redirect URLs | WebLookupSkill parses and fetches results | Xochitl normalizes to real destination URLs and returns fetched text or search snippets instead of the "found links" failure | implemented |
| `AC-CR007-001` | `FR-API-004` | Current weather | User asks for weather in a city | Xochitl routes to WeatherSkill | Xochitl returns current conditions, feels-like temperature, wind, humidity, precipitation, and today's high/low from Open-Meteo | implemented |
| `AC-CR007-002` | `FR-API-004` | Location geocoding | User provides a city/state or city/country location | WeatherSkill runs | The skill resolves the location through Open-Meteo geocoding and uses latitude/longitude for forecast lookup | implemented |
| `AC-CR007-003` | `FR-API-004` | No API key required | Xochitl is run without weather API secrets | User asks for weather | Weather lookup succeeds without reading environment API keys | implemented |
| `AC-CR007-004` | `FR-API-004`, `DATA-DATA-004` | Default weather location | User asks for weather without a specific location and a global weather-location preference exists | WeatherSkill runs | Xochitl uses the stored default geographic context before asking for clarification | implemented |

| `AC-CR004-001` | `FR-ORCH-010` | Intent classification | A user sends a chat message | Xochitl processes the turn | The turn has a structured intent used by routing and tool selection | implemented |
| `AC-CR004-002` | `FR-ORCH-011` | Read-only chain | User asks "help me understand this project" | Xochitl can inspect files | It performs bounded read-only exploration without asking for each read | implemented |
| `AC-CR004-003` | `FR-ORCH-011` | Mutating action | User asks Xochitl to fix a bug | Xochitl identifies code changes | It presents a plan and waits for approval before editing files or running mutating commands | implemented |
| `AC-CR004-004` | `FR-ORCH-012` | Persona loading | A chat session starts | Context is assembled | The system prompt includes persona and behavior layers from the configured artifacts | implemented |
| `AC-CR004-013` | `FR-ORCH-012` | Cultural voice | Xochitl responds in casual or supportive conversation | Persona guidance is active | She blends warmth, Mexican/Latina cultural texture, and light A1-A2 Spanish words or short phrases without overusing Spanish or switching into full untranslated Spanish | implemented |
| `AC-CR004-005` | `DATA-DATA-004` | Preference recall | A stored user preference is relevant | A new session or turn begins | Xochitl recalls and applies the preference without requiring the user to repeat it | implemented |
| `AC-CR004-006` | `DATA-DATA-004` | Preference save | User states a stable preference | The turn completes | Xochitl records the preference through an explicit preference save path | implemented |
| `AC-CR004-007` | `DATA-DATA-005` | Memory preload | A current message relates to prior experience | Context is assembled | Relevant semantic memories are injected within the token budget | implemented |
| `AC-CR004-008` | `FR-ORCH-013` | Skill proposal | A multi-step reusable workflow succeeds | The final response is generated | Xochitl offers to create a skill without forcing it | implemented |
| `AC-CR004-009` | `FR-ORCH-014` | Dynamic skill loading | A valid skill folder exists globally or in the project | Xochitl starts or refreshes skills | The skill is available for conversational tool selection | implemented |
| `AC-CR004-010` | `FR-SDD-005` | Project init | User asks to initialize a project | BMADSkill runs | The project includes BMAD files, SDD scaffolding, and project-local agent instructions | implemented |
| `AC-CR004-011` | `NFR-PERF-007` | Token discipline | The active project has large docs | Xochitl handles a normal productivity chat | It does not inject unrelated BMAD/SDD context unless project workflow intent is detected | proposed |
| `AC-CR004-012` | `ARCH-SDD-002` | Routing preservation | The conversational layer needs an LLM response | It calls a model | The call goes through `TieredRouter` | proposed |

| `AC-CR009-001` | `FR-ORCH-016` | Soul guard | Xochitl is in a long session with many large file injections | Token budget is exceeded | SOUL.md content and Identity Guard text remain in every system prompt; compaction touches only behavior/preferences/memory/files | implemented |
| `AC-CR009-002` | `FR-ORCH-017` | Skill injection | A skill scores ≥0.65 for the user's message | `_agent_loop()` runs | The system prompt includes an `## Active Skill` block with that skill's schema and no other skill schemas | implemented |
| `AC-CR009-003` | `FR-ORCH-018` | Passive observation write | User corrects Xochitl or expresses a clear preference | The turn completes | A `passive_learning_YYYY-MM-DD.md` entry appears in `~/.xochitl/kb/` within 60 seconds | implemented |
| `AC-CR009-004` | `FR-ORCH-018`, `NFR-PERF-008` | Daemon non-blocking | Background review raises an exception or the KB write fails | `BackgroundReview._process()` runs | The main thread is unaffected; the exception is swallowed and logged at DEBUG level | implemented |
| `AC-CR009-005` | `FR-ORCH-019` | Single classifier | Any chat message triggers routing | `router.route()` runs | Exactly one `_classify()` call is made; no `_fast_classify()` call appears in the routing path | implemented |
| `AC-CR009-006` | All CR-009 | Smoke test regression | All changes are applied | `smoke_test.py` executes | 27 tests pass, 0 failures | implemented |
| `AC-CR010-001` | `FR-ORCH-020` | Event emission | `_agent_loop` completes a turn | At least `routing_started` and `llm_complete` events are emitted on the module-level emitter | Adding a subscriber at runtime does not affect the chat response | implemented |
| `AC-CR010-002` | `FR-ORCH-021` | History trim | A session has more than 10 messages | `_route_local()` is called | It receives a list whose first two entries are the summary context block and acknowledgement, followed by exactly 10 real messages | implemented |
| `AC-CR010-003` | `NFR-UI-007` | Staged loop guard | 6 or more staged messages fire consecutively without a real `Prompt.ask()` turn | The staged queue is cleared and a `⚠ Staged message loop detected` warning is printed | The counter resets to 0 on the next real user input | implemented |
| `AC-CR010-004` | `DATA-DATA-006` | Structured fact write | `BackgroundReview._write()` runs and extraction returns a fact with `confidence ≥ 0.4` | `db.upsert_memory_fact()` is called | The fact is stored in `memory_facts` with the correct category enum value | implemented |
| `AC-CR010-005` | `DATA-DATA-007` | HyDE embedding | `VectorMemory._hyde_embed()` calls the local router model with `_HYDE_PROMPT` | The model returns non-empty content | The embedding is computed on the generated passage, not the original query; a model error causes clean fallback to `_embed(query)` with no exception propagating | implemented |
| `AC-CR010-006` | `OPS-CORE-001` | Ollama startup | `scripts/start_ollama.ps1` is executed | All five Ollama env vars are set before `ollama serve` is invoked | `.env.example` lists every tunable with inline comments | implemented |
| `AC-CR011-001` | `NFR-UI-008` | Boot banner | Xochitl starts a chat session | Boot banner is printed | The subtitle reads "Personal AI System", not "Chief of Staff" | implemented |
| `AC-CR011-002` | `NFR-UI-008` | Identity Guard | Any chat session runs | System prompt is assembled | The Identity Guard line reads "personal AI system", not "Chief of Staff" | implemented |
| `AC-CR011-003` | `NFR-UI-008` | Documentation | Any active doc file is read | The string "Chief of Staff" is searched across non-archive files | Zero matches | implemented |
| `AC-CR012-001` | `FR-ORCH-022` | Me.md present | `~/.xochitl/Me.md` exists with content | System prompt is assembled | `## About the User` block appears between Identity Guard and Facts sections | implemented |
| `AC-CR012-002` | `FR-ORCH-022` | Me.md absent | No Me.md file found in any search path | System prompt is assembled | System prompt is unchanged — no empty section injected | implemented |
| `AC-CR012-003` | `NFR-ORCH-001` | Token compaction | Token budget is exceeded | `user_profile.compact()` runs | Top sections (Who I am, Domains) preserved; truncation from bottom with compaction note | implemented |
| `AC-CR012-004` | `FR-ORCH-022` | Search path priority | Both `cwd/.xochitl/Me.md` and `~/.xochitl/Me.md` exist | `UserProfileEngine.ingest()` runs | The `cwd/.xochitl/Me.md` version is used | implemented |
| `AC-CR013-001` | `NFR-ORCH-002` | Long Me.md | `Me.md` has 81+ lines | `UserProfileEngine.ingest()` runs | A dim warning is printed: line count and a note that lower sections may compact | implemented |
| `AC-CR013-002` | `NFR-ORCH-002` | Normal Me.md | `Me.md` has ≤80 lines | `UserProfileEngine.ingest()` runs | No warning is printed | implemented |
| `AC-CR013-003` | `NFR-ORCH-002` | Missing Me.md | No `Me.md` file found | `UserProfileEngine.ingest()` runs | No warning is printed | implemented |
| `AC-CR013-004` | `FR-ORCH-022` | Warning does not block | `Me.md` has 120 lines | `UserProfileEngine.ingest()` runs | File still loads fully; `self._content` contains the full file | implemented |
| `AC-CR031-001` | `FR-UI-005` | Real token streaming | User sends a conversational message (no skill matched) | `_agent_loop` runs with `_stream=True` | Tokens appear on screen progressively as the model generates them, not after a full batch wait | implemented |
| `AC-CR031-002` | `FR-UI-005` | Skill path unaffected | User triggers a skill (`top_score ≥ 0.65`) | `_agent_loop` runs | Non-streaming path used; full `LLMResponse` returned and parsed for `<skill_call>` as before | implemented |
| `AC-CR031-003` | `FR-UI-005` | Cloud streaming | Cloud provider (Gemini or Anthropic) is active | Conversational turn streams | Tokens arrive progressively from the provider's streaming API | implemented |
| `AC-CR031-004` | `FR-UI-005` | Local streaming | Ollama is active | Conversational turn streams | Tokens arrive progressively from Ollama's `stream=True` chat endpoint | implemented |
| `AC-CR031-005` | `FR-UI-005` | No double-print | Streaming turn completes | `start()` runs post-response | Response is not re-printed by `_stream_response()` (`_last_response_streamed` flag) | implemented |
| `AC-CR031-006` | `FR-UI-005` | Empty stream fallback | Streaming yields no tokens | `_agent_loop` runs | Falls back to non-streaming `route()` call; user sees a response | implemented |
| `AC-CR031-007` | `NFR-PERF-009` | Spinner until first token | Model is generating first token | `_StatusContext` is active | Spinner remains visible until streaming begins, then clears cleanly | implemented |
| `AC-CR031-008` | `FR-UI-005` | Smoke tests pass | All changes applied | `python smoke_test.py` runs | 27 tests pass, 0 failures | implemented |
| `AC-CR014-001` | `BUG-API-002` | City-Country query (no comma) | User asks "what is the weather in Tijuana Mexico?" | WeatherSkill geocodes | Coordinates for Tijuana, Baja California, Mexico are resolved and current weather is returned | resolved |
| `AC-CR014-002` | `NFR-API-001` | Country-filtered API call | User provides a location with a recognized country name | `_split_country()` identifies the country | The geocoding URL includes `countrycode=XX` scoping results to that country | implemented |
| `AC-CR014-003` | `NFR-API-001` | Country-aware result ranking | Geocoding returns multiple cities with the same name | `_best_geocode_result()` runs with a known country code | The result whose `country_code` field matches is returned | implemented |
| `AC-CR014-004` | `NFR-API-001` | Proper-noun location cleaning | Location string is "The Hague" | `_clean_location()` runs | "The" is preserved because it is followed by a capital letter; location resolves correctly | implemented |

### Architecture Hardening — Local AI Reference Spec Gap Closure (CR-010)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-020` | functional | P1 | implemented | `src/events.py` provides a thread-safe event bus; `_agent_loop` emits `routing_started`, `skill_matched`, `skill_started`, `skill_complete`, `llm_complete`, and `hitl_required` events so the future web SSE layer can subscribe without coupling to chat internals | `AC-CR010-001` | `CR-010` | Module-level singleton; terminal ignores it, web layer subscribes |
| `FR-ORCH-021` | functional | P0 | implemented | `_route_local()` trims conversation history to the 10 most recent messages before the LLM call, summarising older messages as a heuristic context block, preventing context window overflow on long sessions | `AC-CR010-002` | `CR-010` | `trim_history_for_local()` in `context_loader.py` |
| `NFR-UI-007` | non-functional | P1 | implemented | A consecutive-staged-message counter in `XochitlChat.start()` clears the staged queue and warns the user if more than 5 staged messages fire without real user input | `AC-CR010-003` | `CR-010` | `_consecutive_staged` counter |
| `DATA-DATA-006` | data | P1 | implemented | A `memory_facts` SQLite table stores structured per-turn facts with `category` (preference / context / project / skill / constraint / goal), `confidence` (0–1), `source`, `project`, and a `superseded_by` reference for tombstoning | `AC-CR010-004` | `CR-010` | Written by `BackgroundReview` alongside existing KB markdown |
| `DATA-DATA-007` | data | P1 | implemented | `VectorMemory.recall()` generates a hypothetical document via the fast local model before embedding, so declarative personal notes are retrieved by embedding a statement rather than a question (HyDE pattern); falls back to direct query embedding on failure | `AC-CR010-005` | `CR-010` | `_hyde_embed()` in `src/memory.py` |
| `OPS-CORE-001` | operations | P2 | implemented | `scripts/start_ollama.ps1` configures Ollama with `KEEP_ALIVE=30m`, `NUM_PARALLEL=2`, `FLASH_ATTENTION=1`, `KV_CACHE_TYPE=q8_0`, and `MAX_LOADED_MODELS=2` before starting the server; `.env.example` documents all configurable variables | `AC-CR010-006` | `CR-010` | Run once before `xochitl chat` |

### Product Identity Refactor (CR-011)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `NFR-UI-008` | non-functional | P2 | implemented | All user-facing strings, documentation, and system prompt templates describe Xochitl as a personal AI system; no instance of "Chief of Staff" appears in active (non-archive) files | `AC-CR011-001`, `AC-CR011-002`, `AC-CR011-003` | `CR-011` | Branding/identity refactor |

### User Profile Engine and Me.md (CR-012)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-022` | functional | P1 | implemented | `UserProfileEngine` loads `Me.md` from the persona search path and injects its content as `## About the User` in every system prompt, positioned between the Identity Guard and the Facts block | `AC-CR012-001`, `AC-CR012-002`, `AC-CR012-004` | `CR-012` | `src/context_manager.py` UserProfileEngine |
| `NFR-ORCH-001` | non-functional | P2 | implemented | `Me.md` is designed to remain under 80 lines / 600 tokens; compaction preserves the top sections and truncates from the bottom | `AC-CR012-003` | `CR-012` | Token budget safe |

### Me.md Line Count Warning (CR-013)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `NFR-ORCH-002` | non-functional | P2 | implemented | When `Me.md` loads with more than 80 lines, `UserProfileEngine.ingest()` prints a dim warning to the terminal indicating the line count and that lower sections may compact under token pressure | `AC-CR013-001`, `AC-CR013-002`, `AC-CR013-003`, `AC-CR013-004` | `CR-013` | Inform, don't block |

### UI — LLM Token Streaming (CR-031)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-UI-005` | functional | P1 | implemented | LLM responses for conversational turns are delivered as real token streams from the model provider; words appear progressively as the model generates them, not after a full batch wait | `AC-CR031-001`, `AC-CR031-002`, `AC-CR031-003`, `AC-CR031-004`, `AC-CR031-005`, `AC-CR031-006` | `CR-031` | `stream_local`, `stream_cloud`, `route_stream`, `_agent_loop` |
| `NFR-PERF-009` | non-functional | P2 | accepted | First token appears within 3 seconds for local model and 5 seconds for cloud under normal network conditions | `AC-CR031-007` | `CR-031` | Perceived-latency target |

### API — Weather Geocoding Robustness (CR-014)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `BUG-API-002` | bug | P1 | resolved | WeatherSkill fails to geocode locations expressed as "City Country" without a comma separator (e.g., "Tijuana Mexico") because Open-Meteo's `name` param expects a city name only | `AC-CR014-001` | session | Resolved by CR-014 |
| `NFR-API-001` | non-functional | P1 | implemented | WeatherSkill geocoding resolves recognized country names in location queries to ISO 3166-1 alpha-2 codes, passes `countrycode` to Open-Meteo, and ranks results by country match before falling back to US-state matching or first result | `AC-CR014-002`, `AC-CR014-003`, `AC-CR014-004` | `CR-014` | `_split_country()`, `_COUNTRY_CODES` |

### Security — SSRF Protection (CR-016)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-SEC-005` | security | P0 | implemented | All outbound HTTP requests made by Xochitl skill modules must pass `validate_outbound_url()` before the connection is opened; the validator rejects non-http/https schemes and any hostname that resolves to a private or reserved IP range | `AC-CR016-001`, `AC-CR016-002`, `AC-CR016-003`, `AC-CR016-004`, `AC-CR016-005`, `AC-CR016-006`, `AC-CR016-007` | `CR-016` | `src/security.py` `validate_outbound_url()` |
| `NFR-SEC-003` | non-functional | P0 | implemented | SSRF validation must resolve hostnames to IP addresses via `socket.getaddrinfo()` before range-checking, preventing DNS rebinding bypass | `AC-CR016-001`, `AC-CR016-005` | `CR-016` | Resolve-then-validate; see ADR-002 |

### Acceptance criteria — SSRF Protection (CR-016)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR016-001` | `FR-SEC-005` | Loopback blocked | `validate_outbound_url("http://127.0.0.1/secret")` called | — | Raises `XochitlPermissionError` | implemented |
| `AC-CR016-002` | `FR-SEC-005` | Private range blocked | `validate_outbound_url("http://10.0.0.1/data")` called | — | Raises `XochitlPermissionError` | implemented |
| `AC-CR016-003` | `FR-SEC-005` | Cloud metadata blocked | `validate_outbound_url("http://169.254.169.254/latest/meta-data/")` called | — | Raises `XochitlPermissionError` | implemented |
| `AC-CR016-004` | `FR-SEC-005` | Non-http scheme blocked | `validate_outbound_url("file:///etc/passwd")` called | — | Raises `XochitlPermissionError` | implemented |
| `AC-CR016-005` | `FR-SEC-005`, `NFR-SEC-003` | Public URL allowed | `validate_outbound_url("https://api.open-meteo.com/v1/forecast")` called | — | Returns URL unchanged | implemented |
| `AC-CR016-006` | `FR-SEC-005` | Web skill call site | Inspect `_fetch_text()` and `_search()` in `web_lookup_skill.py` | — | `validate_outbound_url()` called before every `urlopen()` | implemented |
| `AC-CR016-007` | `FR-SEC-005` | Weather skill call site | Inspect `_fetch_json()` in `weather_skill.py` | — | `validate_outbound_url()` called before every `urlopen()` | implemented |

### API — HTTP Retry and Rate Limiting (CR-017)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-API-005` | functional | P1 | implemented | Outbound HTTP requests from skill modules must be retried on transient failures (HTTP 429/500/502/503/504 and network errors) using exponential backoff; a maximum of 3 total attempts are made | `AC-CR017-001`, `AC-CR017-002`, `AC-CR017-003`, `AC-CR017-004`, `AC-CR017-006` | `CR-017` | `src/http_utils.py` `fetch_bytes` retry loop |
| `NFR-PERF-010` | non-functional | P2 | implemented | Retry delays use exponential backoff (`base × 2^attempt`, capped at 4 s) with ±25% random jitter to reduce thundering-herd effects | `AC-CR017-001` | `CR-017` | See ADR-003 |
| `NFR-API-002` | non-functional | P1 | implemented | A per-domain sliding-window rate limiter throttles skill outbound HTTP calls to at most 5 requests per 10-second window; excess calls block the calling thread until a slot opens | `AC-CR017-005` | `CR-017` | `src/http_utils.py` `_rate_limit_acquire` |

### Acceptance criteria — HTTP Retry and Rate Limiting (CR-017)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR017-001` | `FR-API-005`, `NFR-PERF-010` | 429 retried | `fetch_bytes` receives HTTP 429 twice then succeeds | — | Returns response body; total attempts = 3 | implemented |
| `AC-CR017-002` | `FR-API-005` | 400 not retried | `fetch_bytes` receives HTTP 400 | — | `HTTPError(400)` propagates immediately; total attempts = 1 | implemented |
| `AC-CR017-003` | `FR-API-005` | `URLError` retried | `fetch_bytes` receives `URLError` on first call | — | Retry attempted; second call succeeds | implemented |
| `AC-CR017-004` | `FR-API-005` | All attempts exhausted | `fetch_bytes` receives 3× `URLError` | — | Final `URLError` propagates to caller | implemented |
| `AC-CR017-005` | `NFR-API-002` | Rate limit blocks | 6 calls in <10 s to same domain | — | 6th call waits until a slot opens; no call is dropped | implemented |
| `AC-CR017-006` | `FR-API-005` | SSRF not retried | `validate_outbound_url` raises | — | `XochitlPermissionError` propagates immediately; 0 `urlopen` calls | implemented |
| `AC-CR017-007` | `FR-API-005` | Weather call site | Inspect `WeatherSkill._fetch_json` | — | Uses `fetch_bytes`; no direct `urlopen` | implemented |
| `AC-CR017-008` | `FR-API-005` | Web lookup call sites | Inspect `WebLookupSkill._search`, `_fetch_text` | — | Both use `fetch_bytes`; no direct `urlopen` | implemented |

### Orchestration — Session Tiered Governor (CR-026)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-025` | functional | P1 | implemented | Before each LLM turn the chat session evaluates `SessionGovernor.tier()` and applies progressive routing restrictions: `prefer_local` warns the user once; `local_only` forces `force_route="general"` (local model); `hard_stop` returns a canned budget message and skips the LLM call | `AC-CR026-001`, `AC-CR026-002`, `AC-CR026-003`, `AC-CR026-004`, `AC-CR026-006`, `AC-CR026-007` | `CR-026` | `src/governor.py`, `src/chat.py` |
| `NFR-PERF-011` | non-functional | P2 | implemented | Token estimation uses `len(text) // 4` (chars/4 approximation); no I/O, no dependencies; the governor is a rough budget guide, not a billing meter | `AC-CR026-005` | `CR-026`, `ADR-004` | env-var configurable thresholds |

### Acceptance criteria — Session Tiered Governor (CR-026)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR026-001` | `FR-ORCH-025` | Fresh session | `SessionGovernor()` created | — | `tier()` returns `Tier.FULL`; `total_tokens == 0` | implemented |
| `AC-CR026-002` | `FR-ORCH-025` | Prefer-local transition | `record_turn` accumulates ≥ 20 000 est. tokens | — | `tier()` returns `Tier.PREFER_LOCAL`; `force_route()` returns `None` | implemented |
| `AC-CR026-003` | `FR-ORCH-025` | Local-only transition | `record_turn` accumulates ≥ 40 000 est. tokens | — | `tier()` returns `Tier.LOCAL_ONLY`; `force_route()` returns `"general"` | implemented |
| `AC-CR026-004` | `FR-ORCH-025` | Hard-stop transition | `record_turn` accumulates ≥ 80 000 est. tokens | — | `tier()` returns `Tier.HARD_STOP`; `start()` returns budget message without LLM call | implemented |
| `AC-CR026-005` | `NFR-PERF-011` | Env-var override | `XCH_LOCAL_ONLY_TOKENS=1000` set before import | — | `_LOCAL_ONLY_THRESHOLD == 1000`; tier transitions at 1 000 tokens | implemented |
| `AC-CR026-006` | `FR-ORCH-025` | `/budget` command | User types `/budget` in chat | — | Budget detail printed: tier, estimated tokens, thresholds | implemented |
| `AC-CR026-007` | `FR-ORCH-025` | Warning de-dup | `should_warn(Tier.PREFER_LOCAL)` called twice | — | Returns `True` first time, `False` second time | implemented |

### Orchestration — Uncertainty Tiers and Capability Boundary (CR-032)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-026` | functional | P1 | implemented | `prompts/system_xochitl.txt` includes an `[UNCERTAINTY TIERS]` section defining four tiers — CERTAIN, CONFIDENT INFERENCE, UNCERTAIN, UNKNOWN — each with source conditions, marker language examples, and usage rules | `AC-CR032-001` | `CR-032` | Model-behavior guidance; no code logic |
| `FR-ORCH-027` | functional | P1 | implemented | `prompts/system_xochitl.txt` includes a `[CAPABILITY BOUNDARY]` section with explicit CAN and CANNOT lists so the model has permission to say "I can't do that" rather than constructing unreliable workarounds | `AC-CR032-002` | `CR-032` | Model-behavior guidance; no code logic |
| `NFR-ORCH-003` | non-functional | P1 | implemented | When `top_score < 0.2` in `_agent_loop`, a one-line `[TURN CONTEXT]` note is appended to the assembled system prompt for that turn only, signalling an open-ended or general knowledge turn and reminding the model to apply calibrated `[UNCERTAINTY TIERS]` vocabulary; no note is injected when a skill scores >= 0.65 | `AC-CR032-003`, `AC-CR032-004` | `CR-032` | `_OPEN_ENDED_SCORE_THRESHOLD = 0.2` in `chat.py` |

### Acceptance criteria — Uncertainty Tiers and Capability Boundary (CR-032)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR032-001` | `FR-ORCH-026` | Uncertainty tiers present | `prompts/system_xochitl.txt` is read | — | File contains `[UNCERTAINTY TIERS]` section | implemented |
| `AC-CR032-002` | `FR-ORCH-027` | Capability boundary present | `prompts/system_xochitl.txt` is read | — | File contains `[CAPABILITY BOUNDARY]` section | implemented |
| `AC-CR032-003` | `NFR-ORCH-003` | Low-score injection | `top_score < 0.2` in `_agent_loop` | — | Assembled system prompt contains `[TURN CONTEXT]` note | implemented |
| `AC-CR032-004` | `NFR-ORCH-003` | High-score no injection | `top_score >= 0.65` (skill matched) | — | No `[TURN CONTEXT]` note injected | implemented |
| `AC-CR032-005` | `FR-ORCH-026`, `FR-ORCH-027` | Smoke test | `python smoke_test.py` runs | — | Both sections confirmed present in prompt file | implemented |

## Requirement lifecycle notes

- Never reuse deprecated IDs.
- If a requirement changes meaning, create a new ID and mark the old one superseded.
- If a requirement is split, create child IDs and update traceability.
- If a requirement is merged, preserve all old IDs as superseded aliases.
