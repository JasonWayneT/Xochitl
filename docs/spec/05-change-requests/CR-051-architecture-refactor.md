# CR-051 — Architecture Refactor: Pipeline Extraction, Typed FSM, Constants Consolidation

| Field | Value |
|---|---|
| ID | CR-051 |
| Title | Architecture Refactor: Pipeline Extraction, Typed FSM, Constants Consolidation |
| Status | implemented |
| Priority | P1 |
| Source | Post-implementation architecture review (May 2026) |
| Implements | `ARCH-ORCH-002`, `ARCH-ORCH-003`, `NFR-DEV-009`, `NFR-ORCH-018`, `NFR-ORCH-019` |
| Fixes | `BUG-ORCH-008` (governor regression introduced and resolved in this CR) |

## Summary

`chat.py` had grown to 2,526 lines, making it a god object that owned session
lifecycle, UI rendering, pipeline logic, confirmation FSMs, slash commands,
and background daemon management simultaneously.  This CR extracts the
well-defined sub-concerns into dedicated modules while preserving all existing
behaviour.  Five targeted improvements were made:

1. **SQL boundary** — Raw SQL queries (`_live_db_context`, `get_wip_count`)
   moved from `router.py` into `database.py`, enforcing the project invariant.
2. **Dead code removal** — 30 unreachable lines in `_classify_intent` deleted;
   inline `NotionSkill()` instantiations replaced with registry lookups.
3. **AgentPipeline extraction** — `_agent_loop` (~350 lines) extracted into
   `src/agent/pipeline.py`.  `AgentTurnInput` / `TurnResult` dataclasses (which
   previously existed but were unused) now have a real consumer.
4. **Confirmation FSM** — `_handle_action_confirmation` extracted into
   `src/session/confirmation.py` with a typed `PendingAction` enum replacing
   7 string literal dict keys.
5. **Slash command extraction** — `_handle_slash_command` (~250 lines) and its
   status/history helpers extracted into `src/session/slash_commands.py`.

Post-refactor fixes (also in this CR):
- **Constants consolidation** — `src/constants.py` created as the single source
  of truth for 9 constants that were duplicated across 4 files.
- **Dead method removal** — `XochitlChat._skill_call_requires_approval` deleted;
  `agent/pipeline.py` module-level function is the canonical live version.
- **Pipeline docstring** — False "stateless" claim corrected; side effects
  documented.
- **Dead stage removal** — `_apply_response_mode` pipeline stage removed (it
  returned `turn.system_prompt` unchanged — mode is assembled by `_agent_loop`
  before `pipeline.run()` is called).
- **Governor fix** — `FR-ORCH-025` enforcement restored (see `BUG-ORCH-008`).

## Requirements

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `ARCH-ORCH-002` | architecture | P1 | accepted | `AgentPipeline` in `src/agent/pipeline.py` is the sole per-turn execution boundary. It accepts `AgentTurnInput` and returns `TurnResult`. `XochitlChat._agent_loop` is a thin delegate that assembles inputs and integrates outputs back into session state. |
| `ARCH-ORCH-003` | architecture | P1 | accepted | Session-layer concerns (confirmation FSM, slash command dispatch) live in `src/session/`. These modules may not import from `src/chat.py` at runtime (only via `TYPE_CHECKING`). |
| `NFR-DEV-009` | non-functional | P1 | accepted | All shared primitive constants (`_SKILL_INJECT_THRESHOLD`, `_OPEN_ENDED_SCORE_THRESHOLD`, `_SKILL_CALL_RE`, `_ERR`, `_FYI`, `_OK`, `_CONFIRM_YES`, `_CONFIRM_NO`, `_MUTATING_SKILL_ACTIONS`, `_ALWAYS_APPROVE`) must be defined once in `src/constants.py`. No file other than `constants.py` may assign these names to literals. |
| `NFR-ORCH-018` | non-functional | P2 | accepted | `_format_active_skill_block` is intentionally duplicated in `chat.py` (test-imported canonical) and `agent/pipeline.py` (live execution). Both copies must carry a sync-reminder comment. Consolidation deferred to a future `src/skill_format.py` module. |
| `NFR-ORCH-019` | non-functional | P1 | accepted | `AgentPipeline` docstring must accurately describe its side effects: in-place mutation of `turn.context` and `turn.session_history`; possible replacement of `self._background_review`. The class must not be described as "stateless". |

## Acceptance Criteria

| ID | Requirement | Scenario | Expected | Status |
|---|---|---|---|---|
| `AC-CR051-001` | `ARCH-ORCH-002` | Construct `AgentPipeline` with mock callables, call `run(AgentTurnInput(...))` | Returns `TurnResult`; no `XochitlChat` instance needed | implemented |
| `AC-CR051-002` | `ARCH-ORCH-003` | `from src.session.confirmation import PendingAction` | Enum has exactly 7 members matching the 7 former string literals | implemented |
| `AC-CR051-003` | `NFR-DEV-009` | `grep -rn "_SKILL_INJECT_THRESHOLD\s*=" src/ \| grep -v constants.py` | Empty output (single definition only) | implemented |
| `AC-CR051-004` | `NFR-DEV-009` | `from src.chat import _SKILL_INJECT_THRESHOLD; assert _ == 0.65` | Import succeeds; value is 0.65 | implemented |
| `AC-CR051-005` | `BUG-ORCH-008` | Governor at LOCAL_ONLY tier, `_agent_loop` runs | `router.route()` receives `force_route="general"` | implemented |
| `AC-CR051-006` | `ARCH-ORCH-002` | `chat.py` line count | ≤ 1,900 lines after extraction | implemented (1,848 lines) |
| `AC-CR051-007` | `NFR-ORCH-019` | `AgentPipeline` class docstring | Contains "Side effects", "turn.context", "turn.session_history"; does not contain "Stateless" | implemented |

## Files Changed

| File | Change | Reason |
|---|---|---|
| `src/agent/pipeline.py` | Created | Extract `_agent_loop` pipeline logic (ARCH-ORCH-002) |
| `src/agent/turn.py` | Extended | Add `session_history` and `governor_force` fields to `AgentTurnInput` |
| `src/session/confirmation.py` | Created | Extract confirmation FSM with `PendingAction` enum (ARCH-ORCH-003) |
| `src/session/slash_commands.py` | Created | Extract slash command dispatch (ARCH-ORCH-003) |
| `src/session/__init__.py` | Created | Package marker |
| `src/constants.py` | Created | Single source of truth for shared constants (NFR-DEV-009) |
| `src/chat.py` | Refactored | Reduced from 2,526 to 1,848 lines; delegates to new modules |
| `src/database.py` | Extended | `get_live_context_snapshot()`, `get_wip_count()` moved from `router.py` |
| `src/router.py` | Cleaned | Removed raw SQL; delegates to `database.py` helpers |

## Known Deferred Items

| Item | Reason | Target |
|---|---|---|
| `_format_active_skill_block` duplication | Smoke test AC-CR049-006 imports from `src.chat` directly; cannot delete without test update | CR-052 or next dev-standards pass |
| `SlashContext` dataclass | ~~Decouples `session/slash_commands.py` from `XochitlChat` internals~~ **DONE** — `SlashContext` dataclass holds the session state commands need; `slash_commands.py` has no runtime `XochitlChat` dependency. `XochitlChat._build_slash_context()` constructs it; /next and /retry mutations are read back. 5 smoke tests (TASK-DEV-051-b). | Completed |

## Verification

- `python smoke_test.py` — 241 passed, 0 failed (run after each of the 8 commits in this CR).
- Follow-up (CR-052 era): dedicated smoke tests added for every acceptance
  criterion (AC-CR051-001..007), replacing source-inspection-only coverage.
  AC-CR051-003 caught a real duplicate definition of `_SKILL_INJECT_THRESHOLD`
  in `src/eval/harness.py`, since fixed to import from `src/constants.py`.
  `AgentPipeline.__init__` callable params fully type-annotated (NFR-DEV-002).
- All targeted checks pass:
  - Single definition of `_SKILL_INJECT_THRESHOLD`: confirmed via grep.
  - `from src.chat import _SKILL_INJECT_THRESHOLD` — import succeeds, value 0.65.
  - `from src.session.confirmation import PendingAction` — 7 members confirmed.
  - `hasattr(XochitlChat, '_skill_call_requires_approval')` — False (dead method removed).
  - Governor `force_route="general"` flows to router: confirmed via source inspection.
  - `AgentPipeline` docstring contains "Side effects", not "Stateless".

## Commits

| Commit | Description |
|---|---|
| `1d44b5d0` | Initial pipeline extraction, typed FSM, SQL boundary (introduced BUG-ORCH-008) |
| `b647d1d0` | Fix: restore governor force_route enforcement (resolves BUG-ORCH-008) |
| `197980cc` | Constants consolidation, dead code removal, docstring corrections |
