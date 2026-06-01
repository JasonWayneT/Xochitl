# Xochitl Release Notes

## 2026-06-01 — Perplexity Research Pipeline + Intelligent Skill Routing (CR-053 + CR-054)

### What changed

**Perplexity-grade Research Pipeline (CR-053) — FR-RES-005 through FR-RES-023**

Xochitl's research answers now match Perplexity.ai quality: cited, confidence-rated, source-quality-ranked, deduplicated, and format-matched to query intent.

**Deep content extraction (Phase 1)**

- `WebLookupSkill` now fetches **6 sources** (up from 3) with **5,000 chars** of body text per page (up from 260 characters — a single sentence).
- New `_extract_main_content()` method strips `<nav>`, `<footer>`, `<aside>`, and `<header>` blocks before reading; only retains paragraphs ≥40 characters. Result: article prose, not nav menus.
- `ExplorerSkill` evidence cap raised from 500 to **3,000 chars per step**.

**Citation tracking (Phase 2)**

- New `src/research_types.py` — `SourceRecord` dataclass holding `title`, `url`, `domain`, `body`, `trust_score`, and `fetched_at` for each fetched page.
- `WebLookupSkill.execute()` writes `context["research_sources"]` as `list[SourceRecord]`.
- `research.synthesize()` injects `[N]` labels and instructs the LLM to cite sources inline. Every research answer ends with a numbered sources block:
  ```
  [1] "Does Melatonin Help Sleep?" — pubmed.ncbi.nlm.nih.gov
  [2] "Sleep Hormone Overview" — mayoclinic.org
  ```

**Query optimization + decomposition (Phase 3)**

- New `src/query_planner.py`:
  - `rewrite_for_search()` — strips filler words, produces 3–7 keyword search string.
  - `decompose_query()` — splits multi-part questions into 1–4 sub-queries; `ExplorerSkill` runs them in parallel and merges results.

**Source quality scoring (Phase 3b)**

- `query_planner.domain_trust_score()` — Tier 1 (+0.40): `.gov`, `.edu`, PubMed, arXiv, WHO, Nature, ScienceDirect. Tier 2 (+0.20): Reuters, BBC, NPR, Wikipedia, Mayo Clinic. Tier 4 (−0.30): 20-entry hardcoded blocklist (Infowars, naturalnews.com, etc. — never modified by LLM). Links are ranked by trust before the top 6 are fetched.

**Synthesis quality (Phase 4)**

- **Deduplication**: sources sharing >60% character n-gram similarity in their first 500 chars are collapsed to the highest-trust copy. Prevents false confidence from syndicated stories.
- **Intent classification**: `classify_intent()` routes queries to one of: `definition`, `steps`, `comparison`, `verdict`, `timeline`, or `prose`. Comparison → markdown table. Steps → numbered list. Verdict → `VERDICT:` line + evidence.
- **Confidence rating**: LLM rates cross-source agreement 1–5. Maps to `Confidence: HIGH` / `MEDIUM` / `LOW`. LOW + <2 agreeing sources triggers structured insufficient-evidence block instead of a confident answer.
- **Verbatim statistics**: synthesis prompt instructs the model to reproduce exact numbers (never round or paraphrase).
- **Dead code closed**: `ExplorerSkill._synthesize()` replaced by delegation to `research.run_research()`.

**ResearchSkill (Phase 5)**

- New `src/skills/research_skill.py` — dedicated Perplexity-mode skill.
- Scores **0.90** on: "research", "deep research on", "what does the research say", "give me a confident answer", "summarize what's known about".
- Live streaming progress: *"Searching...", "Reading pubmed.nih.gov...", "Synthesizing 6 sources..."* via `context["status_cb"]`.
- Context-aware follow-ups: reads `context["last_research_topic"]`; prepends prior topic when query is short (<8 words) and contains no standalone research trigger.
- Adversarial review: for `verdict` intents or HIGH-confidence answers, appends top challenge as a `Note:` block.

---

**Intelligent Skill Routing (CR-054) — FR-ROUTE-001 through FR-ROUTE-013**

Fixes elliptical follow-up failures, adds semantic skill discovery, builds self-learning vocabulary, and architects for 150+ skills.

**Always-on compact manifest (Phase 1)**

- `ContextManager` now injects a compact skill manifest on every turn — replacing the previous vague stub. Format: one line per skill: `name: when-clause | example 1 / example 2`. Budget: ≤800 tokens for up to 50 skills. The LLM can now emit `<skill_call>` for any known skill even without full schema injection.

**Context-aware follow-up routing (Phase 2)**

- `AgentPipeline.run()` writes `context["last_skill_fired"] = skill_name` (or `""`) at the end of every turn.
- `WeatherSkill`, `ExplorerSkill`, `WebLookupSkill`, and `ResearchSkill` implement a context-boost check: if the message is ≤8 words, contains a follow-up phrase ("what about", "and in", "how about", "same for"), and `last_skill_fired` matches the skill class — returns **0.75** regardless of keyword match.
- Fixes: "what's the weather in San Diego?" → "what about in Hemet?" now routes correctly.

**Hybrid vector routing (Phase 3)**

- New `src/skill_vector.py` — `SkillVectorIndex` (structurally identical to `WorkflowVectorIndex`) targeting LanceDB table `skill_intents`.
- `seed_from_skills()` indexes all `tool_definition()["examples"]` and `when` fields at session start in a background daemon thread. Never blocks startup.
- `SkillScorer` now runs vector fallback when keyword scoring misses: if `SkillVectorIndex.search()` returns a result with similarity ≥0.80, that skill is used. Hard 500ms timeout — silently returns nothing on timeout, never blocks the turn.

**Skill self-learning (Phase 4)**

- New DB tables: `routing_misses` (logs turns where no skill fired + LLM hedged) and `skill_examples` (confirmed learned phrases per skill).
- Routing-miss detection in `AgentPipeline`: hedging phrases ("would you like me to", "did you mean") with no skill fired → persists to `routing_misses`.
- Vector fallback match → phrase persisted to `skill_examples` (hard-add).
- `SkillScorer` loads `skill_examples` into `context["learned_examples"]` on every turn; reloads when `context["skill_examples_dirty"]` is set.

---

### SDD chain updates

| Document | Change |
|----------|--------|
| `docs/spec/05-change-requests/CR-053-perplexity-research-pipeline.md` | CR document (spec) |
| `docs/spec/05-change-requests/CR-054-intelligent-skill-routing.md` | CR document (spec) |
| `docs/spec/06-traceability/traceability-matrix.md` | Added FR-RES-005–023, FR-ROUTE-001–013, NFR-RES-002–005, NFR-ROUTE-001–003 rows |
| `CAPABILITIES.md` | Updated §1 (Conversational Intelligence) and §4 (Technical) with research and routing capabilities |
| `docs/RELEASE_NOTES.md` | This entry |
| `src/research_types.py` | New — `SourceRecord` dataclass |
| `src/query_planner.py` | New — query rewriting, decomposition, domain trust scoring |
| `src/skill_vector.py` | New — `SkillVectorIndex` |
| `src/skills/research_skill.py` | New — `ResearchSkill` |

### New files

| File | Purpose |
|------|---------|
| `src/research_types.py` | `SourceRecord` dataclass (FR-RES-008) |
| `src/query_planner.py` | Query rewriting, decomposition, domain trust, specialized index routing |
| `src/skill_vector.py` | `SkillVectorIndex` for semantic skill discovery |
| `src/skills/research_skill.py` | `ResearchSkill` — Perplexity-mode skill entry point |

### Modified files

| File | Change |
|------|--------|
| `src/skills/web_lookup_skill.py` | 6 sources, 5000-char body, `_extract_main_content()`, `SourceRecord` output, trust-ranked fetching, FR-ROUTE-004 follow-up boost |
| `src/research.py` | Full rewrite: `[N]` citations, confidence, dedup, intent classification, adversarial, `run_research()` accepts `SourceRecord` |
| `src/skills/explorer_skill.py` | 3000-char evidence cap, `decompose_query` at step 1, `_gather()` returns `(str, SourceRecord[])`, delegates to `research.run_research()`, FR-ROUTE-004 boost |
| `src/skills/weather_skill.py` | FR-ROUTE-004 context-aware follow-up boost |
| `src/context_manager.py` | `SkillManifestEngine.compact()` now produces always-on one-liner-per-skill manifest |
| `src/agent/pipeline.py` | Writes `last_skill_fired` to context; routing-miss detection + DB persistence |
| `src/agent/skill_scorer.py` | Vector fallback (500ms timeout), learned-examples loading |
| `src/database.py` | `routing_misses` + `skill_examples` tables |
| `src/skills/__init__.py` | Register `ResearchSkill`; background `SkillVectorIndex.seed_from_skills()` |
| `smoke_test.py` | 295 → 314 tests (19 new ACs); updated Explorer tests for new `_gather`/`_finish` API |

### Smoke test results

```
314 passed  0 failed
```

---

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
