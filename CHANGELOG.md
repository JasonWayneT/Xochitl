# Changelog — Xochitl

All notable changes are documented here at the major milestone level.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Full granular change history is in `docs/spec/05-change-requests/`.

**This project is retired.** Capabilities have been ported to Hermes as plugins and skills.

---

## [Retired] — 2026-05-28

Xochitl's core capabilities (Zettelkasten, BMAD pipeline, Notion sync, memory) have been ported to [Hermes](https://github.com/hermes-cli/hermes) as user plugins and skills. The Xochitl skin for Hermes preserves the persona. This repo is archived.

---

## [0.9.0] — 2026-05

### Added
- Procedural workflow memory — save and replay multi-step task sequences by intent (CR-041, CR-042)
- Controlled initiative system — proactive alerts by category without unsolicited interruptions (CR-038)
- Terminal visual grammar — semantic line prefixes, 80-column wrap, multi-step progress formatting (CR-039)
- Compact reasoning disclosure — action+body pairing for skill results (CR-040)
- Event bus (`XochitlEventEmitter`) — groundwork for future web SSE layer

### Changed
- BackgroundReview daemon now writes structured JSON facts to `memory_facts` table alongside free-text KB files
- Context assembly refactored into a strict 5-layer priority stack; layers 3–5 compact proportionally under token pressure

---

## [0.8.0] — 2026-04

### Added
- LanceDB semantic memory with HyDE recall — hypothetical answer embedded before search for higher relevance
- Separate `workflow_intents` embedding index — procedural memory isolated from semantic facts
- Session token budget governor — progressive local-only routing as budget depletes
- ActionGovernor / SafeExecutor — explicit user approval gate for all write, delete, and mutating shell operations (CR-037)

### Fixed
- Staged message guard — clears runaway skill-chain loops after 6 consecutive staged messages without real user input

---

## [0.7.0] — 2026-03

### Added
- Zettelkasten skill — note creation with 4-tag budget, similarity-gated tag quarantine, auto-promotion after 3 uses
- Dynamic skill system — user-defined skills in `~/.xochitl/skills/`; auto-proposed after repeating patterns
- Orchestrator skill — delegates across other skills for multi-step coordination
- Web lookup skill — DuckDuckGo search + page fetch with URL normalization

### Changed
- TieredRouter expanded with `_FORCE_LOCAL_CATEGORIES` and `_LOCAL_SPECIALIZED_CATEGORIES` — coding tasks now route to `qwen2.5-coder` automatically

---

## [0.5.0] — 2026-02

### Added
- BMAD skill — "I want to build X" scaffolds `projects/<id>/bmad/` and walks Business Model, Architecture, Design
- SDD skill — generates requirements docs with `FR-*` IDs from BMAD artifacts
- Code skill — scaffolds `projects/<id>/src/` with code citing requirement IDs
- Notion sync (PARA methodology) — `xochitl sync` / `xochitl pull`

---

## [0.1.0] — 2026-01

### Added
- Initial release: terminal chat loop with tiered LLM routing (local Ollama primary, cloud fallback)
- SQLite task queue — WIP limit of 3 rows enforced at all times
- Path sandboxing via `src/security.py` — file operations restricted to authorized roots
- `xochitl today`, `xochitl done`, `xochitl plan` CLI commands
