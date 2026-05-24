# CR-012 — UserProfileEngine and Me.md User Identity File

## Status

Implemented.

## Summary

Retroactively documents two additions made in a single session:

1. **`UserProfileEngine`** — a new context engine in `src/context_manager.py` that
   loads a `Me.md` file from the persona search path (`cwd/.xochitl/Me.md` →
   `~/.xochitl/Me.md` → project-root `Me.md.example`) and injects its content into
   every system prompt as an `## About the User` block, positioned immediately after
   the Identity Guard and before the Facts block.

2. **`Me.md` file format** — a portable 50–80 line plain-text identity file
   that briefs Xochitl on who the user is, their domains, how they think, how they
   work, what they are building, and how they want AI to engage with them. The format
   is model-agnostic: the same file can be pointed at any AI tool. A `Me.md.example`
   template is included in the project root.

## Motivation

Xochitl had no persistent, structured way to know who the user is across sessions.
The `PreferenceEngine` and `MemoryEngine` store reactive observations, but there was
no proactive identity layer. Without this, every session starts cold on basic facts
(the user's role, domains, communication preferences, active projects). The Me.md
pattern, popularized by Nick Milo's "AI OS" framework, solves this with a single
author-maintained file rather than implicit accumulation.

## Architecture

```
System prompt assembly order (priority: high → low):
  1. Language hard-guard            — never removed
  2. Identity Guard + SOUL.md       — never removed
  3. About the User (Me.md)         — NEW — max 600 tokens, compacted from bottom
  4. Facts block                    — never removed
  5. Conversation config            — compacted
  6. Skills hint                    — always present
  7. Preferences                    — compacted
  8. Memory                         — compacted first
  9. File context                   — dropped if budget exhausted
```

## Affected Requirements

| ID | Change |
|---|---|
| `FR-ORCH-012` | Persona loading now includes a user-profile layer alongside SOUL.md and conversation config |
| `NFR-PERF-004` | Token budget enforcement updated to account for `user_profile_text`; budget_used_pct includes it |

## New Requirements Proposed

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `FR-ORCH-022` | functional | P1 | `UserProfileEngine` loads `Me.md` from the persona search path and injects its content as `## About the User` in every system prompt, positioned between the Identity Guard and the Facts block |
| `NFR-ORCH-001` | non-functional | P2 | `Me.md` is designed to remain under 80 lines / 600 tokens so it never meaningfully compresses the token budget available to file context or memory |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR012-001` | `FR-ORCH-022` | Me.md present | `~/.xochitl/Me.md` exists with content | System prompt is assembled | The block `## About the User` followed by Me.md content appears between the Identity Guard and Facts sections |
| `AC-CR012-002` | `FR-ORCH-022` | Me.md absent | No Me.md file found in any search path | System prompt is assembled | The system prompt is unchanged — no empty section is injected |
| `AC-CR012-003` | `NFR-ORCH-001` | Token compaction | Token budget is exceeded | `user_profile.compact()` runs | Output preserves the top sections (Who I am, Domains) and truncates from the bottom; a compaction note is appended |
| `AC-CR012-004` | `FR-ORCH-022` | Search path priority | Both `cwd/.xochitl/Me.md` and `~/.xochitl/Me.md` exist | `UserProfileEngine.ingest()` runs | The `cwd/.xochitl/Me.md` version is used (project-local overrides global) |

## Implementation Tasks

| ID | Requirement IDs | Task | File | Status |
|---|---|---|---|---|
| `TASK-CR012-001` | `FR-ORCH-022` | Add `UserProfileEngine` class with `ingest()`, `assemble()`, `compact()` | `src/context_manager.py` | done |
| `TASK-CR012-002` | `FR-ORCH-022` | Instantiate `self.user_profile` in `ContextManager.__init__()` | `src/context_manager.py` | done |
| `TASK-CR012-003` | `FR-ORCH-022` | Call `self.user_profile.ingest()` in `ContextManager.ingest()` | `src/context_manager.py` | done |
| `TASK-CR012-004` | `FR-ORCH-022`, `NFR-PERF-004` | Wire `user_profile_text` into `assemble_system_prompt()` — both under-budget and over-budget paths | `src/context_manager.py` | done |
| `TASK-CR012-005` | `NFR-PERF-004` | Add `user_profile.assemble()` to `budget_used_pct` | `src/context_manager.py` | done |
| `TASK-CR012-006` | `NFR-ORCH-001` | Write `~/.xochitl/Me.md` with user's actual profile content | `~/.xochitl/Me.md` | done |
| `TASK-CR012-007` | `NFR-ORCH-001` | Create `Me.md.example` template in project root | `Me.md.example` | done |

## Verification Results

2026-05-22:
- `py_compile` clean on `src/context_manager.py`.
- `~/.xochitl/Me.md` exists and is 80 lines (~550 tokens estimated).
- `Me.md.example` present in project root.
- Manual inspection: `UserProfileEngine` follows the same lifecycle pattern as
  `SoulEngine` (ingest → assemble → compact); search path uses `_persona_search_paths`
  consistent with all other persona files.
- Smoke/e2e tests not re-run; changes are additive to the context assembly path
  and non-breaking — Me.md absent path returns empty string, existing behavior
  is unchanged.

## Open Issues

- Smoke tests should be extended to cover `AC-CR012-001` through `AC-CR012-004`.
- `Me.md` content is user-maintained; no validation or schema enforcement exists.
  If the file grows beyond ~80 lines the compaction path activates, which is
  acceptable but not signaled to the user.
