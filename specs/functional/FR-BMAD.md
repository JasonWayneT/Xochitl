# FR-BMAD: BMAD/SDD Development Pipeline

**Domain:** Modular Development Pipeline
**BMAD Source:** PRD FR16–FR19, Epic 5
**Primary Module:** `src/skills/bmad_skill.py`, `src/skills/sdd_skill.py`, `src/skills/code_skill.py`

---

## FR-BMAD-001 — Discovery Session Facilitation

**Status:** Implemented
**BMAD Ref:** FR16
**Implements:** `src/bmad.py`

### Description
The system can detect a new project intent and switch to a structured BMAD Discovery Session. The session uses conversational elicitation (JTBD, First Principles) to capture business ideas and project intent, generating structured outputs in the project's planning folder.

### Acceptance Criteria
- GIVEN the user expresses intent to build a new project (e.g., "I want to build X")
  THEN the system detects the BMAD intent and switches to the BMAD module
- GIVEN the BMAD module activates
  THEN it reads the current directory via the File System Tool before beginning
  AND scaffolds a new project folder under `projects/<id>/`
- GIVEN the discovery session runs
  THEN the system facilitates structured elicitation through a conversational loop
  AND generates intermediate planning artifacts in `projects/<id>/bmad/`
- GIVEN the session completes
  THEN the user is left with a documented project idea ready for PRD generation (`FR-BMAD-002`)

### Constraints
- All file writes require permission gating (`FR-SEC-002`)
- The discovery session runs within the persistent Matriarca loop (`FR-ORCH-003`)
- Session artifacts are written in Markdown format

---

## FR-BMAD-002 — PRD & Architecture Artifact Generation

**Status:** Implemented
**BMAD Ref:** FR17
**Implements:** `src/bmad.py`

### Description
Based on a completed Discovery Session, the system generates Product Requirements Documents (PRD) and Architecture Decisions Documents in Markdown format. These documents are stored in the project's `bmad/` folder and serve as the source of truth for SDD spec generation.

### Acceptance Criteria
- GIVEN a completed Discovery Session with captured project intent
  WHEN the user requests PRD generation
  THEN a `prd.md` is generated in `projects/<id>/bmad/`
- GIVEN a completed PRD
  WHEN the user requests Architecture generation
  THEN an `architecture.md` is generated in `projects/<id>/bmad/`
- GIVEN either document is generated
  THEN it includes structured Functional Requirements with IDs in the format `FR-<DOMAIN>-NNN`
- GIVEN the documents are saved
  THEN SDD spec files are scaffolded in `projects/<id>/specs/` based on the FRs

### Constraints
- Generated artifacts use the cloud LLM tier (Gemma-4-26B-A4B or Claude) for quality
- All artifact writes are logged to the Decision Log (`FR-SEC-003`)
- Documents follow the GFM Markdown standard (`FR-UX-001`)

---

## FR-BMAD-003 — SDD-Based Code Review

**Status:** Implemented
**BMAD Ref:** FR18
**Implements:** `src/bmad.py`

### Description
The system reviews existing local code against the established SDD specifications in `projects/<id>/specs/`. It performs an adversarial review checking for missing requirement coverage, orphaned code (code not linked to any FR), and spec violations.

### Acceptance Criteria
- GIVEN a project with SDD specs in `projects/<id>/specs/`
  WHEN the user requests a code review
  THEN the system reads all source files in `projects/<id>/src/`
  AND checks each file for `# Implements FR-*` comments
- GIVEN a function or module lacks a requirement ID comment
  THEN it is flagged as "untraced code" in the review report
- GIVEN a requirement ID is referenced in code but does not exist in `traceability.json`
  THEN it is flagged as a "broken reference" in the review report
- GIVEN a requirement has no corresponding code
  THEN it is flagged as "unimplemented" in the review report

### Constraints
- Review report is presented as a Rich-formatted panel in the CLI
- Review does not modify any files without explicit user confirmation (`FR-SEC-002`)
- References `projects/<id>/specs/traceability.json` as the authoritative ID registry

---

## FR-BMAD-004 — Code Scaffolding Generation

**Status:** Implemented
**BMAD Ref:** FR19
**Implements:** `src/bmad.py`

### Description
Based on SDD specifications, the system drafts initial code structures or refactors for specific requirements. All generated code includes `# Implements <FR-ID>` comments linking back to the specification.

### Acceptance Criteria
- GIVEN an unimplemented requirement ID from the review report
  WHEN the user requests scaffolding for that requirement
  THEN the system generates a stub function or class implementing the requirement's interface
  AND includes `# Implements <FR-ID>` as the first comment in the generated code
- GIVEN multiple requirements are selected for scaffolding
  THEN each is generated in the correct target file as mapped in `traceability.json`
- GIVEN a scaffolded file already exists
  THEN the system appends the new stub rather than overwriting the file
  AND requires user confirmation before writing (`FR-SEC-002`)

### Constraints
- Generated code uses Python 3.12+ with mandatory type hints (per architecture standards)
- All generated code follows PEP 8 and the naming conventions in `architecture.md`
- Cloud LLM (Gemma-4-26B-A4B or Claude) is used for generation quality
