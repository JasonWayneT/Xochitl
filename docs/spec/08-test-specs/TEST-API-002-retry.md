# TEST-API-002 — HTTP Retry and Rate Limiting

**Requirement**: FR-API-005, NFR-PERF-010, NFR-API-002
**CR**: CR-017
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR017-001` | HTTP 429 triggers retry; succeeds on 3rd attempt | `smoke_test.py` — `test_retry_429_succeeds_on_third` | implemented |
| `AC-CR017-002` | HTTP 400 does NOT trigger a retry | `smoke_test.py` — `test_no_retry_on_400` | implemented |
| `AC-CR017-003` | `URLError` triggers a retry | `smoke_test.py` — `test_retry_on_url_error` | implemented |
| `AC-CR017-004` | After 3 failed attempts the final exception propagates | `smoke_test.py` — `test_all_attempts_exhausted` | implemented |
| `AC-CR017-006` | `XochitlPermissionError` (SSRF block) is never retried | `smoke_test.py` — `test_ssrf_not_retried` | implemented |

## Manual verification (run once per new skill that makes outbound calls)

| Test ID | Steps | Expected | Status |
|---|---|---|---|
| `AC-CR017-005` | Call `http_utils._rate_limit_acquire(domain)` 6× in rapid succession with `_RL_CAPACITY=5`, `_RL_WINDOW=10` | 6th call blocks ~10 s; `time.sleep` called inside `_rate_limit_acquire` | verified by code inspection |
| `AC-CR017-007` | Inspect `weather_skill.py::_fetch_json` | `fetch_bytes(url, ...)` called; no direct `urlopen` | verified |
| `AC-CR017-008` | Inspect `web_lookup_skill.py::_search` and `_fetch_text` | `fetch_bytes(url, ...)` called; no direct `urlopen` | verified |

## Notes

- Smoke tests patch `socket.getaddrinfo` to return a public IP so SSRF validation
  passes. Tests patch `src.http_utils.urlopen` to control response behaviour.
  `time.sleep` is patched to prevent actual sleeping during CI.
- `_rate_limit_acquire` is patched out in retry tests to isolate retry logic.
- AC-CR017-005 (rate limiter blocking behaviour) is verified by code inspection rather
  than a timing-sensitive smoke test, which would be fragile in CI environments.
- Any new skill module calling `fetch_bytes` implicitly inherits retry + rate limiting;
  add a manual verification row here confirming the call site uses `fetch_bytes`.
