# BUG-SDD-001 — create_requirement Generates Duplicate IDs After Deletion

## Status
Resolved

## Severity
Medium — deleting or renumbering a requirement causes the next `create_requirement` call to produce an ID already used by a deleted requirement, silently corrupting the spec file and traceability matrix.

## Symptoms
Given a project where FR-CORE-001 and FR-CORE-002 exist and FR-CORE-001 is then deleted from the spec file:

```
Existing: FR-CORE-002
create_requirement(type="CORE") → FR-CORE-001   ← collision with deleted ID
```

The spec file ends up with two sections named `## FR-CORE-001`, and the traceability matrix has two mappings for the same ID.

## Root Cause
`SDDSkill.create_requirement()` generated the next ID by counting existing requirements of that type:

```python
type_reqs = [r for r in reqs if f"-{req_type}-" in r["id"]]
next_num = len(type_reqs) + 1
```

`count + 1` is safe only when no gaps exist. After any deletion the count is less than the highest ID in use, causing a collision.

## Affected Requirements
- `FR-SDD-002` — Spec generation must produce unique, non-colliding requirement IDs

## Fix Applied
**File**: `src/skills/sdd_skill.py`, `create_requirement()`

Replaced count-based ID generation with max-based:

```python
# Before
type_reqs = [r for r in reqs if f"-{req_type}-" in r["id"]]
next_num = len(type_reqs) + 1

# After
type_reqs = [r for r in reqs if f"-{req_type}-" in r["id"]]
nums = [int(m.group(1)) for r in type_reqs if (m := re.search(r'-(\d+)$', r["id"]))]
next_num = max(nums) + 1 if nums else 1
```

The new ID is always one above the highest existing ID for the type, regardless of gaps.

## Regression Acceptance Criterion
`AC-BUG-SDD-001`: Given a project where FR-CORE-001 and FR-CORE-003 exist (FR-CORE-002 was deleted), when `create_requirement(type="CORE")` is called, then the new requirement must be assigned `FR-CORE-004`, not `FR-CORE-003`.
