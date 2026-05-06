# BUG-ORCH-006 — Self-referential intent failure: 'what folder are you in' defaults to generic LLM response

## Status
**FIXED** — `src/router.py` `_fast_classify()` and `_resolve_file_context()`

## Root Cause
1. **Strict Matching**: The self-referential phrase list used exact substring matching. Phrases like "what folder are you in" didn't match "the folder you are in", so the intent wasn't classified as a `file_operation`.
2. **Canned Response**: Because the intent fell back to `simple_qa` and no file context was injected, the local model (Gemma) fell back to its base training and gave a generic "I am an AI" response.
3. **Hardcoded Root**: The "your folder" logic was tied to the project's source root (`_PROJECT_ROOT`), but the user was running Xochitl from a different directory.

## Fix
1. **Fuzzy Detection**: Added a regex backstop in `_fast_classify` to catch any combination of (what/show/list/where) and (folder/dir/files/path).
2. **Path Context**: Updated `_resolve_file_context` to use `Path.cwd()` (current working directory) for self-referential queries. This ensures Xochitl reports on the folder the user is actually in.
3. **Expanded Phrases**: Added common variants like "where are you" and "what folder is this" to the fast-match list.

## Regression AC
`AC-BUG-ORCH-006`: Asking "what folder are you in" or "where am I" must trigger a file operation and return the current working directory path and its contents.

## Date
2026-05-05
