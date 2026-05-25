# CR-038 — Controlled Initiative

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 13 (Group 6 — Autonomy Layer)
**Source**: `docs/planning/exploration-2026-05.md` item #16

> **Note:** Renumbered from CR-036 to resolve ID collision with
> `CR-036-capability-boundary-comms.md` (E17). Capability boundary remains CR-036.

---

## Problem statement

Xochitl is entirely reactive — she only responds to user input. There is no
mechanism for surfacing time-sensitive failures (a Notion sync that failed
silently 10 minutes ago) or appropriate in-session follow-ups (a follow-up
offer when a multi-step task was begun earlier in the session). When something
worth noting happens in the background, it disappears with no path back to
the user.

The planning document warns that unsolicited proactive messages *reduce* system
usage and trust (arxiv 2509.09309) unless they follow a strict policy:
- Permitted categories: (a) time-sensitive system failures, (b) in-session
  follow-ups to work already begun. Nothing else.
- Confidence threshold: ≥ 0.80 before surfacing.
- User-controlled mode: `off | errors_only | full`. Default `errors_only`.
- Auto-suppress a category after 3 consecutive dismissals.
- Every proactive message must be actionable and dismissable in one command.

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| `FR-INIT-001` | `InitiativeEngine.submit(signal)` accepts a `ProactiveSignal`; rejects it silently if: (a) mode is `OFF`, (b) mode is `ERRORS_ONLY` and category is not `SYSTEM_FAILURE`, (c) `signal.confidence < _CONFIDENCE_THRESHOLD (0.80)`, or (d) the category is suppressed; otherwise queues it in `_pending` |
| `FR-INIT-002` | `InitiativeEngine.dismiss(category)` increments the dismissal counter for that category; after `_DISMISS_THRESHOLD (3)` dismissals the category is added to `_suppressed` and all future signals of that category are silently rejected |
| `FR-INIT-003` | `InitiativeEngine.drain() -> list[ProactiveSignal]` returns and clears all pending signals; calling drain() twice returns `[]` on the second call |

### Non-functional

| ID | Requirement |
|---|---|
| `NFR-INIT-001` | `InitiativeEngine` is instantiated once per `XochitlChat` session; `submit()`, `dismiss()`, and `drain()` must never raise to caller — all exceptions are caught internally; `submit()` below-threshold candidates are logged at DEBUG only (never surfaced to user) |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR038-001` | `InitiativeEngine(mode=OFF).submit(high-confidence SYSTEM_FAILURE)` | Signal not queued; `drain()` returns `[]` |
| `AC-CR038-002` | `InitiativeEngine(mode=ERRORS_ONLY).submit(high-confidence SYSTEM_FAILURE)` | Signal queued; `drain()` returns it |
| `AC-CR038-003` | `InitiativeEngine(mode=ERRORS_ONLY).submit(high-confidence IN_SESSION_FOLLOWUP)` | Signal not queued; `drain()` returns `[]` |
| `AC-CR038-004` | `submit(signal with confidence=0.75)` | Rejected; `drain()` returns `[]` |
| `AC-CR038-005` | `dismiss(SYSTEM_FAILURE)` called 3 times, then `submit(high-confidence SYSTEM_FAILURE)` | Signal not queued (suppressed); `drain()` returns `[]` |
| `AC-CR038-006` | `python smoke_test.py` | 129 passed, 0 failed |

---

## Design

### Policy model

```
ProactiveMode.OFF         → reject all signals
ProactiveMode.ERRORS_ONLY → accept SYSTEM_FAILURE only (default)
ProactiveMode.FULL        → accept SYSTEM_FAILURE + IN_SESSION_FOLLOWUP
```

### Signal lifecycle

```
[BackgroundReview detects failure]
        │
        ▼
InitiativeEngine.submit(signal)
        │
        ├─ mode allows? ──No──► silently discard
        ├─ confidence >= 0.80? ──No──► DEBUG log, discard
        ├─ category suppressed? ──Yes──► silently discard
        └─ ► enqueue to _pending
                │
        [turn start in _agent_loop()]
                │
                ▼
        drain() → inject as system hint before LLM call
```

### Dismissal lifecycle

```
User runs /dismiss (or swipes past)
        │
        ▼
InitiativeEngine.dismiss(category)
        │
        ├─ count < 3: increment only
        └─ count == 3: add to _suppressed → permanent suppression
```

### ProactiveSignal format

```python
@dataclass
class ProactiveSignal:
    category: InitiativeCategory
    message: str           # Short, actionable. Max 120 chars.
    confidence: float      # Must be >= 0.80 to be queued
    action_hint: str       # e.g. "Run /sync or /dismiss to skip."
```

The signal is surfaced in `_agent_loop()` by prepending a note block to the
assembled system prompt, similar to the drift identity reminder. The note
identifies itself as `[PROACTIVE ALERT]` so the model knows to surface it
as the first line of its response before handling the user's query.

---

## Implementation tasks

- [x] Write `CR-038-controlled-initiative.md` (renumbered from CR-036)
- [x] `src/initiative.py` (NEW) — `ProactiveMode`, `InitiativeCategory`, `ProactiveSignal`, `InitiativeEngine`
- [x] `src/background_review.py` (UPDATE) — `_initiative_engine` field; `submit_initiative()` public method
- [x] `src/chat.py` (UPDATE) — `InitiativeEngine` in `__init__()`; drain + inject in `_agent_loop()`; `/dismiss` slash command
- [x] `docs/spec/02-requirements-registry.md` — FR-INIT-001, FR-INIT-002, FR-INIT-003, NFR-INIT-001
- [x] `docs/spec/08-test-specs/TEST-INIT-001-controlled-initiative.md`
- [x] `smoke_test.py` — 5 tests (AC-CR038-001 through AC-CR038-005)
- [x] `docs/spec/06-traceability/traceability-matrix.md`
