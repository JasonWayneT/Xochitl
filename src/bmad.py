"""BMAD project detection, workflow loading, and BMAD-aware file saving."""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional


BMAD_STRUCTURE = {
    "planning": "planning-artifacts/",
    "implementation": "implementation-artifacts/",
    "architecture": "planning-artifacts/architecture/",
    "tests": "implementation-artifacts/tests/",
    "docs": "docs/",
    "sprint": "implementation-artifacts/sprints/",
    "ux": "planning-artifacts/ux/",
    "prd": "planning-artifacts/",
}

COMPLEX_WORKFLOWS = {
    "architecture", "prd", "sprint", "party_mode", "feature_planning",
}


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_bmad_project(cwd: Optional[Path] = None) -> Optional[dict]:
    """Walk up from cwd to find .clinerules/. Returns project info or None."""
    current = Path(cwd or Path.cwd())
    while current != current.parent:
        clinerules = current / ".clinerules"
        if clinerules.exists():
            return {
                "root": current,
                "version": _parse_version(clinerules),
                "modules": _detect_modules(clinerules),
                "workflows": _list_workflows(clinerules),
            }
        current = current.parent
    return None


def _parse_version(clinerules: Path) -> str:
    version_file = clinerules / "version.txt"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"


def _detect_modules(clinerules: Path) -> list[str]:
    modules = ["BMM"]
    if (clinerules / "test-architecture").exists():
        modules.append("TEA")
    if (clinerules / "game-dev").exists():
        modules.append("BMGD")
    if (clinerules / "creative-intelligence").exists():
        modules.append("CIS")
    if (clinerules / "builder").exists():
        modules.append("BMB")
    return modules


def _list_workflows(clinerules: Path) -> list[str]:
    workflows_dir = clinerules / "workflows"
    if not workflows_dir.exists():
        return []
    return [p.stem for p in workflows_dir.glob("*.md")]


def get_available_skills(cwd: Optional[Path] = None) -> list[str]:
    base_skills = [
        "task_management", "memory_manager", "notion_sync",
        "xochitl_help", "voice_editor", "file_generation",
    ]
    bmad_project = detect_bmad_project(cwd)
    if bmad_project:
        base_skills.extend(bmad_project["workflows"])
    return base_skills


# ── Workflow loading ───────────────────────────────────────────────────────────

def load_workflow_prompt(bmad_project: dict, workflow_name: str) -> Optional[str]:
    clinerules = bmad_project["root"] / ".clinerules"
    candidates = [
        clinerules / "workflows" / f"{workflow_name}.md",
        clinerules / "workflows" / f"bmad-{workflow_name}.md",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return None


def is_complex_workflow(workflow_name: str) -> bool:
    return any(kw in workflow_name.lower() for kw in COMPLEX_WORKFLOWS)


def build_bmad_context(bmad_project: dict) -> str:
    """Produce a compact BMAD context string for injection into cloud prompts."""
    return (
        f"BMAD Project: {bmad_project['root'].name}\n"
        f"Version: {bmad_project['version']}\n"
        f"Modules: {', '.join(bmad_project['modules'])}\n"
        f"Workflows: {', '.join(bmad_project['workflows'])}"
    )


# ── BMAD-aware file saving ────────────────────────────────────────────────────

def save_artifact(
    content: str,
    artifact_type: str,
    filename: Optional[str] = None,
    explicit_path: Optional[Path] = None,
    cwd: Optional[Path] = None,
) -> Path:
    if not filename:
        filename = _generate_filename(artifact_type)

    if explicit_path:
        target = explicit_path
    else:
        bmad_project = detect_bmad_project(cwd)
        if bmad_project:
            folder = BMAD_STRUCTURE.get(artifact_type, "docs/")
            target = bmad_project["root"] / folder
        else:
            target = Path(__file__).parent.parent / "data" / "generated"

    target.mkdir(parents=True, exist_ok=True)
    filepath = target / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


def _generate_filename(artifact_type: str) -> str:
    base_names = {
        "planning": "prd", "architecture": "architecture",
        "sprint": "sprint-stories", "ux": "wireframes",
        "tests": "test-plan", "docs": "documentation", "prd": "prd",
    }
    base = base_names.get(artifact_type, "document")
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"{base}-{timestamp}.md"


def clickable_path(filepath: Path) -> str:
    return f"file:///{filepath.as_posix()}"


# ── Workflow state persistence in MEMORY.md ───────────────────────────────────

def save_workflow_state(
    workflow: str,
    step: int,
    total_steps: int,
    context_snapshot: str,
) -> None:
    from src.memory import update_memory_section
    content = (
        f"- workflow: {workflow}\n"
        f"  step: {step}/{total_steps}\n"
        f"  context_snapshot: \"{context_snapshot[:100]}\"\n"
        f"  last_active: {datetime.now().isoformat()}"
    )
    update_memory_section("Paused Workflows", content)
