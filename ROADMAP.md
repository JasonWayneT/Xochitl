# Xochitl Roadmap

Running log of what's been built, what's planned, and why.

---

## Done

### Voice Writing Skill — `rewrite-voice`
Xochitl can produce or edit content in Jason's writing voice.
Three modes: Edit (fix errors only), Expand (flesh out a first draft),
Generate (write from scratch given a content seed). Loaded with a full
voice spec and 11 annotated gold examples across four registers.
Intake gates prevent hallucination — no mode runs without confirming
what's needed first.

`.xochitl/skills/rewrite-voice/`

---

### BMAD Native Implementation
Xochitl is now a self-contained BMAD host. Previously, all BMAD skills
silently fell back to LLM config-guessing when `_bmad/` wasn't found.
Now they halt with a clear error and point to `bmad-init`.

**What was built:**
- `resolve_customization.py` — the Python TOML merger BMAD skills
  were always supposed to call. Merges base → team → user override
  layers per BMAD structural rules. Lives at `.xochitl/scripts/`.
- `bmad-init` — bootstraps `_bmad/` in any project directory:
  creates config, copies the resolver, sets up output folders.
  Detects project name from the working directory automatically.
- System prompt BMAD context block — `{project-root}` is always
  the current working directory; run `bmad-init` if `_bmad/`
  is missing; never fall back to guessing.
- Fallback removed from 30 SKILL.md files — replaced with HALT
  and a clear error message pointing to `bmad-init`.

**The intent:** Drop Xochitl into any project folder, run `bmad-init`
once, and all BMAD skills work with correct paths, output locations,
and customization. No manual setup. No silent wrong behavior.

`.xochitl/scripts/resolve_customization.py`
`.xochitl/skills/bmad-init/`

---

### Business Model Canvas — `bmad-business-model-canvas`
Optional methodology skill. Walks through all 9 BMC blocks one at a
time, conversational, no critique. Output lands in
`_bmad-output/planning-artifacts/` where downstream BMAD workflows
(PRD creation, architecture) pick it up automatically as project
knowledge.

The design boundary: methodology skills produce artifacts, BMAD
pipeline skills consume them. They don't need to know about each other.

`.xochitl/skills/bmad-business-model-canvas/`

---

## Planned

### Methodology Skills — v2 and beyond
The BMC is v1 of a wider set of methodology skills that feed into the
BMAD pipeline as optional planning inputs. Next candidates, in rough
priority order:

- **Value Proposition Canvas** — maps customer jobs, pains, gains
  against product features. Natural follow-on to BMC.
- **JTBD (Jobs to Be Done)** — customer motivation framing.
  More useful as reference material first; build the skill once
  the framework is more thoroughly understood.
- **PM methodology reference** — distillate of lessons from PM books
  (Inspired, Continuous Discovery, Lean Startup, etc.). Reference
  document loaded as `persistent_facts`, not an interactive skill.
  Build this by reading the books and distilling the prescriptive
  parts that actually affect how decisions get made.
- **Business Model Generation deeper integration** — Osterwalder's
  validation questions, competitor BMC comparison, pivot analysis.
  Add to the BMC skill via `customize.toml` when ready.

None of these are required for the pipeline to work. Build them
when the underlying knowledge is solid enough to avoid codifying
shallow understanding.

---

### Non-Software SDD Pipeline
BMAD's pipeline applies to any project where you need a documented
decision chain before execution — not just software. A candle
company's organic sourcing standard, a business system's operating
procedures, a product launch plan all benefit from the same
discipline: intent → requirements → design → implementation guide.

The "implementation" at the end of the pipeline doesn't have to
be code. It can be SOPs, certifications, staff training docs,
supplier agreements.

What this needs:
- A way for a project's `config.yaml` to declare its domain type
  (software, business-ops, hybrid) so skills know what kind of
  artifacts to produce.
- Possible parallel to `bmad-create-architecture` for non-software:
  something like `bmad-create-operations-design` that produces a
  process and systems design instead of a technical architecture.
- Confirm that existing skills (PRD, epics, stories) map cleanly
  to business specs and SOPs, or identify which ones need variants.

This is a design conversation before it's a build task.

---

### `resolve_config.py` for Party Mode
`bmad-advanced-elicitation` has an optional call to
`resolve_config.py` (not the same as `resolve_customization.py`)
to load the agent roster for party mode. This script doesn't exist.
Party mode still works without it — agents just won't be dynamically
loaded from config. Low priority, but worth closing eventually.

`.xochitl/scripts/resolve_config.py` — to be written.
