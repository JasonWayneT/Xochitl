# Reusable Prompt: BMAD to Spec Driven Development

Use this prompt when starting or changing a project built WITH Xochitl (i.e., a project under `projects/<id>/`).

```text
You are working in a BMAD-informed Spec Driven Development repository.

Before touching code:
1. Read AGENTS.md and docs/spec/ in the required order.
2. Identify the BMAD source artifacts and requirement IDs relevant to my request.
3. If the request introduces or changes behavior, update the requirements registry first.
4. Update or create the relevant feature spec, design spec, change request, test spec, ADR, or known issue.
5. Update the traceability matrix.
6. Create implementation tasks that cite requirement IDs and acceptance criteria.
7. Only then modify code.

For this request:
[PASTE REQUEST HERE]

Use lightweight mode if the project is small, but still maintain requirement IDs, acceptance criteria, and traceability.

In your final response, include:
- Requirements touched
- Specs updated
- Code changed
- Tests run
- Traceability updates
- Open questions
```
