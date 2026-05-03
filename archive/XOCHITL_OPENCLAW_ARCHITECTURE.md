# Xochitl OpenClaw Architecture

## Paradigm Shift: From CLI to Agent
Instead of a standalone Python CLI (`xochitl today`, `xochitl plan`), Xochitl will be implemented as an **OpenClaw Agent Workspace**. This optimizes the tool for an IDE-centric, terminal-first workflow while providing advanced agentic capabilities out of the box.

## Core Architecture
1. **Interface**: The IDE Terminal. You start an interactive chat session (`openclaw agent`) rather than running static one-off commands.
2. **Personality (`SOUL.md`)**: Xochitl's persona (calm, structured, encouraging, 🌸) is defined via OpenClaw's `SOUL.md` file, giving it a true assistant feel.
3. **Backend Engine**: OpenClaw acts as the local gateway, orchestrating the local Gemma 4 E4B model, handling conversation context, and managing tool execution.
4. **Tool Abstraction**: The core Python logic for Notion integration and SQLite (`tasks.db`) manipulation are wrapped as **OpenClaw Tools (Skills)** instead of custom CLI commands.

## How the Workflow Operates
1. **Interactive Planning**: 
   - **User**: *"What's on the agenda today?"*
   - **Xochitl**: Calls the `get_queue` tool (Python script querying SQLite), formats the response in character, and presents the top 3 tasks.
2. **Execution & Updates**:
   - **User**: *"I finished the navigation component. What's next?"*
   - **Xochitl**: Calls the `mark_done` tool, updates SQLite, fetches the next highest priority task, and responds.
3. **Automated Syncing**:
   - OpenClaw's built-in `cron` executes the Notion sync logic nightly, proactively notifying you in the terminal (or any connected channel) if tasks have rolled over for 3+ days and asking for instructions.

## Key Benefits
* **Flow State**: You never have to leave the IDE.
* **Proactivity**: OpenClaw allows the agent to reach out to you (via cron/webhooks) rather than waiting for manual CLI triggers.
* **Extensibility**: It trivializes adding new capabilities (like Voice Wake) or connecting to different channels (Discord/Telegram) if preferences change in the future.
* **Model Failover**: OpenClaw natively supports failing over to stronger cloud models if the local Gemma model struggles with a specific complex task breakdown.
