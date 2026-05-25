# TEST-PREF-001 — Implicit Preference Learning

**Status**: implemented
**CR**: CR-034
**Requirements covered**: FR-PREF-001, FR-PREF-002, FR-PREF-003, NFR-PREF-001

---

## Scope

Unit tests for `src/preference_learning.py` (pure heuristics, no LLM). Covers:
- `is_rephrased_query()` — word-overlap rephrase detector
- `decay_and_prune()` — confidence decay and below-threshold pruning

`BackgroundReview._maybe_store_rephrase()` is tested via mocking in
`smoke_test.py` alongside the heuristic. No live DB or LLM calls are used.

---

## Test cases

### TC-PREF-001-001 — Rephrase detected (AC-CR034-001)

**Method**: `is_rephrased_query`
**Input**:
- `prev = "What tasks are in my Notion queue?"`
- `curr = "Which Notion tasks are pending?"`

**Expected**: `True`

**Rationale**: Shared content words = {"notion", "tasks"} (count = 2 >=
`_REPHRASE_MIN_SHARED_WORDS`). Jaccard on full token sets: union ≈ 12,
intersection ≈ 4 → Jaccard ≈ 0.33 >= 0.30. Both conditions satisfied.

---

### TC-PREF-001-002 — Different topic (AC-CR034-002)

**Method**: `is_rephrased_query`
**Input**:
- `prev = "What tasks are in my Notion queue?"`
- `curr = "What is the weather today?"`

**Expected**: `False`

**Rationale**: No shared content words after stopword removal ("notion",
"tasks", "queue" vs. "weather", "today"). Shared content count = 0 < 2.
Short-circuits at step 4 of the algorithm.

---

### TC-PREF-001-003 — Identical strings (AC-CR034-003)

**Method**: `is_rephrased_query`
**Input**:
- `prev = "Investigate Python"`
- `curr = "Investigate Python"`

**Expected**: `False`

**Rationale**: Identical strings are not a rephrase signal — they indicate a
retry. The function exits at the identity check (step 1 of algorithm).

---

### TC-PREF-001-004 — Decay applied to implicit preference (AC-CR034-004)

**Method**: `decay_and_prune`
**Setup**: In-memory SQLite with `preferences` table; one row:
```
source="implicit_preference", confidence=0.80
```

**Expected**:
- Row remains in table
- `confidence` is approximately `0.76` (= 0.80 * 0.95)
- `decayed_count >= 1`

**Rationale**: Row starts above `_PRUNE_THRESHOLD (0.30)`. Decay multiplier
`0.95` is applied. Result `0.76` is still above threshold — not pruned.

---

### TC-PREF-001-005 — Row pruned below threshold (AC-CR034-005)

**Method**: `decay_and_prune`
**Setup**: In-memory SQLite with `preferences` table; one row:
```
source="implicit_preference", confidence=0.29
```

**Expected**:
- Row deleted from table
- `pruned_count >= 1`

**Rationale**: `0.29 < _PRUNE_THRESHOLD (0.30)`. The UPDATE skips it (WHERE
confidence >= 0.30 not satisfied). The DELETE removes it.

---

## Mocking strategy

| Dependency | Mock approach |
|---|---|
| SQLite database | `sqlite3.connect(":memory:")` with manual schema creation |
| LLM calls | None — `is_rephrased_query` has no LLM calls (NFR-PREF-001) |
| `upsert_memory_fact` | Not exercised in unit tests; covered by integration |

All tests are deterministic. No real DB, no real LLM, no real timestamps without
freezing (decay result is checked with `pytest.approx` or `abs()` tolerance).
