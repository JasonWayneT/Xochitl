# TEST-ORCH-001 — Session Tiered Governor

**Requirement**: FR-ORCH-025, NFR-PERF-011
**CR**: CR-026
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR026-001` | Fresh `SessionGovernor` starts at FULL tier | `smoke_test.py` — `test_governor_starts_full` | implemented |
| `AC-CR026-002` | After ≥ 20 000 est. tokens, tier is PREFER_LOCAL | `smoke_test.py` — `test_governor_prefer_local_tier` | implemented |
| `AC-CR026-003` | After ≥ 40 000 est. tokens, tier is LOCAL_ONLY; `force_route()` returns `"general"` | `smoke_test.py` — `test_governor_local_only_tier` | implemented |
| `AC-CR026-004` | After ≥ 80 000 est. tokens, tier is HARD_STOP; `force_route()` returns `"general"` | `smoke_test.py` — `test_governor_hard_stop_tier` | implemented |
| `AC-CR026-005` | `XCH_LOCAL_ONLY_TOKENS` env var overrides threshold | `smoke_test.py` — `test_governor_env_override` | implemented |

## Manual verification (run once per chat.py change)

| Test ID | Steps | Expected | Status |
|---|---|---|---|
| `AC-CR026-006` | Start `xochitl chat`, type `/budget` | Prints tier, estimated tokens, and thresholds | verified by inspection |
| `AC-CR026-007` | Set `XCH_PREFER_LOCAL_TOKENS=1`, hold a 3-turn session | Budget warning appears exactly once | pending live test |

## Notes

- Smoke tests bypass `chat.py` and test `SessionGovernor` directly to avoid needing
  a live LLM or chat session.
- The env-var test (AC-CR026-005) patches `os.environ` and reimports the module to
  pick up the new threshold. After the test, the env var is removed and the module
  is reloaded to restore default state.
- The `should_warn()` method is tested implicitly by verifying it returns True the
  first time and False thereafter for the same tier.
