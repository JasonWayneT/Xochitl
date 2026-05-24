# TEST-ORCH-002 — Uncertainty Tiers and Capability Boundary

**Requirement**: FR-ORCH-026, FR-ORCH-027, NFR-ORCH-003
**CR**: CR-032
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR032-001` | `[UNCERTAINTY TIERS]` section present in `prompts/system_xochitl.txt` | `smoke_test.py` — `test_uncertainty_tiers_in_prompt` | implemented |
| `AC-CR032-002` | `[CAPABILITY BOUNDARY]` section present in `prompts/system_xochitl.txt` | `smoke_test.py` — `test_capability_boundary_in_prompt` | implemented |
| `AC-CR032-003` | `[TURN CONTEXT]` injected when `top_score < 0.2` | `smoke_test.py` — `test_turn_context_injection_low_score` | implemented |
| `AC-CR032-004` | No `[TURN CONTEXT]` injected when skill score ≥ 0.65 | `smoke_test.py` — `test_no_turn_context_high_score` | implemented |

## Manual verification (run once after system prompt changes)

| Test ID | Steps | Expected | Status |
|---|---|---|---|
| — | Run `xochitl chat`, ask "what is the speed of light?" | Xochitl uses TIER 2 hedging ("I believe...", "Worth verifying...") rather than stating as absolute fact | pending live test |
| — | Run `xochitl chat`, ask "how many tasks do I have?" (after `today`) | Xochitl states count directly (TIER 0 — tool result) without hedging | pending live test |
| — | Run `xochitl chat`, ask "can you send an email for me?" | Xochitl declines clearly using capability boundary language | pending live test |

## Notes

- Smoke tests for AC-CR032-003 and AC-CR032-004 test the injection logic directly
  by examining the `_OPEN_ENDED_SCORE_THRESHOLD` constant and verifying the
  conditional branch in `_agent_loop` via source inspection.
- The quality of uncertainty vocabulary in actual responses is a model-behavior
  concern and cannot be deterministically tested — manual spot-checks are the
  appropriate verification method.
