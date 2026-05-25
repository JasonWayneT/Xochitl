# TEST-MEM-003 — Procedural Memory Phase 2 (CR-042)

**Status**: implemented  
**Requirements covered**: FR-MEM-012, FR-MEM-013, FR-MEM-014

## Test cases

| ID | AC | Description | Mock boundary |
|---|---|---|---|
| `TEST-MEM-003-001` | AC-CR042-001 | `WorkflowVectorIndex.search` returns scored workflow_id | Patch `_embed` and LanceDB table |
| `TEST-MEM-003-002` | AC-CR042-002 | `distill_workflow_trajectory` parses LLM JSON | `call_local` |
| `TEST-MEM-003-003` | AC-CR042-003 | `execute_workflow` runs mock skills in order | skill `.execute` |
| `TEST-MEM-003-004` | AC-CR042-004 | Hybrid search uses embedding when keyword weak | `WorkflowVectorIndex.search` |

## Verification

```bash
python smoke_test.py   # expect 146 passed, 0 failed (full suite)
```

Smoke labels for CR-042 blocks use ASCII-only strings (Windows cp1252).
