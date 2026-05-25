# TEST-ORCH-006 — Structured Observability

**Requirement**: FR-ORCH-035, FR-ORCH-036, NFR-ORCH-010, NFR-ORCH-011
**CR**: CR-021
**Status**: implemented

---

## Smoke tests (automated, `smoke_test.py`)

| Test ID | Description | Verification method | Status |
|---|---|---|---|
| `AC-CR021-001` | `ObservabilityLogger` defines `start()` and `stop()` | `smoke_test.py` — `t_obs_logger_lifecycle` | implemented |
| `AC-CR021-002` | `routing_started` payload includes `trace_id` key | `smoke_test.py` — `t_routing_started_has_trace_id` | implemented |
| `AC-CR021-003` | `llm_complete` payload includes `tokens_in` and `cost_usd` | `smoke_test.py` — `t_llm_complete_enriched_payload` | implemented |
| `AC-CR021-004` | `agent_traces` table defined in `database.py` schema | `smoke_test.py` — `t_agent_traces_table_exists` | implemented |
| `AC-CR021-005` | `on_event("llm_complete", ...)` assembles trace and calls `_write_jsonl` | `smoke_test.py` — `t_obs_on_llm_complete_writes_jsonl` | implemented |

## Notes

- NFR-ORCH-010 (JSONL 10MB rotation) is verified by source inspection of `_write_jsonl()`.
- NFR-ORCH-011 (background SQLite writes) is verified by checking that `_handle_llm_complete`
  spawns a daemon thread for `_write_db()`.
- Full content (prompt/response) is intentionally NOT logged — only token counts,
  latency, skill names, and costs are stored.
