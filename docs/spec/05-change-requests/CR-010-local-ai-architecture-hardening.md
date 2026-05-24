# CR-010: Local AI Architecture Hardening

## Summary

Seven targeted improvements derived from a structured gap analysis against a local-AI reference
architecture specification. The changes address four reliability gaps (context overflow, runaway
staging loops, unstructured memory, missing event contract) and two quality improvements (HyDE
retrieval, structured fact extraction) plus an operational hardening item (Ollama startup tuning).

No existing behaviours are removed. All changes are additive or internally contained.

## Type

Incremental architectural improvement (single-phase)

## Motivation

A reference spec for local-AI assistants on 14 GB VRAM was evaluated against Xochitl's
implementation across six layers. The weighted gap analysis produced this priority order:

| Rank | Gap | Layer | Weighted gap score |
|---|---|---|---|
| 1 | Rolling history trim absent from local routing | L3 Orchestration | 0.167 |
| 2 | Memory write unstructured; no category or confidence | L5 Memory | 0.152 |
| 3 | No event contract for future web layer | L3 Orchestration | — |
| 4 | Staged-message runaway possible | L3 Orchestration | — |
| 5 | Ollama not configured for production use | L1 Model Serving | 0.090 |
| 6 | HyDE absent from vector recall | L5 Memory | — |

## Root Cause

1. **Context overflow** — `_route_local()` passed the full unbounded `session_history` to the
   local model on every turn. `compress_context()` existed but only fired in `_route_cloud()`.
   Long sessions would silently degrade or error when history exceeded the model's context window.

2. **Runaway staging** — `_staged_message` could be set by a skill result, fire immediately on
   the next iteration, set another staged message, and loop indefinitely with no guard.

3. **Unstructured memory** — `BackgroundReview` wrote one-sentence free-text observations to a
   Markdown file. No category, no confidence score, no structured DB record. The facts were not
   queryable by category or filterable by reliability.

4. **No web event contract** — The future web UI needs typed events to drive status pills, tool
   call cards, and HITL prompts. Without a dedicated emitter in place now, the web layer would
   have to couple directly to chat internals.

5. **Suboptimal retrieval** — `VectorMemory.recall()` embedded the raw user question. Personal
   notes and BMAD documents are written as declarative statements. Embedding a question to search
   declarative content produces systematically worse results than embedding a generated statement.

6. **Ollama defaults** — Default Ollama settings (5-minute keep-alive, no KV cache quantization,
   no flash attention) waste VRAM and cause cold-model latency on every new session.

## Affected Requirements

- `FR-ORCH-018` — BackgroundReview daemon (extends — now also writes structured DB facts)
- `DATA-DATA-003` — Vector retrieval (extends — HyDE wraps existing `_embed()` path)
- `DATA-DATA-005` — Long-term semantic memory preload (compatible — new table supplements it)
- `ARCH-SDD-001` — All LLM calls via TieredRouter (preserves)

## New Requirements

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `FR-ORCH-020` | functional | P1 | `src/events.py` provides a thread-safe event bus; `_agent_loop` emits `routing_started`, `skill_matched`, `skill_started`, `skill_complete`, `llm_complete`, and `hitl_required` events so the future web SSE layer can subscribe without coupling to chat internals |
| `FR-ORCH-021` | functional | P0 | `_route_local()` trims conversation history to the 10 most recent messages before the LLM call, summarising older messages as a heuristic context block, preventing context window overflow on long sessions |
| `NFR-UI-007` | non-functional | P1 | A consecutive-staged-message counter in `XochitlChat.start()` clears the staged queue and warns the user if more than 5 staged messages fire without real user input |
| `DATA-DATA-006` | data | P1 | A `memory_facts` SQLite table stores structured per-turn facts with `category` (preference / context / project / skill / constraint / goal), `confidence` (0–1), `source`, `project`, and a `superseded_by` reference for tombstoning |
| `DATA-DATA-007` | data | P1 | `VectorMemory.recall()` generates a hypothetical document via the fast local model before embedding, so declarative personal notes are retrieved by embedding a statement rather than a question (HyDE pattern); falls back to direct query embedding if the model call fails |
| `OPS-CORE-001` | operations | P2 | `scripts/start_ollama.ps1` configures Ollama with `KEEP_ALIVE=30m`, `NUM_PARALLEL=2`, `FLASH_ATTENTION=1`, `KV_CACHE_TYPE=q8_0`, and `MAX_LOADED_MODELS=2` before starting the server; `.env.example` documents all configurable model and API variables |

## Acceptance Criteria

| ID | Parent | Criterion |
|---|---|---|
| `AC-CR010-001` | `FR-ORCH-020` | When `_agent_loop` completes a turn, at least `routing_started` and `llm_complete` events are emitted on the module-level emitter; adding a subscriber at runtime does not affect the chat response |
| `AC-CR010-002` | `FR-ORCH-021` | When a session has more than 10 messages in `_clean_history()`, `_route_local()` receives a list whose first two entries are the summary context block and acknowledgement, followed by exactly 10 real messages |
| `AC-CR010-003` | `NFR-UI-007` | If 6 or more staged messages fire consecutively without a real `Prompt.ask()` turn, the staged queue is cleared and a `⚠ Staged message loop detected` warning is printed; the counter resets to 0 on the next real user input |
| `AC-CR010-004` | `DATA-DATA-006` | `BackgroundReview._write()` calls `db.upsert_memory_fact()` when the structured extraction returns a fact with `confidence ≥ 0.4`; the fact is stored in `memory_facts` with the correct category enum value |
| `AC-CR010-005` | `DATA-DATA-007` | `VectorMemory._hyde_embed()` calls the local router model with `_HYDE_PROMPT`; if the model returns non-empty content, the embedding is computed on the generated passage, not the original query; a model error causes a clean fallback to `_embed(query)` with no exception propagating |
| `AC-CR010-006` | `OPS-CORE-001` | `scripts/start_ollama.ps1` sets all five Ollama env vars before invoking `ollama serve`; `.env.example` lists every tunable with inline comments explaining the effect |

## Implementation Notes

- `trim_history_for_local()` uses `_summarize_older_history()` (heuristic, no LLM call) so no
  latency is added before the actual routing call.
- `BackgroundReview` now makes **two** local model calls per qualifying turn (unstructured
  observation + structured JSON extraction). Both are gated by `_MIN_WRITE_INTERVAL_SECS = 30`
  and run in the daemon thread — the main thread is never blocked.
- The event emitter singleton is imported as `from src import events as _events` in `chat.py`;
  the terminal `_StatusContext` continues using direct `_status.update()` calls for low latency.
  The emitter is the subscription channel for the web layer only.
- `memory_facts` uses a 80-character prefix match for near-duplicate detection at write time,
  avoiding a vector call. Full semantic dedup (cosine > 0.85) is deferred to the hygiene cron
  (future CR).

## Files Changed

| File | Change |
|---|---|
| `src/events.py` | **New** — `XochitlEventEmitter`, module-level singleton, `emit()` convenience function |
| `src/database.py` | Added `memory_facts` table to `init_db()`; added `_ensure_memory_facts_table()`, `upsert_memory_fact()`, `get_memory_facts()` helpers |
| `src/context_loader.py` | Added `trim_history_for_local()` using existing `_summarize_older_history()` |
| `src/memory.py` | Added `_HYDE_PROMPT`, `_hyde_embed()` to `VectorMemory`; `recall()` now calls `_hyde_embed()` |
| `src/background_review.py` | Added `_STRUCTURED_EXTRACT_PROMPT`, `_VALID_CATEGORIES`, `_extract_structured()`; updated `_process()` and `_write()` signatures; added structured DB write |
| `src/router.py` | `_route_local()` now calls `trim_history_for_local()` before building messages |
| `src/chat.py` | Added `_consecutive_staged` counter and loop guard; imported `src.events`; added `emit()` calls at `routing_started`, `skill_matched`, `skill_started/complete`, `llm_complete`, `hitl_required` |
| `scripts/start_ollama.ps1` | **New** — Ollama startup script with recommended env vars |
| `.env.example` | **New** — All configurable model, API, and Ollama env variables with comments |

## Verification

```
python -m py_compile src/events.py src/database.py src/context_loader.py \
    src/memory.py src/background_review.py src/router.py src/chat.py
python smoke_test.py
# Expected: 54 passed, 0 failed (includes AC-CR010-001..006)
```

2026-05-24:
- `py_compile` clean on all changed modules.
- `python smoke_test.py`: 54 passed, 0 failed.
- `.env.example` and `.xochitl/scripts/resolve_customization.py` added (were missing from working tree).
