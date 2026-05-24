# CR-017 — HTTP Retry and Per-Domain Rate Limiting

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: Resilience audit of skill HTTP call sites
**Implements**: FR-API-005, NFR-PERF-010, NFR-API-002

---

## Problem

Xochitl's skill modules make outbound HTTP calls with no resilience layer:

1. **No retry** — a transient 429, 502, or connection error immediately fails the
   skill, showing the user an error message that disappears on the next attempt.
   External APIs (DuckDuckGo, Open-Meteo) have occasional transient failures that
   would self-resolve with one retry.

2. **No rate limiting** — nothing prevents a chatty session from hammering an API
   with rapid consecutive requests, risking a sustained 429 block or account flag.

Both call sites (`WebLookupSkill`, `WeatherSkill`) call `urlopen()` directly. They
share no common HTTP layer, so any resilience fix applied to one must be copied to
the other (and to every future skill module).

---

## Solution

Introduce `src/http_utils.py` — a shared HTTP utility module that all skill modules
use instead of calling `urlopen()` directly. It provides a single entry point:

```python
fetch_bytes(url, *, headers=None, read_limit=None, timeout=8.0) -> bytes
```

**Pipeline inside `fetch_bytes`:**

1. **SSRF validation** — delegates to `security.validate_outbound_url()` (CR-016).
   Raises `XochitlPermissionError` immediately; never retried.

2. **Per-domain rate limiting** — a sliding-window token bucket (5 requests per 10
   seconds per domain). The calling thread sleeps until a slot opens; no request is
   dropped, just delayed. Thread-safe via a module-level lock.

3. **Retry with exponential backoff + jitter** — up to 3 total attempts (1 initial +
   2 retries). Retries on HTTP 429/500/502/503/504 and network-level errors
   (`URLError`, `TimeoutError`, `OSError`). Non-retryable 4xx responses propagate
   immediately. Delay formula: `base × 2^(attempt-1)` clamped to `MAX_DELAY`, with
   ±25% jitter to reduce thundering herd.

**Retry configuration:**

| Parameter | Value |
|---|---|
| Max attempts | 3 |
| Base delay | 0.5 s |
| Max delay | 4.0 s |
| Jitter | ±25% |
| Retryable statuses | 429, 500, 502, 503, 504 |

**Rate limiter configuration:**

| Parameter | Value |
|---|---|
| Capacity | 5 requests |
| Window | 10 seconds |
| Scope | Per domain (netloc) |
| Behavior when full | Block caller until slot opens |

---

## Skill changes

`WeatherSkill._fetch_json()` and `WebLookupSkill._search()` / `_fetch_text()` are
updated to call `fetch_bytes()` instead of `urlopen()` directly. The explicit
`validate_outbound_url()` calls added by CR-016 are removed from the skills — they
are now baked into `fetch_bytes()`. `Request` and `urlopen` imports are removed from
both skill files.

---

## Requirements

- **FR-API-005** — Outbound HTTP requests from skill modules must be retried on
  transient failures using exponential backoff.
- **NFR-PERF-010** — Retry backoff must use exponential delay with ±25% jitter to
  reduce thundering-herd effects during API outages.
- **NFR-API-002** — A per-domain sliding-window rate limiter must limit skill HTTP
  calls to at most 5 requests per 10-second window per domain.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR017-001` | HTTP 429 triggers a retry; `fetch_bytes` succeeds on the 3rd attempt |
| `AC-CR017-002` | HTTP 400 does not trigger a retry; exception propagates immediately |
| `AC-CR017-003` | `URLError` (connection error) triggers a retry |
| `AC-CR017-004` | After 3 failed attempts, the final exception propagates to the caller |
| `AC-CR017-005` | 6 rapid requests to the same domain — the 6th is delayed until a slot opens |
| `AC-CR017-006` | `XochitlPermissionError` (SSRF) is never retried |
| `AC-CR017-007` | `WeatherSkill._fetch_json` calls `fetch_bytes` (no direct `urlopen`) |
| `AC-CR017-008` | `WebLookupSkill._search` and `_fetch_text` call `fetch_bytes` (no direct `urlopen`) |

---

## Implementation tasks

- [x] Create `src/http_utils.py` with `fetch_bytes`, `_rate_limit_acquire`, retry loop
- [x] Update `src/skills/weather_skill.py` to use `fetch_bytes`
- [x] Update `src/skills/web_lookup_skill.py` to use `fetch_bytes`
- [x] Write `docs/spec/08-test-specs/TEST-API-002-retry.md`
- [x] Update requirements registry and traceability matrix

---

## Known limitations

- The rate limiter blocks the calling thread (the skill worker thread) rather than
  returning an error. For conversational skill calls, a brief delay is preferable to
  a hard error. If non-blocking rate limiting is needed in future, convert to a
  `try/timeout` pattern that raises after a maximum wait.
- Jitter is pseudo-random (`random.random()`); for cryptographic unpredictability,
  replace with `secrets.randbelow()`, but this level of precision is unnecessary for
  retry delays.
