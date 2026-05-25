# CR-025 — Response Mode Switching

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #17 (Group 6)
**Implements**: FR-ORCH-032, FR-ORCH-033, NFR-ORCH-007, NFR-ORCH-008

---

## Problem

Xochitl uses one voice for all outputs. A command like "sync" and a question like
"what's my project status?" receive stylistically identical responses even though one
calls for crisp imperative output and the other calls for structured analysis. The
system prompt is static per session — there is no mechanism to signal to the model
that this turn is an execution command vs. an information request.

---

## Solution

Three named response modes injected as system prompt sections per turn.

### Modes

| Mode | When | System prompt block | Character |
|---|---|---|---|
| `conversational` | Default | None (Xochitl's natural voice) | Warm, exploratory, full persona |
| `operator` | Command verbs detected | `[RESPONSE MODE: OPERATOR]` block | Concise, imperative, action-first, no hedging |
| `report` | Report/summary keywords detected | `[RESPONSE MODE: REPORT]` block | Structured, headers, no filler |

### Architecture

1. **`src/response_mode.py`** — new module:
   - Constants: `MODE_CONVERSATIONAL`, `MODE_OPERATOR`, `MODE_REPORT`
   - `_OPERATOR_MODE_BLOCK`, `_REPORT_MODE_BLOCK` — prompt text injected per turn
   - `infer_mode(user_input: str) -> str` — heuristic inference, no LLM call
   - `mode_block(mode: str) -> str` — returns the prompt block for a given mode

2. **`src/context_manager.py`** — `assemble_system_prompt(mode: str = "conversational") -> str`:
   - Appends `mode_block(mode)` to the assembled prompt for non-conversational modes
   - Mode block is treated as part of the turn context — appended after skills hint

3. **`src/chat.py`** — `XochitlChat`:
   - `self._current_mode: str` — tracks mode between turns for transition detection
   - `_agent_loop()` calls `infer_mode(user_input)` before `assemble_system_prompt()`
   - When mode changes, prints a brief dim transition line before the response

### Mode inference heuristics (NFR-ORCH-008)

`infer_mode()` uses two patterns — no second LLM call:

**OPERATOR** — short imperative utterances (≤ 15 words) starting with a command verb:
`sync`, `run`, `do`, `execute`, `start`, `stop`, `create`, `delete`, `add`, `remove`,
`update`, `push`, `pull`, `mark`, `complete`, `build`, `generate`, `init`, `reset`,
`refresh`, `check`.

Or utterances starting with `!` (explicit operator trigger).

**REPORT** — utterances containing report/structure keywords:
`report`, `summary`, `summarize`, `overview`, `breakdown`, `status report`,
`list all`, `list my`, `show me a report`, `give me a`.

**CONVERSATIONAL** — everything else (default).

---

## Requirements

- **FR-ORCH-032** — `src/response_mode.py` defines three modes (`conversational`,
  `operator`, `report`) and `infer_mode(user_input: str) -> str` that returns the
  appropriate mode for a given utterance.
- **FR-ORCH-033** — `ContextManager.assemble_system_prompt(mode)` appends the
  mode-specific prompt block for `operator` and `report` modes; `conversational`
  mode adds no extra block (Xochitl's default voice).
- **NFR-ORCH-007** — When the response mode changes between consecutive turns,
  `XochitlChat` prints a single dim transition line before the response:
  `"→ operator mode"` or `"→ report mode"` or `"→ conversational mode"`.
- **NFR-ORCH-008** — Mode inference is a regex/keyword heuristic — no second LLM
  call. Inference runs synchronously before the main LLM call.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR025-001` | `src/response_mode.py` defines `MODE_CONVERSATIONAL`, `MODE_OPERATOR`, `MODE_REPORT` |
| `AC-CR025-002` | `infer_mode("sync my tasks")` returns `"operator"` |
| `AC-CR025-003` | `infer_mode("give me a report on my projects")` returns `"report"` |
| `AC-CR025-004` | `infer_mode("what's the weather like?")` returns `"conversational"` |
| `AC-CR025-005` | `assemble_system_prompt(mode="operator")` output contains `[RESPONSE MODE: OPERATOR]` |
| `AC-CR025-006` | `assemble_system_prompt(mode="conversational")` output does NOT contain `[RESPONSE MODE:` |

---

## Implementation tasks

- [x] Write `CR-025-response-modes.md`
- [x] Create `src/response_mode.py`
- [x] Update `src/context_manager.py` — `assemble_system_prompt(mode=...)` parameter
- [x] Update `src/chat.py` — `_current_mode`, `infer_mode()` call, transition announcement
- [x] Write `docs/spec/08-test-specs/TEST-ORCH-005-response-modes.md`
- [x] Update requirements registry with FR-ORCH-032, FR-ORCH-033, NFR-ORCH-007, NFR-ORCH-008
- [x] Update traceability matrix
- [x] Add smoke tests; run full suite

---

## Design notes

- The `conversational` block is intentionally empty (no injected text). Xochitl's
  default persona is already conversational. Injecting a "you are in conversational
  mode" block would add tokens with no behavioral benefit.
- `infer_mode()` errs toward `conversational` on ambiguous input — false negatives
  (failing to detect operator/report) are less disruptive than false positives.
- Mode is per-request, not per-session. The mode for each turn is re-inferred from
  the current utterance — prior mode is only tracked for transition announcements.
- The transition announcement prints before the LLM response, giving the user a
  frame before they read the output. It is a single line and does not require any
  response from the user.
- `assemble_system_prompt()` signature remains backward-compatible: `mode` is a
  keyword argument with a default — all existing call sites work unchanged.
