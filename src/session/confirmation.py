"""ConfirmationHandler — typed confirmation state machine extracted from XochitlChat.

Replaces the untyped `current_context["pending_action"]` string-key FSM with an
explicit enum and a handler class that owns all confirmation-flow logic.

Implements FR-ORCH-007 (LLM fallback for natural yes/no), FR-ORCH-011 (HITL gate).
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from src.router import TieredRouter

from src.constants import _OK, _ERR, _CONFIRM_YES, _CONFIRM_NO


class PendingAction(str, Enum):
    """Valid pending-action states for the confirmation FSM."""
    EXECUTE_SKILL_CALL = "execute_skill_call"
    SYNC_NOTION = "sync_notion"
    PUSH_NOTION = "push_notion"
    INIT_PROJECT = "init_project"
    GENERATE_SPECS = "generate_specs"
    ANALYZE_ISSUE = "analyze_issue"
    SCAFFOLD_CODE = "scaffold_code"

    @classmethod
    def from_str(cls, value: str) -> Optional["PendingAction"]:
        try:
            return cls(value)
        except ValueError:
            return None


class ConfirmationHandler:
    """Handles user confirmation and pending-action execution.

    Args:
        context: Mutable session context dict (mutated in-place).
        find_skill: Registry lookup callable — (name) -> Skill | None.
        router: TieredRouter instance for LLM micro-calls.
        session_history: Mutable session history list.
        current_project: Active project ID, or None.
        execute_pending_skill_call: Callable that runs the staged skill call.
        file_tools: FileTools instance for file operation confirmation.
    """

    def __init__(
        self,
        context: dict,
        find_skill: Callable,
        router: "TieredRouter",
        session_history: list,
        current_project: Optional[str],
        execute_pending_skill_call: Callable,
        file_tools,
    ) -> None:
        self._ctx = context
        self._find_skill = find_skill
        self._router = router
        self._history = session_history
        self._project = current_project
        self._execute_pending_skill_call = execute_pending_skill_call
        self._file_tools = file_tools

    # ── File operation permission gate ────────────────────────────────────────

    def handle_permission_response(self, user_input: str) -> Optional[str]:
        """Check if user is responding to a pending file-operation confirmation.

        Args:
            user_input: Raw user message.

        Returns:
            Response string if a pending operation was resolved, else None.
        """
        q = user_input.lower().strip()
        op_id = self._ctx.get("pending_file_operation")
        if not op_id:
            return None

        if q in _CONFIRM_YES:
            result = self._file_tools.confirm_operation(op_id)
            del self._ctx["pending_file_operation"]
            return result["message"]

        if q in _CONFIRM_NO:
            result = self._file_tools.cancel_operation(op_id)
            del self._ctx["pending_file_operation"]
            return result["message"]

        return None

    # ── Action confirmation gate ──────────────────────────────────────────────

    def handle_action_confirmation(self, user_input: str) -> Optional[str]:
        """Check if user is confirming or cancelling a staged action.

        Implements FR-ORCH-007 — LLM fallback when exact-match fails.

        Args:
            user_input: Raw user message.

        Returns:
            Response string if a pending action was resolved, else None.
        """
        q = user_input.lower().strip()
        raw_action = self._ctx.get("pending_action")
        if not raw_action:
            return None

        # Fast path: exact-match
        if q in _CONFIRM_YES:
            verdict = "yes"
        elif q in _CONFIRM_NO:
            verdict = "no"
        else:
            verdict = self._llm_classify_confirm(raw_action, user_input)
            if verdict == "unclear":
                return None

        if verdict == "yes":
            del self._ctx["pending_action"]
            return self._execute_action(raw_action, user_input)

        if verdict == "no":
            del self._ctx["pending_action"]
            self._ctx.pop("pending_project_id", None)
            self._ctx.pop("pending_project_name", None)
            self._ctx.pop("pending_project_description", None)
            self._ctx.pop("pending_issue_description", None)
            self._ctx.pop("pending_component", None)
            self._ctx.pop("pending_skill_call", None)
            return f"{_OK}, no problem."

        return None

    # ── Action execution (one branch per PendingAction) ───────────────────────

    def _execute_action(self, action: str, user_input: str) -> Optional[str]:
        pa = PendingAction.from_str(action)

        if pa == PendingAction.EXECUTE_SKILL_CALL:
            return self._execute_pending_skill_call()

        if pa == PendingAction.SYNC_NOTION:
            skill = self._find_skill("NotionSkill")
            if skill:
                return skill.execute(user_input, self._ctx, {"direction": "pull"})
            return f"{_ERR} — NotionSkill not available."

        if pa == PendingAction.PUSH_NOTION:
            skill = self._find_skill("NotionSkill")
            if skill:
                return skill.execute(user_input, self._ctx, {"direction": "push"})
            return f"{_ERR} — NotionSkill not available."

        if pa == PendingAction.INIT_PROJECT:
            return self._action_init_project(user_input)

        if pa == PendingAction.GENERATE_SPECS:
            from src.skills.sdd_skill import SDDSkill
            project_id = self._project or self._ctx.get("pending_project_id", "")
            return SDDSkill().generate_specs_from_bmad(project_id)

        if pa == PendingAction.ANALYZE_ISSUE:
            return self._action_analyze_issue()

        if pa == PendingAction.SCAFFOLD_CODE:
            from src.skills.code_skill import CodeSkill
            project_id = self._project or ""
            component = self._ctx.pop("pending_component", "backend")
            return CodeSkill().scaffold_from_specs(project_id, component)

        return None

    def _action_init_project(self, user_input: str) -> str:
        from src.skills.bmad_skill import BMADSkill
        from src.router import _resolve_file_context

        skill = BMADSkill()
        project_id = self._ctx.pop("pending_project_id", "new-project")
        name = self._ctx.pop("pending_project_name", project_id)
        desc = self._ctx.pop("pending_project_description", "")
        skill.init_project(project_id, name, desc)

        file_ctx = _resolve_file_context("", self._history)
        if file_ctx:
            prompt = (
                f"I have just initialized the project '{name}'.\n"
                "Based on the following product specification, please draft a "
                "Business Model (BMM) summary including: Core Value Prop, "
                "Target Users, and Key Features.\n\n"
                f"{file_ctx}"
            )
            result = self._router.route(
                query=prompt,
                conversation_history=[],
                system_prompt="You are a Product Manager drafting a Business Model (BMM) artifact.",
                force_route="general",
            )
            if not result.error:
                skill.save_bmad_artifact(project_id, "business-model", result.content)
                return (
                    f"{_OK} — Created **{name}**.\n\n"
                    "I've read the spec and drafted the **Business Model** for you:\n\n"
                    f"{result.content}\n\n"
                    "Shall we move to **Architecture**?"
                )

        return (
            f"{_OK} — Created **{name}** at `projects/{project_id}/`.\n\n"
            "Let's start with the Business Model. "
            "What's the core struggle this app solves? "
            "Who's experiencing it, and what do they do today instead?"
        )

    def _action_analyze_issue(self) -> str:
        from src.skills.sdd_skill import SDDSkill

        _FYI = "Fíjate"
        project_id = self._project or ""
        issue_desc = self._ctx.pop("pending_issue_description", "")
        sdd = SDDSkill()
        result = sdd.analyze_issue(project_id, issue_desc)
        if "error" in result:
            return f"Analysis failed: {result['error']}"

        confidence = result.get("confidence", 0)
        summary = result.get("summary", "")
        changes = result.get("spec_changes_needed", [])
        guidance = result.get("implementation_guidance", [])

        lines = [f"**Analysis:** {result.get('analysis_type', '?')}"]
        if summary:
            lines.append(f"\n{summary}")
        if changes:
            lines.append("\n**Spec changes needed:**")
            for c in changes:
                lines.append(f"- `{c.get('requirement_id', '?')}`: {c.get('rationale', '')}")
        if guidance:
            lines.append("\n**Implementation guidance:**")
            for g in guidance:
                lines.append(f"- {g}")
        if confidence < 0.75:
            lines.append(f"\n⚠ Confidence {confidence:.0%} — review before applying changes.")
        if changes:
            self._ctx["pending_spec_changes"] = changes
            lines.append("\nWant me to apply the spec changes and create an issue?")
        return "\n".join(lines)

    # ── LLM natural-language confirm classifier ───────────────────────────────

    def _llm_classify_confirm(self, pending_action: str, user_input: str) -> str:
        """LLM micro-call to interpret a natural-language yes/no response.

        Implements FR-ORCH-007. Returns 'yes' | 'no' | 'unclear'.

        Args:
            pending_action: The pending action label for context.
            user_input: Raw user message to classify.

        Returns:
            'yes', 'no', or 'unclear'.
        """
        prompt = (
            f"Pending action: {pending_action}\n"
            f"User says: \"{user_input}\"\n\n"
            "Does the user want to confirm (yes), cancel (no), or is it unclear?\n"
            "Reply with exactly one word: yes | no | unclear"
        )
        result = self._router.route(
            query=prompt,
            conversation_history=[],
            system_prompt="Classify user intent as: yes, no, or unclear. Reply with one word only.",
            force_route="simple_qa",
        )
        if result.error:
            return "unclear"
        raw = (result.content or "").strip().lower()
        first = raw.split()[0] if raw.split() else "unclear"
        if first in {"yes", "y", "confirm", "sure", "ok", "okay", "yep", "yeah", "do", "go", "proceed"}:
            return "yes"
        if first in {"no", "n", "cancel", "stop", "don't", "nope", "never", "abort"}:
            return "no"
        return "unclear"
