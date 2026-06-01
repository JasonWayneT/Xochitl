# CR-053 — Perplexity-grade Research Pipeline

| Field | Value |
|---|---|
| ID | CR-053 |
| Title | Perplexity-grade Research Pipeline |
| Status | planned |
| Priority | P1 |
| Source | Gap analysis (June 2026) — evolve WebLookupSkill + ExplorerSkill into a high-confidence, cited, multi-source research pipeline |
| Implements | `FR-RES-005`–`FR-RES-020`, `NFR-RES-002`–`NFR-RES-005` |
| Depends on | CR-054 Phase 2 (`last_skill_fired` context key) for Phase 5 context-aware queries |

## Summary

Xochitl has foundational web research pieces (`WebLookupSkill`, `ExplorerSkill`,
`research.py`) but they are shallow, uncited, and disconnected from each other.
`WebLookupSkill` returns 260 chars per source. `research.py`'s synthesis and
adversarial machinery is never called by `ExplorerSkill` (dead code). There are
no citations, no confidence communication, no source quality scoring, and no
structured answer format.

This CR wires the existing pieces together, deepens content extraction, adds
citation tracking, source quality routing, and a new `ResearchSkill` entry point
that delivers Perplexity-grade answers: direct response, inline citations,
confidence rating, and a sources block — all within the existing token budget
and skill architecture.

## Key files touched

| File | Change |
|---|---|
| `src/skills/web_lookup_skill.py` | Deeper extraction, more sources, structured tuples |
| `src/research.py` | Wired into ExplorerSkill; updated synthesis prompt |
| `src/research_types.py` | New — `SourceRecord` dataclass |
| `src/query_planner.py` | New — query rewriting and decomposition |
| `src/skills/explorer_skill.py` | Remove inline `_synthesize()`; delegate to `research.run_research()` |
| `src/skills/research_skill.py` | New — dedicated Perplexity-mode skill |
| `src/skills/__init__.py` | Register `ResearchSkill` after `ExplorerSkill` |

## Phases

- **Phase 1** — Deep content extraction
- **Phase 2** — Citation tracking
- **Phase 3** — Query optimization + decomposition
- **Phase 3b** — Source quality scoring
- **Phase 4** — Synthesis quality (confidence, format, dedup, stats, evidence gate)
- **Phase 5** — ResearchSkill with streaming and context awareness

## Requirements

### Phase 1 — Deep Content Extraction

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-RES-005` | functional | P0 | planned | `WebLookupSkill.execute()` fetches up to 6 sources (up from 3). Each source body is capped at 5,000 chars (up from 260). |
| `FR-RES-006` | functional | P0 | planned | `WebLookupSkill._extract_main_content()` strips `<nav>`, `<footer>`, `<aside>`, and `<header>` blocks before HTML tag removal. Only paragraphs of >40 chars are retained. This replaces the current `_clean_text()`-only pass. |
| `FR-RES-007` | functional | P1 | planned | `WebLookupSkill.execute()` returns structured `(title, url, domain, body)` tuples stored in `context["research_sources"]` alongside the formatted string response. |
| `NFR-RES-002` | non-functional | P1 | planned | `ExplorerSkill._gather()` evidence cap raised from 500 chars to 3,000 chars per step to match the deeper content now available from `WebLookupSkill`. |

### Phase 2 — Citation Tracking

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-RES-008` | functional | P0 | planned | New `src/research_types.py` defines `SourceRecord(title: str, url: str, domain: str, body: str, fetched_at: str)`. All research functions accept and return `list[SourceRecord]` rather than bare strings. |
| `FR-RES-009` | functional | P0 | planned | `research.synthesize()` accepts `list[SourceRecord]`, injects `[N]` labels into the synthesis prompt, and instructs the LLM to cite sources using those labels wherever their content is used. |
| `FR-RES-010` | functional | P1 | planned | Every `ResearchSkill` and `ExplorerSkill` response ends with a numbered sources block: `[1] Title — domain.com`. Responses with no sources skip the block. |

### Phase 3 — Query Optimization + Decomposition

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-RES-011` | functional | P1 | planned | New `src/query_planner.py` exports `rewrite_for_search(user_query: str) -> str`: strips filler words and produces a 3–7 word keyword search string via `force_route="simple_qa"`. |
| `FR-RES-012` | functional | P1 | planned | `query_planner.decompose_query(user_query: str) -> list[str]` returns 1–4 sub-queries when the question is multi-part, or `[original]` when simple. Routed via `force_route="simple_qa"`. |
| `FR-RES-013` | functional | P1 | planned | `WebLookupSkill.execute()` calls `rewrite_for_search()` before the DuckDuckGo fetch. `ExplorerSkill.execute()` calls `decompose_query()` at step 1; if >1 sub-query is returned, runs parallel `_gather()` calls (one per sub-query) and merges results. |

### Phase 3b — Source Quality Scoring

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-RES-014` | functional | P1 | planned | `query_planner.route_to_specialized_index(intent: str) -> list[str]` maps detected query intent to preferred source endpoints: academic → PubMed REST API + arXiv API; medical → NIH API; general → DuckDuckGo. All endpoints are free and require no API key. |
| `FR-RES-015` | functional | P1 | planned | A domain trust score is applied to `links[:8]` before fetch selection. Tier 1 (+0.40): `.gov`, `.edu`, `pubmed.ncbi.nlm.nih.gov`, `arxiv.org`, `who.int`, `nature.com`, `sciencedirect.com`. Tier 2 (+0.20): `reuters.com`, `apnews.com`, `bbc.com`, `npr.org`, `wikipedia.org`, `mayoclinic.org`. Tier 3 (0.00): all others. Tier 4 (−0.30): manually curated low-quality list (~20–30 domains). Links are sorted by trust score before the top 6 are fetched. |
| `NFR-RES-003` | non-functional | P2 | planned | The Tier 4 blocklist is a hardcoded constant in `query_planner.py`, not database-driven. Maximum 30 entries. Must not be generated or modified by LLM output. |

### Phase 4 — Synthesis Quality

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-RES-016` | functional | P0 | planned | `ExplorerSkill._synthesize()` is removed. `ExplorerSkill.execute()` delegates to `research.run_research()`, passing the accumulated `list[SourceRecord]` and the active `ResearchMission`. This closes the dead-code gap in `research.py`. |
| `FR-RES-017` | functional | P0 | planned | `research.synthesize()` system prompt asks the LLM to rate cross-source agreement on a 1–5 scale and output it on the first line as `Agreement: N/5`. The score is parsed and surfaced to the user as `Confidence: HIGH` (4–5) / `MEDIUM` (3) / `LOW` (1–2) with a brief reason. |
| `FR-RES-018` | functional | P1 | planned | Before calling `research.synthesize()`, `ExplorerSkill` and `ResearchSkill` run a content-similarity deduplication pass: if two sources share >60% of their first 500 chars, the lower-trust-tier source is dropped. This prevents over-confidence from mirrored news stories. |
| `FR-RES-019` | functional | P1 | planned | Query intent is classified into one of: `definition`, `steps`, `comparison`, `verdict`, `timeline`, or `prose` before synthesis. The synthesis prompt is told the target format. Comparison queries produce a markdown table; steps queries produce a numbered list; verdict queries produce a VERDICT line followed by evidence. |
| `NFR-RES-004` | non-functional | P1 | planned | Numbers, percentages, and statistics from source text must be quoted verbatim in synthesis output. The synthesis prompt explicitly instructs: "When using a specific number or statistic from a source, reproduce it exactly — do not round, approximate, or paraphrase it." |
| `NFR-RES-005` | non-functional | P1 | planned | When post-synthesis confidence is LOW and fewer than 2 sources agreed, the response must begin with a structured insufficient-evidence block: `Confidence: LOW — insufficient source agreement. Here is what I found, but treat this with caution.` The system never silently presents a low-confidence answer as authoritative. |

### Phase 5 — ResearchSkill

| ID | Type | Priority | Status | Requirement |
|---|---|---|---|---|
| `FR-RES-020` | functional | P0 | planned | New `src/skills/research_skill.py` — `ResearchSkill`. `can_handle()` scores 0.90 on: "research", "what does the research say", "give me a confident answer", "deep research on", "summarize what's known about". Registered after `ExplorerSkill` in `src/skills/__init__.py`. |
| `FR-RES-021` | functional | P1 | planned | `ResearchSkill.execute()` streams live progress to the terminal via `context["status_cb"]` if available: "Searching...", "Reading [domain]...", "Synthesizing N sources...". Falls back to silent execution if no callback is wired. |
| `FR-RES-022` | functional | P1 | planned | `ResearchSkill.execute()` reads `context["last_research_topic"]` when present. If the user query is short (<8 words) and does not contain a standalone noun phrase, the query planner prepends the prior topic before decomposition and search. Enables follow-ups like "what about in children?" after a research turn. Depends on CR-054 Phase 2 (`last_skill_fired`) being in place. |
| `FR-RES-023` | functional | P2 | planned | After synthesis, if the query intent is classified as `verdict` or the synthesized answer makes a single strong claim, `research.adversarial_review()` is called and the top challenge is appended as a `Note:` block. User can suppress with `/no-challenge`. |

## Acceptance criteria

| ID | Criterion |
|---|---|
| `AC-CR053-001` | A research query returns 6 sources each with 500–4,000 chars of article prose, no navigation garbage. |
| `AC-CR053-002` | Every synthesized research answer includes inline `[N]` citations and a numbered sources block. |
| `AC-CR053-003` | "What are the effects of AI on employment and healthcare?" produces two separate searches and merges results. |
| `AC-CR053-004` | A medical query (e.g. "does melatonin affect sleep quality?") prefers `.gov` / `.edu` / PubMed sources over `.com` results. |
| `AC-CR053-005` | Every `ResearchSkill` response begins with `Confidence: HIGH/MEDIUM/LOW`. |
| `AC-CR053-006` | A query where sources disagree triggers `Confidence: LOW` with a stated reason rather than a confident synthesis. |
| `AC-CR053-007` | A comparison query (e.g. "compare keto vs. paleo") produces a markdown table, not free-form prose. |
| `AC-CR053-008` | A number from a source (e.g. "32.7% reduction") appears verbatim in the answer, not as "roughly a third". |
| `AC-CR053-009` | "Research the long-term effects of intermittent fasting" completes in under 60 seconds with confidence rating, citations, and sources block. |
| `AC-CR053-010` | After a research turn, "what about in children?" re-runs research with the prior topic prepended. |
