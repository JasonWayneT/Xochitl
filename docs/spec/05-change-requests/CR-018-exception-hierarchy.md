# CR-018 — Custom Exception Hierarchy

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #10 (Group 4)
**Implements**: ARCH-ORCH-001, NFR-DEV-007, NFR-DEV-008

---

## Problem

`src/` raises bare `ValueError`, `RuntimeError`, and `Exception` at domain-level failure
points. The only custom exceptions are `XochitlPermissionError` and `RequiresConfirmation`
in `security.py`. This makes it impossible for callers and the future web/SSE layer
(FR-ORCH-020) to distinguish routing failures from skill errors from security violations
without inspecting exception messages.

---

## Solution

Create `src/exceptions.py` with a thin three-layer hierarchy and migrate key raise sites.

### Hierarchy

```
XochitlError(Exception)          — base; all Xochitl domain errors
├── RouterError                  — LLM routing / model call failures
├── SkillError                   — skill execution failures
│   └── GeocodingError           — geocoding / location resolution failures
├── ContextError                 — context assembly or persona loading failures
├── SandboxError                 — filesystem sandbox violations
│   └── SSRFBlockedError         — outbound URL blocked by SSRF guard
└── NotionError                  — Notion API integration failures
```

`XochitlPermissionError` kept as a backward-compatible alias → `SandboxError`.
`RequiresConfirmation` stays in `security.py` (control-flow, not a domain error).

### Migration scope (this CR)

| Old raise site | File | New exception |
|---|---|---|
| `XochitlPermissionError(f"SSRF: ...")` | `security.py` | `SSRFBlockedError` |
| `XochitlPermissionError(f"SSRF: scheme...")` | `security.py` | `SSRFBlockedError` |
| `XochitlPermissionError(f"SSRF: hostname...")` | `security.py` | `SSRFBlockedError` |
| `ValueError(f"no matching location found...")` | `weather_skill.py` | `GeocodingError` |
| `ValueError(f"location result...did not include coordinates")` | `weather_skill.py` | `GeocodingError` |
| `RuntimeError("NOTION_API_KEY...")` | `notion_sync.py` | `NotionError` |

Other existing `ValueError` raise sites (e.g. `config.py`, `bmad_skill.py`) are
input-validation errors that are appropriate as `ValueError` — leave them unchanged.

---

## Requirements

- **ARCH-ORCH-001** — `src/exceptions.py` defines `XochitlError` as the base exception;
  `RouterError`, `SkillError`, `GeocodingError`, `ContextError`, `SandboxError`,
  `SSRFBlockedError`, and `NotionError` form a documented hierarchy; hierarchy documented
  in module docstring with ASCII tree.
- **NFR-DEV-007** — SSRF-blocked conditions raise `SSRFBlockedError` (not bare
  `XochitlPermissionError`) so HTTP callers can distinguish SSRF blocks from other
  permission denials. `XochitlPermissionError` is kept as a backward-compatible alias
  for `SandboxError`.
- **NFR-DEV-008** — Geocoding failure in `weather_skill.py` raises `GeocodingError`
  (not `ValueError`) so callers can handle location failures separately from
  skill-level failures.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR018-001` | `src/exceptions.py` exists and defines `XochitlError`, `RouterError`, `SkillError`, `GeocodingError`, `ContextError`, `SandboxError`, `SSRFBlockedError`, `NotionError` |
| `AC-CR018-002` | `XochitlPermissionError` resolves to `SandboxError` — i.e. `XochitlPermissionError is SandboxError` |
| `AC-CR018-003` | `SSRFBlockedError` is a subclass of `SandboxError` and `SandboxError` is a subclass of `XochitlError` |
| `AC-CR018-004` | `GeocodingError` is a subclass of `SkillError` and `SkillError` is a subclass of `XochitlError` |
| `AC-CR018-005` | SSRF-blocked conditions in `security.py` raise `SSRFBlockedError` |
| `AC-CR018-006` | Location-not-found conditions in `weather_skill.py` raise `GeocodingError` |

---

## Implementation tasks

- [x] Write `CR-018-exception-hierarchy.md`
- [x] Create `src/exceptions.py`
- [x] Update `src/security.py` — import from exceptions, raise `SSRFBlockedError` for SSRF
- [x] Update `src/skills/weather_skill.py` — raise `GeocodingError` for location failures
- [x] Update `src/notion_sync.py` — raise `NotionError` for missing credentials
- [x] Write `docs/spec/08-test-specs/TEST-ARCH-001-exceptions.md`
- [x] Update requirements registry with ARCH-ORCH-001, NFR-DEV-007, NFR-DEV-008
- [x] Update traceability matrix
- [x] Add smoke tests; run full suite

---

## Design notes

- Only seven leaf types avoids the "caller exhaustion" anti-pattern (>15–20 leaves).
- `SSRFBlockedError` extends `SandboxError` (not `SkillError`) because SSRF is a
  security boundary violation, not a skill failure — callers that catch `SandboxError`
  get both path-restriction and SSRF violations, which is the right grouping.
- `RequiresConfirmation` is deliberately not in the hierarchy — it is control-flow
  (signals that a human confirm step is needed) rather than an error condition.
- The existing `http_utils.py` smoke test (`SSRF: loopback 127.0.0.1 blocked`)
  should continue to pass because the smoke test catches `Exception` generically;
  the type change to `SSRFBlockedError` is additive.
