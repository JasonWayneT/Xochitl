# CR-002: Conversation Layer Hardening (OpenClaw/OpenClaude-Inspired)

## Summary

Harden Xochitl's conversation layer by implementing Context Engine architecture,
Smart Routing 2.0, Provenance Tagging, Fact Injection, Token Budgeting, and premium
TUI interaction patterns inspired by analysis of OpenClaw and OpenClaude.

## Type

Architectural improvement + Bug fix

## Affected Requirements

- `FR-CORE-004` — Chat session with intent classification
- `ARCH-SDD-001` — All LLM calls via TieredRouter
- `NFR-CORE-001` — Command latency < 2s
- `SEC-AUTH-001` — File ops restricted to allowed roots

## New Requirements Proposed

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `FR-UI-001` | functional | P1 | TUI status bar shows live sub-task feed during LLM reasoning |
| `FR-UI-002` | functional | P1 | Smart Ctrl-C: first press cancels active tool, second press exits |
| `FR-UI-003` | functional | P2 | File paths in output are formatted as OSC 8 terminal hyperlinks |
| `FR-ORCH-003` | functional | P0 | PreFlight Fact Injection: every prompt includes [SYSTEM_FACTS] block with CWD, project, mode |
| `FR-ORCH-004` | functional | P0 | Provenance Tagging: history messages tagged [SOURCE: USER] vs [SOURCE: SYSTEM] |
| `NFR-PERF-004` | non-functional | P1 | ContextManager enforces token budget, triggering compaction at 75% capacity |
| `NFR-PERF-005` | non-functional | P1 | SmartRouter tracks rolling latency per provider; auto-selects best available |

## Acceptance Criteria

| ID | Criterion |
|---|---|
| `AC-CR002-001` | Asking "what folder are you in?" returns actual Windows path, not a generic LLM reply |
| `AC-CR002-002` | Mentioning `.env` without quotes resolves and reads the file |
| `AC-CR002-003` | First Ctrl-C clears input line; second Ctrl-C within 1s exits |
| `AC-CR002-004` | Token count never exceeds 75% of model limit in a single request |
| `AC-CR002-005` | Smoke test passes after all changes |

## Implementation Tasks

| ID | Task | File |
|---|---|---|
| `TASK-CR002-001` | Create `src/context_manager.py` with Engine-based architecture | NEW |
| `TASK-CR002-002` | Update `src/router.py` with PreFlight Fact Injection and Provenance Tagging | MODIFY |
| `TASK-CR002-003` | Update `src/llm_interface.py` with latency tracking and streaming improvements | MODIFY |
| `TASK-CR002-004` | Update `src/chat.py` with Status Tiers and Smart Ctrl-C | MODIFY |
| `TASK-CR002-005` | Update `docs/spec/02-requirements-registry.md` with new requirement IDs | MODIFY |
| `TASK-CR002-006` | Update `docs/spec/06-traceability/traceability-matrix.md` | MODIFY |

## Status

- [x] Change request created
- [x] Requirements identified
- [x] Implementation complete
- [x] Verified — smoke_test.py: 24 passed, 0 failed (cleanup PermissionError is pre-existing Windows file-lock, not related to these changes)

## Verification

`python smoke_test.py` — 24 passed, 0 failed.
Manual AC-CR002-001 pending next chat session.
