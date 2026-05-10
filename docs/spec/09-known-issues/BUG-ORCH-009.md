# BUG-ORCH-009 — Skill execute() Crashes on Missing LLM-Supplied Params

## Status
Resolved

## Severity
High — any `<skill_call>` invoked by the LLM without all required params raises an unhandled `KeyError` that crashes the active chat session.

## Symptoms
When the LLM invokes a skill via `<skill_call name="BMADSkill">{"action": "init_project"}</skill_call>` without including `project_id` or `name` in the JSON body, `BMADSkill.execute()` raises:

```
KeyError: 'project_id'
```

Similarly, `CodeSkill.execute()` raises `KeyError: 'requirement_id'` or `KeyError: 'issue_id'` for the `implement` and `fix` actions. In both cases the exception propagated through `_agent_loop` and terminated the session.

## Root Cause
Both `BMADSkill.execute()` and `CodeSkill.execute()` used direct key access (`params["key"]`) for required parameters, assuming the LLM would always supply them. The LLM occasionally omits parameters when invoking skills, especially on first invocation or when the user's message is ambiguous.

Affected code:
- `src/skills/bmad_skill.py` — `params["project_id"]`, `params["name"]`
- `src/skills/code_skill.py` — `params["requirement_id"]` (implement), `params["issue_id"]` (fix), `params["requirement_id"]` (tests)

## Affected Requirements
- `FR-ORCH-008` — Agent loop auto-executes named skills (requires graceful error, not crash)

## Fix Applied
**Files**: `src/skills/bmad_skill.py`, `src/skills/code_skill.py`

Replaced bare key access with `.get()` and early returns:

```python
# BMADSkill — before
result = self.init_project(params["project_id"], params["name"], ...)

# BMADSkill — after
project_id = params.get("project_id")
name = params.get("name")
if not project_id or not name:
    return "I need a project ID and name to initialize a project. ..."
result = self.init_project(project_id, name, ...)

# CodeSkill — before
return self.generate_code_for_requirement(project_id, params["requirement_id"])

# CodeSkill — after
req_id = params.get("requirement_id")
if not req_id:
    return "Specify a requirement_id (e.g. FR-CORE-001) to implement."
return self.generate_code_for_requirement(project_id, req_id)
```

## Regression Acceptance Criterion
`AC-BUG-ORCH-009`: Given an active chat session, when the LLM emits a `<skill_call name="BMADSkill">{"action": "init_project"}</skill_call>` with no `project_id` or `name`, then Xochitl must return a helpful error message and the session must remain active.

## Related
- `BUG-ORCH-010` — Uncaught skill exception crashes session (defence-in-depth fix)
