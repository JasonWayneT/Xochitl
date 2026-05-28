# CR-050: Building the Brain Behind the Curtain
### What We're Fixing Next — and Why Every Single One Matters

---

## Before We Start: The Uncomfortable Truth About AI Assistants

Here's something most AI products don't want to admit: a smart brain in a slow, fragile body is just a frustrating experience. You can have the most capable language model on the planet, but if every message takes two extra seconds to even *start* processing, if the system forgets what you told it last session, if a single misbehaving component silently breaks the whole thing — users stop trusting it.

CR-050 is about fixing the body. Not because the brain isn't good — it is — but because the infrastructure around it has accumulated the kind of technical debt that quietly chips away at the JARVIS experience we're building toward. Twenty targeted improvements. No new features for the sake of features. Just making the whole machine run tighter, faster, and more reliably.

We organized them into four phases, from the quick wins you can ship in an afternoon to the architectural changes that need careful surgery. Let's walk through all of them.

---

## Phase A: The Quick Wins
### *Eight Changes That Should Have Already Been There*

These are the improvements that, once you see them, make you wonder how the system shipped without them. Each one is low-risk, fast to implement, and makes the product meaningfully better.

---

### A1 — Your Text Shouldn't Break at 80 Characters on a Widescreen Monitor

**The problem:** Somewhere in the early days of Xochitl, a developer set the text wrap width to 80 characters and moved on. That was a perfectly reasonable choice in 1980. It is less reasonable on the 27-inch monitor you're using right now, where 80 characters is roughly a third of the available width. Every response Xochitl gives wraps awkwardly in the middle of a wide terminal, leaving an enormous blank expanse to the right.

**The fix:** Instead of a hardcoded number, the text formatter now asks the operating system "how wide is the terminal right now?" every time it wraps text. If you resize the window, the next response fits. If you're on a small laptop screen, it wraps tighter. The system adapts to you instead of the other way around.

**Why it matters for the product:** This is the kind of polish detail that users can't articulate but absolutely notice. A response that fills the terminal naturally feels more professional than one that stops arbitrarily at a narrow column. It's the difference between a product that feels designed for your environment and one that feels like it was designed for someone else's.

---

### A2 — Stopping the Apology Parade (For Real This Time)

**The problem:** Local AI models have a habit of being *extremely* polite. Ask them anything and they'll say "Certainly! Of course! I'd be delighted to help! Absolutely!" before getting to the actual answer. Xochitl already strips these filler openers — but it was only stripping the *first* one. A model that says "Certainly! Of course!" got the "Certainly!" removed and the "Of course!" stayed.

**The fix:** The cleaner now loops until there are no more openers left to remove, up to five passes. In practice this means the model can stack as many sycophantic openers as it wants and every single one gets stripped before the user sees the response.

**Why it matters for the product:** Filler openers erode trust. When every response starts with "Great question!", it starts to feel patronizing. Worse, it makes the AI feel fake — which undermines the whole point of building a JARVIS-like system that feels like a genuine intelligent partner. Clean responses feel more capable, even when the underlying intelligence is identical.

---

### A3 — "How Long Has This Been Sitting Here?"

**The problem:** The daily brief shows you your top three work-in-progress tasks. But it has no memory of time. A task that's been on your plate for three weeks looks identical to one you just added this morning. There's no signal about aging work.

**The fix:** Each task in the brief now shows how long it's been in your queue — "today", "3d", "1w 2d". The timestamp already existed in the database; we just never surfaced it in the interface.

**Why it matters for the product:** This is fundamentally a prioritization nudge. When you see "Refactor auth module (2w 4d)" sitting in your WIP queue, that number creates a gentle accountability pressure that a bare task description never does. It's also just useful information — your next-session context is richer when you know which items are stale versus fresh.

---

### A4 — A Real Health Dashboard for `/status`

**The problem:** The `/status` command added in CR-048 was a good start — it told you the active model, your WIP count, and your token budget. But it was missing the things that actually tell you whether the system is *healthy*: How many facts has Xochitl learned about you? How many saved workflows do you have? Is the background learning process running or has it quietly crashed?

**The fix:** `/status` now shows a fuller picture: memory fact count, saved workflow count, background review daemon status (alive or crashed), and your current initiative (proactive notification) mode. Think of it as the difference between a car dashboard that just shows speed versus one that shows engine temperature, fuel level, and warning lights.

**Why it matters for the product:** Observability is how you build trust in a system you can't see. When a user knows that Xochitl has learned 47 facts about them and has 12 saved workflows, they feel the system working. When they can see the background daemon is running, they know passive learning is active. Invisible systems feel unreliable even when they're working perfectly.

---

### A5 — Different Jobs Need Different Creative Energy

**The problem:** When Xochitl routes a request to a local language model, every request gets the same "temperature" setting — roughly 0.7 on a scale of 0 to 1. Temperature controls how creative versus deterministic the model is. A temperature of 0.7 is a reasonable middle ground, but it's wrong for almost every specific task. Writing code at 0.7 produces inconsistent, sometimes broken output. Brainstorming at 0.7 produces answers that are too cautious and repetitive.

**The fix:** Temperature is now set per routing category. Code generation gets 0.1 (near-deterministic — write the right code, not creative code). Task management gets 0.3 (focused and clear). General conversation gets 0.55. BMAD brainstorming gets 0.85 (loose, exploratory, generative). Each type of work gets the creative energy level that suits it.

**An analogy:** This is like telling a surgeon to be precise and methodical, then turning to a designer and saying "be wild, surprise me." The same person can do both — you just have to tell them which mode to be in. We're now telling the model what mode it's in.

**Why it matters for the product:** Output quality visibly improves without changing a single model. This is a zero-cost performance gain — pure configuration. For local models running on 8–16GB of VRAM, where you can't always use the largest model, getting the temperature right can close a significant gap with larger models on structured tasks.

---

### A6 — Cutting Off the Context Flood Before the Model Drowns

**The problem:** Xochitl can read files and inject their content into the AI's context window to help it answer questions. This sounds great, but there was no total size limit. If you mentioned five different files in one message, up to 50 kilobytes of file content could be injected — which is more than the *entire context window* of many local models. The model would silently truncate the prompt and give you a response based on incomplete information, with no indication that anything went wrong.

**The fix:** Total file context injection is capped at 8 kilobytes. Files are prioritized by recency (most recently modified first), so the most relevant content comes in first. If the cap is hit, the prompt includes a notice: "File context limit reached — N file(s) omitted." At least now you know.

**Why it matters for the product:** Silent failures are the worst kind of failures. When the model gives you a half-baked answer because it only saw half the context, you don't know whether the answer is bad because the model is bad or because the context was truncated. Explicit limits with visible notices turn a silent failure into a recoverable situation. The user knows to ask about one file at a time.

---

### A7 — Some Skills Need More Time to Think

**The problem:** Every skill — whether it's checking the weather (fast) or running a multi-step research investigation (slow) — had the same 30-second timeout. That's too long for a weather check (something is clearly wrong if it takes 30 seconds) and way too short for a research workflow that legitimately needs to make six web requests and synthesize them.

**The fix:** Each skill can now declare its own timeout in its definition. Weather and Maps get 15 seconds. Gmail gets 20. The research explorer gets 120. BMAD (the project planning skill) gets 180. The default remains 30 seconds for anything that doesn't specify. The skill knows its own latency profile better than a global constant does.

**Why it matters for the product:** This is what makes complex workflows actually usable. If the research skill keeps timing out at 30 seconds, users stop using it. If you give it room to breathe, it can deliver the multi-hop reasoning loop that makes it valuable. Meanwhile, tight timeouts on fast skills mean bad states (a skill hung on a network call) are surfaced quickly rather than blocking the user for half a minute.

---

### A8 — Catching Broken Workflows Before They Break on You

**The problem:** When Xochitl saves a workflow (a multi-step procedure), the steps are stored as a JSON blob in the database. There was no validation at save time. If a step was malformed — missing a required field, containing a typo in the skill name — it would be saved silently and then crash at runtime when you tried to run it.

**The fix:** Workflows are now validated before they're saved. Each step must have a `skill` field and a `description` field. If it doesn't, the save fails immediately with a clear error message instead of silently storing a broken workflow for you to discover later.

**Why it matters for the product:** This is classic "fail fast" engineering philosophy. Errors discovered at input time are easy to fix. Errors discovered at runtime — when you're trying to use a workflow and it explodes — require debugging, context-switching, and erode trust in the system. Catching them at save time is strictly better.

---

## Phase B: The Performance Core
### *Six Changes That Make Every Turn Faster*

These are the improvements that collectively cut the perceived latency of using Xochitl. Some save hundreds of milliseconds. Some save seconds. Together, they make the system feel noticeably more responsive.

---

### B1 — The AI Shouldn't Have to Ask Another AI to Route Every Message

**The problem:** Every time you send a message to Xochitl, the system needs to decide what kind of message it is: a task management request? A question? A code request? Right now, for any message that isn't caught by a simple keyword list, it calls a *second AI model* (a small local one called gemma2:2b) just to classify your intent. That classification call takes 500ms to 2 full seconds. Every. Single. Turn.

**The fix:** We're dramatically expanding the rule-based "fast path" that can classify intent without an AI call. If you type a slash command (`/today`, `/sync`), that's always task management — no AI needed. If you type `@Weather`, that's a direct skill call — no classification needed. If you type "yes" or "no" in response to a question, that's simple conversation — no AI needed. For roughly 70% of messages, we can now skip the classification AI entirely.

**An analogy:** Imagine a hotel concierge who, every time a guest asks for directions to the elevator, has to call the front desk manager to confirm what kind of question it is before answering. That's absurd — the concierge knows what directions are. We're teaching the system to recognize the obvious cases itself, so the manager only gets called when the question is genuinely ambiguous.

**Why it matters for the product:** Cutting 500ms–2s from 70% of turns is transformative for user experience. The difference between a 0.5-second response and a 2.5-second response is the difference between "this feels like a real-time conversation" and "I'm waiting on the AI again." This is the single biggest latency improvement in the batch.

---

### B2 — Stop Rebuilding the Same Foundation Every Turn

**The problem:** Every time you send a message, Xochitl assembles the full context for the AI from scratch: it runs `git log` in your terminal, queries the database, reads your `Me.md` profile file, fetches vector embeddings from LanceDB, and stitches together nine different pieces of information into one system prompt. This takes 200–800 milliseconds — and most of this information doesn't change between consecutive messages in the same session.

**The fix:** The assembled context is now cached between turns. If you sent a message 10 seconds ago and the context hasn't changed, Xochitl reuses the cached version instead of rebuilding it from scratch. The cache is smart: it knows to invalidate when a mutating action completes (like syncing Notion or completing a task) or when new messages arrive. Git state refreshes on a 60-second timer independently.

**An analogy:** Think about how you don't re-read a whole book every time you want to continue from where you left off. You have a bookmark. You know where you are. You pick up from the bookmark. The context cache is Xochitl's bookmark.

**Why it matters for the product:** This compounds with the classification fast-path (B1). Combined, the two changes mean that for a typical conversation turn, the system goes from spending 700ms–2.8s on overhead before even touching the LLM to spending near-zero on the fast path. Sessions feel snappier. Local models on constrained hardware benefit disproportionately.

---

### B3 — One Slow Skill Shouldn't Ruin Your Day

**The problem:** Before routing each message, Xochitl asks every registered skill "can you handle this message?" to score relevance. This scoring happens sequentially, one skill at a time. If a skill's `can_handle()` function is slow — maybe it's doing some heavy pattern matching, or it accidentally touches the filesystem — it blocks the entire message-handling pipeline. With ten or more skills registered, one slow skill multiplies into meaningful latency.

**The fix:** Two changes in tandem. First, each skill's `can_handle()` call now runs with a 100-millisecond timeout. If a skill takes longer than that to score itself, it gets a 0.0 (not applicable) and the pipeline moves on. Second, if the same skill is evaluated twice in the same turn (which can happen in the agent loop), the second evaluation uses the cached score from the first — no repeat computation.

**Why it matters for the product:** This is a classic "defensive programming" win. You're not making any skill faster — you're capping the damage any single skill can do to the overall experience. As the skill library grows, this becomes increasingly important. A poorly-written third-party skill or a skill that makes a network request in `can_handle()` can't hold the whole system hostage.

---

### B4 — Background Learning Should Never Quietly Die

**The problem:** Xochitl does passive learning in the background after every turn — it extracts facts about you, detects corrections, and monitors for persona drift. This runs in a separate background thread. If that thread crashes (an unhandled exception, a database timeout, anything), it dies silently. Passive learning stops. You have no idea. The system keeps working but it's no longer learning from you.

**The fix:** The main loop now checks whether the background learning thread is alive before each turn. If it's dead, it automatically restarts it and posts a `SYSTEM_FAILURE` initiative signal (if your proactive mode allows) so you can see that something was restarted. Think of it as an automatic restart mechanism — like how your phone's background services restart if they crash, without requiring you to reboot the whole device.

**Why it matters for the product:** A system that silently degrades is worse than a system that fails loudly, because you can't fix what you can't see. With the watchdog, the degradation is transient (one crash → automatic restart) instead of permanent (crash → dead for the rest of the session). Long-running sessions benefit most — and long-running sessions are exactly the ones where passive learning is most valuable.

---

### B5 — Your "Don't Show Me This" Preference Should Survive a Restart

**The problem:** The initiative engine lets users dismiss types of proactive notifications — deadline alerts, system failure notices, follow-up suggestions. After three dismissals of the same category, that category is permanently suppressed. The problem: "permanently" meant "for this session." Every time you start a new session, the dismissal count resets to zero. A user who dismissed deadline alerts three times yesterday has to dismiss them three more times today.

**The fix:** Dismissal counts are now persisted to the SQLite database. When you start a new session, the initiative engine loads your previous suppression state. If you told the system three times that you don't want celebration notifications, it remembers that forever — not just until you close the terminal.

**Why it matters for the product:** This is the difference between a system that respects user preference and one that merely acknowledges it temporarily. The current behavior creates a frustrating loop: suppress → restart → re-suppress. Persistent preferences mean the system actually adapts to you over time instead of requiring you to re-teach it every session.

---

### B6 — Old Memories Should Fade, Not Calcify

**The problem:** Every time Xochitl learns a fact about you ("Jason is working on the fitness app"), it stores it with a confidence score and never updates that score. A fact from eight months ago carries the same weight as one from this morning. Over time, the system's memory fills with facts that were true once but may not be relevant anymore, all weighted equally, all injected into every prompt.

**The fix:** Facts now decay mathematically over time. Every day a fact goes unconfirmed, its confidence score drops by 5%. After about six weeks, an old unconfirmed fact falls to a floor of 0.3 — present but not dominant. After about six months, if it hasn't been refreshed, it drops below the deletion threshold and is cleaned up automatically. Facts you keep reinforcing stay sharp. Facts that go stale fade naturally.

**An analogy:** Your own memory works this way. You vividly remember where you parked last week. You have a hazier recollection of where you parked eight months ago — it might come back if prompted, but it doesn't crowd out more recent information. The memory system should work the same way.

**Why it matters for the product:** Stale facts are worse than no facts. They actively mislead the AI. Decay keeps the memory system self-maintaining without requiring manual curation — which no user ever does.

---

## Phase C: Reliability
### *Three Changes That Fix Data Integrity Gaps*

---

### C1 — When You Update Your Profile, the AI Should Actually Know

**The problem:** Xochitl's semantic memory uses vector embeddings — mathematical representations of text that allow it to find conceptually similar information even when the exact words are different. These embeddings are generated once when a fact is first stored. If you update your `Me.md` profile (your background, your role, your goals), the new information goes into the profile file — but the *old embeddings* are still sitting in the vector database. When Xochitl searches for relevant memories, it's still searching against your old self.

**The fix:** When Xochitl detects that your `Me.md` has changed (it compares a fingerprint of the file content), it triggers a background re-embedding — regenerating the vector representations from the updated profile. This runs asynchronously so it doesn't slow down your session, but within one session it catches up.

**Why it matters for the product:** If a user goes through a major life change — new job, new project, new focus area — and updates their profile, they expect the AI to adapt. The current behavior would have it adapting in text-based retrieval but not in semantic search, creating an invisible split where some memory paths respond to the update and others don't. This closes that gap.

---

### C2 — Deleted Tasks Should Leave a Trace

**The problem:** When you mark a task complete or delete a project, it disappears from the database permanently. Hard delete. Gone. This means there's no way to ask "what did I complete last month?", no audit trail, no history. If a workflow references a task ID that was deleted, it fails silently.

**The fix:** Tasks and projects are now "soft-deleted" — instead of being removed from the database, they get a `deleted_at` timestamp and are excluded from all active queries. They still exist; they're just invisible to the normal interface. After 30 days, a maintenance process can purge them if desired. A future `/history tasks` command could surface them.

**Why it matters for the product:** This is a foundational data integrity decision that's much easier to make before a product is widely used than after. Once you have years of task history, users start caring about things like "show me everything I completed in Q1." Soft deletes make that possible. Hard deletes make it impossible retroactively.

---

### C3 — The AI Should Be Able to Do Two Things at Once

**The problem:** When Xochitl's LLM generates a response and decides it needs to use a skill, it puts a special `<skill_call>` tag in its output. The parsing logic currently only extracts the *first* one. If the model says "let me check your tasks AND the weather," only the task check happens. The weather request is dropped silently.

**The fix:** The parser now extracts *all* skill call blocks from a response and executes them in sequence, combining the results. Approval-gated skills (like Notion writes) still require confirmation before any subsequent calls proceed — safety first.

**Why it matters for the product:** This unlocks compound requests — one of the most natural ways users interact with AI assistants. "Show me my tasks and today's weather" is a completely reasonable thing to ask. It currently requires two separate messages. With multi-call parsing, one message is enough. This is a direct step toward the JARVIS vision of an assistant that can handle multi-faceted requests in a single turn.

---

## Phase D: The Architectural Changes
### *Three Changes That Require the Most Care — and Deliver the Most Capability*

These are the changes that touch the deepest structural assumptions of the system. They're implemented last, after everything else is stable.

---

### D1 — When a Skill Crashes, It Should Clean Up After Itself

**The problem:** When a skill execution times out — the thread is abandoned (it keeps running in the background until the session ends, then gets killed). If that skill had opened a file, a database connection, or a network socket, those resources stay open. In a long session with multiple timeouts, this is a slow resource leak.

**The fix:** The `Skill` base class now has an optional `cleanup()` method. If a skill times out, Xochitl gives it 5 seconds to run its cleanup routine — close connections, cancel pending requests, release file handles. Skills that don't need cleanup don't implement it (the base class provides a harmless default). Skills that do have it — like the research explorer that might have HTTP requests in flight — can use it to leave the system in a clean state.

**Why it matters for the product:** This is professional-grade engineering. Consumer software can get away with leaked resources because sessions are short and memory is plentiful. A daily driver AI system that runs for hours, handles dozens of requests, and manages external connections needs to be disciplined about resource management. This establishes that discipline at the framework level.

---

### D2 — Your Suppression Preferences Should Mean Something Forever

*(Note: This is the initiative persistence improvement — already covered in Phase B5 above. D1 is the architectural treatment of it.)*

---

### D2 — Watching Responses Appear Word by Word (For Every Request)

**The problem:** There are two modes in Xochitl. When it talks directly to the LLM without invoking a skill, you see the response stream in — one token at a time, like someone typing. It feels alive. But when a skill is involved (which is most of the interesting interactions — weather, tasks, research, Gmail), the system waits for the entire response before showing you anything. Blank screen, then sudden text dump.

**The fix:** Skill-injected turns should also stream. The implementation is delicate: the streaming text needs to display live, but the parser also needs to wait for the complete response to extract `<skill_call>` blocks. The solution buffers the full response for parsing while simultaneously displaying it token-by-token, hiding the `<skill_call>` XML tags from the user and smoothly transitioning to skill execution.

**Why it matters for the product:** This is the most visceral UX improvement in the batch. Streaming responses feel fundamentally different from batch responses — they feel like thinking, not like waiting for a database query. When the most interesting, skill-powered interactions switch from "wait, then dump" to "watch it think," the experience transforms. This is the kind of change users notice immediately and can't articulate precisely but clearly prefer.

---

## The Big Picture: What Does This All Add Up To?

Twenty improvements. Not twenty features — twenty investments in the infrastructure that makes features possible.

Here's the simplest way to understand what this batch does: it makes Xochitl feel like a system that was *designed* rather than assembled. Right now, it works. After CR-050, it works *reliably*, *responsively*, and *respectfully* — respecting your screen size, your notification preferences, your session history, and your time.

The JARVIS comparison is useful here. What made Tony Stark's JARVIS feel like a real system wasn't just that it was smart. It was that it was *fast* — it responded without noticeable delay. It *remembered* — it knew context without being reminded. It *self-maintained* — Tony didn't have to restart it when a component failed. And it *adapted* — it calibrated its behavior to the task at hand.

CR-050 is a direct investment in all four of those qualities.

---

## Quick Reference: All 20 in One Place

| # | What Changes | You Notice Because... |
|---|---|---|
| A1 | Text wraps to your actual screen width | Responses fill the terminal properly |
| A2 | All filler openers removed, not just the first | "Certainly! Of course!" disappears entirely |
| A3 | Task brief shows how long each item has been waiting | "3w 2d" next to a stale task creates urgency |
| A4 | `/status` shows memory facts, workflows, daemon health | You can actually see the system working |
| A5 | Temperature tuned per task type | Code is more precise; brainstorming is more creative |
| A6 | File injection capped at 8 KB total | Local models stop silently truncating your context |
| A7 | Each skill has its own timeout budget | Research works; fast skills fail quickly |
| A8 | Broken workflows caught at save, not at run | Error messages appear when you can act on them |
| B1 | Slash commands and @mentions skip the classifier LLM | 500ms–2s faster on ~70% of turns |
| B2 | Context is cached between turns | No redundant git/DB/file reads every message |
| B3 | Slow `can_handle()` capped at 100ms | One bad skill can't block the whole loop |
| B4 | Background learning restarts automatically if it crashes | Passive learning never silently dies |
| B5 | Notification dismissals persist across sessions | "Stop showing me this" actually means forever |
| B6 | Old memories decay instead of calcifying | Stale facts fade; fresh facts stay prominent |
| C1 | Profile changes trigger semantic memory update | Updated Me.md actually updates how you're understood |
| C2 | Deleted tasks are soft-deleted, not erased | History exists; future `/history tasks` is possible |
| C3 | Multiple skill calls in one LLM response all execute | "Check tasks AND weather" works in one message |
| D1 | Timed-out skills get to clean up after themselves | No resource leaks from abandoned threads |
| D2 | (See D1 — combined in implementation) | — |
| D2 | Skill-powered turns stream token by token | Every interesting interaction feels live |

---

*Next step: implement CR-050 following the session plan at `docs/spec/05-change-requests/CR-050-session-plan.md`. The SDD chain (CR doc → requirements registry → traceability matrix → code → tests → commit) follows the same process as CR-048 and CR-049.*
