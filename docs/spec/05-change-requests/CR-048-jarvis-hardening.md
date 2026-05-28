# CR-048 — JARVIS Hardening

| Field | Value |
|---|---|
| ID | CR-048 |
| Title | JARVIS Hardening — Situational Awareness, Proactive Intelligence, and UX Polish |
| Status | accepted |
| Priority | P1 |
| Author | Jason Wayne |
| Date | 2026-05-27 |
| Implements | FR-JARV-001 through FR-JARV-012, NFR-JARV-001 through NFR-JARV-003 |
| Registry | Add FR-JARV-001 – FR-JARV-012, NFR-JARV-001 – NFR-JARV-003 |

## Summary

Following a comprehensive 50-item JARVIS audit, this CR implements the highest-impact improvements grouped into five themes:

1. **Situational Awareness** — Xochitl knows the time, git state, and Notion freshness on every turn
2. **Proactive Intelligence** — New initiative categories (deadline, follow-on, celebration) + gradual budget warnings
3. **Skill Reliability** — Execution timeout wrapper preventing hung sessions
4. **Session Continuity** — Boot banner shows last-session resume summary
5. **UX Polish** — `/status` command, `@mention` fallback suggestion, richer loading tips

## Motivation

The current system has several gaps between "smart assistant" and "JARVIS-grade":
- `[SYSTEM_FACTS]` tells the model the CWD and WIP count but not the time or git state — causing greetings and context to feel generic
- The `InitiativeEngine` only has two permitted categories; deadlines and follow-on suggestions can't be surfaced proactively
- Sessions start cold with no reference to what was happening last time
- Budget warnings only fire at tier boundaries, not as the user approaches them
- Skill execution can hang indefinitely if an external API stalls

## Theme 1 — Situational Awareness (FR-JARV-001 to FR-JARV-003)

### FR-JARV-001: Time-of-day in SYSTEM_FACTS

`FactsEngine.assemble()` appends a `Time: HH:MM (greeting)` line to the `[SYSTEM_FACTS]` block. This allows Xochitl to naturally greet with "good morning" or adjust response energy at end-of-day without the user having to mention the time.

### FR-JARV-002: Git state in SYSTEM_FACTS

`FactsEngine.ingest()` runs `git rev-parse --abbrev-ref HEAD` and `git log --oneline -1` with a tight timeout. The result appears as `Git: branch=master | last=<short commit message>` in `[SYSTEM_FACTS]`. Failures are silently swallowed — the block is omitted when not in a git repo.

### FR-JARV-003: Notion freshness indicator

`FactsEngine.ingest()` queries `sync_log` for the most recent sync timestamp. The result appears as `Notion: last synced <N> minutes ago` (or "never synced"). Lets Xochitl warn proactively when data is stale without the user asking.

## Theme 2 — Proactive Intelligence (FR-JARV-004 to FR-JARV-005)

### FR-JARV-004: New InitiativeCategory members

Add four new permitted categories to `InitiativeCategory`:
- `DEADLINE` — a task in the queue has a deadline within 48 hours
- `FOLLOWUP_SUGGESTION` — Xochitl identified a natural next step from the prior turn
- `SKILL_HEALTH` — a configured skill is missing credentials or has a stale token
- `CELEBRATION` — a milestone reached (queue drained, N tasks completed today)

`submit()` gates `DEADLINE` and `SKILL_HEALTH` through `ERRORS_ONLY` mode (critical enough to show by default); `FOLLOWUP_SUGGESTION` and `CELEBRATION` require `FULL` mode.

### FR-JARV-005: Gradual budget degradation warnings

`SessionGovernor` exposes `approach_pct(tier)` — the percentage of the gap to the *next* tier threshold consumed. Chat loop shows a yellow hint at 75% and 90% approach to each threshold, giving the user advance notice before hitting a routing change. These are shown at most once each (same `should_warn()` pattern as tier changes).

## Theme 3 — Skill Reliability (FR-JARV-006 to FR-JARV-007)

### FR-JARV-006: Skill execution timeout

`XochitlChat._execute_skill_safe()` wraps `skill.execute()` in a `threading.Thread` with a 30-second join timeout. If the skill does not return within the timeout, the method returns a user-friendly error message and the skill is flagged as `last_skill_timeout=True` in context. This prevents a stalled external API (e.g., Maps, Gmail) from freezing the entire session.

### FR-JARV-007: Skill health check on startup

`XochitlChat.start()` runs a non-blocking health pass over all skills that implement `health_check()` after session creation. Skills that return `False` queue a `SKILL_HEALTH` initiative signal so Xochitl surfaces the issue at the start of the first relevant turn.

## Theme 4 — Session Continuity (FR-JARV-008)

### FR-JARV-008: Session resume summary in boot banner

`_print_boot_banner()` queries the `sessions` table for the most recent prior session's `context_summary` and last-active timestamp. If the gap is < 24 hours and a summary exists, a compact one-line "last session: ..." hint is printed below the WIP dashboard. Lets the user immediately recall where they left off without having to ask.

## Theme 5 — UX Polish (FR-JARV-009 to FR-JARV-012)

### FR-JARV-009: @mention fallback suggestion

When `@SomeName` is not matched to any skill, instead of silently falling through, the system prints `[dim]No skill named 'SomeName'. Try /debug skill to see available skills.[/dim]` and continues with normal routing. Prevents the silent failure that currently occurs.

### FR-JARV-010: Enhanced JARVIS-style loading tips

Expand `_StatusContext._TIPS` from 18 to 30 entries with more capability-revealing, personality-rich tips that teach the user about Xochitl's advanced features (BMAD pipeline, zettelkasten, workflow memory, etc.).

### FR-JARV-011: /status command

`/status` prints a concise system health table: local model online/offline, cloud route available, Notion token present, Gmail token present, session token budget, WIP count. Replaces the need to run `health_check` externally.

### FR-JARV-012: Save session context_summary on every turn

`XochitlChat._record()` (the method that appends every assistant response to history) updates `sessions.context_summary` in the database with a compact one-line summary of the last assistant reply. This feeds FR-JARV-008 (resume summary) on the next session start.

## Acceptance criteria

| ID | Requirement | Scenario | Expected |
|---|---|---|---|
| AC-CR048-001 | FR-JARV-001 | `FactsEngine.assemble()` called at 09:00 | Output contains "Time:" and "Good morning" |
| AC-CR048-002 | FR-JARV-002 | `FactsEngine.assemble()` in git repo | Output contains "Git: branch=" |
| AC-CR048-003 | FR-JARV-002 | `FactsEngine.assemble()` outside git repo | Omits Git line; no exception raised |
| AC-CR048-004 | FR-JARV-003 | `FactsEngine.assemble()` with sync entry | Output contains "Notion:" |
| AC-CR048-005 | FR-JARV-004 | `InitiativeCategory.DEADLINE` imported | Exists in enum without error |
| AC-CR048-006 | FR-JARV-004 | `submit(DEADLINE, conf=0.9)` in ERRORS_ONLY mode | Signal is queued |
| AC-CR048-007 | FR-JARV-004 | `submit(CELEBRATION, conf=0.9)` in ERRORS_ONLY mode | Signal is NOT queued |
| AC-CR048-008 | FR-JARV-005 | `SessionGovernor.approach_pct(Tier.LOCAL_ONLY)` | Returns float 0.0–1.0 |
| AC-CR048-009 | FR-JARV-006 | Skill times out after 30s | Returns timeout error string; no crash |
| AC-CR048-010 | FR-JARV-009 | `@UnknownSkill hello` sent | Response contains "No skill named" |
| AC-CR048-011 | FR-JARV-011 | `/status` typed in chat | Response contains "local model" and "WIP" |
| AC-CR048-012 | All | `python smoke_test.py` | ≥ 165 tests pass, 0 failures |

## Files changed

| File | Change |
|---|---|
| `src/context_manager.py` | `FactsEngine.ingest()` + `assemble()` — time, git, Notion freshness |
| `src/initiative.py` | `InitiativeCategory` — 4 new enum members; `submit()` gate for `DEADLINE`/`SKILL_HEALTH` |
| `src/governor.py` | `approach_pct()`, `should_warn_approach()` methods |
| `src/chat.py` | `_execute_skill_safe()`, `_print_boot_banner()` resume hint, `@mention` fallback, `/status`, tips |
| `smoke_test.py` | New tests for AC-CR048-001 through AC-CR048-011 |
