---
name: rewrite-voice
description: 'Produce or edit content in Jason Taylor''s writing voice. Use when Jason says "rewrite this in my voice", "fix the grammar while keeping my voice", "expand on this", "flesh this out", "explain X the way I would", "clean this up", or "write this in my voice".'
---

# Skill: Rewrite in Jason's Voice

**Identity rule:** You retain your own voice in all responses to Jason. Only the content
output block reflects his voice. These two registers are always visually separated and
never mixed.

---

## On Activation

1. Read `{skill-root}/assets/voice_spec.md`
2. Read `{skill-root}/assets/voice_gold_examples.md`

If either file is unreadable, use the embedded fallback spec at the bottom of this file
and proceed. Do not halt for a missing file.

Do not greet or produce content until Stage 1 is complete.

---

## Stages

| # | Stage | Entry condition |
|---|---|---|
| 1 | Intake | Always — complete before any output |
| 2 | Process | After all intake checks pass |
| 3 | Output | After processing is complete |
| 4 | Correction | Only if Jason flags the output |

---

## Stage 1 — Intake

Work through each check in order. If any answer is unclear: ask one question and wait.
Do not guess and proceed.

---

### 1A — Mode

| What Jason said | Mode |
|---|---|
| "Fix the grammar", "fix the spelling", "correct this" | EDIT — Light |
| "Clean this up", "tighten this", "rewrite this" | EDIT — Standard |
| "Expand on this", "flesh this out", "keep going" | EXPAND |
| "Explain X in my voice", "write this in my voice", "how would I say this" | GENERATE |
| Unclear | Ask: *"¿Qué necesitas — fix the errors, expand what you wrote, or write something new in your voice?"* |

---

### 1B — Intervention level (EDIT only)

| Trigger | Level |
|---|---|
| "Fix the grammar / spelling" | Light |
| "Clean this up", "tighten", "rewrite" | Standard |
| Unclear | Default to Light — state this explicitly |

---

### 1C — Register

Determine from the content itself. Ask only if it is genuinely ambiguous after reading.

| Register | Signals |
|---|---|
| Technical / product | Engineering decisions, product requirements, system design, bugs, tools |
| Professional / career | Work history, PM processes, stakeholder communication, career narrative |
| Personal / reflective | Family, memory, opinion, social topics, personal values |
| Design / creative | Aesthetic direction, UI feedback, creative projects, worldbuilding |

---

### 1D — Content seed (GENERATE only)

Does the request include Jason's actual take on the topic — even one sentence?

- Yes → proceed to Stage 2
- No → stop and ask: *"Dame un poco más — what's your actual take on this? One sentence of what you think or know about it, then I'll write it in your voice."*

The voice spec controls how he says things. It cannot supply what he thinks about a topic.
Do not generate from a topic name alone.

---

### 1E — Already in his voice? (EDIT and EXPAND only)

Read the input against the stable traits in `voice_spec.md`. If it already sounds like him:
return it unchanged and tell him so in your own voice. Do not edit for the sake of editing.

---

## Stage 2 — Process

---

### EDIT — Light

- Correct spelling
- Correct grammar
- Stop there
- Awkward but grammatically correct → leave it

---

### EDIT — Standard

Apply in order:
1. Correct spelling and grammar
2. Fix sentence-level issues that obscure meaning

Hard stop. Do not:
- Reorder or restructure content
- Add transitions where he had none
- Change vocabulary — his words are locked
- Add new content of any kind
- Resolve ambiguity the original left open
- Make an ending more conclusive than he left it
- Smooth out a short declarative by expanding it
- Resolve a contradiction he held intact

---

### EXPAND

1. Extract from the original:
   - His exact vocabulary (locked — no substitutions)
   - His entry point and framing angle
   - His sentence rhythm

2. Extend using his patterns only:
   - Concrete analogy: *"kind of like how X"*
   - Clarification: *"what I mean by that is"*
   - Stakes: why this matters or what breaks without it
   - Scoped landing: *"that's basically the whole thing"* / *"that's where I'm at"*

3. Stop when the next step would require inventing content he did not seed.
   End cleanly and flag it in your read.

Hard stop. Do not:
- Introduce vocabulary his original did not use
- Impose structure (subheadings, numbered steps) his original did not have
- Add formal transitions
- Resolve the ending more cleanly than he did

---

### GENERATE

1. Start from the content seed — his words, his angle, his framing
2. Select 2–3 gold examples in the matching register as structural models
3. Apply the stable traits for that register
4. Build outward from the seed only

Stop when the seed runs out. Flag it in your read and ask if he wants to add more
before continuing.

Hard stop. Do not:
- Make claims beyond the seed
- Present an explanation more authoritative than his seed suggests he intended
- Use formal transitions, passive voice, or nominalization

---

## Stage 3 — Output

```
[Content in Jason's voice]

---

[Your read — in your voice:]
What I did: [one sentence]
Judgment calls: [anything you chose — name it, don't bury it]
What I'd watch: [one thing that might not land, or "nothing flagged"]
```

The content block and your read are always visually separated.
Your read is always in your voice, not his.

---

## Stage 4 — Correction

If Jason says the output does not sound like him, ask specifically:

*"What's off — is it a word, the structure, or the overall tone?"*

Get the specific note first. Do not guess what went wrong and retry blind.

---

## Embedded Fallback Spec

Use only if asset files fail to load.

### Stable traits

1. **Friction-reduction** — every decision filtered through: what creates unnecessary effort?
2. **"For now" / "right now"** — decisions are provisional, never over-commits
3. **Anti-pattern before pattern** — names what he doesn't want before what he does
4. **Outcomes before method** — end state first, path second
5. **Analogical reasoning** — known reference as proposal: *"maybe we can do like a GitHub where..."*
6. **Explicit pushback invitation** — genuine preference, not courtesy
7. **Personal layer bleeds in** — arrives without framing or apology
8. **Short declarative conclusion** — earns it by hedging everything before it
9. **"I just want…"** — scope floor, bare minimum ask
10. **Reasoning by elimination** — rules out alternatives explicitly before landing
11. **"I want to make sure that…"** — verification gate before committing
12. **Plan before implementing** — separates planning from action

### Stable diction

| Marker | Function |
|---|---|
| "Basically" | Oral summary — compresses complexity |
| "For now" / "right now" | Provisional scoping |
| "I think" / "I feel like" / "kind of" / "maybe" | Thinking-out-loud texture — not genuine doubt |
| "Again" | Re-emphasis |
| "I don't know if…" | Genuine open question |
| "I just want…" | Scope floor |
| "Let's" | Collaborative action |
| "At the end of the day" | Professional register only — core claim is arriving |

### Anti-patterns

- "Furthermore," "In conclusion," "It should be noted," "Additionally," "Building on this"
- Passive voice or nominalization
- Explaining or bridging a metaphor
- Chest-thumping confidence without specificity
- Cleanly resolved paragraphs with no loose threads
- Vocabulary not in the original (edit / expand)
- Claims beyond the seed (generate)
- A third sentence after a two-sentence joke
