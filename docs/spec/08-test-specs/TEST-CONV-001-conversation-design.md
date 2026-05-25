# TEST-CONV-001 — Conversation Design A1–A5

**Status**: implemented
**Date**: 2026-05-25
**Implements**: AC-CR028-001 through AC-CR028-005
**CR**: CR-028

---

## Scope

Five pure-function utilities in `src/conversation.py`, `src/anticipation.py`,
`src/brief.py`, and `src/context_manager.py::PreferenceEngine`. All functions
are heuristic/deterministic — no LLM calls, no real network I/O.
External dependencies (DB, subprocess) are mocked at the call boundary.

---

## Test cases

### AC-CR028-001 — `strip_filler_opener()` (A1)

**Requirement**: FR-CONV-001

| # | Input | Expected output | Rationale |
|---|---|---|---|
| 1 | `"Certainly! Here is the answer."` | `"Here is the answer."` | Bare affirmative stripped |
| 2 | `"Great question! Let me explain."` | `"Let me explain."` | Superlative on "question" stripped |
| 3 | `"Of course, I can help."` | `"I can help."` | `"Of course,"` stripped |
| 4 | `"Absolutely! Here you go."` | `"Here you go."` | `"Absolutely!"` stripped |
| 5 | `"I'd be happy to help! Let me check."` | `"Let me check."` | Helper-role opener stripped |
| 6 | `"The file exists at that path."` | unchanged | No filler — passes through |
| 7 | `"Run \`xochitl today\` to refresh."` | unchanged | No filler — passes through |
| 8 | `"Certainly!"` | `"Certainly!"` | Entire response is filler — return original, not empty |

**Edge cases**:
- First letter of remainder is re-capitalised if lowercased by the strip.
- Only the first filler match is stripped (one-pass).
- An all-filler response returns the original (not empty string).

---

### AC-CR028-002 — `uncertainty_hedge()` (A5)

**Requirement**: FR-CONV-005

| # | confidence | Input text | Expected output |
|---|---|---|---|
| 1 | 0.90 | `"The meeting is tomorrow at 3pm."` | unchanged (CERTAIN tier) |
| 2 | 0.86 | `"Task is in the WIP queue."` | unchanged (just above 0.85) |
| 3 | 0.85 | `"The answer is 42."` | `"I think the answer is 42."` (boundary: `>0.85` is CERTAIN; `≤0.85` is MID) |
| 4 | 0.72 | `"The meeting is at 3pm."` | `"I think the meeting is at 3pm."` |
| 5 | 0.60 | `"It is in Projects."` | `"I think it is in Projects."` (lower MID boundary — inclusive) |
| 6 | 0.59 | `"The deadline is Friday."` | `"I'm not certain, but the deadline is Friday — want me to look this up?"` |
| 7 | 0.00 | `"It was yesterday."` | `"I'm not certain, but it was yesterday — want me to look this up?"` |
| 8 | 0.50 | `""` | `ValueError` — text must not be empty |

**Tier boundaries**:
- `confidence > 0.85` → CERTAIN (unchanged)
- `0.60 ≤ confidence ≤ 0.85` → MID (`"I think …"`)
- `confidence < 0.60` → LOW (`"I'm not certain, but … — want me to look this up?"`)

---

### AC-CR028-003 — `AnticipationGate.check()` (A2)

**Requirement**: FR-CONV-002

| # | wip_count | last_session_age_hours | mocked hour | Expected |
|---|---|---|---|---|
| 1 | 1 | 10.0 | 14 (off-peak) | non-None hint (wip + recency = 2 signals) |
| 2 | 0 | None | 14 | None (0 signals) |
| 3 | 2 | 8.0 | 8 (morning) | non-None hint (wip + recency + morning = 3 signals) |
| 4 | 0 | 2.0 | 14 | None (only recency — 1 signal) |
| 5 | 1 | None | 18 (evening) | non-None hint (wip + evening = 2 signals) |

**Hint content checks**:
- Morning signal → hint contains `"Good morning."`
- Evening signal → hint contains `"Winding down?"`
- WIP signal → hint contains `"task"` or queue indicator
- Recency signal → hint contains `"Last session was"` with hours/days
- WIP signal → hint contains `"Run \`xochitl today\`"`

**`check_from_db()` isolation**:
- Any DB exception → silently returns `None` (startup must never fail)

---

### AC-CR028-004 — `build_structured_brief()` (A3)

**Requirement**: FR-CONV-003

| # | queue | notion_pending | git mock | Expected sections |
|---|---|---|---|---|
| 1 | 2 tasks | 1 notion item | stale (26h) | Temporal, Priorities, Async queue, Awareness |
| 2 | 0 tasks | 0 items | no git | Returns non-empty fallback string |
| 3 | 3 tasks | 0 items | fresh (<2h) | Temporal, Priorities (no Awareness) |
| 4 | 0 tasks | 2 items | stale | Temporal, Async queue, Awareness |

**Section invariants**:
- Temporal context always present (day name + time).
- Priorities section only when `len(queue) > 0`.
- Async queue section only when `len(notion_pending) > 0`.
- Awareness section only when git commit is ≥ 2h stale.
- Max 5 items per section (`_MAX_LINES_PER_SECTION = 5`).
- No LLM calls — all data is caller-supplied or git-only (NFR-CONV-001).

---

### AC-CR028-005 — `PreferenceEngine.assemble()` (A4)

**Requirement**: FR-CONV-004

| # | _rows | Expected output |
|---|---|---|
| 1 | `[]` | `""` (empty — no block injected) |
| 2 | 1 global preference | Contains `[BACKGROUND CONTEXT]` and `[/BACKGROUND CONTEXT]` |
| 3 | 1 global preference | Does **not** contain `[global/communication]` (old format) |
| 4 | 1 global preference | Contains `"do not cite"` instruction |
| 5 | 1 global preference | Contains the preference value text |
| 6 | 2 preferences (different categories) | Both values appear; both categories capitalised |

**Negative test**:
- Old raw format `[scope/category] value` must NOT appear.
- `"## User Preferences"` heading must NOT appear (replaced by `[BACKGROUND CONTEXT]` block).

---

## Implementation notes

- All tests are in `smoke_test.py` under the `# ── CR-028` section.
- `datetime.now` in `src/anticipation` is patched via `unittest.mock.patch` so morning/evening
  window tests are time-zone-safe and deterministic (NFR-DEV-005).
- `subprocess.run` in `src/brief` is patched to control git commit timestamps without
  requiring a real git repository in the test runner (NFR-DEV-005).
- `PreferenceEngine` rows are set directly (`engine._rows = [...]`) to bypass DB setup.

---

## Traceability

| Test function | Acceptance criterion | Requirement |
|---|---|---|
| `t_strip_filler_opener_removes_and_passes` | AC-CR028-001 | FR-CONV-001 |
| `t_uncertainty_hedge_three_tiers` | AC-CR028-002 | FR-CONV-005 |
| `t_anticipation_gate_signals` | AC-CR028-003 | FR-CONV-002 |
| `t_build_structured_brief_sections` | AC-CR028-004 | FR-CONV-003 |
| `t_preference_engine_natural_framing` | AC-CR028-005 | FR-CONV-004 |
