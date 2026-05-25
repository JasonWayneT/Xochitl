# TEST-ARCH-001 — Exception Hierarchy

**Requirement**: ARCH-ORCH-001, NFR-DEV-007, NFR-DEV-008
**CR**: CR-018
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR018-001` | `src/exceptions.py` defines all required exception classes | `smoke_test.py` — `test_exception_module_exports` | implemented |
| `AC-CR018-002` | `XochitlPermissionError is SandboxError` (backward-compat alias) | `smoke_test.py` — `test_exception_backward_compat_alias` | implemented |
| `AC-CR018-003` | `SSRFBlockedError` ⊂ `SandboxError` ⊂ `XochitlError` | `smoke_test.py` — `test_exception_hierarchy_sandbox` | implemented |
| `AC-CR018-004` | `GeocodingError` ⊂ `SkillError` ⊂ `XochitlError` | `smoke_test.py` — `test_exception_hierarchy_skill` | implemented |
| `AC-CR018-005` | `security.validate_outbound_url()` raises `SSRFBlockedError` for blocked URLs | `smoke_test.py` — `test_ssrf_raises_ssrf_blocked_error` | implemented |
| `AC-CR018-006` | `WeatherSkill._geocode()` raises `GeocodingError` for unknown location | `smoke_test.py` — `test_weather_geocode_raises_geocoding_error` | implemented |

## Notes

- AC-CR018-002 verifies that existing code catching `XochitlPermissionError` still
  catches `SandboxError` instances — no catch-sites were broken by the migration.
- AC-CR018-005 uses the existing SSRF test infrastructure (`127.0.0.1` loopback).
  The previous smoke tests caught `Exception` generically; the new test is specific
  to `SSRFBlockedError`.
- AC-CR018-006 mocks `fetch_bytes` to return an empty geocoding result, triggering
  the `GeocodingError` path in `WeatherSkill._geocode()`.
