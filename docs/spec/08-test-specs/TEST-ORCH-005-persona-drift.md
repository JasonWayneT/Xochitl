# TEST-ORCH-005 — Persona Drift Detection

**Status**: implemented
**Date**: 2026-05-25
**Implements**: AC-CR033-001 through AC-CR033-006
**CR**: CR-033

---

## Scope

`BackgroundReview` drift-detection methods in `src/background_review.py`
and the `_DRIFT_IDENTITY_REMINDER` constant in `src/chat.py`.

All LLM calls mocked at `src.llm_interface.call_local`. No real LLM calls,
no DB access, no file I/O (NFR-DEV-005).

---

## Test cases

### AC-CR033-001 — DRIFT response sets flag

**Requirement**: FR-ORCH-042, NFR-ORCH-016

| # | Setup | Expected |
|---|---|---|
| 1 | `call_local` mocked to return `"DRIFT"` | `drift_detected` → `True` |
| 2 | Three items in `_recent_responses` | Prompt built and call made |
| 3 | Identity anchor non-empty | Check proceeds |

---

### AC-CR033-002 — OK response leaves flag clear

**Requirement**: FR-ORCH-042, NFR-ORCH-016

| # | Setup | Expected |
|---|---|---|
| 1 | `call_local` mocked to return `"OK — no drift detected"` | `drift_detected` stays `False` |
| 2 | Same setup as AC-CR033-001 otherwise | Only the response content differs |

---

### AC-CR033-003 — `clear_drift()` resets flag

**Requirement**: FR-ORCH-043, NFR-ORCH-017

| # | Setup | Expected |
|---|---|---|
| 1 | Manually set `_drift_detected = True` under lock | `drift_detected` is `True` |
| 2 | Call `clear_drift()` | `drift_detected` is `False` |

---

### AC-CR033-004 — Interval trigger

**Requirement**: FR-ORCH-042

| # | Setup | Expected |
|---|---|---|
| 1 | `_turn_count = _DRIFT_CHECK_INTERVAL`, `_correction_turns = 0` | `_should_run_drift_check()` returns `True` |
| 2 | `_turn_count = _DRIFT_CHECK_INTERVAL - 1`, `_correction_turns = 0` | Returns `False` |
| 3 | `_turn_count = 0`, `_correction_turns = 0` | Returns `False` (zero-turn guard) |

---

### AC-CR033-005 — Correction-pressure trigger

**Requirement**: FR-ORCH-042

| # | Setup | Expected |
|---|---|---|
| 1 | `_turn_count = 1`, `_correction_turns = 2` | `_should_run_drift_check()` returns `True` |
| 2 | `_turn_count = 1`, `_correction_turns = 1` | Returns `False` (only 1 correction, need ≥ 2) |

---

### AC-CR033-006 — `_DRIFT_IDENTITY_REMINDER` defined in `chat.py`

**Requirement**: FR-ORCH-043

| # | Check | Expected |
|---|---|---|
| 1 | `from src.chat import _DRIFT_IDENTITY_REMINDER` | Importable, no error |
| 2 | `isinstance(_DRIFT_IDENTITY_REMINDER, str)` | `True` |
| 3 | Length > 0 | Non-empty |
| 4 | Contains "IDENTITY REMINDER" | Marker present for audit |

---

## Implementation notes

- `_check_drift_with_identity(identity)` is tested directly to bypass
  `_get_identity_anchor()` (which loads SOUL.md). This keeps tests hermetic.
- `call_local` is patched at `src.llm_interface.call_local` — the local import
  inside `_check_drift_with_identity()` resolves the patched version at call time.
- `_should_run_drift_check()` is a named pure method — no side effects,
  directly testable without running `_process()`.

---

## Traceability

| Test function | Acceptance criterion | Requirement |
|---|---|---|
| `t_drift_flag_set_by_drift_response` | AC-CR033-001 | FR-ORCH-042, NFR-ORCH-016 |
| `t_drift_flag_clear_for_ok_response` | AC-CR033-002 | FR-ORCH-042, NFR-ORCH-016 |
| `t_drift_clear_resets_flag` | AC-CR033-003 | FR-ORCH-043, NFR-ORCH-017 |
| `t_drift_interval_trigger` | AC-CR033-004 | FR-ORCH-042 |
| `t_drift_correction_pressure_trigger` | AC-CR033-005 | FR-ORCH-042 |
| `t_drift_reminder_constant_defined` | AC-CR033-006 | FR-ORCH-043 |
