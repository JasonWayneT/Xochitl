# CR-014 - Weather Skill Geocoding Robustness

## Status

Implemented.

## Summary

Three targeted improvements to `WeatherSkill` geocoding that fix a live bug
("Tijuana Mexico" returning no location) and harden the skill against similar
failures for any query using natural-language country suffixes.

**Root cause of bug:** Open-Meteo's geocoding API expects a city name in the
`name` parameter. Submitting "Tijuana Mexico" as a single string finds nothing.
`_geocode_candidates()` only generated fallback candidates for comma-separated
inputs (e.g., "Tijuana, CA"), so space-separated "City Country" queries had no
fallback.

**Fixes applied:**

1. **Country-aware API call** — `_split_country()` (new) scans the location
   string for ~80 recognized country names/aliases and strips the country
   suffix, returning `(city_part, iso2_code)`. When a code is found, the
   geocoding URL includes `&countrycode=XX`, scoping results to the correct
   country before any ranking logic runs.

2. **Country-aware result ranking** — `_best_geocode_result()` now accepts an
   optional `country_code` argument and prefers API results whose `country_code`
   field matches before falling back to US-state matching and then `results[0]`.

3. **Proper-noun protection in `_clean_location()`** — `the` and `in` are now
   stripped only when NOT followed by a capital letter, using a negative
   lookahead (`(?!\s+[A-Z])`). This preserves place names like "The Hague" and
   "The Bronx" while still stripping framing words in "the weather in Mexico".

The existing `elif " " in cleaned` fallback in `_geocode_candidates()` (added
in the immediately preceding session) remains in place as a safety net for
country names not in `_COUNTRY_CODES`.

## Affected Requirements

| ID | Type | Priority | Status | Description |
|---|---|---|---|---|
| `BUG-API-002` | bug | P1 | resolved | WeatherSkill fails to geocode "City Country" queries (no comma) — e.g., "Tijuana Mexico". |
| `NFR-API-001` | non-functional | P1 | implemented | WeatherSkill geocoding resolves recognized country names to ISO codes, passes them as `countrycode` to Open-Meteo, and ranks results by country match before falling back to state/first-result. |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR014-001` | `BUG-API-002` | City-Country query (no comma) | User asks "what is the weather in Tijuana Mexico?" | WeatherSkill geocodes | Coordinates for Tijuana, Baja California, Mexico are resolved and current weather is returned. |
| `AC-CR014-002` | `NFR-API-001` | Country-filtered API call | User provides a location with a recognized country name | `_split_country()` identifies the country | The geocoding URL includes `countrycode=XX` scoping results to that country. |
| `AC-CR014-003` | `NFR-API-001` | Country-aware result ranking | Geocoding returns multiple cities with the same name | `_best_geocode_result()` runs with a known country code | The result whose `country_code` field matches is returned. |
| `AC-CR014-004` | `NFR-API-001` | Proper-noun location cleaning | Location string is "The Hague" | `_clean_location()` runs | "The" is preserved; the location resolves correctly. |

## Implementation Tasks

| ID | Requirement IDs | Task | Notes |
|---|---|---|---|
| `TASK-API-014` | `NFR-API-001`, `BUG-API-002` | Add `_COUNTRY_CODES` dict and `_split_country()`; update `_geocode()` to pass `countrycode`; update `_best_geocode_result()` to rank by country code; fix `_clean_location()` proper-noun guard. | Implemented in `src/skills/weather_skill.py`. |
| `TASK-TEST-014` | `NFR-API-001`, `BUG-API-002` | Add offline smoke coverage for `_split_country()` and country-filtered geocode path. | Pending — `smoke_test.py`. |

## Verification Results

2026-05-23:
- `python -m py_compile src/skills/weather_skill.py` passed.
- `python smoke_test.py` passed (existing suite unchanged).
- Manual reasoning trace confirms:
  - `_split_country("Tijuana Mexico")` → `("Tijuana", "MX")`
  - `_split_country("Escondido, CA")` → `("Escondido, CA", None)` (CA not in `_COUNTRY_CODES`)
  - `_split_country("Paris France")` → `("Paris", "FR")`
  - `_split_country("Atlanta Georgia")` → `("Atlanta Georgia", None)` ("georgia" intentionally excluded from `_COUNTRY_CODES` to prevent US-state misclassification)
  - `_clean_location("The Hague")` → `"The Hague"` (capital H protected by lookahead)
  - `_clean_location("the weather in Mexico")` → `"Mexico"` (lowercase framing words stripped)
