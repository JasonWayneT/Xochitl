# CR-047 — Skill Reliability Hardening

| Field       | Value                                      |
|-------------|--------------------------------------------|
| CR ID       | CR-047                                     |
| Status      | Implemented                                |
| Priority    | High                                       |
| Author      | Jason / Xochitl session                    |
| Created     | 2026-05-27                                 |
| Depends on  | CR-003 (skill dispatch), CR-009 (scoring)  |
| Implements  | FR-ORCH-047, FR-ORCH-048, FR-ORCH-049, FR-ORCH-050, NFR-DEV-009 |

## Problem Statement

Skills fail to trigger on first invocation through three compounding mechanisms:

1. **Narrow keyword matching** — `can_handle()` uses pure substring matching against a
   small fixed list. Natural phrasings that aren't in the list score 0.0. The LLM never
   sees the skill schema, so it cannot invoke the skill even if it knows it exists
   (observed with GmailSkill: "check in my email inbox" scored 0.0 before a manual
   keyword fix; WeatherSkill bypasses agent loop entirely via pre-dispatch).

2. **LLM invocation suppression** — `_format_active_skill_block()` contained the line:
   *"Only invoke if the user clearly wants that action — not for planning or open-ended
   discussion."* This actively trained the LLM to withhold `<skill_call>` even when the
   skill matched. Combined with an `examples` field being absent from `tool_definition()`,
   the LLM had no concrete reference for *when* to call.

3. **No escape hatch and no observability** — When the keyword scorer missed and the LLM
   didn't call the skill, the user had no way to force routing (`@gmail check inbox`) and
   no way to see why it failed (`/debug skill`). Diagnosis required reading source code.

Root-cause audit performed 2026-05-27 — see session transcript.

## Solution

Four targeted fixes that address each failure mode independently:

| Fix | Targets | Mechanism |
|-----|---------|-----------|
| `examples` field in `tool_definition()` | LLM invocation suppression | Injects 5+ trigger phrases into the active-skill block so the LLM has concrete examples |
| Rewrite invocation instruction | LLM invocation suppression | Replace "only invoke if clearly wants" with a proactive-invocation instruction |
| `@skill_name` explicit syntax | No escape hatch | User can force skill routing by prefixing message with `@SkillName` |
| `/debug skill` command | No observability | Shows per-skill `can_handle()` scores from last turn in a scored table |

Process fix: mandatory skill-addition checklist in `AGENTS.md` prevents regressions.

## Requirements

| ID            | Description |
|---------------|-------------|
| FR-ORCH-047   | Every `tool_definition()` must include an `examples` key — a list of ≥3 verbatim user phrases that trigger the skill. `_format_active_skill_block()` injects these under "Example triggers:" so the LLM has concrete invocation reference. |
| FR-ORCH-048   | The active-skill invocation instruction replaces "Only invoke if the user clearly wants that action" with a proactive instruction: invoke when the request falls within the skill's domain without requiring exact keyword matches. |
| FR-ORCH-049   | `/debug skill` in-chat command prints a scored table of all loaded skills against the most recently processed user message, showing each skill's `can_handle()` score and whether it crossed the inject threshold. |
| FR-ORCH-050   | A user message beginning with `@SkillName` (case-insensitive) bypasses `can_handle()` scoring and routes directly to the named skill, skipping the agent loop entirely. The `@SkillName` prefix is stripped before passing to `execute()`. |
| NFR-DEV-009   | `AGENTS.md` includes a mandatory "Adding a Skill" checklist; all five steps must be satisfied before a skill PR can merge: keyword list, `examples` field, `_builtin_skills` registration, smoke test `can_handle()` assertions, and `CAPABILITIES.md` update. |

## Acceptance Criteria

| ID              | Criterion |
|-----------------|-----------|
| AC-CR047-001    | `GmailSkill().tool_definition()["examples"]` is a list of ≥ 3 strings |
| AC-CR047-002    | All 12 registered skills return a non-empty `examples` list from `tool_definition()` |
| AC-CR047-003    | `_format_active_skill_block()` output contains "Example triggers:" when `examples` is present |
| AC-CR047-004    | `_format_active_skill_block()` output does NOT contain "Only invoke if the user clearly wants" |
| AC-CR047-005    | `_format_active_skill_block()` output DOES contain "Invoke proactively" |
| AC-CR047-006    | `/debug skill` slash command returns a string containing "can_handle scores" |
| AC-CR047-007    | A message starting with `@GmailSkill check my inbox` executes `GmailSkill.execute()` without scoring |
| AC-CR047-008    | `AGENTS.md` contains a section titled "Adding a Skill" with a checklist |
| AC-CR047-009    | Smoke tests pass at ≥ 167 (no regressions) |

## Files Changed

| File | Change |
|------|--------|
| `src/skills/base.py` | Add `examples` to `tool_definition()` contract docstring |
| `src/chat.py` | Rewrite invocation instruction; add `/debug skill`; add `@skill` routing |
| `src/skills/gmail_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/weather_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/web_lookup_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/notion_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/bmad_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/sdd_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/code_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/maps_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/explorer_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/workflow_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/zettelkasten_skill.py` | Add `examples` to `tool_definition()` |
| `src/skills/orchestrator_skill.py` | Add `examples` to `tool_definition()` |
| `AGENTS.md` | Add "Adding a Skill" mandatory checklist |
| `CAPABILITIES.md` | Update skill invocation documentation |
| `docs/RELEASE_NOTES.md` | Release notes for v0.x — 2026-05-27 |
| `docs/spec/05-change-requests/CR-047-*.md` | This file |
| `docs/spec/02-requirements-registry.md` | Add FR-ORCH-047–050, NFR-DEV-009, AC-CR047-* |
| `docs/spec/06-traceability/traceability-matrix.md` | Add CR-047 rows |

## Future Work (CR-048)

- Vocabulary-driven base class: standardize `_TRIGGER_PHRASES` class attribute with default
  `can_handle()` implementation so skill authors never write scoring logic manually.
- Score logging to SQLite: persist every `can_handle()` result for analytics — after a
  week of real use, query which phrases consistently score 0.0.
- Global skills manifest always injected: inject all skill names + 1-line "when" on every
  turn (not just active-skill schema), so the LLM can route even when scoring misses.
- Near-miss threshold reduction: lower schema injection from 0.65 to 0.50 for borderline
  scores.
