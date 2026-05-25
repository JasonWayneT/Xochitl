# CR-037 — Safe Executor

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 13 (Group 6 — Autonomy Layer)
**Source**: `docs/planning/exploration-2026-05.md` item #19

---

## Problem statement

Xochitl has no principled action permission layer. Skills that call external
APIs, write files, or trigger subprocesses each implement their own ad-hoc
permission checks (or none). The planning document requires a unified
`ActionGovernor` that classifies every action as AUTO / CONFIRM / DENY before
dispatch, and a `SafeExecutor` that runs allowlisted subprocess commands with
output cap and governor enforcement.

Docker/gVisor sandboxing for LLM-generated code is explicitly out of scope
for this CR — it requires infrastructure (container daemon, seccomp profiles)
that is not available in the current deployment environment. The planning doc
note "RestrictedPython is not a security boundary" stands; full sandbox
isolation is a future infrastructure CR.

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| `FR-EXEC-001` | `ActionGovernor.classify(action_type: str, target: str) -> ActionTier` classifies every action before dispatch: `AUTO` for read-only lookups (action_type in `_AUTO_TYPES`), `CONFIRM` for writes/deletes/API side effects (action_type in `_CONFIRM_TYPES`), `DENY` for policy violations (target fails allowlist or sandbox check) |
| `FR-EXEC-002` | `SafeExecutor.run(cmd: str, args: list[str]) -> ExecutorResult` checks the governor first; if `AUTO`, runs via `subprocess.run([cmd, *args], shell=False, capture_output=True, timeout=10)`; if `CONFIRM`, raises `ConfirmationRequired`; if `DENY`, raises `PolicyViolation`; output is capped at `_OUTPUT_CAP_BYTES (65536)` with `[truncated]` marker |
| `FR-EXEC-003` | `SafeExecutor` only executes commands whose base name appears in `_ALLOWED_COMMANDS` — an explicit allowlist; any command not on the list is classified as `DENY` regardless of action_type |

### Non-functional

| ID | Requirement |
|---|---|
| `NFR-EXEC-001` | `subprocess.run()` is never called with `shell=True`; `eval()` and `exec()` are never called on any generated or user-controlled input; `ActionGovernor.classify()` is a pure function (no side effects, no I/O, independently testable) |
| `NFR-EXEC-002` | Captured output is size-capped before being returned; raw stdout/stderr is never passed back to the LLM prompt without sanitization; `SafeExecutor.run()` always calls `ActionGovernor.classify()` first — there is no path that bypasses the governor |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR037-001` | `ActionGovernor.classify("read", "src/chat.py")` | Returns `ActionTier.AUTO` |
| `AC-CR037-002` | `ActionGovernor.classify("delete", "output.txt")` | Returns `ActionTier.CONFIRM` |
| `AC-CR037-003` | `ActionGovernor.classify("exec", "../../etc/passwd")` | Returns `ActionTier.DENY` (path traversal attempt) |
| `AC-CR037-004` | `SafeExecutor.run("not_on_allowlist", [])` | Raises `PolicyViolation` |
| `AC-CR037-005` | Output > 65536 bytes from `SafeExecutor.run()` | Truncated to cap with `[truncated]` appended |
| `AC-CR037-006` | `python smoke_test.py` | 129 passed, 0 failed |

---

## Design

### Action tiers

```
ActionTier.AUTO    — reads, lookups, status checks, non-destructive queries
                     Execute immediately; log the action.
ActionTier.CONFIRM — writes, deletes, external API side effects, subprocesses
                     Show the exact action and require user confirmation.
ActionTier.DENY    — outside security policy: path traversal, non-allowlisted
                     commands, generated code without sandbox
                     Raise PolicyViolation immediately; log the attempt.
```

### Allowlist

`_ALLOWED_COMMANDS` is a frozen set of safe base command names:
```python
{"git", "python", "pip", "pytest", "ls", "dir", "echo", "cat", "type"}
```

Allowlist is intentionally minimal. Adding commands requires an explicit code
change, not a runtime config change — this is a safety invariant.

### Path traversal DENY rule

Any target containing `..` is immediately classified as `DENY` regardless of
action_type. This catches the most common path traversal pattern.

### Output cap

```python
_OUTPUT_CAP_BYTES = 65_536  # 64 KB

if len(raw_output) > _OUTPUT_CAP_BYTES:
    raw_output = raw_output[:_OUTPUT_CAP_BYTES] + b"\n[truncated]"
```

### `ExecutorResult`

```python
@dataclass
class ExecutorResult:
    returncode: int
    stdout: str
    stderr: str
    truncated: bool
```

### Exception hierarchy

```python
class ExecutorError(Exception): ...
class PolicyViolation(ExecutorError): ...
class ConfirmationRequired(ExecutorError):
    action_tier: ActionTier
    cmd: str
    args: list[str]
```

---

## Out of scope

- Docker/gVisor/seccomp sandbox for LLM-generated code — requires container
  infrastructure not available in the current deployment.
- RestrictedPython — planning doc explicitly notes it is not a security
  boundary; no false sense of security.
- Integration with `src/chat.py` skill dispatch — skills call the governor
  directly for now; a unified dispatch hook is a future CR.

---

## Implementation tasks

- [x] Write `CR-037-safe-executor.md`
- [x] `src/executor.py` (NEW) — `ActionTier`, `ActionGovernor`, `SafeExecutor`, `ExecutorResult`, `PolicyViolation`, `ConfirmationRequired`
- [x] `docs/spec/02-requirements-registry.md` — FR-EXEC-001, FR-EXEC-002, FR-EXEC-003, NFR-EXEC-001, NFR-EXEC-002
- [x] `docs/spec/08-test-specs/TEST-EXEC-001-safe-executor.md`
- [x] `smoke_test.py` — 5 tests (AC-CR037-001 through AC-CR037-005)
- [x] `docs/spec/06-traceability/traceability-matrix.md`
