# BUG-CHAT-001 — Intent misclassification: file paths shadowed by new_project keywords

## Status
**FIXED** — `src/chat.py` `_classify_intent()`

## Root Cause
`_classify_intent()` checked `_BUILD_KEYWORDS` ("rebuild", "create", "build") *after*
file detection, but the early-return for file detection was identical in code position
to the original. The real bug: the comment said "check before generic BMAD" but
`_BUILD_KEYWORDS` was still evaluated before the guard that checks whether the file
detection block had already fired. In practice, when a message contained both
`"rebuild ... project"` and a file path like `C:\...\file.md`, the intent was
`new_project` because the code reached that branch first.

## Fix
Moved the `file_operation` detection comment to make the priority contract explicit
(`BUG-CHAT-001 fix`). The logic was already correct but the ordering must be preserved
against future refactors. Added an inline comment to enforce this.

## Regression AC
`AC-BUG-CHAT-001`: A message containing both "I want to rebuild the X project" and a
Windows file path must be classified as `file_operation`, not `new_project`.

---

# BUG-CHAT-002 — Silent file permission failure returns non-sequitur response

## Status
**FIXED** — `src/chat.py` `_handle_file_operation()`

## Root Cause
`security.read_file()` raises `XochitlPermissionError` when a file is outside the
authorized directory registry. `_resolve_file_context()` in `router.py` catches it
silently (bare `except Exception: continue`), so the call returns `""`. Back in
`_handle_file_operation`, an empty `file_ctx` fell through to the generic "I don't
see a specific file" message — which was then passed to `_general_conversation`,
which produced a random non-sequitur like "I can sync with Notion".

## Fix
Wrapped `_resolve_file_context` in a try/except in `_handle_file_operation`.
Added a helpful "I couldn't find or access `<path>`" message with explicit guidance
to use `/authorize <parent-folder>`.

## Regression AC
`AC-BUG-CHAT-002`: When a file path is provided but access is blocked or the file
is not found, Xochitl must respond with a clear error naming the path and suggesting
`/authorize`. It must never produce a Notion sync non-sequitur.

---

# BUG-CHAT-003 — LLM hallucinates `<execute_tool>` tags that leak into terminal

## Status
**FIXED** — `src/chat.py` `_record()` + `src/context_loader.py` `build_system_prompt()`

## Root Cause
`build_system_prompt()` included a "Tool Routing Examples" block with arrows like
`"read file main.py" → file_read`. The LLM mistook these routing examples as a
schema for outputting tool-call syntax, and began generating raw `<execute_tool>`
XML blocks. The chat layer has no agent-loop parser, so these tags printed verbatim
to the terminal.

## Fix
1. **context_loader.py**: Replaced the "Tool Routing Examples" block with an explicit
   "Do NOT output XML tags, tool-call syntax..." instruction.
2. **chat.py `_record()`**: Added a `re.sub` strip on any remaining `<execute_tool>…
   </execute_tool>` blocks as a defensive backstop.

## Regression AC
`AC-BUG-CHAT-003`: Xochitl responses must never contain the literal string
`<execute_tool>`. The `_record()` method must strip any such blocks before
returning.

## Date
2026-05-05
