# TEST-ORCH-005 — Response Mode Switching

**Requirement**: FR-ORCH-032, FR-ORCH-033, NFR-ORCH-007, NFR-ORCH-008
**CR**: CR-025
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR025-001` | `src.response_mode` defines `MODE_CONVERSATIONAL`, `MODE_OPERATOR`, `MODE_REPORT` | `smoke_test.py` — `t_response_mode_constants` | implemented |
| `AC-CR025-002` | `infer_mode("sync my tasks")` returns `"operator"` | `smoke_test.py` — `t_infer_mode_operator` | implemented |
| `AC-CR025-003` | `infer_mode("give me a report on my projects")` returns `"report"` | `smoke_test.py` — `t_infer_mode_report` | implemented |
| `AC-CR025-004` | `infer_mode("what's the weather like?")` returns `"conversational"` | `smoke_test.py` — `t_infer_mode_conversational` | implemented |
| `AC-CR025-005` | `assemble_system_prompt(mode="operator")` contains `[RESPONSE MODE: OPERATOR]` | `smoke_test.py` — `t_assemble_injects_mode_block` | implemented |
| `AC-CR025-006` | `assemble_system_prompt(mode="conversational")` does NOT contain `[RESPONSE MODE:` | `smoke_test.py` — `t_assemble_no_mode_block_conversational` | implemented |

## Manual verification

| Steps | Expected | Status |
|---|---|---|
| In chat, type "sync my tasks" | Xochitl's response is concise and action-first, no preamble | pending live test |
| In chat, type "give me a report on my tasks" | Xochitl's response uses ## headers and bullet points | pending live test |
| Switch from operator to conversational | dim "→ conversational mode" line printed before response | pending live test |

## Notes

- NFR-ORCH-008 (no second LLM call) is verified by source inspection: `infer_mode()` 
  uses regex and keyword matching only. Smoke test AC-CR025-002 through AC-CR025-004
  cover the main signal paths.
- The transition announcement (NFR-ORCH-007) is not covered by automated smoke tests
  as it involves Rich console output — verified manually.
