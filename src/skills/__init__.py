"""Register all built-in skills into the module-level _registry singleton.

Skills are imported and instantiated here rather than self-registering at
import time. This prevents import-order races and circular import risk.
Each skill is wrapped in _safe_register() so credential failures (e.g.
GmailSkill missing a token file) skip that skill with a warning instead of
crashing startup.
"""
from __future__ import annotations

import logging
from src.skills.registry import _registry  # noqa: F401 — re-exported for callers
from src.skills.base import Skill  # noqa: F401 — re-exported for callers

_log = logging.getLogger("xochitl.skill_registry")


def _safe_register(skill_class: type, *args, **kwargs) -> None:
    try:
        _registry.register(skill_class(*args, **kwargs))
    except Exception as exc:
        _log.warning("Failed to load %s: %s", skill_class.__name__, exc)


# Core skills — order matches the original hardcoded list in chat.py @property skills.
from src.skills.bmad_skill import BMADSkill
_safe_register(BMADSkill)

from src.skills.sdd_skill import SDDSkill
_safe_register(SDDSkill)

from src.skills.code_skill import CodeSkill
_safe_register(CodeSkill)

from src.skills.notion_skill import NotionSkill
_safe_register(NotionSkill)

from src.skills.orchestrator_skill import OrchestratorSkill
_safe_register(OrchestratorSkill)

from src.skills.weather_skill import WeatherSkill
_safe_register(WeatherSkill)

from src.skills.web_lookup_skill import WebLookupSkill
_safe_register(WebLookupSkill)

from src.skills.zettelkasten_skill import ZettelkastenSkill
_safe_register(ZettelkastenSkill)

from src.skills.explorer_skill import ExplorerSkill
_safe_register(ExplorerSkill)

from src.skills.workflow_skill import WorkflowSkill
_safe_register(WorkflowSkill)

from src.skills.maps_skill import MapsSkill
_safe_register(MapsSkill)

from src.skills.gmail_skill import GmailSkill
_safe_register(GmailSkill)

# CR-052 — tool execution skills.
from src.skills.shell_skill import ShellSkill
_safe_register(ShellSkill)

from src.skills.git_skill import GitSkill
_safe_register(GitSkill)

from src.skills.project_scan_skill import ProjectScanSkill
_safe_register(ProjectScanSkill)

# CR-053 — Perplexity-grade research pipeline (FR-RES-020).
# Registered after ExplorerSkill so it doesn't shadow multi-hop investigation mode.
from src.skills.research_skill import ResearchSkill
_safe_register(ResearchSkill)

# CR-054 Phase 3 — seed SkillVectorIndex at session start (FR-ROUTE-007).
# Best-effort: failure must not block startup.
def _seed_skill_vector() -> None:
    try:
        from src.skill_vector import SkillVectorIndex
        SkillVectorIndex().seed_from_skills(_registry.all())
    except Exception as exc:
        _log.debug("skill_vector seed skipped: %s", exc)

try:
    import threading
    threading.Thread(target=_seed_skill_vector, daemon=True, name="skill-vector-seed").start()
except Exception:
    pass
