# BUG-CHAT-005 — BMAD Intent Hijacking by NotionSkill / task_management

## Status
Resolved

## Severity
High — renders BMAD workflow completely inaccessible via natural language

## Symptoms
User says "I want to run it through the bmad method" and Xochitl responds with
a Notion sync prompt instead of launching the BMAD workflow.

## Root Cause
Two concurrent problems:

1. **Missing BMAD fast-path**: `_fast_classify()` in `router.py` had no keyword
   rule for `bmad` or `sdd`. The fast classifier returned `None`, so the query
   fell through to the LLM classifier. The LLM returned `task_management` because
   the phrase "run it through" pattern-matched task scheduling intent.

2. **NotionSkill over-broad keywords**: `NotionSkill.can_handle()` matched on
   the word `"projects"` (a very common word), which scored 0.7 and intercepted
   the intent before any BMAD skill could respond.

## Affected Requirements
- `FR-ORCH-001` — Intent classification must route to the correct handler
- `FR-SDD-001` — BMAD skill must be reachable via natural language

## Fix Applied
**File**: `src/router.py`
- Added top-priority BMAD regex check in `_fast_classify()` before the keyword loop:
  `re.search(r'\bbmad\b|\bsdd\b|spec.driven|run.*through.*bmad|bmad.*method', q)`
- Added `bmad_simple`, `bmad_complex`, `bmad_party_mode` entries to `_KEYWORD_MAP`
- Removed `"project"` from `task_management` keyword list (too generic)

**File**: `src/skills/notion_skill.py`
- Replaced broad keyword list with explicit Notion-specific phrases only
  (`"sync notion"`, `"pull from notion"`, etc.)
- Added `_NOTION_EXCLUSIONS` list — if query contains `bmad`, `sdd`, `spec`,
  `read`, `file`, or `zettle`, NotionSkill scores 0.0

## Regression Acceptance Criterion
`AC-BUG-CHAT-005`: Given a running chat session, when the user says
"I want to run it through the bmad method," then Xochitl must respond
with a BMAD workflow prompt — never a Notion sync or task management response.

## Related
- `BUG-CHAT-001` — Intent shadowing (file_operation vs new_project)
- `CR-002` — Conversation layer hardening
