# Requirements Registry

This is the canonical list of project requirements. Feature specs, tasks, tests, and code changes must trace back here.

## ID naming convention

Use only the categories the project needs.

| Prefix | Category | Example |
|---|---|---|
| `FR` | Functional requirement | `FR-001` |
| `NFR` | Non-functional requirement | `NFR-001` |
| `UX` | User experience requirement | `UX-001` |
| `DES` | Visual or interaction design requirement | `DES-001` |
| `ARCH` | Architecture requirement | `ARCH-001` |
| `DATA` | Data requirement | `DATA-001` |
| `SEC` | Security/privacy requirement | `SEC-001` |
| `INT` | Integration requirement | `INT-001` |
| `OPS` | Operations requirement | `OPS-001` |
| `AC` | Acceptance criterion | `AC-001` |
| `TEST` | Test case | `TEST-001` |
| `BUG` | Known bug or regression | `BUG-001` |
| `ADR` | Architecture decision | `ADR-001` |
| `CR` | Change request | `CR-001` |

## Status values

- `draft`: proposed but not accepted
- `accepted`: approved source of truth
- `implemented`: implemented in code
- `verified`: implemented and validated
- `deprecated`: no longer active
- `superseded`: replaced by another ID

## Requirement records

| ID | Type | Priority | Status | Requirement | Acceptance criteria | Source | Notes |
|---|---|---|---|---|---|---|---|
| `FR-001` | functional | P0 | draft |  | `AC-001` | `BMAD-SRC-001` |  |

## Acceptance criteria

Write acceptance criteria in Given/When/Then form when possible.

| ID | Parent requirement | Scenario | Given | When | Then | Status |
|---|---|---|---|---|---|---|
| `AC-001` | `FR-001` | Happy path |  |  |  | draft |

## Requirement lifecycle notes

- Never reuse deprecated IDs.
- If a requirement changes meaning, create a new ID and mark the old one superseded.
- If a requirement is split, create child IDs and update traceability.
- If a requirement is merged, preserve all old IDs as superseded aliases.
