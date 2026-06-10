# Xochitl on Hermes — Implementation Plan

**Goal**: Use Hermes Agent as the conversation/tool foundation. Layer Xochitl's personality,
Notion, Gmail, task queue, and BMAD pipeline on top as Hermes plugins and skills.

**Hermes source**: `C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\zGithub Projects of Interest\hermes-agent-main`  
**Xochitl source** (reference only, do not break): `C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Xochitl`

---

## Before you start — read this

Hermes uses its own plugin system. **Do not modify Hermes core files.** All custom work
goes in `%LOCALAPPDATA%\hermes\` (Windows native) or `~/.hermes/` (WSL2):

```
%LOCALAPPDATA%\hermes\
├── SOUL.md              ← Xochitl's personality
├── USER.md              ← Jason's profile (injected each session)
├── MEMORY.md            ← Persistent memory index
├── config.yaml          ← Model, provider, tool config
├── .env                 ← Secrets (API keys, Doppler fallback)
├── plugins\
│   └── xochitl\         ← All custom Xochitl work goes here
│       ├── plugin.py    ← Plugin entry point (registers tools + hooks)
│       ├── tools\
│       │   ├── notion_tool.py
│       │   ├── gmail_tool.py
│       │   ├── task_queue_tool.py
│       │   └── bmad_tool.py
│       └── requirements.txt
└── skills\              ← Optional: Hermes skill format for reusable procedures
```

---

## Phase 1 — Install & Personality (Day 1, ~2 hours)

**Goal**: Hermes running with Xochitl's voice. Basic conversation works.

### Step 1.1 — Install Hermes on Windows

```powershell
irm https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1 | iex
```

After install: `hermes doctor` to confirm everything passes.

### Step 1.2 — Configure model

Xochitl currently uses Ollama locally (phi4:14b-q4_K_M for primary, gemma2:2b for router).
Hermes supports Ollama as a "custom" provider:

```yaml
# %LOCALAPPDATA%\hermes\config.yaml
model:
  default: "phi4:14b-q4_K_M"   # or whatever model name Ollama uses
  provider: "ollama"
  base_url: "http://localhost:11434/v1"
```

For cloud fallback (complex tasks), add a second profile or use `hermes model` to switch.

### Step 1.3 — Drop in Xochitl's SOUL.md

Copy `C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Xochitl\docs\examples\SOUL.md.example`
to `%LOCALAPPDATA%\hermes\SOUL.md`.

Edit the copy — remove the example header, keep everything from `## [IDENTITY]` down.

### Step 1.4 — Seed USER.md

Create `%LOCALAPPDATA%\hermes\USER.md` with Jason's profile (pull from Xochitl memory file
`user-jason.md` — strip the YAML frontmatter, keep the content).

### Step 1.5 — Smoke test

```bash
hermes
```

Say "hello" — confirm Xochitl's voice comes through. Ask something casual. Confirm the
personality feels right. If the local model is weak, switch to Claude for this test:
`hermes model` → select Anthropic / claude-sonnet-4-6.

**Done when**: Basic conversation works and Xochitl sounds like Xochitl.

---

## Phase 2 — Notion Integration (Day 1-2, ~4 hours)

**Goal**: `notion` tool available in Hermes. Can sync tasks, read pages, push updates.

### Step 2.1 — Create the plugin scaffold

```
%LOCALAPPDATA%\hermes\plugins\xochitl\
├── plugin.py
├── requirements.txt
└── tools\
    └── notion_tool.py
```

`plugin.py` — minimal entry point:
```python
from . import tools  # triggers tool registration on import
```

`requirements.txt`:
```
notion-client>=2.2.1
```

### Step 2.2 — Port NotionSkill → notion_tool.py

Source: `C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Xochitl\src\skills\notion_skill.py`

Hermes tools use OpenAI function-calling format. Wrap the existing Notion logic:

```python
from agent.tool_registry import registry   # Hermes tool registry

@registry.register(
    name="notion",
    description="Read and update Notion pages, databases, and tasks (PARA methodology).",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_tasks", "get_page", "update_task", "create_task", "sync"],
                "description": "What to do"
            },
            "query": {"type": "string", "description": "Search query or page title"},
            "task_id": {"type": "string", "description": "Notion block/page ID"},
        },
        "required": ["action"]
    }
)
def notion_tool(action: str, query: str = "", task_id: str = "") -> str:
    # Port logic from NotionSkill.execute() here
    ...
```

Key methods to port from `notion_skill.py`:
- `_list_tasks()` → maps to `action: "list_tasks"`
- `_sync()` → maps to `action: "sync"`
- `_get_page()` → maps to `action: "get_page"`

**Secrets**: Add to `%LOCALAPPDATA%\hermes\.env`:
```
NOTION_TOKEN=your_token_here
NOTION_DATABASE_ID=your_database_id_here
```

(Or pull from Doppler — run `doppler secrets download --no-file --format env >> .env` once.)

**Done when**: "What tasks do I have in Notion?" triggers the tool and returns results.

---

## Phase 3 — Gmail Integration (Day 2, ~3 hours)

**Goal**: `gmail` tool available. Can read inbox, search, send.

### Step 3.1 — Port GmailSkill → gmail_tool.py

Source: `C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Xochitl\src\skills\gmail_skill.py`
Auth:   `C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Xochitl\src\google_auth.py`

**Note**: Hermes already has `agent/google_oauth.py`. Check if it covers the same OAuth flow
before re-implementing. If so, reuse it — just write the Gmail-specific tool logic.

Register as `gmail` tool with actions: `inbox`, `search`, `read`, `send`, `mark_read`, `archive`.

**Secrets**:
```
GOOGLE_CREDENTIALS_JSON=<contents of ~/.xochitl/google_credentials.json>
GOOGLE_TOKEN_JSON=<contents of ~/.xochitl/google_token.json>
```

**Done when**: "Check my inbox" shows unread emails. "Send an email to X" works.

---

## Phase 4 — Task Queue (Day 2-3, ~4 hours)

**Goal**: `today`, `done`, `plan` commands work. WIP limit of 3 enforced.

### Step 4.1 — Decide: SQLite vs Notion as source of truth

Two options:
- **Option A** (simpler): Task queue IS Notion. `today` pulls top 3 from Notion database,
  `done` marks them complete in Notion. No local DB needed.
- **Option B** (Xochitl-original): Local SQLite queue with `queue` table (max 3 rows),
  sync to Notion separately.

**Recommendation**: Start with Option A. Less infrastructure, same result.

### Step 4.2 — Port task queue as Hermes skill

Create `%LOCALAPPDATA%\hermes\skills\xochitl-tasks\`:
```
skill.md       ← Hermes skill description (what the skill does, how to invoke it)
scripts\
└── task_ops.py   ← today(), done(), plan() logic calling the notion tool
```

Add slash commands via `hermes_cli/commands.py` extension OR just teach the agent to call
`notion` tool with the right params for `today` / `done` / `plan` phrases.

**Done when**:
- "What's on my plate today?" → returns top 3 tasks from Notion
- "Done with task 1" → marks it complete
- WIP never exceeds 3 active items

---

## Phase 5 — BMAD → SDD → Code Pipeline (Day 3-5, ~8 hours)

**Goal**: "I want to build X" triggers the full BMAD intake → spec → scaffold flow.

### Step 5.1 — Port as a Hermes skill (procedural)

Source files:
- `src/skills/bmad_skill.py`
- `src/skills/sdd_skill.py`
- `src/skills/code_skill.py`
- `.sdd/prompts/` (LLM prompt templates)
- `.sdd/templates/` (document templates)

Create `%LOCALAPPDATA%\hermes\skills\bmad-pipeline\`:
```
skill.md         ← "Guides user through BMAD intake, generates SDD specs, scaffolds code"
scripts\
├── bmad.py      ← Business model + architecture intake
├── sdd.py       ← Requirements spec generation
└── scaffold.py  ← Code generation from specs
```

### Step 5.2 — Copy the SDD templates

Copy `C:\Users\Jason\Desktop\Jason\Resource\CodeProjects\Xochitl\.sdd\` to
`%LOCALAPPDATA%\hermes\skills\bmad-pipeline\.sdd\` so the prompts and templates travel with the skill.

### Step 5.3 — Register a `bmad` tool

```python
@registry.register(
    name="bmad",
    description="Run a step of the BMAD→SDD→Code pipeline for building new apps.",
    parameters={
        "type": "object",
        "properties": {
            "stage": {
                "type": "string",
                "enum": ["init", "bmad", "sdd", "scaffold", "status"],
            },
            "project_id": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["stage"]
    }
)
def bmad_tool(stage: str, project_id: str = "", description: str = "") -> str:
    ...
```

**Done when**: "I want to build a recipe app" triggers BMAD intake and walks through all stages.

---

## Phase 6 — Polish & Local Model Routing (Day 5+, as needed)

These are quality-of-life improvements, not blockers.

### 6.1 — Local model routing

Xochitl's TieredRouter classifies queries and routes to local vs. cloud.
Hermes supports this via `auxiliary_client.py` (a separate smaller model for classification).

Configure in `config.yaml`:
```yaml
model:
  default: "phi4:14b-q4_K_M"
  provider: "ollama"
auxiliary:
  model: "gemma2:2b"
  provider: "ollama"
  use_for: ["approval", "classification"]
```

### 6.2 — Semantic memory (optional)

Hermes uses FTS5 (text search) for session recall. Xochitl uses LanceDB (vector/semantic).
LanceDB gives better fuzzy recall but adds complexity. Skip for now — add later if FTS5
proves insufficient.

### 6.3 — Zettelkasten / Obsidian tool

Port `src/skills/zettelkasten_skill.py` as a `zettel` tool if needed.

---

## Key reference files in Xochitl (do not delete)

| File | Why it matters |
|---|---|
| `src/skills/notion_skill.py` | Full Notion PARA integration |
| `src/skills/gmail_skill.py` | Gmail OAuth + read/send/archive |
| `src/google_auth.py` | OAuth flow, token refresh |
| `src/skills/bmad_skill.py` | BMAD intake, project init |
| `src/skills/sdd_skill.py` | Spec generation |
| `src/skills/code_skill.py` | Code scaffolding |
| `src/router.py` | TieredRouter — model routing logic |
| `.sdd/prompts/` | LLM prompt templates for BMAD |
| `.sdd/templates/` | Document templates |
| `docs/examples/SOUL.md.example` | Xochitl's personality |
| `src/memory.py` | LanceDB semantic memory (optional port) |

---

## Success checklist

- [ ] `hermes` starts and Xochitl's personality comes through
- [ ] Local Ollama model is the default; can switch to cloud
- [ ] "What tasks do I have?" hits Notion and returns real data
- [ ] "Check my inbox" reads Gmail
- [ ] "I'm done with X" marks the task complete
- [ ] "I want to build Y" starts the BMAD flow
- [ ] No Hermes core files were modified (all work in plugins/xochitl/)

---

## What NOT to port (Hermes already covers it)

- Streaming / conversation loop — Hermes owns this
- Shell command execution (`terminal` tool built-in)
- Git operations (`git` tool built-in)
- Web search / browser (`web_search`, `browser` tools built-in)
- File read/write (`read_file`, `write_file` tools built-in)
- Approval / confirmation FSM — Hermes owns this
- Session history + memory — Hermes owns this
- Cron scheduling — Hermes owns this
