# CR-021 — Structured Observability

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list item #13 (Group 5)
**Implements**: FR-ORCH-035, FR-ORCH-036, NFR-ORCH-010, NFR-ORCH-011

---

## Problem

`src/events.py` emits structured events (`routing_started`, `skill_matched`,
`llm_complete`, etc.) but nothing consumes them into persistent, queryable records.
`routing_started` carries no `trace_id`, so multi-step turns cannot be correlated.
`llm_complete` omits `tokens_in` and `cost_usd`. Without structured traces there
is no basis for:
- Debugging regressions after model upgrades (which turns degraded?)
- Uncertainty calibration against accuracy (how well does confidence correlate?)
- Skill selection accuracy measurement (eval harness, CR-022)
- Governor audit logging (which policy triggered, at what cost?)

---

## Solution

### New: `src/observability.py`

`ObservabilityLogger` subscribes to the event bus and assembles a `_TurnTrace`
dataclass across the lifecycle of each turn:

| Event | Action |
|---|---|
| `routing_started` | Extract `trace_id`, record `started_at` |
| `skill_matched` | Record `top_skill`, `top_score` |
| `skill_started` | Record tool call start time |
| `skill_complete` | Record tool call duration and success |
| `llm_complete` | Record `route`, `tokens_in`, `tokens_out`, `cost_usd`, compute `latency_ms` |

On `llm_complete`, the assembled trace is:
1. Appended to a JSONL ring buffer at `~/.xochitl/agent_traces.jsonl`
   (capped at 10MB — rotated to `.jsonl.bak` when exceeded)
2. Inserted into the `agent_traces` SQLite table in a background thread

JSONL record format (aligned with OTel GenAI Semantic Conventions 2025):
```json
{
  "trace_id": "abc123def456",
  "ts": "2026-05-24T10:00:00.123456+00:00",
  "gen_ai.system": "xochitl",
  "gen_ai.request.model": "<route>",
  "gen_ai.usage.prompt_tokens": 1200,
  "gen_ai.usage.completion_tokens": 87,
  "cost_usd": 0.0002,
  "latency_ms": 1234,
  "top_skill": "WeatherSkill",
  "top_score": 0.82,
  "tool_calls": [{"name": "weather", "success": true, "duration_ms": 340}],
  "failure_reason": null
}
```

### Updated: `src/database.py`

New `agent_traces` table (lightweight — optimised for append + recent-N queries):
```sql
CREATE TABLE IF NOT EXISTS agent_traces (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id     TEXT NOT NULL,
    ts           TEXT NOT NULL,
    route        TEXT,
    tokens_in    INTEGER DEFAULT 0,
    tokens_out   INTEGER DEFAULT 0,
    cost_usd     REAL DEFAULT 0.0,
    latency_ms   INTEGER DEFAULT 0,
    top_skill    TEXT,
    top_score    REAL DEFAULT 0.0,
    tool_calls   TEXT,          -- JSON array
    failure_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_traces_ts ON agent_traces(ts DESC);
```

New helper: `insert_agent_trace(conn, trace: dict) -> int`.

### Updated: `src/chat.py`

- `XochitlChat.__init__()` — instantiate and start `ObservabilityLogger()`
- `_agent_loop()` before `routing_started` emit — generate `trace_id` and include
  it in the payload; also add `tokens_in` and `cost_usd` to `llm_complete` payloads.

---

## Requirements

- **FR-ORCH-035** — `ObservabilityLogger` subscribes to the event bus; on each
  `routing_started`/`llm_complete`/`skill_*` event sequence it assembles and
  persists a structured trace record to JSONL + SQLite (`agent_traces` table).
- **FR-ORCH-036** — `routing_started` payload includes a `trace_id` (12-char hex);
  `llm_complete` payload includes `tokens_in` and `cost_usd` in addition to the
  existing `route` and `tokens_out` fields.
- **NFR-ORCH-010** — JSONL ring buffer capped at 10MB; when exceeded, the current
  file is renamed to `agent_traces.jsonl.bak` and a new file is started.
- **NFR-ORCH-011** — SQLite writes happen in a background thread so the main chat
  loop is never blocked by observability I/O; JSONL writes are synchronous but
  append-only (fast) and wrapped in try/except.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR021-001` | `src/observability.py` defines `ObservabilityLogger` with `start()` / `stop()` |
| `AC-CR021-002` | `routing_started` payload includes `trace_id` |
| `AC-CR021-003` | `llm_complete` payload includes `tokens_in` and `cost_usd` |
| `AC-CR021-004` | `agent_traces` table exists in `database.py` schema |
| `AC-CR021-005` | `ObservabilityLogger.on_event("llm_complete", ...)` writes a JSONL entry |

---

## Implementation tasks

- [x] Write `CR-021-observability.md`
- [x] Create `src/observability.py`
- [x] Update `src/database.py` — `agent_traces` table + `insert_agent_trace()`
- [x] Update `src/chat.py` — `trace_id` in `routing_started`, enriched `llm_complete`
- [x] Write `docs/spec/08-test-specs/TEST-ORCH-006-observability.md`
- [x] Update requirements registry
- [x] Update traceability matrix
- [x] Add smoke tests; run full suite

---

## Design notes

- Full prompt/response content is NOT logged (PII risk). Only token counts, latencies,
  skill names, and costs are recorded.
- The JSONL file path is `~/.xochitl/agent_traces.jsonl` (same directory as the
  decision log from FR-SEC-003). JSONL is chosen over SQLite-only because it can be
  streamed, grepped, and shipped to any OTel backend without schema migration.
- Background thread for SQLite writes uses `threading.Thread(daemon=True)` — same
  pattern as `BackgroundReview`. A daemon thread means no session teardown is needed.
- `trace_id` is `secrets.token_hex(6)` (12 hex chars) — short enough for log lines,
  long enough to be unique across a typical session. Full UUID is overkill.
