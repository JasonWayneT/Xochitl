# ADR-001 — Streaming Thread Coordination

**Status**: accepted
**Date**: 2026-05-24
**CR**: CR-031 (LLM Token Streaming)
**Deciders**: Jason Wayne (owner), Xochitl agent

---

## Context

Xochitl's chat loop runs LLM calls in a daemon worker thread via `_run_with_cancel()` so that Ctrl-C on the main thread can cancel a long-running call without killing the session. The main thread simultaneously runs a `rich.Live` display (`_StatusContext`) that shows an animated spinner while the worker is running.

When we added real LLM token streaming (CR-031), tokens need to print to the terminal as they arrive from the worker thread. This creates a conflict: Rich's `Live` context owns terminal output during its lifetime, and printing from a second thread while `Live` is active causes display corruption (tokens appear inside or overwrite the spinner line).

### Options considered

**Option A — Main-thread token queue**: Worker puts each token in a `queue.Queue`; main thread reads the queue inside the `join()` poll loop and prints. When the first token arrives, main thread exits the Live context.
- Pro: clean thread boundary; console writes happen only on main thread.
- Con: adds a `queue.Queue` on the hot path; polling logic more complex; the main thread's `with status_ctx:` block now needs to exit *before* the `while worker.is_alive()` loop exits, requiring restructuring.

**Option B — Stop Live from worker thread before first token**: Worker calls `_status._live.stop()` and sets `_status._live = None` before printing the first token. Main thread's `_StatusContext.__exit__` sees `_live = None` and skips double-exit.
- Pro: minimal diff; no new data structures; worker controls timing naturally.
- Con: worker touches main-thread-owned state (the `Live` object); thread-safety relies on Rich's internal lock.

**Option C — Bypass `_run_with_cancel` entirely for streaming**: Add a new synchronous streaming path in `start()` that calls `route_stream()` directly without a worker thread.
- Pro: eliminates threading concern entirely for the streaming case.
- Con: large refactor of `start()`; duplicates context-setup logic from `process_message()`; loses Ctrl-C cancellability during context assembly.

---

## Decision

**Option B** — stop the Live context from the worker thread before the first streaming token.

Rationale:
- Rich's `Live.stop()` is documented to be thread-safe (uses an internal lock).
- The `transient=True` flag on the Live display means stopping it clears the spinner line cleanly, leaving the cursor in the right position for inline token output.
- Setting `_status._live = None` before calling `stop()` prevents `_StatusContext.__exit__` from calling `live.__exit__()` again after the worker already stopped it.
- The diff is contained to `_agent_loop()` — no changes to `start()`, `_run_with_cancel()`, or the threading model.

---

## Consequences

- **Positive**: streaming tokens appear cleanly below the spinner's cleared position; no display corruption in practice.
- **Positive**: existing Ctrl-C / `_run_with_cancel` cancellability is preserved.
- **Negative**: worker thread touches `_status._live` (a main-thread-owned object). If Rich changes the thread-safety contract for `Live.stop()`, this could break.
- **Limitation**: if `_TERM_DUMB=True` (plain console mode), `_status._live` is `None` and the `stop()` call is skipped — no issue.

---

## Follow-on

If Rich's threading model causes issues in practice, migrate to Option A (token queue) — the architectural surface is small and the migration is mechanical. Track as a known limitation until evidence of real-world problems appears.
