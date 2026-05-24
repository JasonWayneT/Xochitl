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
| `FR-UI-005` | `CR-031` | `CR-031` | `AC-CR031-001`, `AC-CR031-002`, `AC-CR031-003`, `AC-CR031-004`, `AC-CR031-005`, `AC-CR031-006`, `AC-CR031-007`, `AC-CR031-008` | `TASK-UI-031-a`, `TASK-UI-031-b`, `TASK-UI-031-c`, `TASK-UI-031-d` | `src/llm_interface.py` (`stream_cloud`, `_stream_gemini`, `_stream_anthropic`), `src/router.py` (`route_stream`), `src/chat.py` (`_agent_loop` streaming path, `_last_response_streamed`) | py_compile + 27 smoke tests pass | implemented |
| `NFR-PERF-009` | `CR-031` | `CR-031` | `AC-CR031-007` | `TASK-UI-031-c` | `src/chat.py` (`_StatusContext` live-stop before first token) | manual timing | accepted |
| `BUG-API-002` | session | `CR-014` | `AC-CR014-001` | `TASK-API-014` | `src/skills/weather_skill.py` (`_split_country`, `_geocode_candidates` fallback) | py_compile + manual reasoning trace | resolved |
| `NFR-API-001` | `CR-014` | `CR-014` | `AC-CR014-002`, `AC-CR014-003`, `AC-CR014-004` | `TASK-API-014`, `TASK-TEST-014` | `src/skills/weather_skill.py` (`_COUNTRY_CODES`, `_split_country`, `_best_geocode_result`, `_clean_location`) | py_compile + manual reasoning trace; smoke coverage pending `TASK-TEST-014` | implemented |
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

| `FR-ORCH-015` | `CR-008` | `CR-008` | `AC-CR008-001` | `TASK-CR008-001`, `TASK-CR008-002` | `src/router.py` (`_ZETTEL_RE`, `_fast_classify`, `_LOCAL_SPECIALIZED_CATEGORIES`, `_FORCE_LOCAL_CATEGORIES`, `_KEYWORD_MAP`, `_CLASSIFICATION_PROMPT`) | manual | implemented |
| `FR-ZTK-001` | `CR-008` | `CR-008` | `AC-CR008-002` | `TASK-CR008-003`, `TASK-CR008-004` | `src/chat.py` (`_builtin_skills`), `src/skills/zettelkasten_skill.py` (`_ENTER_PHRASES`, `tool_definition`) | manual | implemented |
| `FR-ZTK-002` | `CR-008` | `CR-008` | `AC-CR008-003`, `AC-CR008-004` | `TASK-CR008-005`, `TASK-CR008-006` | `src/skills/zettelkasten_skill.py` (`_VAULT_CONFIG`, `_SCAN_ROOTS`, `_looks_like_vault`, `_scan_for_vaults`, `_load_saved_vault`, `_save_vault`, `_get_vault`) | manual | implemented |
| `FR-ZTK-003` | `CR-008` | `CR-008` | `AC-CR008-005` | `TASK-CR008-007` | `src/skills/zettelkasten_skill.py` (`enter_mode` scaffold check) | manual | implemented |
| `FR-ZTK-004` | `CR-008` | `CR-008` | `AC-CR008-006` | `TASK-CR008-008` | `src/skills/zettelkasten_skill.py` (`_extract_path_hint`) | manual | implemented |
| `FR-ZTK-005` | `CR-008` | `CR-008` | `AC-CR008-007` | `TASK-CR008-009`, `TASK-CR008-010` | `src/skills/zettelkasten_process.py` (`_TAG_BUDGET`, `_suggest_tags`, `_suggest_tags_heuristic`) | manual | implemented |
| `FR-ZTK-006` | `CR-008` | `CR-008` | `AC-CR008-008` | `TASK-CR008-009`, `TASK-CR008-010` | `src/skills/zettelkasten_process.py` (`_similarity_ratio`, `_find_similar_tag`) | manual | implemented |
| `FR-ZTK-007` | `CR-008` | `CR-008` | `AC-CR008-009`, `AC-CR008-010` | `TASK-CR008-009`, `TASK-CR008-010`, `TASK-CR008-011`, `TASK-CR008-012`, `TASK-CR008-013` | `src/skills/zettelkasten_process.py` (`_read_active_tags`, `_read_proposed_tags`, `_write_taxonomy`, `_propose_tag`, `_record_tag_usage`, `apply_pending`), `src/skills/zettelkasten_skill.py` (`vault_status`), `src/skills/zettelkasten_scaffold.py` (`_ensure_proposed_section`) | manual | implemented |
| `NFR-UI-004` | `CR-008` | `CR-008` | `AC-CR008-011` | `TASK-CR008-014` | `src/model_manager.py` (`_log` — removed stderr print) | manual | implemented |
| `NFR-UI-005` | `CR-008` | `CR-008` | `AC-CR008-012` | `TASK-CR008-015` | `src/context_loader.py` (`build_system_prompt` — language rule) | manual | implemented |
| `NFR-UI-006` | `CR-008` | `CR-008` | — | `TASK-CR008-016` | `src/chat.py` (`_StatusContext` — `refresh_per_second=10`, `sleep(0.06)`) | manual | implemented |

| `FR-ORCH-016` | `CR-009` | `CR-009` | `AC-CR009-001` | `TASK-CR009-001`, `TASK-CR009-002` | `src/context_manager.py` (`assemble_system_prompt` — `guard_text` soul merge, never-compact path) | smoke_test + manual long-session | implemented |
| `FR-ORCH-017` | `CR-009` | `CR-009` | `AC-CR009-002` | `TASK-CR009-007`, `TASK-CR009-008` | `src/chat.py` (`_SKILL_INJECT_THRESHOLD`, `_format_active_skill_block`, `_agent_loop` skill scoring loop) | smoke_test + manual | implemented |
| `FR-ORCH-018` | `CR-009` | `CR-009` | `AC-CR009-003`, `AC-CR009-004` | `TASK-CR009-009`, `TASK-CR009-010`, `TASK-CR009-011` | `src/background_review.py` (`BackgroundReview`, `_TurnData`, `_extract`, `_write`), `src/chat.py` (`queue_turn`, `shutdown`) | smoke_test + manual KB inspection | implemented |
| `FR-ORCH-019` | `CR-009` | `CR-009` | `AC-CR009-005` | `TASK-CR009-003`, `TASK-CR009-004` | `src/router.py` (`route` — single `_classify()` call, removed `_fast_classify`, removed duplicate preflight/file context) | smoke_test + manual | implemented |
| `NFR-PERF-008` | `CR-009` | `CR-009` | `AC-CR009-004` | `TASK-CR009-009` | `src/background_review.py` (`Queue(maxsize=20)`, `_MIN_WRITE_INTERVAL_SECS = 30`, `put_nowait` silent drop) | smoke_test | implemented |

| `FR-ORCH-020` | `CR-010` | `CR-010` | `AC-CR010-001` | — | `src/events.py` (`XochitlEventEmitter`, module-level singleton), `src/chat.py` (`_agent_loop` emit calls) | manual + smoke_test | implemented |
| `FR-ORCH-021` | `CR-010` | `CR-010` | `AC-CR010-002` | — | `src/context_loader.py` (`trim_history_for_local`, `_LOCAL_HISTORY_KEEP`), `src/router.py` (`_route_local`) | smoke_test | implemented |
| `NFR-UI-007` | `CR-010` | `CR-010` | `AC-CR010-003` | — | `src/chat.py` (`_consecutive_staged` counter, loop guard in `start()`) | smoke_test | implemented |
| `DATA-DATA-006` | `CR-010` | `CR-010` | `AC-CR010-004` | — | `src/database.py` (`memory_facts` table, `upsert_memory_fact`, `get_memory_facts`), `src/background_review.py` (`_extract_structured`, `_write` DB path) | smoke_test | implemented |
| `DATA-DATA-007` | `CR-010` | `CR-010` | `AC-CR010-005` | — | `src/memory.py` (`_HYDE_PROMPT`, `_hyde_embed`, updated `recall()`) | smoke_test | implemented |
| `OPS-CORE-001` | `CR-010` | `CR-010` | `AC-CR010-006` | — | `scripts/start_ollama.ps1`, `.env.example` | manual | implemented |

| `NFR-UI-008` | `CR-011` | `CR-011` | `AC-CR011-001`, `AC-CR011-002`, `AC-CR011-003` | `TASK-CR011-001` through `TASK-CR011-005` | `src/chat.py`, `src/cli.py`, `src/context_manager.py`, `CLAUDE.md`, `README.md`, `XOCHITL_EXPLAINED.md`, `docs/spec/00-project-constitution.md`, `docs/spec/01-bmad-intake.md` | grep zero-match verification | implemented |

| `FR-ORCH-022` | `CR-012` | `CR-012` | `AC-CR012-001`, `AC-CR012-002`, `AC-CR012-004` | `TASK-CR012-001` through `TASK-CR012-005` | `src/context_manager.py` (`UserProfileEngine`, `ContextManager.__init__`, `ingest`, `assemble_system_prompt`, `budget_used_pct`) | py_compile + manual | implemented |
| `NFR-ORCH-001` | `CR-012` | `CR-012` | `AC-CR012-003` | `TASK-CR012-006`, `TASK-CR012-007` | `~/.xochitl/Me.md`, `Me.md.example` | manual line count | implemented |
| `NFR-ORCH-002` | `CR-013` | `CR-013` | `AC-CR013-001`, `AC-CR013-002`, `AC-CR013-003`, `AC-CR013-004` | `TASK-CR013-001` | `src/context_manager.py` (`UserProfileEngine.ingest`) | manual | implemented |

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
