# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Xochitl (pronounced "so-CHEEL") is a terminal-native personal AI system — modeled after the JARVIS vision. She manages personal tasks via Notion (PARA methodology) and supports a full BMAD → SDD → Code Generation pipeline for building new applications.

## Tech Stack

- **Language**: Python 3.12+
- **CLI**: `click`
- **Terminal UI**: `rich`
- **Database**: SQLite (local task storage and session history)
- **Notion**: `notion-client` library
- **LLM**: Tiered routing via `src/router.py`
  - **Local**: `gemma4-e4b` (Task management, simple QA, file reads)
  - **Cloud**: Gemini 1.5 Pro / Flash or Claude (Complex code, architecture, BMAD)
- **Vector DB**: ChromaDB for long-term memory

## Agent Operating Rules

This project uses BMAD-informed Spec Driven Development. **Read `AGENTS.md` before making any code changes.** The prime directive is: documentation chain first, code second.

Required reading order before coding:
1. `docs/spec/00-project-constitution.md`
2. `docs/spec/01-bmad-intake.md`
3. `docs/spec/02-requirements-registry.md`
4. Relevant files under `docs/spec/03-feature-specs/` through `docs/spec/09-known-issues/`

Every code change must cite at least one requirement ID (`FR-*`, `NFR-*`, `ARCH-*`, etc.) in the commit message or implementation notes.

## Project Structure

```
./
├── src/
│   ├── cli.py                 # Entry point
│   ├── chat.py                # Conversational loop & intent classification
│   ├── router.py              # TieredRouter (Local vs Cloud)
│   ├── task_manager.py        # Task CRUD & queue management
│   ├── notion_sync.py         # Notion integration
│   ├── database.py            # SQLite schema
│   ├── security.py            # Path sandboxing
│   ├── events.py              # Thread-safe event bus for web SSE layer (FR-ORCH-020)
│   └── skills/                # Pipeline logic
│       ├── bmad_skill.py      # Project init & BMAD artifacts
│       ├── sdd_skill.py       # Spec generation & requirement CRUD
│       └── code_skill.py      # Code generation & scaffolding
├── docs/spec/                 # Xochitl-as-a-product SDD specs
│   ├── 00-project-constitution.md
│   ├── 01-bmad-intake.md
│   ├── 02-requirements-registry.md
│   ├── 03-feature-specs/
│   ├── 04-design-specs/
│   ├── 05-change-requests/
│   ├── 06-traceability/traceability-matrix.md
│   ├── 07-decisions/
│   ├── 08-test-specs/
│   └── 09-known-issues/
├── projects/                  # Applications built WITH Xochitl
│   └── <project-id>/
│       ├── .project-meta.yml  # Project metadata
│       ├── bmad/              # BMAD artifacts (business-model.md, etc.)
│       ├── specs/             # SDD requirements (FR-*, traceability.json)
│       └── src/               # Generated code
├── .sdd/                      # SDD configuration, prompts, and templates
│   ├── config.yml
│   ├── prompts/               # LLM prompts for the SDD pipeline
│   └── templates/             # Document templates for generated projects
├── AGENTS.md                  # Agent operating rules (SDD prime directive)
└── requirements.txt
```

## BMAD → SDD → Code Pipeline

1. **Initialization**: `xochitl` -> "I want to build a fitness app" -> Creates `projects/<id>/`.
2. **BMAD**: Walk through Business Model, Architecture, and Design Specs.
3. **SDD**: Generate `specs/core-features.md` from BMAD artifacts.
4. **Code**: Scaffold application structure and implement requirements from specs.
5. **Issue Tracking**: Analyze bugs against specs, update specs, and generate code fixes.

## Commands

```bash
xochitl today           # Refresh daily queue (top 3 tasks)
xochitl done <num>      # Mark task complete
xochitl chat            # (Default) Interactive conversational session
xochitl plan "<name>"   # Decompose project into tasks
xochitl sync            # Push completed tasks to Notion
xochitl pull            # Fetch latest from Notion
```

## Architecture: Key Invariants

- **WIP limit**: `queue` table holds exactly 0–3 rows.
- **Permission model**: Reads are automatic; overwrites/deletes require user confirmation via `FileTools`.
- **Traceability**: All generated code must reference requirement IDs (e.g., `# Implements FR-CORE-001`).
- **Sandboxing**: File operations are restricted to allowed roots defined in `security.py`.

## Development & Testing

- **Smoke Test**: `python smoke_test.py` (Unit tests for pipeline components)
- **E2E Test**: `python end_to_end_test.py` (Mocked full pipeline flow)
- **Linting**: No raw SQL outside `database.py`; all LLM calls via `router.py`.

## Code Quality Standards

These apply to all new code. Violations block merge. Auditing existing code is tracked separately.

### NFR-DEV-001 — Conventional Commits scope (required)

Every commit must include a scope from the closed list below. Scope-less commits are prohibited.

| Scope | Area |
|---|---|
| `core` | Core CLI and task queue (`cli.py`, `task_manager.py`) |
| `api` | External integrations (Notion, LLM providers) |
| `ui` | Terminal UI (`rich` output, prompts) |
| `data` | Database schema, migrations (`database.py`) |
| `auth` | Authentication and security sandboxing (`security.py`) |
| `sdd` | SDD pipeline (BMAD intake, spec gen, code gen) |
| `orch` | Orchestration (`context_manager.py`, `chat.py`, `router.py`, `background_review.py`) |
| `skill` | All files under `src/skills/` |
| `mem` | Memory and retrieval (`memory.py`, ChromaDB layer) |
| `ztk` | Zettelkasten note engine |
| `dev` | Standards, tooling, CI, documentation changes |

Examples: `feat(orch):`, `fix(skill):`, `docs(dev):`, `refactor(data):`

### NFR-DEV-002 — Type hints on all public functions

All public function signatures must include argument type hints and a return type annotation.
Use `Optional[T]` or `T | None` for nullable returns. No unannotated public signatures.

### NFR-DEV-003 — No bare `except:`

Always catch a specific exception type or `Exception` with a named variable:

```python
# Good
except Exception as exc:
    raise RouterError("...") from exc

# Bad
except:          # catches KeyboardInterrupt, SystemExit — dangerous
    pass
except Exception:  # swallows exc silently — no chain
    return None
```

Never `except BaseException:` unless in a top-level shutdown path with explicit justification.

### NFR-DEV-004 — Google-style docstrings on public methods

Priority: skill `can_handle()`, `execute()`, `tool_definition()` interfaces. Required sections:
one-line summary, `Args:`, `Returns:`, `Raises:` (omit only if truly none).

```python
def execute(self, query: str, context: dict) -> SkillResult:
    """Fetch live weather and format it for terminal output.

    Args:
        query: Natural-language weather request from the user.
        context: Assembled context dict from ContextManager.

    Returns:
        SkillResult with formatted weather string or error message.

    Raises:
        GeocodingError: If the location cannot be resolved to coordinates.
    """
```

### NFR-DEV-005 — Testing checklist

Every test function must satisfy all of these:

- [ ] Happy path covered
- [ ] At least one edge case or failure path covered
- [ ] External dependencies (LLM, HTTP, filesystem) mocked at the provider boundary
- [ ] Output is deterministic (no random seeds, no real timestamps without freezing)
- [ ] The test would **fail** if the logic under test were removed or broken

Real API calls are never allowed in unit tests. Use `unittest.mock` or `pytest-recording`.

### NFR-DEV-006 — Security checklist

Every code change touching I/O or user input must verify:

- [ ] No `eval()`, `exec()`, or `pickle.loads()` on user-controlled or LLM-generated input
- [ ] No bare resource leaks — file handles, threads, sockets closed in `finally` or `with`
- [ ] All `urlopen()` / `httpx.get()` calls carry an explicit `timeout=` parameter
- [ ] `subprocess.run()` never uses `shell=True` with generated content
- [ ] No API keys, secrets, or credentials in source files (use env vars via `.env`)
