# CR-013 — Me.md Line Count Warning

## Status

Implemented.

## Summary

`UserProfileEngine` loads `Me.md` silently regardless of file length. If the file
grows past ~80 lines, the compaction path activates under token pressure and
truncates lower sections without any user-visible signal. The user has no way to
know their profile is being silently cut.

This CR adds a line count check in `UserProfileEngine.ingest()`. If `Me.md` exceeds
80 lines, a dim warning is printed to the terminal at session start. No hard limit,
no rejection — the file still loads. The warning is informational only, following
the same philosophy as the tag budget: inform, don't block.

## Motivation

The compaction design intentionally preserves the top sections of Me.md (Who I am,
Domains) and drops from the bottom. But this is only useful if the user knows it's
happening. Silent truncation of a file the user actively maintains is a trust
violation — they may believe Xochitl has full context when it doesn't.

## Affected Requirements

| ID | Change |
|---|---|
| `FR-ORCH-022` | No behavior change — ingest still loads the file; warning is additive |
| `NFR-ORCH-001` | This CR operationalizes the 80-line guidance by surfacing it at runtime |

## New Requirements Proposed

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `NFR-ORCH-002` | non-functional | P2 | When `Me.md` loads with more than 80 lines, `UserProfileEngine.ingest()` prints a dim warning to the terminal indicating the line count and that lower sections may compact under token pressure |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR013-001` | `NFR-ORCH-002` | Long Me.md | `Me.md` has 81+ lines | `UserProfileEngine.ingest()` runs | A dim warning is printed: line count and a note that lower sections may compact |
| `AC-CR013-002` | `NFR-ORCH-002` | Normal Me.md | `Me.md` has ≤80 lines | `UserProfileEngine.ingest()` runs | No warning is printed; ingest is silent |
| `AC-CR013-003` | `NFR-ORCH-002` | Missing Me.md | No `Me.md` file found | `UserProfileEngine.ingest()` runs | No warning is printed; ingest is silent |
| `AC-CR013-004` | `FR-ORCH-022` | Warning does not block | `Me.md` has 120 lines | `UserProfileEngine.ingest()` runs | File still loads fully; warning is printed but `self._content` contains the full file |

## Implementation Tasks

| ID | Requirement IDs | Task | File |
|---|---|---|---|
| `TASK-CR013-001` | `NFR-ORCH-002` | Add line count check after file read in `UserProfileEngine.ingest()`; print dim warning if count > 80 | `src/context_manager.py` |
| `TASK-CR013-002` | `NFR-ORCH-002` | Add `NFR-ORCH-002` to requirements registry | `docs/spec/02-requirements-registry.md` |
| `TASK-CR013-003` | `NFR-ORCH-002` | Add row to traceability matrix | `docs/spec/06-traceability/traceability-matrix.md` |

## Verification Results

2026-05-22:
- `py_compile` clean on `src/context_manager.py`.
- Logic unit-tested inline: line_count=85 triggers warning (True), line_count=79 does not (False).
- AC-CR013-004 confirmed by code inspection: `self._content` is set before the line
  count check runs; the warning branch does not modify `self._content`.
- Full session smoke test not re-run; change is a single additive print call with
  no effect on the assembly or compaction paths.
