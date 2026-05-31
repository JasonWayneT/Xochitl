"""SkillRegistry — decouples skill registration from XochitlChat.

Skills are registered explicitly from src/skills/__init__.py rather than
self-registering at import time. This avoids import-order races and circular
import risk, and makes credential-failing skills (e.g. GmailSkill) skippable
at startup without crashing the session.

Usage:
    from src.skills import _registry
    skills = _registry.all()
    skill  = _registry.by_name("WeatherSkill")
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.skills.base import Skill

_log = logging.getLogger("xochitl.skill_registry")


class SkillRegistry:
    """Thread-safe registry of Skill instances."""

    def __init__(self) -> None:
        self._skills: list[Skill] = []
        self._by_name: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """Add a skill. Duplicate class names are ignored with a warning.

        Args:
            skill: Instantiated Skill to register.
        """
        name = type(skill).__name__
        if name in self._by_name:
            _log.warning("SkillRegistry: duplicate registration ignored for %s", name)
            return
        self._skills.append(skill)
        self._by_name[name] = skill

        # Also index by tool_definition name (lower-cased) for @-routing.
        try:
            defn_name = skill.tool_definition().get("name", "").lower()
            if defn_name and defn_name not in self._by_name:
                self._by_name[defn_name] = skill
        except Exception:
            pass

    def all(self) -> list[Skill]:
        """Return all registered skills in registration order.

        Returns:
            Snapshot list; safe to iterate while new skills are registered.
        """
        return list(self._skills)

    def by_name(self, name: str) -> Skill | None:
        """Look up a skill by class name or tool_definition name (case-insensitive).

        Args:
            name: Skill class name (e.g. "WeatherSkill") or tool name.

        Returns:
            Matching Skill instance, or None.
        """
        key = name.lower() if name else ""
        # Try exact class name first, then lower-case tool name.
        return (
            self._by_name.get(name)
            or self._by_name.get(key)
        )

    def reload_dynamic(self, project_path: str | None) -> None:
        """Remove previously loaded dynamic skills and reload from project_path.

        Args:
            project_path: Path string for the active project, or None to clear only.
        """
        try:
            from src.skills.dynamic_skill import load_dynamic_skills
            dynamic = load_dynamic_skills(project_path)
        except Exception as exc:
            _log.warning("reload_dynamic failed: %s", exc)
            return

        for skill in dynamic:
            name = type(skill).__name__
            if name not in self._by_name:
                self._skills.append(skill)
                self._by_name[name] = skill

    def clear(self) -> None:
        """Remove all registrations. Used in tests only."""
        self._skills.clear()
        self._by_name.clear()


_registry = SkillRegistry()
