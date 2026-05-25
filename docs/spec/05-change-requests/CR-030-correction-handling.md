# CR-030 — Graceful Correction Handling

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #30 (Group 7C)
**Implements**: FR-ORCH-030, FR-ORCH-031, NFR-ORCH-006

---

## Problem

When a user corrects Xochitl — about facts, tone, framing, or approach — there
is no defined handling pattern. Current behavior is inconsistent: sometimes
over-apologetic ("I apologize for the confusion, I should have…"), sometimes
the original wrong answer is re-explained before correction, and corrections
are not reliably persisted to the preference log.

The planning document (#30 / C11) defines three specific anti-patterns to fix:
1. Re-explaining the original wrong answer before correcting.
2. Asking "Does this look better?" after correcting.
3. Over-apologetic filler that breaks conversational flow.

---

## Solution

### 1 — Behavioral guidance in `system_xochitl.txt`

Add a `[CORRECTION HANDLING]` section with the three-step rule:
- **Step 1** — minimal acknowledgment: "Got it.", "Right.", "Noted." One or two words only.
- **Step 2** — apply immediately, no re-explanation, no confirmation request.
- **Step 3** — treat as a preference signal; do not repeat the same mistake.

This section reaches the model on every turn (via the CR-029 template wiring).

### 2 — Correction detection in `BackgroundReview`

Add keyword-based correction-signal detection (`_detect_correction()`). When
a correction turn is detected:
- **Bypass `_MIN_WRITE_INTERVAL_SECS`** — corrections are always captured,
  regardless of how recently a fact was written.
- **Override structured extraction category/confidence** — store as
  category=`"preference"`, confidence=`0.9` (explicit correction is the
  highest-signal input; per the existing `_REVIEW_PROMPT` note: "Corrections
  and pushback are the strongest signal — weight them highest").

### 3 — Recurring-correction escalation to `preferences` table (NFR-ORCH-006)

Before storing in `memory_facts`, check for a near-duplicate (same 80-char
prefix match) indicating the correction has been seen before. If a prior
instance exists (≥ 2 occurrences), also store it in the `preferences` table
via `upsert_preference` with category=`"communication"`, confidence=`0.95`.

This gives `PreferenceEngine` visibility into stable correction patterns so
they are recalled at the start of every turn.

---

## Requirements

- **FR-ORCH-030** — `prompts/system_xochitl.txt` includes a `[CORRECTION HANDLING]`
  section defining the three-step correction pattern (brief ack, apply
  immediately, no over-apology, no re-explanation, no confirmation request).
- **FR-ORCH-031** — `BackgroundReview` detects correction-signal turns via
  `_detect_correction()`; correction turns bypass `_MIN_WRITE_INTERVAL_SECS`
  and are stored as category=`"preference"` with confidence ≥ 0.9.
- **NFR-ORCH-006** — When a correction fact near-duplicate is found in
  `memory_facts` (recurring correction), `BackgroundReview` also calls
  `upsert_preference` with category=`"communication"`, confidence=0.95.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR030-001` | `prompts/system_xochitl.txt` contains `[CORRECTION HANDLING]` section |
| `AC-CR030-002` | `_detect_correction()` returns `True` for correction phrases and `False` for normal input |
| `AC-CR030-003` | Correction turns bypass `_MIN_WRITE_INTERVAL_SECS` rate limit |
| `AC-CR030-004` | Correction facts stored with category=`"preference"` and confidence ≥ 0.9 |
| `AC-CR030-005` | Recurring correction (near-duplicate in `memory_facts`) triggers `upsert_preference` |

---

## Implementation tasks

- [x] Write `CR-030-correction-handling.md`
- [x] Add `[CORRECTION HANDLING]` section to `prompts/system_xochitl.txt`
- [x] Add `_CORRECTION_SIGNALS`, `_detect_correction()`, correction fast-path in `background_review.py`
- [x] Add `_store_correction_fact()` helper — pre-check + upsert + escalation
- [x] Update `_TurnData` and `queue_turn()` to carry `is_correction` flag
- [x] Write `docs/spec/08-test-specs/TEST-ORCH-004-correction.md`
- [x] Update requirements registry and traceability matrix
- [x] Add smoke tests; run full suite

---

## Design notes

- Keyword detection is intentionally heuristic — false positives (marking a
  non-correction as a correction) have a low cost: slightly elevated confidence
  and bypassed rate limit. False negatives miss a correction entirely, which
  is worse. Err on the side of sensitivity.
- The `_MIN_WRITE_INTERVAL_SECS` bypass applies only when `is_correction=True`.
  Rate limiting is preserved for all other turns.
- The `preferences` escalation key is deterministic: `correction_` +
  first 12 chars of hex MD5 of the lowercased 80-char fact prefix. This means
  the same correction stores to the same preference row, which upserts cleanly.
- `_extract_structured()` is still called for correction turns so the LLM
  extracts a well-formed fact sentence. The category and confidence overrides
  are applied in `_write()`, not inside `_extract_structured()`, to keep the
  extraction logic unchanged.
