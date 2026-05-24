# CR-031 — LLM Token Streaming

**Status**: implemented
**Priority**: P1
**Source**: `docs/planning/exploration-2026-05.md` — Group 7 item #33 (D14), #32 (D13)
**Affects**: `src/llm_interface.py`, `src/router.py`, `src/chat.py`

---

## Problem statement

Xochitl currently returns LLM responses as a complete batch: the model generates the entire reply, returns it to the router as a string, and then `_stream_response()` fake-streams it word-by-word via `time.sleep(0.012)`. This creates two problems:

1. **Perceived latency**: The terminal shows a spinning flower for several seconds, then dumps the complete text. There is no intermediate feedback that the model is generating — it feels like a batch job, not a conversation.
2. **False liveness**: The word-delay in `_stream_response()` is cosmetic theatre. It is not tied to actual model generation speed and adds artificial latency on top of real latency.

Per exploration notes: *"Streaming is the primary liveness signal. Without streaming, the CLI feels like a batch job, not a conversation. This is perception-critical."* (Group 7, D13/D14)

---

## Solution

Add real LLM token streaming on both providers:

- **Ollama (local)**: `stream_local()` already exists in `llm_interface.py`. Wire it into the routing path.
- **Gemini (cloud)**: Add `_stream_gemini()` using OpenAI SDK `stream=True`.
- **Anthropic (cloud)**: Add `_stream_anthropic()` using the `anthropic` SDK's native streaming context manager.
- **Unified**: Add `stream_cloud()` dispatcher.
- **Router**: Add `route_stream()` to `TieredRouter` — classifies intent (blocking, fast), then yields tokens from the appropriate provider.
- **Chat loop**: `_agent_loop()` uses the streaming path for conversational turns. Skill-injected turns (where a `<skill_call>` response is expected) continue to use the non-streaming path because they require the full response for parsing.

### Thread coordination

The existing architecture runs `process_message()` in a daemon worker thread via `_run_with_cancel()`, while `rich.Live` runs in the main thread. When `_agent_loop` starts streaming:

1. The worker thread stops the `_StatusContext`'s `Live` display before printing the first token.
2. Tokens are printed directly to the console from the worker thread.
3. The main thread's `with status_ctx:` block exits cleanly because `_live` is set to `None` before the worker stops it.
4. `start()` checks `self._last_response_streamed` to skip `_stream_response()`.

### Streaming scope (v1)

Streaming applies to conversational agent-loop turns only:
- ✅ Conversational responses (no skill injected, `top_score < 0.65`)
- ❌ Skill-injected turns (`top_score ≥ 0.65` → non-streaming, full response needed)
- ❌ Weather / task / file dispatch paths (fast enough, skill-result oriented)

---

## Requirements

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `FR-UI-005` | functional | P1 | LLM responses for conversational turns are delivered as real token streams from the model provider, not synthetic word delays |
| `NFR-PERF-009` | non-functional | P2 | First token appears within 3 seconds for local model and 5 seconds for cloud under normal network conditions |

---

## Acceptance criteria

| ID | Scenario | Given | When | Then |
|---|---|---|---|---|
| `AC-CR031-001` | Real token streaming | User sends a conversational message (no skill matched) | `_agent_loop` runs | Tokens appear on screen progressively as the model generates them, not after a full batch wait |
| `AC-CR031-002` | Skill path unaffected | User triggers a skill (`top_score ≥ 0.65`) | `_agent_loop` runs | Non-streaming path used; full `LLMResponse` returned and parsed for `<skill_call>` as before |
| `AC-CR031-003` | Cloud streaming | Cloud provider (Gemini or Anthropic) is active | Conversational turn streams | Tokens arrive progressively from the provider's streaming API |
| `AC-CR031-004` | Local streaming | Ollama is active | Conversational turn streams | Tokens arrive progressively from Ollama's `stream=True` chat endpoint |
| `AC-CR031-005` | No double-print | Streaming turn completes | `start()` runs post-response | Response is not re-printed by `_stream_response()` |
| `AC-CR031-006` | Empty stream fallback | Streaming yields no tokens | `_agent_loop` runs | Falls back to non-streaming `route()` call; user sees a response |
| `AC-CR031-007` | Spinner until first token | Model is generating first token | `_StatusContext` is active | Spinner remains visible until streaming begins, then clears |
| `AC-CR031-008` | Smoke tests pass | All changes applied | `python smoke_test.py` runs | All existing tests pass |

---

## Implementation tasks

| ID | Task | Module | Status |
|---|---|---|---|
| `TASK-UI-031-a` | Add `_stream_gemini()`, `_stream_anthropic()`, `stream_cloud()` | `src/llm_interface.py` | implemented |
| `TASK-UI-031-b` | Add `stream_local`, `stream_cloud` to router imports; add `route_stream()` to `TieredRouter` | `src/router.py` | implemented |
| `TASK-UI-031-c` | Add `_last_response_streamed` flag; add `_stream` param to `process_message`; update `_agent_loop` streaming path; update `start()` | `src/chat.py` | implemented |
| `TASK-UI-031-d` | Update requirements registry and traceability matrix | SDD docs | implemented |

---

## Known limitations (v1)

- Streaming does not apply to skill-injected turns (by design — `<skill_call>` parsing requires the full response).
- Partial skill calls embedded in streamed output are not filtered in real-time (not a concern in practice since no skill schema is injected for conversational turns).
- `_stream_response()` is kept for non-streaming paths (weather, task, file results, skill outputs) to maintain existing word-paced rendering for those shorter outputs.
- Streaming does not apply to the weather / task / file dispatch paths.

---

## Verification

- `py_compile` passes on all modified files
- `python smoke_test.py` — all existing tests pass
- Manual: `xochitl chat` → send a conversational message → tokens appear progressively
