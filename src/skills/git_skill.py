"""GitSkill — read-only git inspection plus approval-gated add/commit.

Implements FR-GIT-001, FR-GIT-002, FR-GIT-003 (CR-052).

Classification (whitelist — anything not listed is DENY):
  AUTO    : status, diff, log, branch, show   (read-only)
  CONFIRM : add, commit                        (gated by the confirmation FSM
            via _MUTATING_SKILL_ACTIONS["GitSkill"])
  DENY    : push, reset, clean, rebase, checkout, merge, and all else
            (destructive or history-rewriting — never run by this skill)

All execution flows through SafeExecutor (git is allowlisted, shell=False).
"""
from __future__ import annotations

from src.executor import SafeExecutor, PolicyViolation, ExecutorError
from src.skills.base import Skill

_GIT_KEYWORDS = (
    "git status", "git diff", "git log", "git branch", "git show",
    "what changed", "what's changed", "uncommitted", "staged changes",
    "commit this", "commit these", "stage the", "git add", "git commit",
    "show me the diff", "recent commits", "commit history",
)

# Whitelisted verbs and their tiers.
_READ_ACTIONS = frozenset({"status", "diff", "log", "branch", "show"})
_WRITE_ACTIONS = frozenset({"add", "commit"})
# Everything else is DENY (push, reset, clean, rebase, checkout, merge, ...).


class GitSkill(Skill):
    """Inspect and (with approval) stage/commit changes in the local repo."""

    def can_handle(self, user_input: str, context: dict) -> float:
        """Score whether the user wants a git operation.

        Args:
            user_input: Raw user message.
            context: Session context dict (unused).

        Returns:
            0.7 when a git phrase is present, else 0.0.
        """
        q = user_input.lower()
        if any(kw in q for kw in _GIT_KEYWORDS):
            return 0.7
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        """Return the suggestion shown before a git operation.

        Args:
            user_input: Raw user message.
            context: Session context dict (unused).

        Returns:
            A short consent prompt.
        """
        return "I can run git for you (read-only is automatic; add/commit you approve first)."

    def tool_definition(self) -> dict:
        """Return the LLM tool descriptor for GitSkill.

        Returns:
            Descriptor dict (FR-ORCH-005). The ``action`` param drives dispatch.
        """
        return {
            "name": "GitSkill",
            "description": (
                "Runs git: status/diff/log/branch/show (read-only, automatic) and "
                "add/commit (you approve first). Refuses push, reset, clean, "
                "rebase, checkout, merge."
            ),
            "when": "user asks about git status, diff, log, branches, or wants to stage/commit changes",
            "params": {
                "action": "One of: status, diff, log, branch, show, add, commit",
                "path": "(add) path to stage, default '.'",
                "message": "(commit) commit message",
                "ref": "(show) git ref, default HEAD",
            },
            "timeout_secs": 15,
            "examples": [
                "what's the git status?",
                "show me the diff",
                "show recent commits",
                "stage the changes",
                "commit this with message 'fix bug'",
            ],
        }

    @staticmethod
    def classify_action(action: str) -> str:
        """Classify a git action into a tier label.

        Args:
            action: The git verb (e.g. "status", "commit", "push").

        Returns:
            "auto", "confirm", or "deny".
        """
        a = (action or "").lower().strip()
        if a in _READ_ACTIONS:
            return "auto"
        if a in _WRITE_ACTIONS:
            return "confirm"
        return "deny"

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Run a git action.

        Args:
            user_input: Raw user message (unused; action comes from params).
            context: Session context dict; ``last_skill_success`` is set.
            params: Must contain ``action``; optional ``path``/``message``/``ref``.

        Returns:
            Formatted git output, or a clear refusal/error message.

        Raises:
            None — executor exceptions are caught and returned as strings.
        """
        action = (params.get("action") or "").lower().strip()
        tier = self.classify_action(action)

        if tier == "deny":
            context["last_skill_success"] = False
            return (
                f"Ay no — `git {action or '?'}` is not allowed through GitSkill. "
                "I only run status, diff, log, branch, show, add, and commit "
                "(never push, reset, clean, rebase, checkout, or merge)."
            )

        args = self._build_args(action, params)
        if args is None:
            context["last_skill_success"] = False
            return f"Fíjate — couldn't build a git command for action `{action}`."

        executor = SafeExecutor()
        try:
            result = executor.run("git", args, action_type="status", target="git")
        except PolicyViolation as exc:
            context["last_skill_success"] = False
            return f"Ay no — git is not available or was blocked: {exc}"
        except ExecutorError as exc:
            context["last_skill_success"] = False
            return f"Ay no — git failed to run: {exc}"

        context["last_skill_success"] = result.returncode == 0
        return self._format_result(action, args, result)

    @staticmethod
    def _build_args(action: str, params: dict) -> list[str] | None:
        """Build the git argument list for an action.

        Args:
            action: A whitelisted git verb.
            params: The skill params dict.

        Returns:
            Argument list (excluding the leading "git"), or None if unbuildable.
        """
        if action == "status":
            return ["status", "--short", "--branch"]
        if action == "diff":
            path = (params.get("path") or "").strip()
            return ["diff"] + ([path] if path else [])
        if action == "log":
            return ["log", "--oneline", "-10"]
        if action == "branch":
            return ["branch", "--list"]
        if action == "show":
            ref = (params.get("ref") or "HEAD").strip()
            return ["show", "--stat", ref]
        if action == "add":
            path = (params.get("path") or ".").strip()
            return ["add", path]
        if action == "commit":
            message = (params.get("message") or "").strip()
            if not message:
                return None
            return ["commit", "-m", message]
        return None

    @staticmethod
    def _format_result(action: str, args: list[str], result) -> str:
        """Format an ExecutorResult into a readable block.

        Args:
            action: The git verb that ran.
            args: The full git argument list.
            result: The ExecutorResult.

        Returns:
            A multi-line summary with exit status and captured output.
        """
        status = "✓" if result.returncode == 0 else f"✗ exit {result.returncode}"
        lines = [f"`git {' '.join(args)}` {status}"]
        body = (result.stdout.rstrip() + ("\n" + result.stderr.rstrip() if result.stderr.strip() else "")).strip()
        lines.append(body if body else "(no output)")
        if result.truncated:
            lines.append("[output truncated]")
        return "\n".join(lines)
