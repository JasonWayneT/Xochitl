# Non-Functional Requirements

**BMAD Source:** PRD NFR1–NFR10, Epic Requirements Inventory
**Enforcement:** These constraints apply system-wide and must be validated against each implementation module.

---

## Performance

### NFR-PERF-001 — Tier 1/2 Retrieval Latency

**BMAD Ref:** NFR1
**Target Module:** `src/memory.py`

The system shall retrieve local profile (Tier 1) and directory summary knowledge (Tier 2) in **under 100ms** for 95% of requests.

**Measurement:** P95 latency across 1,000 sequential reads in a populated index.

---

### NFR-PERF-002 — Tier 3 Semantic Search Latency

**BMAD Ref:** NFR2
**Target Module:** `src/memory.py`

The system shall return reranked vector search results (LanceDB search + Qwen3-Reranker) in **under 550ms** for 95% of requests.

**Measurement:** P95 end-to-end latency from query submission to top-3 chunks returned, measured on a corpus of 10,000+ chunks.

---

### NFR-PERF-003 — Intent Routing Latency

**BMAD Ref:** NFR3
**Target Module:** `src/router.py`

The system shall classify user intent and route to the appropriate module in **under 500ms** for 95% of requests.

**Measurement:** P95 latency from user input submission to skill invocation start, measured with Gemma-4-E2B running locally.

---

## Reliability & Data Integrity

### NFR-REL-001 — Atomic Write Success Before Embedding

**BMAD Ref:** NFR4
**Target Module:** `src/database.py`

The system shall achieve **100% atomic write success** for all session events to SQLite before any background embedding process is triggered. If the SQLite write fails, embedding must not proceed.

**Measurement:** Zero background embedding jobs initiated without a confirmed, committed SQLite transaction.

---

### NFR-REL-002 — State Recovery Time

**BMAD Ref:** NFR5
**Target Module:** `src/database.py`

The system shall recover conversational state from the persistent SQLite datastore in **under 1 second** upon application restart.

**Measurement:** Time from `xochitl` invocation to first WIP Dashboard render, measured on a populated state database.

---

## Security & Data Sovereignty

### NFR-SEC-001 — Local Execution for Tiers 0–3

**BMAD Ref:** NFR6
**Target Module:** `src/llm_interface.py`, `src/memory.py`

**100% of Tier 0 through Tier 3 data must remain on local disk and never be transmitted to external APIs.** Only explicit Tier 4 operations (web research, Notion sync) may initiate outbound network requests.

**Measurement:** Static analysis confirms no network calls in `memory.py`, `context_loader.py`, `router.py`, `database.py`, or `llm_interface.py` (local model paths only). Validated by architecture boundary enforcement.

---

### NFR-SEC-002 — Permission-on-Write Enforcement

**BMAD Ref:** NFR7
**Target Module:** `src/security.py`

The system shall **block 100% of write operations** outside the explicitly authorized directory registry and require explicit `y/n` human confirmation for any file modification within authorized directories.

**Measurement:** Zero file write operations that bypass `src/security.py`'s authorization check. Enforced by code review — only `src/file_tools.py` may call OS-level write functions, and only after `src/security.py` grants authorization.

---

## Auditability

### NFR-AUD-001 — JSONL Transaction Log Latency

**BMAD Ref:** NFR8
**Target Module:** `src/security.py`

Every tool execution and system-level read/write must be recorded in the human-readable JSONL Transaction Log **within 100ms** of the action occurring.

**Measurement:** Timestamp delta between action completion and log entry append, verified in integration tests.

---

## Sync Integrity

### NFR-SYNC-001 — Local Cache Override on Conflict

**BMAD Ref:** NFR9
**Target Module:** `src/notion_sync.py`

The system shall treat the local SQLite cache as "Master." **All synchronization conflicts with Notion must be resolved in favor of the local cache.** Notion is treated as the "Archive."

**Measurement:** In integration tests, deliberately introduce a conflict; verify the local cache value is preserved after sync.

---

## Research Constraints

### NFR-RES-001 — Time Estimate Required for Tier 4 Operations

**BMAD Ref:** NFR10
**Target Module:** `src/tools.py`

The system shall require a "Time to Complete" estimate during the Research Mission Budgeting Phase to prevent CLI hangs. Any Tier 4 research mission that exceeds the user-defined threshold (default: **5 minutes**) must require explicit user approval before execution.

**Measurement:** Zero Tier 4 research operations initiated without a displayed time estimate and user confirmation.
