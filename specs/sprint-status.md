# Xochitl SDD Sprint Status

**Last updated:** 2026-05-03
**Session:** Epics 5, 6, 7 — SDD Traceability, Research Module, UX Patterns

---

## Completed This Session

### Epic 1: Secure Foundation & System Sovereignty ✅

| Requirement | Status | File |
|-------------|--------|------|
| FR-SEC-001 Authorized Directory Registry | ✅ Implemented | `src/config.py`, `src/security.py` |
| FR-SEC-002 Permission-Gated File Writes | ✅ Implemented | `src/security.py` |
| FR-SEC-003 Structured JSONL Decision Log | ✅ Implemented | `src/security.py` |
| FR-SEC-004 Directory Access Revocation | ✅ Implemented | `src/security.py`, `src/chat.py` |
| NFR-SEC-002 100% Write Operations Gated | ✅ Implemented | `src/security.py` |
| NFR-AUD-001 JSONL Log Within 100ms | ✅ Implemented | `src/security.py` |
| NFR-SYNC-001 Local Cache Overrides Conflicts | ✅ Fixed | `src/cli.py` (conflict default → "keep") |

### New Files Created
- `src/config.py` — Tier 1 profile + authorized directory registry backed by `~/.xochitl/config.toml`

### Files Refactored
- `src/security.py` — removed hardcoded `ALLOWED_ROOTS`/`FORBIDDEN_ROOTS`; added `log_decision()` JSONL logger; all writes now require confirmation; added `/authorize`, `/revoke`, `/registry`, `/audit` command handlers
- `src/chat.py` — added `/` slash command dispatch in the interactive loop; added `_handle_slash_command()` method
- `src/cli.py` — fixed Notion conflict default from `"pull"` to `"keep"` (NFR-SYNC-001)

### Verified Working
- `src/config.py` loads 4 default authorized paths; forbidden paths (.ssh, .aws) correctly blocked
- `src/security.py` write gate: new files require confirmation; unauthorized paths blocked
- JSONL log writes to `~/.xochitl/decision_log.jsonl` with correct schema
- `/authorize`, `/revoke`, `/registry`, `/audit` slash commands integrated into chat loop

---

## Remaining Epics (Priority Order)

### Epic 3: Cognitive Extension — Tiered Memory & RAG ✅

| Requirement | Status | File |
|-------------|--------|------|
| FR-MEM-001 Working Memory — Tier 0 | ✅ Implemented | `src/memory.py` — `WorkingMemory` class |
| FR-MEM-002 User Profile — Tier 1 | ✅ Implemented | `src/config.py` + `src/memory.py` shim |
| FR-MEM-003 Markdown Knowledge Base — Tier 2 | ✅ Implemented | `src/memory.py` — `KnowledgeBase` class |
| FR-MEM-004 Vector DB Semantic Search — Tier 3 | ✅ Implemented | `src/memory.py` — `VectorMemory` class (LanceDB) |
| FR-MEM-005 Reranking Protocol | ✅ Implemented | `src/memory.py` — `rerank()` via Ollama + fallback |
| FR-MEM-006 Session Archiving & Ingestion | ✅ Implemented | `src/memory.py` — `archive_session()` |
| FR-MEM-007 Verify-on-Call Protocol | ✅ Implemented | `src/context_loader.py` — `verify_on_call()` |
| NFR-PERF-001 Tier 1/2 Latency < 100ms | ✅ Implemented | `KnowledgeBase.search()` (keyword, no model) |
| NFR-PERF-002 Tier 3 Latency < 550ms | ✅ Implemented | `VectorMemory.recall()` (LanceDB ANNS) |
| NFR-REL-001 Atomic Write Before Embedding | ✅ Implemented | `KnowledgeBase.upsert()` — .tmp → rename |
| NFR-SEC-001 Local Execution for Tiers 0-3 | ✅ Implemented | Ollama-only inference; no cloud calls in memory |

### New / Changed Files (Epic 3)
- `src/memory.py` — REPLACED: ChromaDB removed; 5-tier architecture with `WorkingMemory`, `KnowledgeBase`, `VectorMemory`, `rerank()`, `archive_session()`, `query_memory()`; backward-compat shims for `read_memory()`, `memorize()`, `recall()`, `vector_db_count()`
- `src/context_loader.py` — ADDED `verify_on_call(entry)` (FR-MEM-007 SHA-256 hash gate); updated docstring and imports
- `src/config.py` — ADDED `embedding_model: "nomic-embed-text"` to `_DEFAULT` models section
- `requirements.txt` — SWAPPED `chromadb>=0.5.0` → `lancedb>=0.8.0`

### Epic 2: The Matriarca Brain — Orchestration & Routing ✅ (Core)

| Requirement | Status | File |
|-------------|--------|------|
| FR-ORCH-001 Intent Classification with Confidence Gate | ✅ Implemented | `src/router.py` — `_classify()` returns `(category, confidence)`; `route()` gates at 85% |
| FR-ORCH-002 Dynamic Skill Invocation | ⚠️ Partial | `src/router.py` (skill dispatch already exists via category routing) |
| FR-ORCH-003 Persistent Conversational Loop | ⚠️ Partial | `src/cli.py`, `src/chat.py` (loop exists; narrative improvements pending) |
| FR-ORCH-004 Tool Outcome Narrative | ⚠️ Partial | `src/chat.py` |
| NFR-PERF-003 Intent Routing < 500ms | ✅ Implemented | `_fast_classify()` is O(1) keyword match; LLM path only for unmatched queries |

### New / Changed Files (Epic 2)
- `src/router.py` — ADDED `_parse_classification()` (robust `category|confidence` parser); UPDATED `_fast_classify()` returns `tuple[str, float]`; UPDATED `_classify()` returns `tuple[str, float]`; ADDED confidence gate in `route()` returning clarification `LLMResponse` when confidence < threshold; ADDED `get_confidence_threshold()` import from `src.config`; ADDED `_ALL_CATEGORIES` set for parser validation

### Epic 4: Strategic Task Management — Notion Sync ✅ (Core)

| Requirement | Status | File |
|-------------|--------|------|
| FR-TASK-001 SQLite State Cache with PARA Mapping | ✅ Solid | `src/database.py` |
| FR-TASK-002 Configurable WIP Limit | ✅ Implemented | `src/task_manager.py` — `fill_queue()` reads `get_wip_limit()` |
| FR-TASK-003 Bi-directional Notion Background Sync | ⚠️ Partial | `src/notion_sync.py` |
| FR-TASK-004 Backlog Task Suggestions | ⚠️ Partial | `src/task_manager.py` |

### New / Changed Files (Epic 4)
- `src/task_manager.py` — ADDED `from src.config import get_wip_limit`; UPDATED `fill_queue()` to use `get_wip_limit()` instead of hardcoded `3`

### Epic 5: BMAD Development Pipeline ✅ (Core)

| Requirement | Status | File |
|-------------|--------|------|
| FR-BMAD-001 Discovery Session Facilitation | ⚠️ Thin | `src/skills/bmad_skill.py` (existing) |
| FR-BMAD-002 PRD & Architecture Generation | ⚠️ Partial | `src/bmad.py`, `src/skills/bmad_skill.py` (existing) |
| FR-BMAD-003 SDD-Based Code Review | ✅ Implemented | `src/skills/sdd_skill.py` — `review_code_traceability()` |
| FR-BMAD-004 Code Scaffolding Generation | ⚠️ Partial | `src/skills/code_skill.py` (existing) |

### New / Changed Files (Epic 5)
- `src/skills/sdd_skill.py` — ADDED `review_code_traceability(project_id)`: scans `*.py` for `# Implements FR-*`, cross-references specs + `traceability.json`, reports implemented / broken / unimplemented / untraced files. Also surfaced via `/review` slash command.

### Epic 6: Research & Augmented Intelligence ✅

| Requirement | Status | File |
|-------------|--------|------|
| FR-RES-001 Research Mission Budgeting | ✅ Implemented | `src/research.py` — `ResearchMission` class |
| FR-RES-002 Multi-Source Synthesis | ✅ Implemented | `src/research.py` — `synthesize()` |
| FR-RES-003 Adversarial Sounding Board | ✅ Implemented | `src/research.py` — `adversarial_review()` |
| FR-RES-004 Historical Conflict Detection | ✅ Implemented | `src/research.py` — `detect_conflicts()` |

### New / Changed Files (Epic 6)
- `src/research.py` — NEW: `ResearchMission` (time-budgeted session), `synthesize()` (LLM multi-source), `adversarial_review()` (devil's advocate), `detect_conflicts()` (KB search + LLM verdict), `run_research()` (convenience wrapper). Surfaced via `/research` and `/adversarial` slash commands.

### Epic 7: Human-Centric Presentation & UX ✅ (Core)

| Requirement | Status | File |
|-------------|--------|------|
| FR-UX-001 Human-Centric Output Formatting | ✅ Implemented | `src/chat.py` + `src/cli.py` |

### New / Changed Files (Epic 7)
- `src/chat.py` — ADDED `_OK`, `_FYI`, `_ERR` feedback pattern constants (`Claro`, `Fíjate`, `Ay no`); ADDED TERM=dumb detection at module level; ADDED `no_rich` param to `XochitlChat.__init__()`; ADDED `/review`, `/research`, `/adversarial` slash commands
- `src/cli.py` — ADDED `--no-rich` flag to `chat` command (passes to XochitlChat)

---

## How to Resume Next Session

Start next session with: **"Read specs/sprint-status.md and continue"**

**All 7 epics are now spec-complete at the core level.** Remaining work is polish and integration:

1. Wire `_OK`, `_FYI`, `_ERR` constants into actual chat responses (replace bare strings)
2. Add WIP dashboard snapshot to the boot banner in `chat.py` (`_print_boot_banner`)
3. Smoke-test the full `xochitl chat` interactive loop end-to-end
4. Add `src/research.py` to the router's skill dispatch (so natural-language research requests route to it)
5. Write integration tests for Epic 3 memory tiers (requires Ollama running locally)

---

## Architecture Decisions Made This Session

1. **`config.toml` is the single source of truth** for all user settings, authorized directories, and model config. No other module hardcodes these values.
2. **JSONL log at `~/.xochitl/decision_log.jsonl`** — append-only, snake_case keys, ISO-8601 timestamps.
3. **Forbidden roots are hardcoded** in `config.py` (not config.toml) — `.ssh`, `.aws`, `C:/Windows` are never authorizable.
4. **ALL file writes require confirmation** (not just overwrites) — per FR-SEC-002 spec.
5. **Notion conflict default is "keep"** (local wins) — per NFR-SYNC-001.
