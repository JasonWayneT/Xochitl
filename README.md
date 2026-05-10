# Xochitl

Terminal-native AI Chief of Staff. Manages personal tasks via Notion (PARA methodology) and runs a full BMAD → SDD → Code generation pipeline for building new applications.

Pronounced *"so-CHEEL"*.

---

## Features

- **Daily task queue** — pulls your top 3 from Notion, tracks WIP, syncs completions back
- **Conversational chat** — intent-classified agent loop with LLM-native skill dispatch
- **BMAD pipeline** — guided Business Model, Architecture, and Design intake for new projects
- **Spec-Driven Development** — requirement management, traceability, and code scaffolding from specs
- **Tiered LLM routing** — local Ollama for fast/simple queries, cloud (Gemini / Claude) for complex work
- **File-safe by default** — reads are automatic; overwrites and deletes require explicit confirmation

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| CLI | `click` |
| Terminal UI | `rich` |
| Database | SQLite |
| Notion | `notion-client` |
| LLM (local) | Ollama `gemma4-e4b` |
| LLM (cloud) | Gemini 1.5 Pro / Flash or Claude |
| Memory | ChromaDB (long-term vector store) |

---

## Installation

```bash
git clone <repo>
cd xochitl
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your Notion token and LLM API keys.

---

## Commands

```bash
xochitl                  # Default: open conversational chat
xochitl chat             # Explicit chat mode
xochitl today            # Refresh daily queue (top 3 tasks)
xochitl done <num>       # Mark a queued task complete
xochitl plan "<name>"    # Decompose a project into tasks
xochitl sync             # Push completed tasks to Notion
xochitl pull             # Fetch latest from Notion
```

---

## BMAD → SDD → Code Pipeline

Xochitl can build applications end-to-end from a plain-English description:

1. **Init** — `"I want to build a fitness app"` → creates `projects/<id>/`
2. **BMAD** — walks through Business Model, Architecture, and Design Specs
3. **SDD** — generates `specs/core-features.md` from BMAD artifacts with structured requirement IDs
4. **Code** — scaffolds application structure and implements requirements
5. **Issues** — analyzes bugs against specs, updates specs, generates fixes

Generated projects live under `projects/<project-id>/` with full traceability back to their requirements.

---

## Project Structure

```
./
├── src/
│   ├── cli.py                 # Entry point
│   ├── chat.py                # Conversational loop & agent dispatch
│   ├── router.py              # TieredRouter (local vs cloud)
│   ├── task_manager.py        # Task CRUD & WIP queue
│   ├── notion_sync.py         # Notion integration
│   ├── database.py            # SQLite schema
│   ├── security.py            # Path sandboxing
│   └── skills/
│       ├── _skill_helpers.py  # Shared utilities (meta I/O, LLM calls, JSON parsing)
│       ├── base.py            # Abstract Skill base class
│       ├── bmad_skill.py      # Project init & BMAD artifacts
│       ├── sdd_skill.py       # Spec generation & requirement CRUD
│       ├── code_skill.py      # Code generation & scaffolding
│       ├── notion_skill.py    # Notion task operations
│       └── orchestrator_skill.py
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
│       ├── .project-meta.yml
│       ├── bmad/
│       ├── specs/
│       └── src/
├── .sdd/                      # SDD config, prompts, and templates
├── smoke_test.py              # Unit tests for pipeline components
├── end_to_end_test.py         # Mocked full pipeline flow
└── AGENTS.md                  # Agent operating rules (read before changing code)
```

---

## Architecture Invariants

- **WIP limit**: `queue` table holds exactly 0–3 rows at all times.
- **No raw SQL outside `src/database.py`**: all DB access is centralized.
- **No LLM calls outside `src/router.py`**: all model calls go through TieredRouter.
- **Sandboxed files**: operations are restricted to allowed roots in `src/security.py`.
- **Permission model**: reads are automatic; overwrites/deletes require user confirmation via `FileTools`.
- **Traceability**: generated code cites requirement IDs (e.g., `# Implements FR-CORE-001`).

---

## Development

```bash
python smoke_test.py        # Unit tests (pipeline components)
python end_to_end_test.py   # Mocked end-to-end pipeline
```

This project is built using its own SDD process. Before making code changes, read `AGENTS.md` — every change must cite a requirement ID (`FR-*`, `NFR-*`, `BUG-*`, etc.) in the commit message.
