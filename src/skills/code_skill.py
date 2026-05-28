"""Code generation skill — scaffold, implement, fix, and test from SDD specs."""
# Implements FR-BMAD-004 (Code Scaffolding Generation — scaffold_from_specs(), generate_code_for_requirement(), fix_issue())

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.skills.base import Skill
from src.skills._yaml_helpers import yaml_load


_PROJECT_ROOT = Path(__file__).parent.parent.parent
_PROJECTS_DIR = _PROJECT_ROOT / "projects"
_SDD_DIR = _PROJECT_ROOT / ".sdd"

_CODE_KEYWORDS = [
    "generate", "scaffold", "implement", "code for",
    "build the", "create the", "write the", "make the",
]
_FIX_KEYWORDS = ["fix", "fix the bug", "patch", "correct the code"]
_TEST_KEYWORDS = ["test", "tests", "generate tests", "write tests"]


class CodeSkill(Skill):

    # ── Skill interface ───────────────────────────────────────────────────────

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()
        score = 0.0

        for kw in _CODE_KEYWORDS + _FIX_KEYWORDS + _TEST_KEYWORDS:
            if kw in q:
                score += 0.2
                break  # one match is enough to start scoring

        if context.get("specs_generated"):
            score += 0.3

        if context.get("current_project"):
            score += 0.1

        return min(score, 1.0)

    def suggest(self, user_input: str, context: dict) -> str:
        q = user_input.lower()

        if not context.get("specs_generated"):
            return "You'll need to generate specs first before I can scaffold code."

        project_id = context.get("current_project", "")
        if any(kw in q for kw in _FIX_KEYWORDS):
            return (
                "I can generate a code fix using your spec context — "
                "so the fix is traceable back to the requirement. Want me to do that?"
            )
        if any(kw in q for kw in _TEST_KEYWORDS):
            return (
                "I can generate pytest tests directly from your acceptance criteria. "
                "Which requirement should I start with?"
            )
        component = "backend" if "backend" in q else ("frontend" in q and "frontend" or "backend")
        return (
            f"I can scaffold the {component} code from your specs. "
            "Every generated function will reference its requirement ID. Want me to go ahead?"
        )

    def tool_definition(self) -> dict:
        # Implements FR-ORCH-005
        return {
            "name": "CodeSkill",
            "description": "Scaffolds code, implements requirements, and generates tests from SDD specs — every function is traceable to a requirement ID.",
            "when": "user says 'scaffold', 'generate code', 'implement', 'write the backend/frontend/api', 'generate tests', or 'fix' a specific bug when a project with specs is active",
            "params": {
                "action": "scaffold | implement | fix | test",
                "component": "backend | frontend | api | models (for scaffold)",
                "requirement_id": "FR-* ID (for implement)",
                "project_id": "(optional) project ID, defaults to active project",
            },
            "examples": [
                "scaffold the backend for my project",
                "implement FR-CORE-001",
                "generate tests for FR-AUTH-002",
                "fix the bug in issue BUG-003",
                "write the API layer from specs",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        action = params.get("action", "")
        project_id = params.get("project_id") or context.get("current_project", "")

        if action == "scaffold":
            return self.scaffold_from_specs(project_id, params.get("component", "backend"))
        if action == "implement":
            return self.generate_code_for_requirement(project_id, params["requirement_id"])
        if action == "fix":
            return self.fix_issue(project_id, params["issue_id"])
        if action == "tests":
            return self.generate_tests(project_id, params["requirement_id"])

        return "Specify an action: scaffold, implement, fix, or tests."

    # ── Scaffold from specs ───────────────────────────────────────────────────

    def scaffold_from_specs(self, project_id: str, component: str = "backend") -> str:
        """Generate initial application code structure from all specs."""
        from src.skills.sdd_skill import SDDSkill
        sdd = SDDSkill()

        if not sdd._read_meta(project_id).get("specs_generated"):
            return "Specs not generated yet. Run generate_specs first."

        reqs = sdd.list_requirements(project_id)
        if not reqs:
            return "No requirements found. Run generate_specs first."

        stack = self._load_project_stack(project_id)
        req_details = []
        for r in reqs[:10]:
            detail = sdd.get_requirement(project_id, r["id"])
            if detail:
                req_details.append(detail)

        system_ctx = self._load_code_prompt()
        prompt = self._build_scaffold_prompt(project_id, component, stack, req_details)

        response_text = self._call_llm(prompt, system_ctx, route="code_generation")
        parsed = self._parse_json_response(
            response_text,
            retry_prompt=prompt,
            retry_system=system_ctx,
            retry_route="code_generation",
        )

        if "error" in parsed:
            return f"Code generation failed: {parsed['error']}"

        written = self._write_generated_files(project_id, parsed.get("files", []))
        test_written = self._write_generated_files(project_id, parsed.get("tests", []))

        # Update traceability for each requirement mentioned
        for update in parsed.get("traceability_updates", []):
            req_id = update.get("requirement_id")
            impl_data = update.get("implementation", {})
            if req_id and impl_data:
                sdd.update_traceability(project_id, req_id, impl_data)

        # Mark code_scaffolded in meta
        meta = sdd._read_meta(project_id)
        meta["code_scaffolded"] = True
        meta["last_worked"] = datetime.now().isoformat()
        sdd._write_meta(project_id, meta)

        all_written = written + test_written
        if not all_written:
            return "LLM returned no files to write. Check that your specs have enough detail."

        lines = [f"Scaffolded {len(written)} source file(s) and {len(test_written)} test file(s):"]
        for path in all_written[:12]:
            lines.append(f"  {path}")
        if len(all_written) > 12:
            lines.append(f"  ... and {len(all_written) - 12} more")
        lines.append("\nAll functions reference their requirement IDs in comments.")
        return "\n".join(lines)

    # ── Implement single requirement ──────────────────────────────────────────

    def generate_code_for_requirement(self, project_id: str, requirement_id: str) -> str:
        """Generate code implementing one specific requirement."""
        from src.skills.sdd_skill import SDDSkill
        sdd = SDDSkill()

        req = sdd.get_requirement(project_id, requirement_id)
        if not req:
            return f"Requirement {requirement_id} not found."

        stack = self._load_project_stack(project_id)
        system_ctx = self._load_code_prompt()
        prompt = self._build_requirement_prompt(project_id, req, stack)

        response_text = self._call_llm(prompt, system_ctx, route="code_generation")
        parsed = self._parse_json_response(
            response_text,
            retry_prompt=prompt,
            retry_system=system_ctx,
            retry_route="code_generation",
        )

        if "error" in parsed:
            return f"Code generation failed: {parsed['error']}"

        written = self._write_generated_files(project_id, parsed.get("files", []))
        test_written = self._write_generated_files(project_id, parsed.get("tests", []))

        for update in parsed.get("traceability_updates", []):
            req_id = update.get("requirement_id")
            impl_data = update.get("implementation", {})
            if req_id and impl_data:
                sdd.update_traceability(project_id, req_id, impl_data)

        all_written = written + test_written
        lines = [f"Implemented {requirement_id}:"]
        for path in all_written:
            lines.append(f"  {path}")
        return "\n".join(lines)

    # ── Fix issue ─────────────────────────────────────────────────────────────

    def fix_issue(self, project_id: str, issue_id: str) -> str:
        """Generate a targeted code fix for an open issue, guided by spec analysis."""
        from src.skills.sdd_skill import SDDSkill
        sdd = SDDSkill()

        issue_path = _PROJECTS_DIR / project_id / "issues" / "open" / f"{issue_id}.yml"
        if not issue_path.exists():
            return f"{issue_id} not found in issues/open/."

        issue_data = yaml_load(issue_path.read_text(encoding="utf-8"))
        affected_reqs = issue_data.get("affected_requirements", [])
        req_details = [sdd.get_requirement(project_id, r) for r in affected_reqs if r]
        req_details = [r for r in req_details if r]

        # Load existing source files for context if they're referenced in traceability
        trace = sdd._load_traceability(project_id)
        existing_code = self._load_relevant_source(project_id, affected_reqs, trace)

        system_ctx = self._load_code_prompt()
        prompt = self._build_fix_prompt(project_id, issue_data, req_details, existing_code)

        response_text = self._call_llm(prompt, system_ctx, route="code_generation")
        parsed = self._parse_json_response(
            response_text,
            retry_prompt=prompt,
            retry_system=system_ctx,
            retry_route="code_generation",
        )

        if "error" in parsed:
            return f"Fix generation failed: {parsed['error']}"

        written = self._write_generated_files(project_id, parsed.get("files", []))
        test_written = self._write_generated_files(project_id, parsed.get("tests", []))

        for update in parsed.get("traceability_updates", []):
            req_id = update.get("requirement_id")
            impl_data = update.get("implementation", {})
            if req_id and impl_data:
                sdd.update_traceability(project_id, req_id, impl_data)

        sdd.close_issue(project_id, issue_id, f"Fixed in: {', '.join(written)}")

        lines = [f"Fixed {issue_id}:"]
        for path in written + test_written:
            lines.append(f"  {path}")
        lines.append(f"\n{issue_id} closed → issues/closed/")
        return "\n".join(lines)

    # ── Generate tests ────────────────────────────────────────────────────────

    def generate_tests(self, project_id: str, requirement_id: str) -> str:
        """Generate pytest test cases from a requirement's acceptance criteria."""
        from src.skills.sdd_skill import SDDSkill
        sdd = SDDSkill()

        req = sdd.get_requirement(project_id, requirement_id)
        if not req:
            return f"Requirement {requirement_id} not found."

        stack = self._load_project_stack(project_id)
        system_ctx = self._load_code_prompt()
        prompt = self._build_test_prompt(project_id, req, stack)

        response_text = self._call_llm(prompt, system_ctx, route="code_generation")
        parsed = self._parse_json_response(
            response_text,
            retry_prompt=prompt,
            retry_system=system_ctx,
            retry_route="code_generation",
        )

        if "error" in parsed:
            return f"Test generation failed: {parsed['error']}"

        written = self._write_generated_files(project_id, parsed.get("tests", []))

        # Update traceability with test info
        trace = sdd._load_traceability(project_id)
        for mapping in trace.get("mappings", []):
            if mapping["id"] == requirement_id:
                for path in written:
                    mapping["tests"].append({"file": path, "cases": []})
                break
        trace["last_updated"] = datetime.now().isoformat()
        sdd._save_traceability(project_id, trace)

        if not written:
            return "No test files generated."
        return f"Generated tests for {requirement_id}:\n" + "\n".join(f"  {p}" for p in written)

    # ── Prompt builders ───────────────────────────────────────────────────────

    def _build_scaffold_prompt(
        self,
        project_id: str,
        component: str,
        stack: dict,
        req_details: list[dict],
    ) -> str:
        req_text = "\n\n".join(
            f"### {r['id']}: {r.get('heading', r['id'])}\n"
            f"Description: {r.get('description', '')}\n"
            f"Acceptance Criteria:\n"
            + "\n".join(f"  - {ac}" for ac in r.get("acceptance_criteria", []))
            for r in req_details
        )
        return (
            f"Scaffold the {component} for project '{project_id}'.\n\n"
            f"TECH STACK:\n{json.dumps(stack, indent=2)}\n\n"
            f"REQUIREMENTS:\n{req_text}\n\n"
            f"Generate all necessary files. Reference requirement IDs in code comments. "
            f"Output ONLY JSON, no markdown wrapping."
        )

    def _build_requirement_prompt(self, project_id: str, req: dict, stack: dict) -> str:
        acs = "\n".join(f"  - {ac}" for ac in req.get("acceptance_criteria", []))
        ecs = "\n".join(f"  - {ec}" for ec in req.get("edge_cases", []))
        return (
            f"Implement requirement {req['id']} for project '{project_id}'.\n\n"
            f"TECH STACK:\n{json.dumps(stack, indent=2)}\n\n"
            f"REQUIREMENT:\n{req.get('description', '')}\n\n"
            f"ACCEPTANCE CRITERIA:\n{acs}\n\n"
            f"EDGE CASES:\n{ecs}\n\n"
            f"Generate implementation and test files. "
            f"Comment each function with '# Implements {req['id']}'. "
            f"Output ONLY JSON, no markdown wrapping."
        )

    def _build_fix_prompt(
        self,
        project_id: str,
        issue_data: dict,
        req_details: list[dict],
        existing_code: dict,
    ) -> str:
        req_text = "\n\n".join(
            f"### {r['id']}\n{r.get('description', '')}\n"
            + "\n".join(f"  - {ac}" for ac in r.get("acceptance_criteria", []))
            for r in req_details
        )
        code_section = ""
        if existing_code:
            code_section = "\n\nEXISTING CODE:\n" + "\n\n".join(
                f"```python\n# {path}\n{content[:2000]}\n```"
                for path, content in existing_code.items()
            )

        return (
            f"Fix this issue for project '{project_id}'.\n\n"
            f"ISSUE: {issue_data.get('title', '')}\n"
            f"DESCRIPTION: {issue_data.get('description', '')}\n\n"
            f"AFFECTED REQUIREMENTS:\n{req_text}"
            f"{code_section}\n\n"
            f"Generate a minimal, targeted fix. Include a regression test. "
            f"Output ONLY JSON, no markdown wrapping."
        )

    def _build_test_prompt(self, project_id: str, req: dict, stack: dict) -> str:
        acs = "\n".join(f"  - {ac}" for ac in req.get("acceptance_criteria", []))
        ecs = "\n".join(f"  - {ec}" for ec in req.get("edge_cases", []))
        return (
            f"Generate pytest tests for requirement {req['id']} in project '{project_id}'.\n\n"
            f"TECH STACK:\n{json.dumps(stack, indent=2)}\n\n"
            f"REQUIREMENT: {req.get('description', '')}\n\n"
            f"ACCEPTANCE CRITERIA:\n{acs}\n\n"
            f"EDGE CASES:\n{ecs}\n\n"
            f"One test function per AC/EC. Name functions like test_ac_core_001_description(). "
            f"Output ONLY JSON in the 'tests' key (no 'files' key needed). "
            f"No markdown wrapping."
        )

    # ── File writing ──────────────────────────────────────────────────────────

    def _write_generated_files(self, project_id: str, file_list: list[dict]) -> list[str]:
        """Write generated files to projects/<project_id>/src or tests/. Returns list of written paths."""
        written = []
        project_path = _PROJECTS_DIR / project_id

        for file_entry in file_list:
            rel_path = file_entry.get("path", "")
            content = file_entry.get("content", "")
            if not rel_path or not content:
                continue

            # Ensure path stays within the project directory
            target = (project_path / rel_path).resolve()
            if not str(target).startswith(str(project_path.resolve())):
                continue  # skip paths that escape the project

            # Refuse to overwrite Xochitl's own files
            protected = {".project-meta.yml", "traceability.json"}
            if target.name in protected or "bmad/" in rel_path or "specs/" in rel_path:
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append(rel_path)

        return written

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _load_project_stack(self, project_id: str) -> dict:
        meta_path = _PROJECTS_DIR / project_id / ".project-meta.yml"
        if not meta_path.exists():
            return {}
        try:
            meta = yaml_load(meta_path.read_text(encoding="utf-8"))
            return meta.get("stack", {})
        except Exception:
            return {}

    def _load_code_prompt(self) -> str:
        prompt_path = _SDD_DIR / "prompts" / "code-generation.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""

    def _load_relevant_source(
        self,
        project_id: str,
        requirement_ids: list[str],
        trace: dict,
    ) -> dict[str, str]:
        """Load source files referenced in traceability for given requirements."""
        result: dict[str, str] = {}
        project_path = _PROJECTS_DIR / project_id

        for mapping in trace.get("mappings", []):
            if mapping["id"] not in requirement_ids:
                continue
            for impl in mapping.get("implementation", []):
                rel_path = impl.get("file", "")
                if not rel_path:
                    continue
                src_path = project_path / rel_path
                if src_path.exists() and rel_path not in result:
                    try:
                        result[rel_path] = src_path.read_text(encoding="utf-8")
                    except Exception:
                        pass
        return result

    def _call_llm(self, prompt: str, system_context: str, route: str = "code_generation") -> str:
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
        retry_route: str = "code_generation",
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
