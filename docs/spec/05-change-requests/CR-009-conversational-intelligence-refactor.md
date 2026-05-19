# CR-009: Conversational Intelligence Refactor

## Summary

Three-phase architectural refactor to make Xochitl behave as a genuine personality-first
conversational AI — similar in quality to Claude Code and Gemini. The changes resolve three
long-standing structural defects: SOUL.md token starvation, triple classification conflict, and
hallucinated skill activation. A new passive background learning daemon is also added so Xochitl
continuously refines its user model without requiring explicit "remember that" commands.

## Type

Architectural improvement (multi-phase)

## Root cause

Four compounding problems identified through reference-project analysis (Symphony, Hermes,
OpenClaw):

1. **SOUL.md token starvation** — `SkillManifestEngine` consumed ~600 tokens of the 6,000-token
   local budget before SOUL.md was assembled. Under budget pressure the compaction path evicted
   soul content first, making Xochitl's personality disappear in long sessions.

2. **Triple classification conflict** — Three independent classifiers ran on every turn:
   `_fast_classify()` in `router.py` (keyword), `_classify()` in `router.py` (LLM), and
   `_classify_intent()` in `chat.py` (keyword). They could disagree silently, causing
   inconsistent routing.

3. **Hallucinated skill activation** — `can_handle()` was defined on every skill but never called
   in the main conversation flow. Skills only fired if the LLM spontaneously produced exact
   `<skill_call>` XML unprompted, with no per-turn guidance injected.

4. **No passive learning** — User corrections and preference signals were only captured if the
   user explicitly said "remember that" or "I prefer". Organic personality signals from the
   exchange were discarded.

## Affected Requirements

- `NFR-PERF-004` — Token budget via ContextManager (extends — SOUL.md now always protected)
- `FR-ORCH-003` — PreFlight Fact Injection (preserves)
- `FR-ORCH-005` — Skill `tool_definition()` injected into system prompt (refines — now only the
  winning skill is injected, not the full manifest)
- `FR-ORCH-008` — Agent loop `<skill_call>` parsing (preserves)
- `ARCH-SDD-001` — All LLM calls via TieredRouter (preserves)
- `BUG-ORCH-007` — Triple classification conflict (resolves)

## New Requirements

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `FR-ORCH-016` | functional | P0 | SOUL.md content is merged into the Identity Guard block and is never evicted or compacted, regardless of token budget pressure |
| `FR-ORCH-017` | functional | P0 | Every `_agent_loop()` call scores all loaded skills via `can_handle()` before the LLM call; the highest-scoring skill above 0.65 has its schema injected into the system prompt for that turn only |
| `FR-ORCH-018` | functional | P1 | A daemon thread runs after every completed turn, extracts a single passive observation about the user from the exchange, and writes it to KnowledgeBase Tier 2 without blocking the main thread |
| `NFR-PERF-008` | non-functional | P1 | The background review daemon uses a bounded queue (maxsize=20), drops silently when full, and writes at most once per 30 seconds to prevent KB noise |
| `FR-ORCH-019` | functional | P0 | `router.route()` uses a single `_classify()` call for intent; `_fast_classify()` is no longer invoked in the routing path, eliminating dual-classifier disagreement |

## Acceptance Criteria

| ID | Criterion |
|---|---|
| `AC-CR009-001` | SOUL.md content appears in every system prompt regardless of session length; compaction never removes the Identity Guard block |
| `AC-CR009-002` | A turn where a skill scores ≥0.65 produces a system prompt that includes that skill's schema in an `## Active Skill` block; a turn scoring <0.65 does not inject any skill schema |
| `AC-CR009-003` | After a turn where the user corrects Xochitl or expresses a preference, a `passive_learning_YYYY-MM-DD.md` entry appears in the KB within 60 seconds |
| `AC-CR009-004` | The background review thread is named `xochitl-background-review`, is daemon=True, and does not block or raise on the main thread under any condition |
| `AC-CR009-005` | `router.route()` contains exactly one call to `self._classify()`; no call to `_fast_classify()` in the routing path |
| `AC-CR009-006` | `smoke_test.py` passes with 0 failures after all changes |

## Design: Phase 1 — Soul Guard & Routing Consolidation

```
ContextManager.assemble_system_prompt()
  │
  ├─ soul_text = self.soul.assemble()
  ├─ base_guard = "## Identity Guard\n1. You are Xochitl..."
  ├─ guard_text = f"{soul_text}\n\n---\n\n{base_guard}"   ← SOUL always first, always kept
  │
  ├─ parts = [guard_text, facts_text]           ← soul + facts always in
  ├─ optional: behavior, skills_hint (2 lines), preferences, memory, files
  │
  └─ COMPACTION: guard_text is NEVER compacted — only optional parts are trimmed

TieredRouter.route(query, ...)
  │
  └─ category, confidence = self._classify(query)   ← single call; _fast_classify() removed
```

**Skills hint** (replaces full 600-token manifest):
```
## Skills
Skills are available for task management, BMAD, code generation, Notion, and more.
They will be provided when relevant to your request.
```

## Design: Phase 2 — Deterministic Skill Injection

```
chat._agent_loop(user_input, cm, status)
  │
  ├─ Score all skills: skill.can_handle(user_input, context) for skill in self.skills
  ├─ top_skill = skill with highest score
  │
  ├─ if top_score >= 0.65:
  │     defn = top_skill.tool_definition()
  │     system_prompt += "\n\n---\n\n" + _format_active_skill_block(defn)
  │
  └─ router.route(query, system=system_prompt, ...)
```

`_format_active_skill_block(defn)` emits:
```
## Active Skill
The following skill is relevant to this request: **SkillName**
Does: <description>
Use when: <when>
To invoke it, output: <skill_call name="X">{...}</skill_call>
```

## Design: Phase 3 — Passive Background Learning

```
XochitlChat.__init__()
  └─ self._background_review = BackgroundReview(); self._background_review.start()

XochitlChat.process_message() — end of every main-path turn:
  └─ self._background_review.queue_turn(user_input, response, project=self.current_project)

BackgroundReview (daemon thread)
  ├─ Queue(maxsize=20) — put_nowait; drops silently when full
  ├─ _extract(): call_local(ROUTER_MODEL, _REVIEW_PROMPT) → ONE sentence or NONE
  │   - Weights corrections and pushback highest
  │   - Filters _NO_EXTRACT_VALUES sentinel set
  │   - Clips multi-sentence to first sentence
  ├─ _write(): atomic .tmp→rename to ~/.xochitl/kb/passive_learning_YYYY-MM-DD.md
  │   - Deduplicates by first-60-char check
  │   - Best-effort Tier 3 VectorMemory.memorize()
  └─ Rate limit: max 1 write per 30 seconds
```

## Implementation Tasks

| ID | Task | File | Phase |
|---|---|---|---|
| `TASK-CR009-001` | Merge SOUL.md into Identity Guard; make guard_text never-compact | `src/context_manager.py` | 1 |
| `TASK-CR009-002` | Replace full SkillManifestEngine call with 2-line skills hint | `src/context_manager.py` | 1 |
| `TASK-CR009-003` | Remove `_fast_classify()` call from `route()`; use single `_classify()` | `src/router.py` | 1 |
| `TASK-CR009-004` | Remove duplicate `_build_preflight_facts()` and `_resolve_file_context()` from `route()` | `src/router.py` | 1 |
| `TASK-CR009-005` | Remove top-level `classify_conversation_intent` import; add lazy import in `_classify_intent()` | `src/chat.py` | 1 |
| `TASK-CR009-006` | Replace steps 5-6 intent dispatch with deterministic keyword guards + `_agent_loop()` fallback | `src/chat.py` | 1 |
| `TASK-CR009-007` | Add `_SKILL_INJECT_THRESHOLD` constant and `_format_active_skill_block()` helper | `src/chat.py` | 2 |
| `TASK-CR009-008` | Add skill scoring loop before LLM call in `_agent_loop()` | `src/chat.py` | 2 |
| `TASK-CR009-009` | Create `BackgroundReview` class with daemon thread, bounded queue, and rate limiting | `src/background_review.py` | 3 |
| `TASK-CR009-010` | Instantiate `BackgroundReview` in `XochitlChat.__init__()` and wire `queue_turn()` at turn end | `src/chat.py` | 3 |
| `TASK-CR009-011` | Call `shutdown()` on exit/quit path | `src/chat.py` | 3 |
| `TASK-CR009-012` | Update requirements registry and traceability matrix | `docs/spec/` | all |

## Status

- [x] Change request created
- [x] Requirements identified
- [x] Implementation complete (Phase 1, 2, 3)
- [x] Verified — smoke_test.py: 27 passed, 0 failed; E2E clean
