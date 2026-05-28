# CR-050 — Performance, Reliability, and Local Model Optimization

| Field | Value |
|---|---|
| ID | CR-050 |
| Title | Performance, Reliability, and Local Model Optimization |
| Status | in-progress |
| Priority | P0–P2 |
| Source | Post-CR-049 audit |
| Implements | FR-PERF-001–008, NFR-PERF-012–015, FR-RELY-001–006, FR-UX-001–006 |

## Summary

Twenty targeted improvements identified after the CR-049 code hardening session. Improvements fall into four themes:

- **Fast Path**: Eliminate redundant LLM calls and stale computations (B1, B2, B3, A5, A6, A7)
- **Context Efficiency**: Reduce per-turn overhead (B2, B3, A6, C3)
- **Reliability**: Fix silent failure modes and persistence gaps (B4, B5, B6, C1, C2, A8)
- **UX Polish**: Surface useful information to the user (A1, A2, A3, A4)

## Requirements

### Performance

| ID | Type | Priority | Status | Requirement | Notes |
|---|---|---|---|---|---|
| `FR-PERF-001` | functional | P0 | accepted | `_fast_classify()` returns a `(category, confidence)` tuple; `_classify()` skips the LLM call when confidence ≥ 0.85 | Implements B1 |
| `FR-PERF-002` | functional | P0 | accepted | `ChatSession` caches assembled system prompt keyed by `(session_id, history_len, last_mutating_skill)`; re-assembles only when the key changes | Implements B2 |
| `FR-PERF-003` | functional | P1 | accepted | Each `can_handle()` call runs inside a `ThreadPoolExecutor` future with a 100ms timeout; result is cached for the current turn message hash | Implements B3 |
| `FR-PERF-004` | functional | P1 | accepted | `_resolve_file_context()` enforces an 8 KB total cap across all injected files; most-recently-modified files are selected first; a truncation notice is appended when the cap is hit | Implements A6 |
| `FR-PERF-005` | functional | P1 | accepted | `_execute_skill_safe()` reads `skill.tool_definition().get("timeout_secs", 30)` instead of using a hardcoded 30-second constant | Implements A7 |
| `FR-PERF-006` | functional | P2 | accepted | `_route_local()` passes `options={"temperature": _CATEGORY_TEMPERATURE[category]}` to each Ollama call; temperature is configurable per category via env vars | Implements A5 |
| `FR-PERF-007` | functional | P1 | accepted | `_parse_skill_calls()` uses `re.findall()` and returns all `<skill_call>` blocks per LLM response; the agent loop executes all calls in sequence | Implements C3 |
| `FR-PERF-008` | functional | P2 | accepted | Skill-injected turns stream tokens to the terminal in real time; `<skill_call>` parsing runs on the completed buffer after streaming ends | Implements D2 |

### Non-functional Performance

| ID | Type | Priority | Status | Requirement | Notes |
|---|---|---|---|---|---|
| `NFR-PERF-012` | non-functional | P1 | accepted | `can_handle()` must complete (or time out) within 100ms per skill per turn | Implements B3 |
| `NFR-PERF-013` | non-functional | P1 | accepted | File context injected per turn must not exceed 8 KB total | Implements A6 |
| `NFR-PERF-014` | non-functional | P2 | accepted | ContextManager cache hit rate ≥ 50% across consecutive turns in a typical session | Implements B2 |
| `NFR-PERF-015` | non-functional | P1 | accepted | Per-skill timeout config must not change default behavior for skills that do not specify `timeout_secs` | Implements A7 |

### Reliability

| ID | Type | Priority | Status | Requirement | Notes |
|---|---|---|---|---|---|
| `FR-RELY-001` | functional | P1 | accepted | When `BackgroundReview.is_alive()` returns False at the start of an agent loop, `ChatSession` restarts the daemon and emits a `SYSTEM_FAILURE` initiative signal | Implements B4 |
| `FR-RELY-002` | functional | P1 | accepted | `InitiativeEngine` persists `_dismissal_counts` and `_suppressed` to a new `initiative_state` SQLite table; state is loaded on construction when `db_path` is provided | Implements B5 |
| `FR-RELY-003` | functional | P1 | accepted | At session start, `decay_memory_facts()` multiplies each `memory_facts.confidence` by `0.95^days_since_update` (floor 0.3) and deletes rows below 0.2 | Implements B6 |
| `FR-RELY-004` | functional | P2 | accepted | `Skill` base class adds an optional `cleanup()` method; `_execute_skill_safe()` calls it in a daemon thread (5-second join limit) after a timeout | Implements D1 |
| `FR-RELY-005` | functional | P2 | accepted | `UserProfileEngine.ingest()` tracks an MD5 hash of `Me.md` content; when the hash changes, `MemoryEngine.re_embed_profile()` is triggered in a background thread | Implements C1 |
| `FR-RELY-006` | functional | P1 | accepted | `upsert_workflow()` validates step dicts with `validate_workflow_steps()` before writing; `ValueError` is raised on invalid steps and caught by the caller | Implements A8 |

### UX

| ID | Type | Priority | Status | Requirement | Notes |
|---|---|---|---|---|---|
| `FR-UX-001` | functional | P2 | accepted | `wrap_text()` calls `shutil.get_terminal_size()` inline at call time instead of relying on the module-level constant, so terminal resizing mid-session is reflected immediately | Implements A1 |
| `FR-UX-002` | functional | P2 | accepted | `strip_filler_opener()` iterates up to 5 times (early-exit on no change) to remove consecutive openers from LLM responses | Implements A2 |
| `FR-UX-003` | functional | P2 | accepted | `build_structured_brief()` includes a human-readable duration label ("today", "3d", "1w 2d") next to each WIP task, derived from `tasks.created_at` | Implements A3 |
| `FR-UX-004` | functional | P1 | accepted | `/status` command is extended to show memory_facts row count, workflows row count, background review daemon health, and initiative mode | Implements A4 |
| `FR-UX-005` | functional | P1 | accepted | `tasks` and `projects` tables gain a `deleted_at TEXT` column; hard DELETEs are replaced by soft-delete UPDATEs; all SELECT queries filter by `deleted_at IS NULL` | Implements C2 |
| `FR-UX-006` | functional | P1 | accepted | When `upsert_workflow()` raises `ValueError`, the calling code in `workflows.py` returns a user-visible error string instead of propagating the exception | Implements A8 companion |

## Acceptance Criteria

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| `AC-CR050-001` | `FR-UX-001` | `wrap_text("x" * 200)` with mocked terminal size 40 | All lines ≤ 40 chars | draft |
| `AC-CR050-002` | `FR-UX-002` | `strip_filler_opener("Certainly! Of course! Let me help — here is the answer.")` | Both openers stripped | draft |
| `AC-CR050-003` | `FR-UX-003` | Brief with task `created_at` 8 days ago | Output contains "1w 1d" | draft |
| `AC-CR050-004` | `FR-UX-004` | `/status` command | Output contains "memory_facts" and "workflows" | draft |
| `AC-CR050-005` | `FR-PERF-006` | `_CATEGORY_TEMPERATURE` values | `code_generation < general < creative` | draft |
| `AC-CR050-006` | `FR-PERF-004` | `_resolve_file_context()` with 10 × 2KB files | Result length ≤ 8 KB + 200 bytes | draft |
| `AC-CR050-007` | `FR-PERF-005` | Skill with `timeout_secs: 1` sleeps 2s | Timeout fires at ~1s | draft |
| `AC-CR050-008` | `FR-RELY-006` | `upsert_workflow()` with step missing `"description"` | Raises `ValueError` | draft |
| `AC-CR050-009` | `FR-PERF-001` | `/today` → `_fast_classify` | Returns `task_management` without LLM call | draft |
| `AC-CR050-010` | `FR-PERF-002` | Two consecutive identical messages | `subprocess.run` called exactly once for git | draft |
| `AC-CR050-011` | `FR-PERF-003` | Skill with `can_handle()` sleeping 2s | Agent loop completes within 500ms | draft |
| `AC-CR050-012` | `FR-RELY-001` | `is_alive()` mocked False | `BackgroundReview.start()` invoked | draft |
| `AC-CR050-013` | `FR-RELY-002` | Dismiss DEADLINE 3×, restart engine from same db | `DEADLINE in engine._suppressed` | draft |
| `AC-CR050-014` | `FR-RELY-003` | `memory_facts` row 180 days old | Confidence reduced or row deleted | draft |
| `AC-CR050-015` | `FR-RELY-005` | Me.md content change detected | `re_embed_profile()` called once | draft |
| `AC-CR050-016` | `FR-UX-005` | Task soft-deleted | Not in `get_task_queue()`; row still in DB | draft |
| `AC-CR050-017` | `FR-PERF-007` | LLM response with two `<skill_call>` blocks | Both `execute()` called | draft |
| `AC-CR050-018` | `FR-RELY-004` | Skill `cleanup()` mock; timeout triggered | Sentinel set within 6 seconds | draft |

## Implementation Order

Phase A → Phase B → Phase C → Phase D (see CR-050-session-plan.md for step-by-step)

## Test Count Targets

| After Phase | Expected Tests |
|---|---|
| Baseline | 186 |
| After Phase A | ~196 |
| After Phase B | ~210 |
| After Phase C | ~220 |
| After Phase D | ~226 |
