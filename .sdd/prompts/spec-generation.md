# Spec Generation Prompt

You are generating SDD (Spec-Driven Development) requirements from BMAD artifacts for a solo developer.

## Your job

Read the BMAD Business Model and Architecture documents and extract 8–15 functional requirements. Each requirement must be:
- Specific and testable
- Traceable back to a BMAD section
- Written at a scope a solo developer can implement in one sitting

## Output Format

Output ONLY JSON. No markdown wrapping. No explanation. Pure JSON.

```json
{
  "requirements": [
    {
      "id": "FR-CORE-001",
      "title": "Short feature name",
      "feature_area": "CORE",
      "description": "One clear sentence describing what this does.",
      "priority": "P0",
      "acceptance_criteria": [
        "AC-CORE-001: GIVEN [context] WHEN [action] THEN [expected result]",
        "AC-CORE-002: GIVEN [another context] WHEN [action] THEN [result]"
      ],
      "edge_cases": [
        "EC-CORE-001: GIVEN [unusual input] WHEN [action] THEN [safe behavior]"
      ],
      "bmad_source": "business-model.md: Solution section"
    }
  ]
}
```

## ID Format

- `FR-<AREA>-<NNN>` where AREA is one of: CORE, API, UI, DATA, AUTH
- Number sequentially within each area: FR-CORE-001, FR-CORE-002, etc.
- Acceptance criteria: AC-<AREA>-<NNN> matching the parent FR
- Edge cases: EC-<AREA>-<NNN> matching the parent FR

## Priority Scale

- P0 = must-have, app doesn't work without it
- P1 = core feature, high value
- P2 = nice to have
- P3 = future consideration

## What makes a good requirement

**Good description:** "Users can create meal prep entries with name, ingredients, and macro totals."
**Bad description:** "The system should allow users to create meals in a user-friendly way."

**Good acceptance criterion:** "AC-CORE-001: GIVEN valid meal data WHEN user submits THEN system saves to database within 200ms"
**Bad acceptance criterion:** "System should be fast and reliable."

## Coverage guidelines

- Extract from both Business Model and Architecture
- Cover the happy path, auth (if any), data validation, and at least one edge case per requirement
- 8–15 total requirements; don't pad with trivial ones
