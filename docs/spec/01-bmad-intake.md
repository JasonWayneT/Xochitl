# BMAD Intake

Paste or summarize BMAD outputs here. This is the staging area before requirements are normalized into project specs.

## Source artifacts

| Source ID | BMAD artifact | Owner/agent | Date | Link or location | Status |
|---|---|---|---|---|---|
| `BMAD-SRC-001` | Initial CLAUDE.md project spec | Jason | 2026-05-04 | `CLAUDE.md` | imported |

## Artifact mapping

| BMAD output | Destination spec |
|---|---|
| Brief, brainstorm, market research, domain research | `00-project-constitution.md` |
| PRD | `02-requirements-registry.md`, feature specs |
| Epics and stories | Feature specs, tasks, acceptance criteria |
| Architecture | Design specs, architecture requirements, ADRs |
| UX design | N/A (terminal UI only) |
| Dev stories | Tasks, acceptance criteria, test specs |
| QA test generation | Test specs and traceability matrix |
| Correct course output | Change requests and updated requirements |

## Raw BMAD notes

```text
Initial project concept captured in CLAUDE.md. Key outputs:
- Terminal-native AI Chief of Staff
- Commands: today, done, chat, plan, sync, pull
- Architecture: TieredRouter (local gemma4-e4b + cloud Gemini/Claude)
- BMAD → SDD → Code pipeline for projects/
- WIP limit: queue holds 0-3 rows
- Notion sync via PARA methodology
- SQLite local storage + ChromaDB vector DB
```

## Normalization notes

- Requirements imported from CLAUDE.md project spec and architecture description
- WIP limit (0–3 rows) treated as a hard architectural constraint (NFR)
- File sandboxing treated as a security requirement (SEC)
- LLM routing isolation treated as an architecture requirement (ARCH)
- Open question: Specific NFR thresholds for LLM response time not yet defined

## Import log

| Date | Imported by | Source IDs | Result | Follow-up |
|---|---|---|---|---|
| 2026-05-04 | Jason | `BMAD-SRC-001` | Constitution and registry scaffolded | Define NFR response time thresholds |
