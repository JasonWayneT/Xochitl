# CR-019 — Reflection / Critic

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #11 (Group 5)
**Implements**: FR-ORCH-037, FR-ORCH-038, NFR-ORCH-012, NFR-ORCH-013

---

## Problem

`BackgroundReview` does passive observation after each turn but performs no
active post-execution quality check. There is no mechanism to catch:

- Skill outputs that did not actually answer the user's question
- Hedgy or uncertain responses that should carry an explicit caveat
- Near-miss routing turns where the response may be partially wrong

Without a lightweight self-critic, Xochitl can silently return degraded answers
on high-uncertainty or multi-step turns with no signal to the user.

---

## Solution

### New: `src/critic.py`

`TurnCritic` provides structured post-execution reflection on non-streaming turns.

**Trigger conditions** — critique fires when any one is true:
| Condition | Rationale |
|---|---|
| `tool_calls_made=True` | Skill was executed — did the output actually answer the goal? |
| `0.20 ≤ top_score < 0.65` | Near-miss routing — model may have guessed the wrong approach |
| Response matches `_HEDGING_PATTERNS` | LLM signalled its own uncertainty |

**Critic prompt** — issues a structured one-line verdict via `force_route="simple_qa"` (local model, fast):

```
Verdict:
  OK: <brief reason>
  CORRECTABLE: <specific error or missing step, ≤20 words>
  AMBIGUOUS: <brief reason, ≤15 words>
```

**Verdict outcomes**:
| Verdict | Action |
|---|---|
| `OK` | Return response unchanged |
| `CORRECTABLE` | Retry router with `[CRITIC NOTE: <note>]` appended to system prompt; cap at `_MAX_CRITIC_ITERATIONS=2` |
| `AMBIGUOUS` | Append `_Fíjate — <note>_` caveat to response and stop |

**Convergence guard**: if a CORRECTABLE retry produces the same response text, bail with an AMBIGUOUS caveat rather than looping.

### Updated: `src/chat.py`

Two changes to `_agent_loop()`:

1. **`_tool_calls_made` flag** — set to `True` after a skill executes; used by `TurnCritic.should_critique()`.
2. **Collect `_final` instead of early-returning** — the post-skill-execution branches now assign to `_final` rather than returning immediately, so the critic can run on all non-streaming paths.

New private method: `XochitlChat._maybe_critique(response, goal, top_score, tool_calls_made, messages, system_prompt, force) -> str`.

Critique never fires on streaming turns (streaming path returns before the critic block). Entire block is wrapped in `try/except` — must never crash the main loop.

---

## Requirements

- **FR-ORCH-037** — `TurnCritic.should_critique()` returns `True` when: (a) a skill was executed, (b) the skill routing score was in the near-miss zone (0.20–0.65), or (c) the response contains hedging language. Never fires on streaming turns.
- **FR-ORCH-038** — `TurnCritic.critique()` returns `CritiqueResult` with verdict in `{"ok", "correctable", "ambiguous"}`. CORRECTABLE triggers a correction retry loop capped at `_MAX_CRITIC_ITERATIONS=2`. AMBIGUOUS appends a `_Fíjate —_` caveat.
- **NFR-ORCH-012** — Critic call uses `force_route="simple_qa"` (local model). At most `_MAX_CRITIC_ITERATIONS` (2) extra LLM calls per turn when critique is triggered. Total overhead: 1 critic call + up to 2 correction calls.
- **NFR-ORCH-013** — Critique never runs on streaming turns. Entire `_maybe_critique()` call is wrapped in `try/except Exception` and silently degrades to returning the original response on any failure.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR019-001` | `src/critic.py` defines `TurnCritic` with callable `should_critique()` and `critique()` |
| `AC-CR019-002` | `should_critique()` returns `True` for all three trigger conditions independently |
| `AC-CR019-003` | `should_critique()` returns `False` for high-score (≥0.65), no-tool, no-hedging response |
| `AC-CR019-004` | `_parse_critic_response()` correctly maps OK / CORRECTABLE / AMBIGUOUS prefixes to verdicts |
| `AC-CR019-005` | `chat.py` defines `_maybe_critique` and references `_MAX_CRITIC_ITERATIONS` (source inspection) |

---

## Implementation tasks

- [x] Write `CR-019-reflection-critic.md`
- [x] Create `src/critic.py`
- [x] Update `src/chat.py` — `_tool_calls_made`, collect `_final`, add `_maybe_critique`
- [x] Write `docs/spec/08-test-specs/TEST-ORCH-007-reflection-critic.md`
- [x] Update requirements registry
- [x] Update traceability matrix
- [x] Add smoke tests; run full suite

---

## Design notes

- Critique is **opt-in by trigger** — trivial low-stakes turns (complete miss zone,
  no tool calls, no hedging) pass through with zero overhead. The latency cost is
  only paid when the signal suggests quality risk.
- **Streaming exclusion** is intentional: streaming turns are generally lower-stakes
  (no skill schema injected) and retraction of already-printed tokens is not possible.
- **CORRECTABLE convergence guard**: if the correction retry produces identical text,
  escalate to AMBIGUOUS caveat instead of looping. Prevents the anti-pattern of
  reflexive re-routing when the output hasn't changed.
- **Local model only** (`force_route="simple_qa"`): one-line structured response is
  well within local model capabilities. Cloud escalation would double latency and cost.
- `_MAX_CRITIC_ITERATIONS=2` matches the planning doc cap ("2 iterations before
  escalating to user").
- Ref: arxiv 2405.06682 — Self-Reflection in LLM Agents
