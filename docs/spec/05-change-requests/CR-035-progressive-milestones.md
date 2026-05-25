# CR-035 — Progressive Personalization Milestones

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 12 (Group 7C — Relationship Building)
**Source**: `docs/planning/exploration-2026-05.md` item #28 (C9)

---

## Problem statement

Xochitl behaves identically in session 1 and session 50. A new user and a
long-term user receive the same degree of formality, the same absence of
proactive anticipation, and the same reluctance to reference memory naturally.
The planning document defines three milestones that gate progressively warmer,
more personalized behavior as the relationship matures — purely based on
session count, with zero user-visible announcement.

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| `FR-PREF-004` | `get_milestone(session_count: int) -> Milestone` returns `Milestone.M1` for sessions 1–5, `Milestone.M2` for sessions 6–20, `Milestone.M3` for sessions 21+ |
| `FR-PREF-005` | `ContextManager.assemble_system_prompt()` injects `milestone_context_block(milestone)` into the assembled prompt; M1 returns an empty string (no extra block); M2 injects a preference-reference + first-name cue; M3 injects a memory-reference + anticipation-enabled cue |

### Non-functional

| ID | Requirement |
|---|---|
| `NFR-PREF-002` | Milestone transitions are silent — never surfaced to the user; logged internally at DEBUG level only; `XochitlChat.start()` computes the milestone and logs it; no announcement string is ever appended to any user-visible output |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR035-001` | `get_milestone(1)` and `get_milestone(5)` | Both return `Milestone.M1` |
| `AC-CR035-002` | `get_milestone(6)` and `get_milestone(20)` | Both return `Milestone.M2` |
| `AC-CR035-003` | `get_milestone(21)` and `get_milestone(100)` | Both return `Milestone.M3` |
| `AC-CR035-004` | `milestone_context_block(Milestone.M1)` | Returns empty string — no extra block for new users |
| `AC-CR035-005` | `milestone_context_block(Milestone.M2)` and `milestone_context_block(Milestone.M3)` | Both return non-empty strings containing personalization guidance |
| `AC-CR035-006` | `python smoke_test.py` | 119 passed, 0 failed |

---

## Design

### Milestone definitions

```
M1 (sessions 1–5):   formal, minimal assumptions, no proactive anticipation
M2 (sessions 6–20):  reference stored preferences, use first name naturally,
                      in-session follow-ups enabled
M3 (sessions 21+):   natural memory reference active, anticipation gate on,
                      milestone-aware brief format
```

### `get_milestone` algorithm

```
if session_count <= 5  → M1
if session_count <= 20 → M2
else                   → M3
```

Session count = total rows in the `sessions` table (one row per
`create_session()` call). Includes the current session — so after the first
ever `xochitl chat`, count = 1 → M1.

### Context block injection

`ContextManager` accepts `milestone_block: str = ""` in `__init__()`.
`assemble_system_prompt()` appends it as the last block (after preferences,
memory, files) when non-empty — keeping it close to the end of the prompt
where local models weight it most strongly.

`XochitlChat` computes the milestone once in `start()` and stores
`self._milestone_block`. It passes it to `ContextManager()` on every turn
in `_agent_loop()`.

### Silent transition

```python
# In start() after session creation:
milestone = get_milestone(session_count)
logger.debug("milestone: %s (sessions: %d)", milestone.value, session_count)
self._milestone_block = milestone_context_block(milestone)
```

No console output. No system prompt announcement. The behavioral change is
the signal — not the label.

---

## Implementation tasks

- [x] Write `CR-035-progressive-milestones.md`
- [x] `src/database.py` (UPDATE) — `get_session_count(conn)` helper
- [x] `src/milestones.py` (NEW) — `Milestone` enum, `get_milestone()`, `milestone_context_block()`
- [x] `src/context_manager.py` (UPDATE) — `milestone_block` in `__init__()`; injection in `assemble_system_prompt()`
- [x] `src/chat.py` (UPDATE) — compute milestone in `start()`; pass `milestone_block` to `ContextManager()` in `_agent_loop()`
- [x] `docs/spec/02-requirements-registry.md` — FR-PREF-004, FR-PREF-005, NFR-PREF-002
- [x] `docs/spec/08-test-specs/TEST-PREF-002-milestones.md`
- [x] `smoke_test.py` — 5 tests (AC-CR035-001 through AC-CR035-005)
- [x] `docs/spec/06-traceability/traceability-matrix.md`
