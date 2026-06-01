"""ProjectScanSkill — bounded, read-only project structure analysis.

Implements FR-SCAN-001 (CR-052).

Two operations:
  - find_symbol: locate where a Python function/class is defined (via ``ast``).
  - list_files:  list files matching a glob pattern.

Bounded by a file cap (XCH_SCAN_MAX_FILES, default 500) and a wall-clock
timeout (XCH_SCAN_TIMEOUT, default 5s). Returns partial results with a notice
when a bound is hit. Purely read-only — no FSM approval required.
"""
from __future__ import annotations

import ast
import os
import time
from pathlib import Path

from src.skills.base import Skill

_MAX_FILES: int = int(os.getenv("XCH_SCAN_MAX_FILES", "500"))
_SCAN_TIMEOUT: float = float(os.getenv("XCH_SCAN_TIMEOUT", "5.0"))

_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    ".xochitl", ".idea", ".vscode",
})

_SCAN_KEYWORDS = (
    "where is", "where's", "where are", "find the function", "find the class",
    "find the method", "where is it defined", "where is it declared",
    "find symbol", "scan the project", "list the files", "list files",
    "what files", "where defined", "locate the",
)


class ProjectScanSkill(Skill):
    """Find symbol definitions and list files within bounded limits."""

    def can_handle(self, user_input: str, context: dict) -> float:
        """Score whether the user wants a project structure lookup.

        Args:
            user_input: Raw user message.
            context: Session context dict (unused).

        Returns:
            0.7 when a scan phrase is present, else 0.0.
        """
        q = user_input.lower()
        if any(kw in q for kw in _SCAN_KEYWORDS):
            return 0.7
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        """Return the suggestion shown before scanning.

        Args:
            user_input: Raw user message.
            context: Session context dict (unused).

        Returns:
            A short prompt.
        """
        return "I can scan the project to find where that's defined or list matching files."

    def tool_definition(self) -> dict:
        """Return the LLM tool descriptor for ProjectScanSkill.

        Returns:
            Descriptor dict (FR-ORCH-005).
        """
        return {
            "name": "ProjectScanSkill",
            "description": (
                "Read-only project analysis: find where a Python function/class is "
                "defined, or list files matching a glob. Bounded and safe."
            ),
            "when": "user asks where a symbol is defined, or to list/find files in the project",
            "params": {
                "action": "find_symbol or list_files",
                "name": "(find_symbol) the function/class name to locate",
                "pattern": "(list_files) glob pattern, default '*.py'",
            },
            "timeout_secs": int(_SCAN_TIMEOUT) + 2,
            "examples": [
                "where is can_handle defined?",
                "find the class AgentPipeline",
                "list the python files in src",
                "where is the SafeExecutor class?",
                "what files match test_*.py",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Dispatch a scan action.

        Args:
            user_input: Raw user message (unused).
            context: Session context dict; ``last_skill_success`` is set.
            params: Must contain ``action``; ``name`` or ``pattern`` per action.

        Returns:
            Formatted scan result, or a clear error message.
        """
        action = (params.get("action") or "").lower().strip()
        if action == "find_symbol":
            name = (params.get("name") or "").strip()
            if not name:
                context["last_skill_success"] = False
                return "Fíjate — which symbol should I look for?"
            locations, capped, scanned = self.find_symbol(name)
            context["last_skill_success"] = True
            return self._format_symbol(name, locations, capped, scanned)

        if action == "list_files":
            pattern = (params.get("pattern") or "*.py").strip()
            files, capped = self.list_files(pattern)
            context["last_skill_success"] = True
            return self._format_files(pattern, files, capped)

        context["last_skill_success"] = False
        return "Fíjate — use action 'find_symbol' or 'list_files'."

    # ── Core bounded scan ─────────────────────────────────────────────────────

    def _iter_files(self, root: Path):
        """Yield files under root, skipping noise dirs, bounded by cap and timeout.

        Args:
            root: Directory to walk.

        Yields:
            Tuples of (path, capped_flag). The capped_flag is True on the final
            yielded item if a bound was hit.
        """
        start = time.monotonic()
        count = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fn in filenames:
                if count >= _MAX_FILES or (time.monotonic() - start) > _SCAN_TIMEOUT:
                    yield None, True
                    return
                count += 1
                yield Path(dirpath) / fn, False

    def find_symbol(
        self, name: str, root: Path | None = None
    ) -> tuple[list[str], bool, int]:
        """Locate Python function/class definitions matching ``name``.

        Args:
            name: Exact symbol name to find.
            root: Scan root; defaults to the current working directory.

        Returns:
            Tuple of (locations, capped, files_scanned). Each location is a
            "path:lineno (kind)" string. ``capped`` is True if a bound was hit.
        """
        root = root or Path.cwd()
        locations: list[str] = []
        capped = False
        scanned = 0
        for path, is_cap in self._iter_files(root):
            if is_cap:
                capped = True
                break
            if path is None or path.suffix != ".py":
                continue
            scanned += 1
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except (SyntaxError, ValueError, OSError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name == name:
                        kind = "class" if isinstance(node, ast.ClassDef) else "function"
                        try:
                            rel = path.relative_to(root)
                        except ValueError:
                            rel = path
                        locations.append(f"{rel}:{node.lineno} ({kind})")
        return locations, capped, scanned

    def list_files(
        self, pattern: str, root: Path | None = None
    ) -> tuple[list[str], bool]:
        """List files whose name matches a glob pattern, bounded.

        Args:
            pattern: Glob pattern matched against the file name (e.g. "*.py").
            root: Scan root; defaults to the current working directory.

        Returns:
            Tuple of (relative_paths, capped).
        """
        import fnmatch

        root = root or Path.cwd()
        matches: list[str] = []
        capped = False
        for path, is_cap in self._iter_files(root):
            if is_cap:
                capped = True
                break
            if path is None:
                continue
            if fnmatch.fnmatch(path.name, pattern):
                try:
                    rel = path.relative_to(root)
                except ValueError:
                    rel = path
                matches.append(str(rel))
        return matches, capped

    # ── Formatting ────────────────────────────────────────────────────────────

    @staticmethod
    def _format_symbol(name: str, locations: list[str], capped: bool, scanned: int) -> str:
        if not locations:
            base = f"No definition of `{name}` found in {scanned} scanned file(s)."
        else:
            base = f"`{name}` defined in:\n" + "\n".join(f"  - {loc}" for loc in locations)
        if capped:
            base += f"\n[scan stopped at the {_MAX_FILES}-file / {_SCAN_TIMEOUT:.0f}s bound — results may be partial]"
        return base

    @staticmethod
    def _format_files(pattern: str, files: list[str], capped: bool) -> str:
        if not files:
            base = f"No files match `{pattern}`."
        else:
            shown = files[:50]
            base = f"{len(files)} file(s) match `{pattern}`:\n" + "\n".join(f"  - {f}" for f in shown)
            if len(files) > 50:
                base += f"\n  [... {len(files) - 50} more ...]"
        if capped:
            base += f"\n[scan stopped at the {_MAX_FILES}-file / {_SCAN_TIMEOUT:.0f}s bound — results may be partial]"
        return base
