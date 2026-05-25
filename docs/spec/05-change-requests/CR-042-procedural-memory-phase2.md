# CR-042 — Procedural Memory Phase 2

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 17 (extends CR-041)
**Source**: Exploration #12 post-MVP: LEGOMem distillation, embedding recall, workflow executor

---

## Problem statement

CR-041 MVP stores mechanical tool-turn steps and recalls by keywords only.
Users need paraphrase-friendly recall, LLM-distilled workflows with failure modes,
and optional deterministic multi-step execution.

---

## Requirements

| ID | Requirement |
|---|---|
| `FR-MEM-012` | `WorkflowVectorIndex` uses LanceDB table `workflow_intents` (separate from `memories`) for trigger embedding search |
| `FR-MEM-013` | `distill_workflow_trajectory()` uses local LLM to produce trigger, steps, expected_outputs, failure_modes; falls back to mechanical distill |
| `FR-MEM-014` | `execute_workflow()` runs stored steps via registered skills; `WorkflowSkill` + `/workflow run <name>` |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR042-001` | Index + search | Embedding search returns workflow when paraphrase close |
| `AC-CR042-002` | LLM distill | Mocked LLM returns JSON; parsed steps persisted |
| `AC-CR042-003` | Executor | Two-step workflow runs mock skills in order |
| `AC-CR042-004` | Hybrid search | Combined score beats keyword-only miss |
| `AC-CR042-005` | `python smoke_test.py` | All tests pass |

---

## Implementation

- [x] `src/workflow_vector.py`
- [x] `src/workflows.py` — distill, hybrid search, executor
- [x] `src/skills/workflow_skill.py`
- [x] `src/chat.py` — register skill, `/workflow run`, LLM save

---

## Verification

**Date**: 2026-05-25  
**Smoke**: `python smoke_test.py` — 146 passed, 0 failed (includes AC-CR042-001 through AC-CR042-004)  
**E2E**: `python end_to_end_test.py` — not re-run  
**Registry / traceability**: `FR-MEM-012` through `FR-MEM-014` marked implemented; `TEST-MEM-003` added.  
**Note**: `FR-MEM-009` recall path extended to hybrid search; keyword-only behavior remains when `use_embeddings=False`.
