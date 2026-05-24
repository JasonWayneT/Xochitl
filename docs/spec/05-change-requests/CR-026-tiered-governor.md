# CR-026 — Session Tiered Governor

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: Cost and safety review of long-running chat sessions
**Implements**: FR-ORCH-025, NFR-PERF-011

---

## Problem

Xochitl's chat sessions have no concept of a token budget. A long session — or a
session involving repeated cloud LLM calls — can silently accumulate unbounded cloud
spend with no user feedback or routing restriction. There is no mechanism for:

1. Alerting the user when the session is consuming significant resources.
2. Progressively restricting routing to the local model before costs escalate.
3. Refusing further LLM calls when a hard limit is exceeded.

---

## Solution

Introduce `src/governor.py` — a `SessionGovernor` class that tracks estimated token
spend across all LLM turns in a session and exposes a tiered routing constraint.

**Tier model (ascending restriction):**

| Tier | Condition | Effect |
|---|---|---|
| `full` | Default (below PREFER_LOCAL threshold) | Normal routing; cloud allowed |
| `prefer_local` | `est_tokens ≥ XCH_PREFER_LOCAL_TOKENS` (default 20 000) | One-time user warning; routing unchanged |
| `local_only` | `est_tokens ≥ XCH_LOCAL_ONLY_TOKENS` (default 40 000) | One-time warning; `force_route="general"` applied — cloud calls blocked |
| `hard_stop` | `est_tokens ≥ XCH_HARD_STOP_TOKENS` (default 80 000) | No LLM call made; canned budget message returned immediately |

**Token estimation:** `len(text) // 4` (1 token ≈ 4 characters; OpenAI rule of thumb).
This is a rough guide, not an exact meter — see ADR-004.

**Integration in `chat.py`:**
1. `XochitlChat.__init__` creates `self._governor = SessionGovernor()`.
2. `start()` checks the tier *before* spinning the worker thread:
   - `hard_stop` → print budget message and `continue` (no LLM call).
   - `prefer_local` / `local_only` → print one-time warning.
3. `_agent_loop()` applies `governor.force_route()` as the `force_route` override
   before calling `router.route()` and `router.route_stream()`.
4. `start()` calls `governor.record_turn(user_input, response)` after each completed
   turn to accumulate estimated usage.
5. `/budget` slash command shows current tier, estimated tokens, and thresholds.

---

## Configuration (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `XCH_PREFER_LOCAL_TOKENS` | `20000` | Est. tokens before local-prefer warning |
| `XCH_LOCAL_ONLY_TOKENS` | `40000` | Est. tokens before local-only enforcement |
| `XCH_HARD_STOP_TOKENS` | `80000` | Est. tokens before hard stop |

---

## Requirements

- **FR-ORCH-025** — Before each LLM turn the chat session evaluates the
  `SessionGovernor` and applies the current tier's routing constraint.
- **NFR-PERF-011** — Token estimation uses a character-count approximation
  (`chars / 4`); the governor is a rough budget guide, not a billing meter.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR026-001` | A freshly created `SessionGovernor` reports tier `full` |
| `AC-CR026-002` | After `record_turn` accumulates ≥ 20 000 estimated tokens, tier is `prefer_local` |
| `AC-CR026-003` | After ≥ 40 000 estimated tokens, tier is `local_only`; `force_route()` returns `"general"` |
| `AC-CR026-004` | After ≥ 80 000 estimated tokens, tier is `hard_stop`; `start()` returns canned message without an LLM call |
| `AC-CR026-005` | `XCH_LOCAL_ONLY_TOKENS=1000` env var lowers the LOCAL_ONLY threshold to 1 000 |
| `AC-CR026-006` | `/budget` slash command prints current tier, estimated token count, and thresholds |
| `AC-CR026-007` | Tier warning messages appear at most once per tier transition per session |

---

## Implementation tasks

- [x] Create `src/governor.py` (`SessionGovernor`, `Tier`, estimation, `force_route`)
- [x] Integrate into `src/chat.py` (`__init__`, `start`, `_agent_loop`, `/budget`)
- [x] Write `docs/spec/08-test-specs/TEST-ORCH-001-governor.md`
- [x] Update requirements registry and traceability matrix

---

## Known limitations

- Token estimation is approximate (chars/4). The true token count depends on the
  tokenizer and model. The governor may over- or under-count by 15–30% for typical
  English text. Use it as a soft guard, not a billing meter.
- The `record_turn` call in `start()` records only `user_input` and the final
  `response` text. It does not count the system prompt or injected context that is
  sent on every turn (typically 500–2 000 tokens). Set thresholds conservatively.
- Skill execution results injected into history (role=tool turns) are not counted.
