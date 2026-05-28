"""Execute saved procedural workflows (CR-042 / FR-MEM-014)."""
# Implements FR-MEM-014

from __future__ import annotations

from src.skills.base import Skill
from src.workflows import execute_workflow, get_workflow_by_name, search_workflows_by_intent


class WorkflowSkill(Skill):
    """Run stored multi-step workflows by name or strong intent match."""

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower().strip()
        if q.startswith("/workflow run"):
            return 0.95
        if "run workflow" in q or "run my " in q and "workflow" in q:
            return 0.75
        wf = search_workflows_by_intent(user_input, project=context.get("current_project"))
        if wf and float(wf.get("match_score") or 0) >= 0.85:
            return 0.80
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        return "I can run a saved procedural workflow for this. Use `/workflow run <name>`."

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Execute a named workflow or best intent match.

        Args:
            user_input: User message (may include workflow name).
            context: Chat context; must include ``_chat_skills`` list injected by XochitlChat.
            params: Optional ``name`` key for explicit workflow.

        Returns:
            Multi-step execution report.
        """
        name = (params.get("name") or "").strip()
        if not name and user_input.lower().startswith("/workflow run"):
            name = user_input.split(maxsplit=2)[-1].strip() if len(user_input.split()) >= 3 else ""
        if not name:
            wf = search_workflows_by_intent(
                user_input,
                project=context.get("current_project"),
            )
            if not wf:
                return "No matching workflow. Use `/workflows` to list or `/workflow save <name>`."
            name = wf["name"]
        else:
            wf = get_workflow_by_name(name)
        if not wf:
            return f"No workflow named '{name}'. Use `/workflows` to list."

        skills = context.get("_chat_skills") or []
        if not skills:
            return "Workflow executor needs an active chat session with skills loaded."

        return execute_workflow(wf, user_input, skills, context)

    def tool_definition(self) -> dict:
        return {
            "name": "WorkflowSkill",
            "description": "Run a saved multi-step procedural workflow by name.",
            "when": "User asks to run a saved routine or /workflow run",
            "params": {"name": "workflow name (optional if intent match)"},
            "examples": [
                "run workflow daily standup",
                "/workflow run morning-review",
                "run my weekly review workflow",
                "execute the deployment checklist workflow",
                "run the code review workflow",
            ],
        }
