# ADR-004 — Token Estimation Strategy for the Session Governor

**Status**: accepted
**Date**: 2026-05-24
**CR**: CR-026 (Session Tiered Governor)
**Deciders**: Jason Wayne (owner), Xochitl agent

---

## Context

`SessionGovernor` needs to estimate token spend per turn in order to apply tiered
routing restrictions. Three strategies were considered.

---

## Options considered

**Option A — API response metadata (actual token counts)**

Most LLM APIs return `usage.prompt_tokens` and `usage.completion_tokens` in the
response body. The `LLMResponse` object returned by `TieredRouter.route()` could
carry these counts.

- Pro: exact; reflects the model's actual tokenizer.
- Con: requires changes to `router.py`, `LLMResponse`, and all provider adapters; the
  streaming path has no synchronous token count; local Ollama counts vary by model.

**Option B — tiktoken (OpenAI tokenizer library)**

`tiktoken` can count tokens for GPT-family models precisely.

- Pro: accurate for OpenAI-tokenized models (GPT, Claude approximate).
- Con: adds a non-trivial dependency; requires a specific encoding per model; still
  wrong for Gemma / Ollama models which use different tokenizers.

**Option C — Character-count approximation: `chars / 4` (selected)**

OpenAI's documented rule of thumb: 1 token ≈ 4 English characters.

- Pro: zero new dependencies; zero I/O overhead; consistent across all models and
  providers; fast (one integer division).
- Con: ±15–30% error for typical English text; larger error for code, JSON, or
  non-English content.

---

## Decision

**Option C — character-count approximation** (`len(text) // 4`).

Rationale:
- The governor is a *soft budget guide*, not a billing meter. A 20–30% estimation
  error is acceptable: thresholds are deliberately conservative, and the user can
  override them via env vars.
- No new dependencies. `governor.py` uses only the Python stdlib.
- Works identically for local (Ollama/Gemma) and cloud (Gemini/Anthropic) turns
  without per-provider logic.
- If exact accounting is needed later, `record_turn` can be extended to accept an
  optional `actual_tokens` parameter (from API response metadata), falling back to
  the character estimate when not provided.

---

## Estimation formula

```python
def _estimate_tokens(text: str) -> int:
    """One token ≈ 4 characters (OpenAI rule of thumb). Returns ≥ 1."""
    return max(1, len(text) // 4)
```

`record_turn(prompt, response)` calls this twice and accumulates the results in
`_prompt_tokens` and `_completion_tokens`.

---

## What is NOT counted

- System prompt (assembled per-turn by `ContextManager`; typically 500–2 000 tokens).
- Injected context (file reads, fact preloads, memory snippets).
- Skill execution result turns (`role=tool` history entries).

**Recommendation**: set thresholds conservatively (e.g., `LOCAL_ONLY` at 40 000 est.
tokens while actual spend may be 50 000–55 000) to leave headroom for uncounted
system context.

---

## Consequences

- **Positive**: zero dependencies, zero latency, works offline.
- **Positive**: future upgrade path: add `actual_tokens=None` parameter to
  `record_turn` without breaking callers.
- **Negative**: systematic undercount of actual tokens if many skill/tool turns or
  large context injections occur.
- **Mitigation**: conservative defaults + env-var override.

---

## Follow-on

If a billing-accurate governor is needed (e.g., when running a shared Xochitl
instance for a team), add an `actual_tokens` override path in `record_turn` and
thread actual API usage metadata through `LLMResponse`. Track as future hardening.
