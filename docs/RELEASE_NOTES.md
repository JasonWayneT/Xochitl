# Xochitl Release Notes

## 2026-05-27 — Skill Reliability Hardening (CR-047) + Gmail & Google Auth fixes

### What changed

**Skill dispatch pipeline — four targeted fixes (CR-047)**

Skills now work reliably the first time they're invoked. Three compounding failure modes were audited and addressed:

1. **`examples` field in every `tool_definition()`** (FR-ORCH-047)
   All 12 built-in skills now return an `examples` list of 5+ verbatim trigger phrases from
   `tool_definition()`. `_format_active_skill_block()` injects these under "Example triggers:"
   so the LLM has concrete phrasing reference, not just a vague "when" description.

2. **Proactive invocation instruction** (FR-ORCH-048)
   The active-skill system prompt block previously included: *"Only invoke if the user clearly
   wants that action."* This was suppressing `<skill_call>` emission even on valid matches.
   Replaced with: *"Invoke proactively when the request falls within the skill's domain."*

3. **`@SkillName` explicit routing** (FR-ORCH-050)
   Users can now force a specific skill by prefixing their message with `@SkillName`.
   Example: `@GmailSkill check my inbox` routes directly to `GmailSkill.execute()`,
   bypassing `can_handle()` scoring entirely.

4. **`/debug skill` observability command** (FR-ORCH-049)
   New in-chat slash command. Type `/debug skill` to see a scored table of all loaded skills
   ranked by their `can_handle()` score against the last user message, with inject-threshold
   pass/fail status.

5. **`AGENTS.md` skill-addition checklist** (NFR-DEV-009)
   Mandatory 5-step checklist in `AGENTS.md` that must be satisfied before any new skill
   is considered complete: keyword vocabulary, `examples` field, `_builtin_skills`
   registration, smoke test assertions, and `CAPABILITIES.md` update.

**Gmail skill — keyword expansion + Doppler credential support**

- Expanded `_READ_KEYWORDS` with 9 new entries covering natural phrasings
  ("check in my email inbox", "got any emails", "any messages", etc.).
- `google_auth.py` now checks `GOOGLE_CREDENTIALS_JSON` env var (set via Doppler) before
  falling back to the file at `~/.xochitl/google_credentials.json`. Token persistence also
  supports `GOOGLE_TOKEN_JSON` env var.

**TurnCritic — CORRECTABLE verdict guard on skill turns**

- Fixed a bug where `TurnCritic` returning CORRECTABLE on a skill-call turn triggered a
  fresh LLM retry that had no access to the skill's output, silently discarding the result
  and replacing it with generic LLM text. CORRECTABLE verdicts on `tool_calls_made=True`
  turns are now downgraded to AMBIGUOUS, preserving skill output.

**Console output — flush argument removed**

- Removed `flush=True` from `console.print()` in the streaming path. Rich's `Console.print()`
  does not accept a `flush` keyword argument; this caused a `TypeError` on every streamed token.

### SDD chain updates

| Document | Change |
|----------|--------|
| `docs/spec/05-change-requests/CR-047-skill-reliability-hardening.md` | New CR document |
| `docs/spec/02-requirements-registry.md` | Added FR-ORCH-047–050, NFR-DEV-009, AC-CR047-001–009 |
| `docs/spec/06-traceability/traceability-matrix.md` | Added 5 CR-047 rows |
| `AGENTS.md` | Added "Adding a new skill" mandatory checklist section |

### Skills updated (examples field added)

All 12 built-in skills: `GmailSkill`, `WeatherSkill`, `WebLookupSkill`, `MapsSkill`,
`NotionSkill`, `BMADSkill`, `SDDSkill`, `CodeSkill`, `OrchestratorSkill`, `ExplorerSkill`,
`WorkflowSkill`, `ZettelkastenSkill`.

### Bug fixes

| Bug | Fix |
|-----|-----|
| `console.print() got unexpected keyword argument 'flush'` | Removed `flush=True` from streaming path |
| Gmail skill not triggered by "check in my email inbox" | Expanded `_READ_KEYWORDS` with 9 new phrasings |
| Gmail credentials not loading from Doppler | Added `GOOGLE_CREDENTIALS_JSON` / `GOOGLE_TOKEN_JSON` env var support |
| Skill output discarded when TurnCritic fires CORRECTABLE | Guard: CORRECTABLE downgraded to AMBIGUOUS on tool-call turns |
| FR-ORCH ID collision in requirements registry | Renamed CR-047 IDs from FR-ORCH-039–042 → FR-ORCH-047–050 |
