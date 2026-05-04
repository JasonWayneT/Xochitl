# FR-TASK: Task Management & Notion Sync

**Domain:** Strategic Task Management
**BMAD Source:** PRD FR12–FR15, Epic 4
**Primary Module:** `src/task_manager.py`, `src/notion_sync.py`, `src/database.py`

---

## FR-TASK-001 — SQLite State Cache with PARA Mapping

**Status:** Implemented
**BMAD Ref:** FR12
**Implements:** `src/task_manager.py`, `src/database.py`

### Description
The system maintains a local SQLite state cache that mirrors the Notion PARA (Projects, Areas, Resources, Archive) structure. All primary task logic runs against this local cache to minimize API latency; a background process handles bi-directional Notion sync.

### Acceptance Criteria
- GIVEN the application starts
  THEN the SQLite database schema includes tables mapping to PARA categories
- GIVEN any task-related operation is requested
  THEN it executes against the local SQLite cache, not the Notion API directly
- GIVEN the local cache is empty on first start
  THEN a full pull from Notion populates it before the session begins
- GIVEN a state conflict occurs between Notion and the local cache
  THEN the local cache value is treated as master (`NFR-SYNC-001`)

### Constraints
- Only `src/database.py` may execute write operations against the SQLite file
- The SQLite file path is `~/.xochitl/state.db`
- State recovery must meet `NFR-REL-002` (< 1 second)

---

## FR-TASK-002 — Configurable WIP Limit

**Status:** Implemented
**BMAD Ref:** FR13
**Implements:** `src/task_manager.py`

### Description
The system enforces a configurable Work-In-Progress (WIP) limit on the local task queue. When the limit is reached, no additional tasks can be moved to active status until a slot opens.

### Acceptance Criteria
- GIVEN the WIP limit is set to N (default: 3) in `config.toml`
  THEN no more than N tasks can exist in the `active` state simultaneously
- GIVEN a user attempts to activate a task when the WIP limit is reached
  THEN the system blocks the action and presents a triage prompt: "Which 3 are we actually doing?"
- GIVEN a task is completed or archived
  THEN a WIP slot opens and the backlog suggestion flow triggers (`FR-TASK-004`)

### Constraints
- WIP limit is set via `WIP_LIMIT` in `config.toml` or `.env`
- The default value is 3
- The `queue` table holds exactly 0–`WIP_LIMIT` rows in the `active` state

---

## FR-TASK-003 — Bi-directional Notion Background Sync

**Status:** Implemented
**BMAD Ref:** FR14
**Implements:** `src/notion_sync.py`

### Description
The system pushes task completion status and progress notes back to Notion via a background sync process. Sync resolves all conflicts in favor of the local SQLite cache.

### Acceptance Criteria
- GIVEN a task is marked complete locally
  THEN the completion status and any progress notes are queued for sync to Notion
- GIVEN the background sync runs
  THEN only the delta (changed tasks) is pushed to Notion, not the full state
- GIVEN Notion returns a conflicting state during sync
  THEN the local cache value overrides the Notion value (`NFR-SYNC-001`)
- GIVEN the Notion API is unreachable
  THEN the sync queue is retained locally and retried on the next sync cycle

### Constraints
- Only `src/notion_sync.py` may make outbound Notion API calls
- All sync operations are logged to the JSONL Decision Log (`FR-SEC-003`)
- Notion is treated as "Archive"; local SQLite is treated as "Master"

---

## FR-TASK-004 — Backlog Task Suggestions

**Status:** Implemented
**BMAD Ref:** FR15
**Implements:** `src/task_manager.py`

### Description
When a WIP slot becomes available (a task is completed or archived), the system proactively suggests the next highest-priority task from the backlog.

### Acceptance Criteria
- GIVEN a WIP slot opens
  THEN the system queries the backlog for the next task by priority
  AND presents it to the user: "Shall we pull in '[Task Name]' next?"
- GIVEN the user accepts the suggestion
  THEN the task is moved from backlog to active status
- GIVEN the user declines
  THEN the system lists the top 3 backlog candidates for manual selection
- GIVEN the backlog is empty
  THEN the system notifies the user and prompts to add new tasks or pull from Notion

### Constraints
- Priority ordering uses the PARA priority field from the Notion schema
- Suggestion is surfaced inline in the conversational loop (not as a blocking prompt)
