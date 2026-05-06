# BUG-ORCH-001 — Context Drop: File references lost in multi-turn conversations

## Status
**FIXED** — `src/router.py` `_resolve_file_context()` + `TieredRouter.route()`

## Root Cause
1. **Scope Restriction**: `_resolve_file_context` only looked at the *current* user message. If a user provided a path in Turn 1, and the system asked for confirmation ("Want to start?"), the user's "yes" in Turn 2 triggered `_resolve_file_context("yes")`, which found nothing.
2. **Category Exclusion**: `TieredRouter.route` only called file resolution for the `file_operations` category. It was skipped for `general` and `simple_qa` (like "yes").
3. **Consequence**: The LLM saw the path in the history but lacked the *actual file content* in its system prompt. It then hallucinated that it had "read" the document and generated a generic summary (e.g., "Assuming the main function...").

## Fix
1. **History Awareness**: `_resolve_file_context` now accepts the `conversation_history` and scans the last 3 turns for paths if none are found in the current query.
2. **Global Injection**: `TieredRouter.route` now injects file context for `general`, `simple_qa`, `bmad_complex`, and `code_generation` categories as well.

## Regression AC
`AC-BUG-ORCH-001`: In a conversation where a file path is mentioned in Turn N, and Turn N+1 is a simple confirmation (e.g., "yes", "go ahead"), the LLM must still have access to the file content from Turn N. It must not hallucinate knowledge it doesn't have.

## Date
2026-05-05
