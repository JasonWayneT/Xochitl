# CR-033 — Persona Drift Detection

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 12 (Group 7B — Persona and Identity Persistence)
**Source**: `docs/planning/exploration-2026-05.md` item #26 (B7)

---

## Problem statement

Long or emotionally charged conversations cause Xochitl to drift from her
established voice without recovery. There is no detection mechanism: once the
persona drifts toward a generic assistant tone, it persists until the session
ends. CR-029 anchored the identity in the system prompt, but a static anchor
is insufficient against multi-turn pressure from corrections, high-stakes
emotional context, or sequential tool-execution sessions.

The planning document identifies three drift triggers:
1. Multiple corrections in succession (≥ 2 correction turns detected by CR-030's `_detect_correction`)
2. High-volume tool-execution session (proxy: correction-pressure threshold)
3. Regular interval check (every `_DRIFT_CHECK_INTERVAL = 12` turns)

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| `FR-ORCH-042` | `BackgroundReview` tracks a per-session turn counter (`_turn_count`) and correction counter (`_correction_turns`); a drift check fires when `_turn_count % _DRIFT_CHECK_INTERVAL == 0` OR `_correction_turns >= 2`; after each drift check, `_correction_turns` resets to 0 |
| `FR-ORCH-043` | When `BackgroundReview.drift_detected` is `True` at the start of a turn, `_agent_loop()` appends `_DRIFT_IDENTITY_REMINDER` to the assembled system prompt and immediately calls `BackgroundReview.clear_drift()` |

### Non-functional

| ID | Requirement |
|---|---|
| `NFR-ORCH-016` | Drift check uses `call_local` with `ROUTER_MODEL` (local model only); prompt is capped by `_DRIFT_PROMPT_MAX_CHARS`; the LLM is asked only "DRIFT or OK"; result parsed case-insensitively for "DRIFT" |
| `NFR-ORCH-017` | Drift check and flag read/write are thread-safe via `_drift_lock`; any exception in `_check_drift_with_identity()` is swallowed silently — drift detection must never disrupt the background thread or the main loop |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR033-001` | `_check_drift_with_identity("Xochitl is warm...")` with `call_local` mocked to return `"DRIFT"` | `drift_detected` becomes `True` |
| `AC-CR033-002` | Same setup but `call_local` returns `"OK — no drift"` | `drift_detected` stays `False` |
| `AC-CR033-003` | Call `clear_drift()` after setting `_drift_detected = True` | `drift_detected` is `False` |
| `AC-CR033-004` | `BackgroundReview` with `_turn_count = _DRIFT_CHECK_INTERVAL`, `_correction_turns = 0` | `_should_run_drift_check()` returns `True` |
| `AC-CR033-005` | `BackgroundReview` with `_turn_count = 1`, `_correction_turns = 2` | `_should_run_drift_check()` returns `True` (correction pressure) |
| `AC-CR033-006` | `from src.chat import _DRIFT_IDENTITY_REMINDER` | Defined; is a non-empty string containing identity-reminder language |
| `AC-CR033-007` | `python smoke_test.py` | 109 passed, 0 failed |

---

## Design

### Drift judge prompt

```
Identity: {identity anchor — up to 200 chars}
Recent responses:
[R1] {last-3 assistant response, 150 chars each}
[R2] ...
[R3] ...
Does the language sound like a different, more generic AI rather than
the defined personality? Answer only: DRIFT or OK.
```

The prompt is intentionally minimal (~100 tokens). The local model only has to
compare two patterns — not summarize or explain. "DRIFT" in the response (any
case) sets the flag.

### Drift triggers

```
_DRIFT_CHECK_INTERVAL = 12   # midpoint of 10-15 from planning doc
_DRIFT_RESPONSE_BUFFER = 3   # keep last 3 assistant responses
```

- **Regular interval**: every 12 completed turns.
- **Correction pressure**: when 2+ correction turns accumulate since last check.
- After each drift check: reset `_correction_turns = 0`.

### Flag lifecycle

```
[background thread]          [main thread / _agent_loop]
     |                              |
     |  sets _drift_detected=True  |  reads drift_detected (property)
     |  under _drift_lock           |  appends _DRIFT_IDENTITY_REMINDER
                                   |  calls clear_drift()
```

`drift_detected` is a thread-safe property. `clear_drift()` acquires `_drift_lock`.

### Identity reminder injected into system prompt

```
\n\n---\n[IDENTITY REMINDER]\nYou are Xochitl, not a generic assistant.
Reconnect with your established voice: warm, direct, culturally grounded.
No filler openers. No over-explanation.\n---
```

Appended after `assemble_system_prompt()`, before skill scoring and LLM call.
The transformer recency bias means the reminder appears close to the end of
the prompt, giving it strong influence on the next response.

---

## Implementation tasks

- [x] Write `CR-033-persona-drift.md`
- [x] Update `src/background_review.py` — drift constants, turn counters, `_drift_detected` flag, `drift_detected` property, `clear_drift()`, `_should_run_drift_check()`, `_check_drift_with_identity()`, `_run_drift_check()`, `_get_identity_anchor()`, trigger in `_process()`
- [x] Update `src/chat.py` — `_DRIFT_IDENTITY_REMINDER` constant, drift injection in `_agent_loop()`
- [x] Update `docs/spec/02-requirements-registry.md` — FR-ORCH-042, FR-ORCH-043, NFR-ORCH-016, NFR-ORCH-017
- [x] Write `docs/spec/08-test-specs/TEST-ORCH-005-persona-drift.md`
- [x] Update `smoke_test.py` — 5 tests (AC-CR033-001 through AC-CR033-006)
- [x] Update `docs/spec/06-traceability/traceability-matrix.md`
