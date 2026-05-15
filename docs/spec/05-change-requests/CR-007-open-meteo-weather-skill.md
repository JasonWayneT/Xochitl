# CR-007 - Open-Meteo Weather Skill

## Status

Implemented.

## Summary

Replace weather-specific web scraping with a dedicated structured weather skill
backed by Open-Meteo. Weather requests should resolve a place name to
coordinates, call Open-Meteo forecast APIs, and return current/today conditions
without requiring an API key.

General live lookup remains covered by `WebLookupSkill`; weather should prefer
`WeatherSkill`.

## Affected Requirements

| ID | Type | Priority | Status | Description |
|---|---|---|---|---|
| `FR-API-004` | functional | P1 | implemented | Xochitl can answer weather requests through a no-key structured weather provider before falling back to generic web lookup. |
| `FR-API-003` | functional | P1 | implemented | Generic web lookup remains available for non-weather live information and fallback snippets. |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR007-001` | `FR-API-004` | Current weather | User asks for weather in a city | Xochitl routes to `WeatherSkill` | Xochitl returns current conditions, feels-like temperature, wind, humidity, precipitation, and today's high/low from Open-Meteo. |
| `AC-CR007-002` | `FR-API-004` | Location geocoding | User provides a city/state or city/country location | `WeatherSkill` runs | The skill resolves the location through Open-Meteo geocoding and uses the returned latitude/longitude for forecast lookup. |
| `AC-CR007-003` | `FR-API-004` | No API key required | Xochitl is run without weather API secrets | User asks for weather | Weather lookup succeeds without reading environment API keys. |
| `AC-CR007-004` | `FR-API-004`, `DATA-DATA-004` | Default weather location | User asks for weather without a specific location and a global weather-location preference exists | `WeatherSkill` runs | Xochitl uses the stored default geographic context before asking for clarification. |

## Implementation Tasks

| ID | Requirement IDs | Task | Notes |
|---|---|---|---|
| `TASK-API-007` | `FR-API-004`, `AC-CR007-001`, `AC-CR007-002`, `AC-CR007-003` | Add `WeatherSkill` using Open-Meteo geocoding and forecast JSON APIs. | Implemented in `src/skills/weather_skill.py`. |
| `TASK-ORCH-007` | `FR-API-004`, `FR-ORCH-005` | Register `WeatherSkill` and route weather/forecast requests to it before `WebLookupSkill`. | Implemented in `src/chat.py`. |
| `TASK-TEST-007` | `FR-API-004` | Add offline smoke coverage for Open-Meteo geocode + forecast formatting. | Implemented in `smoke_test.py`. |
| `TASK-PREF-007` | `FR-API-004`, `DATA-DATA-004`, `AC-CR007-004` | Use structured global preference memory as the default weather geography when a query omits location. | Implemented in `src/skills/weather_skill.py`; user preference stored in SQLite preferences. |

## Verification Results

2026-05-11:
- `python smoke_test.py` passed with 26 tests, including
  `WeatherSkill: Open-Meteo geocode + forecast formatting`.
- `python end_to_end_test.py` passed.
- `python -m py_compile src/skills/weather_skill.py src/skills/web_lookup_skill.py src/chat.py smoke_test.py`
  passed with bytecode writes disabled for the Windows sandbox.
- Manual live `WeatherSkill` check for `what is the weather today in
  Escondido, CA` returned structured Open-Meteo current conditions.
- Manual chat-level check through `XochitlChat.process_message(...)` returned
  structured Open-Meteo weather directly, without requiring the LLM/router path.

2026-05-11 default-location update:
- Added default weather-location preference behavior backed by the existing
  structured preferences table.
- Stored global preferences:
  - `user-home-region`: `User is in San Diego County, California.`
  - `weather-default-geography`: `San Diego, California`
- Verification passed: `smoke_test.py` (27 passed), `end_to_end_test.py` (OK),
  and `py_compile` with bytecode writes disabled.
- Manual live check for `weather today` used the stored weather default and
  returned `San Diego, California, United States`.
