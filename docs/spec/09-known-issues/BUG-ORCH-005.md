# BUG-ORCH-005 — NameError: category is not defined in _route_local

## Status
**FIXED** — `src/router.py` `_route_local()` and `_route_hybrid()`

## Root Cause
A regression introduced in `BUG-ORCH-004`. I added a check for `category in _FORCE_LOCAL_CATEGORIES` within `_route_local` but didn't actually pass the `category` string into the method. This caused a crash whenever a local-first request was made.

## Fix
1. Updated `_route_local` signature to accept `category: str`.
2. Updated all calls in `route()` and `_route_hybrid()` to pass the `category` argument.
3. Restored `_route_hybrid` usage in the main routing logic to ensure specialized models (Coding/Thinking) still have cloud fallback capability while simple tasks (Files/Tasks) remain local-only.

## Regression AC
`AC-BUG-ORCH-005`: Any request using the tiered router (Local, Hybrid, or Cloud) must complete without a `NameError`. Local-first categories must correctly identify themselves to the router to trigger force-local rules.

## Date
2026-05-05
