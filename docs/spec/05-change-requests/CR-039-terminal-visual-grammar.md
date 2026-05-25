# CR-039 — Terminal Visual Grammar

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 14 (Group D — CLI UX)
**Source**: `docs/planning/exploration-2026-05.md` item #31 (D12)

---

## Problem statement

Skill and CLI output lacked a consistent terminal visual language: mixed colors,
inconsistent prefixes, no `--json` mode for scripting, and lines exceeding 80
characters.

---

## Requirements

| ID | Requirement |
|---|---|
| `FR-UI-009` | `src/terminal_output.py` provides `format_line`, `format_block`, `format_step`, `format_skill_output` with semantic prefixes (done/action/warn/fail), 2-space indent, 80-col wrap |
| `FR-UI-010` | CLI group `--json` on all commands: data commands emit JSON; interactive commands (`chat`, `plan`) return `interactive_only` error |
| `NFR-UI-009` | Operational output lines target ≤80 characters for pipe/copy safety |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR039-001` | `wrap_text()` on long string | No line exceeds configured width |
| `AC-CR039-002` | `format_line(..., rich=False)` | Plain prefixes `[ok]`, `->` present |
| `AC-CR039-003` | `format_step(1, 3, "Fetch")` | Contains `[1/3]` |
| `AC-CR039-004` | `xochitl --json today` | Valid JSON with `command` and `data.queue` |
| `AC-CR039-005` | `xochitl --json status` | Valid JSON with `projects` and `queue` |
| `AC-CR039-006` | `xochitl --json chat` | `ok: false`, `interactive_only` |
| `AC-CR039-007` | `python smoke_test.py` | All tests pass |

---

## Implementation

- [x] `src/terminal_output.py` (NEW)
- [x] `src/cli.py` — `--json` on group; `today`, `queue`, `done` JSON branches
- [x] `smoke_test.py` — CR-039 tests (ASCII labels)

---

## Verification

**Date**: 2026-05-25  
**Smoke**: `python smoke_test.py` — 146 passed, 0 failed (includes AC-CR039-001 through AC-CR039-006)  
**E2E**: `python end_to_end_test.py` — not re-run (terminal/CLI formatting only)  
**Registry / traceability**: `FR-UI-009`, `FR-UI-010`, `NFR-UI-009` marked implemented in `02-requirements-registry.md` and traceability matrix.
