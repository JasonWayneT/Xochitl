# CR-045 — Google Maps Skill

| Field       | Value                        |
|-------------|------------------------------|
| CR ID       | CR-045                       |
| Status      | Implemented                  |
| Priority    | Medium                       |
| Author      | Jason / Xochitl session      |
| Created     | 2026-05-25                   |
| Implements  | FR-MAPS-001, FR-MAPS-002     |

## Problem Statement

Xochitl has no awareness of physical space. She cannot answer "how do I get to X",
"how long is the drive", or "find me a coffee shop nearby" — all common daily-use
queries for a JARVIS-style assistant. Google Maps provides reliable data for all of
these via REST APIs with a free-tier API key.

## Solution

Add `src/skills/maps_skill.py` backed by two Google Maps APIs:

- **Directions API** — route, distance, step-by-step instructions, travel time
- **Places Text Search API** — find nearby businesses by category or name

The skill registers alongside existing builtins in `chat.py`. A public utility
function `get_travel_time()` is exported for future use by `calendar_skill.py`
so it can prompt "leave by X for your 3 pm meeting."

## Requirements

| ID           | Description                                                        |
|--------------|--------------------------------------------------------------------|
| FR-MAPS-001  | Xochitl shall return directions and travel time between two points |
| FR-MAPS-002  | Xochitl shall return a list of nearby places matching a search term |
| FR-MAPS-003  | Skill shall use the user's saved home location when origin/location is omitted |
| FR-MAPS-004  | API key shall be read from secrets store (GOOGLE_MAPS_API_KEY)     |
| NFR-MAPS-001 | All Maps HTTP calls shall use `http_utils.fetch_bytes` (retry + SSRF guard) |

## Acceptance Criteria

| ID             | Criterion                                                            |
|----------------|----------------------------------------------------------------------|
| AC-CR045-001   | `can_handle("directions to the library")` returns ≥ 0.90            |
| AC-CR045-002   | `can_handle("find a coffee shop near me")` returns ≥ 0.90           |
| AC-CR045-003   | `can_handle("what is the weather")` returns 0.0                     |
| AC-CR045-004   | `_extract_destination("directions to downtown San Diego")` returns `"downtown San Diego"` |
| AC-CR045-005   | `_format_directions()` includes distance, duration, and step count  |
| AC-CR045-006   | `_format_places()` includes name, address, and rating               |
| AC-CR045-007   | Missing API key returns a clear setup instruction, not an exception  |

## Files Changed

| File                              | Change                              |
|-----------------------------------|-------------------------------------|
| `src/skills/maps_skill.py`        | New — MapsSkill + get_travel_time() |
| `src/chat.py`                     | Register MapsSkill in builtin list  |
| `smoke_test.py`                   | 7 new AC tests                      |

## API Keys Required

| Secret              | Where to get it                                    |
|---------------------|----------------------------------------------------|
| GOOGLE_MAPS_API_KEY | Google Cloud Console → APIs & Services → Credentials |

Enable in Google Cloud Console: Directions API, Places API, Geocoding API.

## Future Work

- `calendar_skill.py` will call `get_travel_time()` to surface "leave by" reminders
- Nearby search radius control via user preference
- Favourite locations (home, work) auto-populated from preferences
