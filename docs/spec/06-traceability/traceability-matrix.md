# Traceability Matrix

Use this matrix to prove that each requirement has a spec, task, implementation, and verification path.

## Matrix

| Requirement ID | Source | Feature/design spec | Acceptance criteria | Tasks | Code/modules | Tests | Status |
|---|---|---|---|---|---|---|---|
| `FR-CORE-001` | `BMAD-SRC-001` | TBD | `AC-CORE-001` | TBD | `src/cli.py`, `src/task_manager.py` | `TEST-CORE-001` | accepted |
| `FR-CORE-002` | `BMAD-SRC-001` | TBD | `AC-CORE-002` | TBD | `src/cli.py`, `src/task_manager.py` | `TEST-CORE-002` | accepted |
| `FR-CORE-003` | `BMAD-SRC-001` | TBD | `AC-CORE-003` | TBD | `src/cli.py`, `src/task_manager.py` | `TEST-CORE-003` | accepted |
| `FR-CORE-004` | `BMAD-SRC-001` | TBD | `AC-CORE-004` | TBD | `src/cli.py`, `src/chat.py` | `TEST-CORE-004` | accepted |
| `NFR-CORE-001` | `BMAD-SRC-001` | TBD | `AC-CORE-005` | TBD | Multiple | `TEST-CORE-005` | accepted |
| `NFR-CORE-002` | `BMAD-SRC-001` | TBD | `AC-CORE-006` | TBD | `src/database.py`, `src/task_manager.py` | `TEST-CORE-006` | accepted |
| `FR-API-001` | `BMAD-SRC-001` | TBD | `AC-API-001` | TBD | `src/cli.py`, `src/notion_sync.py` | `TEST-API-001` | accepted |
| `FR-API-002` | `BMAD-SRC-001` | TBD | `AC-API-002` | TBD | `src/cli.py`, `src/notion_sync.py` | `TEST-API-002` | accepted |
| `FR-API-003` | `CR-006` | `CR-006` | `AC-CR006-001`, `AC-CR006-002` | `TASK-API-006`, `TASK-ORCH-006` | `src/skills/web_lookup_skill.py`, `src/chat.py` | manual | implemented |
| `FR-API-004` | `CR-007` | `CR-007` | `AC-CR007-001`, `AC-CR007-002`, `AC-CR007-003`, `AC-CR007-004` | `TASK-API-007`, `TASK-ORCH-007`, `TASK-TEST-007`, `TASK-PREF-007` | `src/skills/weather_skill.py`, `src/chat.py`, `smoke_test.py`, `src/database.py` preferences helpers | smoke + e2e + manual live lookup | implemented |
| `INT-API-001` | `BMAD-SRC-001` | TBD | `AC-API-003` | TBD | `src/notion_sync.py` | `TEST-API-003` | accepted |
| `DATA-DATA-001` | `BMAD-SRC-001` | TBD | `AC-DATA-001` | TBD | `src/database.py` | `TEST-DATA-001` | accepted |
| `DATA-DATA-002` | `BMAD-SRC-001` | TBD | `AC-DATA-002` | TBD | `src/database.py` | `TEST-DATA-002` | accepted |
| `DATA-DATA-003` | `BMAD-SRC-001` | TBD | `AC-DATA-003` | TBD | `src/database.py` | `TEST-DATA-003` | accepted |
| `SEC-AUTH-001` | `BMAD-SRC-001` | TBD | `AC-AUTH-001` | TBD | `src/security.py` | `TEST-AUTH-001` | accepted |
| `SEC-AUTH-002` | `BMAD-SRC-001` | TBD | `AC-AUTH-002` | TBD | `src/security.py` | `TEST-AUTH-002` | accepted |
| `ARCH-SDD-001` | `BMAD-SRC-001` | TBD | `AC-SDD-001` | TBD | `src/router.py` | `TEST-SDD-001` | accepted |
| `FR-SDD-001` | `BMAD-SRC-001` | TBD | `AC-SDD-002` | TBD | `src/skills/bmad_skill.py` | `TEST-SDD-002` | accepted |
| `FR-SDD-002` | `BMAD-SRC-001` | TBD | `AC-SDD-003` | TBD | `src/skills/sdd_skill.py` | `TEST-SDD-003` | accepted |
| `FR-SDD-003` | `BMAD-SRC-001` | TBD | `AC-SDD-004` | TBD | `src/skills/code_skill.py` | `TEST-SDD-004` | accepted |
| `FR-SDD-004` | `BMAD-SRC-001` | TBD | `AC-SDD-005` | TBD | `src/skills/code_skill.py` | `TEST-SDD-005` | accepted |
| `FR-UI-001` | `CR-002` | `CR-002` | `AC-CR002-003`, `AC-BUG-UI-002-A` | `TASK-CR002-004` | `src/chat.py` (_StatusContext, flower ✿❀ animation) | manual | implemented |
| `FR-UI-002` | `CR-002` | `CR-002` | `AC-CR002-003` | `TASK-CR002-004` | `src/chat.py` (Ctrl-C handler) | manual | implemented |
| `FR-UI-003` | `CR-002` | `CR-002` | `AC-CR002-005` | `TASK-CR002-004` | `src/chat.py` (_osc8_link) | manual | implemented |
| `FR-UI-004` | `CR-005` | `CR-005` | `AC-CR005-002`, `AC-CR005-003` | `TASK-UI-007` | `src/chat.py` (`_stream_response`) | manual | implemented |
| `FR-ORCH-003` | `CR-002` | `CR-002` | `AC-CR002-001` | `TASK-CR002-001`, `TASK-CR002-002` | `src/context_manager.py`, `src/router.py` | manual | implemented |
| `FR-ORCH-004` | `CR-002` | `CR-002` | `AC-CR002-002` | `TASK-CR002-001`, `TASK-CR002-004` | `src/context_manager.py`, `src/chat.py` | manual | implemented |
| `NFR-PERF-004` | `CR-002` | `CR-002` | `AC-CR002-004` | `TASK-CR002-001` | `src/context_manager.py` (ContextManager) | manual | implemented |
| `NFR-PERF-005` | `CR-002` | `CR-002` | `AC-CR002-005` | `TASK-CR002-003` | `src/router.py` (_update_latency) | manual | implemented |
| `BUG-CHAT-005` | session | `BUG-CHAT-005.md` | `AC-BUG-CHAT-005` | resolved | `src/router.py` (_fast_classify, _KEYWORD_MAP), `src/skills/notion_skill.py` | manual | resolved |
| `BUG-CHAT-006` | session | `BUG-CHAT-006.md` | `AC-BUG-CHAT-006` | resolved | `src/context_manager.py` (guard top), `src/router.py` (CWD + regex) | manual | resolved |
| `BUG-UI-002` | session | `BUG-UI-002.md` | `AC-BUG-UI-002-A`, `AC-BUG-UI-002-B` | resolved | `src/chat.py` (_StatusContext), `src/router.py` (_find_by_name) | manual | resolved |
| `BUG-ORCH-007` | session | `BUG-ORCH-007.md` | `AC-BUG-ORCH-007` | resolved | `src/router.py` (_FORCE_LOCAL_CATEGORIES) | manual | resolved |
| `BUG-API-001` | session | `BUG-API-001.md` | `AC-BUG-API-001` | `TASK-BUG-API-001` | `src/skills/web_lookup_skill.py` (_normalize_result_url, _search snippets), `smoke_test.py` | smoke + e2e + manual live lookup | resolved |
| `FR-ORCH-005` | `CR-003` | `CR-003` | `AC-CR003-001`, `AC-CR003-002` | `TASK-CR003-001`, `TASK-CR003-002`, `TASK-CR003-003` | `src/skills/base.py` (tool_definition), all skill files, `src/context_manager.py` (SkillManifestEngine) | manual | implemented |
| `FR-ORCH-006` | `CR-003` | `CR-003` | `AC-CR003-004` | `TASK-CR003-004` | `src/chat.py` (universal ContextManager in all _handle_* methods) | manual | implemented |
| `FR-ORCH-007` | `CR-003` | `CR-003` | `AC-CR003-003` | `TASK-CR003-005` | `src/chat.py` (_handle_action_confirmation, _llm_classify_confirm) | manual | implemented |
| `FR-ORCH-008` | `CR-003` | `CR-003` | `AC-CR003-001`, `AC-CR003-002` | `TASK-CR003-004` | `src/chat.py` (_agent_loop, _parse_skill_call, _find_skill_by_name) | manual | implemented |
| `FR-ORCH-009` | `CR-003` | `CR-003` | `AC-CR003-005` | `TASK-CR003-006` | `src/chat.py` (_clean_history, _record — role=tool handling) | manual | implemented |
| `NFR-PERF-006` | `CR-003` | `CR-003` | — | `TASK-CR003-004` | `src/chat.py` (_parse_skill_call — regex, no LLM) | manual | implemented |

| `FR-ORCH-010` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-001` | `TASK-CR004-001` | `src/intent.py`, `src/chat.py` | syntax + structured intent sanity check | implemented |
| `FR-ORCH-011` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-002`, `AC-CR004-003` | `TASK-CR004-002` | `src/intent.py` (project exploration scope), `src/chat.py` (bounded repo exploration, skill-call approval gate), `src/file_tools.py` (all writes pending confirmation) | py_compile + targeted gate/exploration sanity checks | implemented |
| `FR-ORCH-012` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-004`, `AC-CR004-013` | `TASK-CR004-003` | `src/context_manager.py`, `src/context_loader.py`, `SOUL.md.example`, `conversation.config.example.yaml`, `prompts/system_xochitl.txt`, `docs/conversation-scenarios.md` | syntax + prompt assembly sanity check | implemented |
| `DATA-DATA-004` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-005`, `AC-CR004-006` | `TASK-CR004-004` | `src/database.py` (preferences table/helpers), `src/context_manager.py` (PreferenceEngine), `src/chat.py` (explicit preference save path) | syntax + structured preference sanity check | implemented |
| `DATA-DATA-005` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-007` | `TASK-CR004-005` | `src/context_manager.py` (MemoryEngine selective `memory.recall()` preload), `src/memory.py` | syntax + bounded preload sanity by construction | implemented |
| `FR-ORCH-013` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-008` | `TASK-CR004-006` | `src/chat.py` (_maybe_offer_skill_creation), `src/skills/dynamic_skill.py` (offer text) | targeted reusable-workflow offer sanity check | implemented |
| `FR-ORCH-014` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-009` | `TASK-CR004-006` | `src/skills/dynamic_skill.py` (DynamicSkill/load_dynamic_skills), `src/chat.py` (skill loading), `src/context_manager.py` (manifest copy) | py_compile + targeted dynamic skill loading sanity check | implemented |
| `FR-SDD-005` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-010` | `TASK-CR004-007` | `src/skills/bmad_skill.py` (BMAD/SDD/project AGENTS scaffold), `src/skills/_yaml_helpers.py` (stdlib YAML fallback for metadata) | py_compile + targeted project-init sanity check | implemented |
| `NFR-PERF-007` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-011` | `TASK-CR004-001`, `TASK-CR004-005` | proposed: `src/context_manager.py`, router/context policy | `TEST-CR004-009` | proposed |
| `ARCH-SDD-002` | `CR-004` | `docs/conversational-layer-architecture.md`, `CR-004` | `AC-CR004-012` | `TASK-CR004-008` | proposed: all new conversational modules | `TEST-CR004-010` | proposed |

## Coverage checklist

- [ ] Every P0 requirement has acceptance criteria.
- [ ] Every accepted requirement maps to at least one spec.
- [ ] Every accepted requirement maps to implementation tasks.
- [ ] Every accepted requirement maps to tests or an explicit manual verification method.
- [ ] Every bug fix has a regression test or documented exception.
- [ ] Every ADR maps to affected requirements or constraints.
- [ ] Deprecated and superseded requirements are not used for new work.

## Gaps

| Gap ID | Missing link | Impact | Owner | Due date |
|---|---|---|---|---|
| `GAP-001` | Feature specs not yet created for any requirement | Feature specs are TBD; traceability is incomplete until specs are written | Jason | TBD |
| `GAP-002` | Implementation tasks (TASK-*) not yet assigned | Cannot track implementation progress | Jason | TBD |
| `GAP-003` | Test specs (TEST-*) not yet written | Cannot verify acceptance criteria | Jason | TBD |
| `GAP-004` | Code module paths are placeholder — actual implementations may differ | Traceability to code is approximate | Jason | TBD |
