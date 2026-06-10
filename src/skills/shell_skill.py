"""ShellSkill — governor-gated shell command execution for the chat layer.

Implements FR-EXEC-004, FR-EXEC-005, NFR-EXEC-003 (CR-052).

Every ShellSkill call is approved through the confirmation FSM first (ShellSkill
is in _ALWAYS_APPROVE), so the user always sees the exact command before it runs.
Execution then flows through SafeExecutor, which enforces:
  - the command allowlist (non-allowlisted binaries are refused),
  - shell=False always (no shell injection),
  - an output cap (no uncapped output reaches the LLM),
  - a wall-clock timeout.

This is defense-in-depth, NOT a complete sandbox. Allowlisted interpreters
(python, pip) can still run arbitrary code; the user-approval gate is the
primary protection. Container sandboxing remains out of scope (see CR-037).
"""
from __future__ import annotations

import shlex

from src.executor import (
    SafeExecutor,
    PolicyViolation,
    ConfirmationRequired,
    ExecutorError,
)
from src.skills.base import Skill

_RUN_KEYWORDS = (
    "run the test", "run tests", "run pytest", "run the command",
    "run ruff", "run mypy", "run lint", "run the linter", "type check",
    "execute the command", "run this command", "run it", "run the build",
    "check the tests", "run a shell command",
    # PC / system hardware queries — answered by running systeminfo
    "pc spec", "system spec", "hardware spec", "system info", "systeminfo",
    "my specs", "show my specs", "check my specs", "see my specs",
    "how much ram", "my ram", "pc hardware",
    "my processor", "what cpu", "what processor",
    # Broader hardware / PC detail phrases (apostrophe variants handled by stripping ' from query)
    "pc details", "pc detail", "computer details", "computer specs",
    "pcs specs", "pcs details", "pcs hardware",
    "hardware details", "hardware components", "hardware info",
    "system details", "what hardware", "check hardware",
    "what specs", "what is installed", "what's installed",
    "installed hardware", "pc info", "computer info",
    "running with", "running on this", "what's running", "whats running",
    "tell me about my pc", "tell me about my computer",
    "about my pc", "about my system",
    "what is this pc", "what is my pc", "what is my computer",
    "what processor do i have", "what gpu", "what graphics",
)

# Destructive argument patterns refused even for allowlisted binaries.
# Belt-and-suspenders on top of the allowlist (which already blocks rm/del/etc).
_DANGEROUS_PATTERNS = (
    "rm ", "rmdir", "del ", "erase", "format ", "mkfs",
    "reset --hard", "clean -f", "push --force", "push -f",
    "checkout --", "rebase", "filter-branch",
    "shutdown", "reboot", "kill ", "taskkill",
    "chmod", "chown", "icacls", "sudo ",
    " > ", " >> ", "| sh", "| bash", "curl ", "wget ",
)

_MAX_COMMAND_LEN = 500


class ShellSkill(Skill):
    """Runs allowlisted developer commands under SafeExecutor supervision."""

    def can_handle(self, user_input: str, context: dict) -> float:
        """Score whether the user wants a shell command run.

        Args:
            user_input: Raw user message.
            context: Session context dict (unused).

        Returns:
            0.7 when a run/execute phrase is present, else 0.0.
        """
        # Normalize possessives: strip apostrophes so "pc's"/"pc's" -> "pc".
        # Uses chr() to avoid editor smart-quote substitution corrupting codepoints.
        q = user_input.lower()
        for _a in (chr(0x0027), chr(0x2018), chr(0x2019)):
            q = q.replace(_a + "s", "").replace(_a, "")
        if any(kw in q for kw in _RUN_KEYWORDS):
            return 0.7
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        """Return the suggestion shown before running a command.

        Args:
            user_input: Raw user message.
            context: Session context dict (unused).

        Returns:
            A short consent prompt.
        """
        return "I can run that as an allowlisted shell command (you'll approve it first). Proceed?"

    def tool_definition(self) -> dict:
        """Return the LLM tool descriptor for ShellSkill.

        Returns:
            Descriptor dict with name, description, trigger conditions, params,
            timeout, and example phrases (FR-ORCH-005).
        """
        return {
            "name": "ShellSkill",
            "description": (
                "Runs an allowlisted developer command (pytest, ruff, mypy, git, "
                "python, ls, cat, systeminfo) under a security governor. The user "
                "approves the exact command before it runs. Cannot run arbitrary "
                "system binaries."
            ),
            "when": (
                "user asks to run tests, lint, type-check, execute a specific "
                "allowlisted command, or read PC/system hardware specs"
            ),
            "params": {
                "command": "The full command to run, e.g. 'pytest tests/ -q' or 'ruff check src'",
            },
            "timeout_secs": 30,
            "examples": [
                "run the tests",
                "run pytest on the auth module",
                "run ruff on src",
                "type check with mypy",
                "run python smoke_test.py",
                "what are my PC specs",
                "show system info",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Run an allowlisted command after user approval.

        Args:
            user_input: Raw user message (fallback if no command param).
            context: Session context dict; ``last_skill_success`` is set.
            params: Must contain ``command`` — the full command string.

        Returns:
            Formatted command result (exit code, stdout, stderr), or a clear
            refusal/error message. Never raises for normal failures.

        Raises:
            None — all executor exceptions are caught and returned as strings.
        """
        command = (params.get("command") or params.get("_raw") or "").strip()
        if not command:
            context["last_skill_success"] = False
            return "Fíjate — no command was provided to run."

        if len(command) > _MAX_COMMAND_LEN:
            context["last_skill_success"] = False
            return f"Ay no — command too long ({len(command)} chars, max {_MAX_COMMAND_LEN})."

        low = command.lower()
        for pat in _DANGEROUS_PATTERNS:
            if pat in low:
                context["last_skill_success"] = False
                return (
                    f"Ay no — refused: the command contains a destructive pattern "
                    f"(`{pat.strip()}`). I do not run destructive shell operations."
                )

        # Parse into [cmd, *args] without any shell interpretation.
        try:
            parts = shlex.split(command, posix=False)
        except ValueError as exc:
            context["last_skill_success"] = False
            return f"Ay no — could not parse the command: {exc}"
        if not parts:
            context["last_skill_success"] = False
            return "Fíjate — empty command."

        cmd, args = parts[0], parts[1:]
        # Strip surrounding quotes shlex(posix=False) may leave on args.
        args = [a.strip('"').strip("'") for a in args]

        executor = SafeExecutor()
        try:
            # action_type="status" → AUTO tier. The confirmation FSM already
            # provided user approval for this ShellSkill call; the allowlist and
            # shell=False inside SafeExecutor remain the hard safety controls.
            result = executor.run(cmd, args, action_type="status", target=cmd)
        except PolicyViolation as exc:
            context["last_skill_success"] = False
            return (
                f"Ay no — `{cmd}` is not on the allowlist, so I won't run it. "
                f"Allowed: git, python, pip, pytest, ruff, mypy, ls, cat, systeminfo. ({exc})"
            )
        except ConfirmationRequired:
            # Should not occur with action_type="status"; treat defensively.
            context["last_skill_success"] = False
            return f"Fíjate — `{cmd}` needs explicit confirmation and was not run."
        except ExecutorError as exc:
            context["last_skill_success"] = False
            return f"Ay no — command failed to run: {exc}"

        context["last_skill_success"] = result.returncode == 0
        return self._format_result(command, result)

    @staticmethod
    def _format_result(command: str, result) -> str:
        """Format an ExecutorResult into a readable block.

        Args:
            command: The command that was run.
            result: The ExecutorResult.

        Returns:
            A multi-line summary with exit code and captured output.
        """
        status = "✓ exit 0" if result.returncode == 0 else f"✗ exit {result.returncode}"
        lines = [f"`{command}` → {status}"]
        if result.stdout.strip():
            lines.append("\nstdout:\n" + result.stdout.rstrip())
        if result.stderr.strip():
            lines.append("\nstderr:\n" + result.stderr.rstrip())
        if result.truncated:
            lines.append("\n[output truncated]")
        if not result.stdout.strip() and not result.stderr.strip():
            lines.append("(no output)")
        return "\n".join(lines)
