"""BMAD workflow skill — detects BMAD projects, guides new project creation, saves artifacts."""
# Implements FR-BMAD-001 (Discovery Session Facilitation — init_project() scaffolds project dirs and metadata)
# Implements FR-BMAD-002 (PRD & SDD Artifact Generation — save_bmad_artifact() writes BMAD docs to bmad/ folder)

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.skills.base import Skill
from src.skills._yaml_helpers import yaml_load, yaml_dump


_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PROJECTS_DIR = _PROJECT_ROOT / "projects"

_PLANNING_KEYWORDS = ["plan", "design", "architect", "prd", "feature", "workflow", "sprint"]
_BUILD_KEYWORDS = [
    "build", "rebuild", "rebuilding", "create app", "new app", "new project", "start project",
    "make an app", "i want to build", "i want to make", "i want to create",
]


class BMADSkill(Skill):

    # ── Skill interface ───────────────────────────────────────────────────────

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()

        # Existing BMAD project detected via .clinerules/
        if context.get("bmad_project"):
            if any(kw in q for kw in _PLANNING_KEYWORDS):
                return 0.8
            return 0.1

        # New project initialization request
        if any(kw in q for kw in _BUILD_KEYWORDS):
            return 0.75

        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        q = user_input.lower()

        # New project init
        if any(kw in q for kw in _BUILD_KEYWORDS) and not context.get("bmad_project"):
            return (
                "Let's break this down properly. I'll set up a BMAD project structure "
                "and walk you through Business Model → Architecture → Design before writing any code. "
                "Want to start?"
            )

        # Existing BMAD project
        bmad_project = context.get("bmad_project", {})
        modules = ", ".join(bmad_project.get("modules", ["BMM"]))
        return (
            f"You're in a BMAD project with {modules} modules. "
            "I can walk you through the planning workflow. "
            "Want to do it together (I'll ask questions) or should I draft something for you to review?"
        )

    def tool_definition(self) -> dict:
        # Implements FR-ORCH-005
        return {
            "name": "BMADSkill",
            "description": "Initializes and guides a BMAD project lifecycle: Business Model → Architecture → Design → Code.",
            "when": "user wants to build, create, or make a new app or project; OR user is in a BMAD project and asks about planning, architecture, PRD, sprint, or workflow",
            "params": {
                "action": "init_project | walk_workflow",
                "name": "(optional) project name extracted from user message",
            },
            "timeout_secs": 180,
            "examples": [
                "I want to build a recipe app",
                "let's start a new project",
                "help me plan the architecture for my app",
                "initialize a BMAD project",
                "I need a PRD for my idea",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        action = params.get("action", "")

        if action == "init_project":
            result = self.init_project(
                params["project_id"],
                params["name"],
                params.get("description", ""),
            )
            return (
                f"Created project '{result['name']}' at projects/{result['project_id']}/\n\n"
                "Let's start the BMAD process. First: what's the core problem this app solves? "
                "Who's struggling with it and what do they currently do instead?"
            )

        if action == "save_bmad_artifact":
            path = self.save_bmad_artifact(
                params["project_id"],
                params["artifact_type"],
                params["content"],
            )
            return f"Saved {params['artifact_type']} → {path}"

        if action == "list":
            projects = self.list_projects()
            if not projects:
                return "No SDD projects yet. Say 'I want to build X' to start one."
            lines = [f"  [{p['status'].upper()}] {p['name']} (projects/{p['project_id']}/)" for p in projects]
            return "SDD projects:\n" + "\n".join(lines)

        # Existing mode-based routing for .clinerules/ BMAD
        mode = params.get("mode", "guided")
        bmad_project = context.get("bmad_project", {})
        if mode == "guided":
            return self._guided_workflow(bmad_project)
        return self._draft_workflow(user_input, bmad_project)

    # ── Project lifecycle ─────────────────────────────────────────────────────

    def init_project(self, project_id: str, name: str, description: str) -> dict:
        """Create projects/<project_id>/ BMAD and SDD workspace scaffolding."""
        # Implements FR-SDD-005 / AC-CR004-010.
        project_path = _PROJECTS_DIR / project_id
        for subdir in [
            "bmad",
            "specs",
            "docs",
            "issues/open",
            "issues/in-progress",
            "issues/closed",
            "src",
            "tests",
            ".xochitl/skills",
        ]:
            (project_path / subdir).mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat()
        meta = {
            "project_id": project_id,
            "name": name,
            "description": description,
            "created": now,
            "status": "active",
            "bmad_complete": False,
            "specs_generated": False,
            "code_scaffolded": False,
            "sdd_scaffolded": True,
            "stack": {"backend": None, "frontend": None, "database": None},
            "stats": {"total_requirements": 0, "implemented_requirements": 0, "open_issues": 0},
            "last_worked": now,
        }
        self._write_meta(project_id, meta)
        self._write_initial_bmad_scaffold(project_path, name, description)
        self._write_initial_sdd_scaffold(project_path, project_id, name, description, now)
        self._write_project_agents(project_path, name)
        self._write_project_skill_readme(project_path)
        return {"project_id": project_id, "name": name, "path": str(project_path)}

    def _write_initial_bmad_scaffold(self, project_path: Path, name: str, description: str) -> None:
        self._write_if_missing(
            project_path / "bmad" / "README.md",
            f"""# BMAD Artifacts - {name}

Use this folder for discovery and planning before SDD requirements are generated.

Suggested order:

1. `business-model.md`
2. `architecture.md`
3. `design-specs.md`
4. `constraints.md`
""",
        )
        for filename, title in {
            "business-model.md": "Business Model",
            "architecture.md": "Architecture",
            "design-specs.md": "Design Specs",
            "constraints.md": "Constraints",
        }.items():
            self._write_if_missing(
                project_path / "bmad" / filename,
                f"""# {title} - {name}

Status: draft

## Project Summary

{description or "_To be discovered._"}

## Notes

- Capture decisions here before generating SDD requirements.
""",
            )

    def _write_initial_sdd_scaffold(
        self,
        project_path: Path,
        project_id: str,
        name: str,
        description: str,
        created_at: str,
    ) -> None:
        self._write_if_missing(
            project_path / "specs" / "README.md",
            f"""# SDD Specs - {name}

Specs in this folder are the source of truth for implementation.

Workflow:

1. Finish BMAD artifacts in `../bmad/`.
2. Generate or edit `core-features.md` with requirement IDs.
3. Keep `traceability.json` aligned with requirements, code, tests, and issues.
4. Cite requirement IDs in generated code.
""",
        )
        self._write_if_missing(
            project_path / "specs" / "core-features.md",
            f"""---
feature: core
owner: you
status: draft
---

# Core Features - {name}

Project ID: `{project_id}`

## Source

{description or "_To be discovered from BMAD artifacts._"}

## Requirements

_Generate requirements after BMAD business model and architecture are ready._
""",
        )
        traceability = {
            "project": project_id,
            "version": "1.0",
            "last_updated": created_at,
            "mappings": [],
        }
        self._write_if_missing(
            project_path / "specs" / "traceability.json",
            json.dumps(traceability, indent=2),
        )

    def _write_project_agents(self, project_path: Path, name: str) -> None:
        self._write_if_missing(
            project_path / "AGENTS.md",
            f"""# Agent Instructions for {name}

This project uses the Xochitl BMAD to SDD to code workflow.

## Prime Directive

Do not edit code first. Material changes start from the planning chain:

1. Review BMAD artifacts in `bmad/`.
2. Review SDD specs in `specs/`.
3. Identify or create requirement IDs.
4. Update specs and `specs/traceability.json`.
5. Create or update implementation tasks.
6. Modify code in `src/`.
7. Add or update tests in `tests/`.
8. Run verification and record results.

## Requirement IDs

Use Xochitl-style IDs such as `FR-CORE-001`, `AC-CORE-001`, `TEST-CORE-001`,
`BUG-CORE-001`, and `ADR-001`. Every generated code path should cite the
requirement it implements in a short comment.

## Safety Rules

- Treat BMAD and SDD docs as source of truth when code disagrees.
- Do not silently invent requirements.
- Do not delete or rename requirement IDs without recording a replacement.
- Keep traceability current before marking work complete.
- Ask for approval before destructive file operations or external side effects.
""",
        )

    def _write_project_skill_readme(self, project_path: Path) -> None:
        self._write_if_missing(
            project_path / ".xochitl" / "skills" / "README.md",
            """# Project Skills

Place project-local dynamic skills here.

Expected structure:

```text
<skill-id>/
  SKILL.md
  metadata.yaml
  examples.md
  scripts/
  templates/
```

Enabled skills are loaded into Xochitl's conversational skill manifest while
working in this project.
""",
        )

    def _write_if_missing(self, path: Path, content: str) -> None:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.strip() + "\n", encoding="utf-8")

    def save_bmad_artifact(self, project_id: str, artifact_type: str, content: str) -> str:
        """Write to projects/<project_id>/bmad/<artifact_type>.md."""
        valid_types = {"business-model", "architecture", "design-specs", "constraints"}
        if artifact_type not in valid_types:
            raise ValueError(f"artifact_type must be one of: {valid_types}")

        artifact_path = _PROJECTS_DIR / project_id / "bmad" / f"{artifact_type}.md"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(content, encoding="utf-8")

        # Check if all required BMAD artifacts now exist
        required = {"business-model", "architecture"}
        existing = {p.stem for p in (_PROJECTS_DIR / project_id / "bmad").glob("*.md")}
        if required.issubset(existing):
            meta = self._read_meta(project_id)
            if not meta.get("bmad_complete"):
                meta["bmad_complete"] = True
                meta["last_worked"] = datetime.now().isoformat()
                self._write_meta(project_id, meta)

        return f"projects/{project_id}/bmad/{artifact_type}.md"

    def get_bmad_artifacts(self, project_id: str) -> dict:
        """Return all bmad/*.md files as {stem: content}."""
        bmad_dir = _PROJECTS_DIR / project_id / "bmad"
        if not bmad_dir.exists():
            return {}
        result = {}
        for md_file in sorted(bmad_dir.glob("*.md")):
            try:
                result[md_file.stem] = md_file.read_text(encoding="utf-8")
            except Exception:
                pass
        return result

    def is_bmad_complete(self, project_id: str) -> bool:
        """True if .project-meta.yml has bmad_complete=true and business-model.md exists."""
        meta = self._read_meta(project_id)
        if meta.get("bmad_complete"):
            return True
        # Re-derive from file presence in case meta is stale
        bmad_dir = _PROJECTS_DIR / project_id / "bmad"
        return (bmad_dir / "business-model.md").exists() and (bmad_dir / "architecture.md").exists()

    def list_projects(self) -> list[dict]:
        """Scan projects/ and return metadata for each project."""
        if not _PROJECTS_DIR.exists():
            return []
        results = []
        for project_dir in sorted(_PROJECTS_DIR.iterdir()):
            if not project_dir.is_dir():
                continue
            meta = self._read_meta(project_dir.name)
            if meta:
                results.append(meta)
        return results

    def update_project_stack(self, project_id: str, stack: dict) -> None:
        """Update the stack section of .project-meta.yml."""
        meta = self._read_meta(project_id)
        meta.setdefault("stack", {}).update(stack)
        meta["last_worked"] = datetime.now().isoformat()
        self._write_meta(project_id, meta)

    # ── Existing .clinerules/ workflow ────────────────────────────────────────

    def _guided_workflow(self, bmad_project: dict) -> str:
        return (
            "Let's plan this out. First question: what's the core job to be done? "
            "What problem does this feature actually solve for the user?"
        )

    def _draft_workflow(self, user_input: str, bmad_project: dict) -> str:
        return (
            "Got it. To draft the planning artifacts I'll need a bit more context. "
            "Give me the one-sentence pitch: what's the feature?"
        )

    # ── Meta helpers ──────────────────────────────────────────────────────────

    def _read_meta(self, project_id: str) -> dict:
        meta_path = _PROJECTS_DIR / project_id / ".project-meta.yml"
        if not meta_path.exists():
            return {}
        try:
            return yaml_load(meta_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _write_meta(self, project_id: str, meta: dict) -> None:
        meta_path = _PROJECTS_DIR / project_id / ".project-meta.yml"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(yaml_dump(meta), encoding="utf-8")
