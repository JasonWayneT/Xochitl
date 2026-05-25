# TEST-INIT-001 — Controlled Initiative

**Status**: implemented
**CR**: CR-036
**Requirements covered**: FR-INIT-001, FR-INIT-002, FR-INIT-003, NFR-INIT-001

---

## Scope

Unit tests for `src/initiative.py` — pure policy engine with no external
dependencies. Tests cover the three submission gates (mode, confidence,
suppression), dismissal tracking, and drain semantics.

---

## Test cases

### TC-INIT-001-001 — OFF mode rejects all (AC-CR036-001)

**Method**: `InitiativeEngine.submit` with `mode=OFF`
**Input**: High-confidence `SYSTEM_FAILURE` signal (confidence=0.90)
**Expected**: `drain()` returns `[]`

**Rationale**: `ProactiveMode.OFF` means no proactive messages at all,
regardless of category or confidence.

---

### TC-INIT-001-002 — ERRORS_ONLY allows SYSTEM_FAILURE (AC-CR036-002)

**Method**: `InitiativeEngine.submit` with `mode=ERRORS_ONLY`
**Input**: `SYSTEM_FAILURE` signal with confidence=0.90
**Expected**: `drain()` returns the signal

**Rationale**: Default mode `ERRORS_ONLY` permits `SYSTEM_FAILURE` category
at adequate confidence. The signal must survive all gates.

---

### TC-INIT-001-003 — ERRORS_ONLY rejects IN_SESSION_FOLLOWUP (AC-CR036-003)

**Method**: `InitiativeEngine.submit` with `mode=ERRORS_ONLY`
**Input**: `IN_SESSION_FOLLOWUP` signal with confidence=0.90
**Expected**: `drain()` returns `[]`

**Rationale**: `ERRORS_ONLY` restricts to `SYSTEM_FAILURE` only. A follow-up
signal, even with high confidence, is silently discarded.

---

### TC-INIT-001-004 — Low confidence signal rejected (AC-CR036-004)

**Method**: `InitiativeEngine.submit` with `mode=FULL`
**Input**: `SYSTEM_FAILURE` signal with confidence=0.75 (< 0.80 threshold)
**Expected**: `drain()` returns `[]`

**Rationale**: The confidence gate applies regardless of mode. Below-threshold
signals are logged at DEBUG only, never queued.

---

### TC-INIT-001-005 — Dismissal auto-suppresses after 3 (AC-CR036-005)

**Method**: `InitiativeEngine.dismiss` x3, then `submit`
**Setup**: `mode=FULL`, `SYSTEM_FAILURE`, confidence=0.90
**Expected**: After 3 `dismiss(SYSTEM_FAILURE)` calls, subsequent `submit()`
of a `SYSTEM_FAILURE` signal is silently rejected; `drain()` returns `[]`

**Rationale**: The dismissal counter reaches `_DISMISS_THRESHOLD (3)` and the
category moves to `_suppressed`. Once suppressed, no further signals of that
category are accepted regardless of mode or confidence.

---

## Mocking strategy

| Dependency | Mock approach |
|---|---|
| Database | None — `InitiativeEngine` has no DB access |
| LLM | None — pure policy logic only |
| Events | Not needed — signals submitted directly in tests |

All tests are fully deterministic. `InitiativeEngine` is stateless between
test functions (each test constructs a fresh instance).
