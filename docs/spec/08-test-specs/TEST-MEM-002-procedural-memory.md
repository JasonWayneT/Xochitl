# TEST-MEM-002 — Procedural Memory

**Status**: implemented
**CR**: CR-041 (recall extended by CR-042 hybrid search — see `TEST-MEM-003`)  
**Requirements covered**: FR-MEM-008, FR-MEM-009, FR-MEM-010, FR-MEM-011

---

## Scope

Unit tests for `src/workflows.py` and `database` workflow helpers. No LLM or
network calls. Uses in-memory SQLite with `_ensure_workflows_table`.

---

## Test cases

### TC-MEM-002-001 — Upsert round-trip (AC-CR041-001)

**Method**: `upsert_workflow`, `get_workflow`
**Expected**: Stored name and steps match input

---

### TC-MEM-002-002 — Intent search (AC-CR041-002)

**Method**: `search_workflows_by_intent`
**Setup**: Workflow with trigger "weekly review notion inbox"
**Input**: "run my weekly review"
**Expected**: Top match name is the seeded workflow

---

### TC-MEM-002-003 — Block size cap (AC-CR041-003)

**Method**: `format_workflow_block`
**Expected**: Formatted block length <= 2000 chars (~500 tokens)

---

### TC-MEM-002-004 — Distill from history (AC-CR041-004)

**Method**: `distill_steps_from_history`
**Setup**: Session history with two `role=tool` messages
**Expected**: At least two steps in result

---

## Mocking strategy

| Dependency | Mock approach |
|---|---|
| LLM | None — keyword search only |
| LanceDB | None — separate from semantic memory |
| Filesystem | In-memory SQLite only |
