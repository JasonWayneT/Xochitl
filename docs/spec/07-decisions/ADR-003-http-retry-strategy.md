# ADR-003 — HTTP Retry Strategy: Exponential Backoff vs Fixed Delay

**Status**: accepted
**Date**: 2026-05-24
**CR**: CR-017 (HTTP Retry and Rate Limiting)
**Deciders**: Jason Wayne (owner), Xochitl agent

---

## Context

Xochitl's skill modules (`WebLookupSkill`, `WeatherSkill`) call external APIs that
occasionally return transient errors (429 rate-limited, 502 gateway timeout). The
existing code performs no retry — a single transient failure surfaces as a user-facing
error message even though the next request would likely succeed.

We also need a rate limiter to avoid hammering external APIs during rapid conversational
turns, and a centralized HTTP layer so resilience logic is not duplicated per skill.

### Sub-decision A — retry delay strategy

**Option 1 — No retry (current state)**
Fail immediately on any error.
- Pro: simple; predictable latency.
- Con: transient API glitches create unnecessary user-visible errors.

**Option 2 — Fixed delay retry**
Wait a constant N seconds between attempts.
- Pro: simple.
- Con: N is a guess; may be too short (still rate-limited) or too long (bad UX
  during actual fast recovery).

**Option 3 — Exponential backoff + jitter (selected)**
Wait `base × 2^attempt` seconds, clamped to a max, with ±25% random jitter.
- Pro: adapts to API recovery time; jitter prevents thundering-herd when many
  clients retry simultaneously; widely used pattern (AWS SDK, Google Cloud, etc.).- Con: slightly more complex; max 3 attempts adds at most ~4.5 s latency in the
  worst case (0.5 s + 1 s + 2 s + jitter), which is acceptable for skill calls.

### Sub-decision B — rate limiter algorithm

**Option 1 — Fixed window counter**
Count requests in fixed N-second buckets (e.g., reset every 10 s).
- Pro: simple O(1) state per domain.
- Con: burst possible at window boundary (up to 2× capacity across two adjacent
  windows); request clustering at reset point.

**Option 2 — Sliding window token bucket (selected)**
Keep a deque of recent request timestamps; evict timestamps older than the window.
- Pro: smooth request distribution; no boundary burst; O(capacity) memory per domain.
- Con: slightly more logic; deque iteration on each call.

**Option 3 — Leaky bucket**
Tokens drip in at a fixed rate; excess requests are queued.
- Pro: very smooth output rate.
- Con: harder to implement correctly; overkill for low-volume skill calls.

---

## Decision

**Exponential backoff + jitter** (Sub-decision A Option 3) with a
**sliding-window token bucket** (Sub-decision B Option 2), implemented in a shared
`src/http_utils.py` module.

Rationale:
- Exponential backoff matches well-established best practice for REST API retry.
- Jitter prevents the thundering-herd effect that fixed delay cannot avoid.
- Sliding window is clean and correct without the boundary-burst problem of fixed windows.
- Centralising in `http_utils.py` prevents duplication and ensures every current and
  future skill benefits from the same resilience layer.
- Max 3 attempts cap (adds at most ~4.5 s) stays within acceptable UX latency for
  an interactive chat session where the user already expects some wait time for skill
  calls.

---

## Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Max attempts | 3 | Balances retry coverage against latency; beyond 3, transient errors are likely persistent |
| Base delay | 0.5 s | Fast enough for quick recovery; noticeable but not annoying |
| Max delay | 4.0 s | Cap avoids unacceptably long waits |
| Jitter | ±25% | Sufficient spread to avoid clustering; not so large as to waste time |
| Retryable statuses | 429, 500, 502, 503, 504 | Clearly transient; 4xx (except 429) indicate client errors not worth retrying |
| Rate capacity | 5 req | Generous enough for normal chat patterns; tight enough to prevent runaway loops |
| Rate window | 10 s | Matches typical API rate-limit granularity |

---

## Consequences

- **Positive**: Transient API failures become invisible to the user in most cases.
- **Positive**: Rate limiting protects both the external API and Xochitl's session
  from runaway request loops.
- **Positive**: Single `fetch_bytes()` entry point; future skills automatically inherit
  resilience.
- **Negative**: In the pathological case (3 × 429), latency increases by up to ~4.5 s.
- **Negative**: Rate limiter blocks the skill worker thread. For 5+ rapid requests to
  the same domain, earlier skill calls may hold the thread for up to 10 s.

---

## Follow-on

If skill calls move to async I/O in future, migrate `_rate_limit_acquire` to an
`asyncio.Semaphore` / `asyncio.sleep` pattern and the retry loop to `async`/`await`.
Track as a known limitation until async I/O is introduced.
