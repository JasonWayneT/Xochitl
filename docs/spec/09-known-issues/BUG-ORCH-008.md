# BUG-ORCH-008 — Governor force_route Enforcement Dropped During Pipeline Extraction

## Status
Resolved

## Severity
High — session budget enforcement silently non-functional; cloud routing could
continue past the LOCAL_ONLY and HARD_STOP token-budget thresholds, incurring
unexpected API cost with no routing restriction applied.

## Introduced In
Commit `1d44b5d0` — "refactor(orch): architecture refactor — pipeline extraction,
typed FSM, SQL boundary"

## Fixed In
Commit `b647d1d0` — "fix(orch): restore governor force_route enforcement in
AgentPipeline"

## Symptoms
Session budget warnings appeared in the terminal (the `start()` loop still
checked the governor tier and printed yellow warning text), but the actual
routing constraint — forcing `force_route="general"` for LOCAL_ONLY and
HARD_STOP tiers — was never applied to the LLM call.  Cloud requests continued
silently past the token budget thresholds.

## Root Cause

The original `_agent_loop` contained:

```python
force = "code_generation" if self.force_cloud else None
if force is None:
    _gov_force = self._governor.force_route()
    if _gov_force:
        force = _gov_force
```

When `_agent_loop` was refactored to delegate to `AgentPipeline.run()`, the
pipeline reproduced the first line but not the governor override:

```python
# pipeline.py Stage 5 — after refactor, MISSING governor logic:
force = "code_generation" if turn.force_cloud else None
```

`SessionGovernor.force_route()` was never called inside the pipeline.
`self._governor` was not passed into `AgentPipeline` (by design — the pipeline
avoids a full session reference), so the governor's routing constraint was
unreachable from within the pipeline.

The `start()` loop continued to call `self._governor.tier()` and print warning
banners, giving the appearance of budget enforcement while the actual routing
was unconstrained.

## Affected Requirements
- `FR-ORCH-025` — Tiered routing based on session token budget; LOCAL_ONLY and
  HARD_STOP must block cloud routing

## Fix Applied

**Files changed**: `src/agent/turn.py`, `src/agent/pipeline.py`, `src/chat.py`

1. Added `governor_force: str | None = None` field to `AgentTurnInput`
   (defaulting to `None` so all existing call sites remain valid).
2. In `_agent_loop`, compute `_gov_force = self._governor.force_route() if not
   force_cloud else None` before building the turn, and pass it as
   `governor_force=_gov_force`.
3. In `pipeline.run()` Stage 5, apply it:
   `force = "code_generation" if turn.force_cloud else (turn.governor_force or None)`

`force_cloud=True` continues to take priority over the governor (cloud flag
always wins).  `governor.force_route()` returns `"general"` for LOCAL_ONLY and
HARD_STOP, and `None` for FULL and PREFER_LOCAL.

## Regression Acceptance Criterion

`AC-BUG-ORCH-008`: Given a session where `SessionGovernor.force_route()` returns
`"general"` (LOCAL_ONLY or HARD_STOP tier), when `XochitlChat._agent_loop` runs,
then `router.route()` must receive `force_route="general"`, and no cloud LLM call
must be made for that turn.

## Verification
- `python smoke_test.py` — 241/241 pass after fix.
- Governor smoke tests AC-CR026-001 through AC-CR026-005 continue to pass.
- Source inspection: `_gov_force` computed in `_agent_loop`; `governor_force`
  field present in `AgentTurnInput`; pipeline Stage 5 applies it.

## Related
- `FR-ORCH-025` — Tiered routing (CR-026, ADR-004)
- `CR-026` — Original governor implementation
- `CR-051` — Architecture refactor that introduced this regression
