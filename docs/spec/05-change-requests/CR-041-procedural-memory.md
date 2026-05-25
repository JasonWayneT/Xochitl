# CR-041 — Procedural Memory

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 16 (Group 5 — Runtime Capabilities)
**Source**: `docs/planning/exploration-2026-05.md` item #12

---

## Problem statement

Dynamic skills cover single-shot instructions, but users build repeatable multi-step
routines ("weekly review", "triage Notion inbox") with no durable home. Semantic memory
(RAG) stores facts, not step sequences. Procedural memory needs a separate store with
intent-based recall and compact injection (<=500 tokens).

---

## Requirements

| ID | Requirement |
|---|---|
| `FR-MEM-008` | `workflows` SQLite table stores name, trigger_pattern, steps_json, stats (success/failure, last_used), source (`user_defined` \| `distilled`), optional project |
| `FR-MEM-009` | `search_workflows_by_intent(query)` returns top-1 match by keyword overlap (not semantic vector space) |
| `FR-MEM-010` | `_agent_loop()` injects `[PROCEDURAL WORKFLOW]` block when match score >= 0.50 |
| `FR-MEM-011` | After multi-step success (>=2 tool turns), offer `/workflow save <name>`; slash commands list/save workflows |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR041-001` | `upsert_workflow` + `get_workflow` | Round-trip name, steps, trigger |
| `AC-CR041-002` | `search_workflows_by_intent("weekly review")` | Returns workflow with "weekly" in trigger |
| `AC-CR041-003` | `format_workflow_block()` | Output <= 500 tokens, contains step list |
| `AC-CR041-004` | `distill_steps_from_history` with 2 tool turns | >= 2 steps distilled |
| `AC-CR041-005` | `python smoke_test.py` | All tests pass |

---

## Implementation

- [x] `src/database.py` — `workflows` table + CRUD
- [x] `src/workflows.py` — search, format, distill, save offer
- [x] `src/chat.py` — inject, offer, `/workflows`, `/workflow save`
- [x] `docs/spec/02-requirements-registry.md`, traceability, `TEST-MEM-002`
- [x] `smoke_test.py` — CR-041 tests (ASCII labels)

---

## Verification

**Date**: 2026-05-25  
**Smoke**: `python smoke_test.py` — 146 passed, 0 failed (includes AC-CR041-001 through AC-CR041-004)  
**E2E**: `python end_to_end_test.py` — not re-run  
**Registry / traceability**: `FR-MEM-008` through `FR-MEM-011` marked implemented; `TEST-MEM-002` added.
