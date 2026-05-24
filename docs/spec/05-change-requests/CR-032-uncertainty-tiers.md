# CR-032 — Uncertainty Tiers and Capability Boundary

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: JARVIS interaction layer design (exploration-2026-05, Group 7A/7E)
**Implements**: FR-ORCH-026, FR-ORCH-027, NFR-ORCH-003

---

## Problem

Xochitl's responses currently have no calibrated uncertainty vocabulary. The system
prompt says "Never pretend certainty" but provides no framework, leaving the model to
infer appropriate hedging on its own. This produces:

1. **Over-confident responses** — general knowledge stated as fact when the model is
   extrapolating from training data (potentially stale or incorrect).
2. **Under-confident responses** — unnecessary hedging on stored facts the system
   actually has (e.g., task counts, user preferences, tool results).
3. **Vague capability claims** — the model doesn't have a clear list of what it can
   and cannot actually do, leading to hallucinated workarounds for capability gaps.
4. **No per-turn signal** — open-ended general-knowledge turns look identical to
   skill-matched turns from the model's perspective.

---

## Solution

### 1 — System prompt: `[UNCERTAINTY TIERS]` section

Adds a structured four-tier vocabulary to `prompts/system_xochitl.txt`:

| Tier | Condition | Marker language |
|---|---|---|
| **CERTAIN** | Direct tool result, stored preference, DB fact | "Your task count is 3." No hedge. |
| **CONFIDENT INFERENCE** | Reasoning from strong context clues | "Based on...", "It looks like..." |
| **UNCERTAIN** | Extrapolating, older training data, partial context | "I'm not certain, but...", "Worth verifying..." |
| **UNKNOWN / CAPABILITY BOUNDARY** | Cannot reliably answer | "I don't know.", "I'd need X to answer that." |

Rules: stored preferences/tool results → CERTAIN. Never dress TIER-3 knowledge in
TIER-0 language.

### 2 — System prompt: `[CAPABILITY BOUNDARY]` section

Adds a concise can/cannot list to `prompts/system_xochitl.txt` so the model has
explicit permission to say "I can't do that" rather than constructing unreliable
workarounds.

### 3 — Per-turn `[TURN CONTEXT]` injection

In `_agent_loop()`, when no skill scores above `_OPEN_ENDED_SCORE_THRESHOLD` (0.2),
append a one-line `[TURN CONTEXT]` note to the system prompt **for that turn only**:

```
[TURN CONTEXT: No specific task skill matched — open-ended or general knowledge
turn. Apply [UNCERTAINTY TIERS] vocabulary.]
```

This gives the model a per-turn signal distinguishing open-ended queries (where
calibrated hedging is most important) from skill-matched turns (where the tool
provides ground truth).

---

## Requirements

- **FR-ORCH-026** — The system prompt includes a `[UNCERTAINTY TIERS]` section
  defining CERTAIN / CONFIDENT INFERENCE / UNCERTAIN / UNKNOWN tiers with marker
  language examples and usage rules.
- **FR-ORCH-027** — The system prompt includes a `[CAPABILITY BOUNDARY]` section
  listing what Xochitl can and cannot reliably do.
- **NFR-ORCH-003** — When `top_score < 0.2` in `_agent_loop`, a `[TURN CONTEXT]`
  note is appended to the assembled system prompt for that turn only; no note is
  injected when a skill is matched at or above `_SKILL_INJECT_THRESHOLD`.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR032-001` | `prompts/system_xochitl.txt` contains an `[UNCERTAINTY TIERS]` section with all four tier definitions |
| `AC-CR032-002` | `prompts/system_xochitl.txt` contains a `[CAPABILITY BOUNDARY]` section |
| `AC-CR032-003` | When skill score < 0.2 in `_agent_loop`, the per-turn system prompt contains `[TURN CONTEXT]` |
| `AC-CR032-004` | When a skill scores ≥ 0.65 (matched), no `[TURN CONTEXT]` note is injected |
| `AC-CR032-005` | Smoke test confirms both sections exist in the system prompt file |

---

## Implementation tasks

- [x] Add `[UNCERTAINTY TIERS]` and `[CAPABILITY BOUNDARY]` to `prompts/system_xochitl.txt`
- [x] Add `_OPEN_ENDED_SCORE_THRESHOLD = 0.2` constant to `chat.py`
- [x] Add per-turn `[TURN CONTEXT]` injection in `_agent_loop()`
- [x] Write `docs/spec/08-test-specs/TEST-ORCH-002-uncertainty.md`
- [x] Update requirements registry and traceability matrix

---

## Design notes

- The per-turn injection uses the existing `top_score` from deterministic skill
  scoring — no extra LLM call is required.
- The `[TURN CONTEXT]` note is appended after the skill definition block (if any),
  ensuring it is the last instruction the model sees before the conversation.
- If a skill is matched (`top_score ≥ 0.65`), the skill's tool_definition block is
  already injected and the model has ground-truth data available; no uncertainty
  reminder is needed.
- If `0.2 ≤ top_score < 0.65`: borderline conversational turn — no injection (not
  clearly open-ended, not clearly skill-matched).
