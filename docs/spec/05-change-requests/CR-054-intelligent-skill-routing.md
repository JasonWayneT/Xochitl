# CR-054 — Intelligent Skill Routing

| Field | Value |
|---|---|
| ID | CR-054 |
| Title | Intelligent Skill Routing |
| Status | implemented (Phase 5 — hierarchical domain routing — deferred to ≥150 skills) |
| Priority | P1 |
| Source | Gap analysis (June 2026) — fix elliptical follow-up failures, add semantic skill discovery, build self-learning vocabulary expansion, and design for scale to 1000+ skills |
| Implements | `FR-ROUTE-001`–`FR-ROUTE-015`, `NFR-ROUTE-001`–`NFR-ROUTE-003` |
| Enables | CR-053 Phase 5 (`FR-RES-022` context-aware research follow-ups) |

## Summary

Xochitl's skill routing is keyword-only: `can_handle()` matches on raw user input,
and only high-scoring skills get their definition injected into the system prompt.
This creates three failure modes:

1. **Routing miss** — "what about in hemet?" after a weather query scores 0.0 on
   `WeatherSkill` because it contains no weather keywords. The skill definition is
   never injected, so the LLM cannot emit a `<skill_call>` even if it understands
   the intent.

2. **Synonym blindness** — "fry up some chicken" never reaches a RecipeSkill because
   "fry" is not in the hardcoded keyword list. Vector similarity would catch it;
   keyword matching cannot.

3. **Scale ceiling** — the compact-manifest approach (always inject all skills) works
   at ~15 skills but breaks at 1,000: 1,000 skills × ~40 tokens = 40,000 tokens,
   exceeding the cloud budget entirely.

This CR fixes all three via a layered architecture:
- Always-on compact manifest (solves routing miss for known skills)
- Context-aware `can_handle()` boost (solves elliptical follow-ups)
- Vector pre-filter (solves synonym blindness and scale)
- Self-learning hard-add (grows the vocabulary from confirmed matches)
- Hierarchical domain routing (activates automatically at 150+ skills)

## Key files touched

| File | Change |
|---|---|
| `src/agent/pipeline.py` | Write `last_skill_fired` to context; detect routing misses |
| `src/agent/skill_scorer.py` | Load learned examples into per-skill cache; call vector fallback |
| `src/context_manager.py` | Inject compact skill manifest on every turn |
| `src/skill_vector.py` | New — `SkillVectorIndex` (clone of `WorkflowVectorIndex`) |
| `src/skills/base.py` | Add `domain` tag to `tool_definition()` schema |
| `src/skills/*.py` | Add context-boost logic to `can_handle()` where appropriate; add `domain` tag |
| `src/skills/__init__.py` | Seed `SkillVectorIndex` at session start |
| `src/background_review.py` | Add routing-miss detection; trigger hard-add on confirmed vector match |
| `src/database.py` | New tables: `routing_misses`, `skill_examples` |

## Phases

- **Phase 1** — Always-on compact manifest
- **Phase 2** — Context-aware follow-up routing
- **Phase 3** — Hybrid vector routing + scale thresholds
- **Phase 4** — Skill self-learning (routing-miss detection + hard-add)
- **Phase 5** — Hierarchical domain routing *(activates at 150+ skills)*

## Requirements

### Phase 1 — Always-on Compact Manifest

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-ROUTE-001` | functional | P0 | implemented | `ContextManager` injects a compact skill manifest block on every turn, regardless of keyword score. Format: one line per skill — `name: when-clause \| example 1 / example 2`. Total budget ≤800 tokens for up to 50 skills. |
| `FR-ROUTE-002` | functional | P0 | implemented | The full `_format_active_skill_block` injection is reserved for skills that score above `_SKILL_INJECT_THRESHOLD` (existing behavior). The compact manifest is always present as a fallback so the LLM can emit `<skill_call>` for any known skill even if its full block is not injected. |
| `NFR-ROUTE-001` | non-functional | P1 | implemented | When skill count exceeds 50, the compact manifest is automatically truncated to the 50 most recently used skills (tracked via `context["skill_usage_counts"]`) plus any skill that scored >0.0 on the current turn. This keeps manifest token cost bounded regardless of total skill count. |

### Phase 2 — Context-Aware Follow-up Routing

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-ROUTE-003` | functional | P0 | implemented | `pipeline.py` writes `context["last_skill_fired"] = skill_name` (empty string if no skill fired) at the end of every turn. This key is available to `can_handle()` on the next turn. |
| `FR-ROUTE-004` | functional | P0 | implemented | Skills that handle location-, time-, or topic-scoped follow-ups implement a context-boost check in `can_handle()`: if `len(user_input.split()) <= 8` AND the input contains any of `("what about", "and in", "how about", "same for", "what about in")` AND `context.get("last_skill_fired") == self.__class__.__name__`, return a score of 0.75 regardless of keyword match. |
| `FR-ROUTE-005` | functional | P1 | implemented | `WeatherSkill`, `ResearchSkill`, `ExplorerSkill`, `WebLookupSkill`, and `MapsSkill` implement `FR-ROUTE-004`. Other skills may opt in by implementing the same pattern. |

### Phase 3 — Hybrid Vector Routing

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-ROUTE-006` | functional | P0 | implemented | New `src/skill_vector.py` defines `SkillVectorIndex`, structurally identical to `WorkflowVectorIndex` (`src/workflow_vector.py`) but targeting a `skill_intents` LanceDB table. Uses `nomic-embed-text` via Ollama. |
| `FR-ROUTE-007` | functional | P0 | implemented | At session start, `SkillVectorIndex.seed_from_skills(skills: list[Skill])` indexes all `tool_definition()["examples"]` entries and the `when` field for each skill. Each row stores `{skill_name, phrase, source="seed"\|"learned", indexed_at}`. This is a best-effort operation: failure does not block session start. |
| `FR-ROUTE-008` | functional | P0 | implemented | `SkillScorer.score()` runs vector fallback when keyword scoring returns `None` (score < threshold). Vector fallback calls `SkillVectorIndex.search(user_input, limit=5)`. If any result has `score >= 0.80`, that skill is returned as the match. Vector fallback does not run when keyword scoring already found a match. |
| `NFR-ROUTE-002` | non-functional | P0 | implemented | Vector fallback must not block the main thread beyond 500ms. `SkillVectorIndex.search()` is called with a thread timeout; if the embedding call exceeds the limit, the fallback returns `None` silently and the turn proceeds without a skill match. |
| `FR-ROUTE-009` | functional | P1 | implemented | Scale threshold logic is built into `SkillScorer` from day one and activates automatically based on registered skill count: ≤30 skills — compact manifest only, vector as fallback; 31–150 skills — vector retrieval produces top-20 shortlist; compact manifest is limited to that shortlist. 151+ skills — see Phase 5 (domain routing gate added before vector search). |

### Phase 4 — Skill Self-Learning

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-ROUTE-010` | functional | P1 | implemented | `database.py` adds two tables: `routing_misses {id, user_input, inferred_skill, turn_id, created_at}` and `skill_examples {id, skill_name, phrase, source, confidence, created_at}`. |
| `FR-ROUTE-011` | functional | P1 | implemented | `pipeline.py` detects routing misses: when `skill_fired = None` and the LLM response contains hedging patterns (`"would you like me to"`, `"i think you're asking about"`, `"did you mean"`, `"i can help with"`), a routing-miss event is emitted to `BackgroundReview` with `{user_input, inferred_skill_hint}`. The `inferred_skill_hint` is extracted by pattern-matching the LLM response against known skill names. |
| `FR-ROUTE-012` | functional | P1 | implemented | When `SkillScorer` fires a skill via vector fallback (not keyword), `BackgroundReview` performs a hard-add: the matched phrase is inserted into `skill_examples` with `source="learned"` and indexed into `skill_intents` via `SkillVectorIndex.index_phrase(skill_name, phrase)`. |
| `FR-ROUTE-013` | functional | P1 | implemented | At session start, `SkillScorer` loads all `skill_examples` rows into an in-memory dict keyed by `skill_name`. Each skill's `can_handle()` checks this dict (passed via `context["learned_examples"]`) in addition to its hardcoded keyword list. `BackgroundReview` sets `context["skill_examples_dirty"] = True` when new phrases are added; `SkillScorer` reloads on the next turn when this flag is set. |
| `NFR-ROUTE-003` | non-functional | P2 | implemented | A routing-miss event that has been seen ≥3 times for the same `user_input[:40]` pattern is automatically promoted: the `inferred_skill_hint` is added to `skill_examples` with `confidence=0.70` without waiting for a vector-confirmed match. Frequency threshold is configurable via `XCH_ROUTING_MISS_PROMOTE_THRESHOLD` (default 3). |

### Phase 5 — Hierarchical Domain Routing *(activates at 150+ skills)*

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-ROUTE-014` | functional | P2 | implemented | `tool_definition()` schema gains an optional `domain` field (string). Valid domains: `cooking`, `weather`, `code`, `health`, `finance`, `research`, `productivity`, `communication`, `navigation`, `system`. Skills without a `domain` tag are placed in a catch-all `general` domain. |
| `FR-ROUTE-015` | functional | P2 | implemented | When registered skill count exceeds 150, `SkillScorer` runs a domain-classification step before vector search: a `force_route="simple_qa"` call classifies the user query into one domain (~30ms). Vector search is then scoped to skills in that domain, reducing index size and false-positive rate. Domain classification is skipped (full search used) when the query contains no clear domain signal or the classification returns `general`. |

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR054-001` | "what is the weather in san diego?" followed by "what about in hemet?" routes to `WeatherSkill` on the second turn without keyword match. |
| `AC-CR054-002` | "fry up some chicken" routes to a RecipeSkill (once one exists) via vector similarity, not keyword match. |
| `AC-CR054-003` | After "fry up some chicken" fires RecipeSkill via vector, a second session sees "fry up some chicken" matched via keyword (hard-add persisted). |
| `AC-CR054-004` | With 15 skills registered, compact manifest token cost is ≤800 tokens per turn. |
| `AC-CR054-005` | With 200 skills registered, compact manifest is limited to the vector-retrieved shortlist (~20 skills) — total manifest cost remains ≤800 tokens. |
| `AC-CR054-006` | A routing miss ("I think you're asking about...") for the same pattern ≥3 times promotes the phrase to `skill_examples` automatically. |
| `AC-CR054-007` | Vector fallback completes within 500ms or times out silently — it never blocks a turn. |
| `AC-CR054-008` | With 200+ skills and domain routing active, "what is the weather in Tokyo?" scopes the vector search to the `weather` domain before selecting `WeatherSkill`. |

## Design notes

### Why not vector-only routing?

Dense vector retrieval alone has two problems at Xochitl's current scale (~15 skills):
embedding latency (~100–200ms) exceeds `SkillScorer`'s 100ms budget, and semantic
proximity produces false positives ("cook the books" → RecipeSkill). Keyword matching
is fast and precise for known phrases. The hybrid — keywords first, vector as fallback,
LLM as final arbiter via compact manifest — gives speed, accuracy, and discovery.

### Why the compact manifest is not enough at scale

1,000 skills × ~40 tokens = 40,000 tokens, exceeding the 28,000-token cloud budget.
The vector pre-filter reduces the injected shortlist to ~20 skills (~800 tokens)
regardless of total skill count. This is the same pattern used by LangChain tool
retrieval and Semantic Kernel at scale.

### Hard-add feedback loop

```
First encounter:  "fry up chicken"  →  vector discovery  →  RecipeSkill fires
                                    →  hard-add to skill_examples + skill_intents
Second encounter: "fry up chicken"  →  keyword match (from skill_examples cache)
                                    →  RecipeSkill fires instantly, no vector call
```

The vector index is the discovery layer. The keyword path is the optimized execution
layer. Over time the keyword path accumulates vocabulary and vector lookups become
less frequent for common patterns.
