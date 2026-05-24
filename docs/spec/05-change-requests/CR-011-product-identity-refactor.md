# CR-011 — Product Identity Refactor: Chief of Staff → JARVIS-Inspired Personal AI System

## Status

Implemented.

## Summary

Retroactively documents a branding and identity refactor made in a single session.
The product description "AI Chief of Staff" was removed from all user-facing strings,
documentation, and system prompts. The replacement framing is "personal AI system,"
with CLAUDE.md and XOCHITL_EXPLAINED.md explicitly noting the JARVIS (Just A Rather
Very Intelligent System) vision as the long-term model for what Xochitl is becoming.

This change affects no runtime behavior. It is a documentation, string, and
constitution update only.

## Motivation

The "Chief of Staff" metaphor was never accurate to the product vision. Xochitl is
modeled after JARVIS — a proactive, intelligent, locally-running system that manages
across all domains of the user's life (tasks, knowledge, building, learning). "Chief
of Staff" implies a narrow organizational role and was introduced as a placeholder.
The user identified this as a drift from the intended vision.

## Affected Files

| File | Change |
|---|---|
| `CLAUDE.md` | Updated project overview line |
| `README.md` | Updated tagline |
| `XOCHITL_EXPLAINED.md` | Updated "What She Is" section; added JARVIS reference |
| `src/chat.py` | Boot banner subtitle |
| `src/cli.py` | Banner constant and CLI docstring |
| `src/context_manager.py` | Identity Guard string and SOUL.md fallback string |
| `docs/spec/00-project-constitution.md` | Product type field |
| `docs/spec/01-bmad-intake.md` | Raw BMAD notes section |

## Affected Requirements

| ID | Type | Change |
|---|---|---|
| `FR-ORCH-012` | functional | Persona loading now references a JARVIS-inspired identity; no behavioral change |
| `NFR-UI-008` | non-functional | New — see below |

## New Requirements Proposed

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `NFR-UI-008` | non-functional | P2 | All user-facing strings, documentation, and system prompt templates describe Xochitl as a personal AI system; no instance of "Chief of Staff" appears in active (non-archive) files |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR011-001` | `NFR-UI-008` | Boot banner | Xochitl starts a chat session | Boot banner is printed | The subtitle reads "Personal AI System", not "Chief of Staff" |
| `AC-CR011-002` | `NFR-UI-008` | Identity Guard | Any chat session runs | System prompt is assembled | The Identity Guard line reads "personal AI system", not "Chief of Staff" |
| `AC-CR011-003` | `NFR-UI-008` | Documentation | Any active doc file is read | The string "Chief of Staff" is searched across non-archive files | Zero matches |

## Implementation Tasks

| ID | Requirement IDs | Task | File | Status |
|---|---|---|---|---|
| `TASK-CR011-001` | `NFR-UI-008` | Replace "Chief of Staff" with "Personal AI System" in boot banner | `src/chat.py` | done |
| `TASK-CR011-002` | `NFR-UI-008` | Replace banner constant and CLI docstring | `src/cli.py` | done |
| `TASK-CR011-003` | `NFR-UI-008` | Replace Identity Guard string and SOUL.md fallback | `src/context_manager.py` | done |
| `TASK-CR011-004` | `NFR-UI-008` | Update CLAUDE.md, README.md, XOCHITL_EXPLAINED.md | docs | done |
| `TASK-CR011-005` | `NFR-UI-008` | Update project constitution and BMAD intake | `docs/spec/00-project-constitution.md`, `docs/spec/01-bmad-intake.md` | done |

## Verification Results

2026-05-22:
- `py_compile` clean on `src/chat.py`, `src/cli.py`, `src/context_manager.py`.
- Grep for "Chief of Staff" in non-archive files returns zero matches.
- No behavioral change — runtime behavior is identical.

## Open Issues

- `archive/REFERENCE_CODE_SNIPPETS.md` still contains "Chief of Staff" references.
  This is intentional — archive files are historical record and are not updated.
