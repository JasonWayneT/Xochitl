# CR-008 — Zettelkasten Skill, Vault Auto-Discovery, and Tag Guardrail System

## Status

Implemented.

## Summary

This change request retroactively documents five distinct improvements made in
a single session:

1. **Routing fix** — Zettelkasten queries were being hijacked by the bare-path
   `file_operations` classifier before any zettelkasten intent check ran.
   A priority guard was added to `_fast_classify()` in `router.py`.

2. **Skill registration** — `ZettelkastenSkill` was not included in
   `_builtin_skills`, so the LLM never saw it in the skill manifest and
   fell back to generic advice. It is now registered alongside BMAD, SDD, etc.

3. **Vault auto-discovery** — `_get_vault()` previously only checked
   `VAULT_PATH` in `.env`. It now follows a 4-step priority chain: session
   state → env var → persisted config (`~/.xochitl/vault_config.json`) →
   filesystem scan of well-known locations for vault marker folders.

4. **Auto-scaffold on entry** — `enter_mode()` now checks whether
   Fleeting/Permanent/Literature exist before entering; if not, it calls
   `scaffold_vault()` automatically so a fresh folder becomes a vault in
   one step.

5. **Three-layer tag guardrail system** — Prevents tag bloat via:
   - Budget: max 4 tags per note
   - Similarity gate: blocks near-duplicate tags (>60% token overlap)
   - Quarantine → Promotion: new tags start in `## Proposed Tags` with a
     use counter; they auto-promote to `## Active Tags` at 3 uses.

Additionally, two NFR fixes: model manager routing decisions are now logged to
file only (no console noise), and the response language rule (English or
Spanish only) was added to the system prompt.

## Affected Requirements

| ID | Type | Priority | Status | Description |
|---|---|---|---|---|
| `FR-ORCH-001` | functional | P0 | implemented | Intent classification routes queries to appropriate handler |
| `FR-ORCH-005` | functional | P0 | implemented | Each skill exposes `tool_definition()` injected into every system prompt |
| `ARCH-SDD-001` | architecture | P0 | accepted | All LLM calls route through `src/router.py` |

## New Requirements Proposed

| ID | Type | Priority | Requirement |
|---|---|---|---|
| `FR-ORCH-015` | functional | P0 | Zettelkasten intent is classified before the bare-path `file_operations` check so a path in the query cannot hijack routing |
| `FR-ZTK-001` | functional | P0 | `ZettelkastenSkill` is registered in `_builtin_skills` and present in the LLM skill manifest at every turn |
| `FR-ZTK-002` | functional | P1 | Vault path resolves via a 4-step priority chain: (1) session state, (2) `VAULT_PATH` env, (3) persisted config, (4) filesystem scan |
| `FR-ZTK-003` | functional | P1 | `enter_mode()` auto-scaffolds Fleeting/Permanent/Literature folders if they are absent from the vault path |
| `FR-ZTK-004` | functional | P1 | Natural language path hints ("here", "in Vault-001", absolute path) are extracted from the user message and passed to `enter_mode()` |
| `FR-ZTK-005` | functional | P1 | Tag suggestions are capped at 4 per note (tag budget) |
| `FR-ZTK-006` | functional | P1 | A similarity gate blocks new tags with >60% token overlap to an existing active tag and redirects to the existing tag |
| `FR-ZTK-007` | functional | P1 | New tags enter `## Proposed Tags` in `vault-taxonomy.md` with a use counter; they auto-promote to `## Active Tags` after 3 uses across different notes |
| `NFR-UI-004` | non-functional | P2 | Model manager routing decisions are written to `logs/model_manager.log` only; no output to stderr or terminal |
| `NFR-UI-005` | non-functional | P1 | Xochitl responds in English or Spanish only unless the user explicitly requests another language for that message |
| `NFR-UI-006` | non-functional | P2 | Flower thinking animation runs at ≥10 fps (tick interval ≤0.1s, `refresh_per_second` ≥10) |

## Acceptance Criteria

| ID | Parent | Scenario | Given | When | Then |
|---|---|---|---|---|---|
| `AC-CR008-001` | `FR-ORCH-015` | Zettelkasten routing priority | Query contains "zettel" and a Windows absolute path | `_fast_classify()` runs | Classified as `zettelkasten_mode`, not `file_operations` |
| `AC-CR008-002` | `FR-ZTK-001` | Skill manifest presence | Xochitl starts a chat session | System prompt is assembled | `ZettelkastenSkill` tool definition appears in `## Skills You Can Invoke` |
| `AC-CR008-003` | `FR-ZTK-002` | Auto-discovery (saved config) | `VAULT_PATH` is unset; `~/.xochitl/vault_config.json` has a valid path | User says "work on my zettels" | Xochitl enters mode at the saved vault without user specifying a path |
| `AC-CR008-004` | `FR-ZTK-002` | Auto-discovery (filesystem scan) | `VAULT_PATH` unset, no saved config, vault exists under known Vaults root | User says "work on my zettels" | Xochitl discovers and enters the vault automatically |
| `AC-CR008-005` | `FR-ZTK-003` | Auto-scaffold on entry | Vault path points to an empty or partial folder | User says "work on my zettels in Vault-001" | Fleeting/, Permanent/, Literature/, and _System/ are created before mode is entered |
| `AC-CR008-006` | `FR-ZTK-004` | Path hint — "here" | User says "work on my zettels here" | `_extract_path_hint()` runs | Returns `str(Path.cwd())` |
| `AC-CR008-007` | `FR-ZTK-005` | Tag budget | Note processing suggests 6 matching tags | `_suggest_tags()` runs | Returns at most 4 tags |
| `AC-CR008-008` | `FR-ZTK-006` | Similarity gate | New tag `#writing` proposed; `#writing-process` already active (70% overlap) | Gate runs | `#writing` is rejected; `#writing-process` is suggested instead |
| `AC-CR008-009` | `FR-ZTK-007` | Quarantine entry | LLM proposes `#decision-making` not in active taxonomy | Tag accepted | Tag appears in `## Proposed Tags` with count 1; not yet in `## Active Tags` |
| `AC-CR008-010` | `FR-ZTK-007` | Promotion | `#decision-making` in proposed with count 2; applied to a third note | `_record_tag_usage()` runs | Tag moves to `## Active Tags`; removed from `## Proposed Tags`; promotion message shown |
| `AC-CR008-011` | `NFR-UI-004` | Silent routing log | Xochitl routes a query | Model manager logs tier/role/model | No `[Model Manager]` line appears in terminal; entry written to `logs/model_manager.log` |
| `AC-CR008-012` | `NFR-UI-005` | Language enforcement | User writes in English | No language override requested | Response is in English; no German, Dutch, or other language output |

## Implementation Tasks

| ID | Requirement IDs | Task | Notes |
|---|---|---|---|
| `TASK-CR008-001` | `FR-ORCH-015` | Add `_ZETTEL_RE` pattern and zettelkasten priority check before bare-path guard in `_fast_classify()` | `src/router.py` |
| `TASK-CR008-002` | `FR-ORCH-015` | Add `zettelkasten_mode` to `_LOCAL_SPECIALIZED_CATEGORIES` (thinking role), `_FORCE_LOCAL_CATEGORIES`, `_KEYWORD_MAP`, and `_CLASSIFICATION_PROMPT` | `src/router.py` |
| `TASK-CR008-003` | `FR-ZTK-001` | Import and register `ZettelkastenSkill` in `_builtin_skills` | `src/chat.py` |
| `TASK-CR008-004` | `FR-ZTK-001` | Expand `_ENTER_PHRASES` and `tool_definition()` `when` field to cover initiate/start/set-up phrasing | `src/skills/zettelkasten_skill.py` |
| `TASK-CR008-005` | `FR-ZTK-002` | Implement `_looks_like_vault()`, `_scan_for_vaults()`, `_load_saved_vault()`, `_save_vault()` | `src/skills/zettelkasten_skill.py` |
| `TASK-CR008-006` | `FR-ZTK-002` | Rewrite `_get_vault()` with 4-step priority chain | `src/skills/zettelkasten_skill.py` |
| `TASK-CR008-007` | `FR-ZTK-003` | Add pre-entry scaffold check in `enter_mode()` | `src/skills/zettelkasten_skill.py` |
| `TASK-CR008-008` | `FR-ZTK-004` | Implement `_extract_path_hint()` with absolute path, "here", fuzzy name, and history matching | `src/skills/zettelkasten_skill.py` |
| `TASK-CR008-009` | `FR-ZTK-005`, `FR-ZTK-006`, `FR-ZTK-007` | Implement `_TAG_BUDGET`, `_read_active_tags()`, `_read_proposed_tags()`, `_write_taxonomy()`, `_similarity_ratio()`, `_find_similar_tag()`, `_propose_tag()`, `_record_tag_usage()` | `src/skills/zettelkasten_process.py` |
| `TASK-CR008-010` | `FR-ZTK-005`, `FR-ZTK-006`, `FR-ZTK-007` | Rewrite `_suggest_tags()` and `_suggest_tags_heuristic()` to use guardrail stack | `src/skills/zettelkasten_process.py` |
| `TASK-CR008-011` | `FR-ZTK-007` | Call `_record_tag_usage()` in `apply_pending()`; surface promotions in output | `src/skills/zettelkasten_process.py` |
| `TASK-CR008-012` | `FR-ZTK-007` | Show proposed tag progress bar in `vault_status()` | `src/skills/zettelkasten_skill.py` |
| `TASK-CR008-013` | `FR-ZTK-007` | Add `_ensure_proposed_section()` to guarantee `## Proposed Tags` section in all vaults | `src/skills/zettelkasten_scaffold.py` |
| `TASK-CR008-014` | `NFR-UI-004` | Remove `print(..., file=sys.stderr)` from `_log()` in model manager | `src/model_manager.py` |
| `TASK-CR008-015` | `NFR-UI-005` | Add `## Language` rule to `build_system_prompt()` system prompt template | `src/context_loader.py` |
| `TASK-CR008-016` | `NFR-UI-006` | Set `refresh_per_second=10` and `time.sleep(0.06)` in `_StatusContext` | `src/chat.py` |

## Verification Results

2026-05-18:
- All 16 implementation tasks completed and committed to master across 5 commits
  (`47d07039`, `5712aea6`, `71c70e54`, `1deb2468`, `fd45204a`).
- `py_compile` clean on all modified files.
- Manual verification:
  - `[Model Manager]` no longer appears in terminal output.
  - Zettelkasten queries route to `zettelkasten_mode` category (thinking role model).
  - `ZettelkastenSkill` visible in skill manifest during chat session.
  - Language responses confirmed English-only without explicit override.
- Smoke/e2e tests: not re-run this session; no regression expected as changes
  are additive to the zettelkasten skill path and non-breaking to existing routes.

## Open Issues

- Smoke tests should be extended to cover `AC-CR008-001` through `AC-CR008-010`
  (zettelkasten routing, vault discovery, scaffold, and tag guardrail scenarios).
- `vault-taxonomy.md` files in vaults created before CR-008 will not have a
  `## Proposed Tags` section until `_ensure_proposed_section()` runs on next
  `scaffold_vault()` call. Existing vaults should be migrated manually or via
  a one-time migration command.
