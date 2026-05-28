# CR-050 — Implementation Session Plan
## Performance, Reliability, and Local Model Optimization

---

## START HERE (Read This First)

This document is a **self-contained implementation brief** for a new Claude Code session. It covers all 20 improvements identified in the post-CR-049 audit. You have explicit permission to implement everything here.

**Before writing a single line of code:**

1. Read `AGENTS.md` — the prime directive is documentation chain first, code second
2. Confirm the smoke tests pass clean: `python smoke_test.py` → should show 186 passed, 0 failed
3. Create the CR-050 document at `docs/spec/05-change-requests/CR-050-performance-reliability.md` first
4. Add all requirement IDs to `docs/spec/02-requirements-registry.md`
5. Then implement phase by phase, running smoke tests after each phase
6. Update traceability matrix last, then commit

**Convention:** Every commit must use a scope from the CLAUDE.md table: `feat(orch):`, `fix(skill):`, `refactor(data):`, etc.

**Key invariant:** Never call a skill's `execute()` directly from `can_handle()`. Never call `router.route()` from inside a skill. Never put raw SQL outside `database.py`.

---

## CR-050 Overview

| Field | Value |
|---|---|
| ID | CR-050 |
| Title | Performance, Reliability, and Local Model Optimization |
| Priority | P0–P2 |
| Implements | FR-PERF-001–008, NFR-PERF-012–015, FR-RELY-001–006, FR-UX-001–006 |
| Themes | Fast Path · Context Efficiency · Reliability · Local Model Quality |

**20 improvements across 4 phases:**

| Phase | Theme | Items | Risk | Est. Time |
|---|---|---|---|---|
| A | Quick Wins | 8 items (#11, #13, #19, #16, #17, #8, #9, #12) | Low | 2–3 hrs |
| B | Performance Core | 6 items (#1, #2+#18, #5, #6, #4, #7) | Low–Med | 3–4 hrs |
| C | Reliability | 3 items (#3, #15, #14) | Low–Med | 2–3 hrs |
| D | Architectural | 3 items (#10, #7-multi, #20) | Med–High | 3–5 hrs |

---

## PHASE A — Quick Wins
*Low risk, isolated changes. Implement these first. Each is ≤ 30 minutes.*

---

### A1 — Terminal Width Dynamic Refresh
**Original list item #11**

**What:** `MAX_LINE_WIDTH` in `terminal_output.py` is set once at import via `shutil.get_terminal_size()`. If the user resizes the terminal mid-session, all text wraps to the stale width. Change `wrap_text()` to call `shutil.get_terminal_size()` inline at call time rather than relying on the module-level constant.

**Files:** `src/terminal_output.py`

**Steps:**
1. Keep the module-level `MAX_LINE_WIDTH` constant as the fallback default for use by other modules that import it
2. In `wrap_text(text, width=None)`: change the signature to accept an optional width; if `width` is None, call `shutil.get_terminal_size((80, 24)).columns` inline
3. All callers that pass explicit width continue to work unchanged
4. Add smoke test: call `wrap_text("x" * 200)` with a mocked terminal size of 40; assert result has no line longer than 40 chars

**Test ID:** `t_terminal_width_refreshes_on_wrap`
**Risk:** Low — `wrap_text()` is a pure formatting utility

---

### A2 — Filler Opener Multi-Pass Cleaner
**Original list item #13**

**What:** `strip_filler_opener()` in `conversation.py` uses `re.sub()` which replaces only the first match. If a local model outputs "Certainly! Of course, let me help you with that — " (two openers), only "Certainly!" is removed. Change to a while loop that strips openers until no more match, with a max of 5 iterations to prevent an infinite loop on pathological input.

**Files:** `src/conversation.py` (`strip_filler_opener()`)

**Steps:**
1. Wrap the current `re.sub()` call in a `for _ in range(5):` loop
2. After each substitution, check if `result == original`; if so, break early (no more openers)
3. Update the `original` variable each iteration to track progress
4. Add smoke test: input = `"Certainly! Of course! Let me help — here is the answer."`; assert both openers are stripped and "here is the answer." remains

**Test ID:** `t_strip_filler_handles_double_opener`
**Risk:** Low — max 5 iterations prevents runaway; existing single-opener tests must still pass

---

### A3 — Brief Task Duration in WIP Queue
**Original list item #19**

**What:** `build_structured_brief()` in `brief.py` shows the top 3 WIP tasks but not how long they have been in the queue. Add a duration label ("3d", "1w 2d", "today") next to each task in the brief output, calculated from the task's `created_at` timestamp.

**Files:** `src/brief.py`, `src/database.py` (read `created_at` from queue join)

**Steps:**
1. In `database.py`, update the queue query helper (whichever function `brief.py` calls) to `JOIN tasks ON queue.task_id = tasks.id` and return `tasks.created_at`
2. In `brief.py`, add `_format_duration(created_at: str) -> str`: parse `created_at` as ISO datetime; compute days since; return `"today"` / `"Nd"` / `"Nw Nd"`
3. Inject the duration string into the task line: `f"  {pos}. {description} ({duration})"`
4. Add smoke test: mock queue tasks with a created_at 8 days ago; assert brief output contains "1w 1d"

**Test ID:** `t_brief_shows_task_duration`
**Risk:** Low — additive to existing brief output; `created_at` already exists in schema

---

### A4 — `/status` Command: Memory Tier Stats and Daemon Health
**Original list item #16**

**What:** The existing `/status` command (added in CR-048) shows model, WIP count, and budget. Extend it to also show: (a) memory_facts row count, (b) workflows row count, (c) background review daemon alive/crashed, (d) last successful background write timestamp, (e) initiative mode.

**Files:** `src/chat.py` (`_handle_status_command()`)

**Steps:**
1. In `_handle_status_command()`, add queries: `SELECT COUNT(*) FROM memory_facts`, `SELECT COUNT(*) FROM workflows`
2. Add `background_review.is_alive()` check — show "active" or "stopped"
3. Add `initiative_engine.mode.value` to the output
4. Format as a clean table using `rich.table.Table` — 2 columns (label, value)
5. Add smoke test that `/status` output contains "memory_facts" and "workflows" strings

**Test ID:** `t_status_shows_memory_and_daemon_stats`
**Risk:** Low — additive to existing `/status`; DB queries are read-only

---

### A5 — Local Model Temperature Per Routing Category
**Original list item #17**

**What:** All Ollama calls use the default temperature (0.7). Different task categories benefit from different temperatures. Code generation needs near-deterministic output (0.1); brainstorming needs variety (0.85). Add a `_CATEGORY_TEMPERATURE` dict and pass it as `options={"temperature": ...}` to each local Ollama call.

**Files:** `src/router.py` (`_route_local()`, module top)

**Steps:**
1. Add constant at module top (after imports):
   ```python
   _CATEGORY_TEMPERATURE: dict[str, float] = {
       "code_generation": 0.1,
       "file_operations": 0.15,
       "task_management": 0.3,
       "simple_qa": 0.4,
       "general": 0.55,
       "bmad_brainstorm": 0.85,
       "creative": 0.85,
   }
   _DEFAULT_TEMPERATURE: float = float(os.getenv("XCH_DEFAULT_TEMP", "0.5"))
   ```
2. Add `_load_temperatures() -> dict[str, float]`: reads `XCH_TEMP_{CATEGORY}` env vars (uppercase, underscores) and merges overrides into `_CATEGORY_TEMPERATURE`; call once at module import
3. In `_route_local()`: extract `category` from the routing decision; add `options={"temperature": _CATEGORY_TEMPERATURE.get(category, _DEFAULT_TEMPERATURE)}` to the Ollama call params
4. Log at DEBUG: `"router: temperature=%.2f for category=%s"`
5. Add smoke test: assert `_CATEGORY_TEMPERATURE["code_generation"] < _CATEGORY_TEMPERATURE["general"] < _CATEGORY_TEMPERATURE["creative"]`

**Test ID:** `t_router_temperature_ordered_by_category`
**Risk:** Low — additive `options` param; if Ollama ignores unknown options, behavior is unchanged

---

### A6 — File Context Injection Hard Cap (8 KB Total)
**Original list item #8 / Top 10 item #4**

**What:** `_resolve_file_context()` in `router.py` reads files and injects content into the system prompt with a per-file 10 KB cap but no total cap. Add an 8 KB total cap across all injected files, with truncation notice, to prevent local model context overflow.

**Files:** `src/router.py` (`_resolve_file_context()`)

**Steps:**
1. Add constant: `_FILE_CONTEXT_TOTAL_CAP: int = int(os.getenv("XCH_FILE_CONTEXT_CAP", str(8 * 1024)))`
2. In `_resolve_file_context()`, before the file reading loop, initialize `total_bytes = 0`
3. Sort candidate files by `os.path.getmtime()` descending (most recently modified first) before the loop
4. In the loop, before appending each file's content: check `total_bytes + len(content) > _FILE_CONTEXT_TOTAL_CAP`; if so, append `"\n[File context limit reached — {n} file(s) omitted]"` and break
5. Accumulate `total_bytes += len(content)` for each file appended
6. Add smoke test: call with 10 dummy 2 KB file contents; assert returned string length ≤ `_FILE_CONTEXT_TOTAL_CAP + 200` (200 bytes for the truncation notice)

**Test ID:** `t_file_context_respects_total_cap`
**Risk:** Low — only restricts injection size; no data lost from disk

---

### A7 — Per-Skill Configurable Timeout in `tool_definition()`
**Original list item #9 / Top 10 item #9**

**What:** The 30-second skill execution timeout in `_execute_skill_safe()` is hardcoded. Add an optional `"timeout_secs"` key to `tool_definition()` dicts and read it in `_execute_skill_safe()`.

**Files:** `src/chat.py` (`_execute_skill_safe()`), `src/skills/base.py` (docstring), targeted skill files

**Steps:**
1. In `_execute_skill_safe(skill, user_input, context)`: replace `_timeout = 30` with `_timeout = skill.tool_definition().get("timeout_secs", 30)`
2. In `src/skills/explorer_skill.py` `tool_definition()`: add `"timeout_secs": 120`
3. In `src/skills/bmad_skill.py` `tool_definition()`: add `"timeout_secs": 180`
4. In `src/skills/weather_skill.py` and `maps_skill.py` `tool_definition()`: add `"timeout_secs": 15`
5. In `src/skills/gmail_skill.py` `tool_definition()`: add `"timeout_secs": 20`
6. Update `base.py` docstring for `tool_definition()` to document the optional `timeout_secs` key
7. Add smoke test: mock skill with `tool_definition()` returning `{"timeout_secs": 1}`; task sleeps 2s; assert timeout fires at ~1s and returns timeout message

**Test ID:** `t_execute_skill_safe_respects_per_skill_timeout`
**Risk:** Low — `.get("timeout_secs", 30)` preserves existing behavior for all skills not yet updated

---

### A8 — Workflow Step JSON Schema Validation at Save Time
**Original list item #12**

**What:** Workflow steps are stored as `steps_json` in SQLite with no validation. If a step is missing required keys (`skill`, `description`), it fails silently at runtime. Add a validation function that checks each step dict before `upsert_workflow()` commits it to the database.

**Files:** `src/database.py` (`upsert_workflow()`), `src/workflows.py` (`save_workflow_from_session()`)

**Steps:**
1. Add `_REQUIRED_STEP_KEYS = {"skill", "description"}` constant in `database.py`
2. Add `validate_workflow_steps(steps: list) -> list[str]` in `database.py`: returns a list of error strings (empty = valid); checks each step is a dict and contains all required keys
3. In `upsert_workflow()`: call `validate_workflow_steps()`; if errors, raise `ValueError(f"Invalid workflow steps: {errors}")` before the INSERT
4. In `workflows.py` `save_workflow_from_session()`: catch the `ValueError` and return an error string to the user rather than crashing
5. Add smoke test: call `upsert_workflow()` with a step missing `"description"`; assert `ValueError` is raised with a descriptive message

**Test ID:** `t_upsert_workflow_rejects_invalid_steps`
**Risk:** Low — additive validation; existing valid workflows are unaffected

---

## PHASE B — Performance Core
*Medium effort, high impact. These directly reduce latency and improve local model reliability.*

---

### B1 — Classification Fast-Path: Skip LLM on High-Confidence Rules
**Original list item #5 / Top 10 item #1**

**What:** `router._classify()` calls the local LLM (`gemma2:2b`) on every message that isn't caught by the keyword shortlist. Extend `_fast_classify()` to return a confidence float and skip the LLM call when confidence ≥ 0.85. This eliminates the LLM classification round-trip on ~70% of turns.

**Files:** `src/router.py` (`_fast_classify()`, `_classify()`, module constants)

**Steps:**
1. Change `_fast_classify(user_input: str) -> tuple[str, float]` signature — it currently returns `(category, 1.0)` or `("", 0.0)`; keep this but expand the rule set
2. Add rule groups (in order, first match wins):
   - Input starts with `/` → `("task_management", 1.0)`
   - Input starts with `@` and rest matches `\w+` → `("skill_direct", 1.0)`
   - Input matches `/^\s*(yes|no|ok|done|thanks|bye|exit|quit)\s*$/i` → `("simple_qa", 0.95)`
   - Input length ≤ 12 chars and no special keywords → `("simple_qa", 0.88)`
   - Input matches existing `_KEYWORD_MAP` → return `(category, 0.90)` (currently returns 1.0 — keep at 1.0 for exact matches)
3. Add constant: `_FAST_CLASSIFY_THRESHOLD: float = 0.85`
4. In `_classify()`: call `_fast_classify()` first; if `confidence >= _FAST_CLASSIFY_THRESHOLD`, log debug `"router: fast-path [%s, %.2f]"` and return immediately without the LLM call
5. Track a module-level counter: `_fast_path_hits = 0` (increment on fast-path); expose in debug logging
6. Add smoke tests:
   - `/today` → assert `_fast_classify` returns `task_management` and no LLM is called
   - `@Weather` → assert `skill_direct` fast-path fires
   - `"yes"` → assert `simple_qa` fast-path fires
   - Long ambiguous sentence → assert LLM classifier IS called (fast-path returns low confidence)

**Test ID:** `t_router_fast_path_skips_llm_for_known_patterns`
**Risk:** Medium — extending the rule set can misclassify edge cases. Mitigation: keep threshold at 0.85; anything below calls the LLM as before. Add a `/debug router` command to show last classification path.

---

### B2 — ContextManager Turn-Level Cache
**Original list item #1 / Top 10 item #2**

**What:** `ContextManager` is constructed fresh on every message, running all 9 engines (git subprocess, SQLite queries, Me.md file read, vector recall). Most of this output is stable between consecutive turns. Add a turn-level cache keyed by `(session_id, history_length)` that returns the cached assembled prompt when nothing has changed.

**Files:** `src/chat.py` (`ChatSession.__init__`, `_agent_loop()`, `process_message()`), `src/context_manager.py` (optional: add cache-aware flag)

**Steps:**
1. Add to `ChatSession.__init__`:
   ```python
   self._context_cache: dict | None = None
   self._context_cache_key: tuple | None = None
   ```
2. Define cache key function `_context_cache_key(self) -> tuple`: returns `(self._session_id, len(self._history), self._last_mutating_skill or "")`
3. Add `_last_mutating_skill: str | None = None` — set to the skill class name after any skill that mutates state (Notion, tasks, workflows) completes; reset to None after cache invalidation
4. In `_agent_loop()`, before constructing `ContextManager`:
   ```python
   current_key = self._context_cache_key()
   if current_key == self._context_cache_key_stored:
       assembled_prompt = self._context_cache
   else:
       cm = ContextManager(...)
       assembled_prompt = cm.assemble_system_prompt(...)
       self._context_cache = assembled_prompt
       self._context_cache_key_stored = current_key
   ```
5. Keep `FactsEngine` (git state, time) on a separate 60-second TTL: store `_facts_last_refreshed: float` timestamp; only re-run `FactsEngine.ingest()` if > 60 seconds have passed regardless of cache hit
6. Add smoke test: send two identical messages in sequence; mock `subprocess.run` for git; assert it is called exactly once across both messages

**Test ID:** `t_context_manager_cached_across_consecutive_turns`
**Risk:** Low — cache is invalidated on every history length change. Worst case: stale git state for up to 60 seconds (acceptable). If in doubt about staleness, set `_last_mutating_skill` to force invalidation.

---

### B3 — `can_handle()` Timeout (100ms) and Per-Turn Score Cache
**Original list items #2 and #18 / Top 10 item #3**

**What:** Two related changes. (1) Wrap each `can_handle()` call in a `ThreadPoolExecutor` with a 100ms timeout; a hanging skill scores 0.0 and logs a warning. (2) Cache each skill's score for the current message hash within a turn; if the same message + skill pair is evaluated twice in the same agent loop, return the cached score.

**Files:** `src/chat.py` (agent loop skill scoring block, `ChatSession.__init__`)

**Steps:**
1. Add to `ChatSession.__init__`:
   ```python
   self._score_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="skill_score")
   self._score_cache: dict[tuple[str, int], float] = {}
   ```
   (`ThreadPoolExecutor` from `concurrent.futures` — already in stdlib)
2. Add `_score_skill(skill, user_input: str, context: dict) -> float` helper:
   - Check `self._score_cache.get((skill.__class__.__name__, hash(user_input[:200])))` — return cached if present
   - Submit `skill.can_handle(user_input, context)` to `_score_executor`
   - Call `future.result(timeout=0.1)` — on `TimeoutError`: `_timeout_log.warning("can_handle() timeout: %s", skill.__class__.__name__)`; return 0.0
   - Store result in `_score_cache` and return
3. Replace all `skill.can_handle(user_input, context)` calls in the agent loop with `self._score_skill(skill, user_input, context)`
4. Clear `_score_cache` at the start of each `_agent_loop()` call (new turn = new cache)
5. In `ChatSession` shutdown, call `_score_executor.shutdown(wait=False)`
6. Add smoke test: mock skill whose `can_handle()` sleeps 2s; confirm agent loop completes within 500ms and skill scores 0.0

**Test ID:** `t_can_handle_timeout_prevents_main_loop_block`
**Risk:** Low — `ThreadPoolExecutor.submit()` adds ~1ms overhead per skill. Cache only lives for one turn. Timeout default (0.1s) is generous for all well-behaved skills.

---

### B4 — Background Review Daemon Watchdog and Auto-Restart
**Original list item #3 / Top 10 item #5**

**What:** If the `BackgroundReview` daemon thread crashes, passive learning stops silently for the rest of the session. Add a watchdog in `_agent_loop()` that detects a dead daemon and restarts it. Emit an initiative `SYSTEM_FAILURE` signal on restart.

**Files:** `src/chat.py` (`_agent_loop()`, `ChatSession.__init__()`), `src/background_review.py` (verify `__init__` is idempotent)

**Steps:**
1. In `ChatSession.__init__`, store the factory args for reconstruction:
   ```python
   self._bg_review_args = (self._db_path, self._initiative_engine)
   ```
2. Add `_restart_background_review(self) -> None`:
   ```python
   def _restart_background_review(self) -> None:
       try:
           self._background_review = BackgroundReview(*self._bg_review_args)
           self._background_review.start()
           logger.warning("background_review: daemon restarted")
           self._initiative_engine.submit(ProactiveSignal(
               category=InitiativeCategory.SYSTEM_FAILURE,
               message="Background learning restarted after unexpected crash.",
               confidence=0.90,
               action_hint="Check logs with /debug if this repeats."
           ))
       except Exception as exc:
           logger.error("background_review: restart failed: %s", exc)
   ```
3. In `_agent_loop()`, at the top before skill scoring: `if not self._background_review.is_alive(): self._restart_background_review()`
4. Verify `BackgroundReview.__init__()` reads all state from constructor args (no module-level shared state that would conflict on re-instantiation)
5. Add smoke test: mock `is_alive()` to return False; assert `_restart_background_review()` is called and `background_review.start()` is invoked

**Test ID:** `t_background_review_watchdog_restarts_on_crash`
**Risk:** Low — watchdog only fires when daemon is dead. Re-instantiation is safe as long as `BackgroundReview.__init__` is idempotent (verify first).

---

### B5 — Persist Initiative Dismissal Counts Across Sessions
**Original list item #4 / Top 10 item #6**

**What:** `InitiativeEngine._dismissal_counts` and `_suppressed` reset on every session start. A user who dismisses "deadline" alerts three times gets them suppressed for one session, then the count resets. Persist counts to a new `initiative_state` SQLite table.

**Files:** `src/database.py` (new table + helpers), `src/initiative.py` (`__init__`, `dismiss()`), `src/chat.py` (pass `db_path`)

**Steps:**
1. In `database.py` `init_db()`, add:
   ```sql
   CREATE TABLE IF NOT EXISTS initiative_state (
       category TEXT PRIMARY KEY,
       dismissal_count INTEGER NOT NULL DEFAULT 0,
       suppressed INTEGER NOT NULL DEFAULT 0
   )
   ```
2. Add `get_initiative_state(db_path: str) -> dict[str, dict]` — returns `{category: {"count": N, "suppressed": bool}}`
3. Add `upsert_initiative_state(db_path: str, category: str, count: int, suppressed: bool) -> None` — fire-and-forget, wrapped in try/except
4. In `InitiativeEngine.__init__(self, mode, db_path: str | None = None)`: if `db_path` is provided, load state via `get_initiative_state()`; populate `_dismissal_counts` and `_suppressed`
5. In `InitiativeEngine.dismiss()`: after updating in-memory state, call `upsert_initiative_state()` in a try/except (never raises)
6. In `chat.py`, pass `db_path=self._db_path` when constructing `InitiativeEngine`
7. Add smoke test: create engine with tmp db, dismiss DEADLINE 3×, create new engine from same db path, assert `DEADLINE in engine._suppressed`

**Test ID:** `t_initiative_dismissal_survives_session_restart`
**Risk:** Low — fully backward compatible (db_path is optional). If DB write fails, in-memory state still works.

---

### B6 — Fact Confidence Decay / TTL on `memory_facts`
**Original list item #6 / Top 10 item #7**

**What:** `memory_facts` rows carry static confidence values forever. Add a decay function called at session start: multiply each row's confidence by `0.95^days_since_update`, floor at 0.3; delete rows below 0.2. Follows the existing `decay_and_prune()` pattern in `preference_learning.py`.

**Files:** `src/database.py` (new function), `src/chat.py` (`start()`)

**Steps:**
1. Verify `memory_facts` has `updated_at TEXT` column — if not, add via migration check in `init_db()`:
   ```sql
   ALTER TABLE memory_facts ADD COLUMN updated_at TEXT DEFAULT CURRENT_TIMESTAMP
   ```
   Wrap in try/except `sqlite3.OperationalError` (column already exists = OK)
2. In `background_review.py` `_write()`: ensure `updated_at = CURRENT_TIMESTAMP` is included in the `INSERT OR REPLACE` statement
3. Add `decay_memory_facts(db_path: str) -> int` in `database.py`:
   ```sql
   UPDATE memory_facts
   SET confidence = MAX(0.3, confidence * POWER(0.95, CAST((julianday('now') - julianday(COALESCE(updated_at, created_at, 'now'))) AS REAL)))
   ```
   Then: `DELETE FROM memory_facts WHERE confidence < 0.2`; return count of deleted rows
4. In `chat.py` `start()`: call `decay_memory_facts(self._db_path)` wrapped in try/except, log result at DEBUG
5. Add smoke test: insert fact with `updated_at` = 180 days ago; run `decay_memory_facts()`; assert confidence < original OR row deleted

**Test ID:** `t_memory_facts_decay_reduces_stale_confidence`
**Risk:** Low — decay is gentle (43 days to hit the floor from 1.0). Follows the exact same pattern as the existing `decay_and_prune()` function.

---

## PHASE C — Reliability
*Moderate effort. Fixes persistence and data integrity gaps.*

---

### C1 — LanceDB Re-Embed on `Me.md` / Preference Change
**Original list item #15**

**What:** When `Me.md` is updated or a preference is upserted, the old embeddings in LanceDB remain — semantic recall returns stale matches until the next embedding refresh. Add an invalidation hook: when `UserProfileEngine.ingest()` detects a changed `Me.md` (by comparing hash of file contents), trigger a background re-embedding of the user profile section.

**Files:** `src/context_manager.py` (`UserProfileEngine.ingest()`), `src/memory.py` (add `re_embed_profile()` method), `src/background_review.py` (trigger hook)

**Steps:**
1. In `UserProfileEngine.ingest()`: compute `hashlib.md5(content.encode()).hexdigest()` of the loaded Me.md content; store as `_last_profile_hash`; compare with previous call; if changed, set `self._profile_changed = True`
2. Add `MemoryEngine.re_embed_profile(profile_text: str) -> None` in `memory.py`: generates embeddings for the profile text and upserts into LanceDB `memories` table with `source="profile"` tag; wrap in try/except; run in daemon thread (non-blocking)
3. In `ContextManager.assemble_system_prompt()` (or at the end of ingest): if `_user_profile._profile_changed`, call `self._memory.re_embed_profile(profile_text)` and reset the flag
4. Similarly, in `database.py` `upsert_preference()`: after the DB write, publish an event via `events.emit("preference_changed", {...})` — background_review can subscribe and trigger re-embedding if needed
5. Add smoke test: mock `MemoryEngine.re_embed_profile()`; simulate a Me.md content change; assert `re_embed_profile` is called once

**Test ID:** `t_profile_change_triggers_reembed`
**Risk:** Medium — re-embedding runs in a daemon thread so it won't block. The LanceDB write is idempotent (upsert). Potential edge case: if the file changes twice before the first re-embed completes, the second change wins. This is acceptable.

---

### C2 — Soft-Delete Pattern for Tasks and Projects
**Original list item #14**

**What:** Deleting a task or project in `database.py` is a hard `DELETE`. Completed tasks are removed; if a workflow references a deleted task ID, it fails silently. Add `deleted_at TEXT` column to `tasks` and `projects`; filter all queries with `WHERE deleted_at IS NULL`; replace `DELETE FROM tasks` with `UPDATE tasks SET deleted_at = CURRENT_TIMESTAMP`.

**Files:** `src/database.py` (schema migration + all task/project queries)

**Steps:**
1. In `init_db()`, add migration guards:
   ```python
   for table in ("tasks", "projects"):
       try:
           conn.execute(f"ALTER TABLE {table} ADD COLUMN deleted_at TEXT")
       except sqlite3.OperationalError:
           pass  # column already exists
   ```
2. Audit every `SELECT` that touches `tasks` or `projects` — add `AND deleted_at IS NULL` to all `WHERE` clauses (or `WHERE deleted_at IS NULL` if no existing WHERE)
3. Replace every `DELETE FROM tasks WHERE ...` with `UPDATE tasks SET deleted_at = CURRENT_TIMESTAMP WHERE ...`
4. Replace every `DELETE FROM projects WHERE ...` with `UPDATE projects SET deleted_at = CURRENT_TIMESTAMP WHERE ...`
5. Add `purge_deleted(db_path: str, days_old: int = 30) -> int` — hard-deletes rows where `deleted_at < datetime('now', '-N days')`; call this from a future maintenance command
6. Add smoke test: create a task, soft-delete it, assert it doesn't appear in `get_task_queue()`; assert the row still exists in the DB with `deleted_at` set

**Test ID:** `t_soft_delete_hides_task_from_queue`
**Risk:** Medium — touches many queries in `database.py`. Must audit every SELECT. Use grep: `grep -n "FROM tasks\|FROM projects" src/database.py` to find all affected queries before editing.

---

### C3 — Multi-`<skill_call>` Parsing Per LLM Response
**Original list item #7 / Top 10 item #8**

**What:** `_parse_skill_call()` uses `re.search()` — only the first `<skill_call>` block in an LLM response is executed; subsequent blocks are silently dropped. Change to `re.findall()` and execute all calls in sequence, combining results.

**Files:** `src/chat.py` (`_parse_skill_call()`, `_agent_loop()` execution block)

**Steps:**
1. Change `_parse_skill_call(response: str) -> tuple[str, str] | None` to `_parse_skill_calls(response: str) -> list[tuple[str, str]]` using `re.findall()`
2. Return a list of `(skill_name, args_json)` tuples; empty list if no skill calls found
3. Update `_agent_loop()` execution block: iterate the list; for each call, find the skill via `_find_skill_by_name()` and call `_execute_skill_safe()`
4. Handle the approval gate: if any skill in the list requires confirmation, gate on the first such skill; append a note to the response: `"[Note: {N} additional skill calls are queued — approve this one first]"` and break
5. Combine results: `combined = "\n\n".join(f"### {name}\n{result}" for name, result in zip(names, results))`
6. Keep backward compatibility: the old `_parse_skill_call()` can remain as a wrapper that returns `_parse_skill_calls()[0]` or `None` if empty — update all callers to use the new function
7. Add smoke test: LLM response containing two `<skill_call>` blocks; assert both `execute()` methods are called and both results appear in output

**Test ID:** `t_multiple_skill_calls_all_execute`
**Risk:** Medium — changes the return type and semantics of a core parsing function. Must update all callers. Write the test first (TDD) to lock in expected behavior before changing the implementation.

---

## PHASE D — Architectural Changes
*Higher effort, higher impact. Implement these last once Phase A–C are stable.*

---

### D1 — Graceful Resource Cleanup Hook on Skill Timeout
**Original list item #10 / Top 10 item #10**

**What:** When a skill execution times out, its thread is abandoned (daemon=True, so it dies at session exit). If the skill opened a file handle, network connection, or subprocess, those resources leak until the session ends. Add an optional `cleanup()` method to the `Skill` base class; `_execute_skill_safe()` calls it after a timeout in a separate short-lived thread.

**Files:** `src/skills/base.py` (new `cleanup()` method), `src/chat.py` (`_execute_skill_safe()`), targeted skills that need cleanup (ExplorerSkill, GmailSkill)

**Steps:**
1. Add to `src/skills/base.py`:
   ```python
   def cleanup(self) -> None:
       """Called after a skill timeout. Override to release held resources."""
       pass
   ```
2. In `_execute_skill_safe()`, after the timeout branch:
   ```python
   except TimeoutError:
       cleanup_thread = threading.Thread(
           target=self._safe_cleanup, args=(skill,), daemon=True
       )
       cleanup_thread.start()
       cleanup_thread.join(timeout=5)  # 5 seconds max for cleanup
   ```
3. Add `_safe_cleanup(self, skill: Skill) -> None`: calls `skill.cleanup()` wrapped in try/except; logs any exception at WARNING
4. In `ExplorerSkill`: override `cleanup()` to cancel any in-progress `_gather()` HTTP requests (set a `_cancelled` flag that the step loop checks)
5. In `GmailSkill`: override `cleanup()` to revoke any in-progress API calls (or set a flag)
6. Add smoke test: mock skill with a `cleanup()` that sets a sentinel; trigger a timeout; assert sentinel is set within 6 seconds

**Test ID:** `t_skill_cleanup_called_after_timeout`
**Risk:** Medium — cleanup thread can itself hang; hence the 5-second `join()` limit. The base class no-op means unimplemented `cleanup()` is safe. Flag-based cancellation in ExplorerSkill requires reading its step loop carefully.

---

### D2 — Streaming for Skill-Injected Turns
**Original list item #20**

**What:** When the agent loop injects a skill into the system prompt and routes to the LLM, the response does not stream — the user waits for the full response before seeing anything. Pure LLM turns (no skill injection) already stream via `_stream_response()`. Unify the two paths so skill-injected turns also stream.

**Files:** `src/chat.py` (`_agent_loop()`, `_stream_response()`), `src/router.py` (`route_stream()`)

**Steps:**
1. Audit the current streaming path: `_stream_response()` → `router.route_stream()` → yields tokens. Confirm it handles the assembled system prompt correctly.
2. Identify why skill-injected turns don't stream — likely because the `<skill_call>` parsing logic expects a complete response string. The fix: buffer the stream and parse for `<skill_call>` patterns only after the stream completes, while still displaying tokens live.
3. Add `_stream_and_buffer(prompt, system_prompt) -> tuple[str, str]` helper: yields tokens to `console.print()` in real time; also accumulates the full response string; returns `(displayed_text, full_response)` when the stream ends
4. In the skill-injected branch of `_agent_loop()`: call `_stream_and_buffer()` instead of `router.route()` (non-streaming); after streaming completes, parse `full_response` for `<skill_call>` blocks and execute them
5. Handle the case where the skill call block itself is in the streamed output: the `<skill_call>` XML should not be displayed to the user. Options: (a) strip from displayed output, or (b) only display up to the first `<skill_call>` tag and then switch to skill output display. Approach (b) is recommended.
6. Fallback: if the model doesn't support streaming, route via the existing non-streaming path
7. Add smoke test: mock a streaming LLM response containing a `<skill_call>` block; assert tokens before the block are printed; assert the skill's `execute()` is called; assert skill result appears in final output

**Test ID:** `t_skill_injected_turns_stream_before_skill_call`
**Risk:** High — this touches the core agent loop output path and the streaming/parsing interaction. Implement last, test extensively, and keep the non-streaming path as a fallback flag (`XCH_DISABLE_SKILL_STREAMING=1`). Do not merge without manual testing of all skill types.

---

## Implementation Order

Execute in this exact sequence to minimize risk:

```
Phase A (all low risk):
  A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8
  Run smoke_test.py → confirm 186+ passed

Phase B (performance core):
  B1 → Run tests
  B2 → Run tests
  B3 → Run tests
  B4 → Run tests
  B5 → Run tests
  B6 → Run tests
  Run smoke_test.py → confirm 200+ passed

Phase C (reliability):
  C1 → Run tests
  C2 → Run tests (grep all queries before touching!)
  C3 → Run tests
  Run smoke_test.py → confirm 215+ passed

Phase D (architectural):
  D1 → Run tests
  D2 → Run tests (manual test REQUIRED before commit)
  Run smoke_test.py → confirm 225+ passed

Final:
  Update traceability matrix
  Commit: feat(orch): CR-050 performance, reliability, and local model optimization
  Push to origin/master
```

---

## SDD Checklist for This Session

Before starting code:
- [ ] Create `docs/spec/05-change-requests/CR-050-performance-reliability.md`
- [ ] Add requirement IDs (FR-PERF-001–008, NFR-PERF-012–015, FR-RELY-001–006, FR-UX-001–006) to `docs/spec/02-requirements-registry.md`

After implementation:
- [ ] All new public functions have return type annotations (NFR-DEV-002)
- [ ] No bare `except:` — always `except Exception as exc:` (NFR-DEV-003)
- [ ] Google-style docstrings on all new public methods (NFR-DEV-004)
- [ ] No raw SQL outside `database.py` (CLAUDE.md invariant)
- [ ] No `eval()`, `exec()` anywhere (NFR-DEV-006)
- [ ] All `subprocess.run()` calls use `shell=False` (NFR-DEV-006)
- [ ] Update `docs/spec/06-traceability/traceability-matrix.md` with new rows
- [ ] `python smoke_test.py` → 0 failures
- [ ] Commit with conventional commit scope
- [ ] Push to origin/master

---

## Test Count Targets

| After Phase | Expected Tests |
|---|---|
| Baseline (now) | 186 |
| After Phase A | ~196 (+10) |
| After Phase B | ~210 (+14) |
| After Phase C | ~220 (+10) |
| After Phase D | ~226 (+6) |

---

## Requirement ID Allocation

Use these IDs when writing the requirements registry entries:

| ID | Improvement |
|---|---|
| FR-PERF-001 | Classification fast-path (B1) |
| FR-PERF-002 | ContextManager turn-level cache (B2) |
| FR-PERF-003 | can_handle() timeout + score cache (B3) |
| FR-PERF-004 | File context injection cap (A6) |
| FR-PERF-005 | Per-skill configurable timeout (A7) |
| FR-PERF-006 | Temperature per routing category (A5) |
| FR-PERF-007 | Multi-skill-call parsing (C3) |
| FR-PERF-008 | Streaming for skill-injected turns (D2) |
| NFR-PERF-012 | can_handle() must complete within 100ms |
| NFR-PERF-013 | File context must not exceed 8 KB per turn |
| NFR-PERF-014 | ContextManager cache hit rate ≥ 50% of turns |
| NFR-PERF-015 | Per-skill timeout config must not break existing 30s default |
| FR-RELY-001 | Background review daemon watchdog (B4) |
| FR-RELY-002 | Initiative dismissal persistence (B5) |
| FR-RELY-003 | Fact confidence decay / TTL (B6) |
| FR-RELY-004 | Graceful resource cleanup on timeout (D1) |
| FR-RELY-005 | LanceDB re-embed on profile change (C1) |
| FR-RELY-006 | Workflow step JSON schema validation (A8) |
| FR-UX-001 | Terminal width dynamic refresh (A1) |
| FR-UX-002 | Filler opener multi-pass cleaner (A2) |
| FR-UX-003 | Brief task duration in WIP queue (A3) |
| FR-UX-004 | /status memory tier and daemon stats (A4) |
| FR-UX-005 | Soft-delete for tasks and projects (C2) |
| FR-UX-006 | Workflow step validation user feedback (A8 companion) |
