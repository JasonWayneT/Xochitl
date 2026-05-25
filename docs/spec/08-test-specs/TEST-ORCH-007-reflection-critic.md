# TEST-ORCH-007 — Reflection / Critic

**Requirement**: FR-ORCH-037, FR-ORCH-038, NFR-ORCH-012, NFR-ORCH-013
**CR**: CR-019
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR019-001` | `TurnCritic` defined in `src/critic.py` with callable `should_critique()` and `critique()` | `smoke_test.py` — `t_critic_class_defined` | implemented |
| `AC-CR019-002` | `should_critique()` returns `True` for all three trigger conditions independently | `smoke_test.py` — `t_critic_should_critique_triggers` | implemented |
| `AC-CR019-003` | `should_critique()` returns `False` for high-score, no-tool, non-hedgy response | `smoke_test.py` — `t_critic_no_critique_high_confidence` | implemented |
| `AC-CR019-004` | `_parse_critic_response()` maps OK / CORRECTABLE / AMBIGUOUS prefixes to correct verdicts | `smoke_test.py` — `t_parse_critic_response_verdicts` | implemented |
| `AC-CR019-005` | `chat.py` defines `_maybe_critique` and references `_MAX_CRITIC_ITERATIONS` (source inspection) | `smoke_test.py` — `t_maybe_critique_in_chat` | implemented |

## Notes

- NFR-ORCH-012 (local model, capped iterations) verified by source inspection:
  `critique()` calls `force_route="simple_qa"`; `_maybe_critique` loops over
  `range(_MAX_CRITIC_ITERATIONS)`.
- NFR-ORCH-013 (no streaming, no crash) verified by source inspection:
  streaming path returns before `_maybe_critique` is reached;
  `_maybe_critique` wraps the entire block in `try/except Exception`.
- The convergence guard (identical response → escalate to AMBIGUOUS) prevents
  the anti-pattern of reflexive re-routing when output hasn't changed.
