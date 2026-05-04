# Xochitl — Master Reference Document

**Project:** Xochitl (pronounced "so-CHEEL")  
**Author:** Jason Wayne  
**Version:** 1.1.0  
**Date:** 2026-05-04  

> This document is the single authoritative reference for what Xochitl is, why it was built, how it works, and why every significant architectural decision was made. It is written to be read by a human and explained to another human. It assumes the reader is technically literate but has not seen this codebase before.

---

## Table of Contents

1. [What Xochitl Is](#1-what-xochitl-is)
2. [Why Xochitl Was Built](#2-why-xochitl-was-built)
3. [The Persona — Matriarca](#3-the-persona--matriarca)
4. [System Architecture Overview](#4-system-architecture-overview)
5. [Technology Stack and Why](#5-technology-stack-and-why)
6. [Component Deep Dives](#6-component-deep-dives)
   - [6.1 CLI Entry Point](#61-cli-entry-point--srcclpy)
   - [6.2 Conversational Layer](#62-conversational-layer--srcchatpy)
   - [6.3 Tiered Router](#63-tiered-router--srcrouterpy)
   - [6.4 LLM Interface](#64-llm-interface--srcllm_interfacepy)
   - [6.5 5-Tier Memory System](#65-5-tier-memory-system--srcmemorypy)
   - [6.6 Context Loader](#66-context-loader--srccontext_loaderpy)
   - [6.7 Configuration and Profile](#67-configuration-and-profile--srcconfigpy)
   - [6.8 SQLite Database Layer](#68-sqlite-database-layer--srcdatabasepy)
   - [6.9 Task Manager](#69-task-manager--srctask_managerpy)
   - [6.10 Notion Sync](#610-notion-sync--srcnotion_syncpy)
   - [6.11 Security and Permission Gating](#611-security-and-permission-gating--srcsecuritypy)
   - [6.12 File Tools](#612-file-tools--srcfile_toolspy)
   - [6.13 Tool Registry and Dispatcher](#613-tool-registry-and-dispatcher--srctoolspy)
   - [6.14 Research Module](#614-research-module--srcresearchpy)
   - [6.15 BMAD Module](#615-bmad-module--srcbmadpy)
   - [6.16 Skills Directory](#616-skills-directory--srcskills)
   - [6.17 SOUL.md — The Personality File](#617-soulmd--the-personality-file)
7. [The BMAD → SDD → Code Pipeline](#7-the-bmad--sdd--code-pipeline)
8. [The SDD Traceability System](#8-the-sdd-traceability-system)
9. [Security Model](#9-security-model)
10. [Data Flow — A Request From Start to Finish](#10-data-flow--a-request-from-start-to-finish)
11. [Known Gaps and Roadmap](#11-known-gaps-and-roadmap)

---

## 1. What Xochitl Is

Xochitl is a **terminal-native, local-first AI Chief of Staff**. It runs entirely on your machine as a Python CLI application. You type `xochitl` in a terminal window and it opens a persistent conversation where you can manage tasks, plan projects, read files, sync with Notion, and run a full product-development pipeline — all without leaving your terminal and without your private data touching a cloud server by default.

The name comes from the Nahuatl word for flower. It fits. The system is designed to be the root structure of your entire personal operating system — the thing that everything else grows out of.

Functionally, Xochitl does two things:

**Thing 1: Personal task and project management.** It connects to your Notion workspace and mirrors your projects and tasks locally in a SQLite database. It enforces a strict WIP (Work In Progress) limit of 3 tasks at a time, which is a deliberate productivity constraint: you are only allowed to be working on 3 things simultaneously. When you finish one, it pulls the next one in. Your whole Notion project hierarchy, organized by the PARA methodology (Projects, Areas, Resources, Archives), lives in the local database so everything is instant and offline.

**Thing 2: A guided application development pipeline.** When you want to build something new, Xochitl walks you through a structured process called BMAD (Business Model, Architecture, Design). It collects your ideas through conversation, generates formal planning documents (PRD, architecture docs, user stories), converts those into a Software Design Document with numbered, traceable requirements, and then uses that SDD to generate scaffolded code. Every piece of generated code has a comment pointing back to the requirement that justified its existence. This is the traceability system.

The two functions are not separate products. They are the same system because the same person builds things and manages their work. You use one interface for both.

---

## 2. Why Xochitl Was Built

The problem this system solves is cognitive fragmentation. A person managing multiple projects across different domains — code projects, content projects, admin work, learning — typically has their state scattered across several tools: Notion for tasks, a browser for research, an IDE for code, an AI chat window for thinking. None of these tools know about each other. Every time you switch contexts, you pay a mental tax re-establishing the relevant facts in your head.

Existing AI assistants like Claude.ai or ChatGPT are powerful but stateless by default. They do not remember what you worked on last week, what decisions you made three projects ago, or what your current priorities are. You have to re-explain your situation every time.

Existing project management tools like Notion are excellent for storage and organization but require you to do all the thinking yourself. They hold your tasks but do not help you decide which ones matter most right now, or break down a vague project into concrete 30-minute work chunks.

Xochitl was built to close those gaps by being the single first-contact interface for everything. You open one terminal window in the morning, type `xochitl`, and from that single prompt you can ask what you should be working on, check in on a project's status, get help thinking through a technical problem, generate code, or review a spec. The system knows your history, your priorities, and your working style because it accumulates that information across every session in a local memory system.

The local-first constraint was a deliberate choice, not a compromise. The things you think about, your unfinished projects, your half-formed ideas, your task lists, are private. Sending them to a cloud API as a default is a liability. Xochitl processes everything locally where possible and only escalates to a cloud model when the complexity genuinely requires it (for things like architectural planning or complex code generation), and even then you remain in control.

---

## 3. The Persona — Matriarca

Xochitl does not present itself as a generic AI assistant. It has a specific, documented personality called the Matriarca. This matters because generic AI behavior — hedging every response, apologizing for limitations, using corporate filler language — erodes trust over time. A tool you argue with, or one that constantly reminds you it is an AI, is harder to work with than one that gives you a direct answer and moves on.

The Matriarca persona is defined in a file called `SOUL.md` in the project root. This file is loaded into the system prompt of every single LLM call. Key characteristics:

- **Direct and strategic.** She gives you the answer first, then offers options. She does not redirect you to strategy when you asked for information.
- **Not a yes-man.** She provides a 360-degree view. When you have a bad idea, she says so and explains why, then suggests a mitigation.
- **Light code-switching.** She uses simple Spanish phrases naturally — *claro*, *fíjate*, *ay no* — the way someone would who grew up around the language. This is calibrated carefully: 90-97% English, one phrase at a time, never forced. The purpose is to give her a distinct voice that does not sound like every other AI product.
- **No AI filler.** Hard rules. No "As an AI", no "Great question!", no em dashes, no transition words like "Furthermore" or "Moreover". These phrases signal that you are talking to a machine producing template text. The Matriarca sounds like a person.

The `SOUL.md` file is the single source of truth for voice and behavior. Any code that configures LLM calls reads it from disk at runtime. If you want to change how Xochitl sounds, you edit `SOUL.md` and the change is live on the next session. No code changes needed.

---

## 4. System Architecture Overview

The architecture can be understood as three concentric layers:

**Layer 1 — The Interface.** The user types into a terminal. The CLI (`cli.py`) receives the input and hands it to the conversational layer (`chat.py`), which maintains conversation history and drives the interaction loop.

**Layer 2 — The Brain.** The conversational layer routes each message through the TieredRouter (`router.py`). The router classifies the intent of the message (is this a task management question? a file operation? a BMAD workflow? a simple question?) and decides which model tier to use (local fast model, local reasoning model, or cloud model). All LLM calls flow through a single interface module (`llm_interface.py`) that knows how to talk to both Ollama (local) and cloud providers (Gemini, Anthropic).

**Layer 3 — The Tools.** Once the router decides what kind of response is needed, it either answers directly from its context window or invokes a tool. Tools are Python functions registered in `tools.py`. Each tool handles a specific domain: task management, Notion sync, file operations, memory operations, BMAD pipeline operations, research. The tool dispatcher calls the right function, gets a result, and the conversational layer wraps that result in a Matriarca-voice response.

Underneath all of this runs the memory system — a five-tier hierarchy that pulls relevant context into every LLM call — and the security system, which gates every file write behind an explicit user confirmation.

```
User Input
    ↓
cli.py (command routing)
    ↓
chat.py (conversation loop, history management)
    ↓
router.py (intent classification, model selection)
    ↓
llm_interface.py (Ollama / Gemini / Anthropic)
    ↓
tools.py (dispatcher → task_manager / notion_sync / memory / security / skills / research)
    ↓
database.py / memory.py / security.py (state layer)
```

---

## 5. Technology Stack and Why

### Python 3.12+

Python was the only real choice for this kind of project in 2026. The LLM ecosystem — Ollama, LanceDB, the Anthropic SDK, the Google Generative AI library — is Python-native. The tooling, the documentation, the example code: everything assumes Python. Using any other language would mean fighting the ecosystem at every step.

### SQLite (via `sqlite3` stdlib)

SQLite is the local database. It stores every project, task, area, resource, conversation session, token usage record, and audit log entry.

**Why not Postgres?** Postgres requires a running server process. This is a solo-user local tool. Installing, configuring, and running a database server in the background is unnecessary operational complexity. SQLite is a file. It is always there, it starts instantly, it survives machine restarts without a service manager, and it is zero configuration.

**Why not just Markdown files?** The original spec for this project considered a "Markdown WAL" (Write-Ahead Log) approach where all state was written to human-readable markdown files. This was dropped during the architecture review because it creates correctness problems: two processes could race to write the same file, conflict detection becomes a string-matching exercise, and querying across multiple files for things like "all tasks sorted by project priority" requires loading and parsing every file. SQLite gives you atomic writes, foreign key constraints, and proper queries at no extra cost.

**Why SQLite and not a document database like MongoDB?** The data here is fundamentally relational. Tasks belong to projects. Queue positions reference tasks. Sessions reference token records. The PARA model (Projects, Areas, Resources) maps directly to tables with foreign keys. A document store would require you to re-implement those relationships in application code, which is worse than just using a relational database.

The SQLite file lives at `data/tasks.db` relative to the project root. Foreign keys are enabled (`PRAGMA foreign_keys = ON`) on every connection. The schema uses `TEXT PRIMARY KEY` for IDs because Notion uses UUID-format string IDs and it is simpler to keep everything in the same format.

### LanceDB (Embedded Vector Database)

LanceDB is the vector database used for semantic memory (Tier 3 in the memory hierarchy). It stores embedded representations of past conversation summaries and knowledge base entries, and lets you query them by semantic similarity — meaning you can ask "what do I know about database design?" and it returns the most relevant chunks from your history, not just keyword matches.

**Why LanceDB and not ChromaDB?** This is the specific decision you asked about. ChromaDB is the more commonly referenced embedded vector database in tutorials. LanceDB was chosen for two reasons:

First, LanceDB is genuinely embedded and serverless. It operates as a library, not a server. ChromaDB can run in-process but has a richer dependency tree and was originally designed with a client-server architecture in mind. LanceDB is built from the ground up as an embedded store backed by the Lance columnar format on disk — it is essentially a high-performance file system for vectors.

Second, LanceDB's performance profile is better for this use case. The Lance columnar format is optimized for disk-based random access, which means Tier 3 retrieval (semantic search across potentially thousands of stored memory chunks) stays within the sub-550ms latency budget without requiring everything to be loaded into RAM. ChromaDB's default in-process mode performs similarly for small datasets but degrades faster as the corpus grows.

**Why not Pinecone or a cloud vector database?** Because that would be sending your personal memory to a cloud service. Every conversation you have with Xochitl, every piece of context it stores about your projects and decisions, stays on your machine. A cloud vector database is off the table on principle.

LanceDB files live at `~/.xochitl/lancedb/`.

### Ollama (Local LLM Inference) and LM Studio

Ollama is the local model runtime. It serves language models from your machine via a simple REST API on `localhost:11434`. LM Studio is an alternative local runtime with a GUI; the system supports both and detects which one is running.

**Why local models at all?** For the vast majority of what Xochitl does — classifying intent, answering questions about your tasks, reading files, writing simple summaries — you do not need a frontier model. A local 4B or 26B parameter model running on your GPU handles these tasks quickly, privately, and for free. The cloud models (Gemini Pro, Claude) are reserved for genuinely hard tasks: complex code generation, architectural planning, multi-document synthesis. This split keeps costs low and keeps most of your data local.

### Gemini and Anthropic (Cloud Fallback)

When a task requires cloud-level reasoning, the system routes to either Gemini 1.5 Pro / 2.0 Flash (Google) or Claude (Anthropic). The specific provider is configured via `.env`. Flash variants are used for tasks that need cloud capability but not maximum reasoning depth (most code tasks). Pro variants are used for architecture-level planning.

The system auto-escalates from local to cloud if the local model fails twice consecutively. This is a reliability mechanism: if Ollama is offline or the local model returns garbage, the user still gets a response rather than an error.

### Click (CLI Framework)

Click is the Python library that handles the command-line interface: `xochitl today`, `xochitl done 2`, `xochitl chat`, etc. It is the standard for Python CLI tools. The alternative was Typer (which wraps Click) but Click was already in use and the additional abstraction layer was unnecessary.

### Rich (Terminal Output)

Rich is the library that renders formatted output in the terminal — panels, tables, markdown rendering, colored text, spinners. Without it, everything would print as raw text. Rich is what makes `xochitl` feel like a polished application rather than a script. It also has a `TERM=dumb` detection that degrades gracefully to plain text when running in environments that do not support ANSI escape codes.

### HTTPX (HTTP Client for Notion API)

HTTPX is used for all HTTP calls to the Notion API. It is essentially a modern replacement for the `requests` library with better async support and a cleaner API. The `notion-client` library was considered but HTTPX gives more direct control over pagination and error handling, which matters for the bi-directional sync logic.

---

## 6. Component Deep Dives

### 6.1 CLI Entry Point — `src/cli.py`

**What it does:** This is the front door. Every command the user types goes through here. It defines all the Click commands (`chat`, `today`, `done`, `sync`, `pull`, `plan`, `tasks`, `projects`, `models`) and routes them to the right handler.

**Why it exists as a separate file:** Separation of concerns. `cli.py` knows about commands and flags. It does not know about LLMs, databases, or memory. It imports what it needs from other modules and delegates immediately. This makes it easy to add new commands without touching any business logic.

**How it works:** When you type `xochitl`, the `pyproject.toml` `[project.scripts]` entry points the Python interpreter to `src/cli.py` and calls the `cli` Click group. Each sub-command is a decorated function. The `chat` command, for example, instantiates `XochitlChat` from `chat.py` and calls `.start()`. The `today` command calls `task_manager.fill_queue()` and `task_manager.get_queue_display()` and renders a Rich table. 

One detail worth noting: the CLI defines a custom Rich spinner called `"xochitl"` — a flower blooming sequence using Unicode characters (· ✦ ✿ ❀ ✽). This is the spinner that shows while the LLM is thinking. Small detail but it makes the tool feel intentional.

Implements: FR-ORCH-003 (Persistent Conversational Loop), FR-UX-001 (Human-Centric Output Formatting).

---

### 6.2 Conversational Layer — `src/chat.py`

**What it does:** Manages the interactive conversation loop. It holds the conversation history, detects skill invocations, handles file permission requests, and wraps all tool results in Matriarca-voice text.

**Why it exists as a separate file from `cli.py`:** The CLI is about commands. The chat layer is about the ongoing conversation state — the history, the current project context, the pending file operations. These concerns are different enough to warrant separation. `cli.py` starts things; `chat.py` runs things.

**How it works:** When `XochitlChat.start()` is called, it enters a while loop that:

1. Displays the WIP dashboard header (current queue status).
2. Reads user input via Rich's `Prompt.ask`.
3. Handles slash commands (`/quit`, `/help`, `/revoke`, `/memory`, etc.) directly without going to the LLM.
4. Checks if the input looks like a skill invocation (BMAD, research, SDD commands) and surfaces it with a confirmation prompt.
5. Routes everything else through the TieredRouter.
6. Receives the LLM response, renders it as Markdown via Rich, and loops.

The conversation history is maintained as a list of `{"role": "user"/"assistant", "content": "..."}` dicts. This is the standard format for most LLM APIs. The history is persisted to SQLite in the `sessions` table so it survives restarts.

Three Spanish vocabulary constants at the top of the file mirror SOUL.md's vocabulary palette:
- `_OK = "Claro"` — success/acknowledged
- `_FYI = "Fíjate"` — informational flag
- `_ERR = "Ay no"` — error/blocked

These are used to prefix tool outcome messages, keeping the persona consistent even in programmatic responses.

Implements: FR-ORCH-004 (Tool Outcome Narrative), FR-UX-001, FR-UX-002.

---

### 6.3 Tiered Router — `src/router.py`

**What it does:** The brain of the routing system. Given a user message and conversation history, it classifies the intent, selects the appropriate model tier, builds the right context, and returns an LLM response.

**Why this is the most important module:** Every user message passes through here. The quality of the routing decision determines whether the response is fast and cheap (local) or slow and capable (cloud), and whether the relevant context gets injected. A bad routing decision either wastes money (sent a simple question to a cloud model) or produces a bad response (sent a complex reasoning task to a 4B parameter local model).

**How it works:**

The router first runs `_fast_classify()` — a deterministic keyword matcher that checks for obvious patterns without making an LLM call. If the message starts with "sync" or "pull", it is a `notion_sync` intent. If it mentions "build" or "new project", it is a `bmad_workflow` intent. Fast classification is O(1) and adds no latency.

If fast classification cannot determine the intent, it falls back to `_classify()` — an LLM call to a small, fast local model (configured as `ROUTER_MODEL`, defaulting to `gemma2:2b`) with a structured classification prompt. This model returns a JSON object with an intent category and a confidence score.

If confidence is below the configured threshold (default 85%), the router halts and asks the user for clarification instead of guessing. This is the "confidence gating" mechanism from FR-ORCH-001. The threshold is configurable in `~/.xochitl/config.toml` so you can tune it without changing code.

Once intent is classified, the router injects relevant context:
- Task management queries get a live snapshot of the current queue and projects appended to the system prompt.
- File operation queries get the contents of referenced files read and injected.
- BMAD/code queries get the current project's spec context injected.

Then it routes to the appropriate model:
- **Local categories** (simple QA, task management, memory recall, file reads): Local fast model via Ollama.
- **Local specialized categories** (code tasks): Local coding model (Qwen2.5-Coder).
- **Cloud categories** (architecture planning, complex code generation, BMAD): Cloud model.
- **Hybrid**: Tries local first; if local confidence is below 70%, auto-escalates to cloud.

The `TieredRouter` class also handles local model failure recovery. If the local model fails twice in a row (`_consecutive_local_failures >= 2`), it routes everything to cloud until the local model recovers.

Implements: FR-ORCH-001, FR-ORCH-002, NFR-PERF-003.

---

### 6.4 LLM Interface — `src/llm_interface.py`

**What it does:** The single point of contact between Xochitl and every language model. No other module may call an LLM directly — all inference goes through here.

**Why this boundary matters:** If you ever need to change how Ollama calls are structured, switch cloud providers, add streaming support, or change retry behavior, there is exactly one file to edit. Without this boundary, LLM call patterns would be scattered across router, chat, skills, and research modules, and changing anything would require hunting through the whole codebase.

**How it works:**

`call_local()` sends messages to the Ollama or LM Studio REST API. It handles the slight differences in API format between the two runtimes, reads the configured `LOCAL_MODEL` from environment variables, and returns an `LLMResponse` dataclass with `content`, `route`, and `error` fields.

`call_cloud()` sends messages to either the Gemini API (`google-generativeai`) or the Anthropic API (`anthropic`), depending on `CLOUD_PROVIDER` in `.env`. It selects between Pro and Flash variants based on the task category.

`call_with_retry()` wraps both callers with a simple retry loop — two attempts with a short backoff before returning an error response.

`estimate_confidence()` is a heuristic function that reads an LLM's own output and infers how confident the response is. It checks for hedging language ("I'm not sure", "it depends", "I think"), structural completeness, and response length. This confidence score is used by the router's hybrid path to decide whether to escalate a local response to cloud.

All model names are read from environment variables at import time. The defaults are:
- `LOCAL_MODEL`: `gemma4-e4b`
- `LOCAL_THINKING_MODEL`: `gemma-4-26B-A4B-it-GGUF:UD-IQ4_X`  
- `LOCAL_CODING_MODEL`: `qwen2.5-coder:7b-instruct-q8_0`
- `ROUTER_MODEL`: `gemma2:2b`
- `CLOUD_MODEL_PRO`: `gemini-1.5-pro`
- `CLOUD_MODEL_FLASH`: `gemini-2.0-flash`

Implements: NFR-SEC-001 (local execution for Tiers 0–3).

---

### 6.5 5-Tier Memory System — `src/memory.py`

**What it does:** Implements the complete five-tier memory hierarchy. This is the mechanism by which Xochitl is not stateless — it knows things about you across sessions, projects, and time.

**Why five tiers and not just a database?** Different kinds of memory have different access patterns and latency requirements. Active conversation context needs to be zero-latency (it is already in RAM). User preferences need to be fast but persistent (a config file is fine). Keyword-searchable facts need to be under 100ms. Semantic search for meaning-based recall is allowed to take up to 550ms. Deep research involving live web searches can take seconds. A single storage layer cannot satisfy all of these constraints simultaneously. The tier architecture assigns the right storage mechanism to each access pattern.

**How each tier works:**

**Tier 0 — Working Memory (`WorkingMemory` class)**  
In-process Python list. Append-only (immutable once written). Holds every event that happened during the current session: user messages, tool calls, tool results, errors. Lives entirely in RAM and is discarded at session end. Zero latency because there is no I/O. Used to give the LLM a recent event log in its context window.

**Tier 1 — User Profile (`get_profile()` from config.py)**  
The `~/.xochitl/config.toml` file. Contains your name, preferred persona settings, WIP limit, confidence thresholds, model preferences, and the authorized directory registry. Loaded once at startup. Latency is essentially zero after the first read (Python caches the file content). This is where Xochitl remembers that your name is Jason, that you want a WIP limit of 3, and which directories it is allowed to write to.

**Tier 2 — Markdown Knowledge Base (`KnowledgeBase` class)**  
Keyword search over `~/.xochitl/kb/*.md` files. These are markdown documents you or the system write to capture persistent facts: project summaries, architectural decisions, important preferences. The KB class searches them using simple string matching with TF-IDF-style term frequency scoring. The `verify_on_call()` function in `context_loader.py` hashes every KB entry before injecting it into an LLM context window — if the file has been moved or modified since it was indexed, the hash will not match, and the content is flagged as `[STALE]` so the model knows not to rely on it. This prevents the model from confidently citing information that is no longer accurate.

**Tier 3 — Vector Database (`VectorMemory` class)**  
LanceDB semantic search. When you `memorize()` a topic, the text gets embedded by a local embedding model (`nomic-embed-text` via Ollama) and stored as a vector in LanceDB. When you `recall()` a topic, the query is embedded the same way and the closest vectors in the database are returned. After retrieval, the results are reranked by a cross-encoder model (`Qwen3-Reranker` via Ollama) which scores each candidate for relevance to the query. Only the top 3 reranked results are injected into the LLM context. The reranking step is important because vector similarity is not the same as relevance — a document might be semantically close to your query but not actually useful. The cross-encoder catches those cases.

**Tier 4 — Deep Research (`src/research.py`)**  
Live web search and multi-step reasoning. Handled by the research module, not memory.py directly. See section 6.14.

The `read_memory()` function assembles a combined context string from Tiers 1 and 2 for injection into the system prompt on every call. Tier 3 is only queried when the user explicitly asks Xochitl to recall something, because a vector search on every message would exceed the latency budget.

Implements: FR-MEM-001 through FR-MEM-006, NFR-PERF-001, NFR-PERF-002, NFR-REL-001, NFR-SEC-001.

---

### 6.6 Context Loader — `src/context_loader.py`

**What it does:** Assembles the complete system prompt that goes into every LLM call, and compresses long conversation histories before cloud routing.

**Why this is its own module:** The system prompt has several moving parts: the SOUL.md persona definition, the current memory content, the runtime working directory, tool routing examples. Assembling these correctly and efficiently is complex enough to deserve its own module. Keeping context assembly separate from routing logic means you can change how prompts are structured without touching the routing decision code.

**How `build_system_prompt()` works:**  
1. Reads `SOUL.md` from disk (or uses a provided string if mocked in tests).  
2. Reads the current memory state via `read_memory()`.  
3. Appends the runtime location of the project root (so Xochitl knows where it lives and can construct file paths).  
4. Appends tool routing examples — a short lookup table showing the LLM which intent categories correspond to which tools. This primes the model to use tools correctly.

**How `compress_context()` works:**  
Long conversation histories are expensive to send to cloud APIs — more tokens means more cost and slower responses. Before a cloud call, the full history is compressed into a dense packet:
- The last 5 exchanges are kept verbatim (the model needs recent exact context).
- Older exchanges are summarized into bullet points by a heuristic function (no LLM call needed for this).
- Any file paths mentioned in the history are extracted and their contents are injected (so the model has the actual file content, not just a reference to a path it cannot access).
- The BMAD project context (spec documents, requirement IDs) is injected if the query involves a project.

This compression keeps cloud calls within a predictable token budget.

**The Verify-on-Call protocol (`verify_on_call()`):**  
Every Knowledge Base entry has a SHA-256 hash stored in a `.hashes.json` file in its directory. Before any KB entry is injected into an LLM prompt, its current content is re-hashed and compared against the stored hash. If they differ, the content is prefixed with `[STALE]` so the model knows it might be outdated. If the file no longer exists, the entry is silently dropped. This is how Xochitl stays honest about what it knows — it does not confidently cite information that may have changed since it was indexed.

Implements: FR-MEM-007, FR-UX-002.

---

### 6.7 Configuration and Profile — `src/config.py`

**What it does:** Manages all persistent configuration: user profile, model selections, WIP limits, confidence thresholds, research time budgets, and the authorized directory registry. Everything that should survive application restarts and not be hardcoded lives here.

**Why a TOML file instead of environment variables?** Environment variables are appropriate for secrets (API keys, which live in `.env`) and for things that change between environments (dev vs. prod). User preferences like your name, WIP limit, and model choices are persistent personal configuration — they belong in a config file, not in environment variables you have to reset every time you open a new terminal. TOML was chosen because it is human-readable, it is supported by the Python stdlib since 3.11 (`tomllib`), and its structure maps cleanly to Python dicts.

**How the authorized directory registry works:**  
`config.py` maintains a list of paths that Xochitl is allowed to write to. This list lives in `~/.xochitl/config.toml` under `[authorized_directories]`. Separately, there is a hardcoded list of forbidden roots (`.ssh`, `.aws`, `C:/Windows`, `C:/Program Files`, `/etc`, `/sys`, `/proc`) that cannot be added to the authorized list under any circumstances — these are non-negotiable system protection boundaries.

When the system boots, the project root is automatically added to the authorized list. Any other directory must be explicitly granted by the user. This happens either via a configuration command or when Xochitl asks "I need to write to X — authorize this path?" and the user says yes.

Directory revocation is also supported: `FR-SEC-004` — you can remove a directory from the registry, and subsequent write attempts to that path will be blocked.

Implements: FR-SEC-001, FR-SEC-004, FR-MEM-002, FR-TASK-002, FR-ORCH-001, FR-RES-001, NFR-SEC-002.

---

### 6.8 SQLite Database Layer — `src/database.py`

**What it does:** Owns the SQLite schema and all raw query logic. No other module may execute SQL directly — all database access goes through the functions defined here.

**Why this boundary?** The same reason as `llm_interface.py`. Centralizing all database access means you have one place to look when a query is wrong, one place to add a new index, one place to handle schema migrations. If SQL were scattered across task_manager, notion_sync, and chat, changing the schema would require hunting changes across the codebase.

**The schema — what tables exist and why:**

- **`projects`**: Mirrors Notion projects. `id` is the Notion page UUID. Priority, status, description, deadline, last_synced timestamp.
- **`tasks`**: Tasks belonging to projects. Status can be `todo`, `in_progress`, `done`, `blocked`. The `blocked_by` column holds another task's ID — this supports dependency chains (task B cannot start until task A is done). `days_rolled_over` tracks how many days a task has been in the queue without being completed, which triggers rollover warnings.
- **`queue`**: The WIP queue. Contains at most 3 rows (enforced by a CHECK constraint). Each row has a task_id and a position (1, 2, or 3). When a task is marked done, it is removed from this table and `fill_queue()` is called to pull in the next eligible task.
- **`areas`**: PARA "Areas" from Notion — ongoing responsibilities like "Health" or "Finance."
- **`resources`**: PARA "Resources" — reference material, links, notes.
- **`sessions`**: Conversation sessions. Stores the full conversation JSON and an optional context summary. Used for session resumption and for archiving into Tier 2 memory.
- **`token_usage`**: Records every LLM call with route (local/cloud), token counts, and cost in USD. Used by the stats module to show you how much you have spent.
- **`audit_log`**: Append-only log of database operations. Complements the JSONL decision log in security.py.
- **`sync_log`**: Records each Notion sync run with timestamps and counts.

The database connection uses `sqlite3.Row` as the row factory, which means every result is accessible by column name like a dict (e.g., `row["description"]`) rather than by index. All connections are opened as context managers so commits happen automatically on exit and rollbacks happen on exception.

Implements: FR-TASK-001, NFR-REL-001, NFR-REL-002.

---

### 6.9 Task Manager — `src/task_manager.py`

**What it does:** All task and project CRUD operations, queue management, and rollover logic. It is the business logic layer sitting between the raw SQL in `database.py` and the rest of the application.

**How the WIP queue works:**  
`fill_queue()` is the core operation. It looks at the queue table, calculates how many slots are available (WIP limit minus current queue size), and queries the tasks table for the best eligible candidates. Eligibility rules:
- Status must be `todo`.
- The task's project must be `active`.
- The task must not already be in the queue.
- The task must not be blocked by another task that is not yet `done`.

Candidates are ranked by project priority (high → medium → low) then by `created_at` ascending. This ensures high-priority project tasks are always pulled first, and within a priority level, older tasks are worked before newer ones.

**The rollover mechanism:**  
`run_daily_rollover()` increments `days_rolled_over` for every task currently in the queue. When a task has been in the queue for 3 or more days without being marked done, it is flagged as a rollover candidate. The CLI displays these candidates and asks what to do: keep it in queue, delete it, or reschedule it. This is a deliberate friction mechanism — if a task keeps rolling over, something is wrong and you need to decide what.

**Bulk task creation (`create_tasks_bulk()`):**  
When you use `xochitl plan "<project name>"`, the LLM decomposes the project into a list of tasks with estimates and dependency relationships. `create_tasks_bulk()` handles the insertion of these task lists in a single transaction, correctly resolving forward references in the `blocked_by` field (task 3 might be blocked by task 1, but task 1 does not have its ID assigned yet — this function handles that by assigning all IDs upfront before any inserts).

Implements: FR-TASK-001, FR-TASK-002, FR-TASK-004.

---

### 6.10 Notion Sync — `src/notion_sync.py`

**What it does:** Pulls the four PARA databases (Projects, Areas, Tasks, Resources) from Notion into local SQLite, and pushes completed tasks back up.

**Why local-first with Notion as secondary?** Notion's API has rate limits, requires internet access, and introduces ~200-500ms of latency on every call. If the local task queue depended on a live Notion connection, every `xochitl today` command would be a network request. Instead, the local SQLite database is the master copy. Notion is treated as an archive that you sync against periodically — when you explicitly run `xochitl pull` or `xochitl sync`.

**Conflict detection:**  
When pulling from Notion, the sync compares Notion's `last_edited_time` against the local `last_synced` timestamp for each record. If Notion's record was edited after our last sync, there is a conflict. The `on_conflict` callback decides resolution:
- `"pull"` (default): Notion wins, local record is overwritten.
- `"keep"`: Local record wins, Notion change is ignored.
- `"merge"`: For text fields, both versions are concatenated.

NFR-SYNC-001 mandates that local wins in all conflict cases by default. The rationale: you do your real work locally. Notion changes typically come from syncing on another device or from someone else editing a shared workspace — these should not silently overwrite work you have been doing locally.

**Pagination:**  
The Notion API returns results in pages of up to 100 records. `_db_query_all()` handles pagination automatically, following `next_cursor` until `has_more` is false.

Implements: FR-TASK-003, NFR-SYNC-001.

---

### 6.11 Security and Permission Gating — `src/security.py`

**What it does:** Enforces the "Permission-on-Write" policy for all file system operations, and maintains the JSONL decision log.

**Why this module exists as a hard boundary:** File writes are irreversible. Deletes are irreversible. If an LLM hallucinates a file path or misinterprets a user request and the system writes to that path without asking, data can be lost permanently. The security module exists to make that scenario structurally impossible: every write must pass through `security.py`, and every write requires either prior authorization or explicit user confirmation.

**How the permission check works:**  
Every write attempt calls `_is_allowed(path)`, which checks three things:
1. The path is not inside any of the hardcoded forbidden roots.
2. The path resolves to somewhere under one of the user's authorized directories.
3. If the path is outside the authorized list but not forbidden, `RequiresConfirmation` is raised.

`RequiresConfirmation` is a custom exception that `tools.py` catches. When caught, it prompts the user in the terminal with a `y/n` question. If the user says yes, the write proceeds. If no, it is cancelled. The whole flow is synchronous — the conversation loop pauses and waits for the human decision.

**The JSONL Decision Log:**  
Every read, write, directory listing, and permission grant is recorded in `~/.xochitl/decision_log.jsonl`. Each line is a JSON object with timestamp, operation type, path, and details. The log is append-only and is written within 100ms of the operation (NFR-AUD-001). The JSONL format was chosen specifically because it is grep-friendly — you can run `grep "write" ~/.xochitl/decision_log.jsonl` and see every write operation Xochitl has ever performed. You do not need any special tooling to audit it.

The log is the mechanism by which Xochitl maintains accountability. If something went wrong — a file was written somewhere unexpected, a Notion sync pushed data you did not want — you can look at the decision log and see exactly what happened, when, and why.

Implements: FR-SEC-001 through FR-SEC-004, NFR-SEC-002, NFR-AUD-001.

---

### 6.12 File Tools — `src/file_tools.py`

**What it does:** Provides a conversational file operation interface that sits on top of `security.py`. It manages "pending operations" — operations that have been requested but not yet confirmed.

**The pending operation pattern:**  
When the LLM wants to overwrite an existing file, `file_tools.py` creates a pending operation record with a UUID and returns a `pending_permission` status to the conversational layer. The chat layer then asks the user: "I want to overwrite X. Proceed?" If the user confirms, the operation ID is looked up and executed. If the user declines, the pending record is discarded. This two-step pattern makes it impossible for a write to happen without a human decision in between.

New file creation and reads do not require confirmation — only overwrites and deletes. This maps to how a reasonable person thinks about file operations: reading is always safe, creating something new is low-risk, but overwriting or deleting existing work is where you want human oversight.

Implements: FR-SEC-002.

---

### 6.13 Tool Registry and Dispatcher — `src/tools.py`

**What it does:** Defines every tool that the LLM can invoke, and dispatches tool calls to the right Python function.

**How tool use works:** Modern LLM APIs support "tool use" (also called function calling). You provide the model with a list of tools in a structured JSON format — each with a name, description, and input schema. When the model decides to use a tool, instead of generating text it outputs a structured JSON object specifying which tool to call and what parameters to pass. The code then executes that function and feeds the result back to the model, which incorporates it into its next response.

`TOOL_DEFINITIONS` is the list of all tool schemas. There are currently 29 tools covering: queue management, task CRUD, project management, memory operations (memorize, recall, update_core_memory), file operations (read, write, list directory), artifact saving, Notion sync, BMAD pipeline (init project, save artifact, list projects), SDD operations (generate specs, list/get/create/update requirements), issue tracking (create/analyze/close issues), and code generation (scaffold, implement requirement, fix issue, generate tests).

The `dispatch()` function routes a tool name to its handler. All handlers follow the same pattern: they accept a dict of inputs, call the appropriate underlying module function, and return a string result. All exceptions are caught and returned as human-readable error strings rather than crashing the conversation loop.

One important detail in the dispatcher: `security.RequiresConfirmation` is caught separately from general exceptions. When it is caught, the dispatcher prompts the user in-terminal, waits for y/n, and retries the handler with `_confirmed=True` in the input dict if the user approves. This is how the security permission gate integrates with the tool system.

---

### 6.14 Research Module — `src/research.py`

**What it does:** Implements the Tier 4 research capabilities: web research missions with budget enforcement, multi-source synthesis, adversarial sounding board, and historical conflict detection.

**Why research is its own module and not part of tools.py:**  
Research operations are expensive and potentially slow (web requests, multiple LLM calls, vector searches). They also have a specific pre-execution requirement: the user must approve a time estimate before the research begins. Isolating this logic in its own module makes it easier to enforce the budget gate consistently.

**How the research mission works (`run_research_mission()`):**  
1. The research topic is received.
2. A time and budget estimate is generated and presented to the user.
3. The user approves or rejects.
4. If approved, the mission runs within the configured `research_time_limit_minutes` (default 5 minutes). This is a hard stop — if the time limit is exceeded, the mission terminates with whatever results it has so far.
5. Results are synthesized by the cloud LLM into a coherent answer.

**The adversarial sounding board (`adversarial_review()`):**  
When you ask Xochitl to challenge an idea, it uses a two-pass prompt strategy. The first pass generates the strongest case for the idea (steel-manning). The second pass generates the strongest critique (red teaming). The final response presents both and lets you weigh them. This is the "360-degree view" mentioned in the persona section, implemented as a structured prompting pattern.

**Historical conflict detection (`detect_conflicts()`):**  
Before agreeing with a new direction or recommendation, this function queries Tier 3 memory for past decisions related to the same topic. If it finds relevant historical context, it surfaces potential contradictions: "You considered this approach in March and rejected it because of X. Is that constraint still relevant?" This is one of the more technically sophisticated features — it requires a vector search, a cross-encoder rerank, and an LLM reasoning step to determine whether a historical fact is actually in conflict with the current proposal.

Implements: FR-RES-001 through FR-RES-004, NFR-RES-001.

---

### 6.15 BMAD Module — `src/bmad.py`

**What it does:** Project detection logic and legacy BMAD artifact saving utilities. This module is the older, simpler BMAD layer from the original architecture. Most of the active BMAD functionality has been moved into the skills directory.

**How project detection works:**  
`detect_bmad_project()` walks up the directory tree from the current working directory looking for a `.clinerules/` directory, which signals that you are inside a BMAD project. This is how Xochitl knows you are "inside" a project context without you having to tell it every time.

`save_artifact()` saves a generated artifact (PRD, architecture doc, UX spec) to the correct subdirectory under `_bmad-output/planning-artifacts/`, creating the directory structure if needed.

---

### 6.16 Skills Directory — `src/skills/`

**What it does:** Self-contained Python classes that implement the complete BMAD → SDD → Code pipeline.

**Why a skills directory instead of one BMAD module:**  
The pipeline has three distinct phases with different responsibilities. Grouping them into one file would create a 1,000+ line module that is hard to read and modify. Splitting into three classes keeps each phase's logic isolated:

**`BMADSkill` (`bmad_skill.py`):**  
Handles project initialization and BMAD artifact management. `init_project()` creates the directory structure for a new project under `projects/<id>/` with subdirectories for bmad artifacts, specs, source code, and issues. `save_bmad_artifact()` writes business model, architecture, design spec, and constraints documents to the right locations. `is_bmad_complete()` checks whether all four required BMAD artifacts exist — the system will not allow spec generation until all four are present. This is a pipeline gate that enforces the methodology.

**`SDDSkill` (`sdd_skill.py`):**  
Handles requirement management and traceability. `generate_specs_from_bmad()` reads the four BMAD artifacts and uses a cloud LLM to generate a structured requirements document with numbered IDs in the `FR-DOMAIN-NNN` format. `review_traceability()` is the code review function — it scans every source file in a project for `# Implements FR-*` comments and cross-references against the spec. Files with no traceability comments are flagged as "untraced." Requirements that have no corresponding code comments are flagged as "unimplemented." The output is a human-readable audit report.

**`CodeSkill` (`code_skill.py`):**  
Handles code generation. `scaffold_from_specs()` generates the initial application directory structure and boilerplate code from the spec document. `generate_code_for_requirement()` generates the implementation for a specific requirement by ID, always including the `# Implements <ID>` comment. `fix_issue()` reads an issue file, reads the relevant spec sections, and generates a code fix that references both the issue and the spec. `generate_tests()` generates pytest test cases from a requirement's acceptance criteria.

The base `Skill` class (`base.py`) provides shared utilities: reading the project metadata file, locating the projects directory, resolving the spec file path.

The `_yaml_helpers.py` module provides safe YAML loading and dumping for the `.project-meta.yml` files that store project metadata.

Implements: FR-BMAD-001, FR-BMAD-002 (BMADSkill), FR-BMAD-003 (SDDSkill), FR-BMAD-004 (CodeSkill).

---

### 6.17 SOUL.md — The Personality File

**What it does:** Defines every behavioral rule for the Matriarca persona. It is a markdown document that is loaded at runtime into the system prompt of every LLM call.

**Why a flat file instead of hardcoded strings in Python:**  
You can edit `SOUL.md` without redeploying or restarting anything. The next conversation turn picks up the change automatically. Keeping behavioral configuration in a file that a non-programmer can read and edit is a deliberate design choice. You do not need to know Python to tune how Xochitl talks.

**What it contains:**  
The file is divided into sections: Personality and Voice (tone, reading level, what she is and is not), Writing Constraints (the hard rules — no em dashes, no filler phrases, no AI apologies), Strategic Frameworks (JTBD, Opportunity Cost, First Principles, Pareto — tools she uses only when relevant), Spanish Flavor (calibration rules for code-switching), a Spanish Vocabulary Palette table (approved words grouped by situation), and Behavioral Protocols (pushback level, the 360 Check pattern, when to offer follow-ups vs. just answer).

Every rule in SOUL.md was arrived at through iteration. The no-em-dash rule exists because em dashes are a signature of AI-generated text and they were appearing constantly. The "Answer first, offer second" rule exists because an early version of the system would redirect every question into a strategic meta-discussion instead of just showing the task list you asked for.

---

## 7. The BMAD → SDD → Code Pipeline

This is the development methodology baked into Xochitl for building applications within applications. It is designed for when you want to build something new and want to do it rigorously — with documented requirements, traceable code, and a structured discovery process.

**Phase 1 — BMAD (Discovery and Planning)**  

You start a conversation: "I want to build a fitness tracking app." Xochitl detects the `new_project` intent and invokes `BMADSkill.init_project()`, which creates a project directory at `projects/fitness-tracker/` with the following structure:

```
projects/fitness-tracker/
├── .project-meta.yml     ← project ID, name, status, creation date
├── bmad/                 ← BMAD artifacts
│   ├── business-model.md
│   ├── architecture.md
│   ├── design-specs.md
│   └── constraints.md
├── specs/                ← SDD requirements (generated in Phase 2)
├── src/                  ← generated code (Phase 3)
└── issues/               ← bug/feature tracking (Phase 4)
    └── closed/
```

Then a guided conversation begins. Xochitl asks questions to understand the business model (what problem does this solve, who uses it, how does it make money or deliver value), the architecture (what does the technical system look like), the design specs (what does the UI/UX look like, what are the key flows), and the constraints (what are the non-negotiables — must run on iOS, must not require a server, etc.). Each answer is saved as a BMAD artifact file.

**Phase 2 — SDD (Spec Generation)**  

Once all four BMAD artifacts are complete, `SDDSkill.generate_specs_from_bmad()` reads them and sends them to a cloud LLM with a structured prompt asking it to extract formal functional and non-functional requirements. The output is a set of requirement documents in `specs/functional/` with IDs like `FR-AUTH-001`, `FR-DATA-002`, etc., plus a `specs/traceability.json` mapping every ID to the source module that should implement it.

Every requirement has: a description, acceptance criteria in the Given/When/Then format, constraints, a priority level, and a BMAD reference tracing it back to the original planning artifact that generated it.

**Phase 3 — Code Generation**  

`CodeSkill.scaffold_from_specs()` reads the spec documents and generates the initial application skeleton: directory structure, module files, data models, and boilerplate. Every generated code comment includes `# Implements FR-DOMAIN-NNN` linking the code back to its requirement.

`CodeSkill.generate_code_for_requirement()` generates the implementation for a specific requirement. You call it with a requirement ID and it reads the full requirement — description, acceptance criteria, constraints — and generates code that satisfies those criteria.

**Phase 4 — Issue Tracking**  

When bugs arise, `SDDSkill.analyze_issue()` reads the bug description and the relevant spec sections and determines: is this a spec gap (the requirement does not cover this case), an implementation bug (the code does not follow the spec), or a new requirement (this case was never considered)? The analysis guides the fix — if it is a spec gap, the spec must be updated first, then the code.

`CodeSkill.fix_issue()` generates a code fix referencing both the issue ID and the spec requirements it touches.

**The invariant that makes this work:**  
Every piece of code must trace back to a requirement. Every requirement must trace back to a BMAD artifact. You can follow any line of code backwards to the business decision that justified it. This is the traceability system.

---

## 8. The SDD Traceability System

**What it is:** A mechanism for maintaining a documented chain of accountability from business intent to written code. It consists of three artifacts that must be kept in sync:

**`specs/index.md`:** The master ID registry. Every requirement ID in the entire project, with its title, BMAD reference, and implementing module. The domain table shows you at a glance how many requirements exist in each functional area.

**`specs/functional/FR-*.md` and `specs/non-functional.md`:** The spec files. Each requirement gets a full entry: description, acceptance criteria, constraints, and status (Pending or Implemented). The primary module field tells you exactly where to look in the code.

**`specs/traceability.json`:** Machine-readable mapping of every requirement ID to its implementing module(s), status, and BMAD reference. This file is the input to `SDDSkill.review_traceability()` — the automated code review that scans source files and flags gaps.

**The convention that enforces it:**  
Every Python module that implements a requirement must have `# Implements FR-<DOMAIN>-NNN` comments at the file header. The `review_traceability()` function in `SDDSkill` scans all source files for these comments and cross-references them against `traceability.json`. Files with no comments are flagged. Requirements with no code references are flagged.

**How requirements are named:**  
- Functional: `FR-<DOMAIN>-NNN` (e.g., `FR-ORCH-001`, `FR-MEM-003`)
- Non-Functional: `NFR-<DOMAIN>-NNN` (e.g., `NFR-PERF-001`, `NFR-SEC-002`)
- Domains currently in Xochitl itself: ORCH (orchestration), MEM (memory), TASK (task management), BMAD (pipeline), RES (research), SEC (security), UX (presentation)

**The change propagation rule:**  
Any time a requirement changes, is added, or is removed, the change must flow through all three artifacts — the BMAD planning document, the spec file, and the traceability.json — before touching any code. Any time code moves to a different file, the traceability.json module path must be updated immediately.

---

## 9. Security Model

The security model is built on three principles:

**1. Reads are open. Writes are gated.**  
Reading any file inside or outside the authorized directory list is permitted without confirmation. Writing to, overwriting, or deleting any file requires either a pre-authorized path or explicit user confirmation. This is asymmetric by design: reading is low-risk (it cannot cause data loss), writing is high-risk (it can). The gate is only placed where the risk is.

**2. Some paths are absolutely forbidden.**  
`.ssh`, `.aws`, `C:/Windows`, `C:/Program Files`, `C:/Program Files (x86)`, `/etc`, `/sys`, `/proc` — these cannot be written to under any circumstances, even if the user explicitly authorizes them. The check happens in code before the authorization check. This prevents an attacker or a misbehaving LLM from manipulating the user into granting access to sensitive system directories.

**3. Everything is logged.**  
Every read, write, directory listing, permission grant, and permission denial is recorded in `~/.xochitl/decision_log.jsonl`. The log is JSONL (one JSON object per line) for easy grepping. It is written synchronously within 100ms of the operation so that if the process crashes immediately after an operation, the log still captures what happened. You can reconstruct the complete history of what Xochitl touched on your file system from this log.

The decision log is separate from the SQLite audit log table. The SQLite audit log records database-level operations. The JSONL log records file system operations. Both exist because they serve different audiences: the SQLite log is for programmatic querying, the JSONL log is for human inspection in a text editor or terminal.

---

## 10. Data Flow — A Request From Start to Finish

To make the architecture concrete, here is what happens when you type "sync my tasks from Notion" in the chat loop:

1. **`cli.py`** receives the raw string from Click's argument or from the `chat` loop.

2. **`chat.py`** appends the message to conversation history and calls `router.route()`.

3. **`router.py`** runs `_fast_classify("sync my tasks from Notion")`. The keyword "sync" matches the `notion_sync` fast-classify pattern. Confidence is 1.0 (deterministic). No LLM call is made for classification.

4. **`router.py`** calls `build_system_prompt(read_memory())` to assemble the system prompt from SOUL.md and current memory state.

5. **`router.py`** routes to `_route_local()` because `notion_sync` is in `_LOCAL_CATEGORIES`. The local model is called with the conversation history and system prompt. The model outputs a tool call: `{"name": "sync_notion", "input": {}}`.

6. **`router.py`** returns the `LLMResponse` with the tool call embedded.

7. **`chat.py`** detects the tool call and calls `tools.dispatch("sync_notion", {})`.

8. **`tools.py`** routes to `_handle_sync_notion()`, which calls `notion_sync.pull_and_sync()`.

9. **`notion_sync.py`** calls the Notion API (the only external network call in this whole flow), pages through all four PARA databases, compares each record against local SQLite, handles any conflicts, and calls `database.upsert_project()`, `database.upsert_area()`, etc. for each record.

10. **`database.py`** executes the `INSERT OR ... ON CONFLICT DO UPDATE` SQL against `data/tasks.db`.

11. **`notion_sync.py`** returns a stats dict: `{"projects": 4, "areas": 2, "resources": 1, "conflicts": 0}`.

12. **`tools.py`** formats this as a string: "Pulled 4 projects, 2 areas, 1 resource. Conflicts: 0."

13. **`chat.py`** feeds this tool result back to the local model, which generates a Matriarca-voice response: "Synced. Four projects, two areas, one resource — no conflicts. Want me to refresh the queue with whatever's highest priority now?"

14. **`security.py`** logs the sync operation to `~/.xochitl/decision_log.jsonl`.

15. **`chat.py`** renders the response as Rich Markdown and prints it to the terminal.

Total time: ~500ms for the Notion API call, ~200ms for the local LLM response, <50ms for everything else.

---

## 11. Known Gaps and Roadmap

These are documented gaps from the original planning process. They are intentional non-implementation decisions, not oversights.

**Real-time Notion webhooks (currently pull-only):**  
Notion sync is on-demand — you run `xochitl pull` to fetch changes. A webhook-based system would receive Notion changes in real time. This was deferred because implementing a webhook receiver requires either a background server process or a persistent connection, which adds operational complexity to a local tool. The current pull model is simpler and sufficient for solo use.

**Streaming LLM responses:**  
Currently the system waits for the full LLM response before displaying anything. Streaming (showing tokens as they arrive) would eliminate the perceived latency on long responses. Both Ollama and the Gemini/Anthropic APIs support streaming; the `llm_interface.py` already has a `Generator` type hint in the function signature, but the streaming path is not yet wired into the chat loop.

**Background embedding worker:**  
The original architecture planned for a file system watcher (`watchdog`) that would automatically re-embed documents in the Tier 3 vector database when they changed on disk. Currently, embedding is done synchronously when `memorize()` is called. Automatic background syncing of the Knowledge Base is not yet implemented.

**Session continuity across CLI restarts:**  
Conversation history is saved to SQLite per session. But when you close the terminal and reopen it, you start a new session rather than resuming the last one. The database has everything needed to resume — the `sessions` table stores full conversation JSON — but the session resumption logic in `chat.py` is not yet implemented.

**The orchestrator (background autonomous agent):**  
`cli.py` has a `--with-orchestrator` flag that references a background orchestrator mode. This is stubbed — it starts the chat loop with a flag set, but the autonomous background agent that would run tasks independently while you work is not yet implemented. This was a Phase 3 feature from the roadmap.

**Email integration (Gmail):**  
Listed in the PRD as a Growth Feature. Not started. The architecture for it is clear (OAuth2, token stored in `~/.xochitl/`, local model for classification, integration with task manager for actionable emails), but it has not been built.

**Traceability visualizer:**  
The `review_traceability()` function in SDDSkill produces a text report. A richer version would show this data as an interactive table in the terminal using Rich, with color coding for Implemented vs. Pending requirements, and clickable file paths. The data is all there; the display layer is not.

---

*This document was generated from the live codebase and planning artifacts as of 2026-05-04. It reflects the actual implemented state of the system, not aspirational documentation.*
