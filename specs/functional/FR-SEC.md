# FR-SEC: Security & System Integrity

**Domain:** Security, Permission Gating & Auditability
**BMAD Source:** PRD FR24–FR27, Epic 1
**Primary Module:** `src/security.py`, `src/file_tools.py`

---

## FR-SEC-001 — Authorized Directory Registry

**Status:** Implemented
**BMAD Ref:** FR24
**Implements:** `src/security.py`

### Description
The system maintains a persistent registry of directories where it is authorized to read and write. Authorization is granted once per directory and persists across sessions. No file operation outside the registry may proceed.

### Acceptance Criteria
- GIVEN the user provides a directory path to authorize
  THEN the system validates the path exists and is accessible
  AND adds it to the registry in `~/.xochitl/config.toml`
- GIVEN an authorized directory is requested
  THEN the system confirms authorization and permits the operation
- GIVEN a path outside the registry is requested for a write operation
  THEN the operation is blocked immediately with an error message
- GIVEN the user lists authorized directories
  THEN all current registry entries are displayed with their authorization timestamps

### Constraints
- The registry is stored in `~/.xochitl/config.toml` under `[authorized_directories]`
- Authorization grants persist across application restarts
- Only `src/security.py` may read or write the registry

---

## FR-SEC-002 — Permission-Gated File Writes

**Status:** Implemented
**BMAD Ref:** FR25
**Implements:** `src/security.py`, `src/file_tools.py`

### Description
Every file system write operation requires two gates: (1) the target path must be within an authorized directory, and (2) the user must provide explicit `[y/n]` confirmation before the write executes.

### Acceptance Criteria
- GIVEN an agentic action requires a file system write
  WHEN the target path is NOT within an authorized directory
  THEN the operation is blocked immediately and logged as a `BLOCKED_WRITE` event
- GIVEN an agentic action requires a file system write
  WHEN the target path IS within an authorized directory
  THEN the system displays the full target path and the proposed change
  AND prompts: "Write to [path]? [y/n]"
  AND only proceeds if the user enters 'y'
- GIVEN the user enters 'n'
  THEN the operation is cancelled and logged as a `CANCELLED_WRITE` event

### Constraints
- Must meet `NFR-SEC-002`: 100% of write operations are gated — no exceptions
- All write attempts (allowed, blocked, or cancelled) are logged to the JSONL Decision Log (`FR-SEC-003`)
- Only `src/file_tools.py` may execute the actual file write; `src/security.py` provides the authorization check

---

## FR-SEC-003 — Structured JSONL Decision Log

**Status:** Implemented
**BMAD Ref:** FR26
**Implements:** `src/security.py`

### Description
The system maintains a structured, append-only JSONL Transaction Log that records every tool execution, file read/write, and external API call. Each entry includes timestamp, detected intent, tool name, rationale, and outcome. The log is human-readable and grep-parsable.

### Acceptance Criteria
- GIVEN any tool or agentic action is initiated
  THEN a log entry is appended to the JSONL file within 100ms of the action (`NFR-AUD-001`)
- GIVEN a log entry is written
  THEN it contains the required fields: `timestamp`, `session_id`, `intent`, `tool`, `rationale`, `outcome`, `status`
- GIVEN the log file is queried
  THEN each line is valid JSON with `snake_case` keys
- GIVEN the log grows large
  THEN a rotation or archive mechanism prevents unbounded file growth (configurable max size)

### Log Entry Schema
```json
{
  "timestamp": "2026-05-03T14:30:00Z",
  "session_id": "string",
  "intent": "string",
  "tool": "string",
  "rationale": "string",
  "outcome": "string",
  "status": "success | blocked | cancelled | error"
}
```

### Constraints
- Log file path: `~/.xochitl/decision_log.jsonl`
- Writes are atomic appends — the file is never rewritten in full
- Log is human-readable without specialized tooling (plain `grep` or `jq` sufficient)

---

## FR-SEC-004 — Directory Access Revocation

**Status:** Implemented
**BMAD Ref:** FR27
**Implements:** `src/security.py`

### Description
The system provides a specific command to revoke previously granted directory access from the registry. Revocation takes effect immediately for all subsequent operations in the current and future sessions.

### Acceptance Criteria
- GIVEN the user invokes the revocation command with a directory path (e.g., `/revoke /path/to/dir`)
  THEN the system locates the path in the authorized directory registry
  AND removes it from `~/.xochitl/config.toml`
  AND confirms: "Access to [path] has been revoked."
- GIVEN the path is not in the registry
  THEN the system responds: "That path was not in the registry." (no error)
- GIVEN access is revoked
  THEN any subsequent operation targeting that path is blocked immediately

### Constraints
- Revocation is logged to the JSONL Decision Log (`FR-SEC-003`)
- Revocation is immediate — no restart required
- The revocation command is accessible as a slash command within the interactive loop: `/revoke <path>`
