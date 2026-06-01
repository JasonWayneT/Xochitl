"""Plan-first mode — generate a numbered step plan before any execution.

Implements FR-ORCH-044 (CR-052). Plan generation is strictly read-only: it asks
the local reasoning model for a numbered list of steps and returns it for the
user to review. It never edits files, runs commands, or stages actions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.router import TieredRouter

_PLAN_SYSTEM = (
    "You are a planning assistant. Given a development task, output ONLY a short "
    "numbered list of concrete, ordered steps (maximum 8). Each step is one line. "
    "Do not write code. Do not modify files. Do not run commands. No preamble, no "
    "epilogue — just the numbered steps."
)

_MAX_STEPS = 8


def generate_plan(task: str, router: "TieredRouter") -> str:
    """Generate a numbered plan for a task using the local reasoning model.

    Args:
        task: The task description to plan.
        router: TieredRouter used for the (local) planning call.

    Returns:
        A formatted plan block (header + numbered steps + read-only note), or a
        clear error message. Never raises.
    """
    task = (task or "").strip()
    if not task:
        return "Fíjate — give me a task to plan, e.g. `/plan add a logout button`."

    prompt = (
        f"Break this task into at most {_MAX_STEPS} concrete, ordered steps.\n\n"
        f"Task: {task}"
    )
    try:
        result = router.route(
            query=prompt,
            conversation_history=[],
            system_prompt=_PLAN_SYSTEM,
            force_route="architecture_planning",  # local 'thinking' model
        )
    except Exception as exc:  # noqa: BLE001 — planning must never crash the loop
        return f"Ay no — couldn't generate a plan: {exc}"

    if getattr(result, "error", None):
        return f"Ay no — couldn't generate a plan: {result.error}"

    body = (result.content or "").strip()
    if not body:
        return "Fíjate — the planner returned nothing. Try rephrasing the task."

    return (
        f"**Plan for:** {task}\n\n"
        f"{body}\n\n"
        "_This is a plan only — nothing has been changed or run. "
        "Tell me to proceed with a step when you're ready._"
    )
