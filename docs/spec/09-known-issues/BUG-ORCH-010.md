# BUG-ORCH-010 — Uncaught Skill Exception Crashes Chat Session

## Status
Resolved

## Severity
High — any unhandled exception raised inside `skill.execute()` propagates through `_agent_loop` to `process_message` and terminates the session with a Python traceback.

## Symptoms
A skill that raises any exception during `execute()` (network error, file not found, unexpected LLM response, etc.) caused the entire `XochitlChat.start()` loop to exit with an unhandled exception rather than returning a graceful error message to the user.

## Root Cause
`_agent_loop` called `skill.execute()` without any exception handling:

```python
tool_result = skill.execute(user_input, self.current_context, params)
```

There was no `try/except` wrapper. Any exception — including those from skills invoking the router, writing files, or reading YAML — escaped to the outer `while True` loop in `start()`, which only had a bare `except KeyboardInterrupt` guard.

## Affected Requirements
- `FR-ORCH-008` — Agent loop must be resilient; a failed skill invocation should not abort the session

## Fix Applied
**File**: `src/chat.py`, `_agent_loop()`

Wrapped the `skill.execute()` call in a `try/except`:

```python
try:
    tool_result = skill.execute(user_input, self.current_context, params)
except Exception as exc:
    tool_result = f"{_ERR} — {skill_name} failed: {exc}"
```

The session continues and the error is surfaced as a normal Xochitl response using the `_ERR` vocabulary constant.

## Regression Acceptance Criterion
`AC-BUG-ORCH-010`: Given an active chat session, when a skill invoked via `<skill_call>` raises any exception, then Xochitl must respond with an `Ay no — <SkillName> failed: <reason>` message and the session must remain active for further input.

## Related
- `BUG-ORCH-009` — Missing params KeyError (specific case this defence-in-depth covers)
