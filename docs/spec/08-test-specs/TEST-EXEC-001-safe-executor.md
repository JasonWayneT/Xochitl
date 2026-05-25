# TEST-EXEC-001 — Safe Executor

**Status**: implemented
**CR**: CR-037
**Requirements covered**: FR-EXEC-001, FR-EXEC-002, FR-EXEC-003, NFR-EXEC-001, NFR-EXEC-002

---

## Scope

Unit tests for `src/executor.py`. All subprocess calls are mocked — no real
processes are spawned in tests. Tests cover:

- `ActionGovernor.classify()` — pure-function tier classification
- `SafeExecutor.run()` — allowlist enforcement and output cap
- Exception types — `PolicyViolation`, `ConfirmationRequired`

---

## Test cases

### TC-EXEC-001-001 — AUTO classification for read action (AC-CR037-001)

**Method**: `ActionGovernor.classify`
**Input**: `action_type="read"`, `target="src/chat.py"`
**Expected**: Returns `ActionTier.AUTO`

**Rationale**: `"read"` is in `_AUTO_TYPES`. No path traversal in target.
Demonstrates the happy path for safe, non-destructive lookups.

---

### TC-EXEC-001-002 — CONFIRM classification for delete action (AC-CR037-002)

**Method**: `ActionGovernor.classify`
**Input**: `action_type="delete"`, `target="output.txt"`
**Expected**: Returns `ActionTier.CONFIRM`

**Rationale**: `"delete"` is in `_CONFIRM_TYPES`. Destructive actions require
explicit user confirmation before dispatch.

---

### TC-EXEC-001-003 — DENY on path traversal (AC-CR037-003)

**Method**: `ActionGovernor.classify`
**Input**: `action_type="exec"`, `target="../../etc/passwd"`
**Expected**: Returns `ActionTier.DENY`

**Rationale**: Target contains `..` — path traversal pattern. DENY regardless
of action_type. This is the most critical security gate in the governor.

---

### TC-EXEC-001-004 — PolicyViolation for non-allowlisted command (AC-CR037-004)

**Method**: `SafeExecutor.run`
**Input**: `cmd="not_on_allowlist"`, `args=[]`
**Expected**: Raises `PolicyViolation`

**Rationale**: `_ALLOWED_COMMANDS` does not include `"not_on_allowlist"`.
The allowlist check precedes the governor and is absolute — no bypass.

---

### TC-EXEC-001-005 — Output truncated at 64KB (AC-CR037-005)

**Method**: `SafeExecutor.run` with mocked subprocess returning >64KB output
**Input**: `cmd="git"` (on allowlist), `action_type="read"`, mocked stdout > 65536 bytes
**Expected**: `result.truncated == True`; `result.stdout` ends with `[truncated]`

**Rationale**: Raw output > `_OUTPUT_CAP_BYTES` must be capped before being
returned. Prevents accidental injection of large stdout into LLM prompts.

---

## Mocking strategy

| Dependency | Mock approach |
|---|---|
| `subprocess.run` | `unittest.mock.patch("subprocess.run")` returning mock `CompletedProcess` |
| Filesystem | Not needed — `classify()` is pure; paths are strings only |
| LLM | None — executor has no LLM calls |

Tests use `unittest.mock.patch` at the `subprocess.run` call site within
`src.executor`. No real processes are spawned.
