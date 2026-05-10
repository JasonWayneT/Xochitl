# BUG-SEC-001 — Delete File Intent Bypasses FileTools Confirmation Gate

## Status
Resolved

## Severity
High — a user asking Xochitl to delete a file was silently routed to the agent loop, bypassing the `FileTools.delete_file()` permission model entirely. No confirmation was requested and no deletion actually occurred (the LLM described the action rather than executing it), but the protection was absent rather than enforced.

## Symptoms
User says: "delete src/old_config.py"

Expected: `FileTools.delete_file()` called → `"Delete old_config.py? This cannot be undone."` confirmation prompt.

Actual: Intent classified as `file_operation / delete`, but `_handle_file_operation()` fell through a missing branch to `self._agent_loop(user_input, cm)`. The LLM described the deletion in prose without executing it, and the FileTools consent gate was never engaged.

## Root Cause
The CR-003 refactor removed the explicit write/delete handlers from `_handle_file_operation()` but only added a new `read` branch. The original handler had separate paths for each operation type; after CR-003 only `read` was preserved, and `write`/`delete` silently fell through to `_agent_loop`:

```python
# After CR-003 (broken)
def _handle_file_operation(self, user_input, intent, cm):
    op = intent.get("operation", "read")
    if op == "read":
        ...  # full handling
    return self._agent_loop(user_input, cm)  # delete falls here — no FileTools
```

## Affected Requirements
- `SEC-AUTH-002` — Overwriting or deleting files requires explicit user confirmation via FileTools

## Fix Applied
**File**: `src/chat.py`, `_handle_file_operation()`

Added an explicit `delete` branch before the `read` branch that extracts the target path and routes through `FileTools.delete_file()`:

```python
if op == "delete":
    # Extract path from query (absolute, quoted, or bare filename with extension)
    ...
    result = self.file_tools.delete_file(path)
    if result["status"] == "pending_permission":
        self.current_context["pending_file_operation"] = result["operation_id"]
    return result["message"]
```

`FileTools.delete_file()` always returns `pending_permission` for existing files, which stores an `operation_id` and asks the user to confirm. The existing `_handle_permission_response()` flow then executes or cancels on the next turn.

Write operations remain in the agent loop — the LLM must generate the content, and `_write_generated_files()` has its own path-escape security check that restricts writes to the active project directory.

## Regression Acceptance Criterion
`AC-BUG-SEC-001`: Given an active chat session, when the user says "delete <filename>" where the file exists and is in an authorized directory, then Xochitl must call `FileTools.delete_file()` and ask for explicit confirmation before any file is removed.

## Related
- `SEC-AUTH-002` — Overwrite/delete permission model
- `BUG-ORCH-010` — Skill exception guard (defence-in-depth for write path via CodeSkill)
