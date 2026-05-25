# CR-023 — Bounded Explorer

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 10 (Group 6 — JARVIS Runtime)
**Source**: `docs/planning/exploration-2026-05.md` item #15

---

## Problem statement

Xochitl can execute a single web lookup or skill call, but has no controlled
multi-step investigation loop. When a user asks a complex research question
the system does one search and stops — it cannot chain evidence, evaluate
whether the answer is complete, or decide to look deeper. This makes
Xochitl feel capable of *searching* but not *investigating*.

The `$47K LangChain Loop` failure (Nov 2025) established the anti-pattern:
an unbounded agent loop with no step budget, no convergence detection, and
no escalation path. CR-023 implements the corrective pattern explicitly.

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| `FR-ORCH-039` | `ExplorerSkill.can_handle()` returns ≥ 0.85 for queries containing investigative keywords ("investigate", "research", "explore", "analyze", "dig into", "look into", etc.); returns 0.70 for multi-hop indicators; returns 0.0 for plain lookup queries |
| `FR-ORCH-040` | `ExplorerSkill.execute()` runs a bounded multi-step investigation loop: (1) form subquestion, (2) convergence check, (3) gather evidence via `WebLookupSkill`, (4) score heuristic confidence (no LLM call), (5) stop if confidence > 0.85, (6) escalate if confidence < 0.30 at step ≥ 3, (7) synthesize at budget exhaustion |
| `FR-ORCH-041` | `ExplorerSkill` is registered in `XochitlChat._builtin_skills` and appears in the `skills` property alongside all other built-in skills |

### Non-functional

| ID | Requirement |
|---|---|
| `NFR-ORCH-014` | Hard step budget is `_MAX_STEPS = 6` (named constant, not a magic number). Repeat action-hash = loop detected → stop immediately (before budget). On budget exhaustion, `_synthesize()` is called with a structured `notes` string containing "Step budget exhausted". |
| `NFR-ORCH-015` | Confidence evaluation is a pure heuristic function — no LLM call per step. Sub-question generation (steps 2+) uses `force_route="simple_qa"` (local model). Final synthesis uses `force_route="general"`. |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR023-001` | `from src.skills.explorer_skill import ExplorerSkill` | Importable; `can_handle()`, `execute()`, `suggest()`, `tool_definition()` all callable |
| `AC-CR023-002` | `ExplorerSkill().can_handle("investigate the history of Python", {})` | Returns ≥ 0.65 (above `_SKILL_INJECT_THRESHOLD`) |
| `AC-CR023-003` | `execute()` with `_form_subquestion` patched to always return the same string | Loop detected at step 2; `_synthesize()` called with notes containing "loop"; total gather calls < `_MAX_STEPS` |
| `AC-CR023-004` | `execute()` with medium-quality evidence (confidence stays 0.30–0.85 through all steps) | Budget exhausted after `_MAX_STEPS` steps; `_synthesize()` called with notes containing "budget exhausted" |
| `AC-CR023-005` | `execute()` with rich evidence (3 steps at 420+ chars each → confidence > 0.85) | Stops before `_MAX_STEPS`; `_synthesize()` called without budget note |
| `AC-CR023-006` | `XochitlChat.__new__(XochitlChat)` with `_builtin_skills=None`, `_skills=None`, `current_project=None` | `skills` list contains an `ExplorerSkill` instance |
| `AC-CR023-007` | `python smoke_test.py` | 103 passed, 0 failed |

---

## Design notes

### Step budget and constants

```python
_MAX_STEPS: int = 6               # between 5 (simple) and 12 (research) from planning doc
_CONFIDENCE_HIGH: float = 0.85   # stop and synthesize
_CONFIDENCE_LOW: float = 0.30    # escalate if below this at step ≥ 3
_EARLY_CHECK_STEP: int = 3       # first step where low-confidence can trigger escalation
```

### Convergence detection

Each subquestion is hashed (`hashlib.md5(subquestion.lower().encode()).hexdigest()[:8]`).
If the same hash appears twice the loop is a cycle — stop immediately and synthesize
with a loop-detected note. This prevents the $47K loop failure class.

### Confidence heuristic (no LLM call — NFR-ORCH-015)

```
depth_score = min(len(evidence) * 0.15, 0.45)   # max 0.45 from source count
quality_score based on latest snippet length:
  len > 100 → +0.20
  len > 250 → +0.15
  len > 400 → +0.15
penalty: any low-signal phrase in total evidence → −0.20
result = max(0.0, min(1.0, depth_score + quality_score))
```

With this formula:
- 3 × rich snippets (>400 chars each) → ~0.95 → early stop ✓
- 6 × medium snippets (120 chars each) → ~0.65 → budget exhaustion ✓
- 3 × failure snippets ("couldn't find…") → ~0.25 → escalation ✓

### Source routing (NFR-ORCH-015)

| Call | Route |
|---|---|
| Sub-question generation (steps 2+) | `force_route="simple_qa"` (local model, cheap) |
| Evidence gathering | `WebLookupSkill.execute()` (existing SSRF-protected path) |
| Final synthesis | `force_route="general"` (cloud model for quality) |

### Registration

`ExplorerSkill()` appended to the existing `_builtin_skills` list in
`XochitlChat._get_skills()`. Scoring at `can_handle()` time ensures it
only surfaces when the query is genuinely investigative — it does not
interfere with single-step skill routing.

---

## Implementation tasks

- [x] `src/skills/explorer_skill.py` — `ExplorerSkill` class with `can_handle`, `execute`, `_form_subquestion`, `_gather`, `_score_confidence`, `_synthesize`, `_escalate`
- [x] `src/chat.py` — add `ExplorerSkill` to `_builtin_skills`
- [x] `docs/spec/02-requirements-registry.md` — FR-ORCH-039, FR-ORCH-040, FR-ORCH-041, NFR-ORCH-014, NFR-ORCH-015
- [x] `docs/spec/08-test-specs/TEST-EXPL-001-bounded-explorer.md`
- [x] `smoke_test.py` — 5 tests (AC-CR023-002 through AC-CR023-006)
- [x] `docs/spec/06-traceability/traceability-matrix.md` — 5 new rows
