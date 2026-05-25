# Exploration Notes — May 2026

Status: **draft / still exploring** — do not implement yet.

Sources reviewed:
- `langchain-master/CLAUDE.md` + `AGENTS.md` — dev standards and code quality conventions
- `langchain-master/libs/core/langchain_core/` — runtime patterns (SSRF, retry, rate limiting, exceptions)
- Agent framework design article (effectivesoft, IBM, Arize, Toward Data Science) — capability gap analysis
- JARVIS-framing article (kore, Anthropic, Google ADK, arxiv) — autonomy layer, meta-skills, exploration loop, governor model
- JARVIS interaction design research (arxiv, Anthropic, AI UX literature) — conversation design, persona persistence, relationship building, CLI UX, trust and transparency

---

## Group 1 — Dev Standards (CLAUDE.md / AGENTS.md only, no code changes)

Items that tighten what we write and commit, with no runtime impact.

| # | Item | Source | Notes |
|---|---|---|---|
| 1 | **Conventional Commits scope always required** | LangChain CLAUDE.md | Map scopes to registry area codes: `fix(api):`, `feat(orch):`, `fix(ztk):`, etc. No commit without a scope. |
| 2 | **Type hints + return types on every function** | LangChain CLAUDE.md | Currently inconsistent across `src/`. Treat as a hard rule going forward; audit existing code separately. |
| 3 | **No bare `except:` — always `except Exception as exc:`** | LangChain CLAUDE.md | Use a `msg` variable for error strings. Audit `src/` for bare clauses. |
| 4 | **Google-style docstrings on public methods** | LangChain CLAUDE.md | Priority: skill `can_handle()`, `execute()`, `tool_definition()` interfaces. Args / Returns / Raises sections. |
| 5 | **Testing checklist** | LangChain CLAUDE.md | Add to CLAUDE.md: happy path covered, edge cases covered, mocks for external deps, tests are deterministic, test fails when logic is broken. |
| 6 | **Security checklist** | LangChain CLAUDE.md | Add to CLAUDE.md: no `eval`/`exec`/`pickle` on user input, no bare resource leaks (file handles, threads, sockets). |

Likely CR number: **CR-015** (CLAUDE.md / AGENTS.md standards update)

---

## Group 2 — Security Hardening

| # | Item | Source | Affected files | Notes |
|---|---|---|---|---|
| 7 | **SSRF protection on outbound HTTP** | `langchain_core/_security/_ssrf_protection.py` | `src/skills/weather_skill.py` (`_fetch_json`), `src/skills/web_lookup_skill.py` | Before any `urlopen()` call, validate the URL against a blocklist: private IPs, localhost, link-local (`169.254.x.x`), and cloud metadata endpoints. LangChain implements this with `socket.getaddrinfo` + IP range checks. Xochitl can implement a lightweight version without Pydantic. |

Likely CR number: **CR-016** (outbound URL safety)

---

## Group 3 — Resilience

| # | Item | Source | Affected files | Notes |
|---|---|---|---|---|
| 8 | **Retry with exponential jitter on external API calls** | `langchain_core/runnables/retry.py` + `tenacity` | `src/skills/weather_skill.py` (`_fetch_json`), `src/skills/web_lookup_skill.py` | Use `tenacity`: `wait_exponential_jitter`, `stop_after_attempt(3)`, `retry_if_exception_type((OSError, TimeoutError))`. Transient network failures currently return hard failure with no retry. |
| 9 | **Rate limiter for cloud LLM calls** | `langchain_core/rate_limiters.py` (token bucket) | `src/router.py` | Token bucket, thread-safe. `BackgroundReview` daemon + interactive turns both hit the cloud router. A simple cap (e.g., 10 req/min) prevents cost runaway on long sessions. LangChain's `InMemoryRateLimiter` is a clean reference implementation. |

Likely CR number: **CR-017** (resilience: retry + rate limiting)

---

## Group 4 — Architecture: Exception Hierarchy

| # | Item | Source | Affected files | Notes |
|---|---|---|---|---|
| 10 | **Custom exception hierarchy** | `langchain_core/exceptions.py` | `src/` (new `src/exceptions.py`), all skill files, `src/router.py` | Replace bare `ValueError` / `Exception` with a thin hierarchy: `XochitlError` → `SkillError` / `GeocodingError` / `RouterError` / `ContextError`. Pairs with an `ErrorCode` enum for the future web/SSE layer (`FR-ORCH-020`). LangChain's pattern: one base exception, domain subclasses, optional error code attached to message. |

Likely CR number: **CR-018** (exception hierarchy)

---

## Group 5 — Runtime Capabilities (agent framework gap analysis)

Gaps identified by mapping the capability table from the agent framework article against Xochitl's current implementation.

| # | Capability | Gap | Affected area | Notes |
|---|---|---|---|---|
| 11 | **Reflection / critique** | `BackgroundReview` does passive observation but no active post-execution check | `src/chat.py` (`_agent_loop`), new `src/skills/critic_skill.py` | After a skill executes, a lightweight validator checks: did the output actually answer the question? Is another tool call needed? This hooks into `_agent_loop()` as an optional post-step. Not every turn needs it — only multi-step or high-uncertainty flows. |
| 12 | **Procedural memory** | Dynamic skills are LLM-callable tools; there is no concept of user-defined step sequences that accumulate over time | `src/skills/` (new skill type), `src/database.py` | The 4-bucket model (working / episodic / semantic / **procedural**) is mostly covered but the 4th bucket has no clean home. Procedural memory = reusable multi-step workflows the user builds up ("my weekly review", "how I triage Notion inbox"). Natural evolution of the dynamic skills system with a storage and recall path. |
| 13 | **Structured observability** | `events.py` emits the right events (FR-ORCH-020) but nothing consumes them into structured, queryable logs | `src/events.py`, `src/database.py` (new `agent_traces` table?) | Token usage per call, tool call trace per turn, latency per skill, failure reason. Required for the future web/SSE layer and for debugging regressions after model upgrades. Consumer could write to SQLite or a rotating JSONL file. |
| 14 | **Eval harness** | `smoke_test.py` is unit coverage, not quality measurement. No way to measure answer quality, task completion rate, or skill selection accuracy. | New `src/eval/` or `eval_harness.py` | LangChain's `standard-tests` pattern: shared test contracts per skill/integration type. For Xochitl: golden-set inputs → expected skill selected + expected output shape. Needed to catch regressions when swapping models or changing routing logic. |

Likely CR numbers: **CR-019** (reflection/critic), **CR-020** (procedural memory), **CR-021** (observability), **CR-022** (eval harness)

---

## Group 6 — JARVIS Runtime (autonomy, exploration, initiative)

Items that move Xochitl from a reactive assistant toward a proactive one. These are the highest-leverage capabilities for the JARVIS feel — without them the system is smart but passive. None of these exist in Xochitl today.

**Leaf skills vs platform skills distinction (architectural framing):**
Domain skills (weather, Notion, Zettelkasten) are *leaf skills* — they map one request to one response. The items below are *platform skills* — they make every leaf skill feel more alive because they let the agent sequence, investigate, decide, and initiate rather than just react.

| # | Capability | Gap | Affected area | Notes |
|---|---|---|---|---|
| 15 | **Bounded Explorer** | Xochitl can do a single web search or skill call but has no controlled multi-step investigation loop | New `src/skills/explorer_skill.py`, hooks into `_agent_loop` | The exploration loop: (1) form hypothesis / subquestion, (2) choose source or tool, (3) gather evidence, (4) evaluate confidence, (5) decide whether another step is needed, (6) stop with answer, recommendation, or approval request. Constraints the explorer must always carry: max step budget, allowed source types, confidence threshold, stop condition, handoff format to planner or executor. This is what makes Xochitl feel capable of *investigating* rather than just *searching*. |
| 16 | **Controlled initiative (autonomy layer)** | Xochitl is purely reactive — it only acts when prompted. JARVIS notices things and surfaces them. | `src/background_review.py` (extend), possibly new `src/autonomy.py` | `BackgroundReview` is a passive observer. The autonomy layer goes further: it can notice a pattern, flag a context shift, or surface a proactive insight ("I noticed your Notion queue hasn't moved in 3 days — want me to review it?"). Bounded by an initiative policy: what topics may Xochitl surface unprompted, how often, and under what conditions. Ties directly to the governor (#18). |
| 17 | **Response mode switching** | Personality is a static system prompt (SOUL.md). Xochitl does not adapt communication format to the type of task. | `src/context_manager.py` (system prompt assembly), `SOUL.md` | Three named modes: **conversational** (warm, exploratory, Xochitl's natural voice), **operator** (concise, structured, execution-focused — for multi-step tasks), **report** (structured output, headers, no personality filler — for results the user will act on). Mode can be selected by user or inferred from intent classification. The personality layer shapes *how* results are presented without changing *what* the tools do. |
| 18 | **Tiered governor** | Action approval is binary (FR-ORCH-011): either auto-execute or prompt. No nuanced permission tiers. | `src/chat.py` (`_handle_action_confirmation`), new `src/governor.py` | Three tiers: **auto** (safe, routine — file reads, lookups, memory recalls), **confirm** (risky or ambiguous — file writes, Notion mutations, shell commands, anything with side effects), **deny** (forbidden — operations outside sandboxed roots, destructive commands not explicitly requested). The governor owns this logic as a named module rather than scattered checks in `chat.py`. Ties into the autonomy layer so proactive actions also route through it. |
| 19 | **Executor** | Xochitl generates text and calls HTTP APIs but cannot run code, shell commands, or app automations. | New `src/skills/executor_skill.py`, integrates with governor (#18) | Safely runs: Python snippets in a restricted namespace, shell commands from an allowlist, pre-approved app automations. All execution gates through the governor before running. Output captured, errors surfaced. This is what makes Xochitl feel like it can *do things* rather than just *suggest things* — the key gap between a capable assistant and JARVIS. |

Likely CR numbers: **CR-023** (bounded explorer), **CR-024** (controlled initiative), **CR-025** (response modes), **CR-026** (tiered governor), **CR-027** (executor)

---

## Group 7 — JARVIS Interaction Layer

This group focuses on *how* Xochitl communicates and relates, not *what* she can technically do. These are the interaction quality patterns that determine whether Xochitl feels like a powerful tool or a coherent personal presence. Groups 1–6 built the engine; Group 7 is the driving experience.

**Subgroups:** A (conversation design) · B (persona and identity) · C (relationship building) · D (CLI-specific UX) · E (trust and transparency)

### A. Conversation Design

| # | Item | Gap | Affected area | Notes |
|---|---|---|---|---|
| 20 (A1) | **Presence cues and liveness** | Xochitl responds but doesn't feel present — no forward-lean, no within-session initiative, no acknowledgment of context shift | `src/chat.py`, `SOUL.md` | The "alive" feeling comes from three structural behaviors: (1) within-session initiative ("Following up on the Notion sync you mentioned..."), (2) non-verbosity calibration (shorter = more confident), (3) active-listening acknowledgment at the start of a complex turn. Not personality flair — structural behaviors. |
| 21 (A2) | **Anticipation gate** | No mechanism to surface a relevant item based on converging signals | `src/background_review.py`, `src/context_manager.py` | Signal hierarchy: recency > pattern > calendar > time-of-day. Anticipation fires only when 2+ signals converge. Informational surfacing only — no action-taking. Distinct from controlled initiative (#16): this surfaces context, not executes actions. |
| 22 (A3) | **Structured brief format** | Daily brief (`xochitl today`) is flat text with no consistent information hierarchy | `src/skills/daily_brief_skill.py` | Five sections, each skippable if empty: (1) temporal context, (2) schedule, (3) priorities, (4) async queue ("2 Notion items need your decision"), (5) awareness item ("you haven't committed in 4 days"). Max 5 lines per section. Pull on request — never push unsolicited at session start. |
| 23 (A4) | **Natural memory reference** | Memory facts in `Me.md` and `memory_facts` are stored but never referenced naturally in conversation | `src/context_manager.py`, `src/chat.py` | Reference stored facts as background context: "Given your preference for concise reports..." not "I see in your profile that you prefer...". The reference should feel incidental, not announced. Only invoke facts with confidence ≥ 0.8. |
| 24 (A5) | **Structured failure and uncertainty** | Xochitl surfaces errors and uncertainty inconsistently — sometimes too verbose, sometimes too terse | `src/chat.py`, `SOUL.md`, skill `execute()` signatures | Three-tier model: (p > 0.85) state directly, no hedge; (0.60–0.85) linguistic hedge ("I think...", "most likely..."); (< 0.60) explicit uncertainty + proposed resolution ("I'm not sure — want me to look it up?"). For hard failures: what failed, what was attempted, what the user can do. |

### B. Persona and Identity Persistence

| # | Item | Gap | Affected area | Notes |
|---|---|---|---|---|
| 25 (B6) | **Persona anchoring** | `SOUL.md` is a flat document — behavioral rules are mixed with tone guidance, no structural identity separation | `SOUL.md`, `src/context_manager.py` | Identity block must be structurally distinct (clear header, always at system prompt top). Behavioral examples > behavioral descriptors: not "be warm" but a sample exchange that shows what warm looks like. End-of-system-prompt identity reminder (1–2 sentences) exploits recency bias. |
| 26 (B7) | **Persona drift detection** | Long or emotionally charged conversations cause Xochitl to drift from her intended voice without recovery | `src/background_review.py` (new subtask) | `BackgroundReview` daemon adds a drift check every 10–15 turns: compare recent response tone against SOUL.md behavioral examples. Drift detected → inject identity reminder at end of next system prompt. Context compression must preserve behavioral patterns, not just factual content. |
| 27 (B8) | **Voice and tone consistency** | Tone shifts by task type without a clear framework — inconsistent across skill outputs | `SOUL.md`, all skill `execute()` return strings | Three parameters per response mode: lexical density, hedging level, warmth markers. Define explicitly in SOUL.md and map to each of the three response modes (#17). Each mode has specific parameter values, not just an adjective ("be more concise"). |

### C. Relationship Building

| # | Item | Gap | Affected area | Notes |
|---|---|---|---|---|
| 28 (C9) | **Progressive personalization milestones** | Xochitl treats session 1 and session 100 identically — no progression in familiarity or capability | `src/database.py` (session count), `src/context_manager.py`, `SOUL.md` | 3–4 milestones loaded via config: M1 (sessions 1–5) formal and careful; M2 (6–20) use stored preferences, reference recent history; M3 (20+) natural memory reference, anticipation gate active. Changes are system prompt section swaps — no hardcoded behavior. No announcements to user. |
| 29 (C10) | **Implicit preference learning** | Preferences stored only when explicitly stated by user. No learning from behavioral signals. | `src/background_review.py`, `src/database.py` (memory_facts) | Four safe signal classes: (1) rephrased query → original framing missed, (2) ignored suggestion → negative preference signal, (3) reformulated output → user edited Xochitl's text, (4) interaction timing → long pause before command = deliberation. Confidence decay per session. Reveal through behavioral change only, not announcements. |
| 30 (C11) | **Graceful correction handling** | No defined pattern for user corrections — sometimes Xochitl restates the error, sometimes ignores the correction | `src/chat.py`, `src/background_review.py` | Three-step: (1) minimal acknowledgment ("Got it" — no over-apology), (2) apply correction immediately, (3) store to preference log if pattern (same correction ≥ 2×). Never: "I apologize for the confusion, I should have..." — breaks flow and feels servile. |

### D. CLI-Specific UX

| # | Item | Gap | Affected area | Notes |
|---|---|---|---|---|
| 31 (D12) | **Terminal AI visual grammar** | Output is functional but not tuned to the terminal medium — no consistent visual language | `src/chat.py` (output layer), all skill `execute()` returns | Five conventions: (1) ≤2 semantic colors (green = done, yellow = attention), (2) consistent prefix chars (✓ done, → action, ⚠ warning, ✗ failed), (3) 2-space indent, (4) ≤80 char lines for copy-paste safety, (5) `--json` flag outputs clean JSON for piping. |
| 32 (D13) | **Session liveness signals** | The terminal session feels static — no sense of ongoing presence between turns | `src/chat.py` | Three liveness signals in priority order: (1) streaming (words appear progressively — highest impact), (2) thinking indicator for long operations ("Looking that up..."), (3) session continuity cue at session start ("Continuing from where we left off — you were working on..."). Without streaming, the CLI feels like a batch job. |
| 33 (D14) | **Streaming and progressive output** | Xochitl returns complete responses — no token-level streaming to terminal | `src/router.py`, `src/chat.py` | Highest-leverage single change for perceived liveness. Implementation: router exposes `stream=True` parameter; chat loop prints tokens as they arrive; non-streaming skill outputs (tool calls, DB queries) show a `rich` spinner. Implement conversational streaming first, skill outputs second. |

### E. Trust and Transparency

| # | Item | Gap | Affected area | Notes |
|---|---|---|---|---|
| 34 (E15) | **Compact reasoning disclosure** | Xochitl either hides reasoning entirely or over-explains — no middle ground | `src/chat.py`, skill `execute()` patterns | Compact format: one-line action summary ("Checking weather for San Diego...") → result. Multi-step: numbered brief with ✓/... per step. Full reasoning only on explicit request ("Why?"). Goal is audit-ability, not explanation. |
| 35 (E16) | **Uncertainty disclosure tiers** | No structured uncertainty communication — hedges are ad hoc | `SOUL.md`, `src/chat.py`, all skill outputs | Same three-tier model as A5, codified here as a governance rule: (p > 0.85) state directly; (0.60–0.85) linguistic hedge; (< 0.60) explicit uncertainty + proposed resolution. Confidence derived from: source count, source recency, skill success rate (observability #13), LLM self-assessment. |
| 36 (E17) | **Capability boundary communication** | Xochitl attempts tasks it cannot complete, failing confusingly, or refuses generically without specifics | `src/chat.py` (intent classification), `src/skills/` (`can_handle()`) | Resolve-and-route: classify → check `can_handle()` on each skill → if no match, state specifically what's missing with a forward path. Graceful degradation: if partial handling is possible, offer it explicitly with what's covered. Never silently do a reduced version. |

Likely CR numbers: **CR-028** (conversation design A1–A5), **CR-029** (persona anchoring + drift B6–B8), **CR-030** (relationship building C9–C11), **CR-031** (CLI UX + streaming D12–D14), **CR-032** (trust + transparency E15–E17)

---

## Architectural framing — the six-module practical model

From the JARVIS article. Useful as a north-star layout when designing the above CRs:

| Module | Question it answers | Xochitl mapping |
|---|---|---|
| Conversation brain | "How should I talk?" | SOUL.md + UserProfileEngine + response mode (#17) |
| Task brain | "What is the user trying to accomplish?" | `_classify()` + intent system (FR-ORCH-010) |
| World model | "What do I know about Jason, the project, and current situation?" | ContextManager + preferences + memory_facts + Me.md |
| Explorer | "What should I inspect before deciding?" | WebLookupSkill today → Bounded Explorer (#15) |
| Executor | "What can I safely do?" | HTTP skills today → Executor (#19) |
| Governor | "Should I act now, ask, or stop?" | Action gate (FR-ORCH-011) today → Tiered Governor (#18) |

---

## Xochitl capability coverage summary

| Module | Status | Gap |
|---|---|---|
| Brain (TieredRouter + LLM) | ✅ | — |
| Hands (skill system, leaf skills) | ✅ | — |
| Notebook (ChromaDB + SQLite memory) | ✅ | Procedural memory bucket missing (#12) |
| Map (retrieval + grounding) | ✅ | One-shot only; bounded explorer missing (#15) |
| Supervisor (ContextManager + agent loop) | ✅ | — |
| Reflection / critique | ❌ | #11 |
| Observability | ⚠️ partial | Events emitted but not consumed (#13) |
| Eval harness | ⚠️ partial | Unit tests only, no quality measurement (#14) |
| Explorer | ❌ | #15 |
| Autonomy / initiative | ❌ | #16 |
| Response mode switching | ❌ | #17 |
| Governor (tiered) | ⚠️ partial | Binary today, needs tiers (#18) |
| Executor | ❌ | #19 |
| **— Group 7: Interaction Layer —** | | |
| Streaming / terminal liveness | ❌ | #33 — highest-leverage single change |
| Conversation presence cues | ❌ | #20 |
| Anticipation gate | ❌ | #21 |
| Structured brief format | ⚠️ partial | Flat text today; section hierarchy missing (#22) |
| Natural memory reference | ❌ | Facts stored but never invoked conversationally (#23) |
| Uncertainty disclosure tiers | ⚠️ partial | Ad hoc hedging; no structured model (#24 / #35) |
| Persona anchoring (structural) | ⚠️ partial | SOUL.md exists; identity block not structurally separated (#25) |
| Persona drift detection | ❌ | #26 |
| Progressive relationship milestones | ❌ | #28 |
| Implicit preference learning | ❌ | Explicit statements only (#29) |
| Correction handling | ⚠️ partial | No defined pattern (#30) |
| Terminal visual grammar | ⚠️ partial | Functional but inconsistent (#31) |
| Capability boundary communication | ❌ | Resolve-and-route pattern missing (#36) |

---

## Best Practices Reference

Research pass completed 2026-05-24. For each item: concrete best practices, anti-patterns to avoid, and key reference.

---

### Group 1 — Dev Standards

**#1 Conventional Commits scopes**
- Define a closed scope list (8–15 entries) in `CONTRIBUTING.md` mapped to logical subsystems, not filenames. Enforce with `commitlint` `scope-enum` rule at error level 2 in CI.
- Use footers (`Closes #N`, `FR-ORCH-020`) for issue and requirement references — never in the scope field.
- ❌ Issue IDs as scopes (`fix(#123):`), drifting scope names, file paths as scopes.
- Ref: [Conventional Commits v1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)

**#2 Type hints — incremental adoption**
- Start with `mypy --ignore-missing-imports --no-strict-optional`. Annotate public signatures and `__init__` first. Add strictness flags one sprint at a time (`--disallow-untyped-defs` → `--disallow-incomplete-defs` → `--strict`).
- Type LLM return values as `dict[str, Any]` and wrap in `TypedDict` / `dataclass` before passing downstream to stop `Any` propagation.
- ❌ Enabling `--strict` globally on day one; blanket `# type: ignore` without explanation; annotating with `Any` everywhere to satisfy the checker.
- Ref: [mypy docs](https://mypy.readthedocs.io/)

**#3 Exception handling**
- Always name the caught exception: `except ValueError as exc:`. Attach context before re-raising: `raise RouterError("...") from exc`. Use Python 3.11+ `exc.add_note()` to attach breadcrumbs without wrapping.
- "Raise low, catch high" — domain functions raise specific exceptions; catch only at I/O boundaries (CLI handler, web handler).
- ❌ `except Exception: pass`; `except BaseException:` (swallows `KeyboardInterrupt`); exceptions for normal control flow.
- Ref: [Real Python exception handling best practices](https://realpython.com/ref/best-practices/exception-handling/)

**#4 Google-style docstrings**
- Structure: one-line summary → blank line → optional description → `Examples:` → `Args:` → `Returns:` → `Raises:`. Types in the signature, not the docstring.
- `Raises:` must list all exceptions callers should handle. `Returns:` must document the `None` case for `Optional[T]`.
- ❌ Restating the function name as the summary; omitting `Raises:`; documenting implementation details instead of the interface contract; stale docstrings after signature changes.
- Ref: [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

**#5 Testing checklist for AI/LLM projects**
- Unit tests: mock all LLM calls at the provider boundary with a `FakeLLM` class. Target <100ms per test. Use `pytest-asyncio` for async agent loops.
- Integration tests: run against real APIs in a dedicated CI stage only. Use `pytest-recording` (VCR cassettes) to replay without network calls in PR builds.
- Golden set for skill routing: 30–60 labeled `(utterance, expected_skill)` pairs. Skill accuracy drops >5% → block merge.
- ❌ Real API calls in unit tests; asserting exact LLM output strings; skipping async test coverage; no golden set for routing.
- Ref: [dasroot.net — Python Agent Testing Best Practices](https://dasroot.net/posts/2026/02/python-agent-testing-best-practices-tools/)

**#6 Security checklist**
- Never call `eval()` / `exec()` with user-controlled or LLM-generated input — any string passed to `eval` is an RCE sink (Microsoft Security Blog, May 2026).
- Never deserialize `pickle` from untrusted sources. Use `safetensors` for model weights; run `modelscan` in CI.
- Always set timeouts on outbound HTTP: `httpx` default is `None` — pass `timeout=30` explicitly. Use `contextlib.ExitStack` for resource cleanup.
- ❌ `subprocess.run(user_input, shell=True)`; trusting pickle from model registries; API keys in source files.
- Ref: [Microsoft Security Blog — Prompts Become Shells (May 2026)](https://www.microsoft.com/en-us/security/blog/2026/05/07/prompts-become-shells-rce-vulnerabilities-ai-agent-frameworks/)

---

### Group 2 — Security

**#7 SSRF protection on outbound HTTP**
- **Resolve-then-validate pattern**: resolve hostname to IP via `socket.getaddrinfo()`, then check against blocklist using `ipaddress.ip_address(ip).is_private`. Do this before any `urlopen()` / `httpx.get()` call. Prevents DNS rebinding (TOCTOU).
- Blocklist: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16` (AWS IMDSv1), `::1`, `fd00::/8`. Protocol allowlist: `https://`, `http://` only — reject `file://`, `ftp://`, `gopher://` before DNS.
- Canonicalize URLs before checking — decimal-encoded IPs (`http://2130706433/`) and octal bypass naive string matching.
- Wrap as `validate_outbound_url(url: str) -> str` raising `SSRFBlockedError`. ~30 lines, no Pydantic needed.
- ❌ String-matching `"169.254.169.254"` in raw URL; checking hostname before DNS resolution; blocking only IPv4 while leaving IPv6 open.
- Ref: CVE-2026-25580 (pydantic-ai shipped this exact gap)

---

### Group 3 — Resilience

**#8 Retry with exponential jitter**
- Use `tenacity`: `wait_exponential_jitter(initial=1, max=60, jitter=5)` + `stop_after_attempt(5)`. Jitter prevents synchronized retry storms.
- Retry only on transient exceptions: `RateLimitError`, `APITimeoutError`, `ServiceUnavailableError` (HTTP 429, 503, 504). **Never** retry HTTP 400, 401, 403 — permanent failures.
- Log each retry with attempt number, wait duration, exception class via `before_sleep` callback.
- For streaming LLM calls, don't retry mid-stream. Only retry on connection failures.
- ❌ Retrying 400-class errors; fixed wait with no backoff; no `max` cap on backoff; retrying calls that already committed side effects.
- Ref: [tenacity docs](https://tenacity.readthedocs.io/)

**#9 Rate limiting for LLM API calls**
- Use token bucket. Track both request count and token count as separate buckets — LLM APIs impose both RPM and TPM limits simultaneously.
- `pyrate-limiter` for async + thread-safe support backed by SQLite for persistence across restarts. `LangChain InMemoryRateLimiter` as a lightweight reference.
- Expose rate limit state in observability: log `tokens_remaining`, `requests_remaining`, `wait_time_ms` on each acquire.
- ❌ Single global lock for all API calls (kills async concurrency); tracking only request count not token count; no wait/retry integration with Item 8.
- Ref: [pyrate-limiter PyPI](https://pypi.org/project/pyrate-limiter/)

---

### Group 4 — Architecture

**#10 Custom exception hierarchy**
- Three-layer hierarchy: `XochitlError(Exception)` → domain groups (`RouterError`, `NotionError`, `SandboxError`, `TaskError`) → specific leaves (`RouterTimeoutError(RouterError)`). Callers can catch at any layer.
- Store structured fields as attributes, not only in the message string: `RouterError(message, model_id=..., attempt=..., status_code=...)`.
- Distinguish user-facing errors from internal errors via `user_message: str | None` attribute on the base class. CLI shows `user_message` when set; generic fallback otherwise.
- Add `ErrorCode` enum per exception class — feeds structured observability (#13) and web/SSE layer.
- ❌ Inheriting from `BaseException`; one catch-all `XochitlError` with a `subtype` string; >15–20 leaf types (caller exhaustion).
- Ref: [TheCodeForge — Custom exceptions](https://thecodeforge.io/python/custom-exceptions-python/)

---

### Group 5 — Runtime Capabilities

**#11 Reflection / self-critique**
- Post-execution critic prompt: "Here is the task goal and the response produced. Identify factual errors, missing steps, or constraint violations." Cheaper than re-running the full task.
- For high-stakes decisions: sample 3 times at `temperature > 0` and compare (self-consistency, Wang et al. 2023). If all three agree on structure, proceed. If they diverge, surface a caveat.
- Re-route vs caveat: correctable errors → re-route to clarification loop. Structurally ambiguous → surface caveat and stop. Cap reflection at 2 iterations before escalating to user.
- Trajectory-level reflection for multi-step tasks: pass intermediate steps to the reflection prompt, not just the final output.
- ❌ Infinite reflection loops; reflexive re-routing when output hasn't changed; reflection on every low-stakes action (2x latency for trivial queries); unconditionally trusting LLM self-assessment.
- Ref: [arxiv 2405.06682 — Self-Reflection in LLM Agents](https://arxiv.org/pdf/2405.06682)

**#12 Procedural memory**
- Separate from semantic memory (ChromaDB / RAG). Procedural = reusable step sequences, decision rules. Store in a versioned YAML workflow library (or SQLite table) keyed by workflow name. Semantic = "what is X"; procedural = "how do I do X".
- **LEGOMem pattern**: after a successful multi-step task, distill the trajectory into a reusable workflow unit: trigger pattern, step sequence, expected outputs, known failure modes. On subsequent similar tasks, start from this template.
- Retrieve top-1 matching workflow by embedding similarity on intent detection. Keep entries ≤500 tokens. Tag with last-used timestamp and success/failure count for learned prioritization.
- ❌ Storing procedural workflows in the same vector space as semantic facts (retrieval conflation); hardcoding all workflows in the system prompt (context fills up); never pruning stale workflows; conflating with episodic memory.
- Ref: [LEGOMem — arxiv 2510.04851](https://arxiv.org/pdf/2510.04851)

**#13 Structured observability**
- Minimum log per LLM call: `model_id`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_first_token_ms`, `latency_total_ms`, `tool_calls: [{name, args_hash, success, duration_ms}]`, `failure_reason`, `trace_id`.
- Storage: JSONL ring buffer (append-only, capped at 10MB) for raw stream; flush to SQLite background thread for queryable analytics. Each tool invocation = child span of parent LLM span.
- Use OpenTelemetry GenAI Semantic Conventions (2025) attributes: `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.prompt_tokens`. Compatible with any OTel backend later.
- ❌ Logging full prompt/response content without redaction (PII risk); unstructured text logs; no `trace_id` across multi-step tasks; `print()` for observability.
- Ref: [OpenTelemetry GenAI Observability (2026)](https://opentelemetry.io/blog/2026/genai-observability/)

**#14 Eval harness**
- Golden set: 30–60 labeled `(utterance, expected_skill, expected_output_schema, pass_criteria)` examples per capability, version-controlled alongside code. Include adversarial and edge-case inputs.
- Skill accuracy: report per-skill F1 (precision + recall), not just overall accuracy. Target >90% before shipping a new skill. Fail build if accuracy drops >5% or task completion drops >3% vs baseline.
- LLM-as-judge for open-ended task completion: cheaper than human review, consistent at scale. Store baseline scores as a JSON artifact in the repo.
- Model swap protocol: run harness on both old and new model, produce side-by-side report, require human sign-off on regressions.
- ❌ Golden sets covering happy path only; asserting exact LLM output strings; skipping per-skill recall; not versioning the golden set.
- Ref: [Confident AI — LLM Agent Evaluation](https://www.confident-ai.com/blog/llm-agent-evaluation-complete-guide)

---

### Group 6 — JARVIS Runtime

**#15 Bounded exploration**
- Hard step budget as a named config value (not a magic number): 12 steps for research, 5 for simple queries. On budget exhaustion, emit a structured `BudgetExhausted` event: `{steps_taken, last_state_summary, recommended_action}`.
- Convergence detection: hash the action taken each step. Repeat-hash = loop detected → stop and escalate immediately.
- Confidence threshold: after each step the agent emits 0–1 confidence. >0.85 → stop and return. <0.3 after 3 steps → escalate for user clarification.
- Context window budget: at 70% of model context limit, trigger a summarization step ("current plan, progress, remaining criteria"), then continue in compressed context.
- ❌ No step limit at all (the `$47K LangChain Loop`, Nov 2025: 11 days unbounded); step budget as a buried constant; treating convergence and hard-stop as the same signal; summarization that doesn't check if the summary itself fits.
- Ref: [DEV Community — Multi-Agent Loop Stop Conditions](https://dev.to/dowhatmatters/stopping-conditions-that-actually-stop-multi-agent-loops-bnb)

**#16 Controlled initiative**
- Initiative policy — permitted categories: (a) time-sensitive failures ("Notion sync failed silently 10 min ago"), (b) in-session follow-ups to work already begun. Never: unsolicited productivity tips, personality engagement, or recommendations not connected to an active task.
- Confidence threshold of ≥0.8 before surfacing a proactive insight. Log all sub-threshold candidates internally for threshold tuning.
- Expose user preference: `proactive_mode: off | errors_only | full`. Default `errors_only`. Auto-suppress a category after 3 consecutive dismissals by the user.
- Every proactive message must be actionable and dismissable in one command.
- ❌ "Good morning brief" unsolicited messages (elicits self-threat responses, reduces system usage per arxiv 2509.09309); no dismiss mechanism (alert fatigue); proactive output requiring multiple follow-up actions; pattern-matching without confidence threshold.
- Ref: [arxiv 2509.09309 — Proactive AI Adoption can be Threatening](https://arxiv.org/pdf/2509.09309)

**#17 Response mode switching**
- Three modes as **system prompt sections injected conditionally** (not code branches): `CONVERSATIONAL` (warm, exploratory, Xochitl's voice), `OPERATOR` (concise, imperative, no hedging — "Done. 3 tasks synced."), `REPORT` (structured, headers, no personality filler).
- Lightweight mode inference before LLM call: presence of command verb ("sync", "run", "do") → OPERATOR; explicit formatting cue ("give me a report") → REPORT; otherwise → CONVERSATIONAL. Can be a regex heuristic, no second LLM call needed.
- Announce mode transitions explicitly: "Switching to report mode — this will take a moment." Silent switches cause user disorientation (arxiv 2602.07338).
- Mode is per-request, not per-session. Always re-infer from the current utterance.
- ❌ Implementing mode as hardcoded Python `if` branches; same system prompt for all modes; no transition announcement; inferring mode from history alone.
- Ref: [arxiv 2602.07338 — Intent Mismatch in Multi-Turn Conversations](https://arxiv.org/html/2602.07338v1)

**#18 Tiered governor**
- Three tiers:
  - **AUTO**: reads, lookups, status checks, non-destructive queries. Execute immediately, log only.
  - **CONFIRM**: writes, deletes, external API side effects, spawning subprocesses. Show exact action + reversibility. Require `y/N`.
  - **DENY**: outside security policy (filesystem beyond sandbox root, non-allowlisted hosts, generated code without sandbox). Raise `PolicyViolation` immediately; log the attempt.
- Governor as a named module (`src/governor.py`): `Governor.check(action: Action) -> Permission` is a **pure function** — no side effects, independently testable, auditable.
- Policy stored in YAML/TOML (`governor_policy.toml`) with `version` + `last_updated` fields. Log every CONFIRM/DENY with the policy version that produced it.
- Governor runs **synchronously before every action dispatch** — not as a post-hoc audit. All paths (CLI, autonomy layer, executor) call the same governor.
- ❌ Checking permissions only at CLI layer (internal callers bypass); permission logic embedded in business code; confirming reads (permission fatigue); policy as Python `if` statements (not auditable).
- Ref: [Microsoft Agent Governance Toolkit (Apr 2026)](https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/)

**#19 Safe executor**
- Three trust tiers:
  - **LLM-generated code**: Docker / gVisor + seccomp. No network, no host filesystem. 5-second wall-clock timeout. `docker run --rm --network=none --memory=128m`.
  - **Semi-trusted allowlisted commands**: `subprocess.run([cmd, ...], timeout=10, capture_output=True, shell=False)`. Command must match `(command, allowed_args_pattern)` allowlist.
  - **Never**: `eval()`, `exec()`, `subprocess.run(shell=True)` with any generated content.
- RestrictedPython is **not a security boundary** — it is defense-in-depth only. Requires OS-level isolation (subprocess + AppArmor/seccomp) alongside it.
- Capture output with size cap (max 64KB). Truncate with `[truncated]` marker. Never pass raw captured output back to the LLM prompt without sanitization — it's an injection path.
- Always call `Governor.check(action=EXEC, ...)` before running anything. Executor is a consumer of the governor, not a peer to it.
- ❌ Trusting RestrictedPython alone; no memory/CPU limits on subprocess; passing raw stdout/stderr into next LLM prompt; unlimited capture buffer; no allowlist for operator-mode commands.
- Ref: [CodeJail — openedx](https://github.com/openedx/codejail), [Microsoft Security Blog — Prompts Become Shells (May 2026)](https://www.microsoft.com/en-us/security/blog/2026/05/07/prompts-become-shells-rce-vulnerabilities-ai-agent-frameworks/)

---

### Group 7 — JARVIS Interaction Layer

#### A. Conversation Design

**#20 (A1) Presence cues and liveness**
- Three structural signals (not personality): (1) within-session initiative ("Following up on..."), (2) non-verbosity calibration (shorter response = higher confidence — use deliberately), (3) active-listening acknowledgment at the start of a complex turn.
- Presence comes from relevance, not enthusiasm. No "Great question!", no "Certainly!", no filler openers.
- ❌ Opening every response with a filler phrase; explaining what you're about to do before doing it; defaulting to longer responses for complex topics.
- Ref: conversational AI presence research synthesis

**#21 (A2) Anticipation gate**
- Signal hierarchy (weight order): recency > established pattern > calendar event > time-of-day. Never fire on a single signal alone. 2+ signals required to surface anything.
- Informational only: "You have a meeting in 20 minutes and three open tasks — want a summary?" Never: "I'm going to summarize your tasks now."
- Gate conditions: confidence ≥ 0.7, signal count ≥ 2, `proactive_mode` not `off`. Informational surfacing → not action-taking.
- ❌ Firing on time-of-day alone; taking actions (vs surfacing information); no dismiss mechanism; surfacing during active task execution.
- Ref: anticipation patterns in proactive AI systems

**#22 (A3) Structured brief format**
- Five sections, each skippable if empty: (1) temporal context ("Monday, 7:43am"), (2) schedule, (3) priorities (top 3 tasks), (4) async queue ("2 Notion items need a decision"), (5) awareness item. Max 5 lines per section total.
- Pull on request (`xochitl today`) — never push-at-session-start unsolicited.
- ❌ Flat text brief with no section hierarchy; briefs longer than 20 lines; unsolicited session-opening brief (alert fatigue).
- Ref: morning brief format patterns in agentic assistants

**#23 (A4) Natural memory reference**
- Reference stored facts as incidental context, not data retrieval: "Given your work on the fitness app..." not "I found in your memory that you are working on a fitness app."
- Only surface facts with confidence ≥ 0.8 (reinforced at least once). Low-confidence facts silently inform routing but are never stated.
- ❌ Announcing retrieval ("I checked your profile and..."); citing stale facts without recency check; surfacing facts unrelated to current turn.
- Ref: natural memory reference patterns in long-term AI assistants

**#24 (A5) Uncertainty communication tiers** *(see also #35 — both point to the same model)*
- Three-tier model: (p > 0.85) state directly, no hedge; (0.60–0.85) linguistic hedge ("I think...", "most likely..."); (< 0.60) explicit uncertainty + proposed resolution ("I'm not sure — want me to look it up?").
- Confidence sources: source count, source recency, skill success rate (from observability #13), LLM self-assessment calibrated against golden set (#14).
- For hard failures: state what failed, what was attempted, what the user can do. Never: "An error occurred."
- ❌ Hedging everything regardless of confidence (cry-wolf effect); no hedge when confidence is genuinely low; conflating "I don't know" with "I can't do that" (different messages).
- Ref: epistemic humility and uncertainty expression in LLM output design

---

#### B. Persona and Identity Persistence

**#25 (B6) Persona anchoring**
- Identity block structurally separated in system prompt with a clear header (`# IDENTITY AND VOICE`). Always first. Never merged with capability instructions or tool definitions.
- Content: (1) name + one-sentence framing, (2) three behavioral examples as mini-dialogues (showing, not telling), (3) one line per mode mapping: conversational / operator / report.
- End-of-system-prompt identity reminder (1–2 sentences) exploits transformer recency bias — especially effective in long sessions and after context summarization.
- ❌ Mixing identity with operational rules; descriptors only ("be warm") with no behavioral examples; identity block appearing after tool definitions or at the bottom of the prompt.
- Ref: system prompt identity architecture in production AI assistants

**#26 (B7) Persona drift detection**
- `BackgroundReview` periodic check every 10–15 turns: sample last 3 assistant responses, compare tone and framing against SOUL.md behavioral examples using a lightweight LLM-as-judge pass (~100 tokens).
- Drift triggers: emotional or high-pressure conversation, multiple corrections in succession, multi-tool execution session, context compression event.
- Correction: inject identity reminder at end of next system prompt composition. Do not reset the conversation.
- Context compression (long-history summarization) must include a behavioral patterns section, not only factual content.
- ❌ No drift detection at all; resetting the system prompt on drift (disrupts user mental model); drift check on every turn (cost sink); treating drift as a bug not a signal.
- Ref: persona drift research in long-context LLM systems

**#27 (B8) Voice and tone consistency across modes**
- Three parameters defined per response mode in SOUL.md: lexical density (information per sentence), hedging level (how much qualifying language), warmth markers (specific phrases from Xochitl's voice).
  - CONVERSATIONAL: medium density, low hedging, warmth markers on.
  - OPERATOR: high density, no hedging, warmth markers off.
  - REPORT: high density, minimal hedging, warmth markers off, headers required.
- "Warmth markers" are specific phrases that are Xochitl's own — not generic friendliness, but defined examples in SOUL.md.
- ❌ Defining mode as a single adjective ("be concise"); undefined warmth markers (tone becomes generic LLM voice); allowing density to vary within a single response.
- Ref: conversational AI tone design and mode consistency research

---

#### C. Relationship Building

**#28 (C9) Progressive personalization milestones**
- 3–4 milestones based on session count loaded from config:
  - M1 (sessions 1–5): formal, minimal assumptions, no proactive anticipation.
  - M2 (sessions 6–20): reference stored preferences, use first name naturally, in-session follow-ups enabled.
  - M3 (sessions 21+): natural memory reference active, anticipation gate on, milestone-aware brief format.
- Milestone transitions are silent — log internally, never announce to user ("We've been working together for 20 sessions!" is wrong).
- ❌ Announcing milestones; jumping to M3 behaviors too early; milestone as a counter with no behavioral differentiation between levels.
- Ref: progressive trust and personalization design in AI assistants

**#29 (C10) Implicit preference learning**
- Four safe signal classes only (avoid over-inference): (1) rephrased query → original framing missed → note preferred framing, (2) ignored suggestion → negative preference signal, (3) reformulated output → user edited Xochitl's text → store direction of change, (4) timing → notably longer-than-average pause before command = deliberation detected.
- Confidence decay: `confidence *= 0.95` per session without reinforcement. Prune preferences below 0.3.
- Reveal through behavioral change only, not announcements. "I've learned you prefer X" is wrong — just do X.
- ❌ Storing raw conversation chunks as preferences (unstructured); announcing learned preferences; high confidence from a single observation; never decaying preferences over time.
- Ref: implicit preference learning in LLM personalization systems

**#30 (C11) Graceful correction handling**
- Three-step pattern: (1) minimal acknowledgment ("Got it" / "Right" — no over-apology), (2) apply correction immediately in next output, (3) store to preference log if recurring (same correction type ≥ 2×).
- If the same correction recurs without being applied: that's a bug in preference storage or context assembly, not a persona issue.
- ❌ Re-explaining the original (wrong) answer before correcting it; asking "Does this look better?" (forces user to evaluate); "I apologize for the confusion, I should have..." (breaks flow, feels servile).
- Ref: correction handling patterns in conversational AI

---

#### D. CLI-Specific UX

**#31 (D12) Terminal visual grammar**
- Five conventions applied uniformly across all skill outputs: (1) ≤2 semantic colors (green = done/success, yellow = needs attention), (2) prefix chars (✓ done, → action needed, ⚠ warning, ✗ failed), (3) 2-space indent, (4) ≤80 char lines for pipe safety, (5) `--json` flag on all commands for machine-readable output.
- Status lines for long multi-step operations: `[1/3] Fetching forecast... done` — not a GUI progress bar.
- ❌ Rainbow color output; varying indent depths across skills; lines > 80 chars; no machine-readable mode.
- Ref: terminal AI UX conventions and CLI design patterns

**#32 (D13) Session liveness signals**
- Three signals in priority order: (1) **streaming** (words appear progressively — highest-impact, single biggest liveness improvement), (2) **thinking indicator** for operations > 1s ("Looking that up..."), (3) **session continuity cue** at session start ("Continuing from where we left off — you were working on...").
- Without streaming, the CLI feels like a batch job, not a conversation. This is perception-critical.
- Session continuity cue: one line referencing the most recent meaningful event. User opt-out via preference.
- ❌ Batch-return all output; long silences with no indicator; re-introducing Xochitl at every session start (breaks continuity).
- Ref: liveness and presence in terminal-native AI UX

**#33 (D14) Streaming implementation**
- Router `stream=True` path: yield tokens as they arrive from the LLM. Chat loop reads from the generator and prints each token inline.
- Non-streaming outputs (tool calls, DB queries): show a single-line `rich.spinner` while waiting. Clear on completion.
- Order of implementation: (1) streaming in conversational loop first — this is the visible win, (2) skill output streaming second. Don't try to stream atomic tool-call results.
- Rich library: `Console().print(token, end="", flush=True)` for inline streaming; `Live` context for updateable single-line spinners.
- ❌ Attempting to stream atomic tool-call results; showing a progress bar for 1-second operations; no fallback for models that don't support streaming.
- Ref: rich library streaming patterns; LLM streaming UX research

---

#### E. Trust and Transparency

**#34 (E15) Compact reasoning disclosure**
- Format: one-line action summary → result. Multi-step: numbered brief with ✓ / in-progress indicator per step. Full reasoning only on explicit request ("Why?" or "How did you get that?").
- The goal is audit-ability (user can verify what happened), not explanation (user understands every inference). These are different goals with different verbosity levels.
- ❌ Explaining reasoning before showing the result; showing full intermediate tool outputs inline; "Thinking step by step..." prefix on every response.
- Ref: transparency vs. verbosity in agentic AI system design

**#35 (E16) Uncertainty disclosure tiers** *(see #24 — same model, reinforced here as a governance concern)*
- Implement the three-tier model as a named utility in `src/chat.py`: `uncertainty_hedge(confidence: float, text: str) -> str`. Applied consistently across all skill outputs.
- Confidence calibration: run against eval golden set (#14) to check if self-reported confidence correlates with actual accuracy. Recalibrate system prompt wording if systematically over- or under-confident.
- ❌ Hedging regardless of confidence; no hedge when genuinely uncertain; different hedging language per skill (inconsistent voice).
- Ref: uncertainty communication tiers in AI assistant design

**#36 (E17) Capability boundary communication (resolve-and-route)**
- Before attempting any task: (1) classify intent, (2) check `can_handle()` on each skill, (3) if no match: state specifically what's missing with a forward path ("I can search the web but can't execute the code — want me to explain the approach instead?").
- Graceful degradation: if partial handling possible, offer it explicitly and state what's covered. Never silently deliver a reduced version.
- Maintain a capability boundary summary in SOUL.md: what Xochitl can, cannot, and almost-can do. Update when new skills added.
- ❌ Attempting tasks knowing they will fail; generic "I can't do that" without specifics; silently doing a reduced version; hallucinating capability.
- Ref: capability boundary design and resolve-and-route patterns in AI assistants

---

## Cross-cutting findings

1. **Governor-first architecture** — Items 15, 16, 18, and 19 all converge on the same pattern: a single named `Governor` module as the enforcement point for all consequential actions. Implement it before the executor and autonomy layer. Retrofitting is expensive.
2. **Observability enables everything else** — Evals (#14), reflection tuning (#11), governor auditing (#18), and uncertainty calibration (#35) all depend on clean structured logs (#13). Instrument first.
3. **The `$47K loop` failure mode** — The most concrete cautionary example for bounded exploration (#15). Fix is three lines: step counter, hash-based convergence check, hard-stop escalation path. The industry learned this the hard way in Nov 2025.
4. **SSRF is not optional** — pydantic-ai shipped CVE-2026-25580 for exactly this gap in 2026. Fix is a 30-line utility function. Every agent that fetches URLs needs it.
5. **Proactive initiative backfires without a clear policy** — Research (arxiv 2509.09309) shows unsolicited proactive messages reduce system usage and trust. Default to `errors_only`, always make it dismissable. Applies equally to anticipation gate (#21) and controlled initiative (#16).
6. **Anthropic's prime directive for agents**: start simple, add agentic complexity only when simpler solutions fall short. Xochitl's existing tiered router architecture already follows this — preserve it as the foundation for everything above.
7. **Streaming is the single highest-leverage interaction change** — Of all 36 items, streaming (#33) has the largest perceived-quality improvement for the smallest implementation surface: one router parameter, one chat loop change. The JARVIS feeling is built on liveness, and liveness starts with streaming.
8. **Persona and capability are two separate contracts** — Groups 1–6 define what Xochitl can do; Group 7 defines how she shows up. Both matter, but they fail independently. A highly capable agent with a drifting persona feels broken. A warm, consistent persona with no capability feels like a toy. Xochitl needs both tracks progressing in parallel.
9. **Uncertainty tiers are the trust contract** — The three-tier model (#24 / #35) is not a style choice. Users calibrate trust based on how consistently an agent signals its own confidence. Inconsistent hedging is more trust-damaging than consistent under-confidence. Implement once, apply everywhere.
10. **Memory reference must feel incidental, not transactional** — Explicit memory retrieval announcements break the "personal assistant" frame. The JARVIS feeling requires that stored knowledge surfaces naturally, as if Xochitl always knew it about Jason — not as if she looked it up (#23, #29).

---

## Open questions / still exploring

- Are there other repos or articles worth reviewing before locking the plan?
- **Updated priority suggestion** (rough, reflects both Groups 1–6 and Group 7):
  1. **Streaming (#33)** — highest JARVIS leverage, relatively low implementation risk
  2. **SSRF protection (#7)** — security, non-negotiable
  3. **Resilience: retry + rate limiting (#8–9)**
  4. **Tiered governor (#18)** — prerequisite for executor and autonomy layer
  5. **Uncertainty tiers (#24 / #35)** — foundational trust contract, low cost
  6. **Persona anchoring (#25)** — SOUL.md restructure, low code cost, high identity value
  7. **Correction handling (#30)** — quick pattern addition to `chat.py`
  8. **Standards (#1–6)** — apply to new code written for items above
  9. **Exception hierarchy (#10)**
  10. **Bounded explorer (#15)**, **Response modes (#17)**, **Capability boundary communication (#36)**
  11. **Reflection (#11)**, **Observability (#13)**, **Eval harness (#14)**
  12. **Anticipation gate (#21)**, **Persona drift (#26)**, **Implicit preference learning (#29)**, **Progressive milestones (#28)**
  13. **Controlled initiative (#16)**, **Executor (#19)** — highest risk, last
- Response mode switching (#17) is low-code but high-design — worth a direct conversation about what "operator mode" and "report mode" should actually feel like for Jason before implementing.
- Executor (#19) carries the most risk — needs careful governor design complete before touching it.
- Group 7 items B6–B8 (persona) and C9–C11 (relationship) will need a design conversation: what do the milestone boundaries look like in practice for Jason's actual usage patterns?
- Streaming (#33) may surface router architecture choices — is Gemma4 local accessible via a streaming API? Worth a quick spike before committing to CR-031.

---

## Status

**Updated**: 2026-05-25  
**Smoke**: 146 passed, 0 failed (`python smoke_test.py`)  
**Last CR completed**: CR-042 (procedural memory phase 2)

### Completed (exploration items)

All 36 exploration gap items are implemented.

| CR | Item |
|----|------|
| CR-038 | Controlled initiative (renumbered from CR-036 collision) |
| CR-039 | Terminal visual grammar (#31 / D12) |
| CR-040 | Compact reasoning disclosure (#34 / E15) |
| CR-041 | Procedural memory (#12) MVP |
| CR-042 | Procedural memory phase 2: LLM distill, embedding recall, executor |

### Outstanding

None from the original 36-item gap analysis.

### Handoff gotchas (paste at session start)

- Windows cp1252: smoke `test("label", fn)` strings must be **ASCII only** (`>=`, `->`, not Unicode).
- `src/governor.py` = token budget; `src/executor.py` = action permission (`ActionGovernor`); `src/initiative.py` = proactive policy.
- `preferences` table columns: `preference_key`, `preference_value` (not `key`/`value`).
- Capability boundary remains **CR-036**; controlled initiative is **CR-038**.
