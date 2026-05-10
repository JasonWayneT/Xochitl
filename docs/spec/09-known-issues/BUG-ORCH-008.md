# BUG-ORCH-008 — Double SYSTEM_FACTS Injection

## Status
Resolved

## Severity
Medium — every CM-assembled prompt received the `[SYSTEM_FACTS]` block twice, inflating token usage and causing the LLM to see duplicate environment context on every turn.

## Symptoms
System prompts assembled by `ContextManager.assemble_system_prompt()` already contained a `[SYSTEM_FACTS]` block from `FactsEngine`. When passed to `TieredRouter.route()`, the router unconditionally prepended a second `[SYSTEM_FACTS]` block via `_build_preflight_facts()`. The LLM received identical CWD, project, and platform facts twice in every system prompt.

## Root Cause
`FR-ORCH-003` was implemented in two places independently:

1. `src/context_manager.py` — `FactsEngine.assemble()` builds `[SYSTEM_FACTS]` and includes it in every call to `cm.assemble_system_prompt()`.
2. `src/router.py` — `TieredRouter.route()` unconditionally prepends `_build_preflight_facts()` to whatever system prompt it receives (line 456–457).

Before CR-003 the CM didn't exist, so the router's injection was the only copy. After CR-003 introduced universal CM usage, every CM-routed call started producing two copies.

## Affected Requirements
- `FR-ORCH-003` — PreFlight Fact Injection (implementation conflict between two modules)
- `NFR-PERF-004` — Token budget enforcement (wasted tokens on duplicate facts)

## Fix Applied
**File**: `src/router.py`

Added a guard so `_build_preflight_facts()` only runs when `[SYSTEM_FACTS]` is not already present in the incoming system prompt:

```python
# Before
facts_block = _build_preflight_facts()
system_prompt = facts_block + "\n\n" + system_prompt

# After
if "[SYSTEM_FACTS]" not in system_prompt:
    facts_block = _build_preflight_facts()
    system_prompt = facts_block + "\n\n" + system_prompt
```

This preserves correct behavior for any caller that does not use the CM (they still get facts injected) while avoiding the duplicate for CM-assembled prompts.

## Regression Acceptance Criterion
`AC-BUG-ORCH-008`: Given a chat session using the universal ContextManager, when any `_handle_*` path calls `router.route()` with a CM-assembled system prompt, then the resulting system prompt must contain exactly one `[SYSTEM_FACTS]` block.
