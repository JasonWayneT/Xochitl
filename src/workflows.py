"""Procedural memory — reusable multi-step workflows (CR-041, CR-042).

CR-041: SQLite storage, keyword recall, prompt injection, save offer.
CR-042: Embedding index, LLM distillation, workflow executor.
"""
# Implements FR-MEM-008 through FR-MEM-014

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional

from src import database as db
from src.terminal_output import format_step

_MATCH_THRESHOLD = 0.50
_EMBED_WEIGHT = 0.55
_KEYWORD_WEIGHT = 0.45
_MAX_BLOCK_CHARS = 2000
_AUTO_RUN_THRESHOLD = 0.85

_DISTILL_PROMPT = """You distill a successful multi-step session into a reusable workflow.
Return ONLY valid JSON (no markdown fences) with this shape:
{{
  "trigger_pattern": "short phrases that should recall this workflow",
  "steps": [
    {{"skill": "SkillClassName", "description": "what this step does", "params": {{}}}}
  ],
  "expected_outputs": "what done looks like",
  "failure_modes": "what can go wrong"
}}
Use Skill names from the session (e.g. NotionSkill, WeatherSkill). Max 8 steps.

Session transcript:
{transcript}
"""


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def score_workflow_match(query: str, trigger_pattern: str, name: str) -> float:
    """Keyword overlap score (FR-MEM-009)."""
    q = _tokenize(query)
    if not q:
        return 0.0
    hay = _tokenize(f"{trigger_pattern} {name}")
    if not hay:
        return 0.0
    overlap = len(q & hay) / len(q)
    if overlap < 0.25:
        return 0.0
    return min(0.95, overlap * 1.15)


def _build_transcript(session_history: list[dict], max_chars: int = 6000) -> str:
    lines: list[str] = []
    for msg in session_history[-30:]:
        role = msg.get("role", "")
        content = (msg.get("content") or "")[:800]
        if role == "tool":
            skill = msg.get("skill", "tool")
            lines.append(f"TOOL {skill}: {content}")
        elif role in ("user", "assistant"):
            lines.append(f"{role.upper()}: {content}")
    text = "\n".join(lines)
    return text[:max_chars]


def distill_workflow_trajectory(
    session_history: list[dict],
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    """LEGOMem-style distillation via local LLM (FR-MEM-013).

    Args:
        session_history: Recent session messages.
        use_llm: When False, mechanical fallback only.

    Returns:
        Dict with trigger_pattern, steps, expected_outputs, failure_modes.
    """
    mechanical_steps = distill_steps_from_history(session_history)
    fallback = {
        "trigger_pattern": "",
        "steps": mechanical_steps,
        "expected_outputs": "",
        "failure_modes": "",
        "source": "mechanical",
    }
    if not use_llm or len(mechanical_steps) < 2:
        return fallback

    transcript = _build_transcript(session_history)
    if not transcript.strip():
        return fallback

    try:
        from src.llm_interface import call_local, ROUTER_MODEL
        result = call_local(
            messages=[{
                "role": "user",
                "content": _DISTILL_PROMPT.format(transcript=transcript),
            }],
            model=ROUTER_MODEL,
            temperature=0.2,
        )
        if result.error or not result.content:
            return fallback
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        steps = parsed.get("steps") or mechanical_steps
        if not isinstance(steps, list) or len(steps) < 2:
            steps = mechanical_steps
        return {
            "trigger_pattern": str(parsed.get("trigger_pattern") or "")[:500],
            "steps": steps,
            "expected_outputs": str(parsed.get("expected_outputs") or "")[:500],
            "failure_modes": str(parsed.get("failure_modes") or "")[:500],
            "source": "llm",
        }
    except Exception:
        return fallback


def _row_to_workflow(row: Any, match_score: float = 0.0) -> dict[str, Any]:
    steps_raw = row["steps_json"] or "[]"
    try:
        steps = json.loads(steps_raw)
    except json.JSONDecodeError:
        steps = []
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "trigger_pattern": row["trigger_pattern"],
        "steps": steps if isinstance(steps, list) else [],
        "expected_outputs": row["expected_outputs"] or "",
        "failure_modes": row["failure_modes"] or "",
        "project": row["project"],
        "source": row["source"],
        "confidence": float(row["confidence"]),
        "success_count": int(row["success_count"] or 0),
        "failure_count": int(row["failure_count"] or 0),
        "match_score": match_score,
    }


def _hybrid_scores(
    query: str,
    rows: list[Any],
    *,
    project: Optional[str] = None,
) -> list[tuple[Any, float, str]]:
    """Combine keyword and embedding scores per workflow row."""
    from src.workflow_vector import WorkflowVectorIndex

    embed_hits = {
        h["workflow_id"]: h["score"]
        for h in WorkflowVectorIndex().search(query, project=project, limit=20)
    }
    scored: list[tuple[Any, float, str]] = []
    for row in rows:
        wid = int(row["id"])
        kw = score_workflow_match(query, row["trigger_pattern"], row["name"])
        emb = embed_hits.get(wid, 0.0)
        if emb > 0 and kw > 0:
            combined = _EMBED_WEIGHT * emb + _KEYWORD_WEIGHT * kw
            method = "hybrid"
        elif emb >= kw:
            combined = emb
            method = "embedding"
        else:
            combined = kw
            method = "keyword"
        scored.append((row, combined, method))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def search_workflows_by_intent(
    query: str,
    *,
    project: Optional[str] = None,
    use_embeddings: bool = True,
) -> Optional[dict[str, Any]]:
    """Top-1 workflow via hybrid keyword + embedding search (FR-MEM-009, FR-MEM-012)."""
    with db.get_connection() as conn:
        rows = db.list_workflows(conn, project=project)
    if not rows:
        return None

    if use_embeddings:
        scored = _hybrid_scores(query, rows, project=project)
        if scored and scored[0][1] >= _MATCH_THRESHOLD:
            row, score, _method = scored[0]
            return _row_to_workflow(row, score)
        return None

    best: Optional[dict[str, Any]] = None
    best_score = 0.0
    for row in rows:
        score = score_workflow_match(query, row["trigger_pattern"], row["name"])
        if score > best_score:
            best_score = score
            best = _row_to_workflow(row, score)
    if best is None or best_score < _MATCH_THRESHOLD:
        return None
    best["match_score"] = best_score
    return best


def get_workflow_by_name(name: str) -> Optional[dict[str, Any]]:
    """Load active workflow dict by name."""
    with db.get_connection() as conn:
        row = db.get_workflow(conn, name)
    if not row:
        return None
    return _row_to_workflow(row, 0.0)


def format_workflow_block(workflow: dict[str, Any]) -> str:
    """Format workflow for system-prompt injection (FR-MEM-010)."""
    lines = [
        "[PROCEDURAL WORKFLOW]",
        f"Name: {workflow.get('name', 'workflow')}",
        f"Trigger: {workflow.get('trigger_pattern', '')}",
        "Steps:",
    ]
    for i, step in enumerate(workflow.get("steps") or [], start=1):
        label = step.get("description") or step.get("skill") or step.get("type") or "step"
        lines.append(f"  {i}. {label}")
    if workflow.get("expected_outputs"):
        lines.append(f"Expected: {workflow['expected_outputs']}")
    if workflow.get("failure_modes"):
        lines.append(f"Watch for: {workflow['failure_modes']}")
    lines.append("Follow this sequence when appropriate. Do not dump raw tool logs.")
    if float(workflow.get("match_score") or 0) >= _AUTO_RUN_THRESHOLD:
        lines.append(f"Strong match — user may run `/workflow run {workflow.get('name')}` to execute.")
    block = "\n".join(lines)
    if len(block) > _MAX_BLOCK_CHARS:
        block = block[: _MAX_BLOCK_CHARS - 20].rstrip() + "\n[truncated]"
    return block


def distill_steps_from_history(session_history: list[dict]) -> list[dict]:
    """Mechanical step list from tool turns (CR-041 fallback)."""
    steps: list[dict] = []
    for msg in session_history:
        if msg.get("role") != "tool":
            continue
        skill = msg.get("skill") or "tool"
        snippet = (msg.get("content") or "")[:120].replace("\n", " ")
        steps.append({
            "type": "skill",
            "skill": skill,
            "description": f"Run {skill}" + (f" — {snippet}" if snippet else ""),
            "params": {},
        })
    return steps


def _index_workflow_embedding(workflow_id: int, name: str, trigger: str, project: Optional[str]) -> None:
    try:
        from src.workflow_vector import WorkflowVectorIndex
        WorkflowVectorIndex().index_workflow(
            workflow_id, name, trigger, project=project or "",
        )
    except Exception:
        pass


def save_workflow_from_session(
    name: str,
    trigger_pattern: str,
    session_history: list[dict],
    *,
    project: Optional[str] = None,
    source: str = "distilled",
    use_llm_distill: bool = True,
) -> int:
    """Persist workflow; LLM distill when enabled (FR-MEM-008, FR-MEM-011, FR-MEM-013)."""
    distilled = distill_workflow_trajectory(session_history, use_llm=use_llm_distill)
    steps = distilled.get("steps") or []
    if len(steps) < 2:
        raise ValueError("Need at least two steps to save a workflow")
    trigger = trigger_pattern.strip() or distilled.get("trigger_pattern") or name
    with db.get_connection() as conn:
        wid = db.upsert_workflow(
            conn,
            name,
            trigger,
            steps,
            expected_outputs=distilled.get("expected_outputs") or None,
            failure_modes=distilled.get("failure_modes") or None,
            project=project,
            source=source if distilled.get("source") != "llm" else "distilled",
        )
    _index_workflow_embedding(wid, name, trigger, project)
    return wid


def find_skill_by_name(skills: list[Any], name: str) -> Any:
    """Resolve a skill instance from class or tool name."""
    if not name:
        return None
    target = name.strip().lower()
    for skill in skills:
        cls = type(skill).__name__.lower()
        if cls == target or cls == f"{target}skill":
            return skill
        try:
            defn = skill.tool_definition()
            if defn.get("name", "").lower() == target:
                return skill
        except Exception:
            continue
    return None


def execute_workflow(
    workflow: dict[str, Any],
    user_input: str,
    skills: list[Any],
    context: dict,
) -> str:
    """Run each workflow step through matching skills (FR-MEM-014).

    Args:
        workflow: Workflow dict with steps list.
        user_input: Original user message (passed to each skill).
        skills: Loaded skill instances from XochitlChat.
        context: Shared context dict.

    Returns:
        Formatted multi-step result for the user.
    """
    steps = workflow.get("steps") or []
    if not steps:
        return "Workflow has no steps."

    total = len(steps)
    lines = [f"**Running workflow: {workflow.get('name')}** ({total} steps)\n"]
    failures = 0

    for i, step in enumerate(steps, start=1):
        label = step.get("description") or step.get("skill") or f"Step {i}"
        skill_name = step.get("skill") or ""
        lines.append(format_step(i, total, label, done=False))

        skill = find_skill_by_name(skills, skill_name)
        if not skill:
            lines.append(f"  [fail] Skill not found: {skill_name or '(none)'}")
            failures += 1
            lines.append(format_step(i, total, label, done=True))
            continue

        params = step.get("params") if isinstance(step.get("params"), dict) else {}
        try:
            out = skill.execute(user_input, context, params)
            preview = (out or "").strip()
            if len(preview) > 400:
                preview = preview[:397] + "..."
            lines.append(f"  {preview}")
        except Exception as exc:
            lines.append(f"  [fail] {type(exc).__name__}: {exc}")
            failures += 1
        lines.append(format_step(i, total, label, done=True))

    if failures:
        record_match_usage(int(workflow["id"]), success=False)
        lines.append(f"\nCompleted with {failures} step failure(s).")
    else:
        record_match_usage(int(workflow["id"]), success=True)
        lines.append("\nWorkflow finished successfully.")
    return "\n".join(lines)


def list_workflows_formatted(project: Optional[str] = None) -> str:
    """Human-readable workflow list."""
    with db.get_connection() as conn:
        rows = db.list_workflows(conn, project=project)
    if not rows:
        return "No saved workflows yet. After a multi-step task: `/workflow save <name>`"
    lines = ["**Saved workflows**"]
    for row in rows:
        steps = json.loads(row["steps_json"] or "[]")
        lines.append(
            f"- **{row['name']}** ({len(steps)} steps) — trigger: {row['trigger_pattern'][:60]}"
        )
    lines.append("\nRun: `/workflow run <name>`")
    return "\n".join(lines)


def build_workflow_save_offer(user_input: str) -> str:
    """Offer saving a procedural workflow."""
    return (
        "\n\n---\n"
        "This looked like a repeatable routine. Save it as a procedural workflow?\n"
        "  `/workflow save <name>` — LLM-distilled steps from this session\n"
        "  `/workflow run <name>` — execute a saved workflow\n"
        "  `/workflows` — list saved workflows\n"
        "---"
    )


def record_match_usage(workflow_id: int, *, success: bool = True) -> None:
    """Update workflow run stats."""
    with db.get_connection() as conn:
        db.record_workflow_run(conn, workflow_id, success=success)
