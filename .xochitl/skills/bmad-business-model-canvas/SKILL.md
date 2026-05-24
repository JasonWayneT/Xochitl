---
name: bmad-business-model-canvas
description: 'Walk through the 9 Business Model Canvas blocks to document your business model. Use when the user says "let''s do a business model canvas", "create a BMC", "think through our business model", or "let''s map out the business".'
---

# Business Model Canvas

**Goal:** Walk through all 9 BMC blocks one at a time and produce a clean canvas
document that can be used as input for downstream planning (PRD, architecture,
business specs).

**This skill is optional.** It produces a planning artifact — not a required
pipeline step. Run it when you want to think through your business model before
or alongside product and project planning.

**Tone:** Conversational. One block at a time. No critique, no challenges,
no expansions. If the user says "not sure yet" or "skip", record it as TBD
and move forward without comment.

---

## On Activation

Ask what project or business this canvas is for. Use the answer as the
document title.

Then walk through the 9 blocks below in order. For each one:

1. State the block name and ask the single framing question.
2. Wait for the answer.
3. Confirm you have it with one short acknowledgment (e.g., "Got it.") and
   move immediately to the next block.

Do not summarize what the user said back to them at length. Do not offer
observations. Do not ask follow-up questions unless the answer is completely
blank. Keep the conversation moving.

---

## The 9 Blocks

### Block 1 — Customer Segments
> "Who are you building this for? Describe the specific group or groups of
> people — or organizations — you're creating value for."

### Block 2 — Value Propositions
> "What problem are you solving for them, or what need are you meeting?
> What makes someone choose you over doing nothing or going somewhere else?"

### Block 3 — Channels
> "How do your customers find out about you, and how do they actually get
> your product or service? Walk me through how that journey works."

### Block 4 — Customer Relationships
> "What kind of relationship do your customers expect from you — personal
> contact, self-service, automated, community? How do you keep them?"

### Block 5 — Revenue Streams
> "How does the business make money? What are people paying for, and how
> do they pay?"

### Block 6 — Key Resources
> "What do you absolutely need in place to deliver your value proposition —
> physical assets, people, intellectual property, money, anything?"

### Block 7 — Key Activities
> "What are the most important things you have to actually do every day to
> make this work?"

### Block 8 — Key Partners
> "Who do you rely on that you're not doing yourself — suppliers, partners,
> platforms, collaborators? What do you get from them?"

### Block 9 — Cost Structure
> "What are your biggest costs? What's expensive to run or build?"

---

## Output

After the final block, assemble the canvas and present it in full:

```markdown
# Business Model Canvas

**Business / Project:** {name}
**Date:** {date}

---

## 1. Customer Segments
{answer}

## 2. Value Propositions
{answer}

## 3. Channels
{answer}

## 4. Customer Relationships
{answer}

## 5. Revenue Streams
{answer}

## 6. Key Resources
{answer}

## 7. Key Activities
{answer}

## 8. Key Partners
{answer}

## 9. Cost Structure
{answer}
```

After presenting, offer to save it. Preferred location in order:

1. `_bmad-output/planning-artifacts/business-model-canvas.md` — if that
   folder exists in the current project (it will if `bmad-init` was run).
2. Ask the user where to save it.
3. Leave it in the conversation if they prefer.

Do not save without confirming the path first.
