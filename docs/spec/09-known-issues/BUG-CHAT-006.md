# BUG-CHAT-006 — "Remote AI" Identity Hallucination

## Status
Resolved

## Severity
Critical — undermines core value proposition of Xochitl as a local terminal agent

## Symptoms
User asks "can you see the zettlelib folder?" and Xochitl responds:
> "As a large language model, I don't have direct access to your local
> file system..."

This is factually wrong — Xochitl is a local agent with filesystem access.

## Root Cause
Three compounding issues:

1. **Identity Guard at wrong position**: The Identity Guard text was appended
   at the *end* of the system prompt (lowest priority). LLMs weight earlier
   instructions more heavily, so the guard was routinely overridden by the
   model's pre-trained default identity ("I am a remote AI").

2. **CWD missing from search roots**: `_resolve_file_context()` in `router.py`
   searched `_PROJECT_ROOT`, `~/Desktop/...`, and `~/Documents` — but NOT
   `Path.cwd()`. If the user was in a different working directory (e.g.,
   `CodeProjects`), the fuzzy folder search came up empty and Xochitl
   defaulted to claiming she couldn't see any files.

3. **Fuzzy regex too narrow**: `_fast_classify()` only matched
   `(what|show|list|where)` before a folder keyword. The words `"see"`,
   `"view"`, `"browse"`, `"look"`, and `"check"` were not included, so
   "can you see the folder" bypassed the file-operation fast path entirely.

## Affected Requirements
- `FR-ORCH-003` — PreFlight Fact Injection must ground the LLM in reality
- `AC-CR002-001` — "What folder are you in?" must return actual CWD

## Fix Applied
**File**: `src/context_manager.py`
- Moved Identity Guard to the **first** section of `assemble_system_prompt()`,
  before Facts, Soul, Memory, and File context
- Guard is now priority #1 and is never compacted or removed

**File**: `src/router.py`
- Added `Path.cwd()` as the first entry in `search_roots` list
- Expanded fuzzy regex to include `see|read|view|browse|look|check` before
  folder/dir/files keywords
- Added `"can you see"` and `"do you see"` to `_KEYWORD_MAP["file_operations"]`

## Regression Acceptance Criterion
`AC-BUG-CHAT-006`: Given a running chat session where the CWD contains a
folder named `zettlelib`, when the user asks "can you see the zettle folder?",
then Xochitl must confirm she can see it and offer to help — never claim to
be a remote AI without filesystem access.

## Related
- `FR-ORCH-003` — PreFlight Fact Injection
- `CR-002` — Conversation layer hardening
- `BUG-CHAT-005` — BMAD intent hijacking
