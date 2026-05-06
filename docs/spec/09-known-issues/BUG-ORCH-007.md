# BUG-ORCH-007 — BMAD + File Requests Escape to Cloud, Triggering 429 Quota Error

## Status
Resolved

## Severity
High — renders BMAD + file reading completely non-functional on free-tier API keys

## Symptoms
User asks Xochitl to "run through the bmad method" while providing a file path.
Xochitl responds with a raw 429 API error from `gemini-2.0-flash` instead of
using the local Ollama model.

```
Ay no — Error code: 429 RESOURCE_EXHAUSTED
* Quota exceeded for metric: generate_content_free_tier_requests
  model: gemini-2.0-flash
```

## Root Cause
The intent classifier correctly routed the request to `bmad_simple`, but
`bmad_simple` was in `_LOCAL_CATEGORIES` (prefers local) but **not** in
`_FORCE_LOCAL_CATEGORIES` (must stay local). When Ollama was slow to respond
or returned a non-200, `TieredRouter` automatically fell back to the configured
cloud provider (Gemini 2.0 Flash), which immediately hit the free-tier rate limit.

The distinction matters:
- `_LOCAL_CATEGORIES` → *prefer* local, *allow* cloud fallback
- `_FORCE_LOCAL_CATEGORIES` → *always* local, *never* cloud fallback

## Affected Requirements
- `NFR-PERF-001` — Local-first: all file and task operations must default to local
- `FR-ORCH-003` — PreFlight Fact Injection must not trigger cloud quota usage

## Fix Applied
**File**: `src/router.py`
- Added `"bmad_simple"` to `_FORCE_LOCAL_CATEGORIES`
- BMAD + file requests now always stay on the local Ollama model
- Cloud fallback is still available for `bmad_complex` and `bmad_party_mode`
  which genuinely benefit from larger cloud context windows

## Regression Acceptance Criterion
`AC-BUG-ORCH-007`: Given a running chat session with Ollama available, when
the user asks to run a file through the BMAD workflow, then the request must
be handled by the local model — no Gemini API call must be made and no 429
error must appear.

## Related
- `BUG-CHAT-005` — BMAD intent hijacking
- `BUG-ORCH-006` — Cloud fallback quota exhaustion
- `NFR-PERF-001` — Local-first architecture
