"""Xochitl domain exception hierarchy.

Implements ARCH-ORCH-001 (CR-018).

All Xochitl domain errors extend XochitlError so callers can catch at the
right level without inspecting exception messages.

Hierarchy::

    XochitlError(Exception)          — base; all Xochitl domain errors
    ├── RouterError                  — LLM routing / model call failures
    ├── SkillError                   — skill execution failures
    │   └── GeocodingError           — geocoding / location resolution failures
    ├── ContextError                 — context assembly or persona loading failures
    ├── SandboxError                 — filesystem sandbox / security violations
    │   └── SSRFBlockedError         — outbound URL blocked by SSRF guard
    └── NotionError                  — Notion API integration failures

Usage::

    from src.exceptions import GeocodingError, SSRFBlockedError

    raise GeocodingError(f"no matching location found for {location!r}")
    raise SSRFBlockedError(f"SSRF: host resolves to blocked address {ip}")

Backward compatibility:
    XochitlPermissionError is an alias for SandboxError so existing catch-sites
    that reference XochitlPermissionError continue to work unchanged.
"""

from __future__ import annotations

__all__ = [
    "XochitlError",
    "RouterError",
    "SkillError",
    "GeocodingError",
    "ContextError",
    "SandboxError",
    "SSRFBlockedError",
    "NotionError",
    # backward-compat alias
    "XochitlPermissionError",
]


class XochitlError(Exception):
    """Base class for all Xochitl domain exceptions.

    Catching XochitlError covers all domain-level failures while allowing
    lower-level exceptions (KeyboardInterrupt, MemoryError) to propagate.
    """


class RouterError(XochitlError):
    """LLM routing or model call failure.

    Raised when the TieredRouter cannot complete a model call — e.g. the
    local model is unavailable, a cloud API returns a permanent error, or
    the routing logic rejects a request.
    """


class SkillError(XochitlError):
    """Skill execution failure.

    Raised by skill classes when they cannot fulfil a request — e.g. a
    required external service is unreachable or the skill receives invalid
    input that it cannot process.
    """


class GeocodingError(SkillError):
    """Geocoding or location-resolution failure.

    Raised by WeatherSkill (and any future location-aware skill) when a
    location string cannot be resolved to coordinates, or when the geocoding
    API returns an unexpected response.
    """


class ContextError(XochitlError):
    """Context assembly or persona-loading failure.

    Raised by ContextManager and related engines when a critical component
    of the system prompt cannot be assembled — e.g. a required template
    placeholder is missing or SOUL.md cannot be parsed.
    """


class SandboxError(XochitlError):
    """Filesystem sandbox or security-policy violation.

    Raised when an operation is rejected by the security layer — e.g.
    a path outside the allowed roots is accessed, or an outbound URL is
    blocked by the SSRF guard (see SSRFBlockedError).
    """


class SSRFBlockedError(SandboxError):
    """Outbound URL blocked by the SSRF guard.

    Subclass of SandboxError so callers that catch SandboxError get both
    path-restriction and SSRF violations, while callers that need to
    distinguish the two can catch SSRFBlockedError specifically.

    Raised by security.validate_outbound_url() when the destination IP
    resolves to a private, loopback, or cloud-metadata address.
    """


class NotionError(XochitlError):
    """Notion API integration failure.

    Raised when a Notion API call fails due to missing credentials, an
    API-level error, or an unexpected response structure.
    """


# ── Backward-compatible alias ────────────────────────────────────────────────
# XochitlPermissionError was defined in security.py before CR-018.
# Keep it as an alias so existing catch-sites are not broken.
XochitlPermissionError = SandboxError
