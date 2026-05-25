# TEST-ORCH-003 — Persona Anchoring and SOUL.md Structure

**Requirement**: FR-ORCH-028, FR-ORCH-029, NFR-ORCH-004, NFR-ORCH-005
**CR**: CR-029
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR029-001` | `SOUL.md.example` has `## [IDENTITY]` section and no "Chief of Staff" | `smoke_test.py` — `test_soul_example_structured` | implemented |
| `AC-CR029-002` | `SoulEngine.identity_anchor` is non-empty after ingest | `smoke_test.py` — `test_soul_engine_identity_anchor` | implemented |
| `AC-CR029-003` | `SoulEngine.compact(10)` preserves `[IDENTITY]` content | `smoke_test.py` — `test_soul_engine_compact_preserves_identity` | implemented |
| `AC-CR029-004` | `assemble_system_prompt()` output contains `[GOAL]` | `smoke_test.py` — `test_assemble_system_prompt_wires_template` | implemented |
| `AC-CR029-005` | `assemble_system_prompt()` output contains `[UNCERTAINTY TIERS]` | `smoke_test.py` — `test_assemble_system_prompt_wires_template` | implemented |

## Manual verification (run once after changes)

| Test ID | Steps | Expected | Status |
|---|---|---|---|
| — | Run `xochitl chat`, ask "what is your goal?" | Xochitl describes her goals aligned with `[GOAL]` section from system_xochitl.txt | pending live test |
| — | Run `xochitl chat`, ask about uncertainty | Xochitl uses TIER vocabulary — confirming `[UNCERTAINTY TIERS]` reached the model | pending live test |
| — | Remove `~/.xochitl/SOUL.md`, run `xochitl chat` | System falls back to `SOUL.md.example`; Xochitl does not introduce herself as "Chief of Staff" | pending live test |

## Notes

- `AC-CR029-004` and `AC-CR029-005` together confirm that the template wiring
  closes the gap identified in CR-029 — both the structural behavior guide and
  the CR-032 uncertainty vocabulary now reach the model.
- `SoulEngine.compact()` correctness is tested in isolation (AC-CR029-003).
  In the live path, `guard_text` is never compacted — compact() is tested here
  to ensure future correctness if the compaction policy changes.
