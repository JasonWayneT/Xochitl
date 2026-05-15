# CR-006 - Web Lookup Skill (Internet Access Without Weather API)

## Status

Implemented.

## Summary

Enable Xochitl to answer live internet questions (including weather) without
integrating a dedicated weather API. This change adds a general web lookup
skill that performs public web search and summarizes fetched results.

## Affected Requirements

| ID | Type | Priority | Status | Description |
|---|---|---|---|---|
| `FR-API-003` | functional | P1 | implemented | Xochitl can perform internet lookup through a web-search skill for live, external information requests. |
| `ARCH-SDD-001` | architecture | P0 | accepted | Existing model-routing invariant preserved; web lookup is a skill/tool path, not a direct model call path. |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR006-001` | `FR-API-003` | Weather via internet | User asks for weather in a city | Xochitl routes to web lookup skill | Xochitl returns a summary from public web results without using a dedicated weather API. |
| `AC-CR006-002` | `FR-API-003` | General live lookup | User asks for current online info | Skill runs | Xochitl returns concise source-backed snippets from fetched pages. |

## Implementation Tasks

| ID | Requirement IDs | Task | Notes |
|---|---|---|---|
| `TASK-API-006` | `FR-API-003` | Add `WebLookupSkill` with web search + fetch + summarize behavior. | Implemented in `src/skills/web_lookup_skill.py`. |
| `TASK-ORCH-006` | `FR-API-003` | Register web lookup skill in built-in skill manifest. | Implemented in `src/chat.py`. |

## Verification Results

2026-05-11:
- Skill file and registration updated.
- Local runtime tests were not executed here because Python launcher is unavailable in this environment.

