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

## Requirement lifecycle notes

- Never reuse deprecated IDs.
- If a requirement changes meaning, create a new ID and mark the old one superseded.
- If a requirement is split, create child IDs and update traceability.
- If a requirement is merged, preserve all old IDs as superseded aliases.
