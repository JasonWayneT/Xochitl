# TEST-PREF-002 — Progressive Personalization Milestones

**Status**: implemented
**CR**: CR-035
**Requirements covered**: FR-PREF-004, FR-PREF-005, NFR-PREF-002

---

## Scope

Unit tests for `src/milestones.py` (pure functions — no DB, no LLM).

- `get_milestone(session_count)` — boundary classification
- `milestone_context_block(milestone)` — block content by tier

Integration path (ContextManager receiving `milestone_block`) is validated
via `py_compile` and source inspection; full system-prompt integration is
covered by the existing `assemble_system_prompt()` smoke path.

---

## Test cases

### TC-PREF-002-001 — M1 boundary (sessions 1–5) (AC-CR035-001)

**Method**: `get_milestone`
**Input**: `1`, `5`
**Expected**: Both return `Milestone.M1`

**Rationale**: Boundaries: <= 5 maps to M1. Checks both the minimum (session
1 = very first session) and the maximum of the M1 range.

---

### TC-PREF-002-002 — M2 boundary (sessions 6–20) (AC-CR035-002)

**Method**: `get_milestone`
**Input**: `6`, `20`
**Expected**: Both return `Milestone.M2`

**Rationale**: 6 is the first session to cross into M2. 20 is the last session
in M2 before escalation to M3.

---

### TC-PREF-002-003 — M3 boundary (sessions 21+) (AC-CR035-003)

**Method**: `get_milestone`
**Input**: `21`, `100`
**Expected**: Both return `Milestone.M3`

**Rationale**: 21 is the first M3 session. 100 confirms no upper bound.

---

### TC-PREF-002-004 — M1 block is empty (AC-CR035-004)

**Method**: `milestone_context_block`
**Input**: `Milestone.M1`
**Expected**: Returns `""` (empty string)

**Rationale**: New users receive default behavior. Injecting a personalization
block for session 1 would risk priming the model toward false familiarity.

---

### TC-PREF-002-005 — M2 and M3 blocks are non-empty (AC-CR035-005)

**Method**: `milestone_context_block`
**Input**: `Milestone.M2`, `Milestone.M3`
**Expected**: Both return non-empty strings containing personalization guidance

**Rationale**: M2 must reference preferences and first-name use. M3 must
reference memory and anticipation. Both blocks must be non-empty to actually
alter model behavior.

---

## Mocking strategy

| Dependency | Mock approach |
|---|---|
| Database | Not needed — `get_milestone` is a pure function |
| LLM | Not needed — no LLM calls in `milestones.py` |
| ContextManager | Not exercised in unit tests; integration verified by source inspection |

All tests are fully deterministic. No external I/O of any kind.
