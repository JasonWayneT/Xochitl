# ADR-002 — SSRF Validation: Resolve-Then-Validate vs. Naive Blocklist

**Status**: accepted
**Date**: 2026-05-24
**CR**: CR-016 (SSRF Protection)
**Deciders**: Jason Wayne (owner), Xochitl agent

---

## Context

Xochitl's skill modules (`WebLookupSkill`, `WeatherSkill`) make outbound HTTP requests
using `urllib.request.urlopen()`. No validation existed to prevent requests to private
or reserved IP ranges. We need to add a guard before implementing additional skill
modules that make outbound calls.

### The DNS rebinding problem

A naive string-based blocklist (e.g., reject URLs whose hostname looks like `127.x.x.x`
or `192.168.x.x`) is easy to bypass: an attacker controls a DNS server that returns
`public.example.com → 10.0.0.1`. The hostname string passes the blocklist, but the
connection lands on an internal host. This is a **DNS rebinding attack**.

### Options considered

**Option A — Naive hostname-string blocklist**
Check whether the URL hostname *string* matches known private-range patterns.
- Pro: simple, no DNS overhead, no socket dependency.
- Con: trivially bypassed by DNS rebinding. Provides false confidence.

**Option B — Resolve-then-validate (selected)**
Call `socket.getaddrinfo(host, None)` to resolve the hostname to all IPs, then check
each resolved IP against a set of `ipaddress.ip_network` ranges.
- Pro: defeats DNS rebinding; standard pattern for SSRF prevention in Python.
- Con: adds one DNS round-trip per fetch (~1–5 ms); `getaddrinfo` can raise on
  resolution failure (treated as blocked).
- Con: DNS TOCTOU window — a TTL-0 record could rebind between validation and the
  actual `urlopen()`. Millisecond-window attack; impractical for passive adversaries.

**Option C — Outbound proxy with kernel-level IP filtering**
Route all outbound requests through a local proxy configured to block private ranges at
the TCP layer.
- Pro: closes the DNS TOCTOU window entirely.
- Con: requires infrastructure (a running proxy process); adds operational complexity
  out of scope for a terminal-native personal AI system.

---

## Decision

**Option B — resolve-then-validate** implemented in `src/security.py` as
`validate_outbound_url(url: str) -> str`.

Rationale:
- Defeats the primary threat vector (DNS rebinding) without infrastructure dependencies.
- Python stdlib only (`socket`, `ipaddress`, `urllib.parse`) — no new dependencies.
- Fits cleanly into `security.py` alongside existing `XochitlPermissionError`
  exception, `log_decision()` audit trail, and file-operation guards.
- The DNS TOCTOU window is acknowledged in CR-016 as a known limitation and flagged
  for future hardening if stricter guarantees are required.

---

## Implementation detail

```python
_ALLOWED_SCHEMES = frozenset({"http", "https"})

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # cloud metadata (IMDS)
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

def validate_outbound_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise XochitlPermissionError(f"SSRF: scheme '{parsed.scheme}' not allowed")
    host = parsed.hostname
    if not host:
        raise XochitlPermissionError("SSRF: could not extract hostname from URL")
    try:
        results = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise XochitlPermissionError(f"SSRF: hostname resolution failed for '{host}': {e}")
    for _family, _type, _proto, _canonname, sockaddr in results:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise XochitlPermissionError(
                    f"SSRF: host '{host}' resolves to blocked IP {ip} ({network})"
                )
    return url
```

---

## Consequences

- **Positive**: DNS rebinding attacks are defeated — all resolved IPs are checked, not
  just the textual hostname.
- **Positive**: `XochitlPermissionError` integrates with the existing security module;
  callers can catch and log consistently.
- **Positive**: No new runtime dependencies.
- **Negative**: One additional DNS lookup per outbound fetch (~1–5 ms). Negligible
  compared to HTTP round-trip time.
- **Limitation**: DNS TOCTOU window. Accepted as a known limitation per CR-016.

---

## Follow-on

If Xochitl gains a web-facing layer that processes high-volume external requests, migrate
to Option C (proxy-based filtering). Track as a known limitation until that surface exists.
