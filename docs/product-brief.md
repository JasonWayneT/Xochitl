---
title: Xochitl Product Brief
status: draft
created: 2026-06-08
updated: 2026-06-08
---

# Xochitl

> A terminal-native personal AI system — local-first, memory-persistent, and built around a tiered routing architecture that keeps local models primary and escalates to cloud only when necessary.

**On pause.** Active development is paused while priority goes to job search and Hermes exploration. The architecture remains a reference point for what Hermes is being built toward.

---

## Executive Summary

Xochitl (pronounced "so-CHEEL") is a personal AI system built on the JARVIS vision: a structured terminal agent that knows who you are, remembers what you care about, and can help build software through a spec-first pipeline. It manages personal tasks via Notion, maintains semantic and procedural memory across SQLite and LanceDB, and uses a tiered LLM routing system that keeps local models primary and escalates to cloud only for high-complexity work.

The project grew to over 167 automated tests, a full skills architecture, and a spec-driven development pipeline for building new applications. Development is currently paused — priority has shifted to job search and exploring Hermes as a plugin-based evolution of the same vision.

---

## The Problem

Most AI assistants are stateless — each conversation starts from zero. They don't know your project context, your personal preferences, your open tasks, or the decisions you made last week. Cloud-first tools require you to push private data to external servers. And none of them have a structured way to use AI to actually build software, not just chat about it.

---

## What Was Built

**Tiered LLM routing.** Three-tier system: a fast local router model (Gemma2 2B) handles classification, a primary local model (phi4 14B) handles most work, a coding model (qwen2.5-coder 14B) handles code tasks. Cloud escalation (Claude, Gemini) only for architecture-level complexity. No API call made that a local model can handle.

**Persistent memory.** Two memory layers: SQLite for task queue, session history, and procedural workflows; LanceDB for semantic memory via vector embeddings. Xochitl remembers what was said across sessions and can retrieve relevant past context by meaning, not just keyword.

**Skills architecture.** Modular skill system: Zettelkasten note processing, BMAD planning, spec-driven code generation, Notion task sync, web research, weather, file operations. Each skill has an explicit can_handle interface — the router dispatches, the skill executes.

**Spec-driven development pipeline.** BMAD → SDD → Code: a structured pipeline for using Xochitl to build new applications. From business model through architecture, requirements, and code generation, with traceability IDs linking every code change to a spec requirement.

**Permission model.** Reads are automatic. File overwrites and deletes require explicit user confirmation. Sandboxed to allowed roots. Every action disclosed before execution.

---

## Architecture Philosophy

The same principles that run through all of Jason's projects:

- **Local-first.** Models run on device. Cloud is an escalation path, not the default.
- **Deterministic over creative.** Structured outputs, constrained LLM calls, explicit permission gates.
- **Grounded, not hallucinated.** Memory retrieval from what exists; the system doesn't invent.
- **Minimal footprint.** WIP limit of 3 tasks. The task queue holds exactly 0–3 rows.

---

## Status

- 167 automated smoke tests passing
- Full skills suite operational: Zettelkasten, BMAD, SDD, Notion, web, weather
- Spec-driven development pipeline used to build multiple internal projects
- Development paused — not abandoned. The architecture and lessons from Xochitl directly inform what Hermes is being built toward.

---

## Portfolio Note

Xochitl is included as a retired project to show the scope and evolution of the work. It demonstrates: building a full Python AI application from scratch, tiered inference architecture, semantic memory systems, and a structured approach to using AI to build software. The skills and architectural patterns it established are what Hermes is built on.
