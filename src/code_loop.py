"""Bounded generate→run→fix loop control flow.

Implements FR-CODE-005 (CR-052). The control flow is a pure function so it can
be tested without running real tests or writing real files: callers inject a
``run_tests`` callable and an ``apply_fix`` callable.

Safety: the loop NEVER applies a fix on its own. ``apply_fix`` is supplied by
the caller, and the caller decides whether that callable writes files (opt-in,
``XCH_CODE_AUTOFIX=1``) or is a no-op (default — report only). The loop only
governs *how many* iterations may happen and guarantees termination.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

# Hard cap on fix attempts. Override with XCH_MAX_FIX_ITERATIONS.
_MAX_FIX_ITERATIONS: int = int(os.getenv("XCH_MAX_FIX_ITERATIONS", "3"))


@dataclass
class FixLoopResult:
    """Outcome of a generate→run→fix loop.

    Attributes:
        passed: True if tests passed (initially or after a fix).
        iterations: Number of fix attempts made (0 if it passed first run).
        final_output: The last test output observed.
        stopped_reason: "passed", "max_iterations", or "no_fix".
    """
    passed: bool
    iterations: int
    final_output: str
    stopped_reason: str


def run_fix_loop(
    run_tests: Callable[[], tuple[bool, str]],
    apply_fix: Callable[[str], bool],
    max_iterations: int | None = None,
) -> FixLoopResult:
    """Run tests, and on failure attempt bounded fixes until they pass or give up.

    Args:
        run_tests: Callable returning ``(passed, output)``. Called once up front
            and once after each applied fix.
        apply_fix: Callable given the failing test output; returns True if it
            applied a fix (so another test run is warranted), False to stop.
        max_iterations: Maximum fix attempts. Defaults to ``_MAX_FIX_ITERATIONS``.
            Pass 0 for report-only (run tests once, never fix).

    Returns:
        A ``FixLoopResult``. The loop is guaranteed to terminate: it runs at most
        ``max_iterations`` fix attempts and re-runs tests at most
        ``max_iterations + 1`` times total.
    """
    cap = _MAX_FIX_ITERATIONS if max_iterations is None else max(0, int(max_iterations))

    passed, output = run_tests()
    if passed:
        return FixLoopResult(True, 0, output, "passed")

    iterations = 0
    while iterations < cap:
        applied = apply_fix(output)
        if not applied:
            return FixLoopResult(False, iterations, output, "no_fix")
        iterations += 1
        passed, output = run_tests()
        if passed:
            return FixLoopResult(True, iterations, output, "passed")

    return FixLoopResult(False, iterations, output, "max_iterations")


def autofix_enabled() -> bool:
    """Return True when autonomous fix-and-write is explicitly opted in.

    Returns:
        True only when ``XCH_CODE_AUTOFIX=1``. Default is False (report-only),
        so the assistant never writes files in an unattended loop unless the
        user turns it on.
    """
    return os.getenv("XCH_CODE_AUTOFIX") == "1"
