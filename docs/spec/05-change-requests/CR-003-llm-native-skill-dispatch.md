# CR-003: LLM-Native Skill Dispatch

## Summary

Replace brittle keyword-based intent routing and the fragile suggest→confirm skill
pattern with an LLM-controlled agent loop. The model sees its available skills as
structured tool definitions and decides when to invoke them via `<skill_call>` markers.
This gives Xochitl a Claude/Gemini-style experience where the model drives action,
not a cascade of Python keyword checks.

## Type

Architectural improvement

## Root cause

Four compounding problems in the pre-CR-003 conversation layer:

1. **Dual classification systems** — `chat.py::_classify_intent()` (keyword-only) and
   `router.py::_fast_classify()` (also keyword-only) run independently and can disagree
   on the same message. Neither uses the LLM to understand intent.

2. **Skill detection gated by intent** — `_check_skills()` only fires when
   `intent["type"]` is NOT in `(general, simple_question, task_query)`. A message that
   trips a task keyword bypasses skill scoring entirely, even if a skill scores 0.9.

3. **Fragile confirmation** — `_CONFIRM_YES` / `_CONFIRM_NO` are exact-match sets.
   "Go for it", "please do", and "sounds good" all fail silently.

4. **LLM never sees its own tools** — The model is only invoked for the final response.
   All routing decisions are made by Python keyword matching. The LLM has no agency
   over which skill runs.

## Affected Requirements

- `FR-CORE-004` — Chat session with intent classification (extends)
- `ARCH-SDD-001` — All LLM calls via TieredRouter (preserves)
- `FR-ORCH-003` — PreFlight Fact Injection (preserves)
- `FR-ORCH-004` — Provenance Tagging (preserves)
- `NFR-PERF-004` — Token budget via ContextManager (extends)

## New Requirements

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `FR-ORCH-005` | functional | P0 | Skills expose `tool_definition()` descriptor injected into every system prompt so the LLM knows what it can invoke |
| `FR-ORCH-006` | functional | P0 | All response paths use `ContextManager` for system prompt assembly (universal CM) |
| `FR-ORCH-007` | functional | P1 | Natural confirmation: pending-action yes/no falls back to an LLM micro-call when exact-match fails |
| `FR-ORCH-008` | functional | P0 | Agent loop: `process_message()` parses LLM responses for `<skill_call>` markers and auto-executes the named skill |
| `FR-ORCH-009` | functional | P1 | Skill-aware history: tool invocations and results are preserved as `role=tool` turns in session history and serialized for LLM context |
| `NFR-PERF-006` | non-functional | P1 | `<skill_call>` regex parsing adds <10ms overhead per turn; re-synthesis LLM call only fires when a skill actually executes |

## Acceptance Criteria

| ID | Criterion |
|---|---|
| `AC-CR003-001` | User says "sync my notion tasks" → NotionSkill executes and returns result without requiring a separate "yes" confirmation turn |
| `AC-CR003-002` | User says "I want to build a recipe tracking app" → BMADSkill fires via skill manifest, not keyword matching |
| `AC-CR003-003` | User says "go for it" / "sounds good" / "please" after a pending action → confirmed correctly via LLM fallback |
| `AC-CR003-004` | All `_handle_*` methods use `cm.assemble_system_prompt()` — no ad-hoc `build_system_prompt()` calls remain |
| `AC-CR003-005` | Tool turns appear in `_clean_history()` as assistant messages with `[Tool: SkillName]` prefix |
| `AC-CR003-006` | `smoke_test.py` passes after all changes |

## Design: Agent Loop

```
process_message(user_input)
  │
  ├─ [pending permission?]  → _handle_permission_response()
  ├─ [pending action?]      → _handle_action_confirmation() (with LLM fallback)
  │
  ├─ Build ContextManager(route, skills=self.skills)
  │   └─ includes SkillManifestEngine → "## Skills You Can Invoke" block
  │
  ├─ _classify_intent()  [fast keyword path for file/task/research only]
  │
  ├─ if task_query    → _handle_task_query(cm)
  ├─ if file_operation → _handle_file_operation(cm)
  ├─ if research      → _handle_research()
  │
  └─ else (all other intents) → _agent_loop(user_input, cm)
       │
       ├─ router.route(query, messages=cm.assemble_messages(), system=cm.assemble_system_prompt())
       ├─ _parse_skill_call(response)
       │    ├─ None  → return clean response
       │    └─ (SkillName, params) →
       │         skill.execute(user_input, context, params)
       │         append role=tool to session_history
       │         return skill result (or LLM text + skill result if both non-empty)
       └─ strip stray <skill_call> tags from visible response
```

## Skill Manifest Format

Each skill's `tool_definition()` is formatted into the system prompt:

```
## Skills You Can Invoke

<skill_call name="SKILL_NAME">{"param": "value"}</skill_call>

**BMADSkill**
  - Does: Initialize and guide a BMAD project lifecycle.
  - Use when: user wants to build/create a new app or project
  - Params: `action`: init_project | walk_workflow, `name`: project name
...
```

## Implementation Tasks

| ID | Task | File |
|---|---|---|
| `TASK-CR003-001` | Add abstract `tool_definition()` to `Skill` base class | `src/skills/base.py` |
| `TASK-CR003-002` | Implement `tool_definition()` in all five skill classes | `src/skills/*.py` |
| `TASK-CR003-003` | Add `SkillManifestEngine` to `ContextManager` | `src/context_manager.py` |
| `TASK-CR003-004` | Update `process_message()` with universal CM and agent loop | `src/chat.py` |
| `TASK-CR003-005` | Improve `_handle_action_confirmation()` with LLM fallback | `src/chat.py` |
| `TASK-CR003-006` | Update `_clean_history()` to serialize tool turns | `src/chat.py` |
| `TASK-CR003-007` | Update requirements registry and traceability matrix | `docs/spec/` |

## Status

- [x] Change request created
- [x] Requirements identified
- [x] Implementation complete
- [x] Verified — smoke_test.py: 24 passed, 0 failed
