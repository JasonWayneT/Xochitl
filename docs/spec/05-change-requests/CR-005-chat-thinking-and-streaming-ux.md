# CR-005 - Chat Thinking and Streaming UX

## Status

Implemented (pending full runtime validation in user's installed CLI path).

## Summary

Improve chat responsiveness so the UI does not appear hung during model work.
The thinking indicator should animate continuously with a simple, stable label,
and assistant responses should render incrementally instead of arriving as one
large blob.

## Change Type

UI behavior change (terminal UX hardening).

## Affected Requirements

| ID | Type | Priority | Status | Description |
|---|---|---|---|---|
| `FR-UI-001` | functional | P1 | implemented | Live status indicator remains visually active during model/tool processing. |
| `FR-UI-004` | functional | P1 | implemented | Chat replies stream incrementally for plain-text responses, with markdown-safe fallback rendering. |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR005-001` | `FR-UI-001` | Non-hanging thinking UI | Chat is waiting on model/tool work | A turn takes more than 1 second | Flower animation continues updating with `thinking...` and a live working note; it does not appear frozen. |
| `AC-CR005-002` | `FR-UI-004` | Incremental response rendering | Assistant returns plain text | Xochitl prints the response | Output appears incrementally (chunked/streamed) rather than as one final blob. |
| `AC-CR005-003` | `FR-UI-004` | Markdown safety | Assistant returns markdown-heavy content | Xochitl prints the response | Renderer falls back to full markdown print so formatting stays intact. |

## Implementation Tasks

| ID | Requirement IDs | Task | Notes |
|---|---|---|---|
| `TASK-UI-005` | `FR-UI-001`, `AC-CR005-001` | Keep status animation alive independently of status-label changes. | Add background refresh tick in `_StatusContext`. |
| `TASK-UI-006` | `FR-UI-001` | Simplify visible status label to `thinking...` and move details into a short working note. | Avoid stuck-looking elapsed timer display. |
| `TASK-UI-007` | `FR-UI-004`, `AC-CR005-002`, `AC-CR005-003` | Add incremental response renderer with markdown fallback. | Implement `_stream_response()` and route assistant output through it. |

## Verification Results

2026-05-11:
- Code updated in `src/chat.py` for continuous status refresh and incremental output rendering.
- Runtime verification in this environment is blocked because Python launcher is unavailable (`python` and `py` not found), so local execution checks could not be run here.
- User reported seeing old behavior (`❀ Exploring project (0.2s)` and blob output), indicating their invoked `xochitl` binary likely points to a different install path than this workspace copy.

## Open Issues / Risks

- Installed CLI path mismatch may mask local code changes until the executable is re-pointed or reinstalled from this repository checkout.
