# TEST-SEC-001 — SSRF Protection

**Requirement**: FR-SEC-005, NFR-SEC-003
**CR**: CR-016
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR016-001` | `validate_outbound_url("http://127.0.0.1/secret")` raises `XochitlPermissionError` | `smoke_test.py` — `test_ssrf_loopback_blocked` | implemented |
| `AC-CR016-002` | `validate_outbound_url("http://10.0.0.1/data")` raises `XochitlPermissionError` | `smoke_test.py` — `test_ssrf_private_blocked` | implemented |
| `AC-CR016-003` | `validate_outbound_url("http://169.254.169.254/latest/meta-data/")` raises `XochitlPermissionError` | `smoke_test.py` — `test_ssrf_metadata_blocked` | implemented |
| `AC-CR016-004` | `validate_outbound_url("file:///etc/passwd")` raises `XochitlPermissionError` | `smoke_test.py` — `test_ssrf_scheme_blocked` | implemented |
| `AC-CR016-005` | `validate_outbound_url("https://api.open-meteo.com/v1/forecast")` returns URL unchanged | `smoke_test.py` — `test_ssrf_public_allowed` | implemented |

## Manual verification (run once after new skill adds outbound HTTP)

| Test ID | Steps | Expected | Status |
|---|---|---|---|
| `AC-CR016-006` | Inspect `web_lookup_skill.py::_fetch_text` and `_search` — confirm `validate_outbound_url(url)` is called before `urlopen()` | Call site present; no `urlopen` without prior validation | verified |
| `AC-CR016-007` | Inspect `weather_skill.py::_fetch_json` — confirm `validate_outbound_url(url)` is called before `urlopen()` | Call site present; no `urlopen` without prior validation | verified |

## Notes

- The smoke tests for AC-CR016-001 through AC-CR016-004 use `unittest.mock` to patch
  `socket.getaddrinfo` to return the target IP directly, avoiding actual DNS resolution
  in the test harness.
- AC-CR016-005 patches `getaddrinfo` to return a known public IP (e.g., `93.184.216.34`)
  and verifies that no exception is raised.
- Any new skill module that calls `urlopen()` or `requests.get()` must call
  `validate_outbound_url()` first — add a manual verification row here and a smoke test.
- The DNS TOCTOU limitation (see ADR-002) is a known acceptance; no test covers it.
