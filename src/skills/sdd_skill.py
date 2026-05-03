"""SDD (Spec-Driven Development) skill — requirements, issues, and traceability."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.skills.base import Skill
from src.skills._yaml_helpers import yaml_load, yaml_dump


_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PROJECTS_DIR = _PROJECT_ROOT / "projects"
_SDD_DIR = _PROJECT_ROOT / ".sdd"

_SDD_KEYWORDS = [
    "spec", "requirement", "fr-", "ac-", "ec-",
    "analyze", "traceability", "requirements",
]
_ISSUE_KEYWORDS = [
    "bug", "issue", "broken", "doesn't work", "error",
    "problem", "failing", "wrong behavior",
]


class SDDSkill(Skill):

    # ── Skill interface ───────────────────────────────────────────────────────

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()
        score = 0.0

        for kw in _SDD_KEYWORDS:
            if kw in q:
                score += 0.2
        for kw in _ISSUE_KEYWORDS:
            if kw in q:
                score += 0.15

        if context.get("current_project"):
            score += 0.25

        return min(score, 1.0)

    def suggest(self, user_input: str, context: dict) -> str:
        q = user_input.lower()
        project_id = context.get("current_project")

        if project_id and not context.get("specs_generated") and context.get("bmad_complete"):
            return (
                "BMAD is complete. Want me to generate SDD requirements from your "
                "business model and architecture? I'll produce 10–15 testable requirements."
            )

        if any(kw in q for kw in _ISSUE_KEYWORDS) and project_id:
            return (
                "I can analyze this against your specs — find whether it's a spec gap, "
                "a spec bug, or a code bug — and suggest the exact requirement update. Should I?"
            )

        if "spec" in q or "requirement" in q:
            return "I can help with spec-driven development: creating, updating, and tracing requirements."

        return "I can manage your SDD requirements and issue tracking."

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        action = params.get("action", "")
        project_id = params.get("project_id") or context.get("current_project", "")

        if action == "generate_specs":
            return self.generate_specs_from_bmad(project_id)
        if action == "list_requirements":
            reqs = self.list_requirements(project_id)
            if not reqs:
                return "No requirements found. Generate specs first."
            lines = [f"  {r['id']}: {r['description'][:80]} [{r['status']}]" for r in reqs]
            return "\n".join(lines)
        if action == "get_requirement":
            req = self.get_requirement(project_id, params["requirement_id"])
            return json.dumps(req, indent=2) if req else f"{params['requirement_id']} not found."
        if action == "create_requirement":
            return self.create_requirement(project_id, params.get("req_type", "CORE"), params.get("content", {}))
        if action == "analyze_issue":
            return json.dumps(self.analyze_issue(project_id, params.get("issue_description", user_input)), indent=2)
        if action == "create_issue":
            return self.create_issue(project_id, params.get("issue_type", "bug"), params.get("title", ""), params.get("description", user_input))
        if action == "update_requirement":
            return self.update_requirement(project_id, params["requirement_id"], params.get("updates", {}))

        return "Specify an action: generate_specs, list_requirements, get_requirement, analyze_issue, create_issue, update_requirement."

    # ── Spec generation ───────────────────────────────────────────────────────

    def generate_specs_from_bmad(self, project_id: str) -> str:
        """Generate SDD requirements from completed BMAD artifacts via LLM."""
        from src.skills.bmad_skill import BMADSkill
        bmad = BMADSkill()

        if not bmad.is_bmad_complete(project_id):
            artifacts = bmad.get_bmad_artifacts(project_id)
            missing = [k for k in ["business-model", "architecture"] if k not in artifacts]
            return f"BMAD is incomplete. Missing: {', '.join(missing)}. Complete BMAD first."

        artifacts = bmad.get_bmad_artifacts(project_id)
        system_ctx = self._load_sdd_prompt("spec-generation")

        design_section = (
            f"\nDESIGN SPECS:\n{artifacts['design-specs']}"
            if "design-specs" in artifacts else ""
        )
        prompt = (
            f"Generate SDD requirements from these BMAD artifacts.\n\n"
            f"BUSINESS MODEL:\n{artifacts.get('business-model', '(not found)')}\n\n"
            f"ARCHITECTURE:\n{artifacts.get('architecture', '(not found)')}"
            f"{design_section}\n\n"
            f"Output ONLY JSON, no markdown wrapping."
        )

        response_text = self._call_llm(prompt, system_ctx, route="bmad_complex")
        parsed = self._parse_json_response(
            response_text,
            retry_prompt=prompt,
            retry_system=system_ctx,
            retry_route="bmad_complex",
        )

        if "error" in parsed:
            return f"Failed to generate specs: {parsed['error']}"

        requirements = parsed.get("requirements", [])
        if not requirements:
            return "LLM returned no requirements. Check that your BMAD artifacts have enough detail."

        # Write spec file
        spec_content = self._build_spec_file_content(project_id, requirements)
        spec_path = _PROJECTS_DIR / project_id / "specs" / "core-features.md"
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(spec_content, encoding="utf-8")

        # Initialize traceability matrix
        self._init_traceability(project_id, requirements)

        # Update meta
        meta = self._read_meta(project_id)
        meta["specs_generated"] = True
        meta["stats"]["total_requirements"] = len(requirements)
        meta["last_worked"] = datetime.now().isoformat()
        self._write_meta(project_id, meta)

        lines = [f"Generated {len(requirements)} requirements in `specs/core-features.md`:"]
        for r in requirements[:8]:
            lines.append(f"  - {r.get('id', '?')}: {r.get('description', '')[:70]}")
        if len(requirements) > 8:
            lines.append(f"  ... and {len(requirements) - 8} more")
        lines.append("\nReady to scaffold the code?")
        return "\n".join(lines)

    def _build_spec_file_content(self, project_id: str, requirements: list[dict]) -> str:
        meta = self._read_meta(project_id)
        name = meta.get("name", project_id)
        today = datetime.now().strftime("%Y-%m-%d")

        lines = [
            "---",
            "feature: core",
            "owner: you",
            f"last_updated: {today}",
            "---",
            "",
            f"# Core Features — {name}",
            "",
        ]

        for req in requirements:
            req_id = req.get("id", "FR-CORE-000")
            title = req.get("title", req_id)
            lines += [
                f"## {req_id}: {title}",
                f"**Status:** not_implemented",
                f"**Priority:** {req.get('priority', 'P1')}",
                f"**BMAD Source:** {req.get('bmad_source', '_(not mapped)_')}",
                "",
                "**Description:**",
                req.get("description", ""),
                "",
                "**Acceptance Criteria:**",
            ]
            for ac in req.get("acceptance_criteria", []):
                lines.append(f"- {ac}")
            lines += [
                "",
                "**Edge Cases:**",
            ]
            for ec in req.get("edge_cases", []):
                lines.append(f"- {ec}")
            lines += [
                "",
                "**Implementation:** _(pending)_",
                "",
                "**Traceability:**",
                f"- Maps to: BMAD `{req.get('bmad_source', 'unknown')}`",
                "- Issue: _(none)_",
                "",
                "---",
                "",
            ]

        return "\n".join(lines)

    def _init_traceability(self, project_id: str, requirements: list[dict]) -> None:
        mappings = []
        for req in requirements:
            req_id = req.get("id", "")
            mappings.append({
                "id": req_id,
                "type": "functional",
                "spec_file": "specs/core-features.md",
                "spec_section": f"## {req_id}",
                "bmad_sources": [
                    {
                        "file": "bmad/business-model.md",
                        "section": req.get("bmad_source", ""),
                        "relevance": "primary",
                    }
                ],
                "implementation": [],
                "tests": [],
                "issues": [],
                "status": "not_implemented",
            })

        data = {
            "project": project_id,
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "mappings": mappings,
        }
        self._save_traceability(project_id, data)

    # ── Requirement CRUD ──────────────────────────────────────────────────────

    def list_requirements(self, project_id: str) -> list[dict]:
        """Return all FR-* requirements from spec files."""
        spec_dir = _PROJECTS_DIR / project_id / "specs"
        if not spec_dir.exists():
            return []

        results = []
        id_pattern = re.compile(r"^## (FR-[A-Z]+-\d+)[:\s]*(.*?)$", re.MULTILINE)
        status_pattern = re.compile(r"\*\*Status:\*\*\s*(\S+)")

        for spec_file in sorted(spec_dir.glob("*-features.md")):
            try:
                content = spec_file.read_text(encoding="utf-8")
                for m in id_pattern.finditer(content):
                    req_id = m.group(1)
                    title = m.group(2).strip()
                    window = content[m.start(): m.start() + 400]
                    sm = status_pattern.search(window)
                    status = sm.group(1) if sm else "unknown"
                    results.append({
                        "id": req_id,
                        "description": title,
                        "status": status,
                        "file": spec_file.name,
                    })
            except Exception:
                continue

        return results

    def get_requirement(self, project_id: str, requirement_id: str) -> Optional[dict]:
        """Return parsed details of a single requirement."""
        spec_dir = _PROJECTS_DIR / project_id / "specs"
        if not spec_dir.exists():
            return None

        escaped = re.escape(requirement_id)
        section_pattern = re.compile(
            rf"^## ({escaped}[^\n]*)\n(.*?)(?=^## FR-|\Z)",
            re.MULTILINE | re.DOTALL,
        )

        for spec_file in sorted(spec_dir.glob("*-features.md")):
            try:
                content = spec_file.read_text(encoding="utf-8")
                m = section_pattern.search(content)
                if m:
                    body = m.group(2)
                    return {
                        "id": requirement_id,
                        "heading": m.group(1),
                        "file": spec_file.name,
                        "status": self._extract_field(body, "Status"),
                        "priority": self._extract_field(body, "Priority"),
                        "description": self._extract_description(body),
                        "acceptance_criteria": self._extract_list(body, "Acceptance Criteria"),
                        "edge_cases": self._extract_list(body, "Edge Cases"),
                        "implementation": self._extract_field(body, "Implementation"),
                    }
            except Exception:
                continue
        return None

    def create_requirement(self, project_id: str, req_type: str, content: dict) -> str:
        """Append a new FR-* block to specs/core-features.md."""
        spec_file = _PROJECTS_DIR / project_id / "specs" / "core-features.md"
        if not spec_file.exists():
            return "No spec file found. Run generate_specs first."

        reqs = self.list_requirements(project_id)
        type_reqs = [r for r in reqs if f"-{req_type}-" in r["id"]]
        next_num = len(type_reqs) + 1
        req_id = f"FR-{req_type}-{next_num:03d}"
        today = datetime.now().strftime("%Y-%m-%d")

        block = (
            f"\n## {req_id}: {content.get('title', 'New Requirement')}\n"
            f"**Status:** not_implemented\n"
            f"**Priority:** {content.get('priority', 'P2')}\n"
            f"**BMAD Source:** {content.get('bmad_source', '_(not mapped)_')}\n\n"
            f"**Description:**\n{content.get('description', '')}\n\n"
            f"**Acceptance Criteria:**\n"
            f"- AC-{req_type}-{next_num:03d}: GIVEN [context] WHEN [action] THEN [result]\n\n"
            f"**Edge Cases:**\n"
            f"- EC-{req_type}-{next_num:03d}: GIVEN [unusual input] WHEN [action] THEN [behavior]\n\n"
            f"**Implementation:** _(pending)_\n\n"
            f"**Traceability:**\n"
            f"- Maps to: BMAD _(not mapped)_\n"
            f"- Issue: _(none)_\n\n"
            f"---\n"
        )

        existing = spec_file.read_text(encoding="utf-8")
        spec_file.write_text(existing + block, encoding="utf-8")

        # Update traceability
        trace = self._load_traceability(project_id)
        trace["mappings"].append({
            "id": req_id,
            "type": "functional",
            "spec_file": "specs/core-features.md",
            "spec_section": f"## {req_id}",
            "bmad_sources": [],
            "implementation": [],
            "tests": [],
            "issues": [],
            "status": "not_implemented",
        })
        trace["last_updated"] = datetime.now().isoformat()
        self._save_traceability(project_id, trace)

        # Update meta stats
        meta = self._read_meta(project_id)
        meta.setdefault("stats", {})["total_requirements"] = len(reqs) + 1
        self._write_meta(project_id, meta)

        return f"Created {req_id} in specs/core-features.md"

    def update_requirement(self, project_id: str, requirement_id: str, updates: dict) -> str:
        """Edit a requirement section in-place in the spec file."""
        spec_dir = _PROJECTS_DIR / project_id / "specs"
        if not spec_dir.exists():
            return f"No specs directory for project {project_id}."

        escaped = re.escape(requirement_id)
        section_pattern = re.compile(
            rf"(^## {escaped}[^\n]*\n)(.*?)(?=^## FR-|\Z)",
            re.MULTILINE | re.DOTALL,
        )

        for spec_file in sorted(spec_dir.glob("*-features.md")):
            try:
                content = spec_file.read_text(encoding="utf-8")
                m = section_pattern.search(content)
                if not m:
                    continue

                original_body = m.group(2)
                new_body = original_body

                if "status" in updates:
                    new_body = re.sub(
                        r"\*\*Status:\*\*\s*\S+",
                        f"**Status:** {updates['status']}",
                        new_body,
                    )
                if "priority" in updates:
                    new_body = re.sub(
                        r"\*\*Priority:\*\*\s*\S+",
                        f"**Priority:** {updates['priority']}",
                        new_body,
                    )
                if "description" in updates:
                    new_body = re.sub(
                        r"(\*\*Description:\*\*\n)[^\n]*",
                        rf"\g<1>{updates['description']}",
                        new_body,
                    )
                if "add_acceptance_criterion" in updates:
                    ac = updates["add_acceptance_criterion"]
                    new_body = re.sub(
                        r"(\*\*Acceptance Criteria:\*\*\n)((?:- .+\n?)*)",
                        rf"\g<1>\g<2>- {ac}\n",
                        new_body,
                    )
                if "implementation" in updates:
                    new_body = re.sub(
                        r"\*\*Implementation:\*\* .*",
                        f"**Implementation:** {updates['implementation']}",
                        new_body,
                    )

                new_content = content[: m.start(2)] + new_body + content[m.end(2):]
                spec_file.write_text(new_content, encoding="utf-8")

                self._log_spec_change(
                    project_id=project_id,
                    requirement_id=requirement_id,
                    change_type="modify",
                    previous=original_body[:300],
                    updated=str(updates),
                    trigger=updates.get("trigger", "manual"),
                )

                return f"Updated {requirement_id}: {', '.join(k for k in updates if k != 'trigger')}"
            except Exception as e:
                return f"Error updating {requirement_id}: {e}"

        return f"Requirement {requirement_id} not found."

    # ── Issue management ──────────────────────────────────────────────────────

    def create_issue(self, project_id: str, issue_type: str, title: str, description: str) -> str:
        """Create a new issue YAML file in issues/open/."""
        issues_open = _PROJECTS_DIR / project_id / "issues" / "open"
        issues_closed = _PROJECTS_DIR / project_id / "issues" / "closed"
        issues_open.mkdir(parents=True, exist_ok=True)

        existing_open = list(issues_open.glob("BUG-*.yml"))
        existing_closed = list(issues_closed.glob("BUG-*.yml")) if issues_closed.exists() else []
        next_num = len(existing_open) + len(existing_closed) + 1
        issue_id = f"BUG-{next_num:03d}"

        issue_data = {
            "id": issue_id,
            "type": issue_type,
            "project": project_id,
            "created": datetime.now().isoformat(),
            "status": "open",
            "title": title or description[:60],
            "description": description,
            "reproduction": [],
            "expected": "",
            "actual": "",
            "environment": {"version": "0.1.0", "platform": ""},
            "affected_requirements": [],
            "analysis": None,
            "spec_impact": None,
            "priority": "P2",
        }

        issue_path = issues_open / f"{issue_id}.yml"
        issue_path.write_text(yaml_dump(issue_data), encoding="utf-8")

        # Update meta
        meta = self._read_meta(project_id)
        meta.setdefault("stats", {})["open_issues"] = (
            meta["stats"].get("open_issues", 0) + 1
        )
        self._write_meta(project_id, meta)

        return f"Created {issue_id}: {issue_data['title']}\nFile: issues/open/{issue_id}.yml"

    def analyze_issue(self, project_id: str, issue_id_or_description: str) -> dict:
        """Analyze a bug/feature against specs via LLM. Returns analysis dict."""
        reqs = self.list_requirements(project_id)
        req_summary = "\n".join(
            f"  {r['id']}: {r['description'][:100]} [{r['status']}]"
            for r in reqs[:20]
        )

        system_ctx = self._load_sdd_prompt("issue-analysis")
        prompt = (
            f"Analyze this issue against the project specifications.\n\n"
            f"ISSUE:\n{issue_id_or_description}\n\n"
            f"CURRENT REQUIREMENTS:\n{req_summary}\n\n"
            f"Output ONLY JSON, no markdown wrapping."
        )

        response_text = self._call_llm(prompt, system_ctx, route="bmad_complex")
        parsed = self._parse_json_response(
            response_text,
            retry_prompt=prompt,
            retry_system=system_ctx,
            retry_route="bmad_complex",
        )

        if "error" not in parsed and issue_id_or_description.startswith("BUG-"):
            self._annotate_issue_file(project_id, issue_id_or_description, parsed)

        return parsed

    def close_issue(self, project_id: str, issue_id: str, resolution: str) -> str:
        """Move issue from open → closed."""
        open_dir = _PROJECTS_DIR / project_id / "issues" / "open"
        closed_dir = _PROJECTS_DIR / project_id / "issues" / "closed"
        closed_dir.mkdir(parents=True, exist_ok=True)

        issue_path = open_dir / f"{issue_id}.yml"
        if not issue_path.exists():
            return f"{issue_id} not found in issues/open/."

        try:
            data = yaml_load(issue_path.read_text(encoding="utf-8"))
            data["status"] = "closed"
            data["resolution"] = resolution
            data["closed_at"] = datetime.now().isoformat()

            closed_path = closed_dir / f"{issue_id}.yml"
            closed_path.write_text(yaml_dump(data), encoding="utf-8")
            issue_path.unlink()

            # Update meta
            meta = self._read_meta(project_id)
            open_count = meta.get("stats", {}).get("open_issues", 1)
            meta.setdefault("stats", {})["open_issues"] = max(0, open_count - 1)
            self._write_meta(project_id, meta)

            return f"Closed {issue_id} → issues/closed/{issue_id}.yml"
        except Exception as e:
            return f"Error closing {issue_id}: {e}"

    # ── Traceability ──────────────────────────────────────────────────────────

    def update_traceability(self, project_id: str, requirement_id: str, impl_data: dict) -> None:
        """Add implementation entry to traceability matrix and mark requirement as implemented."""
        trace = self._load_traceability(project_id)
        for mapping in trace.get("mappings", []):
            if mapping["id"] == requirement_id:
                mapping["implementation"].append(impl_data)
                mapping["status"] = "implemented"
                break
        trace["last_updated"] = datetime.now().isoformat()
        self._save_traceability(project_id, trace)

        # Sync status to spec file
        self.update_requirement(project_id, requirement_id, {
            "status": "implemented",
            "implementation": (
                f"`{impl_data.get('file', '')}::"
                f"{', '.join(impl_data.get('functions', []))}`"
            ),
        })

        # Update meta stats
        reqs = self.list_requirements(project_id)
        implemented = sum(1 for r in reqs if r["status"] == "implemented")
        meta = self._read_meta(project_id)
        meta.setdefault("stats", {})["implemented_requirements"] = implemented
        self._write_meta(project_id, meta)

    def _load_traceability(self, project_id: str) -> dict:
        trace_path = _PROJECTS_DIR / project_id / "specs" / "traceability.json"
        if trace_path.exists():
            try:
                return json.loads(trace_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "project": project_id,
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "mappings": [],
        }

    def _save_traceability(self, project_id: str, data: dict) -> None:
        trace_path = _PROJECTS_DIR / project_id / "specs" / "traceability.json"
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_next_step_suggestion(self, project_id: str) -> str:
        """Return a natural next-step suggestion based on project state."""
        meta = self._read_meta(project_id)
        if not meta:
            return "Project not found."
        if not meta.get("bmad_complete"):
            return "Complete the BMAD artifacts first (business model + architecture)."
        if not meta.get("specs_generated"):
            return "BMAD is done. Want me to generate SDD requirements?"
        open_issues = meta.get("stats", {}).get("open_issues", 0)
        if open_issues > 0:
            return f"You have {open_issues} open issue(s). Want me to analyze them against your specs?"
        if not meta.get("code_scaffolded"):
            return "Specs are ready. Want me to scaffold the application code?"
        return "Project is in progress. Say 'show requirements' to see what's left to implement."

    # ── LLM helpers ───────────────────────────────────────────────────────────

    def _load_sdd_prompt(self, prompt_name: str) -> str:
        prompt_path = _SDD_DIR / "prompts" / f"{prompt_name}.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""

    def _call_llm(self, prompt: str, system_context: str, route: str = "bmad_complex") -> str:
        from src.router import get_router
        router = get_router()
        result = router.route(
            query=prompt,
            conversation_history=[],
            system_prompt=system_context,
            force_route=route,
        )
        return result.content if not result.error else ""

    def _parse_json_response(
        self,
        response_text: str,
        retry_prompt: str = "",
        retry_system: str = "",
        retry_route: str = "bmad_complex",
    ) -> dict:
        """Strip markdown fences and parse JSON. Retry once on failure."""

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
            retry_text = self._call_llm(
                f"Your previous response was not valid JSON. "
                f"Return ONLY a JSON object, no markdown wrapping.\n\n{retry_prompt}",
                retry_system,
                route=retry_route,
            )
            parsed = _try_parse(retry_text)
            if parsed is not None:
                return parsed

        return {"error": "Could not parse LLM response as JSON", "raw": response_text[:500]}

    # ── Spec parsing helpers ──────────────────────────────────────────────────

    def _extract_field(self, body: str, field_name: str) -> str:
        m = re.search(rf"\*\*{re.escape(field_name)}:\*\*\s*(.+?)(?:\n|$)", body)
        return m.group(1).strip() if m else ""

    def _extract_description(self, body: str) -> str:
        m = re.search(r"\*\*Description:\*\*\n(.+?)(?=\n\n|\*\*)", body, re.DOTALL)
        return m.group(1).strip() if m else ""

    def _extract_list(self, body: str, field_name: str) -> list[str]:
        m = re.search(rf"\*\*{re.escape(field_name)}:\*\*\n((?:- .+\n?)*)", body)
        if not m:
            return []
        return [line[2:].strip() for line in m.group(1).splitlines() if line.startswith("- ")]

    # ── Spec-changes audit log ────────────────────────────────────────────────

    def _log_spec_change(
        self,
        project_id: str,
        requirement_id: str,
        change_type: str,
        previous: str,
        updated: str,
        trigger: str,
    ) -> None:
        log_path = _SDD_DIR / "logs" / "spec-changes.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "project": project_id,
            "requirement_id": requirement_id,
            "change_type": change_type,
            "previous": previous,
            "updated": updated,
            "trigger": trigger,
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    # ── Issue file helpers ────────────────────────────────────────────────────

    def _annotate_issue_file(self, project_id: str, issue_id: str, analysis: dict) -> None:
        """Write LLM analysis back into the issue file."""
        issue_path = _PROJECTS_DIR / project_id / "issues" / "open" / f"{issue_id}.yml"
        if not issue_path.exists():
            return
        try:
            data = yaml_load(issue_path.read_text(encoding="utf-8"))
            data["analysis"] = analysis.get("analysis_type", "unknown")
            data["affected_requirements"] = analysis.get("affected_requirements", [])
            issue_path.write_text(yaml_dump(data), encoding="utf-8")
        except Exception:
            pass

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
