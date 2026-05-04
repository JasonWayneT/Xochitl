# FR-RES: Research & Augmented Intelligence

**Domain:** Augmented Intelligence & Research (Tier 4)
**BMAD Source:** PRD FR20–FR23, Epic 6
**Primary Module:** `src/research.py`, `src/memory.py`

---

## FR-RES-001 — Research Mission Budgeting

**Status:** Implemented
**BMAD Ref:** FR20
**Implements:** `src/tools.py`

### Description
Before executing a Tier 4 web research operation, the system identifies the knowledge gap, estimates the token cost, search count, and time to complete, and requires explicit user approval. This prevents runaway CLI sessions and unexpected API costs.

### Acceptance Criteria
- GIVEN a user request requires web research
  THEN the system enters a "Budgeting Phase" before executing
  AND presents: estimated token usage, number of searches, and estimated time to complete
- GIVEN the time estimate exceeds the user-configured threshold (default: 5 minutes)
  THEN the system warns: "Fíjate, this mission may take over 5 minutes. Continue? [y/n]"
- GIVEN the user approves the budget
  THEN the research mission executes
- GIVEN the user declines
  THEN the system offers a narrowed scope or suggests using cached Tier 2/3 knowledge instead

### Constraints
- Must meet `NFR-RES-001`: every Tier 4 operation must include a "Time to Complete" estimate
- Budget approval is logged to the Decision Log (`FR-SEC-003`)
- Tier 4 is the only tier permitted to make external network calls via `src/tools.py`

---

## FR-RES-002 — Multi-Source Research Synthesis

**Status:** Implemented
**BMAD Ref:** FR21
**Implements:** `src/tools.py`, `src/chat.py`

### Description
After a research mission completes, the system synthesizes findings from multiple web sources with the user's local historical context (Tier 2/3) to produce a unified, contextually-grounded response.

### Acceptance Criteria
- GIVEN research results are collected from multiple web sources
  THEN the system queries Tier 2/3 for related historical context
  AND combines both in a single synthesized response
- GIVEN the user has previous notes or project decisions related to the topic
  THEN those are surfaced alongside new research findings
- GIVEN conflicting information exists between web research and local history
  THEN the system explicitly highlights the conflict and presents both perspectives

### Constraints
- Synthesis uses the cloud reasoning model (Gemma-4-26B-A4B or Claude)
- Local context injection follows the Reranking Protocol (`FR-MEM-005`)
- Web sources are cited inline in the response

---

## FR-RES-003 — Adversarial Sounding Board

**Status:** Implemented
**BMAD Ref:** FR22
**Implements:** `src/tools.py`

### Description
The system acts as a Strategic Sounding Board using the Adversarial Peer Protocol. Given a plan or strategy, it performs three structured analyses: Steel-man (strongest case for the idea), Red Team (most likely failure modes), and Pre-Mortem (what went wrong if this failed).

### Acceptance Criteria
- GIVEN the user submits a plan or strategy for review
  THEN the system runs the three-part Adversarial Peer Protocol in sequence
- GIVEN Step 1 (Steel-man)
  THEN the system articulates the strongest possible case for the plan
- GIVEN Step 2 (Red Team)
  THEN the system identifies the top 3 most likely failure modes with rationale
- GIVEN Step 3 (Pre-Mortem)
  THEN the system simulates a future failure scenario and traces back the root cause
- GIVEN all three analyses complete
  THEN a structured report is rendered as a Rich panel in the CLI

### Constraints
- Uses cloud reasoning model for analysis depth
- Analysis results are stored in Working Memory (`FR-MEM-001`) for reference during the session
- User must explicitly request the Adversarial Protocol — it is not triggered automatically

---

## FR-RES-004 — Historical Conflict Detection

**Status:** Implemented
**BMAD Ref:** FR23
**Implements:** `src/tools.py`, `src/memory.py`

### Description
The system queries the memory tiers (Tier 2/3) to detect contradictions between current plans or decisions and previous project facts, requirements, or architectural decisions. Conflicts are surfaced proactively before the user commits to a course of action.

### Acceptance Criteria
- GIVEN the user proposes a decision or plan
  THEN the system queries Tier 2/3 for related historical decisions
- GIVEN a contradiction is found
  THEN the system flags it: "Fíjate, this conflicts with [previous decision] from [date]."
  AND presents both the current plan and the conflicting historical fact side by side
- GIVEN no conflicts are found
  THEN the system confirms: "No conflicts with previous decisions detected."
- GIVEN the user wants to override a detected conflict
  THEN the system logs the override decision with rationale in the Decision Log (`FR-SEC-003`)

### Constraints
- Conflict detection runs against Tier 2 and Tier 3 only (local data, no web calls)
- Detection must complete within 1 second total (Tier 2 + Tier 3 latency combined)
- Overrides require explicit user acknowledgment before proceeding
