# Xochitl Project Map (Agnostic Onboarding)

> **Agent Instruction:** Read this file FIRST to understand the workspace without scanning every directory.

## 1. Tech Stack
- **Core:** Python 3.12+ (Async, standard library preference)
- **Database:** SQLite (src/database.py), ChromaDB (src/memory.py)
- **CLI:** Typer/Click-based (src/cli.py)
- **LLMs:** Multi-provider (src/llm_interface.py)
- **Intelligence:** Intent classification (src/intent.py), Unified Context (src/context_manager.py)

## 2. Directory Map
- `src/` — Core logic.
  - `skills/` — Code-backed skills (SDDs, BMAD, Code Ops).
  - `router.py` — Turn-by-turn routing logic.
- `.xochitl/skills/` — **Single Source of Truth** for conversational workflows (Agent-agnostic).
- `docs/spec/` — Source of truth for requirements and change requests.
- `archive/` — Reference snippets and legacy architecture docs.

## 3. Core Workflows
1. **Research First:** Always check `docs/spec/` and `src/` before proposing changes.
2. **Intent Loop:** Exploration -> Planning -> Approval -> Execution -> Validation.
3. **Requirement IDs:** Citations (e.g., `FR-ORCH-012`) are mandatory in code comments.
4. **Skill Dispatch:** Use `<skill_call name="X">{}</skill_call>` for tools.

## 4. Current State (Sprint Status)
- **Active:** Hardening the Conversational Intelligence layer (CR-004).
- **Recent:** Consolidated `.agent`, `.agents`, and `.claude` bloat into `.xochitl/skills/`.
- **Goal:** Enable agent-agnostic fast-onboarding via this map.

## 5. Quick Links
- [Capabilities Manifest](CAPABILITIES.md)
- [Requirements Registry](docs/spec/02-requirements-registry.md)
- [Traceability Matrix](docs/spec/06-traceability/traceability-matrix.md)
- [System Prompt Template](prompts/system_xochitl.txt)
