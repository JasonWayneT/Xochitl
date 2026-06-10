# Understanding Xochitl

> A learning guide — not a manual. Written for someone who wants to understand *why* this was built, *how* it thinks, and *what* it cost to build it this way.

---

## What She Is

Xochitl (pronounced *so-CHEEL*) is a personal AI assistant that runs on your own computer. She lives in the terminal — the text-based command window where developers type commands — and her job is to be a personal AI system — JARVIS-inspired: managing tasks, building software alongside you, and remembering who you are and how you work over time.

The name is Nahuatl (Aztec) for "flower." It was chosen deliberately. She has a Latina/Mexican cultural voice — warm, direct, occasionally slipping in a word or two of Spanish. Not the sterile neutrality of most AI tools. A personality.

---

## Why Build This Instead of Using ChatGPT?

This is the first question worth answering honestly, because ChatGPT, Claude, and Gemini are genuinely excellent. So why build something custom?

**Privacy and ownership.** When you type into ChatGPT, your words travel to a data center, get processed by a model you don't control, and the company retains rights to use that data. Everything you tell Xochitl about your projects, preferences, and habits stays on your computer. The only time data leaves your machine is when you explicitly ask her to use a cloud model for something complex — and you know when that's happening.

**She knows your environment.** Every AI conversation with ChatGPT starts from zero. It doesn't know what folder you're in, what project you're working on, what tasks you have open, or what you told it three weeks ago. Xochitl knows all of that automatically. Before every response, she assembles a context package: your current directory, your open tasks, your stated preferences, and relevant memories from past conversations. ChatGPT has a fresh slate every time. Xochitl has a running relationship.

**Cost.** Running a local AI model costs electricity. Running cloud models costs API fees per request. Xochitl routes most work to free local models and saves the expensive cloud calls for the genuinely hard problems. A typical workday costs near zero.

**She can act, not just answer.** Xochitl can read your files, understand your codebase, run commands, manage your Notion tasks, and write code — all within a single conversation. General-purpose AI assistants answer questions. Xochitl does work.

---

## How She Thinks: Two Brains, One Decision

Xochitl doesn't use a single AI model. She uses a tiered system — two brains that handle different kinds of work.

**The local brain** runs entirely on your computer using a technology called Ollama. At boot, Xochitl detects how much GPU memory your machine has and automatically selects the best models for your hardware — no configuration needed. A workstation with 20+ GB gets large reasoning models; a laptop with 8 GB gets leaner but still capable ones. There's also a smaller "router" model whose only job is to read your message in milliseconds and decide where it should go. Both run offline, instantly, for free.

| Profile | GPU memory | What she picks |
|---|---|---|
| Workstation | 20 GB+ | Large reasoning model (e.g. Qwen3 32B) |
| Desktop | 12–20 GB | Mid-size model (e.g. Qwen3 14B) |
| Laptop | 6–12 GB | Compact model (e.g. Qwen 9B) |
| Minimal | < 6 GB | Lightweight model (e.g. Phi-4 mini) |

**The cloud brain** is called when the task is genuinely difficult — production code, architectural reasoning, interpreting large documents. It routes to Gemini 1.5 Flash by default (1,500 free requests per day). These are the same top-tier models available via API, called only when the local brain isn't the right tool.

**The routing decision** happens before you even see a loading indicator. The router model reads your message, compares it against a set of task categories (file reading, coding, creative writing, simple question, web lookup, etc.), and makes a call. Simple and sensitive tasks go local. Hard problems go cloud.

The trade-off here is real and worth being honest about: local models are good, not always excellent. On complex reasoning tasks, architectural decisions, or long-document analysis, the cloud models are noticeably better. The routing system tries to catch these cases, but it's not perfect. The design philosophy is: local for 80% of the work, cloud for the 20% that needs it. This keeps costs near zero and privacy high without sacrificing quality where it matters.

---

## How She Remembers: Four Kinds of Memory

This is where Xochitl differs most sharply from typical AI assistants. There are four distinct memory systems, each solving a different problem.

### Layer 1 — Preferences

When you tell Xochitl something that should be permanent — "I always want responses in English," "I'm a senior engineer, don't over-explain basics," "my default project is the fitness app" — she stores that in a structured database table. Next session, next week, next month: she already knows. You never repeat yourself.

This isn't magic. It's a simple database row. But the effect, in practice, feels like the difference between a colleague who remembers you and a contractor who asks the same onboarding questions every Monday.

### Layer 2 — Semantic Memory

After conversations, a background process reviews what was said and writes observations to a **LanceDB** vector store at `~/.xochitl/lancedb/` (table `memories`). A vector database stores ideas as mathematical coordinates — think of every concept as a point in a vast abstract space where similar ideas cluster near each other. "I like concise answers" and "keep it brief" would be nearby points even though they share no words.

When you start a new session and ask about your fitness app, Xochitl searches that space for nearby points — past decisions, design choices, preferences — and quietly injects the relevant ones into her thinking before she responds. She's not looking for exact keywords. She's finding similar *meaning*.

The most recent improvement here (called HyDE) solves a subtle problem: your personal notes are written as statements ("I decided to use SQLite because of its simplicity"). When you search with a question ("what database did I choose?"), the mathematical distance between a question and a statement can be surprisingly large, even though they mean the same thing. HyDE works around this by first generating a hypothetical answer — "I chose SQLite for its simplicity and zero-setup nature" — and then using *that* to search. It finds your actual note far more reliably than searching with the question directly.

### Layer 3 — Structured Facts

The newest layer. A second pass in the background learning system extracts structured facts from conversations and stores them with a category (preference, project detail, constraint, goal, skill) and a confidence score from 0–100%. Low-confidence facts are stored but not acted on. High-confidence facts get proactively injected into context. This gives Xochitl a queryable knowledge base — not just a pile of text — so facts can be filtered, searched, and superseded when you change your mind.

### Layer 4 — Procedural Memory (Workflows)

Semantic memory answers *what you know*. Procedural memory answers *how you do things repeatedly*.

When you complete a useful multi-step routine — triaging Notion, a weekly review, a research pass — Xochitl can offer to save it as a **workflow**: a named sequence of steps with a trigger phrase, expected outputs, and known failure modes. Workflows live in SQLite (`workflows` table). Recall uses **hybrid search**: keyword overlap plus a **separate** LanceDB table (`workflow_intents`) so workflow triggers are not mixed with personal facts.

In chat:

- Mentioning a trigger can inject a `[PROCEDURAL WORKFLOW]` block into her thinking (guidance, not silent auto-run).
- `/workflow save <name>` distills the current session (local LLM when available, mechanical fallback otherwise).
- `/workflow run <name>` executes each step through the matching skill, with visible step progress.

This is the difference between remembering a fact ("I use PARA") and remembering a procedure ("every Monday I sync inbox, then queue, then brief").

---

## How She Learns: The Background Reviewer

A daemon is a program that runs continuously in the background, invisible to you.

After every conversation turn, Xochitl queues that exchange for review. A background process called BackgroundReview wakes up 30 seconds after the last message (so it never slows down your conversation) and asks: is there anything worth remembering here?

It does this twice. First, a plain-language observation ("User prefers short answers on productivity topics"). Second, a structured extraction that categorizes the fact, assigns a confidence score, and decides whether it meets the 40% confidence threshold to write to the database. Idle chit-chat doesn't pollute her memory. Signals worth keeping make it through.

The trade-off: this background process makes two extra model calls per significant turn. They happen in a separate thread so you never wait for them. But your local GPU is doing extra work for about 30 seconds after each turn. On a 14 GB VRAM system this is acceptable. On weaker hardware it might cause warmth you can feel.

---

## What She Can Do: The Skills

Skills are discrete capabilities Xochitl invokes when a conversation calls for them. They're not separate apps — they're tools she picks up and puts down within a single conversation.

**Zettelkasten.** A structured note-taking system inspired by the card-filing method of German sociologist Niklas Luhmann, who used it to write over 70 books. Xochitl manages a vault of notes with a tag system that prevents sprawl: new tags go into "quarantine" until they've proven useful (used 3 or more times), then graduate to your active taxonomy. The limit of 4 tags per note forces you to be precise rather than tag everything into chaos.

**BMAD Pipeline.** BMAD stands for Business Model, Architecture, and Design. When you want to build something new, you start here. Xochitl walks you through what you're building, who it's for, what the architecture looks like, and what the design constraints are. These answers become formal artifacts that feed everything that comes next.

**Spec-Driven Development.** From BMAD artifacts, Xochitl generates formal requirement documents where every feature gets a traceable ID (like `FR-CORE-001`). Every piece of code generated afterward references these IDs. If something breaks six months later, you can trace the bug back to the requirement, the decision that shaped it, and the original design intent. This sounds bureaucratic and it is — but it's the kind of bureaucracy that saves you from yourself six months from now.

**Code Generation.** Given requirements, Xochitl generates code that cites the requirement it implements. The connection between intention and implementation is explicit and permanent.

**Weather.** Real-time conditions and forecasts via Open-Meteo. No API key needed.

**Web Lookup.** DuckDuckGo-based search and page fetching for live information when local knowledge isn't enough.

**Notion Sync.** Two-way sync with your Notion workspace using the PARA methodology — Projects, Areas, Resources, Archive — for task organization that scales.

**Google Maps.** Directions, turn-by-turn steps, travel time, and nearby places (restaurants, shops, etc.) via Google Maps APIs. Say "directions to downtown" or "find a coffee shop near me." The `get_travel_time()` utility is also used internally by future calendar integration to surface "leave by" reminders.

**Gmail.** Read your inbox, search by sender or subject, open full message bodies, send email, mark as read, and archive — all from the terminal. After any listing, say "read email 2" to open it. Auth is handled once via browser OAuth and saved to `~/.xochitl/google_token.json`.

**Dynamic Skills.** You can teach Xochitl new one-off capabilities, and she'll persist them as reusable skills under `.xochitl/skills/`. If a multi-step process keeps repeating, she may offer to turn it into a dynamic skill — separate from procedural workflows, which are stored as named multi-step routines (see Layer 4).

**Workflow execution.** `WorkflowSkill` runs saved procedures step-by-step when you use `/workflow run` or ask to run a saved routine with a strong intent match.

**Bounded exploration.** `ExplorerSkill` chains read-only file reads and searches with strict step and loop limits — useful for "figure out how this repo is organized" without write permission on every step.

---

## How She Talks in the Terminal

Recent work made the CLI easier to scan and safer to pipe:

- **Visual grammar** — Lines use plain prefixes (`done`, `action`, `warn`, `fail`) and wrap near 80 columns so logs stay readable in narrow terminals.
- **Compact disclosure** — Before a tool runs, you often see one line summarizing the action; results pair that label with the body. Ask "why did you…?" for a fuller expansion without dumping raw tool JSON by default.
- **JSON mode** — `xochitl --json today` (and similar) emit structured output for scripts; interactive `chat` still requires a normal session.
- **Session budget** — A token governor can shift routing toward local-only models as a long session grows, and warn before hard stop.

---

## The Safety Model

Xochitl applies one rule consistently: **reads are automatic, writes require your approval.**

She can freely read files, search your codebase, and inspect directories without asking. The moment an action would change something — write a file, delete something, run a mutating command — she stops, presents a plan, and waits for your explicit go-ahead. No surprises.

Path sandboxing adds another layer. She can only access directories you've explicitly authorized. Your SSH keys, your `.env` files with API credentials, your home directory — none of these are reachable unless you specifically grant access. The boundaries are intentional and firm.

**Action governor.** Beyond chat-level approval, mutating shell commands go through an allowlist executor: reads may be automatic, deletes and non-allowlisted commands are denied or require confirmation. Path traversal in targets is rejected outright.

**Controlled initiative.** She can surface proactive alerts (errors, follow-ups) when enabled, but categories you dismiss repeatedly are suppressed — so helpful nudges do not become notification spam.

---

## Honest Limitations

**Local model quality scales with your hardware.** Xochitl automatically selects the best local model for your GPU. On a workstation with 20+ GB of VRAM, local quality is excellent. On a laptop with 6–8 GB, local models are capable for most tasks but the cloud brain handles the hard ones. The routing system tries to catch these cases, but it's not perfect — sometimes a complex question goes local when it should escalate.

**Speed on first load.** The first time a model is used in a session, Ollama loads it into GPU memory. This takes 5–15 seconds. After that, responses are near-instant. Keeping models warm between sessions eliminates most of this delay after the first use.

**Terminal-only.** Xochitl lives in the command line. This is intentional — terminal interfaces are fast, scriptable, and composable — but it's a real barrier for people who don't work in a terminal daily. A web interface is planned, and the groundwork is already in place.

**Memory is not perfect.** The background learning system can misclassify facts or assign incorrect confidence scores. Retrieval finds the right memory most of the time, not always. Memory feels more like an attentive colleague who occasionally forgets than a perfect database that never errs.

**Context window limits.** Even with history trimming and compression, very long sessions can degrade in quality as older conversation context gets summarized away. This is a fundamental limitation of how language models work, not a bug that can be fully fixed.

---

## Where She's Going

The event bus added recently exists specifically to make a web interface transition smooth. Every significant event during a conversation — routing decisions, skill invocations, model completions, approval gates — now fires a typed event on a thread-safe internal channel.

When the web UI arrives, it subscribes to that channel and renders status indicators, tool call cards, and approval prompts in real time — without needing to reach into the terminal's internals. The terminal interface is just the current subscriber to a system that was designed from the start to serve more.

The architecture is web-ready. The terminal is where she lives today.

---

## Related docs

| Doc | Purpose |
|---|---|
| [README.md](README.md) | Architecture reference, commands, project layout |
| [CAPABILITIES.md](CAPABILITIES.md) | Checklist of verified capabilities |
| [docs/spec/02-requirements-registry.md](docs/spec/02-requirements-registry.md) | Formal `FR-*` requirements |
| [AGENTS.md](AGENTS.md) | SDD rules for contributors and agents |

**Verification (May 2026):** `python smoke_test.py` — 167 passed, 0 failed.
