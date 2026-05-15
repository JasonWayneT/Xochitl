# Zettelkasten — Complete Guide

**What this is:** A Zettelkasten skill built inside Xochitl. You run it from the terminal. Your vault is a folder that Obsidian also points to. No server, no plugin, no bat scripts — just the terminal and the folders.

**Why it exists:** To give you a thinking partner for building a permanent knowledge base, not just a note collection. The difference matters. A note collection grows but stays inert. A Zettelkasten grows and starts surprising you — surfacing connections you didn't make, tensions you didn't notice, ideas you forgot you had.

---

## The Method — What Zettelkasten Actually Is

Niklas Luhmann was a German sociologist who produced 70 books and over 400 papers using a slip box (Zettelkasten) of 90,000 index cards over 30 years. He said the slip box was his most important thinking partner — not because it stored information, but because it talked back. When he went to file a new note, he would find connections he hadn't anticipated. The system surprised him.

The mechanics that made it work:

**One idea per note.** Not one topic — one *claim*. A claim is something you could argue with. "Value maps" is a topic. "Value maps describe mechanism, not promise" is a claim. The difference is everything: a claim has implications, connects to other claims, and can be wrong. A topic just sits there.

**Your own words, always.** Copying is not thinking. When you restate an idea in your own words, you find out whether you actually understood it. If you can't restate it, you didn't understand it yet — and that's valuable information.

**Links over storage.** The magic of the system is not what's in the notes. It's the web between them. A note with no links is just a file. A note that connects to five other notes in five different domains is a node in a thinking network. The network is the point.

**Write for your future self.** Every permanent note must be self-contained. No "this argument," no "as I mentioned," no pronouns without antecedents. Future-you has no memory of writing it and no patience for cryptic references. Write as if handing the note to a smart colleague who wasn't in the room.

**Output orientation.** Luhmann always had book projects running. The Zettelkasten was a writing machine, not an archive. Notes existed to be pulled into writing. If you never produce anything from the vault, it becomes a collection — which is what most failed Zettelkasten systems become.

---

## The Three Note Types

### Fleeting Notes
Raw captures. No format. No friction. A sentence, a question, a reaction, something you overheard that stuck. Drop it in `Fleeting/` and move on.

These are disposable. Most get discarded or promoted into permanent notes. They're not a backlog to manage — they're a pressure valve so you never lose a thought.

### Literature Notes
One file per source. Written in your own words while reading — not quotes, not highlights, not summaries of summaries. What did the author say that mattered to you, in language you would use?

Tied to the source. Stay close to what the author actually argued. Your interpretation comes later, in the permanent note.

**These are reference, not a queue.** You don't "process" literature notes. You go back to them when you're ready to develop an idea. The permanent note you write backlinks here for provenance.

**Format:**
```markdown
# Value Proposition Design — Osterwalder et al.

## May 11
p.29 — value map describes how value is created, not what.
       mechanism vs outcome framing.

p.31 — pain relievers and gain creators operate on different
       psychology — not just opposites of each other.

## May 14
p.67 — customer jobs have three layers: functional, social, emotional.
       most products only address functional.
```

Add a date header each reading session. That's the only action required.

### Permanent Notes
One note, one idea. This is your actual knowledge base. Every note is a standalone claim written in your own words, linked to other notes.

These are the only notes that get processed through Xochitl. Everything else — fleeting, literature — is upstream of this.

---

## The Transition That Most Systems Miss

**The literature note → permanent note transition is a human act, and it needs a trigger.**

This is where most Zettelkasten systems die. You accumulate literature notes. You intend to "process them later." Later never comes. The vault fills with reference material that never becomes knowledge.

**The rule:** Write at least one permanent note per reading session, while the ideas are alive in your head.

Not later. Not in batch on Sunday. Right after — or even during — reading, when you find yourself thinking "wait, this connects to something I already believe." That moment of recognition is the permanent note. Capture it then.

The literature note jogs your memory. The permanent note captures the insight. The insight comes from your thinking, not from the reading — the reading just gave you material to think with.

A session where you read 40 pages and write zero permanent notes is a session where you consumed but didn't think. A session where you read 10 pages and write one permanent note is a productive session.

---

## Permanent Note Template

Xochitl writes the frontmatter automatically. You write the title and body.

```markdown
---
id: 20260511-001
created: 2026-05-11
source:
tags: []
status: seedling
---

# Value maps describe mechanism, not promise

Value maps reveal how you intend to create value, not what value
you claim to deliver. The distinction matters because mechanism is
designable — promise is just positioning.

A company can iterate on its mechanism. It cannot iterate on a
promise it can't back up. The value map forces the question: what
are we actually doing, not what do we claim to be doing?

[[Customer jobs are tripartite]] — both resist optimising for the
output before understanding the structure underneath it.
```

**Rules for the body:**

- **100–400 words.** 100–200 is ideal. Under 100 is probably an underdeveloped edge. Over 400 is probably two notes.
- **Prose, not bullets.** Bullets list. Prose argues. The act of connecting sentences forces you to find the logic between ideas. If you can't connect two bullets in prose, they might not belong in the same note.
- **State the claim, give the reasoning, name a condition where it fails.** "Under what conditions would this not be true?" is the most generative question you can ask about a permanent note. A note that can't answer it is just an assertion.
- **No context dependency.** No "this argument," no "the author above," no implicit references. The note must stand alone.

**Status:** `seedling` → `evergreen`. You promote manually when an idea has held up — when you've returned to it, referenced it in other notes, and it's still standing. Xochitl never decides status. That's your judgment.

---

## Links Are the Point — Tags Are Navigation

**Links come first.** A note linked to five others in five different domains is doing real work. A note with five tags and no links is just filed.

Tags are for finding things. Links are for thinking. When you add a link, you have to articulate the relationship — extends, contradicts, parallels, applies. That articulation is the thinking. Tags bypass it.

Use tags for practical navigation (you want to find all notes tagged `#strategy` quickly). Use links for intellectual connections (this note on value maps talks to this note on mental models because they're both about framing).

The processing pipeline reflects this: **links first, tags second.**

---

## What a Note Body Should Do

Most practitioners write the claim and stop. Luhmann went further. A permanent note body should:

1. **State the claim** — in your own words, not the author's
2. **Give the reasoning** — why you believe this, or what made it click
3. **Name implications** — "if this is true, then..." points toward the next note
4. **Acknowledge a limit** — under what conditions would this fail?

The limit is the most important and most skipped. A note that can't name its own conditions is fragile. A note that knows its limits is strong — and often points toward a dialectic tension with another note in your vault.

---

## Setup (One Time)

**1. Set your vault path**

Open `.env` in the Xochitl project and fill in:
```
VAULT_PATH=C:\Users\Jason\...\YourVaultName
```

**2. Scaffold the vault**

Tell Xochitl:
```
scaffold my vault
```

This creates the folder structure and writes the Obsidian graph config so the right folders are excluded from the graph.

**3. Open in Obsidian**

Obsidian → "Open folder as vault" → select your vault folder.
The graph is already configured. `_System/` and `Fleeting/` are hidden.

Done. Set `VAULT_PATH` once, never think about it again.

---

## Vault Structure

```
YourVault/
├── Fleeting/       Quick captures — no format, disposable
├── Literature/     One file per source — reading notes in your words
├── Permanent/      One file per idea — your actual knowledge base
└── _System/        Xochitl's workspace — never touch this manually
    ├── vault-index.md          compact index for serendipity engine
    ├── Master Tag List.md      canonical tag taxonomy
    ├── Parked Questions.md     unresolved questions from processing
    ├── Decision Log.md         audit trail of all Xochitl actions
    └── Prompt Library/         versioned processing prompts
```

The Obsidian graph shows only `Literature/` and `Permanent/`. Everything else is hidden. Once you have 20–30 permanent notes, open the graph — the clusters and orphans tell you where your thinking is dense and where it has gaps.

---

## Mode Switching

Xochitl has a Notion inbox (tasks, projects) and a vault inbox (notes). To prevent confusion, you switch modes explicitly.

```
"let's work on zettles"     →  [ZETTEL MODE ON]
"done for today"            →  [ZETTEL MODE OFF]
```

When zettel mode turns on, Xochitl:
- Scans `Permanent/` for notes missing frontmatter and scaffolds them silently
- Reports how many fleeting notes, permanent notes, and parked questions are waiting

While in zettel mode, "inbox," "what should I do," and "what's in my inbox" refer to the vault — not Notion. Xochitl announces both switches so there's never ambiguity.

---

## Commands

### Mode
| Say | Does |
|-----|------|
| `"let's work on zettles"` | Enter zettel mode, scan vault, report status |
| `"done for today"` | Exit zettel mode |
| `"vault status"` | Counts of notes and parked questions |

### Creating notes
| Say | Does |
|-----|------|
| `"I'm reading Value Proposition Design"` | Creates `Literature/value-proposition-design.md` |
| `"new note: [claim as full sentence]"` | Creates scaffolded file in `Permanent/` |

### Processing
| Say | Does |
|-----|------|
| `"process that note"` | Runs pipeline on most recently modified permanent note |
| `"process [filename]"` | Runs pipeline on a specific note |
| `"process my fleeting notes"` | Shows fleeting notes for triage — keep, discard, or promote |

### Discovery
| Say | Does |
|-----|------|
| `"what's connecting lately?"` | Scans vault for non-obvious cross-domain connections |
| `"clarity check [filename]"` | Optional coaching pass on a permanent note |

---

## Processing Pipeline

When you say "process that note," here's exactly what happens — in order:

**1. Word count (automatic, silent)**
- Under 100 words → "This might be the edge of an idea — what are you claiming?"
- 100–400 words → silent, proceed
- Over 400 words → "This might be covering more than one idea — what's the core claim?"

**2. Atomicity check (fires only if something looks wrong)**
- Title looks like a topic → "What's the argument you'd make about it?"
- Note seems to cover multiple ideas → "Are these the same claim or doing separate jobs?"
- If the note is clean → silent, proceed immediately

**3. Single confirmation — links first, then tags**
```
Links:
  [[Customer jobs are tripartite]] — extends
  [[First principles strips assumptions]] — parallel structure, different domain
⚡ Tension: [[Good strategy optimises for outcomes]] — these might disagree

Tags: #strategy #design-thinking

Accept / Edit
```
Everything at once. One response. Done.

**4. Clarity coaching (always optional, always after confirmation)**
```
→ Clarity check? (optional)
```
Ignore it and Xochitl moves on. Say yes for 2–3 specific suggestions.
The offer never repeats if ignored.

**Maximum 4 exchanges for a clean note.** If a session is taking longer than that, something is wrong with the note, not the system.

---

## Serendipity Engine

Every permanent note you process gets embedded into a vector database. Xochitl uses semantic similarity — not keyword matching — to find connections across domains.

"Mechanism vs outcome" finds "process vs result thinking" not because they share words but because they're making the same move in idea-space. This is the kind of connection you wouldn't find by searching.

**Passive** — during every processing session, one non-obvious connection surfaces automatically in the link suggestions.

**Active** — say `"what's connecting lately?"` to scan across your recent notes.

**Dialectic** — Xochitl separately looks for notes making *opposing* claims and flags them with ⚡. Productive tension is more valuable than agreement. Two notes disagreeing is the beginning of a synthesis.

*Requires Ollama running with `nomic-embed-text`. Without it, keyword-based links still work — serendipity just won't surface cross-domain connections.*

---

## Clarity Coaching — What It Checks

When you ask for a clarity check, Xochitl looks for four specific problems:

**1. Title as topic, not claim**
"Value Maps" → should be "Value maps describe mechanism, not promise"
A claim is arguable. A topic is just a label. If someone can't disagree with your title, it's a topic.

**2. Vague qualifiers**
"kind of," "sort of," "basically," "generally" — these signal an unfinished thought. What's the precise word underneath the hedge?

**3. Author's voice, not yours**
The note reads as what Osterwalder said, not what you think. One line of attribution frees the rest to be your argument.

**4. Bullets instead of prose**
Bullets list. Prose argues. If the body is bulleted, the ideas are filed, not connected.

---

## What's Missing — Known Gaps

These are features intentionally deferred, not forgotten.

**Note sequences (Folgezettel)**
Luhmann's most powerful mechanic. Notes didn't just link — they formed threads. Note 1a elaborates on 1. Note 1b challenges 1. Note 1a1 responds to that challenge. You could follow a line of reasoning through the box.

In a digital system, links partially replace this. But the habit of asking "does this continue, branch from, or challenge an existing note?" is more generative than asking "what does this connect to?" The first is sequential thinking. The second is associative. Both matter.

Not implemented yet. Worth doing manually for now: when you write a permanent note, ask yourself what thread it belongs to.

**Writing projects — output orientation**
The Zettelkasten was built to write from. When you want to write about something, you should be able to ask Xochitl "what do I have on X?" and get relevant permanent notes, identified gaps, and a scaffolded outline. This is Phase 7 and it's the payoff of the whole system.

Without it, the vault is a collection. With it, the vault becomes a writing partner.

**Context collapse check**
The atomicity pass currently checks word count and whether the title is a claim. It should also check: does this note depend on context the reader won't have? "This argument" without specifying which argument fails the test. "As I mentioned" fails the test. Each note must stand alone without needing the session that produced it. Not enforced yet — worth checking manually.

---

## The Valley of Death

Most Zettelkasten systems fail before they're useful.

The system starts surprising you around **100 permanent notes** — that's when the first non-obvious clusters appear and the serendipity engine has enough material to find real connections. Before that it feels like maintenance without payoff.

0–50 notes: the grind. You're building the habit and the taxonomy. Don't optimize the system during this phase. Just add notes.

50–100 notes: the first patterns emerge. You'll notice you keep tagging things the same way, keep linking to the same few notes. That's the first signal.

100+: the system starts talking back.

Set this expectation now so you don't abandon the vault at note 30 thinking it isn't working.

---

## Typical Session

```
you:   let's work on zettles
xo:    [ZETTEL MODE] 2 fleeting notes, 1 permanent note ready.

you:   new note: constraints reveal what a system actually values
xo:    Created Permanent/constraints-reveal-what-a-system-actually-values.md
       Open it in Obsidian and write the body.

[you write 160 words in Obsidian, come back to terminal]

you:   process that note
xo:    Links:  (change verb if wrong)
         [[Mechanism Over Outcome]] — extends
         [[First Principles Thinking]] — analogizes  [non-obvious]
       ⚡ Tension: [[Flexibility Is A Design Virtue]]
       verbs: extends, contradicts, qualifies, applies, explains, analogizes, supports

       Tags: #systems-thinking #strategy

       Accept / Edit

you:   accept, but change First Principles to applies
xo:    Done. → Clarity check? (optional)

you:   [ignores it]

you:   done for today
xo:    [ZETTEL MODE OFF]

       You read from value-proposition-design.md this session but didn't
       process a permanent note. What claim survived this session?
       (skip to exit cleanly)

you:   constraints reveal what a system actually values
xo:    Created Permanent/constraints-reveal-what-a-system-actually-values.md
       Open it in Obsidian and write the body.
```

---

## Tips

**The title is the hardest part — do it first.** If you can't write a title that's a full arguable claim before you write the body, the idea isn't ready yet. Put it in Fleeting and come back to it. Don't start writing the body of a note whose claim you can't name.

**One permanent note per reading session, minimum.** While the ideas are alive. The literature note is a reminder; the permanent note is the thinking.

**Links before tags.** A note with five good links and no tags is more valuable than a note with five tags and no links. Tags help you find things. Links help you think.

**Ask "under what conditions is this false?"** A note that can't answer this is just an assertion. A note that can answer it knows its own limits — and those limits often point toward the next note.

**Name the relationship when you link.** "extends," "contradicts," "parallels," "applies to." The act of choosing the word is the thinking. Don't just drop a wikilink.

**The graph view is the payoff.** Once you have 20–30 permanent notes, open the Obsidian graph. Dense clusters show where you think most. Orphans show blind spots. Notes with many incoming links are emerging hubs — ideas that other ideas keep returning to. Those hubs often become the foundation of something you'll want to write.

**Don't optimize the system before you have 100 notes.** Resist the urge to redesign the folder structure, rename tags, or change the template. The system works if you use it. Optimize later when you have real data about what's bothering you.

---

## Scale Architecture

Built for scale from the start — not because there are multiple users now, but because the patterns matter and the product should be learnable from.

### Principle: dumb durable vault, smart replaceable app

The Markdown vault is permanent and user-owned. The app layer is volatile and machine-owned. Never mix them.

**What lives in Markdown (durable):**
- Note content, titles, frontmatter (`id`, `created`, `source`, `tags`, `status`)
- Typed wikilinks in body prose
- Human-readable session log in `_System/Decision Log.md`

**What lives in app state only (volatile):**
- Vector embeddings and embedding model version
- Review schedules, retrieval history, ease scores
- AI suggestion history (accepted, rejected, confidence)
- Session records and metrics
- Tension queue state
- Writing project context and outlines
- Graph metric snapshots

If the app layer is ever deleted or rebuilt, the vault survives intact and readable in any Markdown editor.

### App-owned collections (target schema)

| Collection | Purpose |
|------------|---------|
| `note_index` | File path, id, title, status, word count, last modified, hash |
| `embeddings` | Vector store references and embedding model version |
| `link_suggestions` | Candidate link, relation verb, confidence, accepted/rejected, rationale |
| `retrieval_cards` | Prompt, note id, card type, due date, ease, last result, failure count |
| `tensions` | Note A, note B, contradiction hypothesis, state, resolution note id |
| `sessions` | Session start/end, literature touched, notes processed, closeout reflection |
| `writing_projects` | Topic, selected notes, outline, gaps, exported drafts |

### Async processing model (target)

Capture and note creation are synchronous — zero latency. Processing is synchronous now (by request) but designed to move async:

1. User writes note in Obsidian
2. App detects file change, queues background analysis job
3. Next time user enters zettel mode, suggestions are already waiting
4. User reviews pre-computed suggestions in one confirmation screen

This prevents the "20 questions during capture" problem while still doing the full analysis. The user's cognitive load is lowest right after writing — not the right moment for a pipeline. The right moment is the next session, when the note is slightly cold.

---

## Success Metrics

These are the signals that tell you whether the system is doing what it's supposed to do. Useful now for personal calibration; essential if this ever becomes a product.

| Metric | Direction | Why it matters |
|--------|-----------|----------------|
| Capture latency | Keep near zero | If capture slows, users stop capturing |
| Literature sessions with ≥1 permanent note | Increase | Measures whether the transition gap is closing |
| Permanent notes with typed links | Increase | Connection quality, not just note count |
| Retrieval prompts completed per week | Increase slowly | Durable learning behavior, not just storage |
| Notes reused in output projects | Increase | Is the vault becoming a writing machine? |
| Orphan permanent notes | Decrease | Graph integration — ideas finding their place |
| Evergreen promotions | Healthy slow increase | Knowledge maturing over time |
| User edits to AI-suggested verbs | Healthy nonzero | AI being challenged, not passively accepted |
| Sessions with closeout reflection answered | Optional increase | Metacognitive engagement without forcing it |
| Tension resolutions per month | Increase | Contradictions becoming synthesis |

**The leading indicator to watch:** literature sessions with at least one permanent note created. If that number isn't growing, the system isn't converting consumption into knowledge — which is the whole job.

---

## Roadmap

| Phase | Status | What |
|-------|--------|------|
| 1 | ✅ Done | Mode switching, vault status, session scan, session metrics |
| 2 | ✅ Done | Vault scaffold, note creation tools |
| 3 | ✅ Done | Processing pipeline — word count, atomicity, context-collapse, tags, typed links |
| 4 | ✅ Done | Serendipity engine — vector embeddings, dialectic detection |
| 5 | ✅ Done | Clarity coaching |
| 6 | ✅ Done | Fleeting triage, parked questions, vault index, session-close trigger |
| 7 | 🔲 Next | Retrieval cards — 3 prompts per session, app-owned state, "what should I review?" |
| 8 | 🔲 Next | Tension queue — resolve ⚡ flags: preserve, condition, synthesize, reject |
| 9 | 🔲 Next | Output mode — "what do I have on X?": clusters, gaps, tensions, outline |
| 10 | 🔲 Later | Evergreen evidence prompt — suggest promotion based on retrieval + link count |
| 11 | 🔲 Later | Graph diagnostics — orphan alerts, hub detection, bridge suggestions |
| 12 | 🔲 Later | Async processing — pre-compute suggestions between sessions |
| 13 | 🔲 Later | Thread maps — Folgezettel-style sequencing without brittle IDs |
