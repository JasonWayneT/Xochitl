---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/product-brief.md
workflowType: 'architecture'
project_name: 'Xochitl'
user_name: 'Jason'
date: '2026-05-03'
lastStep: 8
status: 'complete'
completedAt: '2026-05-03'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements:**
The system is an autonomous, intent-driven CLI framework ("Matriarca") capable of executing complex background tasks (Notion sync, BMAD SDD generation, web research) while maintaining a persistent conversational loop. It relies on a fast-inference intent router to map user input to modular skills dynamically.

**Non-Functional Requirements:**
Architectural decisions are heavily constrained by local-first requirements. All state must be reliably persisted locally via Write-Ahead Logging (WAL) and SQLite. Retrieval must be extremely fast (<100ms for profiles, <550ms for reranked semantic search), requiring highly optimized local vector databases and cross-encoders. Strict permission-gating and JSONL transaction logging are mandatory.

**Scale & Complexity:**
The project represents a high-complexity system bridging multiple distinct domains (LLM orchestration, databases, file system events, external APIs).

- Primary domain: CLI Agent Framework
- Complexity level: High
- Estimated architectural components: 6-8 core modules (Router, LLM Engine, 5-Tier Memory Controller, Notion Sync, CLI Interface, Permission Gatekeeper)

### Technical Constraints & Dependencies

- Must run completely offline for Tier 0-3 tasks (Local models).
- Requires LanceDB for vector storage and SQLite for state management.
- Requires Qwen3-Reranker and Gemma-4 models.

### Cross-Cutting Concerns Identified

- **Local Data Sovereignty:** Ensuring zero data leaks to external APIs for local tiers.
- **State Reliability:** Resolving state conflicts between external APIs (Notion) and the local master cache.
- **Auditability:** Pervasive transaction logging across all tools.

## Starter Template Evaluation

### Primary Technology Domain

Python CLI Application (Brownfield) based on project requirements analysis and existing workspace state.

### Starter Options Considered

- **Custom Python (Existing)**: Retaining the existing `pyproject.toml` and `src/` layout.
- **Typer/Click Template**: Standard CLI template generators (Discarded, project is already initialized).

### Selected Starter: Custom Python Setup (Brownfield)

**Rationale for Selection:**
The project is an existing application with an established Python module structure (`src/*.py`), `requirements.txt`, and `pyproject.toml`. Instead of generating a new boilerplate, we will formalize the architectural decisions embedded in the current setup.

**Initialization Command:**

```bash
# N/A - Brownfield project. Dependencies can be installed via:
pip install -r requirements.txt
# or via pip local install
pip install -e .
```

**Architectural Decisions Provided by Foundation:**

**Language & Runtime:**
Python 3.x, utilizing standard typing for type safety.

**Styling Solution:**
N/A (CLI Tool). Console output styling handled via Python CLI libraries.

**Build Tooling:**
Standard Python packaging configured via `pyproject.toml` and `setuptools`/`wheel`.

**Testing Framework:**
Assumed `pytest` or `unittest` (standard Python testing ecosystem).

**Code Organization:**
Flat `src/` module layout separating concerns (`bmad.py`, `chat.py`, `llm_interface.py`, `memory.py`, `database.py`).

**Development Experience:**
Local virtual environments (`venv`) and standard pip dependency management.

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Local Database Selection (SQLite)
- Vector Database Selection (LanceDB)
- Model Architecture (Gemma-4 for reasoning/routing, Qwen3 for reranking)
- Transaction Logging format (JSONL)

**Important Decisions (Shape Architecture):**
- File System permission enforcement (Gating logic)
- Notion Synchronization logic (Local cache as Master)

### Data Architecture

- **Primary State Database:** SQLite (Chosen for robust local, file-based persistence. *Note: Overriding PRD blueprint, Markdown WAL is dropped entirely in favor of SQLite as the sole master source of truth for state*).
- **Semantic Vector Database:** LanceDB (Embedded, serverless, optimized for local disk-based indexing).
- **Sync Strategy:** Bi-directional sync with Notion, resolving all state conflicts in favor of the local SQLite cache.

### Authentication & Security

- **Authentication:** N/A (Local execution only).
- **File System Security:** "Permission-on-Write" policy. The system maintains a persistent registry of authorized directories in `~/.xochitl/config.toml` and requires explicit `y/n` human confirmation for any modification outside this registry.
- **Auditability:** 100% of tool executions and system-level reads/writes are recorded in a JSONL Transaction Log.

### API & Communication Patterns

- **Intent Routing:** User input is parsed by a local fast-inference model (e.g., Gemma-4-E2B) acting as a Controller, which invokes and parameterizes local Python modular skills.
- **External API Communication:** Restricted to explicit Tier 4 actions (e.g., Web Search, Notion Sync). Tiers 0-3 must operate offline.

### Frontend Architecture

- **Interface:** Terminal Native (CLI).
- **Output:** Conversational Markdown to `stdout` for humans, JSONL to `stdout` or logs for programmatic pipelining.

### Infrastructure & Deployment

- **Runtime:** Python 3.x.
- **Deployment:** Installed locally via `pip install -e .`.
- **Environment Management:** API keys (Notion, optional LLM fallbacks) managed via `.env`.

### Decision Impact Analysis

**Implementation Sequence:**
1. Transaction Logging & Permission Gatekeeper (Security First).
2. SQLite Local State Cache & Notion Sync Module.
3. LanceDB Integration & JIT Context Retrieval.
4. Gemma/Qwen Model Orchestration (The Brain).

**Cross-Component Dependencies:**
- The dropping of Markdown WAL simplifies the database module but means vector embedding processes must read directly from SQLite rather than watching flat files for `on_change` events.

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Critical Conflict Points Identified:**
4 areas where AI agents could make different choices (Type safety, Naming, Error Handling, Logging Formats).

### Naming Patterns

**Database Naming Conventions:**
- Tables: Plural `snake_case` (e.g., `tasks`, `conversations`).
- Columns: `snake_case` (e.g., `created_at`, `user_intent`).
- Foreign Keys: `[table_singular]_id` (e.g., `session_id`).

**Code Naming Conventions (Strict PEP 8):**
- Classes: `PascalCase` (e.g., `TieredMemoryRouter`).
- Functions & Variables: `snake_case` (e.g., `sync_notion_state()`).
- Constants: `UPPER_SNAKE_CASE` (e.g., `WIP_LIMIT`).

### Structure Patterns

**File Structure Patterns:**
- Flat module structure in `src/`. No deep nesting.
- `__init__.py` files used only to expose public API surfaces.

### Format Patterns

**Data Exchange Formats (JSONL Logs):**
- All JSON/JSONL keys must use `snake_case` to natively map to Python dictionaries and SQLite rows.
- Dates must be ISO-8601 strings (e.g., `2026-05-03T14:30:00Z`).

**CLI Output Formats:**
- Rich Markdown to `stdout` for the conversational loop.
- Raw JSONL to `stdout` (or piped file) when invoked programmatically.

### Process Patterns

**Error Handling Patterns:**
- Do not catch generic `Exception` unless at the absolute top of the CLI loop.
- Use custom exception classes (e.g., `XochitlPermissionError`, `StateConflictError`).
- Return non-zero exit codes immediately upon catastrophic failure (e.g., `sys.exit(1)`).

**Type Safety:**
- All function signatures MUST include Python type hints (`def process_intent(text: str) -> dict:`).
- Use `typing.Optional` explicitly rather than assuming `None`.

### Enforcement Guidelines

**All AI Agents MUST:**
- Adhere strictly to PEP 8 and the defined naming conventions.
- Provide type hints for all functions.
- Output JSON with `snake_case` keys.

**Pattern Enforcement:**
- Verified during SDD implementation. Code lacking type hints or breaking naming conventions will fail agent-driven peer review.

## Project Structure & Boundaries

### Complete Project Directory Structure

```text
Xochitl/
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── README.md
├── src/
│   ├── __init__.py
│   ├── cli.py             # Entry point & interactive loop
│   ├── chat.py            # Conversational formatting & history
│   ├── router.py          # Intent classification & gatekeeper (FR1-FR4)
│   ├── llm_interface.py   # Gemma/Qwen model bindings
│   ├── memory.py          # 5-Tier Memory & LanceDB integration (FR5-FR11)
│   ├── context_loader.py  # JIT Retrieval & Verify-on-Call logic
│   ├── database.py        # SQLite connection management
│   ├── notion_sync.py     # Notion API integration (FR12-FR15)
│   ├── task_manager.py    # Local WIP & backlog queue handling
│   ├── file_tools.py      # File system manipulation
│   ├── security.py        # Permission gating & JSONL logging (FR24-FR27)
│   ├── tools.py           # Web research & general tool schemas (FR20-FR23)
│   ├── bmad.py            # BMAD pipeline orchestrator (FR16-FR19)
│   └── skills/            # Modular skill definitions
└── tests/
    ├── unit/
    └── integration/
```

### Architectural Boundaries

**API Boundaries:**
- **External Services:** Only `notion_sync.py` and `tools.py` (web research) are permitted to make outbound network requests. All other modules operate completely offline.
- **LLM Integration:** All model inference must pass through `llm_interface.py` to ensure local execution compliance.

**Component Boundaries:**
- **State Management:** Only `database.py` is permitted to execute write operations against the SQLite state cache.
- **File System:** Only `security.py` can authorize directory writes, executed via `file_tools.py`.

### Requirements to Structure Mapping

**Feature/Epic Mapping:**
- **Orchestration (FR1-FR4):** `src/router.py`, `src/cli.py`
- **Memory (FR5-FR11):** `src/memory.py`, `src/context_loader.py`
- **Notion Sync (FR12-FR15):** `src/notion_sync.py`, `src/task_manager.py`
- **BMAD Pipeline (FR16-FR19):** `src/bmad.py`
- **Research (FR20-FR23):** `src/tools.py`, `src/chat.py`
- **Security (FR24-FR27):** `src/security.py`, `src/database.py`

### File Organization Patterns

**Configuration Files:**
- `~/.xochitl/config.toml`: Persistent user profile (Tier 1 memory) and authorized directory registry.
- `.env`: Secure credentials loaded at runtime by `cli.py`.

**Test Organization:**
- Unit tests co-located in `tests/unit/` mirroring the `src/` file structure (e.g., `test_router.py`).

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:**
High. The combination of Python, SQLite (for state), and LanceDB (for embedded vectors) provides a stable, zero-dependency local runtime that fulfills the offline-first constraints.

**Pattern Consistency:**
High. PEP 8, snake_case JSON outputs, and comprehensive type-hinting form a unified, coherent pattern for AI agents to follow.

**Structure Alignment:**
High. The flat `src/` directory structure perfectly supports the component boundaries and ensures that external API calls and disk writes remain cleanly isolated.

### Requirements Coverage Validation ✅

**Functional Requirements Coverage:**
100% Coverage. All 27 FRs are explicitly mapped to specific Python modules (e.g., FR24-FR27 to `src/security.py`).

**Non-Functional Requirements Coverage:**
100% Coverage. Performance is supported by local model execution; Security is enforced by architectural boundaries; Reliability is guaranteed by shifting from Markdown WAL to SQLite as the master cache.

### Implementation Readiness Validation ✅

**Decision Completeness:**
Complete. Database, routing, API restrictions, and infrastructure decisions are fully finalized.

**Structure Completeness:**
Complete. Every required file for the MVP is defined in the project tree.

**Pattern Completeness:**
Complete. Strict rules for naming, errors, and formatting are documented.

### Gap Analysis Results

**Nice-to-Have Gaps:**
- Implementing pre-commit hooks to automatically enforce the PEP 8 and type-hinting patterns prior to CI/CD.

### Validation Issues Addressed

None. The architecture required no major corrections during final validation.

### Architecture Completeness Checklist

**Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed
- [x] Technical constraints identified
- [x] Cross-cutting concerns mapped

**Architectural Decisions**
- [x] Critical decisions documented with versions
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**Implementation Patterns**
- [x] Naming conventions established
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented

**Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped
- [x] Requirements to structure mapping complete

### Architecture Readiness Assessment

**Overall Status:** READY FOR IMPLEMENTATION

**Confidence Level:** High

**Key Strengths:**
- Extremely rigid data sovereignty and security boundaries.
- Simplified state management (SQLite) reduces synchronization bugs.
- Clear, unambiguous file mapping for future AI agent implementation.

**Areas for Future Enhancement:**
- Automated linting enforcement tools.
- Granular performance tracing for the fast-inference router.

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all architectural decisions exactly as documented.
- Use implementation patterns consistently across all components.
- Respect project structure and boundaries.
- Refer to this document for all architectural questions.

**First Implementation Priority:**
Initialize SQLite local state cache and implement the foundational transaction logging & permission gatekeeper (`src/security.py`).