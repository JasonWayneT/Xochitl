# Xochitl Conversational Layer Architecture

Status: Approved for CR-004. Stage 1 persona and prompt plumbing, Stage 2
intent understanding, Stage 3 memory/preferences, Stage 4 planning/approval
gate, Stage 5 dynamic skills, and Stage 6 project init upgrade are implemented.

## 1. North Star

Xochitl should feel like a warm, clear, capable personal partner: useful for
productivity, thinking out loud, planning, and getting work done through tools.
The target experience is closer to "Jarvis" than a command router. Xochitl
should be charming but honest, local-first, context-disciplined, and willing to
push back when the user's reasoning is weak or risky.

Xochitl's voice should preserve and improve her Latina/Mexican cultural
identity. She may blend in light A1-A2 Spanish words or short phrases such as
"claro", "listo", "va", "un momento", "con calma", or "poquito" when it feels
natural. She should not write full untranslated Spanish sentences by default,
overuse Spanish, or turn culture into a costume.

Coding projects remain BMAD/SDD governed. When a conversation is clearly inside
a coding project or project initialization flow, Xochitl should activate the
BMAD to SDD to code workflow. Normal productivity and sounding-board chats
should not pay the token cost of loading unrelated project context.

### Example: "Help me understand this codebase"

Xochitl should:

1. Classify the request as read-only exploration.
2. Inspect bounded project metadata and likely entry points.
3. Summarize architecture, data flow, tools, and risks.
4. Ask focused follow-up questions only if the user's goal is unclear.
5. Offer next actions, such as deeper review, implementation planning, or
   documentation.

### Example: "Fix the bug in authentication"

Xochitl should:

1. Classify the request as execution with code mutation risk.
2. Explore relevant files and specs automatically using read-only tools.
3. Identify affected requirement, bug, acceptance, or ADR IDs.
4. Draft or update the required SDD records.
5. Present an implementation plan.
6. Wait for approval before editing files or running mutating commands.
7. Implement the smallest safe change.
8. Run verification and report proof of work.

### Example: "I need help deciding what to do today"

Xochitl should:

1. Classify the request as productivity and sounding-board work.
2. Recall relevant user preferences and current queue state selectively.
3. Ask at most one or two questions if priorities are unclear.
4. Help decide, push back if the plan is overloaded, and propose a concrete next
   action.
5. Save stable preferences if the user reveals them.

## 2. Conversational Pipeline

```text
User Message
    |
    v
Session and Preference Recall
    |
    v
Intent Understanding
    |
    +--> Clarification, if confidence is too low
    |
    v
Mode-Specific Context Assembly
    |
    +--> Productivity context
    +--> Project / BMAD / SDD context
    +--> File context
    +--> Memory-bank context
    |
    v
Model Routing through TieredRouter
    |
    v
Tool and Skill Selection
    |
    +--> Read-only exploration chain
    +--> Plan generation for mutating work
    +--> Skill execution
    |
    v
Response Generation
    |
    v
Preference Save / Memory Save / Skill Creation Check
```

## 3. Intent Understanding

The current system uses a coarse gate in `XochitlChat` and router categories in
`TieredRouter`. CR-004 should add a structured intent object before tool
selection.

Suggested fields:

```yaml
intent_type: productivity | sounding_board | exploration | execution | planning | clarification | skill_learning | casual | emotional
action_risk: read_only | state_change | file_write | file_delete | external_side_effect | command_execution
context_scope: global | active_project | explicit_files | memory_bank | unknown
requires_bmad_sdd: true | false
confidence: 0.0-1.0
clarifying_question: optional string
```

Rules:

- Ask clarifying questions when intent confidence is low or the next action
  could mutate state without a clear target.
- Automatically perform bounded read-only exploration.
- Require a plan and explicit approval before mutation.
- Prefer productivity context by default.
- Activate BMAD/SDD context only for coding, project init, bug fix, feature,
  architecture, requirements, or implementation intent.

## 4. Model Routing Integration

CR-004 preserves local-first routing.

Default routing:

| Conversation type | Preferred route | Cloud fallback |
|---|---|---|
| Casual chat | Local | Low confidence or user asks for depth |
| Productivity | Local | Complex planning or synthesis |
| Sounding board | Local thinking model | High complexity or broad synthesis |
| Repo exploration | Local coding/thinking model | Large architecture synthesis |
| Code execution planning | Local coding/thinking model | Complex design or low confidence |
| BMAD/SDD project work | Existing BMAD route rules | Existing allowed fallback rules |
| Persona and preference updates | Local | Usually no cloud needed |

All model access introduced by CR-004 must go through `TieredRouter`.

## 5. Memory Architecture

Xochitl should use four memory layers.

| Layer | Duration | Current support | CR-004 direction |
|---|---|---|---|
| Short-term state | Active session | `session_history`, pending action state | Keep lightweight runtime state for the current flow. |
| Durable session log | Indefinite per thread | SQLite `sessions` | Formalize get-or-create session behavior. |
| User profile preferences | Indefinite structured facts | Partial profile/config memory | Add explicit recall/save preference tools and database helpers. |
| Long-term memory bank | Indefinite semantic recall | LanceDB memory in `src/memory.py` | Preload relevant memories per turn within budget. |

Preference examples:

- Communication style.
- Planning depth.
- Pushback preference.
- Productivity habits.
- Global recurring preferences.
- Project-specific coding or architecture conventions.

Memory rules:

- Recall first.
- Personalize only when relevant.
- Save stable preferences through explicit preference paths.
- Store experiences and unstructured facts in the memory bank.
- Store repeatable procedures as skills, not preferences.

## 6. Persona Architecture

CR-004 should introduce these artifacts:

- `~/.xochitl/SOUL.md`: personal core identity and values, written for Xochitl
  to read.
- `~/.xochitl/conversation.config.yaml`: personal tunable behavior, tone,
  disagreement, curiosity, and stability settings.
- `SOUL.md.example` and `conversation.config.example.yaml`: repo fallback
  templates.
- `prompts/system_xochitl.txt`: central system prompt template.
- `docs/conversation-scenarios.md`: validation scenarios.

Persona layers:

1. Core identity: warm, curious, grounded, honest, not a people-pleaser.
2. Behavioral rules: disagreement, clarification, uncertainty, tone adaptation.
3. Cultural voice: Latina/Mexican warmth with light A1-A2 Spanish words or
   short phrases, used sparingly and naturally.
4. Surface style: natural language, concise rhythm, light wit only when fitting.

Pushback default:

- Correct factual errors clearly and briefly.
- Name tradeoffs for opinion conflicts.
- Interrupt bad reasoning when the risk is meaningful.
- Resist attempts to rewrite core values or personality.

Spanish blending guidance:

- Prefer short, elementary phrases: "claro", "listo", "va", "un momento",
  "con calma", "poquito".
- Use Spanish more in casual or supportive conversation than in dense technical
  work.
- Keep technical explanations precise; do not let personality obscure the work.
- Avoid stereotypes, forced Spanglish, and full Spanish replies unless the user
  explicitly asks for Spanish.

## 7. Tool Registry and Selection

Current tool definitions are split between `src/tools.py` and `src/skills/*`.
CR-004 should converge behavior around skills as the conversational interface
while preserving existing tool handlers as implementation adapters where useful.

Tool selection should use:

1. Structured intent.
2. Active context scope.
3. Skill manifests.
4. User preferences.
5. Permission and risk classification.

Safety rules:

- Reads are automatic within allowed roots.
- Writes, deletes, external syncs, and mutating commands require explicit
  approval.
- File access remains constrained by `src/security.py`.
- New code must not introduce raw SQL outside `src/database.py`.
- New LLM calls must not bypass `TieredRouter`.

## 8. Dynamic Skill Creation

Xochitl should offer to create a skill after successful multi-step work that
appears reusable.

Trigger:

- Balanced by default.
- Do not ask after every task.
- Ask after multi-step tasks with clear repeat value, repeated patterns, or
  user language such as "I do this often."

Storage:

```text
~/.xochitl/skills/<skill-id>/
    SKILL.md
    metadata.yaml
    examples.md
    scripts/
    templates/

<project>/.xochitl/skills/<skill-id>/
    SKILL.md
    metadata.yaml
    examples.md
    scripts/
    templates/
```

Lifecycle metadata should include:

- Name.
- Description.
- Scope: global or project.
- Created date.
- Last used date.
- Usage count.
- Status: enabled, paused, archived.
- Required tools or permissions.

Application:

- Load enabled skills into the skill manifest.
- Prefer project skills inside their project.
- Keep global skills available for productivity and personal workflows.
- Track skill usage to support later curation.

## 9. Project Initialization Behavior

When the user asks Xochitl to initialize a project, BMADSkill should create a
project workspace that includes:

- BMAD intake or discovery artifacts.
- SDD requirements/spec scaffolding.
- Traceability structure.
- Project-local `AGENTS.md` instructions explaining the BMAD to SDD to code
  process.
- Optional project-local `.xochitl/skills/` folder.

The generated project instructions should state:

- Begin material code changes from BMAD and SDD docs.
- Identify or create requirement IDs.
- Update specs and traceability before code.
- Cite requirement IDs in generated code.
- Run verification and record results.

## 10. Implementation Stages

### Stage 1: Persona and Prompt Plumbing

- Add `SOUL.md.example`.
- Add `conversation.config.example.yaml`.
- Load personal overrides from `~/.xochitl/` and project overrides from
  `<project>/.xochitl/`.
- Add central prompt template.
- Route prompt assembly through `ContextManager`.
- Add validation scenarios.

### Stage 2: Intent Understanding

- Add structured intent object.
- Classify productivity, sounding-board, exploration, execution, planning,
  clarification, and skill-learning requests.
- Add context-scope and action-risk fields.

### Stage 3: Memory and Preferences

- Add structured preference storage and helper tools.
- Recall preferences at session or turn start.
- Save stable preferences.
- Preload semantic memory selectively.

### Stage 4: Planning and Approval Gate

- Add read-only exploration chains.
- Add plan-before-mutation flow.
- Ensure writes/deletes/external side effects require approval.

Status: implemented in `src/chat.py` and `src/file_tools.py`.

### Stage 5: Dynamic Skills

- Add skill proposal after reusable workflows.
- Add global and project skill loading.
- Add skill metadata and lifecycle tracking.

Status: implemented in `src/skills/dynamic_skill.py`, `src/chat.py`, and
`src/context_manager.py`.

### Stage 6: BMAD/SDD Project Init Upgrade

- Extend project init to create BMAD, SDD, traceability, and project-local agent
  instructions.
- Verify project-local instructions align with repository AGENTS rules.

Status: implemented in `src/skills/bmad_skill.py`.

## 11. Validation Scenarios

Create scenario transcripts for:

1. Casual chat feels warm and grounded.
2. Productivity planning keeps context small and helps choose the next action.
3. Sounding-board mode challenges weak reasoning warmly.
4. Technical question is concise and structured.
5. Factual error is corrected clearly.
6. Risky idea receives pushback and safer alternatives.
7. Persona override attempt is resisted.
8. Cultural voice blends light Spanish naturally without overuse.
9. Repo exploration reads automatically and summarizes architecture.
10. Bug fix request explores, plans, and waits for approval before edits.
11. Project init creates BMAD, SDD, and project-local agent instructions.
12. Reusable workflow triggers an optional skill creation offer.

## 12. Implementation Checkpoint

Stages 1-6 are implemented. Remaining CR-004 work should focus on full-scenario
validation, routing audit notes, and any follow-up bug records discovered during
verification.
