# Xochitl SDD Spec Index

**Project:** Xochitl (Matriarca)
**Version:** 1.1.0
**Date:** 2026-05-03
**Source:** Derived from BMAD planning artifacts in `_bmad-output/planning-artifacts/`

## Overview

All code in this project must reference at least one requirement ID using the comment pattern:
`# Implements <ID>` or `# Implements <ID>, <ID>`

## Requirement Domains

| Domain | Prefix | File | Count |
|--------|--------|------|-------|
| Orchestration & Routing | `FR-ORCH` | `functional/FR-ORCH.md` | 4 |
| Tiered Memory & RAG | `FR-MEM` | `functional/FR-MEM.md` | 7 |
| Task Management & Notion | `FR-TASK` | `functional/FR-TASK.md` | 4 |
| BMAD/SDD Pipeline | `FR-BMAD` | `functional/FR-BMAD.md` | 4 |
| Research & Augmented AI | `FR-RES` | `functional/FR-RES.md` | 4 |
| Security & System Integrity | `FR-SEC` | `functional/FR-SEC.md` | 4 |
| UX & Presentation | `FR-UX` | `functional/FR-UX.md` | 2 |
| Performance | `NFR-PERF` | `non-functional.md` | 3 |
| Reliability | `NFR-REL` | `non-functional.md` | 2 |
| Security NFRs | `NFR-SEC` | `non-functional.md` | 2 |
| Auditability | `NFR-AUD` | `non-functional.md` | 1 |
| Sync Integrity | `NFR-SYNC` | `non-functional.md` | 1 |
| Research Constraints | `NFR-RES` | `non-functional.md` | 1 |

## Full Requirement ID Registry

### Functional Requirements

| ID | Title | BMAD Ref | Module |
|----|-------|----------|--------|
| FR-ORCH-001 | Intent Classification with Confidence Gating | FR1 | `src/router.py` |
| FR-ORCH-002 | Dynamic Skill Invocation | FR2 | `src/router.py` |
| FR-ORCH-003 | Persistent Conversational Loop | FR3 | `src/cli.py` |
| FR-ORCH-004 | Tool Outcome Narrative | FR4 | `src/chat.py` |
| FR-MEM-001 | Working Memory — Tier 0 | FR5 | `src/memory.py` |
| FR-MEM-002 | User Profile — Tier 1 | FR6 | `src/memory.py` |
| FR-MEM-003 | Markdown Knowledge Base — Tier 2 | FR7 | `src/memory.py` |
| FR-MEM-004 | Vector DB Semantic Search — Tier 3 | FR8 | `src/memory.py` |
| FR-MEM-005 | Reranking Protocol | FR9 | `src/memory.py` |
| FR-MEM-006 | Session Archiving & Ingestion | FR10 | `src/memory.py` |
| FR-MEM-007 | Verify-on-Call Protocol | FR11 | `src/context_loader.py` |
| FR-TASK-001 | SQLite State Cache with PARA Mapping | FR12 | `src/task_manager.py`, `src/database.py` |
| FR-TASK-002 | Configurable WIP Limit | FR13 | `src/task_manager.py` |
| FR-TASK-003 | Bi-directional Notion Background Sync | FR14 | `src/notion_sync.py` |
| FR-TASK-004 | Backlog Task Suggestions | FR15 | `src/task_manager.py` |
| FR-BMAD-001 | Discovery Session Facilitation | FR16 | `src/bmad.py` |
| FR-BMAD-002 | PRD & SDD Artifact Generation | FR17 | `src/bmad.py` |
| FR-BMAD-003 | SDD-Based Code Review | FR18 | `src/bmad.py` |
| FR-BMAD-004 | Code Scaffolding Generation | FR19 | `src/bmad.py` |
| FR-RES-001 | Research Mission Budgeting | FR20 | `src/tools.py` |
| FR-RES-002 | Multi-Source Synthesis | FR21 | `src/tools.py`, `src/chat.py` |
| FR-RES-003 | Adversarial Sounding Board | FR22 | `src/tools.py` |
| FR-RES-004 | Historical Conflict Detection | FR23 | `src/tools.py`, `src/memory.py` |
| FR-SEC-001 | Authorized Directory Registry | FR24 | `src/security.py` |
| FR-SEC-002 | Permission-Gated File Writes | FR25 | `src/security.py`, `src/file_tools.py` |
| FR-SEC-003 | Structured JSONL Decision Log | FR26 | `src/security.py` |
| FR-SEC-004 | Directory Access Revocation | FR27 | `src/security.py` |
| FR-UX-001 | Human-Centric Output Formatting | FR28 | `src/cli.py`, `src/chat.py` |
| FR-UX-002 | Personality, Voice & Code-Switched Speech | FR29 | `SOUL.md`, `src/context_loader.py`, `src/chat.py` |

### Non-Functional Requirements

| ID | Title | BMAD Ref | Target |
|----|-------|----------|--------|
| NFR-PERF-001 | Tier 1/2 Retrieval Latency < 100ms | NFR1 | `src/memory.py` |
| NFR-PERF-002 | Tier 3 Semantic Search Latency < 550ms | NFR2 | `src/memory.py` |
| NFR-PERF-003 | Intent Routing Latency < 500ms | NFR3 | `src/router.py` |
| NFR-REL-001 | Atomic Write Success Before Embedding | NFR4 | `src/database.py` |
| NFR-REL-002 | State Recovery < 1 Second | NFR5 | `src/database.py` |
| NFR-SEC-001 | Local Execution Only for Tiers 0–3 | NFR6 | `src/llm_interface.py` |
| NFR-SEC-002 | Permission-on-Write for All File Ops | NFR7 | `src/security.py` |
| NFR-AUD-001 | JSONL Transaction Log Within 100ms | NFR8 | `src/security.py` |
| NFR-SYNC-001 | Local Cache Overrides Sync Conflicts | NFR9 | `src/notion_sync.py` |
| NFR-RES-001 | Research Missions Require Time Estimate | NFR10 | `src/tools.py` |

## Traceability

See `specs/traceability.json` for the machine-readable ID→file mapping used by the BMAD pipeline during code review.
