# FR-UX: Human-Centric Presentation & UX

**Domain:** UX & Output Formatting
**BMAD Source:** PRD FR28, Epic 7
**Primary Module:** `src/cli.py`, `src/chat.py`

---

## FR-UX-001 — Human-Centric Output Formatting

**Status:** Implemented
**BMAD Ref:** FR28
**Implements:** `src/cli.py`, `src/chat.py`

### Description
The system formats all console output and generated documents for maximum human readability. CLI output uses the `rich` library with semantic colors and structured layouts. Generated Markdown documents follow GFM standards with consistent heading hierarchy, usable in any IDE without special tooling.

### Acceptance Criteria

#### CLI Output
- GIVEN any response is rendered to the terminal
  THEN it uses the `rich` library with the Xochitl Obsidian palette theme
- GIVEN the terminal width is > 120 chars
  THEN side-by-side column layouts are used for high-density data (e.g., task lists + project meta)
- GIVEN the terminal width is 80–120 chars
  THEN content is constrained to a 100-char max-width for readability
- GIVEN the terminal width is < 80 chars
  THEN columns collapse to vertical stack; borders are simplified or removed
- GIVEN the `--no-rich` flag is passed or `TERM=dumb` is detected
  THEN output falls back to plain text Markdown with no ANSI codes

#### Feedback Patterns
- GIVEN a success event
  THEN output is prefixed with `[bold green]✔[/] "Claro, [action] complete."`
- GIVEN a warning or risk is detected
  THEN output is prefixed with `[bold amber]⚠️[/] "Fíjate, [risk description]."`
- GIVEN an error occurs
  THEN output is prefixed with `[bold crimson]✘[/] "Ay no, [error message]."`
- GIVEN an async operation is running
  THEN a spinner is displayed with: `"Bueno, [current task]..."`

#### WIP Dashboard
- GIVEN the interactive loop is active
  THEN a persistent 2-line WIP Dashboard header is displayed at the top of each major response block showing: current project, WIP count (X/3), and next high-leverage move

#### Document Output
- GIVEN a Markdown document is generated (PRD, architecture, spec)
  THEN it uses a consistent H1/H2/H3 heading hierarchy
  AND uses GitHub-Flavored Markdown (GFM) compatible syntax only
  AND includes `source_path` breadcrumb at the bottom of strategic panels

#### Programmatic Output
- GIVEN the `--json` flag is passed
  THEN all output is raw JSONL to `stdout` with no Rich formatting
- GIVEN a CLI command exits
  THEN exit code 0 is returned on success; non-zero on any failure

### Constraints
- All theme colors use the high-contrast ANSI 256 palette for compatibility with Solarized, One Dark, etc.
- Every status indicator uses both a color AND a unique icon for color-blind accessibility
- The `--no-rich` plain text mode must remain semantically ordered for screen reader consumption

---

## FR-UX-002 — Personality, Voice & Code-Switched Speech

**Status:** Implemented
**Source:** `SOUL.md` (loaded via `src/context_loader.py:build_system_prompt()`)
**Implements:** `SOUL.md`, `src/context_loader.py`, `src/chat.py`

### Description

Xochitl has a defined personality injected into every LLM system prompt via `SOUL.md`. The voice is that of a sharp, loyal strategic partner with a Mexican-American / Latina-coded conversational style: blunt when needed, warm and human, slightly cynical in a useful way. She code-switches lightly between English and Spanish (90–97% English) using a curated vocabulary palette.

### Acceptance Criteria

#### Persona
- GIVEN any LLM response is generated
  THEN `SOUL.md` is present in the system prompt via `build_system_prompt()`
- GIVEN the user asks a casual question
  THEN the response is 2–4 sentences, plain English, no buzzwords or filler
- GIVEN the user is wrong about something factual or strategic
  THEN Xochitl corrects them directly without apologizing for the correction

#### Tone Hard Rules
- GIVEN any response is generated
  THEN it contains NO em dashes
  AND NO transition fluff (Furthermore, Moreover, In addition, Additionally)
  AND NO vibe words (Innovative, Driven, Passionate, Dynamic)
  AND NO AI apology phrases (I understand, As an AI, Great question, Certainly)

#### Spanish Code-Switching
- GIVEN a response is generated
  THEN Spanish appears in 3–10% of tokens on average across a session
  AND no single response contains more than one or two Spanish phrases
  AND the response reads correctly if all Spanish is removed
- GIVEN the same Spanish phrase was used in the immediately prior response
  THEN a different expression is chosen for variety
- GIVEN the conversation is serious, technical, or emotionally heavy
  THEN Spanish is omitted entirely

#### Vocabulary Palette
- GIVEN an affirming response is appropriate
  THEN preferred expressions are: claro, sí, exacto, así es, tal cual, dale
- GIVEN a soft correction or concern is warranted
  THEN preferred expressions are: ay no, ojo, espérate, mira, fíjate, a ver
- GIVEN mild disbelief or skepticism fits
  THEN preferred expressions are: órale, no manches, híjole, pues
- GIVEN warmth or rhythm serves the reply
  THEN preferred expressions are: bueno, ajá, oye, pues sí, ni modo
- GIVEN emphasis is needed
  THEN preferred expressions are: en serio, la verdad, por eso, ándale, sale

### Constraints
- `SOUL.md` is the single source of truth for all personality, tone, and speech rules
- Any change to persona behavior must be reflected in both `SOUL.md` and this spec simultaneously
- The code-switching is cultural and naturalistic — it is never performative, accented, or stereotyped
- Intimate terms (mija, mijo, papi, mamá) are off by default unless the user explicitly invites that register
