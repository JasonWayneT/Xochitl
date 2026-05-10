# CR-004 - Conversational Intelligence Layer

## Status

Stages 1-6 are implemented. CR validation/audit follow-up remains pending.

## Summary

Design and implement Xochitl's conversational intelligence layer so the primary
experience feels like a local-first personal productivity partner and sounding
board with access to tools, memory, and skills. Xochitl should keep context
small, route models cost-consciously, chain read-only exploration automatically,
and require approval before writes, deletes, or mutating commands.

This change extends the existing chat, routing, context, memory, and skill
systems. It does not replace the local-first model routing or the BMAD/SDD
workflow.

## User Direction

- Optimize first for personal productivity, sounding-board use, and a "Jarvis"
  style assistant experience.
- Keep BMAD/SDD active for coding projects, but do not load coding-project
  context into every normal conversation.
- Use as few tokens as practical. Prefer selective context over broad context.
- Push back warmly and clearly, including interrupting bad reasoning when needed.
- Automatically chain read-only actions. Stop for plan and approval before
  writes, deletes, or mutating command execution.
- Suggest skill creation after successful multi-step work that appears reusable.
- Store global skills under `~/.xochitl/skills/` and project skills under
  `<project>/.xochitl/skills/`.
- Keep slash commands as optional power-user shortcuts.
- Store preferences globally unless they are clearly project-specific.
- Use local models by default for productivity chat, with cloud fallback for
  complex reasoning, synthesis, planning, or low confidence.
- Include persistent personal persona/config loading from `~/.xochitl/`, repo
  fallback templates, a central system prompt template, and test conversation
  scenarios in the implementation plan.
- Preserve and improve Xochitl's Latina/Mexican cultural voice. She should use
  light A1-A2 Spanish words or short phrases naturally, not full untranslated
  Spanish sentences, and never as a caricature.
- When Xochitl initializes a project, it should create BMAD files, SDD workflow
  scaffolding, and an `AGENTS.md` style instruction file that explains the SDD
  process for future agents working in that project.

## Affected Requirements

| ID | Type | Priority | Status | Description |
|---|---|---|---|---|
| `FR-ORCH-010` | functional | P0 | implemented | Xochitl classifies each chat turn into exploration, execution, planning, clarification, productivity, emotional/support, or skill-learning intent before tool selection. |
| `FR-ORCH-011` | functional | P0 | implemented | Xochitl chains read-only exploration actions automatically and requires a plan plus explicit approval before writes, deletes, or mutating commands. |
| `FR-ORCH-012` | functional | P0 | implemented | Xochitl loads persona and behavior instructions from project-local overrides, `~/.xochitl/`, repo fallback templates, and a central system prompt template through the existing context assembly path. |
| `DATA-DATA-004` | data | P0 | implemented | Xochitl stores structured user preferences separately from semantic memory and recalls relevant preferences at the start of conversations. |
| `DATA-DATA-005` | data | P1 | implemented | Xochitl preloads relevant long-term semantic memories for each turn using meaning-based retrieval while respecting token budgets. |
| `FR-ORCH-013` | functional | P1 | implemented | Xochitl detects successful reusable multi-step workflows and offers to create a skill after the task completes. |
| `FR-ORCH-014` | functional | P1 | implemented | Xochitl loads global and project-specific dynamic skills from filesystem skill folders with metadata, examples, and optional assets. |
| `FR-SDD-005` | functional | P0 | implemented | Project initialization creates BMAD artifacts, SDD workflow scaffolding, and project-local agent instructions explaining the BMAD to SDD to code process. |
| `NFR-PERF-007` | non-functional | P0 | proposed | Conversational context assembly prefers selective retrieval and mode-specific context to minimize token use and reduce confusion. |
| `ARCH-SDD-002` | architecture | P0 | proposed | Conversational model calls continue to route through `TieredRouter`; no new raw model API calls are introduced. |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR004-001` | `FR-ORCH-010` | Intent classification | A user sends a chat message | Xochitl processes the turn | The turn has a structured intent used by routing and tool selection. |
| `AC-CR004-002` | `FR-ORCH-011` | Read-only chain | User asks "help me understand this project" | Xochitl can inspect files | It performs bounded read-only exploration without asking for each read. |
| `AC-CR004-003` | `FR-ORCH-011` | Mutating action | User asks Xochitl to fix a bug | Xochitl identifies code changes | It presents a plan and waits for approval before editing files or running mutating commands. |
| `AC-CR004-004` | `FR-ORCH-012` | Persona loading | A chat session starts | Context is assembled | The system prompt includes persona and behavior layers from the configured artifacts. |
| `AC-CR004-013` | `FR-ORCH-012` | Cultural voice | Xochitl responds in casual or supportive conversation | Persona guidance is active | She blends warmth, Mexican/Latina cultural texture, and light A1-A2 Spanish words or short phrases without overusing Spanish or switching into full untranslated Spanish. |
| `AC-CR004-005` | `DATA-DATA-004` | Preference recall | A stored user preference is relevant | A new session or turn begins | Xochitl recalls and applies the preference without requiring the user to repeat it. |
| `AC-CR004-006` | `DATA-DATA-004` | Preference save | User states a stable preference | The turn completes | Xochitl records the preference through an explicit preference save path. |
| `AC-CR004-007` | `DATA-DATA-005` | Memory preload | A current message relates to prior experience | Context is assembled | Relevant semantic memories are injected within the token budget. |
| `AC-CR004-008` | `FR-ORCH-013` | Skill proposal | A multi-step reusable workflow succeeds | The final response is generated | Xochitl offers to create a skill without forcing it. |
| `AC-CR004-009` | `FR-ORCH-014` | Dynamic skill loading | A valid skill folder exists globally or in the project | Xochitl starts or refreshes skills | The skill is available for conversational tool selection. |
| `AC-CR004-010` | `FR-SDD-005` | Project init | User asks to initialize a project | BMADSkill runs | The project includes BMAD files, SDD scaffolding, and project-local agent instructions. |
| `AC-CR004-011` | `NFR-PERF-007` | Token discipline | The active project has large docs | Xochitl handles a normal productivity chat | It does not inject unrelated BMAD/SDD context unless project workflow intent is detected. |
| `AC-CR004-012` | `ARCH-SDD-002` | Routing preservation | The conversational layer needs an LLM response | It calls a model | The call goes through `TieredRouter`. |

## Implementation Tasks

| ID | Requirement IDs | Task | Notes |
|---|---|---|---|
| `TASK-CR004-001` | `FR-ORCH-010`, `NFR-PERF-007` | Add a structured intent layer for conversation mode, action type, risk, and confidence. | Implemented for deterministic first-pass classification of productivity, sounding-board, exploration, execution, planning, clarification, emotional, casual, and skill-learning turns. |
| `TASK-CR004-002` | `FR-ORCH-011` | Add a bounded read-only exploration chain and plan-before-mutation gate. | Implemented in chat flow. Mutating skill calls are staged as pending plans, and new file writes now require confirmation through FileTools. |
| `TASK-CR004-003` | `FR-ORCH-012` | Add persona artifacts and central prompt template plumbing through ContextManager. | Implemented. Preserves existing system facts, provenance, skill manifest, and Xochitl's light Latina/Mexican voice. |
| `TASK-CR004-004` | `DATA-DATA-004` | Add structured preference store and recall/save tools. | Implemented with `preferences` table, database helpers, explicit chat save path, and ContextManager preference recall. |
| `TASK-CR004-005` | `DATA-DATA-005` | Formalize memory-bank preload from semantic memory. | Implemented through selective `memory.recall()` preload in `MemoryEngine`; recall is bounded to top 3 results. |
| `TASK-CR004-006` | `FR-ORCH-013`, `FR-ORCH-014` | Add dynamic skill proposal, storage, loading, and lifecycle metadata. | Implemented. Enabled dynamic skills load from global and project folders into the existing manifest; reusable workflows trigger one optional skill-creation offer per session. |
| `TASK-CR004-007` | `FR-SDD-005` | Extend project initialization to include BMAD, SDD scaffolding, and project-local agent instructions. | Implemented. `BMADSkill.init_project()` creates BMAD placeholders, SDD specs/traceability scaffolding, tests/src folders, project `.xochitl/skills/`, and project-local `AGENTS.md`. |
| `TASK-CR004-008` | `ARCH-SDD-002` | Audit new conversational calls to ensure all model access goes through `TieredRouter`. | Also document any existing direct-call debt separately. |
| `TASK-CR004-009` | all CR-004 requirements | Add scenario tests and manual validation transcripts. | Include casual, technical, factual correction, risky idea, persona override, project init, and reusable workflow cases. |

## Verification Plan

- Run `python smoke_test.py`.
- Run `python end_to_end_test.py`.
- Add or update targeted tests for intent classification, preference storage,
  memory preload, skill loading, and project initialization.
- Manually validate the scenario transcripts defined in the conversational
  architecture document, including the cultural voice scenario.

## Verification Results

2026-05-10:

- `py_compile src/context_manager.py`: passed using bundled Codex Python.
- Prompt assembly sanity check: passed. `ContextManager` loads the persona,
  behavior config, and system template into the assembled prompt using the
  project -> user -> repo fallback order.
- Structured intent sanity check: passed. Representative productivity,
  exploration, execution, file-read, and skill-learning inputs produced the
  expected `intent_type`, `action_risk`, `context_scope`, and legacy handler
  `type` fields.
- Stage 3 syntax check: passed for `src/database.py`, `src/context_manager.py`,
  `src/chat.py`, and `src/intent.py` using bundled Codex Python.
- Structured preference sanity check: passed. `db.upsert_preference()`,
  `db.search_preferences()`, and `db.mark_preferences_used()` created,
  retrieved, marked, and then cleaned up a temporary preference row.
- Stage 4 syntax check: passed for `src/chat.py` and `src/file_tools.py` using
  bundled Codex Python.
- Stage 4 targeted approval-gate sanity check: passed. Mutating `CodeSkill`
  calls are converted into a pending `execute_skill_call` plan, require a yes/no
  response, and record the approved tool result as a `role=tool` turn.
- Stage 4 targeted exploration-intent sanity check: passed. "Help me understand
  this project" classifies as read-only active-project exploration.
- Stage 5 syntax check: passed for `src/chat.py`, `src/context_manager.py`, and
  `src/skills/dynamic_skill.py` using bundled Codex Python.
- Stage 5 targeted dynamic skill sanity check: passed. A temporary project-local
  skill with `SKILL.md`, `metadata.yaml`, and `examples.md` loaded into the
  manifest, exposed a safe `DynamicSkill_*` tool name, executed by returning
  its workflow text, and recorded session usage in memory. Skill-creation offer
  heuristic also passed for explicit reusable-workflow language.
- Stage 6 syntax check: passed for `src/skills/bmad_skill.py` and
  `src/skills/_yaml_helpers.py` using bundled Codex Python.
- Stage 6 targeted project-init sanity check: passed. A temporary project
  initialized with BMAD placeholder artifacts, SDD `core-features.md`,
  `specs/traceability.json`, `tests/`, project `.xochitl/skills/`, and
  project-local `AGENTS.md`; metadata recorded `sdd_scaffolded: true`.
- Dependency fallback syntax check: passed for `src/__init__.py`, `src/chat.py`,
  and `src/llm_interface.py` using bundled Codex Python.
- `smoke_test.py` with bundled Codex Python: 24 passed, 0 failed.
- `end_to_end_test.py` with bundled Codex Python: passed.
- `python smoke_test.py`: could not run with `python` because Python is not on
  PATH.
- `python end_to_end_test.py`: could not run with `python` because Python is not
  on PATH.

## Open Issues

- Existing docs reference ChromaDB while the code uses LanceDB. CR-004 should
  avoid widening that drift and should clarify the long-term memory backend.
- Existing code contains some raw SQL outside `src/database.py` and at least one
  direct model-call path outside `TieredRouter`; those are pre-existing
  architecture debts and should be handled deliberately, not silently mixed into
  this implementation unless required.
