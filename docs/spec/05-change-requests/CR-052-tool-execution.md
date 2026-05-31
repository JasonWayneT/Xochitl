# CR-052 — Local CLI Assistant: Tool Execution & Project Awareness

| Field | Value |
|---|---|
| ID | CR-052 |
| Title | Local CLI Assistant: Tool Execution & Project Awareness |
| Status | in progress |
| Priority | P1 |
| Source | Gap analysis (May 2026) — evolve Xochitl into a serious local CLI dev assistant |
| Implements | `FR-EXEC-004`–`FR-EXEC-009`, `FR-GIT-001`–`FR-GIT-003`, `FR-SCAN-001`, `FR-CODE-005`, `FR-UI-011`, `FR-MEM-015`–`FR-MEM-017`, `FR-ORCH-044`, `NFR-EXEC-003`, `NFR-SEC-006` |

## Summary

Xochitl is a functioning personal AI system. The gap to a Claude/Gemini-CLI-class
local dev assistant sits in three areas: shell execution is defined (`SafeExecutor`,
`ActionGovernor`) but not reachable from chat; git is not a first-class tool; and
code generation has no execution/verification loop. This CR closes those gaps in
dependency order, plus supporting safety and awareness features.

All work is local-first (no cloud). New capabilities are gated through the existing
`ActionGovernor` (AUTO/CONFIRM/DENY) and confirmation FSM. No autonomy is introduced
before read-only and approval-gated paths exist.

## Phases

- **Phase 2 — Safe file editing**: diff preview, multi-file confirmation, recent-edits buffer
- **Phase 3 — Tool-using assistant**: ShellSkill, GitSkill, ProjectScanSkill, CodeSkill execution loop
- **Quick wins**: OrchestratorSkill honesty guard, auto-authorize CWD
- **Planning**: lightweight plan-first mode
- **Phase 4 — Project memory**: /index, smart compaction, stale-context detection

## Requirements

### Safe file editing (Phase 2)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-UI-011` | functional | P1 | accepted | `FileTools.write_file()` for an existing file includes a unified diff (old vs new) in the returned `pending_permission` message, capped at a configurable line count. New-file writes show a content preview. Implemented in `src/diff_preview.py`. |
| `FR-MEM-015` | functional | P2 | accepted | A bounded ring buffer of the last N file edits (path, op type, timestamp, line delta) is tracked per session and injected into the SYSTEM_FACTS block so the assistant can answer "what did I just change?" without re-reading. |

### Safety honesty (Quick win)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `NFR-SEC-006` | non-functional | P1 | accepted | `OrchestratorSkill` must not offer to "delegate to a background agent" while the real daemon is unimplemented. Its `suggest()` and `tool_definition()` state that delegation is not yet available; status queries still work. |

### Shell execution (Phase 3)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-EXEC-004` | functional | P0 | accepted | `ShellSkill` exposes `SafeExecutor`-gated command execution to the conversational layer. Registered via `_safe_register()` in `src/skills/__init__.py`. |
| `FR-EXEC-005` | functional | P0 | accepted | `ShellSkill` supports the developer test/lint/build commands: `pytest`, `ruff`, `mypy`, `python -m`. These map to `ActionTier.CONFIRM` (require approval). Read-only commands (`ls`, `cat`, `git status`) map to `ActionTier.AUTO`. |
| `NFR-EXEC-003` | non-functional | P0 | accepted | `ShellSkill` never uses `shell=True`. All execution flows through `SafeExecutor.run()` which enforces the allowlist and output cap. Dangerous verbs (`rm`, `del`, `format`, `reset --hard`) are DENY. |

### Git (Phase 3)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-GIT-001` | functional | P1 | accepted | `GitSkill` exposes read-only git operations (`status`, `diff`, `log`, `branch`, `show`) at `ActionTier.AUTO`. |
| `FR-GIT-002` | functional | P1 | accepted | `GitSkill` supports `add` and `commit` at `ActionTier.CONFIRM`; the confirmation message includes the staged diff summary before the commit proceeds. |
| `FR-GIT-003` | functional | P1 | accepted | `GitSkill` classifies `push --force`, `reset --hard`, and `clean -f` as DENY — never executed. |

### Project awareness (Phase 3)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-SCAN-001` | functional | P1 | accepted | `ProjectScanSkill` performs bounded read-only project structure analysis: list files matching a pattern, find where a Python symbol (function/class) is defined via `ast`. Capped at 500 files and a wall-clock timeout; returns partial results on cap. |

### Code execution loop (Phase 3)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-CODE-005` | functional | P1 | accepted | After generating code to a file, `CodeSkill` can run the associated test command via `ShellSkill`, parse pass/fail, and apply one fix pass on failure, capped at `_MAX_FIX_ITERATIONS` (3). The loop always terminates and reports the final test result. |

### Auto-authorize (Quick win)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-EXEC-006` | functional | P2 | accepted | When `XCH_AUTO_AUTHORIZE=1`, `XochitlChat.start()` authorizes `Path.cwd()` at session start and announces it. Skipped (with a dim warning) if CWD is the user's home directory. Off by default. |

### Plan-first mode (Planning)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-ORCH-044` | functional | P1 | accepted | A `/plan <task>` slash command (and `think:` message prefix) generates a numbered step list via the local reasoning model and stages it for approval before any execution begins. Plan generation makes no file or shell changes. |

### Project memory (Phase 4)

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-MEM-016` | functional | P2 | accepted | A `/index` slash command embeds the current project's source files into LanceDB (chunked), queryable via existing memory recall. Bounded by file count and extension allowlist. |
| `FR-MEM-017` | functional | P2 | accepted | `FileContextEngine.compact()` summarizes injected file content via the local model when token pressure exceeds 80%, instead of hard truncation. Falls back to truncation on summarization failure. |
| `FR-EXEC-007` | functional | P2 | accepted | Injected file content carries a content hash; when the on-disk file changes after injection, a stale-context warning is surfaced. |

## Acceptance Criteria

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| `AC-CR052-001` | `FR-UI-011` | `make_diff_preview(old, new, path)` with changed content | Returns unified-diff string with `---`/`+++` headers and `+`/`-` lines | draft |
| `AC-CR052-002` | `FR-UI-011` | `FileTools.write_file()` on existing file | `pending_permission` message contains a diff section | draft |
| `AC-CR052-003` | `FR-MEM-015` | Record 3 edits, render ring buffer | Buffer contains all 3, most-recent last, capped at N | draft |
| `AC-CR052-004` | `NFR-SEC-006` | `OrchestratorSkill.suggest()` for a delegate request | Message states delegation is not yet available | draft |
| `AC-CR052-005` | `FR-EXEC-004` | `from src.skills.shell_skill import ShellSkill` registered | `_registry.by_name("ShellSkill")` is not None | draft |
| `AC-CR052-006` | `FR-EXEC-005` | `ShellSkill.can_handle("run the tests")` | Score ≥ 0.65 | draft |
| `AC-CR052-007` | `NFR-EXEC-003` | `ShellSkill` attempts `rm -rf` | `SafeExecutor` raises `PolicyViolation` (DENY) | draft |
| `AC-CR052-008` | `FR-GIT-001` | `GitSkill` classifies `git status` | `ActionTier.AUTO` | draft |
| `AC-CR052-009` | `FR-GIT-003` | `GitSkill` classifies `git push --force` | DENY — not executed | draft |
| `AC-CR052-010` | `FR-SCAN-001` | `ProjectScanSkill.find_symbol("can_handle")` in src/skills | Returns ≥1 file:line location | draft |
| `AC-CR052-011` | `FR-SCAN-001` | Scan with 1000-file dir mocked | Stops at 500-file cap, returns partial + notice | draft |
| `AC-CR052-012` | `FR-CODE-005` | Code loop with test that fails once then passes | Loop runs ≤ 3 iterations, terminates, reports pass | draft |
| `AC-CR052-013` | `FR-CODE-005` | Code loop with always-failing test | Stops at `_MAX_FIX_ITERATIONS`, reports final failure | draft |
| `AC-CR052-014` | `FR-EXEC-006` | `start()` with `XCH_AUTO_AUTHORIZE=1`, CWD in a project | `Path.cwd()` is authorized | draft |
| `AC-CR052-015` | `FR-EXEC-006` | `XCH_AUTO_AUTHORIZE=1`, CWD == home | Authorization skipped, warning shown | draft |
| `AC-CR052-016` | `FR-ORCH-044` | `/plan refactor the router` | Numbered plan staged for approval; no files changed | draft |
| `AC-CR052-017` | `FR-MEM-016` | `/index` in a project with .py files | Files embedded into LanceDB; count reported | draft |
| `AC-CR052-018` | `FR-MEM-017` | `FileContextEngine.compact()` over-budget | Returns summarized (not hard-truncated) content; falls back on error | draft |
| `AC-CR052-019` | `FR-EXEC-007` | Inject a file, modify on disk, re-query | Stale-context warning surfaced | draft |

## Out of Scope (Do Not Build in CR-052)

- OrchestratorSkill real background daemon (Phase 5; needs process isolation)
- Resume/job automation workflow (Phase 5)
- Browser automation (attack surface)
- Multi-provider LLM routing beyond existing Gemini/Anthropic
- Streaming shell output (basic ShellSkill first)
- `SlashContext` dataclass refactor (TASK-DEV-051-b)

## Verification

Each phase is committed independently with smoke tests added per acceptance
criterion. `python smoke_test.py` and `python tests/end_to_end_test.py` must pass
after every commit.
