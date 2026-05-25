# CR-015 — Dev Standards Update

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #1–6 (Group 1)
**Implements**: NFR-DEV-001, NFR-DEV-002, NFR-DEV-003, NFR-DEV-004, NFR-DEV-005, NFR-DEV-006

---

## Problem

`CLAUDE.md` and `AGENTS.md` define SDD process rules and architecture invariants but lack
explicit code quality standards. Six concrete standards — commit scopes, type hints, exception
handling, docstrings, testing, and security checklists — are unspecified, leading to
inconsistency across `src/` as the codebase grows.

---

## Solution

Documentation-only change: add a **Code Quality Standards** section to `CLAUDE.md` covering
all six items. Update `AGENTS.md` to add the commit scope list and scope-required rule to
the Requirement ID section. No runtime code changes.

### Items added to `CLAUDE.md`

1. **NFR-DEV-001 — Conventional Commits scope always required**
   - Closed scope list mapped to `AGENTS.md` area codes.
   - Scope required on every commit; no scope-less commits allowed.

2. **NFR-DEV-002 — Type hints on all public functions**
   - All public function signatures and return types must be annotated.
   - Treat as a hard rule on new code; audit existing code separately.

3. **NFR-DEV-003 — No bare `except:`**
   - Always `except Exception as exc:` — never `except:` or `except BaseException:`.
   - Use `raise XochitlError(…) from exc` to preserve chain.

4. **NFR-DEV-004 — Google-style docstrings on public methods**
   - Priority: skill `can_handle()`, `execute()`, `tool_definition()` interfaces.
   - Required sections: one-line summary, `Args:`, `Returns:`, `Raises:`.

5. **NFR-DEV-005 — Testing checklist**
   - Happy path covered, edge cases covered, mocks for external deps,
     tests are deterministic, test fails when logic is broken.
   - Real API calls never in unit tests.

6. **NFR-DEV-006 — Security checklist**
   - No `eval()`/`exec()`/`pickle` on user or LLM-generated input.
   - No bare resource leaks (file handles, threads, sockets).
   - Explicit `timeout=` on all outbound HTTP calls.

### Items added to `AGENTS.md`

- Commit scope list added to the Requirement ID section.
- Rule: "Every commit must include a scope from the closed list."

---

## Requirements

- **NFR-DEV-001** — All commits include a scope from the closed list (`core`, `api`, `ui`,
  `data`, `auth`, `sdd`, `orch`, `ztk`, `mem`, `skill`, `dev`); scope-less commits are
  prohibited.
- **NFR-DEV-002** — All new public function signatures include argument type hints and a
  return type annotation; `Optional[T]` or `T | None` for nullable returns.
- **NFR-DEV-003** — No bare `except:` clauses anywhere in `src/`; always
  `except Exception as exc:` or a specific exception type; always preserve the exception
  chain with `raise … from exc` or `raise … from None`.
- **NFR-DEV-004** — Public methods on skill classes, context engines, and database helpers
  carry Google-style docstrings with at minimum: one-line summary, `Args:`, `Returns:`,
  `Raises:` sections.
- **NFR-DEV-005** — Test functions cover: happy path, at least one edge case, external
  dependencies mocked, output is deterministic, and the test would fail if the logic
  under test were removed.
- **NFR-DEV-006** — No `eval()`, `exec()`, or `pickle.loads()` on user-controlled or
  LLM-generated input anywhere in `src/`; no bare resource leaks; all `urlopen()`/`httpx`
  calls carry an explicit timeout.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR015-001` | `CLAUDE.md` contains a `## Code Quality Standards` section |
| `AC-CR015-002` | `CLAUDE.md` lists all six standards with their NFR IDs |
| `AC-CR015-003` | `AGENTS.md` lists the closed commit scope list |
| `AC-CR015-004` | `AGENTS.md` states that a scope is required on every commit |

---

## Implementation tasks

- [x] Write `CR-015-dev-standards.md`
- [x] Add `## Code Quality Standards` section to `CLAUDE.md`
- [x] Add commit scope list + rule to `AGENTS.md`
- [x] Update requirements registry with NFR-DEV-001 through NFR-DEV-006
- [x] Update traceability matrix with 6 new rows

---

## Design notes

- These standards apply to new code going forward. Existing code is not retroactively
  required to be updated in this CR — a separate audit CR can track that.
- `NFR-DEV-003` intentionally excludes `except KeyboardInterrupt` and other
  `BaseException` subclasses that callers may need to handle explicitly (e.g. in
  `shutdown()` paths) — the spirit is "no silent catch-all swallowing."
- The scope `orch` covers orchestration (`context_manager.py`, `chat.py`, `router.py`,
  `background_review.py`); `ztk` covers Zettelkasten / memory engines; `skill` covers
  all files under `src/skills/`; `mem` covers `src/memory.py` and ChromaDB layer;
  `dev` covers standards, tooling, and CI changes.
