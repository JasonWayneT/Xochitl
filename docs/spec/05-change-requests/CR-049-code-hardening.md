# CR-049 — Code Hardening

| Field | Value |
|---|---|
| ID | CR-049 |
| Title | Code Hardening — Bug Fixes, Type Safety, and UX Completeness |
| Status | accepted |
| Priority | P0–P1 |
| Author | Jason Wayne |
| Date | 2026-05-27 |
| Implements | FR-HARD-001 through FR-HARD-010, NFR-HARD-001 through NFR-HARD-005 |
| Registry | Add FR-HARD-001 – FR-HARD-010, NFR-HARD-001 – NFR-HARD-005 |

## Summary

Post-CR-048 audit identified 40+ concrete improvement opportunities. This CR addresses the highest-priority subset:

1. **Bug Fixes (P0)** — stderr lost on executor truncation, column-name f-string in SQL, missing exception context in workflow steps
2. **Code Hardening (P1)** — dynamic terminal width, complete initiative discard logging, type-safe examples guard, skill name index
3. **Type Safety (NFR-DEV-002)** — complete return-type annotations on `action_disclosure.py`, `database.py` key functions
4. **Docstrings (NFR-DEV-004)** — Google-style docstrings on all `action_disclosure.py` public functions and `score_workflow_match`
5. **New UX Feature** — `/history` slash command to view recent session context summaries

## Bug Fixes

### FR-HARD-001: Preserve stderr on executor truncation

`executor.py run()` currently discards `stderr` entirely when stdout fills `_OUTPUT_CAP_BYTES` (sets `stderr_raw = b""`). If a command produces both large stdout and error output (e.g., a build command that emits a wall of output then an error), the error is invisible to the user. Fix: split the cap 80/20 (stdout gets 80%, stderr gets 20%) so critical error context is always preserved.

### FR-HARD-002: Static SQL in record_workflow_run

`database.py record_workflow_run()` builds the column name via `f"UPDATE workflows SET {col}={col}+1"`. While `col` comes from a hardcoded boolean ternary (not user input), the pattern is a code smell that tools like bandit will flag. Fix: use two static parameterized SQL statements instead of a dynamic f-string.

### FR-HARD-003: Include exception type in workflow step failure

`workflows.py execute_workflow()` appends `f"  [fail] {exc}"` on step failure. This loses the exception class, making debugging hard. Fix: log `f"  [fail] {type(exc).__name__}: {exc}"`.

## Code Hardening

### FR-HARD-004: Dynamic terminal width in terminal_output.py

`MAX_LINE_WIDTH = 80` is hardcoded. On wide terminals (120+ columns), responses are wrapped at 80 chars unnecessarily. On narrow terminals (< 80), text can overflow. Fix: use `shutil.get_terminal_size((80, 24)).columns` at import time.

### FR-HARD-005: Complete initiative discard logging

`InitiativeEngine.submit()` logs when signals are below the confidence threshold but silently discards (no log) when: mode is OFF, mode is ERRORS_ONLY and category is not critical, or category is suppressed. Adding debug-level logs to all three paths makes initiative behavior observable without noise in production.

### FR-HARD-006: Type-safe examples guard in _format_active_skill_block

`_format_active_skill_block()` does `if examples:` then `for ex in examples[:6]`. If a skill's `tool_definition()` returns `examples` as a string (e.g. `"see docs"`), iterating would produce single characters. Guard: `if isinstance(examples, list) and examples:`.

### FR-HARD-007: Skill name index for O(1) lookup

`_find_skill_by_name()` iterates every skill and calls `skill.tool_definition()` on each — O(N) with a non-trivial cost per call. Replace with a `_skill_name_index: dict[str, Skill]` cached lazily from the `skills` property.

## Type Safety & Docstrings

### NFR-HARD-001: Return-type annotations on action_disclosure.py

All six public functions missing `-> bool` or `-> str` return annotations.

### NFR-HARD-002: Google-style docstrings on action_disclosure.py

All six public functions missing Google-style docstrings (required by NFR-DEV-004).

### NFR-HARD-003: Return-type annotations on key database.py functions

`queue_size`, `record_workflow_run`, `upsert_preference`, `get_session_count`, `audit` missing explicit `-> int`, `-> None`, etc.

### NFR-HARD-004: Docstring on score_workflow_match

`workflows.py score_workflow_match()` is a public function with no docstring — violates NFR-DEV-004.

## New Feature

### FR-HARD-008: /history slash command

`/history [N]` prints a table of the last N (default 5) session summaries from the `sessions` table — started_at timestamp, last_active, and context_summary excerpt. Lets the user quickly recall what they were working on in previous sessions without leaving the chat.

### FR-HARD-009: /help improvements

Expand `/help` to show a structured table of all slash commands with one-line descriptions, rather than delegating entirely to `stats.help_text()`.

### FR-HARD-010: Skill health_check() protocol in base class

Add `health_check() -> bool` as an optional method in the `Skill` base class (returning `True` by default). Skills that depend on external credentials override it. This formalizes FR-JARV-007 which assumed the protocol existed.

## Acceptance Criteria

| ID | Requirement | Scenario | Expected |
|---|---|---|---|
| AC-CR049-001 | FR-HARD-001 | ExecutorResult with truncated output | stderr field contains partial data, not empty |
| AC-CR049-002 | FR-HARD-002 | record_workflow_run(success=True) | SQL uses static string, no f-string interpolation |
| AC-CR049-003 | FR-HARD-003 | Workflow step raises ValueError | fail message contains "ValueError:" prefix |
| AC-CR049-004 | FR-HARD-004 | wrap_text called at runtime | uses terminal width, not hardcoded 80 |
| AC-CR049-005 | FR-HARD-005 | submit() with mode=OFF | debug log emitted |
| AC-CR049-006 | FR-HARD-006 | _format_active_skill_block with examples="" | no crash, no character-per-line output |
| AC-CR049-007 | FR-HARD-007 | _find_skill_by_name called twice | tool_definition() not called twice for same skill |
| AC-CR049-008 | NFR-HARD-001 | inspect action_disclosure public functions | all have return type annotations |
| AC-CR049-009 | FR-HARD-008 | /history typed in chat | response contains session timestamps |
| AC-CR049-010 | FR-HARD-010 | Skill().health_check() called on base class | returns True |
| AC-CR049-011 | All | python smoke_test.py | ≥ 176 tests pass, 0 failures |

## Files Changed

| File | Change |
|---|---|
| `src/executor.py` | Split cap 80/20 between stdout/stderr |
| `src/database.py` | Static SQL in `record_workflow_run`; return type hints on key functions |
| `src/workflows.py` | Exception type in step failure message; docstring on `score_workflow_match` |
| `src/terminal_output.py` | Dynamic terminal width via `shutil.get_terminal_size` |
| `src/initiative.py` | Debug logging on all discard paths |
| `src/chat.py` | isinstance guard in `_format_active_skill_block`; skill name index; `/history` command; `/help` improvements |
| `src/action_disclosure.py` | Return-type annotations + Google-style docstrings on all 6 public functions |
| `src/skills/base.py` | `health_check() -> bool` default method |
| `smoke_test.py` | New tests for AC-CR049-001 through AC-CR049-010 |
