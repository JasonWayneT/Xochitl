# FR-ORCH: Orchestration & Routing

**Domain:** Intent-Driven Orchestration (The Brain)
**BMAD Source:** PRD FR1–FR4, Epic 2
**Primary Module:** `src/router.py`, `src/cli.py`, `src/chat.py`

---

## FR-ORCH-001 — Intent Classification with Confidence Gating

**Status:** Implemented
**BMAD Ref:** FR1
**Implements:** `src/router.py`

### Description
The system classifies user input into intent categories using a local fast-inference model (Gemma-4-E2B). A configurable confidence threshold gate halts processing and requests clarification when classification confidence falls below the threshold.

### Acceptance Criteria
- GIVEN user input is received
  WHEN the intent classifier runs
  THEN an intent label and confidence score are returned
- GIVEN classification confidence is ≥ the configured threshold (default: 85%)
  THEN the intent is accepted and routing proceeds
- GIVEN classification confidence is < 85%
  THEN the system halts, logs the ambiguity, and prompts the user for clarification
- GIVEN a custom threshold is set in `config.toml`
  THEN that value overrides the 85% default

### Constraints
- The classifier must use the local `Gemma-4-E2B` model only (no cloud calls)
- Routing must complete within `NFR-PERF-003` (< 500ms)
- Ambiguity logs must be written to the JSONL Decision Log (`FR-SEC-003`)

---

## FR-ORCH-002 — Dynamic Skill Invocation

**Status:** Implemented
**BMAD Ref:** FR2
**Implements:** `src/router.py`

### Description
The Controller dynamically invokes and parameterizes modular Python skills based on the detected intent from `FR-ORCH-001`. Skills are self-contained modules within `src/skills/` or direct module functions.

### Acceptance Criteria
- GIVEN a confirmed intent with confidence ≥ threshold
  THEN the Controller identifies the correct skill module
  AND extracts required parameters from the user's input
  AND invokes the skill with those parameters
- GIVEN the required parameters cannot be extracted
  THEN the system prompts the user for the missing values before invocation
- GIVEN a skill module raises an exception
  THEN the error is caught, logged to the Decision Log, and a user-facing error message is displayed

### Constraints
- All skill invocations must be logged (`FR-SEC-003`)
- No skill may make external network calls except `notion_sync.py` and `tools.py`

---

## FR-ORCH-003 — Persistent Conversational Loop

**Status:** Implemented
**BMAD Ref:** FR3
**Implements:** `src/cli.py`

### Description
The CLI maintains a persistent interactive loop under the "Matriarca" persona. The loop remains responsive to new user input while background tasks (e.g., Notion sync, embedding) execute asynchronously.

### Acceptance Criteria
- GIVEN the user invokes `xochitl` with no arguments
  THEN an interactive chat loop starts and displays the WIP Dashboard header
- GIVEN a background task is running
  THEN the user can still enter new input without waiting for the background task to complete
- GIVEN a background task finishes
  THEN the result is surfaced inline in the next conversational turn
- GIVEN the user types `/quit` or sends EOF
  THEN the loop exits gracefully with exit code 0

### Constraints
- The loop must be non-blocking for background tasks
- Session state must be persisted to SQLite (`FR-MEM-001`) across turns

---

## FR-ORCH-004 — Tool Outcome Narrative

**Status:** Implemented
**BMAD Ref:** FR4
**Implements:** `src/chat.py`

### Description
When a tool or skill completes, the system presents the outcome as an integrated Matriarca-persona conversational response rather than raw structured output. The narrative synthesizes tool results with conversational context.

### Acceptance Criteria
- GIVEN a skill execution completes with a result
  THEN the result is formatted as a Matriarca-voice response (not raw JSON or a dump of data)
- GIVEN a Notion sync completes
  THEN the response references the actual task names and status changes in natural language
- GIVEN a research mission completes
  THEN the synthesized summary is presented first, with structured data available on request

### Constraints
- Raw JSONL output is reserved for programmatic pipelining mode only (`--json` flag)
- All narrative responses must follow the UX feedback patterns defined in `FR-UX-001`
