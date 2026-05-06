# BUG-UI-001 — Startup crash: `AttributeError: module 'src.memory' has no attribute '_get_collection'`

## Status
**FIXED** — resolved in `src/stats.py` health_check().

## Severity
Critical — prevents Xochitl from starting at all.

## Affected Requirements
- FR-MEM-004 (Vector DB Semantic Search — Tier 3, LanceDB)
- NFR-REL-001 (Atomic write before embedding)

## Root Cause
`src/stats.py::health_check()` called `mem._get_collection()`, a legacy ChromaDB
function. The memory module was refactored to LanceDB (`VectorMemory._open_table()`)
but `health_check()` was never updated to match the new API surface. The module
has no `_get_collection` attribute, so Python raises `AttributeError` on startup.

## Regression Acceptance Criterion
`AC-BUG-UI-001`: Running `xochitl` (or `xochitl chat`) must not raise
`AttributeError` on `src.memory`. The health check must return a dict with a
`vector_db` boolean key without crashing.

## Test Case
`TEST-BUG-UI-001`: In `smoke_test.py`, import `health_check` from `src.stats`
and assert it returns a dict containing the key `vector_db` without raising.

## Fix Applied
`src/stats.py` line 58:
- **Before**: `vector_ok = mem._get_collection() is not None`
- **After**: `vector_ok = mem.VectorMemory()._open_table() is not None`

Error message updated from "ChromaDB unavailable" → "LanceDB unavailable" to
match the current backend.

## Date
2026-05-05
