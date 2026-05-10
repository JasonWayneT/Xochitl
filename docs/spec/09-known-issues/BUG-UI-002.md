# BUG-UI-002 — Status Indicator Freezes at 0.0s During File Context Resolution

## Status
Resolved

## Severity
Medium — UX degradation; user cannot tell if system is hanging or working

## Symptoms
When asking Xochitl to read or find a folder, the status bar shows:
```
  ◌ Resolving file context  (0.0s)
```
The timer never advances past 0.0s and the animation freezes. The UI appears
to hang even when the system is actively working.

## Root Cause
`_resolve_file_context()` in `router.py` used `root.rglob("*")` — a fully
recursive directory walk — to search for named folders/files. When the search
root was a large directory (e.g., `CodeProjects` containing hundreds of
sub-folders), this call blocked the Python thread entirely, preventing the
`Rich.Live` display from refreshing its render loop. Since `Rich.Live` updates
on the same thread, the elapsed timer was never incremented.

Additionally, the `◌` glyph was a static Unicode character — it did not
animate at all, making it visually indistinguishable from a frozen state.

## Affected Requirements
- `FR-UI-001` — Status bar must show live sub-task feed with elapsed timer
- `NFR-PERF-004` — File context resolution must not block the UI thread

## Fix Applied (Two-Part)

### Part 1 — Search Depth Limit
**File**: `src/router.py` — `_find_by_name()`
- Replaced unbounded `root.rglob("*")` with a two-stage shallow search:
  1. `root.iterdir()` — immediate children only (O(N), very fast)
  2. `root.glob("*/*")` — exactly 2 levels deep (bounded)
- This limits worst-case scan to ~thousands of entries vs. tens of thousands

### Part 2 — Flower Animation
**File**: `src/chat.py` — `_StatusContext`
- Replaced static `◌` glyph with a cycling flower animation: `✿ ❀ ✿ ❀`
- Added `_frame` counter that advances on every `_render()` call (4 fps)
- Flowers match the Xochitl splash screen aesthetic
- Result: even when the search is taking time, the animation cycles visibly

## Regression Acceptance Criterion
`AC-BUG-UI-002-A`: When Xochitl is resolving file context, the status
indicator must visually animate (flower must cycle between ✿ and ❀).

`AC-BUG-UI-002-B`: A search for a folder in a directory with 200+ sub-folders
must complete and return a result within 3 seconds.

## Related
- `FR-UI-001` — Status Tiers (Rich Live display)
- `BUG-CHAT-006` — Remote AI hallucination (same file resolution path)
- `CR-002` — Conversation layer hardening
