---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/planning-artifacts/architecture.md
---

# Xochitl - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Xochitl, decomposing the requirements from the PRD and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Classify user input into intent categories with a Confidence Threshold Gate (halt if <85%).
FR2: Controller can dynamically invoke and parameterize modular skills based on detected intent.
FR3: Maintain persistent conversation loop ("Matriarca") while executing background tools.
FR4: Present tool outcomes as an integrated conversational narrative.
FR5: Maintain immutable Working Memory (Tier 0) for active session context.
FR6: Recall and update User Profile Preferences (Tier 1) at the start of every session.
FR7: Index and retrieve context from Local Markdown Knowledge Base (Tier 2).
FR8: Perform semantic similarity searches across Vector DB (Tier 3).
FR9: Rerank retrieval results using Qwen3-Reranker for high-signal context injection.
FR10: Automatically Archive and Ingest chat sessions back into Tier 2 Markdown files.
FR11: Execute Verify-on-Call Protocol at retrieval (validate hash and location).
FR12: Maintain Local State Cache (SQLite) mirroring Notion PARA structure as the master source of truth.
FR13: Enforce a configurable WIP limit (e.g., 3 items) on the local task queue.
FR14: Push task completion status and progress notes back to Notion via background sync.
FR15: Suggest tasks from the "Backlog" when a WIP slot becomes available.
FR16: Facilitate a Discovery Session to capture business ideas and project intent.
FR17: Generate Product Requirements (PRD) and SDD files based on discovery sessions.
FR18: Review local code against established SDD specifications.
FR19: Draft code refactors or initial scaffolding based on the BMAD/SDD pipeline.
FR20: Identify knowledge gaps and execute a Web Research Mission Budgeting Phase (token/cost/time estimates).
FR21: Synthesis multi-source web data with the user’s local historical context.
FR22: Act as a Strategic Sounding Board using the Adversarial Peer Protocol (Steel-man, Red Team, Pre-Mortem).
FR23: Perform Historical Conflict Detection to surface contradictions with previous decisions.
FR24: Maintain a persistent registry of Authorized Directories.
FR25: Execute Permission-Gated Writes to the local file system (explicit y/n confirmation).
FR26: Maintain a structured JSONL Decision Log (timestamp, intent, rationale, outcomes).
FR27: Revoke authorized directory access through a specific command.
FR28: Format console and file outputs for maximum human readability (Click/Rich for CLI, organized/IDE-agnostic Markdown for documents).

### NonFunctional Requirements

NFR1: Tier 1 & 2 retrieval latency < 100ms.
NFR2: Tier 3 semantic search latency < 550ms.
NFR3: Intent routing latency < 500ms.
NFR4: 100% atomic write success for session events before background embedding.
NFR5: State recovery from persistent datastore < 1s.
NFR6: 100% local execution for Tiers 0-3 (no data leaks).
NFR7: Strict "Permission-on-Write" policy for all file system modifications.
NFR8: human-readable/parsable JSONL Transaction Log updated within 100ms of occurrence.
NFR9: Bi-directional sync resolves all collisions in favor of the local SQLite cache.
NFR10: Web Research missions must include a "Time to Complete" estimate to prevent CLI hangs.

### Additional Requirements

- Primary Technology: Python 3.x CLI Application (Brownfield).
- Database: SQLite (Primary state database, replaces Markdown WAL for state).
- Vector DB: LanceDB (Embedded, serverless).
- Models: Gemma-4-26B-A4B (Reasoning), Gemma-4-E2B (Gatekeeper/Router), Qwen3-Reranker-0.6B (Reranking).
- Libraries: `click` and `rich` for console UI.
- Coding Standards: Strict PEP 8, mandatory type hints for all function signatures.

### FR Coverage Map

FR1: Epic 2 - Intent classification.
FR2: Epic 2 - Dynamic skill invocation.
FR3: Epic 2 - Persistent conversation loop.
FR4: Epic 2 - Narrative tool presentation.
FR5: Epic 3 - Tier 0 Interaction Memory.
FR6: Epic 3 - Tier 1 Profile Memory.
FR7: Epic 3 - Tier 2 Knowledge Memory.
FR8: Epic 3 - Tier 3 Vector Search.
FR9: Epic 3 - Reranking protocol.
FR10: Epic 3 - Session archiving.
FR11: Epic 3 - Verify-on-Call protocol.
FR12: Epic 4 - SQLite State Cache/PARA.
FR13: Epic 4 - WIP limits.
FR14: Epic 4 - Notion background sync.
FR15: Epic 4 - Backlog task suggestions.
FR16: Epic 5 - BMAD Discovery sessions.
FR17: Epic 5 - PRD/SDD generation.
FR18: Epic 5 - SDD-based code review.
FR19: Epic 5 - Scaffolding generation.
FR20: Epic 6 - Web Research budgeting.
FR21: Epic 6 - Research synthesis.
FR22: Epic 6 - Adversarial Peer protocols.
FR23: Epic 6 - Historical conflict detection.
FR24: Epic 1 - Authorized directory registry.
FR25: Epic 1 - Permission-gated writes.
FR26: Epic 1 - JSONL Decision logging.
FR27: Epic 1 - Access revocation.
FR28: Epic 7 - Human-Centric Presentation.

## Epic List

### Epic 1: Secure Foundation & System Sovereignty
### Epic 2: The Matriarca Brain (Orchestration & Routing)
### Epic 3: Cognitive Extension (Tiered Memory & RAG)
### Epic 4: Strategic Task Management (Notion Sync)
### Epic 5: The BMAD Development Pipeline
### Epic 6: Augmented Intelligence & Research
### Epic 7: Human-Centric Presentation & UX

## Epic 1: Secure Foundation & System Sovereignty

Establish the "Guardian" layer. Users get a secured CLI environment where all actions are logged and file writes are strictly permission-gated.

### Story 1.1: Authorized Directory Registry & Management

As an Admin,
I want to manage a registry of authorized directories,
So that the system knows exactly where it is allowed to operate.

**Acceptance Criteria:**

**Given** the user is in the Xochitl CLI
**When** the user provides a directory path to authorize
**Then** the path is validated (exists and is accessible)
**And** the path is stored in the persistent registry (`~/.xochitl/config.toml`)

**Given** an existing authorized directory
**When** the user invokes the revocation command for that path
**Then** the directory is removed from the registry

### Story 1.2: Permission-Gated Write Operations

As a User,
I want the system to ask for explicit confirmation before modifying any file,
So that I maintain absolute sovereignty over my local environment.

**Acceptance Criteria:**

**Given** an agentic action requires a file system write
**When** the target path is NOT within an authorized directory
**Then** the operation is blocked immediately

**Given** an agentic action requires a file system write
**When** the target path IS within an authorized directory
**Then** the system prompts the user for explicit [y/n] confirmation
**And** the write only proceeds if the user enters 'y'

### Story 1.3: Structured JSONL Decision Logging

As a System Auditor,
I want every tool execution and rationale recorded in a structured JSONL format,
So that I can verify the agent's behavior.

**Acceptance Criteria:**

**Given** any tool or agentic action is initiated
**When** the action completes
**Then** a new entry is appended to the JSONL decision log with timestamp, intent, tool, rationale, and outcome.

## Epic 2: The Matriarca Brain (Orchestration & Routing)

Implement the intent-driven controller. The system can now understand user requests and route to the correct tool.

### Story 2.1: Local Intent Routing with Confidence Gating
**Acceptance Criteria:** Gemma-4-E2B identifies intent; confidence < 85% triggers clarification prompt.

### Story 2.2: Dynamic Skill Invocation & Parameterization
**Acceptance Criteria:** Extracts parameters and dynamically calls skill module based on identified intent.

### Story 2.3: Persistent Conversational Narrative Loop
**Acceptance Criteria:** CLI remains responsive during background tasks; outcomes synthesized into Matriarca-persona responses.

## Epic 3: Cognitive Extension (Tiered Memory & RAG)

Build the high-fidelity memory system. Xochitl gains the ability to remember past conversations and project context.

### Story 3.1: 5-Tier Memory Hierarchy Implementation (T0-T3)
**Acceptance Criteria:** T0-T3 loaded within latency targets; 100% local execution for all context.

### Story 3.2: High-Signal RAG with Sub-100ms Reranking
**Acceptance Criteria:** Qwen3-Reranker scores top 10; only top 3 snippets injected into prompt.

### Story 3.3: Automated Session Archiving & JIT Verification
**Acceptance Criteria:** WAL history writing; Verify-on-Call validates location/hash at retrieval.

## Epic 4: Strategic Task Management (Notion Sync)

Integrate the Notion/PARA workflow. Local state and Notion are kept in perfect harmony.

### Story 4.1: SQLite State Cache with Notion PARA Mapping
**Acceptance Criteria:** SQLite mirroring PARA; local cache serves as master source for logic.

### Story 4.2: Configurable WIP Limit & Backlog Suggestions
**Acceptance Criteria:** Blocks new tasks if limit reached; suggests next item when slot opens.

### Story 4.3: Bi-directional Background Sync & Status Pushing
**Acceptance Criteria:** Delta identified and pushed to Notion; local state overrides conflicts.

## Epic 5: The BMAD Development Pipeline

Implement the autonomous project discovery and documentation workflow.

### Story 5.1: Autonomous Discovery Session & Intent Capture
**Acceptance Criteria:** Switches to BMAD module and runs conversational loop for new project ideas.

### Story 5.2: Automated PRD & Architecture Generation
**Acceptance Criteria:** Generates Markdown artifacts in planning folder based on session data.

### Story 5.3: SDD-based Code Review & Scaffolding
**Acceptance Criteria:** Adversarial review against PRD/SDD; drafts initial code structures.

## Epic 6: Augmented Intelligence & Research

Deploy the advanced reasoning and web research capabilities.

### Story 6.1: Research Mission Budgeting & Cost Estimation
**Acceptance Criteria:** Provides token/time/cost estimates before execution of Tier 4 research.

### Story 6.2: Multi-source Synthesis with Historical Context
**Acceptance Criteria:** Injects local memory into research outcomes for unified response.

### Story 6.3: Adversarial Sounding Board (Red Team/Pre-Mortem)
**Acceptance Criteria:** Performs Steel-man, Red Team, and Pre-Mortem analysis on plans.

### Story 6.4: Historical Conflict Detection & Contradiction Alerting
**Acceptance Criteria:** Alerts user if current plans contradict historical project facts.

## Epic 7: Human-Centric Presentation & UX

Establish high-fidelity interfaces for both real-time interaction and produced artifacts.

### Story 7.1: Semantic Console Highlighting & Layout
**Acceptance Criteria:** CLI output uses semantic colors (Rich/Click); complex data uses tables and panels for organization.

### Story 7.2: IDE-Agnostic Organized Documentation System
**Acceptance Criteria:** Generated documents follow consistent heading hierarchy and GFM standards for high readability in any IDE.
