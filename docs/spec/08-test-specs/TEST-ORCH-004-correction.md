# TEST-ORCH-004 — Graceful Correction Handling

**Requirement**: FR-ORCH-030, FR-ORCH-031, NFR-ORCH-006
**CR**: CR-030
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR030-001` | `[CORRECTION HANDLING]` section present in system prompt | `smoke_test.py` — `test_correction_handling_in_prompt` | implemented |
| `AC-CR030-002` | `_detect_correction()` returns True/False correctly | `smoke_test.py` — `test_detect_correction_signals` | implemented |
| `AC-CR030-003` | Correction turns bypass rate limit | `smoke_test.py` — `test_correction_bypasses_rate_limit` | implemented |
| `AC-CR030-004` | Correction facts stored with category=preference, confidence>=0.9 | `smoke_test.py` — `test_correction_storage_category` | implemented |
| `AC-CR030-005` | Recurring correction escalates to preferences table | `smoke_test.py` — `test_correction_escalation_to_preferences` | implemented |

## Manual verification

| Steps | Expected | Status |
|---|---|---|
| In chat, ask something; correct Xochitl with "no, actually…" | Xochitl replies with "Got it." or "Right." — no apology, no re-explanation | pending live test |
| Give the same correction twice across turns | Second time it should feel like Xochitl already knew — no repetition of the mistake | pending live test |

## Notes

- AC-CR030-003 is verified by inspecting `BackgroundReview._process()` source
  for the correction fast-path branch — no live daemon required.
- AC-CR030-005 is verified by calling `BackgroundReview._store_correction_fact()`
  directly in a test with a mock DB connection.
