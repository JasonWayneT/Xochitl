"""AgentPipeline — the full per-turn agent execution pipeline.

Extracted from XochitlChat._agent_loop so the pipeline logic is independently
testable without a full chat session object.

Pipeline stages (in order):
  1. BackgroundReview watchdog
  2. Observability trace-id
  3. Response-mode inference + announcement
  4. System-prompt assembly (workflow recall, skill scoring, context injection)
  5. LLM routing (streaming or non-streaming)
  6. Skill-call parsing + dispatch (with approval gate)
  7. Post-execution critique (optional)

Returns TurnResult consumed by XochitlChat.

Implements FR-ORCH-008, FR-PERF-003, FR-PERF-007, FR-PERF-008, FR-UI-005.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import TYPE_CHECKING, Optional

from src.agent.turn import AgentTurnInput, TurnResult
from src.agent.skill_parser import parse_skill_calls, strip_skill_calls
from src.agent.skill_scorer import SkillScorer
from src import events as _events
from src.action_disclosure import format_compact_result, infer_action_label

if TYPE_CHECKING:
    from src.router import TieredRouter
    from src.skills.base import Skill

_log = logging.getLogger("xochitl.agent.pipeline")

# Skill injection threshold — must match chat.py constant.
_SKILL_INJECT_THRESHOLD = 0.65
_OPEN_ENDED_SCORE_THRESHOLD = 0.2

# Regex used to strip <skill_call> tags from visible output.
_SKILL_CALL_RE = re.compile(
    r'<skill_call\s+name=["\'](\w+)["\']>(.*?)</skill_call>',
    re.DOTALL | re.IGNORECASE,
)

_ERR = "Ay no"
_FYI = "Fíjate"

# Skill actions that require user approval before execution.
_MUTATING_SKILL_ACTIONS: dict[str, set[str]] = {
    "BMADSkill": {"init_project", "save_bmad_artifact"},
    "SDDSkill": {"generate_specs", "create_requirement", "create_issue", "update_requirement", "close_issue"},
    "CodeSkill": {"scaffold", "implement", "fix", "tests", "test"},
}

# Approval requirement by skill name (regardless of action param).
_ALWAYS_APPROVE: frozenset[str] = frozenset({"NotionSkill", "CodeSkill"})


def _format_active_skill_block(defn: dict) -> str:
    """Format one skill's tool_definition() as a per-turn system prompt block."""
    name = defn.get("name", "")
    description = defn.get("description", "")
    when = defn.get("when", "")
    params = defn.get("params", {})
    examples = defn.get("examples", [])

    lines = [
        "## Active Skill",
        f"The following skill is relevant to this request: **{name}**",
        f"Does: {description}",
        f"Use when: {when}",
        "",
        "To invoke it, output this EXACT format anywhere in your response:",
        "",
        f'  <skill_call name="{name}">{{"param": "value"}}</skill_call>',
        "",
        "Read-only skills execute immediately. "
        "Mutating skills are staged for user approval first.",
        "Invoke proactively when the request falls within this skill's domain — "
        "you do not need exact keyword matches, just clear intent.",
    ]
    if isinstance(examples, list) and examples:
        lines.append("")
        lines.append("Example triggers:")
        for ex in examples[:6]:
            lines.append(f'  · "{ex}"')
    if params:
        lines.append("")
        lines.append(f"Parameters for {name}:")
        for k, v in params.items():
            lines.append(f"  `{k}`: {v}")

    return "\n".join(lines)


def _skill_call_requires_approval(skill: "Skill", params: dict) -> bool:
    """Return True when a skill call mutates files, state, or services."""
    name = type(skill).__name__
    action = str(params.get("action", "")).strip()
    if name in _ALWAYS_APPROVE:
        return True
    if name == "OrchestratorSkill":
        return bool(params.get("task_id"))
    if action and action in _MUTATING_SKILL_ACTIONS.get(name, set()):
        return True
    return False


def _risk_label(skill_name: str) -> str:
    labels = {
        "NotionSkill": "external side effect with Notion",
        "OrchestratorSkill": "background command/workspace execution",
        "CodeSkill": "file writes in the active project",
        "BMADSkill": "project/spec file writes",
        "SDDSkill": "project/spec file writes",
    }
    return labels.get(skill_name, "state change")


class AgentPipeline:
    """Stateless per-turn pipeline.  Call run() once per agent turn.

    The pipeline is intentionally stateless — all session state is passed in
    via AgentTurnInput and returned via TurnResult.  Side effects (console
    output, event emission, context mutation) happen inside run() but are
    bounded and documented.

    Args:
        router: TieredRouter instance shared with the session.
        skill_scorer: SkillScorer instance (carries per-turn cache).
        find_skill: Callable(name) -> Skill | None — registry lookup.
        execute_skill: Callable(skill, user_input, context, params) -> str.
        emit_action_line: Callable(label) -> None — prints disclosure line.
        console_print: Callable(*args, **kwargs) — Rich console.print equivalent.
        stage_skill_call: Callable(skill, params, user_input, visible) -> str
            — called when a mutating skill needs approval; returns the plan text.
        background_review: Optional BackgroundReview instance for watchdog.
        initiative: Optional InitiativeEngine for proactive signals.
        drift_reminder: Optional string injected when drift is detected.
    """

    def __init__(
        self,
        router: "TieredRouter",
        skill_scorer: SkillScorer,
        find_skill,
        execute_skill,
        emit_action_line,
        console_print,
        stage_skill_call,
        background_review=None,
        initiative=None,
        drift_reminder: str = "",
    ) -> None:
        self._router = router
        self._scorer = skill_scorer
        self._find_skill = find_skill
        self._execute_skill = execute_skill
        self._emit_action_line = emit_action_line
        self._console_print = console_print
        self._stage_skill_call = stage_skill_call
        self._background_review = background_review
        self._initiative = initiative
        self._drift_reminder = drift_reminder

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self, turn: AgentTurnInput, _status=None) -> TurnResult:
        """Execute one agent turn and return TurnResult.

        Args:
            turn: All inputs for this pipeline pass.
            _status: Optional _StatusContext for live status updates.

        Returns:
            TurnResult with response text and metadata.
        """
        # Stage 1 — BackgroundReview watchdog
        self._maybe_restart_background_review()

        # Stage 2 — per-turn trace ID
        import secrets as _sec
        _trace_id = _sec.token_hex(6)
        _events.emit("routing_started", {"query": turn.user_input[:100], "trace_id": _trace_id})

        # Stage 3 — response mode inference
        system_prompt, _new_mode = self._apply_response_mode(turn)

        # Stage 4a — identity drift reminder
        system_prompt = self._apply_drift_reminder(system_prompt)

        # Stage 4b — proactive initiative signals
        system_prompt = self._apply_initiative_signals(system_prompt)

        # Stage 4c — workflow recall
        system_prompt = self._apply_workflow_recall(turn, system_prompt, _status)

        # Stage 4d — skill scoring + injection
        system_prompt, top_skill, top_score, score_key = self._apply_skill_scoring(
            turn, system_prompt, _status
        )

        # Stage 4e — turn context block (near-miss / complete-miss)
        system_prompt = self._apply_turn_context(system_prompt, top_skill, top_score)

        # Stage 5 — LLM routing
        # FR-ORCH-025: force_cloud wins; governor force_route applies only when
        # no other force is set (mirrors the logic from the original _agent_loop).
        # governor.force_route() returns "general" for LOCAL_ONLY / HARD_STOP tiers.
        force = "code_generation" if turn.force_cloud else (turn.governor_force or None)
        _skill_was_injected = (
            top_skill is not None and top_score >= _SKILL_INJECT_THRESHOLD
        )
        response_text, was_streamed = self._route(
            turn, system_prompt, force, _status, skill_injected=_skill_was_injected
        )

        if was_streamed and not _SKILL_CALL_RE.search(response_text):
            # Pure streaming turn — no skill calls possible without schema injection
            clean = _SKILL_CALL_RE.sub("", response_text).strip() or response_text
            return TurnResult(
                response=clean,
                was_streamed=True,
                new_score_cache=(
                    (type(top_skill).__name__, top_score) if top_skill else None
                ),
                new_score_cache_key=score_key,
            )

        # Stage 6 — skill-call dispatch
        skill_calls = parse_skill_calls(response_text)
        visible = _SKILL_CALL_RE.sub("", response_text).strip()
        tool_calls_made = False
        last_skill_name = ""
        last_mutating = ""

        if skill_calls:
            result_parts: list[str] = [visible] if visible else []
            remaining = len(skill_calls)
            for skill_name, params in skill_calls:
                remaining -= 1
                skill = self._find_skill(skill_name)
                if not skill:
                    result_parts.append(f"[dim][{skill_name}: skill not found][/dim]")
                    continue

                if _skill_call_requires_approval(skill, params):
                    _events.emit("hitl_required", {
                        "action": str(params.get("action", skill_name)),
                        "risk": _risk_label(type(skill).__name__),
                    })
                    if remaining > 0:
                        result_parts.append(
                            f"[dim][Note: {remaining} additional skill call(s) queued "
                            f"— approve this one first][/dim]"
                        )
                    plan = self._stage_skill_call(
                        skill, params, turn.user_input, "\n\n".join(result_parts)
                    )
                    return TurnResult(
                        response=plan,
                        was_streamed=was_streamed,
                        skill_fired=skill_name,
                        new_score_cache=(
                            (type(top_skill).__name__, top_score) if top_skill else None
                        ),
                        new_score_cache_key=score_key,
                    )

                _events.emit("skill_started", {"skill": skill_name, "params": list(params.keys())})
                if _status:
                    _status.update(f"running skill: {skill_name}")
                self._emit_action_line(infer_action_label(turn.user_input, skill_name))
                tool_result = self._execute_skill(
                    skill, turn.user_input, turn.context, params
                )
                _events.emit("skill_complete", {"skill": skill_name, "success": True})
                tool_calls_made = True
                last_skill_name = skill_name
                last_mutating = skill_name

                from src.terminal_output import format_skill_output
                formatted = format_skill_output(tool_result)
                turn.context["last_skill_name"] = skill_name
                turn.context["last_action_summary"] = infer_action_label(
                    turn.user_input, skill_name
                )

                # FR-ORCH-009: persist tool turn in session history.
                from datetime import datetime as _dt
                turn.session_history.append({
                    "role": "tool",
                    "skill": skill_name,
                    "content": tool_result,
                    "timestamp": _dt.now().isoformat(),
                })

                # Record procedural workflow usage
                _wf_id = turn.context.get("active_workflow_id")
                if _wf_id:
                    try:
                        from src.workflows import record_match_usage
                        record_match_usage(int(_wf_id), success=True)
                    except Exception:
                        pass

                result_parts.append(
                    format_compact_result(
                        turn.context["last_action_summary"], formatted or tool_result
                    )
                )

            final = "\n\n".join(result_parts) if result_parts else response_text
        else:
            final = visible or response_text

        # Stage 7 — post-execution critique
        messages = turn.messages
        final = self._maybe_critique(
            final, turn.user_input, top_score, tool_calls_made,
            messages, system_prompt, force
        )

        return TurnResult(
            response=final,
            was_streamed=was_streamed,
            skill_fired=last_skill_name or None,
            new_score_cache=(
                (type(top_skill).__name__, top_score) if top_skill else None
            ),
            new_score_cache_key=score_key,
            last_mutating_skill=last_mutating,
        )

    # ── Stage helpers ─────────────────────────────────────────────────────────

    def _maybe_restart_background_review(self) -> None:
        br = self._background_review
        if br is None:
            return
        if not br.is_alive():
            try:
                from src.background_review import BackgroundReview
                new_br = BackgroundReview()
                new_br.start()
                if self._initiative:
                    new_br._initiative_engine = self._initiative
                self._background_review = new_br
                _events.emit("SYSTEM_FAILURE", {
                    "component": "BackgroundReview",
                    "action": "restarted",
                })
            except Exception:
                pass

    def _apply_response_mode(self, turn: AgentTurnInput) -> tuple[str, str]:
        """Infer response mode and assemble system prompt."""
        try:
            from src.response_mode import infer_mode as _infer_mode
            _new_mode = _infer_mode(turn.user_input)
        except ImportError:
            _new_mode = "conversational"

        # The caller (chat.py) handles the mode-transition announcement since it
        # owns the console and tracks _current_mode across turns.
        system_prompt = turn.system_prompt
        return system_prompt, _new_mode

    def _apply_drift_reminder(self, system_prompt: str) -> str:
        if self._drift_reminder and self._background_review and \
                getattr(self._background_review, "drift_detected", False):
            system_prompt += self._drift_reminder
            self._background_review.clear_drift()
        return system_prompt

    def _apply_initiative_signals(self, system_prompt: str) -> str:
        try:
            if self._initiative:
                signals = self._initiative.drain()
                if signals:
                    sig = signals[0]
                    system_prompt += (
                        "\n\n---\n"
                        "[PROACTIVE ALERT]\n"
                        f"{sig.message}\n"
                        f"{sig.action_hint}\n"
                        "---"
                    )
        except Exception:
            pass
        return system_prompt

    def _apply_workflow_recall(
        self, turn: AgentTurnInput, system_prompt: str, _status
    ) -> str:
        turn.context.pop("active_workflow_id", None)
        turn.context.pop("active_workflow_name", None)
        try:
            from src.workflows import format_workflow_block, search_workflows_by_intent
            _wf = search_workflows_by_intent(turn.user_input, project=turn.current_project)
            if _wf:
                system_prompt += (
                    "\n\n---\n" + format_workflow_block(_wf) + "\n---"
                )
                turn.context["active_workflow_id"] = _wf["id"]
                turn.context["active_workflow_name"] = _wf["name"]
                if _status:
                    _status.update(f"workflow: {_wf['name']}")
        except Exception:
            pass
        return system_prompt

    def _apply_skill_scoring(
        self, turn: AgentTurnInput, system_prompt: str, _status
    ) -> tuple[str, Optional["Skill"], float, tuple]:
        self._scorer.update_skills(turn.skills)
        score_key: tuple = (hash(turn.user_input), len(turn.skills))
        top_skill, top_score, score_key = self._scorer.score(
            turn.user_input, turn.context, score_key=score_key
        )

        if top_skill is not None and top_score >= _SKILL_INJECT_THRESHOLD:
            defn = top_skill.tool_definition()
            system_prompt = system_prompt + "\n\n---\n\n" + _format_active_skill_block(defn)
            _events.emit("skill_matched", {"skill": defn.get("name", ""), "score": top_score})
            if _status:
                _status.update(f"skill ready: {defn.get('name', type(top_skill).__name__)}")

        return system_prompt, top_skill, top_score, score_key

    def _apply_turn_context(
        self,
        system_prompt: str,
        top_skill: Optional["Skill"],
        top_score: float,
    ) -> str:
        if top_skill is not None and top_score >= _SKILL_INJECT_THRESHOLD:
            return system_prompt  # skill schema handles it

        if top_skill is not None and top_score >= _OPEN_ENDED_SCORE_THRESHOLD:
            skill_label = type(top_skill).__name__.replace("Skill", "").strip() or "Unknown"
            return (
                system_prompt
                + f"\n\n[TURN CONTEXT: Near-match — '{skill_label}' skill scored "
                f"{top_score:.2f} (below injection threshold of {_SKILL_INJECT_THRESHOLD}). "
                "State clearly what this skill can and cannot cover for the current request. "
                "Do NOT silently deliver a reduced version — if partial handling is possible, "
                "say so explicitly. Apply [UNCERTAINTY TIERS] vocabulary as appropriate.]\n"
            )

        return (
            system_prompt
            + f"\n\n[TURN CONTEXT: No specific skill matched this request "
            f"(top score {top_score:.2f}, threshold {_OPEN_ENDED_SCORE_THRESHOLD}). "
            "If this request falls outside Xochitl's capabilities, state specifically "
            "what is missing and offer the nearest available forward path — see [CAPABILITY BOUNDARY]. "
            "Apply [UNCERTAINTY TIERS] vocabulary as appropriate.]\n"
        )

    def _route(
        self,
        turn: AgentTurnInput,
        system_prompt: str,
        force: Optional[str],
        _status,
        skill_injected: bool = False,
    ) -> tuple[str, bool]:
        """Route to LLM. Returns (response_text, was_streamed)."""
        # Determine streaming mode flags
        _disable_skill_stream = os.getenv("XCH_DISABLE_SKILL_STREAMING") == "1"
        _skill_injected = skill_injected

        use_streaming_pure = turn.stream and not turn.force_cloud and not _skill_injected
        use_streaming_skill = (
            turn.stream and not turn.force_cloud and _skill_injected and not _disable_skill_stream
        )

        if use_streaming_pure:
            response_text = self._stream_pure(turn, system_prompt, force, _status)
            if response_text:
                _events.emit("llm_complete", {
                    "route": "stream",
                    "tokens_in": 0,
                    "tokens_out": len(response_text),
                    "cost_usd": 0.0,
                })
                return response_text, True

        if use_streaming_skill:
            _displayed, response_text = self._stream_and_buffer(
                turn, system_prompt, force, _status
            )
            if response_text:
                _events.emit("llm_complete", {
                    "route": "stream_skill",
                    "tokens_in": 0,
                    "tokens_out": len(response_text),
                    "cost_usd": 0.0,
                })
                return response_text, True

        # Non-streaming fallback
        result = self._router.route(
            query=turn.user_input,
            conversation_history=turn.messages,
            system_prompt=system_prompt,
            force_route=force,
        )
        if result.error:
            return f"{_ERR} — {result.error}", False

        _events.emit("llm_complete", {
            "route": str(result.route),
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "cost_usd": result.cost_usd,
        })
        return result.content or "", False

    def _stream_pure(
        self, turn: AgentTurnInput, system_prompt: str, force: Optional[str], _status
    ) -> str:
        """Stream tokens with no skill injection; return buffered text or '' on failure."""
        self._stop_status(_status)
        buffer: list[str] = []
        printed_header = False
        try:
            for token in self._router.route_stream(
                query=turn.user_input,
                conversation_history=turn.messages,
                system_prompt=system_prompt,
                force_route=force,
            ):
                if not printed_header:
                    self._console_print(f"\n[bold]Xochitl[/bold]: ", end="")
                    printed_header = True
                self._console_print(token, end="")
                buffer.append(token)
        except Exception:
            return ""
        if buffer:
            self._console_print()
        return "".join(buffer)

    def _stream_and_buffer(
        self, turn: AgentTurnInput, system_prompt: str, force: Optional[str], _status
    ) -> tuple[str, str]:
        """Stream tokens live; stop displaying at first <skill_call>; return (displayed, full)."""
        self._stop_status(_status)
        buffer: list[str] = []
        displayed: list[str] = []
        printed_header = False
        skill_call_started = False

        try:
            for token in self._router.route_stream(
                query=turn.user_input,
                conversation_history=turn.messages,
                system_prompt=system_prompt,
                force_route=force,
            ):
                buffer.append(token)
                if skill_call_started:
                    continue
                if "<skill_call" in "".join(buffer):
                    skill_call_started = True
                    continue
                if not printed_header:
                    self._console_print(f"\n[bold]Xochitl[/bold]: ", end="")
                    printed_header = True
                self._console_print(token, end="")
                displayed.append(token)
        except Exception:
            pass

        if displayed:
            self._console_print()

        return "".join(displayed), "".join(buffer)

    @staticmethod
    def _stop_status(_status) -> None:
        """Stop the live status spinner before printing streaming tokens."""
        if _status is None:
            return
        _status._stop_event.set()
        if getattr(_status, "_refresh_thread", None):
            _status._refresh_thread.join(timeout=0.3)
            _status._refresh_thread = None
        live = getattr(_status, "_live", None)
        _status._live = None
        if live:
            try:
                live.stop()
            except Exception:
                pass

    def _maybe_critique(
        self,
        response: str,
        goal: str,
        top_score: float,
        tool_calls_made: bool,
        messages: list[dict],
        system_prompt: str,
        force: Optional[str],
    ) -> str:
        """Run post-execution critique if warranted. Implements FR-ORCH-037."""
        try:
            from src.critic import TurnCritic, _MAX_CRITIC_ITERATIONS
            _critic = TurnCritic()
            if not _critic.should_critique(top_score, tool_calls_made, response):
                return response

            current_response = response
            current_system = system_prompt

            for _ in range(_MAX_CRITIC_ITERATIONS):
                cresult = _critic.critique(
                    goal=goal,
                    response=current_response,
                    router=self._router,
                )
                if cresult.verdict == "ok":
                    break

                if cresult.verdict == "ambiguous":
                    current_response = current_response + f"\n\n_{_FYI} — {cresult.note}_"
                    break

                if tool_calls_made and cresult.verdict == "correctable":
                    current_response = current_response + f"\n\n_{_FYI} — {cresult.note}_"
                    break

                current_system = (
                    current_system
                    + f"\n\n[CRITIC NOTE: The previous response had this issue: "
                    f"{cresult.note} — please address it in your next response.]"
                )
                retry = self._router.route(
                    query=goal,
                    conversation_history=messages,
                    system_prompt=current_system,
                    force_route=force,
                )
                if retry.error:
                    break
                new_response = _SKILL_CALL_RE.sub("", retry.content or "").strip()
                if not new_response or new_response == current_response:
                    current_response = current_response + f"\n\n_{_FYI} — {cresult.note}_"
                    break
                current_response = new_response

            return current_response
        except Exception:
            return response  # critic must never crash the main loop (NFR-ORCH-013)
