# CR-034 — Implicit Preference Learning

**Status**: implemented
**Date**: 2026-05-25
**Priority**: 12 (Group 7C — Relationship Building)
**Source**: `docs/planning/exploration-2026-05.md` item #29 (C10)

---

## Problem statement

Xochitl only learns from preferences the user states explicitly. If Jason
types "keep it short" once, that preference is stored. But if he consistently
rephrases a question because the first framing didn't land, or if a preference
silently fades (he stopped using a feature 6 sessions ago), nothing updates.
The result is a system that feels like it never grows more attuned — every
session is session 1 from a preference perspective.

The planning document (#29 C10) defines four safe implicit signal classes:
1. **Rephrased query** — user follows up with a reworded version of the same question
2. Ignored suggestion (skipped — requires suggestion-tracking infrastructure)
3. Reformulated output (skipped — requires clipboard/editor integration)
4. Timing (skipped — requires inter-turn timing UI layer)

Signals 2–4 require infrastructure that does not exist. This CR implements
**Signal 1 (rephrased query)** plus the **confidence decay + pruning** mechanism
that prevents stale implicit preferences from persisting indefinitely.

---

## Requirements

### Functional

| ID | Requirement |
|---|---|
| `FR-PREF-001` | `is_rephrased_query(prev: str, curr: str) -> bool` — pure heuristic; returns `True` when (a) the strings are not identical AND (b) shared non-stopword count ≥ `_REPHRASE_MIN_SHARED_WORDS (2)` AND (c) Jaccard similarity on all tokens ≥ `_REPHRASE_SIMILARITY_THRESHOLD (0.30)` |
| `FR-PREF-002` | `BackgroundReview` tracks the previous user input (`_prev_user_input`); after each turn, if `is_rephrased_query(prev, curr)` returns `True`, stores an implicit preference fact to `memory_facts` with `category="preference"`, `source="implicit_rephrase_detection"`, `confidence=0.65` |
| `FR-PREF-003` | `decay_and_prune(conn) -> tuple[int, int]` applies `confidence *= _CONFIDENCE_DECAY_RATE (0.95)` to all preferences with `source="implicit_preference"`; then deletes rows where `confidence < _PRUNE_THRESHOLD (0.30)`; called once at session start from `XochitlChat.start()`; returns `(decayed_count, pruned_count)` |

### Non-functional

| ID | Requirement |
|---|---|
| `NFR-PREF-001` | `is_rephrased_query` is a pure function — no LLM call, no DB access, no side effects; `decay_and_prune` must not raise (wrapped in try/except at call site); rephrase storage must not raise (wrapped in `_maybe_store_rephrase`) |

---

## Acceptance criteria

| ID | Scenario | Expected |
|---|---|---|
| `AC-CR034-001` | `is_rephrased_query("What tasks are in my Notion queue?", "Which Notion tasks are pending?")` | `True` (2 shared non-stopwords, Jaccard ≥ 0.30) |
| `AC-CR034-002` | `is_rephrased_query("What tasks are in my Notion queue?", "What is the weather today?")` | `False` (different topics — shared non-stopwords = 0) |
| `AC-CR034-003` | `is_rephrased_query("Investigate Python", "Investigate Python")` | `False` (identical strings → no rephrase signal) |
| `AC-CR034-004` | `decay_and_prune` on implicit preference with `confidence=0.80` | `confidence` becomes `0.80 * 0.95 = 0.76`; row not pruned |
| `AC-CR034-005` | `decay_and_prune` on implicit preference with `confidence=0.29` (below threshold) | Row deleted; `pruned_count ≥ 1` |
| `AC-CR034-006` | `python smoke_test.py` | 114 passed, 0 failed |

---

## Design

### `is_rephrased_query` algorithm

```
1. Identical → return False
2. Tokenize both strings to word sets (regex \b\w+\b, lowercased)
3. content_set = tokens - _STOPWORDS
4. shared_content = prev_content ∩ curr_content
5. If len(shared_content) < 2 → return False
6. jaccard = |prev_tokens ∩ curr_tokens| / |prev_tokens ∪ curr_tokens|
7. Return jaccard ≥ 0.30
```

### Confidence decay

Only implicit preferences (`source="implicit_preference"`) are decayed.
Explicit user preferences (`source="user_stated"`, `source="correction_pattern"`)
are never decayed — they represent direct user intent.

```
UPDATE preferences
SET confidence = confidence * 0.95
WHERE source = 'implicit_preference' AND confidence >= 0.30

DELETE FROM preferences
WHERE source = 'implicit_preference' AND confidence < 0.30
```

### Rephrase storage

When detected in `BackgroundReview._maybe_store_rephrase()`:
```
upsert_memory_fact(conn,
    fact="User rephrased '{prev[:60]}' as '{curr[:60]}' — second framing preferred.",
    category="preference",
    confidence=0.65,
    source="implicit_rephrase_detection",
    project=project,
)
```

This is stored as a `memory_facts` entry (not a `preferences` row) because it
is a short-lived behavioral observation, not a durable preference. It surfaces
in `BackgroundReview`'s normal KB pipeline and may escalate to the preferences
table via the correction-escalation mechanism if the same rephrase recurs.

---

## Implementation tasks

- [x] Write `CR-034-implicit-preference-learning.md`
- [x] `src/preference_learning.py` (NEW) — `is_rephrased_query`, `decay_and_prune`, `_STOPWORDS`
- [x] `src/background_review.py` (UPDATE) — `_prev_user_input` field, `_maybe_store_rephrase()`, rephrase hook in `_process()`
- [x] `src/chat.py` (UPDATE) — `decay_and_prune` call at session start in `start()`
- [x] `docs/spec/02-requirements-registry.md` — FR-PREF-001, FR-PREF-002, FR-PREF-003, NFR-PREF-001
- [x] `docs/spec/08-test-specs/TEST-PREF-001-implicit-learning.md`
- [x] `smoke_test.py` — 5 tests (AC-CR034-001 through AC-CR034-005)
- [x] `docs/spec/06-traceability/traceability-matrix.md`
