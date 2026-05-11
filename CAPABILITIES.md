# Xochitl Capabilities Manifest

Xochitl is a high-intelligence agentic CLI designed for software engineering, project planning (BMAD), and personal productivity. This document summarizes her verified capabilities as of May 2026.

## 1. Conversational Intelligence (The "Brain")
- **Intent Classification:** Automatically categorizes every turn (Exploration, Planning, Execution, etc.) to choose the best response strategy.
- **Autonomous Exploration:** Chained read-only actions (file searching, reading) to gather context without asking for permission on every step.
- **Safety Gating:** Mandatory plan presentation and explicit user approval before any file writes, deletions, or mutating shell commands.
- **Persona & Memory:** 
  - **Preference Engine:** Remembers and applies your stated preferences across sessions.
  - **Semantic Memory:** Long-term vector-based recall via ChromaDB.
  - **Cultural Voice:** Matriarca persona—warm, supportive, with Latina/Mexican cultural texture.

## 2. SDD Pipeline (The "Engineer")
- **BMAD Intake:** Transforms Business Model, Architecture, and Design artifacts into technical specifications.
- **Project Scaffolding:** Initializes standard project structures (`bmad/`, `specs/`, `src/`) with traceability files.
- **Traceability Enforcement:** Automatically cites requirement IDs (e.g., `# Implements FR-CORE-001`) in generated code.
- **Issue Analysis:** Diagnoses bugs, updates specifications, and generates fix code based on existing requirements.

## 3. Productivity & Workflows
- **Task Management:** Local SQLite-backed queue with a strict WIP (Work-In-Progress) limit of 3.
- **Notion Sync:** Two-way sync of tasks using the PARA methodology.
- **Daily Dashboard:** `xochitl today` command for a prioritized high-signal view of your work.
- **Dynamic Skills:** Can "learn" and persist new workflows as reusable skills in `.xochitl/skills/`.

## 4. Technical Capabilities
- **Agnostic LLM Routing:** Tiered routing between local models (Gemma/Qwen) and cloud models (Claude 3.5/Gemini 1.5 Pro).
- **Security Sandboxing:** Strict path-based permission model preventing access to sensitive system or credential folders.
- **Context Management:** Token-budget discipline with automatic history compaction and fact-injection (CWD, WIP, Platform).
- **Tool Dispatch:** LLM-native skill invocation using `<skill_call>` syntax.

## 5. Command Reference
- `xochitl chat` — Interactive session (default).
- `xochitl today` — Daily prioritized task view.
- `xochitl plan "<project>"` — Decompose goals into tasks.
- `xochitl done <id>` — Complete a task.
- `xochitl sync` — Push/pull from Notion.
- `xochitl authorize <path>` — Grant file access to a new directory.

---
*For detailed implementation requirements, see [docs/spec/02-requirements-registry.md](docs/spec/02-requirements-registry.md).*
