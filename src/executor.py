"""Safe executor with action permission governor.

Implements FR-EXEC-001 (ActionGovernor — pure classify function),
FR-EXEC-002 (SafeExecutor.run — governor-first dispatch with output cap),
FR-EXEC-003 (allowlist enforcement), NFR-EXEC-001 (no shell=True, no eval/exec,
pure classify), NFR-EXEC-002 (output cap, no raw stdout to LLM prompt,
governor always first).

Docker/gVisor sandboxing for LLM-generated code is explicitly out of scope
— it requires container infrastructure not available in the current deployment.
See CR-037 for rationale.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePath
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

# Subprocess output cap — raw output larger than this is truncated (FR-EXEC-002).
_OUTPUT_CAP_BYTES: int = 65_536  # 64 KB

# Per-command wall-clock timeout in seconds for subprocess calls.
_SUBPROCESS_TIMEOUT_SECS: int = 10

# Allowlist of permitted base command names (FR-EXEC-003).
# Intentionally minimal — adding commands requires an explicit code change.
_ALLOWED_COMMANDS: frozenset[str] = frozenset({
    "git", "python", "python3", "pip", "pip3",
    "pytest", "ls", "dir", "echo", "cat", "type",
    # CR-052 FR-EXEC-005: developer test/lint/type tools.
    "ruff", "mypy",
    # Read-only system info (Windows). Lets Xochitl answer PC-specs questions.
    "systeminfo",
})

# Action types that map to AUTO tier (read-only, non-destructive).
_AUTO_TYPES: frozenset[str] = frozenset({
    "read", "lookup", "status", "check", "list", "search", "get", "fetch",
})

# Action types that map to CONFIRM tier (writes, deletes, side effects).
_CONFIRM_TYPES: frozenset[str] = frozenset({
    "write", "delete", "remove", "update", "create", "post", "patch",
    "sync", "push", "exec", "run", "subprocess",
})


# ── Enumerations ──────────────────────────────────────────────────────────────

class ActionTier(str, Enum):
    """Permission tier for a proposed action (planning doc #18, #19).

    AUTO    — read-only / non-destructive. Execute immediately, log only.
    CONFIRM — writes, deletes, external side effects. Require user y/N.
    DENY    — outside security policy. Raise PolicyViolation immediately.
    """

    AUTO = "auto"
    CONFIRM = "confirm"
    DENY = "deny"


# ── Exceptions ────────────────────────────────────────────────────────────────

class ExecutorError(Exception):
    """Base class for all executor errors."""


class PolicyViolation(ExecutorError):
    """Raised when an action is classified DENY — outside security policy.

    Logged and re-raised immediately; never silently swallowed.
    """


@dataclass
class ConfirmationRequired(ExecutorError):
    """Raised when an action is classified CONFIRM — user must approve.

    The caller is responsible for prompting the user and re-invoking
    SafeExecutor.run() only after receiving explicit confirmation.

    Attributes:
        action_tier: Always ``ActionTier.CONFIRM``.
        cmd: The command that requires confirmation.
        args: Arguments to the command.
    """

    action_tier: ActionTier
    cmd: str
    args: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Confirmation required: {self.cmd} {' '.join(self.args)} "
            f"(tier={self.action_tier.value})"
        )


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ExecutorResult:
    """Result of a successful SafeExecutor.run() call.

    Attributes:
        returncode: Exit code from the subprocess (0 = success).
        stdout: Captured standard output (decoded UTF-8, lossy).
        stderr: Captured standard error (decoded UTF-8, lossy).
        truncated: True if stdout + stderr were capped at _OUTPUT_CAP_BYTES.
    """

    returncode: int
    stdout: str
    stderr: str
    truncated: bool = False


# ── Governor ─────────────────────────────────────────────────────────────────

class ActionGovernor:
    """Pure-function action classifier (FR-EXEC-001).

    No state, no side effects, no I/O — fully testable in isolation.
    Classifies (action_type, target) pairs into ActionTier before dispatch.
    """

    @staticmethod
    def classify(action_type: str, target: str = "") -> ActionTier:
        """Classify an action as AUTO, CONFIRM, or DENY (FR-EXEC-001).

        Classification rules (in priority order):
          1. DENY: target contains path traversal sequences ("..").
          2. AUTO: action_type is in _AUTO_TYPES.
          3. CONFIRM: action_type is in _CONFIRM_TYPES.
          4. DENY: action_type not recognised (fail closed).

        Pure function — no side effects, no I/O (NFR-EXEC-001).

        Args:
            action_type: Verb describing the action (e.g. "read", "delete").
                Case-insensitive.
            target: The object of the action (file path, URL, etc.).

        Returns:
            The ``ActionTier`` that governs this action.
        """
        action_lower = action_type.lower().strip()
        target_str = str(target)

        # Path traversal check — catches "../../etc/passwd" style attacks.
        # Uses PurePath for cross-platform normalisation, then checks parts.
        try:
            if ".." in PurePath(target_str).parts:
                logger.warning(
                    "executor: DENY path traversal attempt: action=%s target=%s",
                    action_lower,
                    target_str,
                )
                return ActionTier.DENY
        except Exception:
            # PurePath can raise on some degenerate inputs — treat as DENY.
            return ActionTier.DENY

        # Also catch raw ".." substring in case PurePath misses edge cases.
        if ".." in target_str:
            return ActionTier.DENY

        if action_lower in _AUTO_TYPES:
            return ActionTier.AUTO

        if action_lower in _CONFIRM_TYPES:
            return ActionTier.CONFIRM

        # Unknown action type — fail closed.
        logger.warning(
            "executor: DENY unknown action type: %s (target=%s)",
            action_lower,
            target_str,
        )
        return ActionTier.DENY


# ── Executor ──────────────────────────────────────────────────────────────────

class SafeExecutor:
    """Allowlist-enforced subprocess executor with output cap (FR-EXEC-002, FR-EXEC-003).

    The governor is ALWAYS called first — there is no path that bypasses it
    (NFR-EXEC-002). shell=True is NEVER used (NFR-EXEC-001).
    """

    def __init__(self, governor: Optional[ActionGovernor] = None) -> None:
        self._governor = governor or ActionGovernor()

    def run(
        self,
        cmd: str,
        args: Optional[list[str]] = None,
        *,
        action_type: str = "exec",
        target: str = "",
    ) -> ExecutorResult:
        """Run an allowlisted command under governor supervision (FR-EXEC-002).

        Steps:
          1. Allowlist check — DENY if cmd base name not in _ALLOWED_COMMANDS.
          2. Governor classification — AUTO proceeds; CONFIRM raises; DENY raises.
          3. subprocess.run(shell=False) with _SUBPROCESS_TIMEOUT_SECS.
          4. Output cap — truncate to _OUTPUT_CAP_BYTES if needed.

        Args:
            cmd: The executable to run (base name checked against allowlist).
            args: Arguments to pass (must not include shell metacharacters).
            action_type: Verb for governor classification (default "exec").
            target: Target resource for governor classification.

        Returns:
            ``ExecutorResult`` with captured stdout/stderr and truncation flag.

        Raises:
            PolicyViolation: If cmd is not allowlisted, or governor returns DENY.
            ConfirmationRequired: If governor returns CONFIRM.
            ExecutorError: On subprocess timeout or unexpected OS error.
        """
        if args is None:
            args = []

        # FR-EXEC-003: allowlist check — governor does not override this.
        base_cmd = PurePath(cmd).name
        if base_cmd not in _ALLOWED_COMMANDS:
            msg = f"Command '{base_cmd}' is not on the executor allowlist"
            logger.warning("executor: DENY — %s", msg)
            raise PolicyViolation(msg)

        # FR-EXEC-001 / NFR-EXEC-002: governor ALWAYS runs before dispatch.
        effective_target = target or cmd
        tier = self._governor.classify(action_type, effective_target)
        logger.debug(
            "executor: %s classified as %s (action=%s, target=%s)",
            cmd,
            tier.value,
            action_type,
            effective_target,
        )

        if tier == ActionTier.DENY:
            msg = (
                f"Action '{action_type}' on '{effective_target}' is denied by policy"
            )
            logger.warning("executor: DENY — %s", msg)
            raise PolicyViolation(msg)

        if tier == ActionTier.CONFIRM:
            raise ConfirmationRequired(
                action_tier=ActionTier.CONFIRM,
                cmd=cmd,
                args=list(args),
            )

        # ActionTier.AUTO — execute now.
        # NFR-EXEC-001: shell=False always; never eval/exec on generated content.
        try:
            proc = subprocess.run(
                [cmd, *args],
                shell=False,             # NEVER True — NFR-EXEC-001
                capture_output=True,
                timeout=_SUBPROCESS_TIMEOUT_SECS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExecutorError(
                f"Command '{cmd}' timed out after {_SUBPROCESS_TIMEOUT_SECS}s"
            ) from exc
        except OSError as exc:
            raise ExecutorError(f"Command '{cmd}' failed to start: {exc}") from exc

        # NFR-EXEC-002: cap output before returning — never pass uncapped to LLM.
        # FR-HARD-001: split cap 80/20 so stderr is never silently discarded.
        raw = proc.stdout + proc.stderr
        truncated = len(raw) > _OUTPUT_CAP_BYTES
        if truncated:
            _stdout_cap = int(_OUTPUT_CAP_BYTES * 0.80)
            _stderr_cap = _OUTPUT_CAP_BYTES - _stdout_cap
            stdout_raw = proc.stdout[:_stdout_cap]
            if len(proc.stdout) > _stdout_cap:
                stdout_raw += f"\n[stdout truncated — {len(proc.stdout)} bytes total]".encode()
            stderr_raw = proc.stderr[:_stderr_cap]
            if len(proc.stderr) > _stderr_cap:
                stderr_raw += f"\n[stderr truncated — {len(proc.stderr)} bytes total]".encode()
        else:
            stdout_raw = proc.stdout
            stderr_raw = proc.stderr

        return ExecutorResult(
            returncode=proc.returncode,
            stdout=stdout_raw.decode("utf-8", errors="replace"),
            stderr=stderr_raw.decode("utf-8", errors="replace"),
            truncated=truncated,
        )
