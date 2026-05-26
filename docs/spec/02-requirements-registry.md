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
| `DEV` | Development standards, tooling, code quality |

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

### Orchestration — Persona Anchoring and SOUL.md Restructure (CR-029)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-028` | functional | P0 | implemented | `assemble_system_prompt()` calls `_render_system_prompt_template()` so the static behavior sections from `prompts/system_xochitl.txt` — including `[GOAL]`, `[DISAGREEMENT PROTOCOL]`, `[TONE ADAPTATION]`, `[SPANISH AND CULTURAL VOICE]`, `[INTERACTION RULES]`, `[UNCERTAINTY TIERS]`, `[CAPABILITY BOUNDARY]`, and `[BMAD CONTEXT]` — are included in the system prompt on every turn | `AC-CR029-004`, `AC-CR029-005` | `CR-029` | Previously `_render_system_prompt_template()` was defined but never called |
| `FR-ORCH-029` | functional | P1 | implemented | `SOUL.md.example` follows a structured four-section format (`## [IDENTITY]`, `## [VOICE]`, `## [VALUES]`, `## [BOUNDARIES]`); the `[IDENTITY]` section is the load-bearing persona anchor; "Chief of Staff" identity language is removed | `AC-CR029-001` | `CR-029` | `SOUL.md.example` |
| `NFR-ORCH-004` | non-functional | P1 | implemented | `SoulEngine.ingest()` extracts the `[IDENTITY]` section as `identity_anchor`; if the section is absent from SOUL.md, a yellow warning is printed and a fallback anchor is used | `AC-CR029-002` | `CR-029` | `SoulEngine._extract_section()`, `identity_anchor` property |
| `NFR-ORCH-005` | non-functional | P1 | implemented | `SoulEngine.compact()` always preserves the `[IDENTITY]` section content regardless of the `max_tokens` budget; `[VOICE]`, `[VALUES]`, `[BOUNDARIES]` are included in that order until the budget is exhausted | `AC-CR029-003` | `CR-029` | Section-aware compact replaces naive line-by-line truncation |

### Acceptance criteria — Persona Anchoring and SOUL.md Restructure (CR-029)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR029-001` | `FR-ORCH-029` | Soul structure | `SOUL.md.example` is read | — | File contains `## [IDENTITY]` section; does not contain "Chief of Staff" | implemented |
| `AC-CR029-002` | `NFR-ORCH-004` | Identity anchor | `SoulEngine.ingest()` runs | — | `soul.identity_anchor` is non-empty and contains text from the `[IDENTITY]` section | implemented |
| `AC-CR029-003` | `NFR-ORCH-005` | Compact preserves identity | `SoulEngine.compact(80)` called | — | Compacted output contains first 40 chars of `identity_anchor`; output is shorter than full soul text | implemented |
| `AC-CR029-004` | `FR-ORCH-028` | Template wired — behavior | `ContextManager.assemble_system_prompt()` called | — | Output contains `[GOAL]` (confirming behavior template sections reach model) | implemented |
| `AC-CR029-005` | `FR-ORCH-028` | Template wired — uncertainty | `ContextManager.assemble_system_prompt()` called | — | Output contains `[UNCERTAINTY TIERS]` (confirming CR-032 vocabulary reaches model) | implemented |
| `AC-CR029-006` | All CR-029 | Smoke tests | `python smoke_test.py` runs | — | 58 passed, 0 failed | implemented |

### Orchestration — Graceful Correction Handling (CR-030)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-030` | functional | P1 | implemented | `prompts/system_xochitl.txt` includes a `[CORRECTION HANDLING]` section defining a three-step correction pattern: (1) minimal acknowledgment ("Got it.", "Right.", "Noted."), (2) apply immediately without re-explanation or confirmation, (3) treat as preference signal and do not repeat the mistake | `AC-CR030-001` | `CR-030` | `prompts/system_xochitl.txt` |
| `FR-ORCH-031` | functional | P1 | implemented | `BackgroundReview` detects correction-signal turns via `_detect_correction()`; correction turns bypass `_MIN_WRITE_INTERVAL_SECS` rate limit and are stored as category=`"preference"` with confidence ≥ 0.9 | `AC-CR030-002`, `AC-CR030-003`, `AC-CR030-004` | `CR-030` | `src/background_review.py` — `_CORRECTION_SIGNALS`, `_detect_correction()`, `_TurnData.is_correction`, `_store_correction_fact()` |
| `NFR-ORCH-006` | non-functional | P1 | implemented | When a correction fact near-duplicate is found in `memory_facts` (80-char LOWER prefix match), `BackgroundReview._store_correction_fact()` also calls `upsert_preference()` with category=`"communication"`, confidence=0.95, and a deterministic key (`"correction_" + MD5 prefix) | `AC-CR030-005` | `CR-030` | Recurring-correction escalation; key is stable across upserts |

### Acceptance criteria — Graceful Correction Handling (CR-030)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR030-001` | `FR-ORCH-030` | Prompt section | `prompts/system_xochitl.txt` is read | — | File contains `[CORRECTION HANDLING]` section with minimal-ack examples ("Got it.", "Noted.") | implemented |
| `AC-CR030-002` | `FR-ORCH-031` | Detection — True | `_detect_correction()` called with correction phrases | — | Returns `True` for "no,", "actually", "I meant", "let me clarify", etc. | implemented |
| `AC-CR030-003` | `FR-ORCH-031` | Rate-limit bypass | `BackgroundReview._process()` source inspected | — | `is_correction` flag present; correction turns bypass `_MIN_WRITE_INTERVAL_SECS` | implemented |
| `AC-CR030-004` | `FR-ORCH-031` | Correction storage | `_store_correction_fact()` source inspected | — | Stores with category=`"preference"` and confidence≥0.9 | implemented |
| `AC-CR030-005` | `NFR-ORCH-006` | Escalation | `_store_correction_fact()` called with mock DB having near-duplicate | — | `upsert_preference()` called with category=`"communication"`, confidence≥0.9, key starting with `"correction_"` | implemented |
| `AC-CR030-006` | All CR-030 | Smoke tests | `python smoke_test.py` runs | — | 63 passed, 0 failed | implemented |

### Development Standards (CR-015)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `NFR-DEV-001` | non-functional | P1 | implemented | Every commit includes a scope from the closed list (`core`, `api`, `ui`, `data`, `auth`, `sdd`, `orch`, `skill`, `mem`, `ztk`, `dev`); scope-less commits are prohibited | `AC-CR015-001`, `AC-CR015-003`, `AC-CR015-004` | `CR-015` | Scope list in `CLAUDE.md` §NFR-DEV-001 and `AGENTS.md §Commit conventions` |
| `NFR-DEV-002` | non-functional | P1 | implemented | All new public function signatures include argument type hints and a return type annotation; `Optional[T]` or `T \| None` for nullable returns | `AC-CR015-002` | `CR-015` | Applies to new code; existing code audited separately |
| `NFR-DEV-003` | non-functional | P1 | implemented | No bare `except:` clauses in `src/`; always `except Exception as exc:` or a specific type; exception chain preserved with `raise … from exc` | `AC-CR015-002` | `CR-015` | `except BaseException:` allowed only in shutdown paths with explicit justification |
| `NFR-DEV-004` | non-functional | P1 | implemented | Public methods on skill classes, context engines, and database helpers carry Google-style docstrings (one-line summary + `Args:` + `Returns:` + `Raises:`) | `AC-CR015-002` | `CR-015` | Priority: `can_handle()`, `execute()`, `tool_definition()` |
| `NFR-DEV-005` | non-functional | P1 | implemented | Every test function covers: happy path, at least one edge/failure case, external deps mocked, output deterministic, test fails if logic removed | `AC-CR015-002` | `CR-015` | No real API calls in unit tests |
| `NFR-DEV-006` | non-functional | P1 | implemented | No `eval()`/`exec()`/`pickle.loads()` on user or LLM-generated input; no bare resource leaks; all outbound HTTP carries explicit `timeout=`; `subprocess.run()` never `shell=True` with generated content | `AC-CR015-002` | `CR-015` | |

### Acceptance criteria — Development Standards (CR-015)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR015-001` | `NFR-DEV-001` | Scope standards in CLAUDE.md | `CLAUDE.md` is read | — | File contains `## Code Quality Standards` section with scope table | implemented |
| `AC-CR015-002` | `NFR-DEV-002` through `NFR-DEV-006` | Standards documented | `CLAUDE.md` is read | — | All six NFR-DEV-* standards listed with descriptions | implemented |
| `AC-CR015-003` | `NFR-DEV-001` | Scope list in AGENTS.md | `AGENTS.md` is read | — | File contains a `## Commit conventions` section with the closed scope list | implemented |
| `AC-CR015-004` | `NFR-DEV-001` | Scope rule in AGENTS.md | `AGENTS.md` is read | — | Section states that scope-less commits are prohibited | implemented |

### Architecture — Exception Hierarchy (CR-018)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `ARCH-ORCH-001` | architecture | P1 | implemented | `src/exceptions.py` defines `XochitlError` as the base exception with a documented hierarchy: `RouterError`, `SkillError`, `GeocodingError`, `ContextError`, `SandboxError`, `SSRFBlockedError`, `NotionError`; hierarchy documented in module docstring with ASCII tree | `AC-CR018-001`, `AC-CR018-003`, `AC-CR018-004` | `CR-018` | `src/exceptions.py` |
| `NFR-DEV-007` | non-functional | P1 | implemented | SSRF-blocked conditions raise `SSRFBlockedError` (not bare `XochitlPermissionError`); `XochitlPermissionError` is kept as a backward-compatible alias for `SandboxError` so existing catch-sites are not broken | `AC-CR018-002`, `AC-CR018-005` | `CR-018` | `src/security.py` — three SSRF raise sites updated |
| `NFR-DEV-008` | non-functional | P1 | implemented | Geocoding failure in `weather_skill.py` raises `GeocodingError` (not `ValueError`) so callers can handle location failures separately from generic skill failures | `AC-CR018-006` | `CR-018` | `src/skills/weather_skill.py` — two raise sites updated |

### Acceptance criteria — Exception Hierarchy (CR-018)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR018-001` | `ARCH-ORCH-001` | Module exports | `src.exceptions` imported | — | All eight exception classes importable without error | implemented |
| `AC-CR018-002` | `NFR-DEV-007` | Alias | `XochitlPermissionError is SandboxError` | — | Returns `True`; existing catch-sites catch `SandboxError` | implemented |
| `AC-CR018-003` | `ARCH-ORCH-001` | Sandbox hierarchy | Hierarchy inspected | — | `SSRFBlockedError` ⊂ `SandboxError` ⊂ `XochitlError` | implemented |
| `AC-CR018-004` | `ARCH-ORCH-001` | Skill hierarchy | Hierarchy inspected | — | `GeocodingError` ⊂ `SkillError` ⊂ `XochitlError` | implemented |
| `AC-CR018-005` | `NFR-DEV-007` | SSRF raise type | `validate_outbound_url("http://127.0.0.1/")` | — | Raises `SSRFBlockedError` (not generic `Exception`) | implemented |
| `AC-CR018-006` | `NFR-DEV-008` | Geocoding raise type | `WeatherSkill._geocode("NowhereVille")` with empty mock | — | Raises `GeocodingError` (not `ValueError`) | implemented |
| `AC-CR018-007` | All CR-018 | Smoke tests | `python smoke_test.py` runs | — | 69 passed, 0 failed | implemented |

### Orchestration — Response Mode Switching (CR-025)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-032` | functional | P1 | implemented | `src/response_mode.py` defines three modes (`conversational`, `operator`, `report`) and `infer_mode(user_input: str) -> str` using regex/keyword heuristics — no LLM call | `AC-CR025-001` through `AC-CR025-004` | `CR-025` | `src/response_mode.py` |
| `FR-ORCH-033` | functional | P1 | implemented | `ContextManager.assemble_system_prompt(mode: str = "conversational") -> str` appends the mode-specific prompt block for `operator` and `report` modes; `conversational` mode adds no extra block | `AC-CR025-005`, `AC-CR025-006` | `CR-025` | `src/context_manager.py` — mode block appended after skills hint in both budget paths |
| `NFR-ORCH-007` | non-functional | P1 | implemented | When response mode changes between consecutive turns, `XochitlChat` prints a single dim transition line before the response (`"→ operator mode"`, etc.) | — | `CR-025` | `src/chat.py` — `_agent_loop()` mode transition announcement |
| `NFR-ORCH-008` | non-functional | P1 | implemented | Mode inference is a regex/keyword heuristic — no second LLM call; `infer_mode()` runs synchronously before the main LLM call | `AC-CR025-002` through `AC-CR025-004` | `CR-025` | `src/response_mode.py` — compiled regex + frozenset keyword lookup |

### Acceptance criteria — Response Mode Switching (CR-025)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR025-001` | `FR-ORCH-032` | Constants | `src.response_mode` imported | — | All three `MODE_*` constants have correct string values | implemented |
| `AC-CR025-002` | `FR-ORCH-032`, `NFR-ORCH-008` | Operator inference | `infer_mode("sync my tasks")` | — | Returns `"operator"` | implemented |
| `AC-CR025-003` | `FR-ORCH-032`, `NFR-ORCH-008` | Report inference | `infer_mode("give me a report on my projects")` | — | Returns `"report"` | implemented |
| `AC-CR025-004` | `FR-ORCH-032`, `NFR-ORCH-008` | Conversational fallback | `infer_mode("what's the weather like?")` | — | Returns `"conversational"` | implemented |
| `AC-CR025-005` | `FR-ORCH-033` | Operator block injected | `assemble_system_prompt(mode="operator")` called | — | Output contains `[RESPONSE MODE: OPERATOR]` | implemented |
| `AC-CR025-006` | `FR-ORCH-033` | No block for conversational | `assemble_system_prompt()` with default mode | — | Output does NOT contain `[RESPONSE MODE:` | implemented |
| `AC-CR025-007` | All CR-025 | Smoke tests | `python smoke_test.py` runs | — | 75 passed, 0 failed | implemented |

### Orchestration — Capability Boundary Communication (CR-036)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-034` | functional | P1 | implemented | `_agent_loop()` distinguishes three skill-score zones and injects differentiated `[TURN CONTEXT]` per zone: skill-matched (`≥ 0.65`) = no extra context; near-miss (`0.20–0.65`) = skill name + partial-coverage guidance + no-silent-reduction prohibition; complete-miss (`< 0.20`) = capability boundary note + forward-path instruction | `AC-CR036-001`, `AC-CR036-002`, `AC-CR036-003` | `CR-036` | `src/chat.py` — three-zone if/elif/else replacing two-zone if |
| `NFR-ORCH-009` | non-functional | P1 | implemented | Near-miss and complete-miss [TURN CONTEXT] notes injected without any additional LLM call; information comes from existing `can_handle()` scores | `AC-CR036-001`, `AC-CR036-002`, `AC-CR036-003` | `CR-036` | No new imports or modules — targeted if/elif/else in `_agent_loop()` |

### Acceptance criteria — Capability Boundary Communication (CR-036)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR036-001` | `FR-ORCH-034` | Complete miss | `top_score < 0.20` (source inspection) | — | `[TURN CONTEXT]` contains `[CAPABILITY BOUNDARY]` reference and forward-path instruction | implemented |
| `AC-CR036-002` | `FR-ORCH-034` | Near-miss | `0.20 ≤ top_score < 0.65` (source inspection) | — | `[TURN CONTEXT]` contains skill name, near-miss note, and no-silent-reduction prohibition | implemented |
| `AC-CR036-003` | `FR-ORCH-034` | Skill matched | `top_score ≥ 0.65` (source inspection) | — | Skill-matched zone uses `pass` — no `[TURN CONTEXT]` injected | implemented |
| `AC-CR036-004` | All CR-036 | Smoke tests | `python smoke_test.py` runs | — | 78 passed, 0 failed | implemented |

### Orchestration — Structured Observability (CR-021)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-035` | functional | P1 | implemented | `ObservabilityLogger` subscribes to the event bus; on each `routing_started`/`llm_complete`/`skill_*` event sequence it assembles and persists a structured `_TurnTrace` record to JSONL + SQLite (`agent_traces` table) | `AC-CR021-001`, `AC-CR021-004`, `AC-CR021-005` | `CR-021` | `src/observability.py` — `ObservabilityLogger`; `src/database.py` — `agent_traces` table |
| `FR-ORCH-036` | functional | P1 | implemented | `routing_started` payload includes a `trace_id` (12-char hex); `llm_complete` payload includes `tokens_in` and `cost_usd` in addition to the existing `route` and `tokens_out` fields | `AC-CR021-002`, `AC-CR021-003` | `CR-021` | `src/chat.py` — `_agent_loop()` emits enriched payloads |
| `NFR-ORCH-010` | non-functional | P1 | implemented | JSONL ring buffer capped at 10 MB; when exceeded the current file is renamed to `agent_traces.jsonl.bak` and a new file is started | — | `CR-021` | `src/observability.py` — `_write_jsonl()` rotation logic |
| `NFR-ORCH-011` | non-functional | P1 | implemented | SQLite writes happen in a background daemon thread so the main chat loop is never blocked by observability I/O; JSONL writes are synchronous append-only wrapped in try/except | — | `CR-021` | `src/observability.py` — `_handle_llm_complete()` spawns `threading.Thread(daemon=True)` |

### Acceptance criteria — Structured Observability (CR-021)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR021-001` | `FR-ORCH-035` | Lifecycle | Import `ObservabilityLogger` | — | `start()` and `stop()` are callable | implemented |
| `AC-CR021-002` | `FR-ORCH-036` | trace_id in routing_started | Source inspection of `chat.py` | — | `"trace_id"` key present in `routing_started` emit | implemented |
| `AC-CR021-003` | `FR-ORCH-036` | Enriched llm_complete | Source inspection of `chat.py` | — | `"tokens_in"` and `"cost_usd"` keys present in `llm_complete` emit | implemented |
| `AC-CR021-004` | `FR-ORCH-035` | Schema | Source inspection of `database.py` | — | `agent_traces` table and `insert_agent_trace()` defined | implemented |
| `AC-CR021-005` | `FR-ORCH-035` | JSONL write | `on_event("llm_complete", ...)` called with primed trace | — | `_write_jsonl()` called once with record containing `trace_id` | implemented |
| `AC-CR021-006` | All CR-021 | Smoke tests | `python smoke_test.py` runs | — | 83 passed, 0 failed | implemented |

### Orchestration — Reflection / Critic (CR-019)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-037` | functional | P1 | implemented | `TurnCritic.should_critique()` returns `True` when: (a) a skill was executed, (b) skill score in near-miss zone (0.20–0.65), or (c) response matches `_HEDGING_PATTERNS`. Never fires on streaming turns. | `AC-CR019-001`, `AC-CR019-002`, `AC-CR019-003` | `CR-019` | `src/critic.py` — `TurnCritic.should_critique()`; `src/chat.py` — `_maybe_critique()` called only from non-streaming path |
| `FR-ORCH-038` | functional | P1 | implemented | `TurnCritic.critique()` returns `CritiqueResult` with verdict in `{"ok", "correctable", "ambiguous"}`. CORRECTABLE triggers retry loop (capped at `_MAX_CRITIC_ITERATIONS=2`). AMBIGUOUS appends `_Fíjate —_` caveat. | `AC-CR019-004`, `AC-CR019-005` | `CR-019` | `src/critic.py` — `critique()`, `_parse_critic_response()`; `src/chat.py` — `_maybe_critique()` correction loop |
| `NFR-ORCH-012` | non-functional | P1 | implemented | Critic call uses `force_route="simple_qa"` (local model). At most `_MAX_CRITIC_ITERATIONS` (2) extra LLM calls per turn when triggered. | — | `CR-019` | `src/critic.py` — `critique()` uses `force_route="simple_qa"`; `src/chat.py` — `range(_MAX_CRITIC_ITERATIONS)` loop |
| `NFR-ORCH-013` | non-functional | P1 | implemented | Critique never runs on streaming turns. `_maybe_critique()` is wrapped in `try/except Exception` and silently degrades to returning the original response on any failure. | — | `CR-019` | `src/chat.py` — streaming path returns before `_maybe_critique`; `try/except Exception` in `_maybe_critique` |

### Acceptance criteria — Reflection / Critic (CR-019)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR019-001` | `FR-ORCH-037`, `FR-ORCH-038` | Class structure | Import `TurnCritic` | — | `should_critique()` and `critique()` are callable | implemented |
| `AC-CR019-002` | `FR-ORCH-037` | Trigger conditions | `should_critique()` with each trigger independently | — | Returns `True` for tool_calls_made, near-miss score, and hedging language | implemented |
| `AC-CR019-003` | `FR-ORCH-037` | No trigger | `should_critique(score=0.90, tool_calls_made=False, response="confident answer")` | — | Returns `False` | implemented |
| `AC-CR019-004` | `FR-ORCH-038` | Parsing | `_parse_critic_response()` with OK / CORRECTABLE / AMBIGUOUS prefixes | — | Correct verdicts returned | implemented |
| `AC-CR019-005` | `FR-ORCH-037`, `NFR-ORCH-012` | Integration | Source inspection of `chat.py` | — | `_maybe_critique` and `_MAX_CRITIC_ITERATIONS` both present | implemented |
| `AC-CR019-006` | All CR-019 | Smoke tests | `python smoke_test.py` runs | — | 88 passed, 0 failed | implemented |

### Evaluation — Eval Harness (CR-022)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-EVAL-001` | functional | P1 | implemented | `src/eval/golden_set.py` defines `GOLDEN_SET` of ≥30 `GoldenExample` instances covering all 8 built-in skills and ≥5 no-skill cases; ≥6 adversarial examples documenting routing gaps | `AC-CR022-001`, `AC-CR022-002` | `CR-022` | `src/eval/golden_set.py` — 34 examples; initial baseline 94.1% (32/34) |
| `FR-EVAL-002` | functional | P1 | implemented | `run_eval()` returns `EvalReport` with per-skill precision, recall, F1; overall accuracy; and list of failing utterances | `AC-CR022-003`, `AC-CR022-004` | `CR-022` | `src/eval/harness.py` — `run_eval()`, `EvalReport`, `SkillMetrics` |
| `FR-EVAL-003` | functional | P1 | implemented | `run_eval()` loads `src/eval/baseline.json` (if present) and sets `regression=True` when accuracy drops > 5pp from baseline; `--save-baseline` flag overwrites baseline | `AC-CR022-005` | `CR-022` | `src/eval/harness.py` — `_load_baseline()`, `_save_baseline()`; `eval_harness.py` — CLI flag |
| `NFR-EVAL-001` | non-functional | P1 | implemented | Harness runs without LLM calls (`can_handle()` only); full 34-example golden set completes in < 2 s | — | `CR-022` | `src/eval/harness.py` — `_score_example()` calls only `skill.can_handle()` |

### Acceptance criteria — Eval Harness (CR-022)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR022-001` | `FR-EVAL-001`, `FR-EVAL-002` | Import | `from src.eval.harness import run_eval, EvalReport` | — | Both importable | implemented |
| `AC-CR022-002` | `FR-EVAL-001` | Coverage | Inspect `GOLDEN_SET` | — | ≥30 examples, all 8 skills covered, ≥5 no-skill cases | implemented |
| `AC-CR022-003` | `FR-EVAL-002` | Fields | Inspect `EvalReport` dataclass fields | — | `accuracy`, `per_skill`, `regression`, `gaps`, `total`, `correct` all present | implemented |
| `AC-CR022-004` | `FR-EVAL-002`, `NFR-EVAL-001` | Run | `run_eval()` with temp baseline path | — | Returns `EvalReport`; `total ≥ 30`; `accuracy ≥ 80%` | implemented |
| `AC-CR022-005` | `FR-EVAL-003` | Regression | Inject baseline 100%, run eval | — | `regression=True`; `baseline_accuracy=1.0` | implemented |
| `AC-CR022-006` | All CR-022 | Smoke tests | `python smoke_test.py` runs | — | 93 passed, 0 failed | implemented |

### Conversation Design — A1–A5 (CR-028)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-CONV-001` | functional | P1 | implemented | `strip_filler_opener(response: str) -> str` removes sycophantic filler phrases ("Certainly!", "Great question!", "I'd be happy to help!", etc.) from the start of each LLM response; applied in `XochitlChat._record()` | `AC-CR028-001` | `CR-028` | `src/conversation.py` — one-pass compiled regex; re-capitalises remainder |
| `FR-CONV-002` | functional | P1 | implemented | `AnticipationGate.check()` evaluates four contextual signals (wip, recency ≥4h, morning 06–10, evening 17–21) at session start and returns a one-line informational hint when ≥2 signals converge; never fires mid-session and never takes action | `AC-CR028-003` | `CR-028` | `src/anticipation.py` — `AnticipationGate`; called from `_print_boot_banner()` in `chat.py` |
| `FR-CONV-003` | functional | P1 | implemented | `build_structured_brief(queue, notion_pending) -> str` returns a five-section Markdown brief (temporal context, priorities, async queue, awareness); each section is skipped when empty; accessible via `/brief` slash command; never pushed unsolicited | `AC-CR028-004` | `CR-028` | `src/brief.py`; `/brief` command in `chat.py` |
| `FR-CONV-004` | functional | P1 | implemented | `PreferenceEngine.assemble()` frames stored preferences as natural background context (`[BACKGROUND CONTEXT] … [/BACKGROUND CONTEXT]`) with explicit instruction not to cite them; replaces old raw `[scope/category] value` format | `AC-CR028-005` | `CR-028` | `src/context_manager.py` — `PreferenceEngine.assemble()` |
| `FR-CONV-005` | functional | P1 | implemented | `uncertainty_hedge(confidence: float, text: str) -> str` applies calibrated framing per three-tier model: `>0.85` direct, `0.60–0.85` → `"I think …"`, `<0.60` → `"I'm not certain, but … — want me to look this up?"` | `AC-CR028-002` | `CR-028` | `src/conversation.py` — exported utility for skill `execute()` methods |
| `NFR-CONV-001` | non-functional | P1 | implemented | All five CR-028 functions are pure/heuristic — no LLM calls; `strip_filler_opener()` and `uncertainty_hedge()` are synchronous pure functions; `AnticipationGate.check()` reads only DB + wall clock; `build_structured_brief()` reads only caller-supplied data + git | `AC-CR028-001` through `AC-CR028-005` | `CR-028` | Verified by test isolation — no router import |

### Acceptance criteria — Conversation Design (CR-028)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR028-001` | `FR-CONV-001` | Filler stripped | `strip_filler_opener("Certainly! Here is the answer.")` | — | Returns `"Here is the answer."` | implemented |
| `AC-CR028-002` | `FR-CONV-005` | Three tiers | `uncertainty_hedge(confidence, text)` at each bracket boundary | — | Correct tier applied per boundary; `ValueError` on empty text | implemented |
| `AC-CR028-003` | `FR-CONV-002` | Gate fires | `AnticipationGate.check(wip_count=1, last_session_age_hours=10)` at hour 14 | — | Non-None hint string returned (wip + recency = 2 signals) | implemented |
| `AC-CR028-004` | `FR-CONV-003` | Sections present | `build_structured_brief(queue=[…], notion_pending=[…])` | — | String contains `**Priorities**`, `**Async queue**`, and day name | implemented |
| `AC-CR028-005` | `FR-CONV-004` | Natural framing | Source inspection of `PreferenceEngine.assemble()` | — | Output contains `[BACKGROUND CONTEXT]` block; old `[scope/category]` format absent | implemented |
| `AC-CR028-006` | All CR-028 | Smoke tests | `python smoke_test.py` runs | — | 98 passed, 0 failed | implemented |

### Persona Drift Detection (CR-033)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-042` | functional | P1 | implemented | `BackgroundReview` tracks `_turn_count` and `_correction_turns` per session; `_should_run_drift_check()` returns `True` when `_turn_count % _DRIFT_CHECK_INTERVAL == 0` OR `_correction_turns >= 2`; after each check `_correction_turns` resets to 0 | `AC-CR033-004`, `AC-CR033-005` | `CR-033` | `src/background_review.py` — `_DRIFT_CHECK_INTERVAL=12`, `_should_run_drift_check()`, drift tracking in `_process()` |
| `FR-ORCH-043` | functional | P1 | implemented | When `BackgroundReview.drift_detected` is `True` at the start of a turn, `_agent_loop()` appends `_DRIFT_IDENTITY_REMINDER` to the system prompt and immediately calls `clear_drift()` | `AC-CR033-003`, `AC-CR033-006` | `CR-033` | `src/chat.py` — `_DRIFT_IDENTITY_REMINDER` constant; drift injection between `assemble_system_prompt()` and Phase 2 skill scoring |
| `NFR-ORCH-016` | non-functional | P1 | implemented | Drift judge uses `call_local` with `ROUTER_MODEL` (local model); prompt capped at `_DRIFT_PROMPT_MAX_CHARS=800`; only asked "DRIFT or OK"; result parsed case-insensitively for "DRIFT" | `AC-CR033-001`, `AC-CR033-002` | `CR-033` | `src/background_review.py` — `_DRIFT_JUDGE_PROMPT`, `_check_drift_with_identity()`, `_DRIFT_PROMPT_MAX_CHARS` |
| `NFR-ORCH-017` | non-functional | P1 | implemented | Drift flag read/write are thread-safe via `_drift_lock`; all exceptions in `_check_drift_with_identity()` are swallowed silently; `_get_identity_anchor()` returns empty string on any failure | `AC-CR033-003` | `CR-033` | `src/background_review.py` — `_drift_lock`, try/except in `_run_drift_check()` and `_get_identity_anchor()` |

### Acceptance criteria — Persona Drift Detection (CR-033)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR033-001` | `FR-ORCH-042`, `NFR-ORCH-016` | DRIFT response | `_check_drift_with_identity(identity)` with `call_local` returning `"DRIFT"` | — | `drift_detected` becomes `True` | implemented |
| `AC-CR033-002` | `FR-ORCH-042`, `NFR-ORCH-016` | OK response | Same setup, `call_local` returns `"OK"` | — | `drift_detected` stays `False` | implemented |
| `AC-CR033-003` | `FR-ORCH-043`, `NFR-ORCH-017` | clear_drift | Set `_drift_detected=True`, call `clear_drift()` | — | `drift_detected` is `False` | implemented |
| `AC-CR033-004` | `FR-ORCH-042` | Interval trigger | `_turn_count=_DRIFT_CHECK_INTERVAL`, `_correction_turns=0` | — | `_should_run_drift_check()` returns `True` | implemented |
| `AC-CR033-005` | `FR-ORCH-042` | Correction pressure | `_turn_count=1`, `_correction_turns=2` | — | `_should_run_drift_check()` returns `True` | implemented |
| `AC-CR033-006` | `FR-ORCH-043` | Reminder constant | `from src.chat import _DRIFT_IDENTITY_REMINDER` | — | Non-empty string; contains "IDENTITY REMINDER" | implemented |
| `AC-CR033-007` | All CR-033 | Smoke tests | `python smoke_test.py` | — | 109 passed, 0 failed | implemented |

### Implicit Preference Learning (CR-034)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-PREF-001` | functional | P1 | implemented | `is_rephrased_query(prev, curr) -> bool` — pure heuristic; returns `True` when (a) strings are not identical AND (b) shared non-stopword count >= `_REPHRASE_MIN_SHARED_WORDS (2)` AND (c) Jaccard similarity on all tokens >= `_REPHRASE_SIMILARITY_THRESHOLD (0.30)` | `AC-CR034-001`, `AC-CR034-002`, `AC-CR034-003` | `CR-034` | `src/preference_learning.py` — `is_rephrased_query()`, `_STOPWORDS`, `_REPHRASE_MIN_SHARED_WORDS`, `_REPHRASE_SIMILARITY_THRESHOLD` |
| `FR-PREF-002` | functional | P1 | implemented | `BackgroundReview` tracks `_prev_user_input`; after each turn if `is_rephrased_query(prev, curr)` is `True`, stores a `memory_facts` entry with `category="preference"`, `source="implicit_rephrase_detection"`, `confidence=0.65` | `AC-CR034-001` | `CR-034` | `src/background_review.py` — `_prev_user_input`, `_maybe_store_rephrase()`, rephrase hook in `_process()` |
| `FR-PREF-003` | functional | P1 | implemented | `decay_and_prune(conn) -> tuple[int, int]` applies `confidence *= 0.95` to implicit preferences; deletes rows where `confidence < 0.30`; called once at session start from `XochitlChat.start()`; returns `(decayed_count, pruned_count)` | `AC-CR034-004`, `AC-CR034-005` | `CR-034` | `src/preference_learning.py` — `decay_and_prune()`; `src/chat.py` — try/except call in `start()` |
| `NFR-PREF-001` | non-functional | P1 | implemented | `is_rephrased_query` is a pure function (no LLM call, no DB access); `decay_and_prune` wrapped in try/except at call site; `_maybe_store_rephrase` wrapped in try/except — none may raise to caller | `AC-CR034-001` through `AC-CR034-005` | `CR-034` | `src/preference_learning.py`, `src/background_review.py`, `src/chat.py` |

### Acceptance criteria — Implicit Preference Learning (CR-034)

| ID | Requirements | Scenario | Input | Pre-conditions | Expected | Status |
|---|---|---|---|---|---|---|
| `AC-CR034-001` | `FR-PREF-001` | Rephrase detected | `is_rephrased_query("What tasks are in my Notion queue?", "Which Notion tasks are pending?")` | — | `True` | implemented |
| `AC-CR034-002` | `FR-PREF-001` | Different topic | `is_rephrased_query("What tasks are in my Notion queue?", "What is the weather today?")` | — | `False` | implemented |
| `AC-CR034-003` | `FR-PREF-001` | Identical strings | `is_rephrased_query("Investigate Python", "Investigate Python")` | — | `False` | implemented |
| `AC-CR034-004` | `FR-PREF-003` | Decay applied | `decay_and_prune` on implicit preference with `confidence=0.80` | In-memory SQLite | `confidence` becomes `0.76`; row not pruned | implemented |
| `AC-CR034-005` | `FR-PREF-003` | Pruned below threshold | `decay_and_prune` on implicit preference with `confidence=0.29` | In-memory SQLite | Row deleted; `pruned_count >= 1` | implemented |
| `AC-CR034-006` | All CR-034 | Smoke tests | `python smoke_test.py` | — | 114 passed, 0 failed | implemented |

### Progressive Personalization Milestones (CR-035)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-PREF-004` | functional | P1 | implemented | `get_milestone(session_count: int) -> Milestone` returns `Milestone.M1` for sessions 1–5, `Milestone.M2` for sessions 6–20, `Milestone.M3` for sessions 21+; pure function, no DB access | `AC-CR035-001`, `AC-CR035-002`, `AC-CR035-003` | `CR-035` | `src/milestones.py` — `Milestone` enum, `get_milestone()`, `_M1_MAX_SESSIONS=5`, `_M2_MAX_SESSIONS=20` |
| `FR-PREF-005` | functional | P1 | implemented | `ContextManager.assemble_system_prompt()` injects `milestone_context_block(milestone)` when non-empty; M1 returns `""` (no injection); M2 and M3 inject personalization guidance blocks | `AC-CR035-004`, `AC-CR035-005` | `CR-035` | `src/milestones.py` — `milestone_context_block()`, `_MILESTONE_BLOCKS`; `src/context_manager.py` — `milestone_block` param in `__init__()`, injection in `assemble_system_prompt()` |
| `NFR-PREF-002` | non-functional | P1 | implemented | Milestone transitions are silent — logged internally at DEBUG only; never surfaced to user; `XochitlChat.start()` computes milestone and logs it; `_milestone_block` used per-turn; no user-facing announcement ever written | `AC-CR035-001` through `AC-CR035-005` | `CR-035` | `src/chat.py` — `logger.debug()` only; try/except wrapper around milestone computation; `getattr(self, "_milestone_block", "")` fallback in `_agent_loop()` |

### Acceptance criteria — Progressive Personalization Milestones (CR-035)

| ID | Requirements | Scenario | Input | Pre-conditions | Expected | Status |
|---|---|---|---|---|---|---|
| `AC-CR035-001` | `FR-PREF-004` | M1 boundary | `get_milestone(1)` and `get_milestone(5)` | — | Both return `Milestone.M1` | implemented |
| `AC-CR035-002` | `FR-PREF-004` | M2 boundary | `get_milestone(6)` and `get_milestone(20)` | — | Both return `Milestone.M2` | implemented |
| `AC-CR035-003` | `FR-PREF-004` | M3 boundary | `get_milestone(21)` and `get_milestone(100)` | — | Both return `Milestone.M3` | implemented |
| `AC-CR035-004` | `FR-PREF-005` | M1 empty block | `milestone_context_block(Milestone.M1)` | — | Returns empty string | implemented |
| `AC-CR035-005` | `FR-PREF-005` | M2/M3 blocks non-empty | `milestone_context_block(Milestone.M2)`, `milestone_context_block(Milestone.M3)` | — | Both return non-empty strings with `## Personalization` header | implemented |
| `AC-CR035-006` | All CR-035 | Smoke tests | `python smoke_test.py` | — | 119 passed, 0 failed | implemented |

### Controlled Initiative (CR-038)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-INIT-001` | functional | P1 | implemented | `InitiativeEngine.submit(signal)` rejects silently if: mode=OFF, mode=ERRORS_ONLY and category != SYSTEM_FAILURE, confidence < 0.80, or category suppressed; otherwise queues in `_pending` | `AC-CR038-001`, `AC-CR038-002`, `AC-CR038-003`, `AC-CR038-004` | `CR-038` | `src/initiative.py` — `InitiativeEngine.submit()`, `_CONFIDENCE_THRESHOLD=0.80`, `ProactiveMode` checks |
| `FR-INIT-002` | functional | P1 | implemented | `InitiativeEngine.dismiss(category)` increments dismissal counter; after `_DISMISS_THRESHOLD (3)` the category is added to `_suppressed` and all future signals of that category are rejected | `AC-CR038-005` | `CR-038` | `src/initiative.py` — `dismiss()`, `_DISMISS_THRESHOLD=3`, `_suppressed` set |
| `FR-INIT-003` | functional | P1 | implemented | `InitiativeEngine.drain() -> list[ProactiveSignal]` returns and clears `_pending`; second call returns `[]` | `AC-CR038-002` | `CR-038` | `src/initiative.py` — `drain()` |
| `NFR-INIT-001` | non-functional | P1 | implemented | `submit()`, `dismiss()`, `drain()` never raise; below-threshold candidates logged at DEBUG only; `InitiativeEngine` wired to `BackgroundReview` via `_initiative_engine`; signals drained in `_agent_loop()` before LLM call | `AC-CR038-001` through `AC-CR038-005` | `CR-038` | `src/initiative.py` — try/except in all public methods; `src/chat.py` — drain+inject in `_agent_loop()`; `src/background_review.py` — `submit_initiative()` |

### Acceptance criteria — Controlled Initiative (CR-038)

| ID | Requirements | Scenario | Input | Pre-conditions | Expected | Status |
|---|---|---|---|---|---|---|
| `AC-CR038-001` | `FR-INIT-001` | OFF rejects all | `mode=OFF`, `SYSTEM_FAILURE`, conf=0.90 | — | `drain()` returns `[]` | implemented |
| `AC-CR038-002` | `FR-INIT-001`, `FR-INIT-003` | ERRORS_ONLY allows failure | `mode=ERRORS_ONLY`, `SYSTEM_FAILURE`, conf=0.90 | — | `drain()` returns the signal | implemented |
| `AC-CR038-003` | `FR-INIT-001` | ERRORS_ONLY rejects followup | `mode=ERRORS_ONLY`, `IN_SESSION_FOLLOWUP`, conf=0.90 | — | `drain()` returns `[]` | implemented |
| `AC-CR038-004` | `FR-INIT-001` | Low confidence rejected | `mode=FULL`, `SYSTEM_FAILURE`, conf=0.75 | — | `drain()` returns `[]` | implemented |
| `AC-CR038-005` | `FR-INIT-002` | 3 dismissals suppress | `dismiss()` x3, then `submit()` high-confidence | — | `drain()` returns `[]` | implemented |
| `AC-CR038-006` | All CR-038 | Smoke tests | `python smoke_test.py` | — | 129 passed, 0 failed | implemented |

### Safe Executor (CR-037)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-EXEC-001` | functional | P1 | implemented | `ActionGovernor.classify(action_type, target) -> ActionTier` returns AUTO for _AUTO_TYPES, CONFIRM for _CONFIRM_TYPES, DENY for path traversal or unknown types; pure function (NFR-EXEC-001) | `AC-CR037-001`, `AC-CR037-002`, `AC-CR037-003` | `CR-037` | `src/executor.py` — `ActionGovernor.classify()`, `_AUTO_TYPES`, `_CONFIRM_TYPES`, path traversal check |
| `FR-EXEC-002` | functional | P1 | implemented | `SafeExecutor.run(cmd, args)` calls governor first; AUTO proceeds via `subprocess.run(shell=False)`; CONFIRM raises `ConfirmationRequired`; DENY raises `PolicyViolation`; output capped at `_OUTPUT_CAP_BYTES (65536)` with `[truncated]` | `AC-CR037-004`, `AC-CR037-005` | `CR-037` | `src/executor.py` — `SafeExecutor.run()`, `_OUTPUT_CAP_BYTES=65536`, `ConfirmationRequired`, `PolicyViolation` |
| `FR-EXEC-003` | functional | P1 | implemented | `SafeExecutor` only executes commands in `_ALLOWED_COMMANDS` frozenset; any other command raises `PolicyViolation` before governor runs | `AC-CR037-004` | `CR-037` | `src/executor.py` — `_ALLOWED_COMMANDS` frozenset, allowlist check in `run()` |
| `NFR-EXEC-001` | non-functional | P1 | implemented | `subprocess.run()` never called with `shell=True`; `eval()` and `exec()` never called on generated/user-controlled input; `ActionGovernor.classify()` is a pure function with no side effects or I/O | `AC-CR037-001`, `AC-CR037-002`, `AC-CR037-003` | `CR-037` | `src/executor.py` — `shell=False` in `run()`; no `eval`/`exec` calls; `classify()` is a static method |
| `NFR-EXEC-002` | non-functional | P1 | implemented | Output size-capped before returning; raw stdout/stderr never passed uncapped to LLM; governor always called before any `subprocess.run()` — no bypass path | `AC-CR037-005` | `CR-037` | `src/executor.py` — output cap logic in `run()` after `subprocess.run()`; governor check precedes subprocess call |

### Acceptance criteria — Safe Executor (CR-037)

| ID | Requirements | Scenario | Input | Pre-conditions | Expected | Status |
|---|---|---|---|---|---|---|
| `AC-CR037-001` | `FR-EXEC-001` | AUTO for read | `classify("read", "src/chat.py")` | — | `ActionTier.AUTO` | implemented |
| `AC-CR037-002` | `FR-EXEC-001` | CONFIRM for delete | `classify("delete", "output.txt")` | — | `ActionTier.CONFIRM` | implemented |
| `AC-CR037-003` | `FR-EXEC-001` | DENY path traversal | `classify("exec", "../../etc/passwd")` | — | `ActionTier.DENY` | implemented |
| `AC-CR037-004` | `FR-EXEC-003` | PolicyViolation for unknown cmd | `SafeExecutor.run("not_on_allowlist", [])` | — | Raises `PolicyViolation` | implemented |
| `AC-CR037-005` | `FR-EXEC-002`, `NFR-EXEC-002` | Output truncated | `run("git", ...)` with mocked stdout > 65536 bytes | subprocess mocked | `result.truncated=True`; stdout contains `[truncated]` | implemented |
| `AC-CR037-006` | All CR-037 | Smoke tests | `python smoke_test.py` | — | 129 passed, 0 failed | implemented |

### Bounded Explorer (CR-023)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-039` | functional | P1 | implemented | `ExplorerSkill.can_handle()` returns ≥ 0.85 for queries containing investigative keywords ("investigate", "research", "explore", "analyze", "dig into", "look into", etc.); returns 0.70 for multi-hop indicators; returns 0.0 for plain lookup queries | `AC-CR023-002` | `CR-023` | `src/skills/explorer_skill.py` — `ExplorerSkill.can_handle()`; keyword tuples `_INVESTIGATIVE_KEYWORDS`, `_MULTI_HOP_INDICATORS` |
| `FR-ORCH-040` | functional | P1 | implemented | `ExplorerSkill.execute()` runs a bounded multi-step investigation loop: (1) form subquestion, (2) convergence check via action hash, (3) gather evidence via `WebLookupSkill`, (4) score heuristic confidence (no LLM call), (5) stop if confidence > 0.85, (6) escalate if confidence < 0.30 at step ≥ 3, (7) synthesize at budget exhaustion | `AC-CR023-003`, `AC-CR023-004`, `AC-CR023-005` | `CR-023` | `src/skills/explorer_skill.py` — `ExplorerSkill.execute()` and private helpers |
| `FR-ORCH-041` | functional | P1 | implemented | `ExplorerSkill` is registered in `XochitlChat._builtin_skills` and present in the `skills` property alongside all other built-in skills | `AC-CR023-006` | `CR-023` | `src/chat.py` — `ExplorerSkill()` appended to `_builtin_skills` list |
| `NFR-ORCH-014` | non-functional | P1 | implemented | Hard step budget is `_MAX_STEPS = 6` (named constant); repeat action-hash = loop detected → stop immediately before budget; on budget exhaustion `_synthesize()` is called with notes containing "Step budget exhausted" | `AC-CR023-003`, `AC-CR023-004` | `CR-023` | `src/skills/explorer_skill.py` — `_MAX_STEPS`, `seen_hashes` set, post-loop `_synthesize()` call |
| `NFR-ORCH-015` | non-functional | P1 | implemented | Confidence evaluation is a pure heuristic (no LLM call per step); sub-question generation steps 2+ use `force_route="simple_qa"`; final synthesis uses `force_route="general"` | `AC-CR023-003`, `AC-CR023-004`, `AC-CR023-005` | `CR-023` | `src/skills/explorer_skill.py` — `_score_confidence()` has no router import; `_form_subquestion()` and `_synthesize()` use explicit `force_route` |

### Acceptance criteria — Bounded Explorer (CR-023)

| ID | Requirement | Scenario | Trigger | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR023-001` | `FR-ORCH-039`, `FR-ORCH-040` | Import | `from src.skills.explorer_skill import ExplorerSkill` | — | `can_handle()`, `execute()`, `suggest()`, `tool_definition()` all callable | implemented |
| `AC-CR023-002` | `FR-ORCH-039` | Keyword scoring | `ExplorerSkill().can_handle("investigate the history of Python", {})` | — | Returns ≥ 0.65 (above `_SKILL_INJECT_THRESHOLD`); plain queries return 0.0 | implemented |
| `AC-CR023-003` | `FR-ORCH-040`, `NFR-ORCH-014` | Loop detection | `execute()` with `_form_subquestion` patched to always return the same string | — | Loop detected at step 2; `_synthesize()` called with notes containing "loop"; gather calls < `_MAX_STEPS` | implemented |
| `AC-CR023-004` | `FR-ORCH-040`, `NFR-ORCH-014` | Budget exhaustion | `execute()` with medium-quality evidence (confidence stays 0.30–0.85 through all steps) | — | After `_MAX_STEPS` steps `_synthesize()` called with notes containing "budget exhausted" | implemented |
| `AC-CR023-005` | `FR-ORCH-040`, `NFR-ORCH-015` | High-confidence stop | `execute()` with rich evidence (420-char snippets → confidence > 0.85 at step 3) | — | Stops before `_MAX_STEPS`; `_synthesize()` called without budget note | implemented |
| `AC-CR023-006` | `FR-ORCH-041` | Registration | `XochitlChat.__new__` with `_builtin_skills=None` then inspect `.skills` | — | `ExplorerSkill` instance present in list | implemented |
| `AC-CR023-007` | All CR-023 | Smoke tests | `python smoke_test.py` | — | 103 passed, 0 failed | implemented |

### Terminal Visual Grammar (CR-039)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-UI-009` | functional | P1 | implemented | `src/terminal_output.py` provides semantic line formatting: prefixes (done/action/warn/fail), 2-space indent, 80-col wrap via `format_line`, `format_block`, `format_step`, `format_skill_output` | `AC-CR039-001`, `AC-CR039-002`, `AC-CR039-003` | `CR-039` | `src/terminal_output.py` |
| `FR-UI-010` | functional | P1 | implemented | CLI group accepts `--json`; `today`, `queue`, `done` emit `cli_payload()` JSON | `AC-CR039-004` | `CR-039` | `src/cli.py` — `_json_mode()`, `print_json()` |
| `NFR-UI-009` | non-functional | P2 | implemented | Wrapped operational lines target ≤80 characters for pipe/copy safety | `AC-CR039-001` | `CR-039` | `MAX_LINE_WIDTH = 80` in `terminal_output.py` |

### Acceptance criteria — Terminal Visual Grammar (CR-039)

| ID | Requirements | Scenario | Input | Pre-conditions | Expected | Status |
|---|---|---|---|---|---|---|
| `AC-CR039-001` | `FR-UI-009`, `NFR-UI-009` | Wrap width | `wrap_text()` on long string, width=40 | — | All lines ≤42 (continuation indent) | implemented |
| `AC-CR039-002` | `FR-UI-009` | Plain prefixes | `format_line(..., rich=False)` | — | `[ok]` and `->` prefixes present | implemented |
| `AC-CR039-003` | `FR-UI-009` | Step format | `format_step(1, 3, "Fetch")` | — | Output contains `[1/3]` | implemented |
| `AC-CR039-004` | `FR-UI-010` | CLI JSON | `xochitl --json today` | — | Valid JSON with `command` and `data.queue` | implemented |
| `AC-CR039-005` | `FR-UI-010` | Status JSON | `xochitl --json status` | — | JSON contains `projects` and `queue` | implemented |
| `AC-CR039-006` | `FR-UI-010` | Chat JSON guard | `xochitl --json chat` | — | `ok: false`, `interactive_only` error | implemented |
| `AC-CR039-007` | All CR-039 | Smoke tests | `python smoke_test.py` | — | 146 passed, 0 failed (suite cumulative) | implemented |

### Compact Reasoning Disclosure (CR-040)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-ORCH-044` | functional | P1 | implemented | One-line action summary printed before skill/weather execution via `_emit_action_line()` and `action_summary()` | `AC-CR040-002` | `CR-040` | `src/chat.py`, `src/action_disclosure.py` |
| `FR-ORCH-045` | functional | P1 | implemented | Skill results use `format_compact_result()` to pair action label with formatted body | `AC-CR040-003` | `CR-040` | `src/chat.py` `_agent_loop()` skill path |
| `FR-ORCH-046` | functional | P1 | implemented | `is_why_request()` short-circuits to `build_why_expansion()` in `process_message()` | `AC-CR040-001` | `CR-040` | `src/chat.py`, `prompts/system_xochitl.txt` `[REASONING DISCLOSURE]` |

### Acceptance criteria — Compact Reasoning Disclosure (CR-040)

| ID | Requirements | Scenario | Input | Pre-conditions | Expected | Status |
|---|---|---|---|---|---|---|
| `AC-CR040-001` | `FR-ORCH-046` | Why detection | `is_why_request("Why?")` vs normal query | — | True for why; False for weather query | implemented |
| `AC-CR040-002` | `FR-ORCH-044` | Action summary | `action_summary("Checking weather")` | — | Label text in output | implemented |
| `AC-CR040-003` | `FR-ORCH-045` | Compact result | `format_compact_result(action, body)` | — | Both action and body present | implemented |
| `AC-CR040-004` | `FR-ORCH-046` | Prompt section | Read `system_xochitl.txt` | — | Contains `[REASONING DISCLOSURE]` | implemented |
| `AC-CR040-005` | All CR-040 | Smoke tests | `python smoke_test.py` | — | 146 passed, 0 failed (suite cumulative) | implemented |

### Procedural Memory (CR-041)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-MEM-008` | functional | P1 | implemented | `workflows` SQLite table + CRUD for reusable step sequences (separate from semantic memory) | `AC-CR041-001` | `CR-041` | `src/database.py` |
| `FR-MEM-009` | functional | P1 | implemented | `search_workflows_by_intent()` top-1 hybrid match (keyword + `workflow_intents` embeddings, CR-042) when score >= 0.50 | `AC-CR041-002`, `AC-CR042-004` | `CR-041`, `CR-042` | `src/workflows.py`, `src/workflow_vector.py` |
| `FR-MEM-010` | functional | P1 | implemented | `_agent_loop()` injects `[PROCEDURAL WORKFLOW]` block capped at 2000 chars | `AC-CR041-003` | `CR-041` | `src/chat.py` |
| `FR-MEM-011` | functional | P1 | implemented | Multi-step offer + `/workflows` + `/workflow save <name>` (LLM distill, CR-042) + `/workflow run <name>` | `AC-CR041-004`, `AC-CR042-003` | `CR-041`, `CR-042` | `src/workflows.py`, `src/chat.py`, `src/skills/workflow_skill.py` |

### Acceptance criteria — Procedural Memory (CR-041)

| ID | Requirements | Scenario | Input | Pre-conditions | Expected | Status |
|---|---|---|---|---|---|---|
| `AC-CR041-001` | `FR-MEM-008` | Upsert round-trip | in-memory DB | — | Name and steps match | implemented |
| `AC-CR041-002` | `FR-MEM-009` | Intent search | weekly review query | seeded workflow | Match returned | implemented |
| `AC-CR041-003` | `FR-MEM-010` | Block cap | `format_workflow_block` | large steps | len <= 2000 | implemented |
| `AC-CR041-004` | `FR-MEM-011` | Distill | 2 tool turns in history | — | >= 2 steps | implemented |
| `AC-CR041-005` | All CR-041 | Smoke tests | `python smoke_test.py` | — | 146 passed, 0 failed (suite cumulative) | implemented |

### Procedural Memory Phase 2 (CR-042)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-MEM-012` | functional | P2 | implemented | `WorkflowVectorIndex` LanceDB table `workflow_intents` for embedding recall (separate from `memories`) | `AC-CR042-001`, `AC-CR042-004` | `CR-042` | `src/workflow_vector.py` |
| `FR-MEM-013` | functional | P2 | implemented | `distill_workflow_trajectory()` LLM distillation with mechanical fallback on save | `AC-CR042-002` | `CR-042` | `src/workflows.py` |
| `FR-MEM-014` | functional | P2 | implemented | `execute_workflow()` + `WorkflowSkill` + `/workflow run <name>` | `AC-CR042-003` | `CR-042` | `src/workflows.py`, `src/skills/workflow_skill.py`, `src/chat.py` |

### Acceptance criteria — Procedural Memory Phase 2 (CR-042)

| ID | Requirements | Scenario | Input | Pre-conditions | Expected | Status |
|---|---|---|---|---|---|---|
| `AC-CR042-001` | `FR-MEM-012` | Vector search | mocked index | indexed workflow | workflow_id returned | implemented |
| `AC-CR042-002` | `FR-MEM-013` | LLM distill | mocked `call_local` | JSON steps | parsed and used | implemented |
| `AC-CR042-003` | `FR-MEM-014` | Executor | two mock skills | workflow dict | both steps run in order | implemented |
| `AC-CR042-004` | `FR-MEM-012` | Hybrid search | embed hit + weak keyword | seeded row | combined score matches | implemented |
| `AC-CR042-005` | All CR-042 | Smoke tests | `python smoke_test.py` | — | 146 passed, 0 failed | implemented |

### GPU-Aware Model Selection (CR-043)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-GPU-001` | functional | P1 | implemented | `_classify_profile()` maps total VRAM (MB) to `HardwareProfile` enum: WORKSTATION>=20GB, DESKTOP>=12GB, LAPTOP>=6GB, MINIMAL<6GB | `AC-CR043-001`, `AC-CR043-002`, `AC-CR043-003` | `CR-043` | `src/model_manager.py` |
| `FR-GPU-002` | functional | P1 | implemented | `select_model()` returns model name from `_PROFILES[_HARDWARE_PROFILE][role]`; detected once at import time | `AC-CR043-004` | `CR-043` | `src/model_manager.py` |
| `FR-GPU-003` | functional | P2 | implemented | `get_startup_report()` returns GPU info + model assignments as plain text | `AC-CR043-005` | `CR-043` | `src/model_manager.py` |
| `NFR-GPU-001` | non-functional | P1 | implemented | Profile detection uses total VRAM (stable), not free VRAM (fluctuates) | `AC-CR043-003` | `CR-043` | `src/model_manager.py` (`get_vram_info`) |

### Acceptance criteria — GPU-Aware Model Selection (CR-043)

| ID | Requirements | Scenario | Input | Expected | Status |
|---|---|---|---|---|---|
| `AC-CR043-001` | `FR-GPU-001` | 16 GB total VRAM | `_classify_profile(16384)` | `DESKTOP` | implemented |
| `AC-CR043-002` | `FR-GPU-001` | 8 GB total VRAM | `_classify_profile(8192)` | `LAPTOP` | implemented |
| `AC-CR043-003` | `FR-GPU-001`, `NFR-GPU-001` | No GPU / None | `_classify_profile(None)` | `MINIMAL` | implemented |
| `AC-CR043-004` | `FR-GPU-002` | DESKTOP + thinking role | `select_model("thinking")` w/ DESKTOP profile | `qwen3:14b` | implemented |
| `AC-CR043-005` | `FR-GPU-003` | Startup report | `get_startup_report()` | contains profile name and model name | implemented |

### Doppler-First Secrets Management (CR-044)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `NFR-SEC-002` | non-functional | P1 | implemented | `secrets.load()` injects Doppler secrets into `os.environ` at boot before any skill reads credentials | `AC-CR044-001` | `CR-044` | `src/secrets.py` (`_try_doppler`) |
| `NFR-SEC-003` | non-functional | P1 | implemented | Falls back to `.env` if Doppler unavailable; silent in both cases | `AC-CR044-002` | `CR-044` | `src/secrets.py` (`_try_dotenv`) |
| `NFR-SEC-004` | non-functional | P1 | implemented | Doppler keys do not overwrite keys already in `os.environ` (non-destructive merge) | `AC-CR044-003` | `CR-044` | `src/secrets.py` (`_try_doppler` — `if key not in os.environ`) |

### Acceptance criteria — Doppler Secrets (CR-044)

| ID | Requirements | Scenario | Expected | Status |
|---|---|---|---|---|
| `AC-CR044-001` | `NFR-SEC-002` | Doppler CLI available and configured | `secrets.load()` returns `'doppler'` | implemented |
| `AC-CR044-002` | `NFR-SEC-003` | Doppler unavailable, .env present | `secrets.load()` returns `'dotenv'` | implemented |
| `AC-CR044-003` | `NFR-SEC-004` | Key already in env | Doppler value does not overwrite | implemented |

### Google Maps Skill (CR-045)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-MAPS-001` | functional | P1 | implemented | Directions and travel time between two points via Google Directions API | `AC-CR045-001`, `AC-CR045-004`, `AC-CR045-005` | `CR-045` | `src/skills/maps_skill.py` (`_directions`, `_format_directions`) |
| `FR-MAPS-002` | functional | P1 | implemented | Places search (restaurants, shops, etc.) near a location via Google Places API | `AC-CR045-002`, `AC-CR045-006` | `CR-045` | `src/skills/maps_skill.py` (`_places`, `_format_places`) |
| `FR-MAPS-003` | functional | P2 | implemented | Uses saved home preference as default origin/location when omitted | — | `CR-045` | `src/skills/maps_skill.py` (`_default_location`) |
| `FR-MAPS-004` | non-functional | P1 | implemented | API key read from secrets store (`GOOGLE_MAPS_API_KEY`); missing key returns setup instruction | `AC-CR045-007` | `CR-045` | `src/skills/maps_skill.py` (`execute`) |
| `NFR-MAPS-001` | non-functional | P1 | implemented | All Maps HTTP calls use `http_utils.fetch_bytes` (SSRF guard + retry) | — | `CR-045` | `src/skills/maps_skill.py` (`_fetch_json`) |

### Acceptance criteria — Google Maps (CR-045)

| ID | Requirements | Scenario | Expected | Status |
|---|---|---|---|---|
| `AC-CR045-001` | `FR-MAPS-001` | `can_handle("directions to the library")` | >= 0.90 | implemented |
| `AC-CR045-002` | `FR-MAPS-002` | `can_handle("find a coffee shop near me")` | >= 0.90 | implemented |
| `AC-CR045-003` | `FR-MAPS-001` | `can_handle("what is the weather")` | 0.0 | implemented |
| `AC-CR045-004` | `FR-MAPS-001` | `_extract_destination("directions to downtown San Diego")` | contains "San Diego" | implemented |
| `AC-CR045-005` | `FR-MAPS-001` | `_format_directions()` with mock data | includes distance, duration, steps | implemented |
| `AC-CR045-006` | `FR-MAPS-002` | `_format_places()` with mock data | includes name, rating, open status | implemented |
| `AC-CR045-007` | `FR-MAPS-004` | Missing API key | returns setup instruction with key name | implemented |

### Gmail Skill (CR-046a)

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-GMAIL-001` | functional | P1 | implemented | List unread inbox messages with from/subject/date/snippet; `gmail_last_list` stored in context | `AC-CR046a-001`, `AC-CR046a-006` | `CR-046a` | `src/skills/gmail_skill.py` (`_inbox`, `_format_inbox`) |
| `FR-GMAIL-002` | functional | P1 | implemented | Search Gmail using natural-language queries mapped to Gmail query syntax | `AC-CR046a-003`, `AC-CR046a-005` | `CR-046a` | `src/skills/gmail_skill.py` (`_search`, `_extract_search_query`) |
| `FR-GMAIL-003` | functional | P1 | implemented | Send email via RFC 2822 + base64url encoding to Gmail send API | `AC-CR046a-002`, `AC-CR046a-008` | `CR-046a` | `src/skills/gmail_skill.py` (`_send`, `_build_raw_message`) |
| `FR-GMAIL-004` | functional | P2 | implemented | Mark as read and archive emails by 1-based index into last shown list | — | `CR-046a` | `src/skills/gmail_skill.py` (`_mark_read`) |
| `NFR-GMAIL-001` | non-functional | P1 | implemented | Auth failure returns descriptive message; no email content persisted to disk | `AC-CR046a-009` | `CR-046a` | `src/skills/gmail_skill.py` (`execute` try/except) |

### Acceptance criteria — Gmail (CR-046a)

| ID | Requirements | Scenario | Expected | Status |
|---|---|---|---|---|
| `AC-CR046a-001` | `FR-GMAIL-001` | `can_handle("check my email")` | >= 0.90 | implemented |
| `AC-CR046a-002` | `FR-GMAIL-003` | `can_handle("send an email to bob")` | >= 0.90 | implemented |
| `AC-CR046a-003` | `FR-GMAIL-002` | `can_handle("find emails from alice")` | >= 0.90 | implemented |
| `AC-CR046a-004` | `FR-GMAIL-001` | `can_handle("what is the weather")` | 0.0 | implemented |
| `AC-CR046a-005` | `FR-GMAIL-002` | `_extract_search_query("emails from alice@gmail.com")` | `"from:alice@gmail.com"` | implemented |
| `AC-CR046a-006` | `FR-GMAIL-001` | `_format_inbox()` with mock data | includes sender, subject, snippet | implemented |
| `AC-CR046a-007` | `FR-GMAIL-001` | `_format_full_message()` with mock data | includes From, To, Subject, body | implemented |
| `AC-CR046a-008` | `FR-GMAIL-003` | `_build_raw_message()` | non-empty base64, contains recipient | implemented |
| `AC-CR046a-009` | `NFR-GMAIL-001` | Auth FileNotFoundError | returns descriptive string, no exception raised | implemented |

## Requirement lifecycle notes

- Never reuse deprecated IDs.
- If a requirement changes meaning, create a new ID and mark the old one superseded.
- If a requirement is split, create child IDs and update traceability.
- If a requirement is merged, preserve all old IDs as superseded aliases.
