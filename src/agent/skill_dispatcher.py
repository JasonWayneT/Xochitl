"""skill_dispatcher — governor-gated skill execution with timeout.

Extracted from XochitlChat._execute_skill_safe so the execution + permission
logic can be tested without the full chat session object.

The dispatcher always returns a str — it never raises for normal skill errors
or timeouts.  ConfirmationRequired IS re-raised so the session loop in chat.py
can prompt the user.  PolicyViolation IS re-raised so it surfaces to the caller.

FR-EXEC-001, FR-EXEC-002, FR-PERF-005, FR-RELY-004.
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import TYPE_CHECKING

from src.executor import ActionGovernor, ActionTier, ConfirmationRequired, PolicyViolation

if TYPE_CHECKING:
    from src.skills.base import Skill

_log = logging.getLogger("xochitl.skill_dispatcher")

_DEFAULT_TIMEOUT = 30.0
_CLEANUP_TIMEOUT = 5.0
_ERR = "Ay no"


def dispatch(
    skill: Skill,
    params: dict,
    user_input: str,
    context: dict,
    governor: ActionGovernor | None = None,
    timeout_secs: float = _DEFAULT_TIMEOUT,
) -> str:
    """Execute a skill after ActionGovernor approval.

    The per-skill timeout is read from ``skill.tool_definition()["timeout_secs"]``
    when available; the caller's ``timeout_secs`` argument is the fallback.

    Args:
        skill: Instantiated Skill to execute.
        params: Parsed params dict from the <skill_call> body.
        user_input: Raw user message forwarded to skill.execute().
        context: Mutable session context dict; skill writes into it in place.
        governor: ActionGovernor instance.  Defaults to a fresh one if None.
        timeout_secs: Max seconds to wait for skill.execute().

    Returns:
        Skill output string, or a user-visible error/timeout message.

    Raises:
        ConfirmationRequired: When the governor requires explicit user approval
            before the action can proceed.  The caller (chat.py session loop)
            must catch this, prompt the user, and retry.
        PolicyViolation: When the governor denies the action outright.
    """
    if governor is None:
        governor = ActionGovernor()

    skill_name = type(skill).__name__

    # FR-PERF-005: read per-skill timeout from tool_definition(); fall back to arg.
    try:
        timeout_secs = float(skill.tool_definition().get("timeout_secs", timeout_secs))
    except Exception:
        pass

    # ActionGovernor check — must happen before any execution.
    action_type = str(params.get("action", "fetch")).strip()
    target = str(params.get("target", "")).strip()
    tier = governor.classify(action_type, target)

    if tier == ActionTier.DENY:
        raise PolicyViolation(
            f"{skill_name} action '{action_type}' on '{target}' denied by policy"
        )
    if tier == ActionTier.CONFIRM:
        args = [target] if target else []
        raise ConfirmationRequired(
            action_tier=ActionTier.CONFIRM,
            cmd=f"{skill_name}.{action_type}",
            args=args,
        )

    # Execute with timeout via a daemon thread + queue (mirrors _execute_skill_safe).
    result_q: queue.Queue = queue.Queue()

    def _worker() -> None:
        try:
            result_q.put(("ok", skill.execute(user_input, context, params)))
        except Exception as exc:
            result_q.put(("err", str(exc)))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join(timeout=timeout_secs)

    if t.is_alive():
        _log.warning("skill_timeout skill=%s timeout=%.0fs", skill_name, timeout_secs)
        # FR-RELY-004: give the skill 5s to release its resources.
        def _safe_cleanup() -> None:
            try:
                skill.cleanup()
            except Exception:
                pass

        ct = threading.Thread(target=_safe_cleanup, daemon=True)
        ct.start()
        ct.join(timeout=_CLEANUP_TIMEOUT)
        context["last_skill_timeout"] = True
        return (
            f"[dim]{_ERR} — {skill_name} took longer than {int(timeout_secs)}s to respond. "
            f"The skill may be waiting on an external API. "
            f"Please try again or check your connection.[/dim]"
        )

    context["last_skill_timeout"] = False
    try:
        status, value = result_q.get_nowait()
    except queue.Empty:
        return f"[dim]{_ERR} — skill returned no result.[/dim]"

    if status == "err":
        return f"[dim]{_ERR} — skill error: {value}[/dim]"

    return value or ""
