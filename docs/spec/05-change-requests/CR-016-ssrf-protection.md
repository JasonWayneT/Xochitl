# CR-016 — SSRF Protection for Outbound HTTP Requests

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: Security audit of skill HTTP call sites
**Implements**: FR-SEC-005, NFR-SEC-003

---

## Problem

Xochitl's skill modules make outbound HTTP requests without validating the destination.
Two call sites are affected:

1. **`web_lookup_skill.py::_fetch_text(url)`** — fetches arbitrary URLs extracted from
   DuckDuckGo search results. A poisoned result (or a response from a compromised
   DuckDuckGo mirror) could include a URL resolving to `169.254.169.254` (AWS/GCP/Azure
   instance metadata), a private RFC 1918 address, or `localhost` — causing Xochitl to
   relay sensitive internal data to the user's terminal.

2. **`weather_skill.py::_fetch_json(url)`** — currently fetches only hardcoded
   Open-Meteo hostnames, but no runtime guard prevents a future refactor from
   introducing user-supplied or config-driven URLs without protection.

A naive hostname-string blocklist is insufficient because an attacker-controlled DNS
server can return a private IP for a public-looking hostname (DNS rebinding attack).

---

## Solution

Add `validate_outbound_url(url: str) -> str` to `src/security.py`. The validator:

1. Rejects any scheme that is not `http` or `https`.
2. Resolves the hostname to **all** IP addresses via `socket.getaddrinfo()`.
3. Checks each resolved IP against a blocklist of private and reserved ranges
   (loopback, RFC 1918, link-local / cloud metadata, carrier-grade NAT, IPv6 ULA).
4. Raises `XochitlPermissionError` if any resolved IP falls within a blocked range.
5. Returns the original URL unchanged if all checks pass.

Call sites updated:
- `WebLookupSkill._fetch_text(url)` — validate before `urlopen()`
- `WebLookupSkill._search(query)` — validate DuckDuckGo base URL (defense in depth)
- `WeatherSkill._fetch_json(url)` — validate before `urlopen()`

---

## Blocked IP ranges

| Range | Purpose |
|---|---|
| `0.0.0.0/8` | "This" network (RFC 1122) |
| `10.0.0.0/8` | RFC 1918 private |
| `100.64.0.0/10` | Carrier-grade NAT shared space (RFC 6598) |
| `127.0.0.0/8` | IPv4 loopback |
| `169.254.0.0/16` | Link-local / cloud metadata (AWS, GCP, Azure IMDS) |
| `172.16.0.0/12` | RFC 1918 private |
| `192.168.0.0/16` | RFC 1918 private |
| `198.51.100.0/24` | Documentation / TEST-NET-2 (RFC 5737) |
| `203.0.113.0/24` | Documentation / TEST-NET-3 (RFC 5737) |
| `::1/128` | IPv6 loopback |
| `fc00::/7` | IPv6 ULA (covers `fc00::/8` and `fd00::/8`) |
| `fe80::/10` | IPv6 link-local |

---

## Requirements

- **FR-SEC-005** — All outbound HTTP requests made by Xochitl skill modules must pass
  `validate_outbound_url()` before the connection is opened.
- **NFR-SEC-003** — SSRF validation must resolve hostnames to IP addresses before
  range-checking (resolve-then-validate) to prevent DNS rebinding bypass.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR016-001` | `validate_outbound_url("http://127.0.0.1/secret")` raises `XochitlPermissionError` |
| `AC-CR016-002` | `validate_outbound_url("http://10.0.0.1/data")` raises `XochitlPermissionError` |
| `AC-CR016-003` | `validate_outbound_url("http://169.254.169.254/latest/meta-data/")` raises `XochitlPermissionError` |
| `AC-CR016-004` | `validate_outbound_url("file:///etc/passwd")` raises `XochitlPermissionError` |
| `AC-CR016-005` | `validate_outbound_url("https://api.open-meteo.com/v1/forecast")` returns the URL unchanged |
| `AC-CR016-006` | `WebLookupSkill._fetch_text()` calls `validate_outbound_url()` before `urlopen()` |
| `AC-CR016-007` | `WeatherSkill._fetch_json()` calls `validate_outbound_url()` before `urlopen()` |

---

## Implementation tasks

- [x] Implement `validate_outbound_url()` in `src/security.py`
- [x] Update `src/skills/web_lookup_skill.py` (`_search`, `_fetch_text`)
- [x] Update `src/skills/weather_skill.py` (`_fetch_json`)
- [x] Write `docs/spec/08-test-specs/TEST-SEC-001-ssrf.md`
- [x] Update traceability matrix

---

## Known limitations

- DNS resolution at validation time adds ~1–5 ms per outbound fetch; acceptable for
  skill API calls which already incur network latency.
- **DNS TOCTOU**: A TTL-0 DNS record could theoretically rebind between the
  `getaddrinfo()` call and the actual `urlopen()`. This is a fundamental limitation of
  resolve-then-validate; mitigated by the millisecond window being impractical for
  passive attackers. If stricter guarantees are needed, migrate to a proxy with
  kernel-level IP filtering (track as future hardening).
