---
stepsCompleted:
  - step-01-init
  - step-02-discovery
  - step-02b-vision
  - step-02c-executive-summary
  - step-03-success
  - step-04-journeys
  - step-05-domain
  - step-06-innovation
  - step-07-project-type
  - step-08-scoping
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief.md
  - XOCHITL_OVERVIEW.md
  - XOCHITL_IMPLEMENTATION_PLAN.md
  - XOCHITL_BMAD_SDD_IMPLEMENTATION_GAP_ANALYSIS.md
  - XOCHITL_MASTER_ARCHITECTURE.md
  - SOUL.md
  - MEMORY.md
documentCounts:
  briefCount: 1
  researchCount: 0
  brainstormingCount: 0
  projectDocsCount: 6
classification:
  projectType: CLI Agent Framework
  domain: AI Orchestration & Personal Productivity
  complexity: High
  projectContext: Brownfield
  persona: Matriarca
  securityRule: Permission required for writes; read access is open.
releaseMode: phased
workflowType: prd
---

# Product Requirements Document - Xochitl (Matriarca)

**Author:** Jason
**Date:** Sunday, May 3, 2026

## Executive Summary

Xochitl is a local-first, context-aware agentic framework designed to function as a cognitive extension for the user. Operating as a "Matriarca"—an authoritative, strategic, and protective peer—Xochitl bridges the gap between raw data and high-level decision-making. By integrating a deep understanding of the user’s personal history, project management (Notion), and technical methodologies (BMAD/SDD), the framework transforms from a reactive utility into a proactive, "thinking" collaborator that manages sovereignty and executes multi-step strategic plans.

### What Makes This Special

Xochitl differentiates itself through three core technical pillars underpinned by a high-fidelity **Tiered Memory Architecture**:

*   **Augmented Intelligence (The Collaborative Partner):** An inference engine that acts as a semantic sounding board, mapping real-time conversation to an existing knowledge base. It provides synthesis and risk identification rather than simple responses, acting as a "thinking" peer.
*   **Tiered Memory & Heuristic Retrieval:** A robust RAG pipeline and long-term memory architecture that treats digital history as a liquid asset. This system comprises:
    *   **Short-Term Working Memory:** Managed via immutable `context.state` objects and session-based event logs to maintain immediate conversational context and state.
    *   **Persistent Memory:** Database-backed services and User Profile Stores that ensure personalization and conversation continuity survive application restarts.
    *   **Long-Term Multimodal Memory:** A semantic "Memory Bank" (Vector DB/Embeddings) that archives past sessions and media, utilizing automated retrieval to inject relevant historical facts into every turn.
*   **Agentic Orchestration:** A modular, cross-platform autonomous workflow layer capable of navigating APIs (Notion, Gmail) and local system environments to execute complex tasks, such as the autonomous BMAD → SDD → Code pipeline.

## Project Classification

*   **Project Type:** CLI Agent Framework
*   **Domain:** AI Orchestration & Personal Productivity
*   **Complexity:** High (Multi-tier memory management, multi-agent orchestration, system-file autonomy)
*   **Project Context:** Brownfield (Formalizing and expanding an existing codebase for SDD readiness)

## Success Criteria

### User Success
*   **Task Automation:** Success is defined by Xochitl's ability to autonomously navigate and execute multi-step tasks (e.g., Notion sync, strategic planning) with minimal user intervention.
*   **Strategic Collaboration:** Xochitl acts as a peer who pushes back only to prevent errors or offer superior alternatives, ensuring the user stays on the most effective path.
*   **Reduced Cognitive Load:** The user feels a measurable shift from "managing" tasks to "directing" Xochitl's execution.

### Business & Project Success
*   **Reliability:** The primary metric. Zero data loss in the memory tiers and high consistency in tool execution.
*   **Adoption Rate:** Xochitl becomes the daily "first-contact" interface for all project management and strategic thinking.
*   **Modular Utility:** Successful integration of tools (like the BMAD pipeline) as optional, high-value modules rather than core constraints.

### Technical Success
*   **Hybrid Model Orchestration:** Seamless routing between local models (for speed/privacy) and advanced cloud models (for complex reasoning/code generation).
*   **Memory Fidelity:** High-accuracy recall from the Long-Term Memory Bank, ensuring the "expert past self" context is always available.
*   **Modular Integrity:** Tools like the BMAD → SDD → Code pipeline produce high-quality, actionable drafts that serve as solid foundations for further work.

## Product Scope

### MVP - Minimum Viable Product
*   **Tiered Memory System:** Implementation of Short-Term (State), Persistent (DB), and Long-Term (RAG) memory.
*   **Project Management:** Notion integration (PARA methodology) with a 3-item local WIP limit.
*   **BMAD Modular Tool:** A functional pipeline for discovering ideas and generating SDD-ready documentation.
*   **Local-First Chat:** A robust CLI interface with tiered LLM routing.

### Growth Features (Post-MVP)
*   **Online Service Integration:** Gmail/Email summarization and actionable intent extraction.
*   **Research Orchestration:** Automated web search and synthesis capabilities.
*   **Interface Evolution:** Developing a rich UI layer on top of the CLI for better data visualization.

### Vision (Future)
*   **Agentic Delegation:** Xochitl orchestrating a team of specialized sub-agents for complex builds.
*   **Predictive Assistance:** Proactive strategic advice based on long-term memory patterns and project timelines.

## User Journeys

### 1. The Context-Aware Transition (Chat → Execution)
*   **Persona:** Jason, the Visionary.
*   **Opening Scene:** Jason is in a new folder and says, "Xochitl, I have an idea for a tool that helps with X. Let's start the BMAD process here."
*   **Rising Action:** Xochitl doesn't just "talk." She detects the intent, **invokes the File System Tool** to read the current directory, and **switches to the BMAD Module**. 
*   **Climax:** She starts a structured discovery session, using her conversational layer to facilitate while the BMAD module generates the planning artifacts in the background.
*   **Resolution:** The project is scaffolded and documented without Jason ever leaving the conversation.

### 2. The Daily Sync (Context-Driven PM)
*   **Persona:** Jason, the Executor.
*   **Opening Scene:** "Xochitl, what are we doing today?"
*   **Rising Action:** Xochitl recognizes the "status check" intent. She **invokes the Notion Module**, pulls the current WIP items, and compares them against the local `MEMORY.md` to see what actually happened since the last session.
*   **Climax:** She presents the tasks and asks, "I see you made progress on the RAG script last night. Should we mark that off in Notion and pull in the next task?"
*   **Resolution:** Jason is aligned and his systems are in sync with a single sentence.

### 3. The Research-Backed Advisor (Strategic Loop)
*   **Persona:** Jason, the Thinking Partner.
*   **Opening Scene:** "Xochitl, I'm stuck on this LinkedIn strategy. Does this approach actually work with the new algorithm?"
*   **Rising Action:** Xochitl analyzes the strategy in the current chat. She determines her internal knowledge is insufficient and **invokes the Web Research Tool**.
*   **Climax:** She synthesizes the new research with Jason's existing "Brand Growth" project context. She pushes back: "Actually, this approach is outdated; the research suggests X is better for engagement now."
*   **Resolution:** Jason gets expert advice that is both researched and contextually relevant.

### 4. The "Guardian" (System Owner)
*   **Persona:** Jason, the Admin.
*   **Opening Scene:** Jason wants to ensure his "Expert Past Self" context is actually being captured.
*   **Rising Action:** He asks Xochitl for a "Memory Audit." She provides a summary of the latest ingested facts and confirms the status of the persistent database.
*   **Climax:** He notices an old, irrelevant fact. He directs Xochitl to "Prune the session archive for Project Alpha."
*   **Resolution:** The system remains lean and high-fidelity. Jason has full sovereignty over his data.

### Journey Requirements Summary
*   **Intent-Driven Orchestration (The Brain):** A persistent conversational interface (Controller) that intelligently routes requests to specialized modular skills based on real-time context.
*   **Modular Skill Architecture (The Tools):** A library of self-contained modules (Notion Sync, BMAD → SDD → Code, Web Research, File Tools) that can be parameterized and chained.
*   **Context-First Execution:** Environmental awareness (reading local files, checking git state) to ground advice and tool selection without boilerplate user input.
*   **Tiered Memory Integration:** Reliable state management (Sessions), persistence (DB), and semantic recall (RAG) to maintain the "Matriarca" wisdom across all tools.
*   **Proactive Prompting:** Capability to suggest backlog tasks, identify strategic risks, and celebrate completions ("¡Felicidades!").

## Domain-Specific Requirements

### Compliance & Regulatory
*   **Data Sovereignty:** All data remains local and human-readable. No encryption at rest for artifacts or configuration files to ensure the user maintains "Right to Audit" without specialized tools.
*   **Data Purge Policy (Roadmap):** A formal policy for memory expiration and intentional "forgetting" is identified for the post-MVP roadmap.

### Technical Constraints
*   **Persistent Permission System:** Xochitl maintains a persistent registry of authorized directories. Access is granted once per directory and persists across sessions. 
*   **Revocation Mechanism:** A specific command/tool must exist to prune or revoke directory access from the registry.
*   **JIT (Just-In-Time) Memory Loading:** To optimize token usage and maintain high-fidelity reasoning, the RAG pipeline must prioritize JIT retrieval. Only contextually relevant "memory fragments" are injected into the context window, regardless of total model capacity.

### Integration Requirements
*   **Transaction Logging:** Every tool execution, system-file read/write, and external API call must be recorded in a robust, human-readable Transaction Log. This ensures accountability for all "Matriarca" actions.

### Risk Mitigations
*   **Permission Gating:** Strict "Permission-on-Write" policy for any system-level changes, even within authorized directories.
*   **Auditability:** The combination of human-readable files and transaction logs allows for immediate user verification if the system behaves unexpectedly.

## Innovation & Novel Patterns

### Detected Innovation Areas
- **The "Matriarca" Paradigm:** Shifting from a generic "Chief of Staff" to an "Expert Past Self" governance layer. The system acts as a custodian of the user's legacy and methodology.
- **Intent-Driven Orchestration:** A persistent "Intelligent Controller" that dynamically invokes modular "Actuators" (Notion, BMAD, etc.) based on environmental context (files, git state, history).
- **Three-Tiered Memory Architecture:** A local-first, high-fidelity memory system combining immutable state, persistent databases, and JIT-retrieved RAG to maintain deep context without overwhelming context windows.

### Validation Approach
- **Internal Dogfooding:** Continuous usage by the primary developer to refine the "Matriarca" persona, test proactive task predictions, and validate the modular skill transitions.
- **Iterative Refinement:** Direct feedback loops between system performance (reliability/adoption metrics) and architecture adjustments.

### Risk Mitigation
- **Fallback to Directives:** If the "Matriarca" advice or prediction misses the mark, the system maintains a robust "Directive" mode for explicit command execution.
- **Human-in-the-loop Validation:** Every autonomous action and system-level write requires explicit user permission, mitigating the risk of incorrect "expert" decisions.

## CLI Agent Framework Specific Requirements (Final Master Blueprint)

### 1. The 5-Tier Memory Hierarchy
Xochitl utilizes a tiered retrieval strategy to ensure accuracy and low-latency performance:

| Tier | Type | Storage | Persistence | Latency | Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0** | **Interaction** | Process RAM | Session-only | ~0ms | Active conversation state and "sticky notes." |
| **1** | **Profile** | `config.toml` | Permanent | <10ms | Static identity, user preferences, and keys. |
| **2** | **Knowledge** | Local Markdown | Permanent | <100ms | App-Agnostic Source of Truth. Includes directory summaries. |
| **3** | **Long-Term** | Vector DB | Permanent | 500ms+ | Semantic search/embeddings for "meaning-based" recall. |
| **4** | **Deep Research**| Agentic Search | Ephemeral | 5s+ | Live web research or multi-turn reasoning loops. |

### 2. Operational Workflows (The "Snappy" Engine)
*   **Small Model Gatekeeper:** A fast-inference model (e.g., Gemma 2B) performs intent classification. Routine CLI tasks skip Tier 3 and 4 entirely.
*   **The Reranking Protocol:** After a Tier 3 vector search, a lightweight cross-encoder (e.g., Qwen3-Reranker-0.6B) reranks the top 10 results. Only the top 3 highest-signal snippets are passed to the primary model. (Adds ~50ms but eliminates retrieval noise).
*   **Asynchronous Ingestion:** 
    *   **Write-Ahead Logging (WAL):** New facts are written immediately to local Markdown.
    *   **Background Embedding:** A worker monitors the file system for `on_move` or `on_delete` events to keep the Vector DB synced and healthy.
*   **Safety Confirmation Gate:** Any agentic action that modifies the file system or executes a "High-Risk" CLI command requires an explicit y/n human confirmation.

### 3. Data Storage & Indexing Strategy
*   **File-Over-App Architecture:** Xochitl treats the local file system as the primary database, independent of third-party apps like Obsidian or Logseq.
*   **Mandatory Metadata Schema:**
    *   `category`: (e.g., work, personal, judo)
    *   `created_at`: (ISO timestamp)
    *   `last_modified`: (To handle "Recency Bias")
    *   `source_path`: (Relative path to the .md file)
*   **Hierarchical Summarization:** Tier 2 includes "Parent" summaries for every directory. Xochitl searches these first to find the right "neighborhood" before diving into specific file chunks.
*   **Recency Bias:** In context conflicts, the system defaults to the most recent data point.

### 4. Technical Stack Recommendation (2026 Local-First)
*   **LLM:** Gemma-4-26B-A4B (MoE) for reasoning; Gemma-4-E2B for the Gatekeeper.
*   **Vector DB:** LanceDB (Embedded, serverless, optimized for local disk-based indexing).
*   **Reranker:** Qwen3-Reranker-0.6B for sub-100ms relevance scoring.
*   **Watcher:** Python `watchdog` or Node `chokidar` for real-time file system integrity.

## Functional Requirements

### 1. Intent-Driven Orchestration (The Brain)
*   **FR1:** The system can classify user input into intent categories using a Confidence Threshold Gate. If classification confidence is below a configurable threshold (e.g., 85%), the system must halt and request manual clarification.
*   **FR2:** The Controller can dynamically invoke and parameterize modular skills based on detected intent.
*   **FR3:** The system can maintain a persistent conversation loop ("Matriarca") while executing background tools.
*   **FR4:** The system can present tool outcomes (e.g., research results, sync status) as an integrated conversational narrative.

### 2. Tiered Memory & Knowledge Management
*   **FR5:** The system can maintain an immutable Working Memory (Tier 0) for active session context.
*   **FR6:** The system can recall and update User Profile Preferences (Tier 1) at the start of every session.
*   **FR7:** The system can index and retrieve context from a Local Markdown Knowledge Base (Tier 2).
*   **FR8:** The system can perform semantic similarity searches across a Vector DB (Tier 3).
*   **FR9:** The system can Rerank retrieval results (e.g., using Qwen3-Reranker) to ensure high-signal context injection.
*   **FR10:** The system can automatically Archive and Ingest chat sessions back into Tier 2 Markdown files.
*   **FR11:** The system can execute a Verify-on-Call Protocol at the moment of retrieval, validating the hash and location of a file. If the file has moved or changed, the index must update dynamically before context injection.

### 3. Project & Task Management (Notion Sync)
*   **FR12:** The system can maintain a Local State Cache that mirrors the Notion PARA structure. All primary logic must run against this cache to minimize API latency, with a background process handling bi-directional sync.
*   **FR13:** The system can enforce a configurable WIP limit (e.g., 3 items) on the local task queue.
*   **FR14:** The system can push task completion status and progress notes back to Notion via the sync process.
*   **FR15:** The system can suggest tasks from the "Backlog" when a WIP slot becomes available.

### 4. Modular Development Pipeline (BMAD/SDD)
*   **FR16:** The system can facilitate a Discovery Session to capture business ideas and project intent.
*   **FR17:** The system can generate Product Requirements (PRD) and SDD files based on discovery sessions.
*   **FR18:** The system can review local code against established SDD specifications.
*   **FR19:** The system can draft code refactors or initial scaffolding based on the BMAD/SDD pipeline.

### 5. Research & Augmented Intelligence
*   **FR20:** The system can identify knowledge gaps and execute a Web Research Mission Budgeting Phase, estimating token and search costs and requiring user approval before execution.
*   **FR21:** The system can synthesize multi-source web data with the user’s local historical context.
*   **FR22:** The system can act as a Strategic Sounding Board using the Adversarial Peer Protocol (Steel-man comprehension, Red Team failure identification, and Pre-Mortem simulation).
*   **FR23:** The system can perform Historical Conflict Detection by querying memory to surface contradictions between current plans and previous project decisions or requirements.

### 6. Security & System Integrity
*   **FR24:** The system can maintain a persistent registry of Authorized Directories.
*   **FR25:** The system can execute Permission-Gated Writes to the local file system.
*   **FR26:** The system can maintain a structured Decision Log recording timestamp, detected intent, tool selection rationale, and specific outcomes in a programmatically parsable format.
*   **FR27:** The system can revoke authorized directory access through a specific command.

## Non-Functional Requirements

### Performance
*   **Tier 1 & 2 Retrieval Latency:** The system shall retrieve local profile and directory summary knowledge in under 100ms for 95% of requests.
*   **Tier 3 Semantic Search Latency:** The system shall return reranked vector search results in under 550ms.
*   **Intent Routing Latency:** The system shall classify user intent and route to the appropriate module in under 500ms.

### Reliability & Data Integrity
*   **Persistence Reliability:** The system shall achieve 100% atomic write success for all session events before attempting background embedding.
*   **State Recovery:** The system shall recover conversational state from the persistent datastore within 1 second upon application restart.

### Security & Sovereignty
*   **Local Execution:** 100% of Tier 0 through Tier 3 data must remain on local disk and never be transmitted to external APIs unless explicitly authorized in Tier 4 operations.
*   **Permission Gating:** The system shall block 100% of write operations outside of the explicitly authorized directory registry and require explicit `y/n` human confirmation for any file modification.
*   **Auditability:** Every tool execution and system-file read/write must be recorded in a human-readable Transaction Log within 100ms of occurrence.

### Risk Mitigation & Constraints
*   **FR12 (Bi-directional Sync) - State Conflict:** The system shall treat Notion as the "Archive" and the local persistent datastore as the "Master." All synchronization collisions must be resolved in favor of the local cache.
*   **FR20 (Research Missions) - Cost/Time Bloat:** The system shall require a "Time to Complete" estimate during the budgeting phase to prevent CLI hangs exceeding user-defined thresholds (e.g., 5 minutes).
*   **FR26 (Decision Log) - Log Fatigue:** The system shall output the transaction log in structured JSONL format to enable simplified, grep-based auditing via a standalone 'Xochitl-Audit' utility.

## CLI Implementation Requirements

### Command Structure
*   **Interactive Mode:** The primary interface is a persistent, interactive chat loop invoked via `xochitl`.
*   **Directives:** The system supports CLI flags for one-shot execution (e.g., `xochitl --task "Sync Notion"` or `xochitl --bmad`).
*   **Administrative Commands:** The system provides built-in slash commands within the interactive loop (e.g., `/audit` for memory review, `/revoke` for directory permission revocation).

### Output Formats
*   **Standard Output:** The system shall render rich, conversational Markdown to `stdout` for human consumption.
*   **Structured Output:** The system shall output all transaction logs and programmatic artifacts in JSON/JSONL format to support downstream script processing.

### Config Schema
*   **Profile Configuration:** User preferences and persistent identity shall be defined in `~/.xochitl/config.toml`.
*   **Environment Variables:** API keys and sensitive operational thresholds shall be managed via `.env` files (e.g., `OPENAI_API_KEY`, `WIP_LIMIT`).
*   **State Cache:** Local synchronization state shall be maintained in a local SQLite database (`~/.xochitl/state.db`).

### Scripting Support
*   **Pipelining:** The CLI must support `stdin` and `stdout` pipelining to allow integration with existing bash/powershell scripts (e.g., `cat input.txt | xochitl --summarize`).
*   **Exit Codes:** The system must return standard exit codes (0 for success, non-zero for failures) to enable automated workflow halting.

## Project Scoping & Phased Development

### MVP Strategy & Philosophy

**MVP Approach:** Experience & Reliability MVP. Focusing on a snappy, expert-level local assistant that acts as a cognitive extension.
**Resource Requirements:** Solo developer (Jason) with advanced local-first AI stack.

### MVP Feature Set (Phase 1)

**Core User Journeys Supported:**
- The Context-Aware Transition (Chat -> Execution)
- The Daily Sync (Context-Driven PM)
- The "Guardian" (System Owner)

**Must-Have Capabilities:**
- **Intent-Driven Controller:** Gemma-4-E2B for intent classification and modular tool routing.
- **5-Tier Memory Hierarchy:** T0-T4 implementation as defined in the Master Blueprint.
- **Reranking Protocol:** Qwen3-Reranker-0.6B integration for high-signal retrieval.
- **Notion PARA Sync:** Bi-directional task management with 3-item WIP limit.
- **BMAD/SDD Pipeline:** Basic requirement generation and project discovery tool.
- **File System Integrity:** Background watcher for source_path consistency.
- **Write-Ahead Logging (WAL):** Human-readable plain-text memory persistence.

### Post-MVP Features

**Phase 2 (Growth):**
- **Online Service Integration:** Gmail/Email summarization.
- **Hierarchical Summarization:** Automated directory-level summaries for Tier 2.
- **Deep Research:** Multi-turn agentic reasoning loops for Tier 4.

**Phase 3 (Expansion):**
- **Agentic Delegation:** Orchestrating specialized sub-agents.
- **Predictive Assistance:** Proactive strategic pivots based on long-term patterns.
- **Rich Interface:** Evolution from CLI to GUI.

### Risk Mitigation Strategy

**Technical Risks:** Background embedding worker failure. Mitigation: WAL ensures Markdown is always the Source of Truth.
**Market Risks:** Adoption friction. Mitigation: Direct dogfooding for persona refinement.
**Resource Risks:** Local hardware constraints. Mitigation: Model quantization and JIT retrieval.
