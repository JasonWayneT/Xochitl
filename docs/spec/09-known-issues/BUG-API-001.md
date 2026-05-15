# BUG-API-001 - Weather Lookup Cannot Read Result Content

## Status
Resolved

## Severity
High - breaks `FR-API-003` weather lookup for a common live-information request

## Symptoms
User asks "what is the weather today in Escondido, CA" and confirms the
location. Xochitl responds:

```text
I found links, but couldn't read their content right now.
```

## Root Cause
`WebLookupSkill` searched DuckDuckGo successfully, but result URLs were
DuckDuckGo redirect links containing HTML-escaped query separators such as
`&amp;rut=...`. `_normalize_result_url()` parsed those links before
HTML-unescaping them, so the extracted `uddg` destination still included the
DuckDuckGo redirect wrapper. Fetching that malformed URL returned HTTP 400.

The fallback snippet parser was also too narrow because DuckDuckGo snippets can
appear in more than one element type. When target weather pages rejected fetches,
Xochitl had no usable result snippet to show.

## Affected Requirements
- `FR-API-003` - Xochitl can perform internet lookup through a web-search skill
- `AC-CR006-001` - Weather via internet
- `AC-CR006-002` - General live lookup

## Fix Applied
**File**: `src/skills/web_lookup_skill.py`
- HTML-unescape DuckDuckGo hrefs before parsing redirect query parameters.
- Decode absolute DuckDuckGo redirect URLs as well as relative `/l/?uddg=...`
  result URLs.
- Parse result snippets from `a`, `div`, or `span` elements so blocked target
  pages still have a search-result fallback.

## Regression Acceptance Criterion
`AC-BUG-API-001`: Given DuckDuckGo returns weather results as redirect URLs
with HTML-escaped query parameters, when the user asks for weather in a city,
then `WebLookupSkill` must normalize the result to the real destination URL and
return fetched page text or a search-result snippet instead of saying it found
links but could not read them.

## Verification
2026-05-11:
- `python smoke_test.py` passed with 25 tests, including
  `WebLookupSkill: normalizes DDG redirects and keeps snippets`.
- `python end_to_end_test.py` passed.
- `python -m py_compile src/skills/web_lookup_skill.py src/chat.py smoke_test.py`
  passed.
- Manual live check for `weather today in Escondido, CA` returned web result
  snippets and set `last_skill_success=True`.

## Related
- `CR-006` - Web Lookup Skill
- `FR-API-003` - Internet lookup for live external information
