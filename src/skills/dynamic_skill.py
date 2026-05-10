"""Filesystem-backed dynamic skills for CR-004 stage 5.

Dynamic skills are read-only conversational skills loaded from:

- ~/.xochitl/skills/<skill-id>/
- <project>/.xochitl/skills/<skill-id>/

They expose metadata to the existing SkillManifestEngine and return their
SKILL.md instructions when invoked. Mutating behavior still belongs in regular
code-backed skills.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from src.skills.base import Skill


_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PROJECTS_DIR = _PROJECT_ROOT / "projects"
_META_NAME = "metadata.yaml"
_SKILL_NAME = "SKILL.md"


class DynamicSkill(Skill):
    """A skill definition loaded from a user or project skill folder."""

    def __init__(self, skill_dir: Path, scope: str, project_id: Optional[str] = None):
        self.skill_dir = Path(skill_dir)
        self.scope = scope
        self.project_id = project_id
        self.metadata = _read_metadata(self.skill_dir / _META_NAME)
        self.skill_id = self.metadata.get("id") or self.skill_dir.name
        self.name = self.metadata.get("name") or _title_from_slug(self.skill_id)
        self.description = self.metadata.get("description") or _read_first_paragraph(self.skill_dir / _SKILL_NAME)
        self.status = self.metadata.get("status", "enabled")

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()
        haystack = " ".join([
            self.skill_id,
            self.name,
            self.description,
            " ".join(self.metadata.get("tags", [])) if isinstance(self.metadata.get("tags"), list) else "",
        ]).lower()
        if self.status != "enabled":
            return 0.0
        if any(token and token in q for token in _tokens(haystack)):
            return 0.45
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        return f"I can use the `{self.name}` skill for this. Want me to pull in its workflow?"

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        usage = context.setdefault("dynamic_skill_usage", {})
        usage[self.skill_id] = usage.get(self.skill_id, 0) + 1
        body = _read_text(self.skill_dir / _SKILL_NAME)
        examples = _read_text(self.skill_dir / "examples.md")
        parts = [f"Using dynamic skill: **{self.name}**", body.strip()]
        if examples.strip():
            parts.extend(["", "Examples:", examples.strip()])
        return "\n\n".join(part for part in parts if part)

    def tool_definition(self) -> dict:
        safe_name = _safe_tool_name(self.skill_id)
        return {
            "name": safe_name,
            "description": self.description[:240],
            "when": self.metadata.get("when") or self.description[:240],
            "params": {},
        }


def load_dynamic_skills(project_id: Optional[str] = None) -> list[DynamicSkill]:
    """Load enabled global and project-local dynamic skills.

    Implements FR-ORCH-014 / AC-CR004-009.
    """
    skills: list[DynamicSkill] = []
    seen: set[str] = set()

    for scope, root in _skill_roots(project_id):
        if not root.exists():
            continue
        for skill_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            if (skill_dir / _SKILL_NAME).exists() is False:
                continue
            skill = DynamicSkill(skill_dir, scope, project_id if scope == "project" else None)
            if skill.status != "enabled":
                continue
            key = _safe_tool_name(skill.skill_id).lower()
            if key in seen:
                continue
            seen.add(key)
            skills.append(skill)

    return skills


def build_skill_creation_offer(user_input: str, context: dict) -> str:
    """Return a non-forcing offer to create a reusable skill."""
    scope = "project" if context.get("current_project") else "global"
    target = (
        f"`projects/{context['current_project']}/.xochitl/skills/`"
        if scope == "project"
        else "`~/.xochitl/skills/`"
    )
    return (
        "\n\nThis looks reusable. I can turn the workflow into a "
        f"{scope} skill under {target} after we finish, so next time it shows up "
        "in my skill manifest automatically."
    )


def _skill_roots(project_id: Optional[str]) -> list[tuple[str, Path]]:
    roots = [("global", Path.home() / ".xochitl" / "skills")]
    if project_id:
        roots.insert(0, ("project", _PROJECTS_DIR / project_id / ".xochitl" / "skills"))
    return roots


def _read_metadata(path: Path) -> dict:
    if not path.exists():
        return {}
    text = _read_text(path)
    return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict:
    data: dict = {}
    current_list_key: Optional[str] = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- ") and current_list_key:
            data.setdefault(current_list_key, []).append(line[2:].strip().strip("\"'"))
            continue
        current_list_key = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = value.strip("\"'")
    return data


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _read_first_paragraph(path: Path) -> str:
    text = _read_text(path).strip()
    if not text:
        return "User-defined workflow skill."
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    first = paragraphs[0] if paragraphs else text
    return re.sub(r"^# +", "", first).strip()


def _safe_tool_name(skill_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", skill_id).strip("_")
    if not slug:
        slug = "dynamic_skill"
    if not slug[0].isalpha():
        slug = f"skill_{slug}"
    return f"DynamicSkill_{slug}"


def _title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", slug) if part) or "Dynamic Skill"


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]{4,}", text.lower())[:20]]
