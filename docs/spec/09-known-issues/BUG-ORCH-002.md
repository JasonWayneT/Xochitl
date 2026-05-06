# BUG-ORCH-002 — Hallucination: LLM role-playing agent actions instead of executing them

## Status
**FIXED** — `src/chat.py` `_check_skills()` + `_handle_action_confirmation()`

## Root Cause
1. **Disconnected Skills**: `_check_skills` returned a suggestion string (e.g., "Want to start?") but did not set `pending_action` in the context. Consequently, when the user said "yes", the system didn't know it was supposed to call `init_project`.
2. **LLM Fill-in**: Because the system didn't handle the "yes" with code, it fell through to `_general_conversation`. The LLM saw the history where it had just asked "Want to start?", assumed it was an agent that *could* initialize projects, and began role-playing the initialization (e.g., "Scanning directory...", "Created project!").
3. **Missing Context**: Because it was just role-playing, it didn't have the actual file content (even after the `BUG-ORCH-001` fix, because role-playing a project setup is a complex task that needs specific seeding). It defaulted to generic knowledge (hallucinating "Zettle" as a payment app).

## Fix
1. **Confirmation Linkage**: `_check_skills` now explicitly sets `pending_action = "init_project"` and metadata (name, id) when the BMAD skill makes a suggestion.
2. **Automated Seeding**: `_handle_action_confirmation` for `init_project` now reads the spec file from history, calls the LLM to draft the first BMAD artifact (`business-model.md`), and saves it. This forces the system to use the *real* content immediately.

## Regression AC
`AC-BUG-ORCH-002`: When a user confirms a new project initialization, Xochitl must execute the actual `mkdir` and `save_artifact` logic. It must return a real summary of the provided spec, not a generic "Payment Service" hallucination.

## Date
2026-05-05
