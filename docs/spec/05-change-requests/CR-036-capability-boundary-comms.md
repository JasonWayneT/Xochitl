# CR-036 — Capability Boundary Communication

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #36 (Group 7E)
**Implements**: FR-ORCH-034, NFR-ORCH-009

---

## Problem

When a user request does not match any skill, Xochitl falls through to a generic
LLM response with no per-turn guidance about what is or isn't possible. The model
may attempt a reduced version of the task silently, or hallucinate capability, rather
than stating specifically what is missing and offering a forward path.

The existing `[CAPABILITY BOUNDARY]` system prompt section describes what Xochitl
can and cannot do in general terms but provides no per-turn, request-specific signal.

Two failure zones exist in the skill scoring pipeline:

1. **Near-miss** (`0.20 ≤ score < 0.65`): A skill partially matched but did not
   cross the injection threshold. The model receives no information about which skill
   came close or what it covers.
2. **Complete miss** (`score < 0.20`): No skill matched. The model only gets the
   generic open-ended [TURN CONTEXT] note from CR-032.

---

## Solution

Improve the per-turn `[TURN CONTEXT]` injection in `_agent_loop()` to give the model
actionable boundary guidance for both failure zones:

**Near-miss zone** (new) — when `_OPEN_ENDED_SCORE_THRESHOLD ≤ top_score < _SKILL_INJECT_THRESHOLD`:
- Inject the matched skill's name and a brief note that it partially matched
- Direct the model to state what the skill can cover vs. what it cannot
- Prohibit silently delivering a reduced version

**Complete-miss zone** (improved) — when `top_score < _OPEN_ENDED_SCORE_THRESHOLD`:
- Upgrade the generic "open-ended turn" note to an explicit capability-boundary note
- Direct the model to consult `[CAPABILITY BOUNDARY]` and offer a specific forward path

Both zones also retain the uncertainty tiers reminder.

No new files. No new modules. Targeted improvement to two `[TURN CONTEXT]` strings
in `chat.py`.

---

## Requirements

- **FR-ORCH-034** — `_agent_loop()` distinguishes three skill-score zones and
  injects differentiated `[TURN CONTEXT]` guidance:
  - **Skill matched** (`score ≥ 0.65`): skill schema injected, no extra [TURN CONTEXT] note
  - **Near-miss** (`0.20 ≤ score < 0.65`): near-miss note with skill name; prohibits silent
    capability reduction
  - **Complete miss** (`score < 0.20`): capability boundary note; directs model to offer a
    specific forward path per `[CAPABILITY BOUNDARY]`
- **NFR-ORCH-009** — The near-miss and complete-miss [TURN CONTEXT] notes are injected
  without any additional LLM call; the existing skill scoring pipeline provides all needed
  information.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR036-001` | When `top_score < 0.20`, the assembled system prompt contains `[CAPABILITY BOUNDARY]` reference in the [TURN CONTEXT] block |
| `AC-CR036-002` | When `0.20 ≤ top_score < 0.65`, the assembled system prompt contains the matched skill name and "near-miss" guidance in the [TURN CONTEXT] block |
| `AC-CR036-003` | When `top_score ≥ 0.65`, no near-miss or boundary [TURN CONTEXT] is injected (skill schema handles it) |

---

## Implementation tasks

- [x] Write `CR-036-capability-boundary-comms.md`
- [x] Update `src/chat.py` — three-zone [TURN CONTEXT] logic in `_agent_loop()`
- [x] Update requirements registry with FR-ORCH-034, NFR-ORCH-009
- [x] Update traceability matrix
- [x] Add smoke tests; run full suite

---

## Design notes

- The near-miss zone (`0.20–0.65`) is the critical gap. Users asking "can you deploy
  my code?" score 0.3 on CodeSkill but don't cross the injection threshold — without
  this fix the model gets no skill context at all.
- The skill name used in the near-miss note comes from `type(top_skill).__name__`
  with "Skill" stripped — readable without the full schema.
- Preserving the uncertainty-tiers reminder in both new contexts keeps CR-032 behavior
  intact for all non-skill turns.
- No change to the `_SKILL_INJECT_THRESHOLD` or `_OPEN_ENDED_SCORE_THRESHOLD` values —
  this CR only improves what's injected in the zones between them.
