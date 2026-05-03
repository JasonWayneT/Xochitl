# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Xochitl (pronounced "so-CHEEL") is a terminal-native AI Chief of Staff. It manages personal tasks via Notion (PARA methodology) and supports a full BMAD → SDD → Code Generation pipeline for building new applications.

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
│   └── skills/                # Pipeline logic
│       ├── bmad_skill.py      # Project init & BMAD artifacts
│       ├── sdd_skill.py       # Spec generation & requirement CRUD
│       └── code_skill.py      # Code generation & scaffolding
├── projects/                  # Applications built WITH Xochitl
│   └── <project-id>/
│       ├── .project-meta.yml  # Project metadata
│       ├── bmad/              # BMAD artifacts (business-model.md, etc.)
│       ├── specs/             # SDD requirements (FR-*, traceability.json)
│       └── src/               # Generated code
├── .sdd/                      # SDD configuration and prompts
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
