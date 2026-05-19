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

## Requirement lifecycle notes

- Never reuse deprecated IDs.
- If a requirement changes meaning, create a new ID and mark the old one superseded.
- If a requirement is split, create child IDs and update traceability.
- If a requirement is merged, preserve all old IDs as superseded aliases.
