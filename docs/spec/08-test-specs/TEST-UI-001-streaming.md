# TEST-UI-001 — LLM Token Streaming

**Requirement**: FR-UI-005
**CR**: CR-031
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR031-002` | Skill path uses non-streaming route when `top_score ≥ 0.65` | `chat._detect_current_project` and `chat._check_specs_exist` used in smoke harness; skill scoring exercised | implemented |
| `AC-CR031-008` | All 27 existing smoke tests pass after streaming changes | `python smoke_test.py` → 27 passed 0 failed | implemented |

## Manual verification (run once per provider change)

| Test ID | Steps | Expected | Status |
|---|---|---|---|
| `AC-CR031-001` | Run `xochitl chat`, send "what's the capital of Japan?" | Tokens appear progressively, not as a batch dump | verified |
| `AC-CR031-003` | Set `CLOUD_PROVIDER=gemini`, repeat above | Gemini tokens stream progressively | pending live test |
| `AC-CR031-004` | Ensure Ollama running, set local route, repeat above | Ollama tokens stream progressively | pending live test |
| `AC-CR031-005` | Check terminal — no double-print of same response | Response appears once | verified |
| `AC-CR031-006` | Simulate empty stream (kill Ollama mid-stream) | Falls back to non-streaming `route()` path | pending |
| `AC-CR031-007` | Watch spinner during a conversational turn | Spinner visible until first token, then clears | verified |

## Notes

- Streaming path only activates when `top_score < 0.65` (no skill schema injected). Skill-matched turns intentionally use the non-streaming path — verified by existing skill dispatch smoke tests.
- `_last_response_streamed` flag reset happens at the start of each turn in `start()`, so a crash mid-stream does not affect the next turn.
