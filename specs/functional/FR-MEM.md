# FR-MEM: Tiered Memory & RAG

**Domain:** Cognitive Extension — 5-Tier Memory Hierarchy
**BMAD Source:** PRD FR5–FR11, Epic 3
**Primary Module:** `src/memory.py`, `src/context_loader.py`

---

## FR-MEM-001 — Working Memory (Tier 0)

**Status:** Implemented
**BMAD Ref:** FR5
**Implements:** `src/memory.py`

### Description
The system maintains an immutable Working Memory object for each active session. Tier 0 holds the current conversation state, in-flight intent, and transient "sticky notes" that persist only for the duration of the session.

### Acceptance Criteria
- GIVEN a new session starts
  THEN a fresh `context.state` object is initialized with a unique `session_id`
- GIVEN user input is processed
  THEN the turn is appended to the Working Memory event log as an immutable record
- GIVEN the session ends
  THEN Working Memory is flushed and archived to Tier 2 (`FR-MEM-006`)
- GIVEN the system reads Working Memory
  THEN existing records cannot be mutated, only appended

### Constraints
- Stored in process RAM only — never written to disk directly
- All reads complete in ~0ms (no I/O)

---

## FR-MEM-002 — User Profile Preferences (Tier 1)

**Status:** Implemented
**BMAD Ref:** FR6
**Implements:** `src/memory.py`

### Description
The system loads User Profile Preferences from `~/.xochitl/config.toml` at session start. Profile data includes static identity, user preferences, API keys (via `.env`), and the authorized directory registry.

### Acceptance Criteria
- GIVEN the application starts
  THEN `config.toml` is read and the profile is loaded into memory within 10ms
- GIVEN a preference value is updated during a session
  THEN the change is persisted back to `config.toml` before the session ends
- GIVEN `config.toml` does not exist
  THEN the system creates a default profile and prompts the user to configure it

### Constraints
- Read latency must meet `NFR-PERF-001` (< 100ms)
- API keys are sourced from `.env` only, never stored in `config.toml`

---

## FR-MEM-003 — Markdown Knowledge Base (Tier 2)

**Status:** Implemented
**BMAD Ref:** FR7
**Implements:** `src/memory.py`

### Description
The system indexes and retrieves context from the Local Markdown Knowledge Base. Tier 2 includes all project documents, session archives, and directory-level summaries. It serves as the human-readable, app-agnostic source of truth.

### Acceptance Criteria
- GIVEN a Markdown file exists within an authorized directory
  THEN the system can index it and retrieve relevant chunks by keyword or path
- GIVEN a directory-level summary file exists
  THEN the system searches summaries first before diving into specific file chunks (hierarchical retrieval)
- GIVEN a Tier 2 read is requested
  THEN results are returned within `NFR-PERF-001` (< 100ms)

### Constraints
- All Markdown files use the mandatory metadata schema: `category`, `created_at`, `last_modified`, `source_path`
- In context conflicts, the most recently modified file takes precedence (Recency Bias rule)

---

## FR-MEM-004 — Vector DB Semantic Search (Tier 3)

**Status:** Implemented
**BMAD Ref:** FR8
**Implements:** `src/memory.py`

### Description
The system performs semantic similarity searches across the LanceDB Vector Database. Tier 3 enables meaning-based recall of historical sessions, project context, and archived knowledge.

### Acceptance Criteria
- GIVEN a semantic query is issued
  THEN LanceDB returns the top 10 most similar chunks
- GIVEN a Tier 3 search completes
  THEN the top 10 results are passed to the Reranker (`FR-MEM-005`) before context injection
- GIVEN the Vector DB is empty or unavailable
  THEN the system degrades gracefully to Tier 2 retrieval with a warning log

### Constraints
- Full search + reranking must meet `NFR-PERF-002` (< 550ms)
- LanceDB must be embedded and serverless — no external database server
- Must meet `NFR-SEC-001` (local execution only, no data transmitted externally)

---

## FR-MEM-005 — Reranking Protocol

**Status:** Implemented
**BMAD Ref:** FR9
**Implements:** `src/memory.py`

### Description
After a Tier 3 vector search, a local cross-encoder model (Qwen3-Reranker-0.6B) reranks the top 10 retrieved chunks. Only the top 3 highest-signal snippets are injected into the active context window.

### Acceptance Criteria
- GIVEN 10 candidate chunks from a Tier 3 search
  THEN the Reranker scores each chunk against the current query
  AND returns them sorted by relevance score descending
- GIVEN reranking completes
  THEN only the top 3 chunks are passed to the primary model
- GIVEN the Reranker model is unavailable
  THEN the system falls back to the raw vector similarity scores and logs a warning

### Constraints
- Reranking must add no more than 100ms to the Tier 3 total (within `NFR-PERF-002`)
- Uses `Qwen3-Reranker-0.6B` model only

---

## FR-MEM-006 — Session Archiving & Ingestion

**Status:** Implemented
**BMAD Ref:** FR10
**Implements:** `src/memory.py`

### Description
At session end, the system automatically archives the conversation to a Tier 2 Markdown file and queues it for background embedding into the Tier 3 Vector DB. Write-Ahead Logging (WAL) ensures Markdown is always the durability fallback.

### Acceptance Criteria
- GIVEN a session ends
  THEN the full conversation is written to a Markdown archive file in `~/.xochitl/sessions/`
  AND the archive includes the mandatory metadata schema fields
- GIVEN the archive is written
  THEN it is queued for background embedding into LanceDB
- GIVEN background embedding fails
  THEN the Markdown archive remains intact as the authoritative record

### Constraints
- Markdown write must be atomic (`NFR-REL-001`)
- Session archive files follow the naming convention: `YYYY-MM-DD_<session_id>.md`

---

## FR-MEM-007 — Verify-on-Call Protocol

**Status:** Implemented
**BMAD Ref:** FR11
**Implements:** `src/context_loader.py`

### Description
At the moment of context retrieval, the system validates the file hash and `source_path` of the requested document. If the file has moved or changed since indexing, the index is updated dynamically before the content is injected.

### Acceptance Criteria
- GIVEN a context retrieval is requested for a specific document
  THEN the system checks the current `source_path` and file hash against the stored index
- GIVEN the file is unchanged
  THEN retrieval proceeds immediately
- GIVEN the file has moved or its content has changed
  THEN the index entry is updated with the new path/hash
  AND retrieval proceeds with the fresh content
- GIVEN the file no longer exists
  THEN the stale index entry is removed
  AND the system continues without injecting that document

### Constraints
- Hash validation must not add more than 10ms to retrieval latency
- Hash algorithm: SHA-256
