# CR-040 — Compact Reasoning Disclosure

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 15 (Group E — Trust)
**Source**: `docs/planning/exploration-2026-05.md` item #34 (E15)

---

## Problem statement

Responses either hid what happened or over-explained. Users need audit-ability:
a one-line action summary before results, with full reasoning only on explicit
"Why?" / "How did you get that?" requests.

---

## Requirements

| ID | Requirement |
|---|---|
| `FR-ORCH-044` | `action_summary()` / `_emit_action_line()` print one-line action before skill or weather work |
| `FR-ORCH-045` | `format_compact_result()` pairs action summary with formatted result body |
| `FR-ORCH-046` | `is_why_request()` triggers `build_why_expansion()` in `process_message()` without a full re-run |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR040-001` | `is_why_request("Why?")` | Returns `True`; normal queries `False` |
| `AC-CR040-002` | `action_summary("Checking weather")` | Label present in output |
| `AC-CR040-003` | `format_compact_result(action, body)` | Both action and body in string |
| `AC-CR040-004` | `prompts/system_xochitl.txt` | Contains `[REASONING DISCLOSURE]` section |
| `AC-CR040-005` | `python smoke_test.py` | All tests pass |

---

## Implementation

- [x] `src/action_disclosure.py` (NEW)
- [x] `src/chat.py` — why branch, `_emit_action_line`, compact skill results
- [x] `prompts/system_xochitl.txt` — `[REASONING DISCLOSURE]`
- [x] `smoke_test.py` — CR-040 tests (ASCII labels)

---

## Verification

**Date**: 2026-05-25  
**Smoke**: `python smoke_test.py` — 146 passed, 0 failed (includes AC-CR040-001 through AC-CR040-003)  
**E2E**: `python end_to_end_test.py` — not re-run  
**Registry / traceability**: `FR-ORCH-044` through `FR-ORCH-046` marked implemented.
