"""Shared utilities for Xochitl skills.

Centralises the three patterns that every skill duplicated:
  - project meta read/write (.project-meta.yml)
  - LLM calls via TieredRouter
  - JSON response parsing with markdown-fence stripping and a single retry
"""

import json
import re
from pathlib import Path
from typing import Optional

from src.skills._yaml_helpers import yaml_load, yaml_dump

_PROJECT_ROOT = Path(__file__).parent.parent.parent
PROJECTS_DIR = _PROJECT_ROOT / "projects"


# ── Project metadata ──────────────────────────────────────────────────────────

def read_project_meta(project_id: str) -> dict:
    meta_path = PROJECTS_DIR / project_id / ".project-meta.yml"
    if not meta_path.exists():
        return {}
    try:
        return yaml_load(meta_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def write_project_meta(project_id: str, meta: dict) -> None:
    meta_path = PROJECTS_DIR / project_id / ".project-meta.yml"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(yaml_dump(meta), encoding="utf-8")


# ── LLM call ─────────────────────────────────────────────────────────────────

def call_skill_llm(prompt: str, system_context: str, route: str = "bmad_complex") -> str:
    """Route a prompt through TieredRouter and return the response text."""
    from src.router import get_router
    router = get_router()
    result = router.route(
        query=prompt,
        conversation_history=[],
        system_prompt=system_context,
        force_route=route,
    )
    return result.content if not result.error else ""


# ── JSON response parsing ─────────────────────────────────────────────────────

def parse_skill_json(
    response_text: str,
    retry_prompt: str = "",
    retry_system: str = "",
    retry_route: str = "bmad_complex",
) -> dict:
    """Strip markdown fences and parse JSON from an LLM response.

    Retries once with an explicit correction prompt if the first parse fails.
    Returns {"error": ..., "raw": ...} on total failure.
    """

    def _try_parse(text: str) -> Optional[dict]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    parsed = _try_parse(response_text)
    if parsed is not None:
        return parsed

    if retry_prompt:
        retry_text = call_skill_llm(
            f"Your previous response was not valid JSON. "
            f"Return ONLY a JSON object, no markdown wrapping.\n\n{retry_prompt}",
            retry_system,
            route=retry_route,
        )
        parsed = _try_parse(retry_text)
        if parsed is not None:
            return parsed

    return {"error": "Could not parse LLM response as JSON", "raw": response_text[:500]}
