# CR-028 — Conversation Design A1–A5

**Status**: implemented
**Date**: 2026-05-24
**Requested by**: priority list items #20–#24 (Group 7-A)
**Implements**: FR-CONV-001, FR-CONV-002, FR-CONV-003, FR-CONV-004, FR-CONV-005, NFR-CONV-001

---

## Problem

Xochitl's interaction layer lacks five structural conversation quality patterns:

| # | Item | Gap |
|---|---|---|
| A1 (#20) | Presence cues | Responses open with sycophantic fillers ("Great question!", "Certainly!") |
| A2 (#21) | Anticipation gate | No contextual signal surfacing at session start |
| A3 (#22) | Structured brief | Daily brief is flat LLM text with no consistent section hierarchy |
| A4 (#23) | Natural memory reference | Preferences injected as raw `[global/category] value` data, not natural context |
| A5 (#24) | Uncertainty communication | No programmatic hedge utility; hedging is ad hoc per response |

---

## Solution

### New: `src/conversation.py`

**A1 — `strip_filler_opener(response: str) -> str`**

Strips sycophantic filler phrases from response openers before they reach the user.
Compiled regex covers: "Great question!", "Certainly!", "Of course!", "Absolutely!",
"Sure!", "I'd be happy to help!", etc. Applied in `XochitlChat._record()`.

**A5 — `uncertainty_hedge(confidence: float, text: str) -> str`**

Three-tier utility (mirrors `[UNCERTAINTY TIERS]` in SOUL.md):
- `confidence > 0.85` → text unchanged (direct statement)
- `0.60 ≤ confidence ≤ 0.85` → `"I think " + text`
- `confidence < 0.60` → `"I'm not certain, but " + text + " — want me to look this up?"`

### New: `src/anticipation.py`

**A2 — `AnticipationGate`**

Evaluates three signals at session start:
- `wip`: WIP queue is non-empty
- `recency`: last session was ≥ 4 hours ago
- `morning` / `evening`: time-of-day context (06–10h / 17–21h)

Fires only when **≥2 signals converge**. Returns a one-line informational
hint (e.g. "Good morning. You have 2 tasks in queue. Last session was 6h ago.
Run `xochitl today` for your priorities."). Never takes action. Called from
`_print_boot_banner()` in `chat.py`.

### New: `src/brief.py`

**A3 — `build_structured_brief(queue, notion_pending) -> str`**

Five-section brief with consistent hierarchy (each section skipped if empty):
1. **Temporal context** — day + time
2. **Schedule** — skipped (no calendar integration)
3. **Priorities** — top 3 WIP tasks
4. **Async queue** — Notion items needing decisions / overflow tasks
5. **Awareness** — one contextual nudge (last git commit age)

Max 5 lines per section. Called from the `/brief` slash command in `chat.py`.

### Updated: `src/context_manager.py` — `PreferenceEngine.assemble()`

**A4 — Natural memory reference**

Changes the preference injection format from raw structured data:
```
## User Preferences
- [global/communication] I prefer concise reports
```
To natural background context framing:
```
[BACKGROUND CONTEXT]
Apply these user preferences silently — do not cite them explicitly:
- Communication: I prefer concise reports
[/BACKGROUND CONTEXT]
```

### Updated: `src/chat.py`

- `_record()` — wraps every response through `strip_filler_opener()` (A1)
- `_print_boot_banner()` — calls `AnticipationGate.check()`, shows hint if signals converge (A2)
- `_handle_slash_command()` — `/brief` command calls `build_structured_brief()` (A3)

---

## Requirements

- **FR-CONV-001** — `strip_filler_opener()` removes sycophantic opener phrases from responses before display; applied in `_record()`.
- **FR-CONV-002** — `AnticipationGate.check()` returns an informational surfacing hint when ≥2 of (wip, recency, morning, evening) signals converge; never takes action; shown at boot banner only.
- **FR-CONV-003** — `build_structured_brief()` returns a 5-section brief (temporal, schedule, priorities, async queue, awareness); accessible via `/brief` slash command; never pushed unsolicited.
- **FR-CONV-004** — `PreferenceEngine.assemble()` frames stored preferences as natural background context ("Communication: …") with explicit instruction not to cite them, rather than raw `[scope/category]` data.
- **FR-CONV-005** — `uncertainty_hedge(confidence, text)` returns hedged text per three-tier model: > 0.85 direct, 0.60–0.85 linguistic hedge, < 0.60 explicit uncertainty + proposed resolution.
- **NFR-CONV-001** — All five functions are pure/heuristic — no LLM calls. `strip_filler_opener()` and `uncertainty_hedge()` are synchronous pure functions. `AnticipationGate.check()` reads only DB + wall clock. `build_structured_brief()` reads only DB + git.

---

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR028-001` | `strip_filler_opener()` removes known filler phrases; returns unchanged text when no filler present |
| `AC-CR028-002` | `uncertainty_hedge()` returns correct tier for each confidence bracket |
| `AC-CR028-003` | `AnticipationGate.check()` returns a hint string with ≥2 signals; `None` with < 2 |
| `AC-CR028-004` | `build_structured_brief()` returns string containing all non-empty section headers |
| `AC-CR028-005` | `PreferenceEngine.assemble()` uses natural framing — source inspection confirms `[BACKGROUND CONTEXT]` block |

---

## Implementation tasks

- [x] Write `CR-028-conversation-design.md`
- [x] Create `src/conversation.py` (A1, A5)
- [x] Create `src/anticipation.py` (A2)
- [x] Create `src/brief.py` (A3)
- [x] Update `src/context_manager.py` — `PreferenceEngine.assemble()` (A4)
- [x] Update `src/chat.py` — `_record()`, `_print_boot_banner()`, `/brief` command
- [x] Write `docs/spec/08-test-specs/TEST-CONV-001-conversation-design.md`
- [x] Update requirements registry
- [x] Update traceability matrix
- [x] Add smoke tests; run full suite

---

## Design notes

- **Anti-filler is one-pass**: only the first matching filler pattern is stripped per response. This prevents over-stripping in cases where "Sure" is used mid-sentence.
- **Anticipation gate is opt-out**: future work can add a `proactive_mode=off` preference to suppress it. For now it always fires when signals converge.
- **Brief is pull-only**: the `/brief` command must be explicitly invoked. No unsolicited session-opening brief (alert fatigue risk per planning doc).
- **Natural preference framing does not suppress the data**: all preference values are still included; only the presentation changes. The instruction "do not cite them explicitly" prevents `"I see in your preferences that..."` patterns.
- **A5 uncertainty_hedge is a utility, not an enforcer**: it is exported for skill use; it does not post-process LLM responses (that would require confidence scoring on every turn). Skill execute() methods can call it to annotate their own confidence.
