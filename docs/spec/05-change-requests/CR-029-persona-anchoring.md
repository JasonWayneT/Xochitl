# CR-029 — Persona Anchoring and SOUL.md Restructure

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #25 (Group 7A design)
**Implements**: FR-ORCH-028, FR-ORCH-029, NFR-ORCH-004, NFR-ORCH-005

---

## Problem

### 1 — `_render_system_prompt_template()` is never called

`context_manager.py` defines `_load_system_prompt_template()` and
`_render_system_prompt_template()` to inject the static behavior sections from
`prompts/system_xochitl.txt` — but `assemble_system_prompt()` never calls
`_render_system_prompt_template()`. As a result:

- `[GOAL]` — never sent to the model
- `[DISAGREEMENT PROTOCOL]` — never sent to the model
- `[TONE ADAPTATION]` — never sent to the model
- `[SPANISH AND CULTURAL VOICE]` — never sent to the model
- `[INTERACTION RULES]` — never sent to the model
- `[UNCERTAINTY TIERS]` (added in CR-032) — never sent to the model
- `[CAPABILITY BOUNDARY]` (added in CR-032) — never sent to the model
- `[BMAD CONTEXT]` — never sent to the model

The `[TURN CONTEXT]` note from CR-032 references `[UNCERTAINTY TIERS]`
vocabulary, but the vocabulary definitions never appear in the prompt.

### 2 — `SOUL.md.example` uses stale identity text

`SOUL.md.example` still reads "terminal-native AI Chief of Staff" — the
identity language CR-011 was supposed to standardise. The example is the
fallback persona used by all installations without a custom `SOUL.md`.

### 3 — SOUL.md has no structure

`SOUL.md` is free-form prose with no section markers, making it impossible to:
- Validate that the identity-critical section is present
- Intelligently compact the soul (keep identity, drop voice notes)
- Extract a pinned identity anchor without reading the whole file

---

## Solution

### 1 — Wire the behavior template

In `assemble_system_prompt()`, replace the inline soul-block construction
with a call to `_render_system_prompt_template()`:

```python
template_body = _render_system_prompt_template(
    identity_guard=base_guard,
    soul=soul_text,
    conversation_config=behavior_config_text,
)
guard_text = _LANG_HARD_GUARD + template_body
```

`guard_text` is already declared load-bearing and never compacted — embedding
the rendered template there ensures every static behavior section reaches the
model on every turn. The `ConversationConfigEngine` output is now part of
`guard_text`; it no longer appears as a separate compactible part.

### 2 — Restructure SOUL.md.example

Replace the free-form prose with four clearly marked sections:

| Section | Purpose | Compaction priority |
|---|---|---|
| `## [IDENTITY]` | Who Xochitl is — the identity anchor | Always preserved |
| `## [VOICE]` | Tone, cultural texture, Spanish blending | Preserved after identity |
| `## [VALUES]` | What she cares about | Preserved after voice |
| `## [BOUNDARIES]` | What she will not do | Dropped last under pressure |

Fix "Chief of Staff" → "personal AI system".

### 3 — Section-aware SoulEngine

- `ingest()` — extract `## [IDENTITY]` block into `_identity_anchor`; print a
  yellow warning and inject a minimal fallback if `[IDENTITY]` is missing.
- `identity_anchor` property — returns the extracted identity text.
- `compact()` — always preserves `[IDENTITY]` content; adds other sections
  in priority order until the budget is exhausted.

---

## Requirements

- **FR-ORCH-028** — `assemble_system_prompt()` calls `_render_system_prompt_template()`
  so the static behavior sections from `prompts/system_xochitl.txt` are
  included in the system prompt on every turn.
- **FR-ORCH-029** — `SOUL.md.example` follows the structured four-section
  format (`## [IDENTITY]`, `## [VOICE]`, `## [VALUES]`, `## [BOUNDARIES]`);
  the `[IDENTITY]` section is the load-bearing persona anchor.
- **NFR-ORCH-004** — `SoulEngine.ingest()` extracts the `[IDENTITY]` section
  as `identity_anchor`; if absent, prints a warning and uses a fallback string.
- **NFR-ORCH-005** — `SoulEngine.compact()` always preserves the `[IDENTITY]`
  section content regardless of the `max_tokens` budget.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR029-001` | `SOUL.md.example` contains `## [IDENTITY]` section and does not contain "Chief of Staff" |
| `AC-CR029-002` | After `SoulEngine.ingest()`, `soul.identity_anchor` is non-empty and contains text from the `[IDENTITY]` section |
| `AC-CR029-003` | `SoulEngine.compact(10)` returns text that includes the `[IDENTITY]` section content |
| `AC-CR029-004` | `ContextManager.assemble_system_prompt()` output contains `[GOAL]` (confirming template is wired) |
| `AC-CR029-005` | `ContextManager.assemble_system_prompt()` output contains `[UNCERTAINTY TIERS]` (confirming CR-032 sections reach the model) |
| `AC-CR029-006` | Smoke tests: all 5 ACs confirmed; full suite still passes |

---

## Implementation tasks

- [x] Write `CR-029-persona-anchoring.md`
- [x] Restructure `SOUL.md.example` with four sections; fix "Chief of Staff"
- [x] Update `SoulEngine` — `_identity_anchor` field, `_extract_section()`, `identity_anchor` property, new `compact()`
- [x] Update `assemble_system_prompt()` — wire `_render_system_prompt_template()`; remove behavior from separate parts
- [x] Write `docs/spec/08-test-specs/TEST-ORCH-003-persona.md`
- [x] Update requirements registry and traceability matrix
- [x] Add smoke tests; run full suite

---

## Design notes

- `guard_text` is load-bearing and never compacted — embedding the rendered
  template there is the right place for identity + static behavior guidance.
- `ConversationConfigEngine` output is now part of `guard_text`; the engine
  remains but `assemble_system_prompt()` no longer adds it as a separate
  compactible section. The engine is still useful for standalone use.
- `SoulEngine.compact()` was previously dead code (guard_text bypasses it);
  it is now correct so future callers and tests work properly.
- The `{{SOUL}}` placeholder in `system_xochitl.txt` is replaced with the
  SOUL.md content. If SOUL.md is absent, `SoulEngine.ingest()` returns a
  minimal fallback sentence.
