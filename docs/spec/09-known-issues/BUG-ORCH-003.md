# BUG-ORCH-003 — Folder resolution: Unquoted folder names are ignored

## Status
**FIXED** — `src/router.py` `_resolve_file_context()`

## Root Cause
The file resolution logic was too strict, only looking for:
1. Explicit absolute paths (regex-based).
2. Filenames with extensions (regex-based).
3. Quoted strings (e.g. `"my folder"`).

If a user said `read the zettlelib folder`, the word `zettlelib` was not quoted and had no extension, so it was never passed to the search function. This resulted in an empty file context and a confusing error message.

## Fix
Added a word-based search to `_resolve_file_context`. It now extracts every word with 3+ characters from the query and attempts to find a matching directory in the authorized registry. Common stop words ("the", "and", "read", etc.) are excluded to keep the search efficient.

## Regression AC
`AC-BUG-ORCH-003`: A query like `read the [foldername] folder` should correctly resolve `[foldername]` even if it is not quoted or part of a full path, provided it exists in an authorized directory.

## Date
2026-05-05
