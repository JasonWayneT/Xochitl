# TEST-EXPL-001 — Bounded Explorer

**Status**: implemented
**Date**: 2026-05-25
**Implements**: AC-CR023-001 through AC-CR023-006
**CR**: CR-023

---

## Scope

`ExplorerSkill` in `src/skills/explorer_skill.py`. Pure skill class with
deterministic `can_handle()` scoring and a mocked execution loop.
No real web requests, no real LLM calls, no DB access.

External dependencies mocked at the call boundary:
- `ExplorerSkill._form_subquestion` — patched via `patch.object`
- `ExplorerSkill._gather` — patched via `patch.object`
- `ExplorerSkill._synthesize` — patched via `patch.object` where needed

---

## Test cases

### AC-CR023-002 — `can_handle()` scoring

**Requirement**: FR-ORCH-039

| # | Input | Expected score | Rationale |
|---|---|---|---|
| 1 | `"Investigate the history of Python"` | ≥ 0.65 | "investigate" is an investigative keyword |
| 2 | `"research quantum computing trends"` | ≥ 0.65 | "research" is an investigative keyword |
| 3 | `"what's the weather today"` | 0.0 | Weather query — no investigative keywords |
| 4 | `"hello"` | 0.0 | No keywords at all |
| 5 | `"analyze the impact of streaming on latency"` | ≥ 0.65 | "analyze" is an investigative keyword |

**Edge cases**:
- Keyword match is case-insensitive (q = user_input.lower()).
- A score ≥ 0.65 satisfies `_SKILL_INJECT_THRESHOLD` even if < 0.85.

---

### AC-CR023-003 — Loop detection (NFR-ORCH-014)

**Requirement**: FR-ORCH-040, NFR-ORCH-014

| # | Setup | Expected |
|---|---|---|
| 1 | `_form_subquestion` always returns the same string | Hash repeats at step 2 → `_synthesize` called with notes containing "loop" |
| 2 | Gather call count | < `_MAX_STEPS` (loop stops before budget) |
| 3 | `_synthesize` called once | With `notes` kwarg containing "loop" |

**Implementation note**:
`_form_subquestion` is patched at the class level via `patch.object`. The first
call (step 1) and second call (step 2) return the same string, causing
`hashlib.md5(subq.lower().encode()).hexdigest()[:8]` to match on step 2.

---

### AC-CR023-004 — Budget exhaustion (NFR-ORCH-014)

**Requirement**: FR-ORCH-040, NFR-ORCH-014

| # | Setup | Expected |
|---|---|---|
| 1 | `_form_subquestion` returns unique string per step (no loop) | No loop detection fires |
| 2 | `_gather` returns 120-char snippet (medium quality) | Confidence ≈ 0.65 every step — never > 0.85, never < 0.30 |
| 3 | After `_MAX_STEPS` (6) steps | `_synthesize` called with `notes` containing "budget exhausted" |

**Confidence path** (with medium snippets):
```
step 3: depth=min(3×0.15, 0.45)=0.45, quality(120-char)=0.20, total=0.65
step 6: depth=0.45, quality=0.20, total=0.65  → neither stop nor escalate → budget
```

---

### AC-CR023-005 — High-confidence early stop (NFR-ORCH-015)

**Requirement**: FR-ORCH-040, NFR-ORCH-015

| # | Setup | Expected |
|---|---|---|
| 1 | `_gather` returns 420-char snippet each step | Quality bonuses push confidence > 0.85 at step 3 |
| 2 | `_synthesize` called | Without budget-exhausted note |
| 3 | Gather call count | < `_MAX_STEPS` (stopped early) |

**Confidence path** (with rich snippets, 420 chars):
```
step 1: depth=0.15, quality(>100=+0.20, >250=+0.15, >400=+0.15)=0.50, total=0.65
step 2: depth=0.30, quality=0.50, total=0.80  → not > 0.85
step 3: depth=0.45, quality=0.50, total=0.95  → > 0.85 → STOP
```

---

### AC-CR023-006 — Registration in `_builtin_skills`

**Requirement**: FR-ORCH-041

| # | Approach | Expected |
|---|---|---|
| 1 | `XochitlChat.__new__(XochitlChat)` | Returns uninitialised instance without triggering `__init__` |
| 2 | Set `chat._builtin_skills = None`, `chat._skills = None`, `chat.current_project = None` | Attributes safe for `skills` property access |
| 3 | Inspect `chat.skills` | Contains at least one `ExplorerSkill` instance |

---

## Implementation notes

- All tests are in `smoke_test.py` under the `# ── CR-023` section.
- `_form_subquestion` and `_gather` are patched via `patch.object(ExplorerSkill, ...)` to
  keep tests isolated from the router and WebLookupSkill (NFR-DEV-005).
- `_synthesize` is replaced with a side-effect function that records the `notes` kwarg,
  allowing assertions on what triggered the stop without exercising the real router.
- The registration test uses `__new__` to bypass `XochitlChat.__init__` (no DB, no threads).

---

## Traceability

| Test function | Acceptance criterion | Requirement |
|---|---|---|
| `t_explorer_skill_can_handle_scoring` | AC-CR023-002 | FR-ORCH-039 |
| `t_explorer_skill_loop_detection` | AC-CR023-003 | FR-ORCH-040, NFR-ORCH-014 |
| `t_explorer_skill_budget_exhaustion` | AC-CR023-004 | FR-ORCH-040, NFR-ORCH-014 |
| `t_explorer_skill_high_confidence_stops_early` | AC-CR023-005 | FR-ORCH-040, NFR-ORCH-015 |
| `t_explorer_skill_registration` | AC-CR023-006 | FR-ORCH-041 |
