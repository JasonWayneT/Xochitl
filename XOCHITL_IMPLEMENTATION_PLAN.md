# Xochitl Implementation Plan: BMAD → SDD → Code Pipeline

**Based on:** `XOCHITL_BMAD_SDD_IMPLEMENTATION_GAP_ANALYSIS.md`  
**Codebase audit date:** 2026-05-02  
**Status:** Implemented (Verified via smoke and E2E tests)

---

## Baseline Audit

The conversational core (chat loop, routing, task management, Notion sync, BMAD detection) is **~80% complete**. The BMAD→SDD→Code pipeline is **0% implemented**.

### What exists and is reusable
| Component | File | Key API to reuse |
|---|---|---|
| LLM routing | `src/router.py` | `TieredRouter.route(query, route_type, system_context)` |
| Skill detection | `src/chat.py` | `_check_skills()` → `Skill.can_handle()` / `suggest()` / `execute()` |
| Skill contract | `src/skills/base.py` | `Skill` ABC with `can_handle`, `suggest`, `execute` |
| Tool dispatch | `src/tools.py` | `dispatch(tool_name, params)` — add new `_handle_*` functions here |
| File I/O | `src/file_tools.py` | `FileTools.read_file()` / `write_file()` with confirmation gates |
| Security | `src/security.py` | Allowed/forbidden roots sandbox |
| BMAD detection | `src/bmad.py` | `detect_bmad_project()`, `build_bmad_context()` |
| Artifact save | `src/tools.py` | `_handle_save_artifact()` |

### What does NOT exist (build from scratch)
- `projects/<project-id>/` directory structure
- `.sdd/` config + prompts directory
- `src/skills/sdd_skill.py`
- `src/skills/code_skill.py`
- Project context detection in `chat.py`
- FR-*/AC-*/EC-* requirement system
- Traceability matrix (`traceability.json`)
- Issue tracking (`issues/open/`, `issues/closed/`)

---

## Phase 1 — Foundation
**Goal:** "I want to build X" → creates project structure + guides through BMAD → saves artifacts  
**Estimated effort:** 1 weekend

### 1.1 Create directory scaffolding

**New directories to create (committed as `.gitkeep`):**
```
projects/
.sdd/
.sdd/prompts/
.sdd/logs/
```

### 1.2 Create `.sdd/config.yml`

```yaml
llm:
  provider: tiered

workflow:
  auto_analyze_issues: true
  require_manual_approval: false
  auto_update_specs: true

confidence:
  min_for_auto_action: 0.75

directories:
  projects: projects
  sdd_config: .sdd
  logs: .sdd/logs
```

### 1.3 Create `.sdd/prompts/` files

Three files (exact content specified in gap analysis §Part 7):
- `.sdd/prompts/spec-generation.md`
- `.sdd/prompts/issue-analysis.md`
- `.sdd/prompts/code-generation.md`

### 1.4 Expand `src/skills/bmad_skill.py`

Add these methods to `BMADSkill` (keep existing `_guided_workflow` and `_draft_workflow`):

```python
def init_project(self, project_id: str, name: str, description: str) -> dict:
    """Create projects/<project-id>/ structure and .project-meta.yml."""
    # Creates: bmad/, specs/, issues/open/, issues/in-progress/, issues/closed/, src/
    # Writes: .project-meta.yml from template
    # Returns: {"project_id": ..., "path": ..., "created": True}

def save_bmad_artifact(self, project_id: str, artifact_type: str, content: str) -> str:
    """Write to projects/<project-id>/bmad/<artifact_type>.md via FileTools."""
    # artifact_type: "business-model" | "architecture" | "design-specs" | "constraints"
    # Returns: file path written

def get_bmad_artifacts(self, project_id: str) -> dict:
    """Load all bmad/*.md files for a project, return as {filename: content}."""

def is_bmad_complete(self, project_id: str) -> bool:
    """Check .project-meta.yml bmad_complete flag + that business-model.md exists."""

def list_projects(self) -> list[dict]:
    """Scan projects/ directory, read each .project-meta.yml, return list."""
```

**Template: `.project-meta.yml`** (written by `init_project`):
```yaml
project_id: "{project_id}"
name: "{name}"
description: "{description}"
created: "{iso_timestamp}"
status: active

bmad_complete: false
specs_generated: false
code_scaffolded: false

stack:
  backend: null
  frontend: null
  database: null

stats:
  total_requirements: 0
  implemented_requirements: 0
  open_issues: 0

last_worked: "{iso_timestamp}"
```

### 1.5 Register new tools in `src/tools.py`

Add to the dispatch table:
```python
"init_project":       _handle_init_project,       # calls BMADSkill.init_project()
"save_bmad_artifact": _handle_save_bmad_artifact,  # calls BMADSkill.save_bmad_artifact()
"list_projects_sdd":  _handle_list_projects_sdd,   # calls BMADSkill.list_projects()
```

### 1.6 Integration test criteria (Phase 1 done when)
- [ ] User says "I want to build a diet app" → `projects/diet-tracker/` created with all subdirs
- [ ] `.project-meta.yml` written with correct structure
- [ ] User provides business model → `bmad/business-model.md` written
- [ ] `BMADSkill.is_bmad_complete()` returns `True` after all 4 BMAD artifacts saved
- [ ] File operations go through `FileTools` / `security.py` (no raw `open()` calls)

---

## Phase 2 — SDD Core
**Goal:** BMAD artifacts → 10–15 structured requirements in `specs/`  
**Estimated effort:** 1 weekend

### 2.1 Create `src/skills/sdd_skill.py`

Full class with these methods:

```python
class SDDSkill(Skill):
    def can_handle(self, user_input: str, context: dict) -> float:
        # Keywords: spec, requirement, FR-, AC-, EC-, analyze, traceability
        # Boost: +0.3 if context["current_project"] is set
        # Cap at 1.0

    def suggest(self, user_input: str, context: dict) -> str:
        # If BMAD complete but specs not generated → suggest generating specs
        # If "bug" or "issue" in input → suggest analysis

    def execute(self, user_input: str, context: dict, params: dict = None) -> str:
        # Route by params["action"]:
        #   "generate_specs"     → generate_specs_from_bmad()
        #   "get_requirement"    → get_requirement()
        #   "list_requirements"  → list_requirements()
        #   "create_requirement" → create_requirement()
        #   "update_requirement" → update_requirement()

    def generate_specs_from_bmad(self, project_id: str) -> str:
        """Call TieredRouter with spec-generation prompt + BMAD artifacts.
        Parse JSON response → write specs/core-features.md + traceability.json.
        Update .project-meta.yml: specs_generated=true, total_requirements=N."""

    def get_requirement(self, project_id: str, requirement_id: str) -> dict:
        """Parse specs/*.md to find and return requirement block by ID."""

    def list_requirements(self, project_id: str) -> list[dict]:
        """Return all FR-* IDs + descriptions + status from all specs/*.md files."""

    def create_requirement(self, project_id: str, req_type: str, content: dict) -> str:
        """Append new FR-* block to appropriate specs file. Auto-assign next ID."""

    def _load_sdd_prompt(self, prompt_name: str) -> str:
        """Read .sdd/prompts/{prompt_name}.md."""

    def _load_traceability(self, project_id: str) -> dict:
        """Load projects/{project_id}/specs/traceability.json or return empty template."""

    def _save_traceability(self, project_id: str, data: dict) -> None:
        """Persist traceability.json via FileTools."""
```

**Spec file format** generated by `generate_specs_from_bmad()`:

File: `projects/<project-id>/specs/core-features.md`
```markdown
---
feature: core
owner: you
last_updated: {date}
---

# Core Features — {Project Name}

## FR-CORE-001: {Feature Name}
**Status:** not_implemented
**Priority:** P1
**BMAD Source:** `bmad/business-model.md` — {section}

**Description:**
{one sentence}

**Acceptance Criteria:**
- AC-CORE-001: GIVEN {context} WHEN {action} THEN {result}

**Edge Cases:**
- EC-CORE-001: GIVEN {unusual input} WHEN {action} THEN {behavior}

**Implementation:** _(pending)_

**Traceability:**
- Maps to: BMAD `business-model.md`
- Issue: _(none)_
```

### 2.2 Register SDD tools in `src/tools.py`

```python
"generate_specs":     _handle_generate_specs,     # SDDSkill.generate_specs_from_bmad()
"get_requirement":    _handle_get_requirement,     # SDDSkill.get_requirement()
"list_requirements":  _handle_list_requirements,   # SDDSkill.list_requirements()
"create_requirement": _handle_create_requirement,  # SDDSkill.create_requirement()
```

### 2.3 LLM routing for spec generation

In `SDDSkill.generate_specs_from_bmad()`:
```python
router = TieredRouter()
response = router.route(
    query=full_prompt,
    route_type="bmad_complex",   # existing route type → cloud model
    system_context=self._load_sdd_prompt("spec-generation")
)
```

The LLM must return pure JSON (enforced by prompt). If JSON parse fails, retry once then surface error to user.

### 2.4 Integration test criteria (Phase 2 done when)
- [ ] `sdd_skill.generate_specs_from_bmad("diet-tracker")` → writes `specs/core-features.md` with ≥8 FR-* blocks
- [ ] `specs/traceability.json` created with correct structure
- [ ] `.project-meta.yml` updated: `specs_generated: true`, `total_requirements: N`
- [ ] `sdd_skill.list_requirements("diet-tracker")` returns all IDs
- [ ] `sdd_skill.get_requirement("diet-tracker", "FR-CORE-001")` returns parsed dict
- [ ] Failed JSON from LLM retries once, then returns human-readable error

---

## Phase 3 — Issue Analysis
**Goal:** User reports bug → Xochitl analyzes against specs → updates requirement → creates issue file  
**Estimated effort:** 1 weekend

### 3.1 Add issue management to `SDDSkill`

```python
def create_issue(self, project_id: str, issue_type: str, title: str, description: str) -> str:
    """Write projects/{project_id}/issues/open/BUG-NNN.yml. Auto-increment ID."""

def analyze_issue(self, project_id: str, issue_id_or_description: str) -> dict:
    """Load spec context + issue text. Call TieredRouter with issue-analysis prompt.
    Return analysis dict: {analysis_type, affected_requirements, spec_changes_needed,
    implementation_guidance, confidence}."""

def update_requirement(self, project_id: str, requirement_id: str, updates: dict) -> str:
    """Edit FR-* block in specs/*.md in-place. Write change to .sdd/logs/spec-changes.jsonl."""

def close_issue(self, project_id: str, issue_id: str, resolution: str) -> str:
    """Move issues/open/BUG-NNN.yml → issues/closed/. Update status field."""

def update_traceability(self, project_id: str, requirement_id: str, impl_data: dict) -> None:
    """Add/update mapping entry in traceability.json.
    impl_data: {"file": ..., "functions": [...], "lines": [...]}"""
```

**Issue file format** (`issues/open/BUG-NNN.yml`):
```yaml
id: BUG-{NNN}
type: bug
project: {project_id}
created: {iso_timestamp}
status: open

title: "{title}"
description: |
  {description}

reproduction: []
expected: ""
actual: ""

environment:
  version: "0.1.0"
  platform: ""

affected_requirements: []
analysis: null
spec_impact: null
priority: P2
```

### 3.2 Spec-changes audit log

Each call to `update_requirement()` appends to `.sdd/logs/spec-changes.jsonl`:
```json
{"timestamp": "...", "project": "...", "requirement_id": "FR-CORE-001",
 "change_type": "modify", "previous": "...", "updated": "...", "trigger": "BUG-001"}
```

### 3.3 Register issue tools in `src/tools.py`

```python
"create_issue":       _handle_create_issue,
"analyze_issue":      _handle_analyze_issue,
"update_requirement": _handle_update_requirement,
"close_issue":        _handle_close_issue,
```

### 3.4 Integration test criteria (Phase 3 done when)
- [ ] User says "the app accepts negative calories" → issue file created at `issues/open/BUG-001.yml`
- [ ] `analyze_issue()` returns `analysis_type: "spec_gap"` with correct `affected_requirements`
- [ ] `update_requirement("diet-tracker", "FR-CORE-001", {...})` edits the markdown in-place, preserves all other blocks
- [ ] `.sdd/logs/spec-changes.jsonl` has one appended line after the update
- [ ] Confidence < 0.75 → Xochitl asks user to review before applying change

---

## Phase 4 — Code Generation
**Goal:** Specs → scaffolded code; issues → code fix with test  
**Estimated effort:** 1 weekend

### 4.1 Create `src/skills/code_skill.py`

```python
class CodeSkill(Skill):
    def can_handle(self, user_input: str, context: dict) -> float:
        # Keywords: generate, scaffold, implement, code, build, fix
        # Requires: context["specs_generated"] == True for boost
        # Cap at 1.0

    def suggest(self, user_input: str, context: dict) -> str:
        # If specs not generated → "Generate specs first"
        # If specs exist → "Scaffold [component]?"

    def execute(self, user_input: str, context: dict, params: dict = None) -> str:
        # Route by params["action"]:
        #   "scaffold"     → scaffold_from_specs()
        #   "implement"    → generate_code_for_requirement()
        #   "fix"          → fix_issue()
        #   "tests"        → generate_tests()

    def scaffold_from_specs(self, project_id: str, component: str) -> str:
        """Load specs + architecture. Call TieredRouter with code-generation prompt.
        Parse JSON response → write files via FileTools. Return summary of files created."""
        # Uses qwen2.5-coder route type for implementation

    def generate_code_for_requirement(self, project_id: str, requirement_id: str) -> str:
        """Implement one FR-* from spec. Call TieredRouter. Write file(s). Update traceability."""

    def fix_issue(self, project_id: str, issue_id: str) -> str:
        """Load issue + affected requirements + relevant source files.
        Call TieredRouter. Apply fix. Update traceability. Close issue."""

    def generate_tests(self, project_id: str, requirement_id: str) -> str:
        """Generate pytest cases from AC-* acceptance criteria. Write tests/ file."""

    def _load_project_stack(self, project_id: str) -> dict:
        """Read .project-meta.yml and return stack dict."""
```

**LLM routing for code generation:**
```python
# In CodeSkill
router = TieredRouter()
response = router.route(
    query=full_prompt,
    route_type="code_generation",   # → qwen2.5-coder:7b via Ollama
    system_context=self._load_code_prompt()
)
```

**After writing generated files:**
- Call `SDDSkill.update_traceability()` with implementation data from LLM response
- Update `.project-meta.yml` `implemented_requirements` count
- Update FR-* status to `"implemented"` in spec file

### 4.2 Register code tools in `src/tools.py`

```python
"scaffold_project":    _handle_scaffold_project,
"implement_requirement": _handle_implement_requirement,
"fix_issue_code":      _handle_fix_issue_code,
"generate_tests":      _handle_generate_tests,
```

### 4.3 Integration test criteria (Phase 4 done when)
- [ ] "Scaffold the backend" → generates `src/api/`, `src/models/` with correct stack from `.project-meta.yml`
- [ ] Generated files reference requirement IDs in comments (`# Implements FR-CORE-001`)
- [ ] `generate_tests("diet-tracker", "FR-CORE-001")` → pytest file with one test per AC-* criterion
- [ ] `fix_issue("diet-tracker", "BUG-001")` → edits source, writes test, closes issue, updates traceability
- [ ] All generated files go through `FileTools` (not raw `open()`)

---

## Phase 5 — Integration
**Goal:** End-to-end flow works; project context auto-detected; conversational suggestions feel natural  
**Estimated effort:** 1 weekend

### 5.1 Project context detection in `src/chat.py`

Add to `XochitlChat.__init__()`:
```python
self.current_project: str | None = None
```

Add to `XochitlChat.process_message()` before intent classification:
```python
self.current_project = self._detect_current_project()
if self.current_project:
    self.current_context["current_project"] = self.current_project
    self.current_context["specs_generated"] = self._check_specs_exist(self.current_project)
    self.current_context["bmad_complete"] = self._check_bmad_complete(self.current_project)
```

Add new private methods to `XochitlChat`:
```python
def _detect_current_project(self) -> str | None:
    """Return project_id if CWD is inside projects/<project-id>/ and .project-meta.yml exists."""

def _check_specs_exist(self, project_id: str) -> bool:
    """True if projects/<project-id>/specs/ has at least one *-features.md."""

def _check_bmad_complete(self, project_id: str) -> bool:
    """Read .project-meta.yml bmad_complete field."""
```

### 5.2 Extend intent classification in `src/chat.py`

Current intents: `task_query, action_request, file_operation, orchestrator_query, bmad_workflow, general`

Add:
- `sdd_workflow` — triggers when FR-*/AC-*/spec/requirement keywords present
- `code_generation` — triggers when generate/scaffold/implement + specs_generated context
- `issue_tracking` — triggers when bug/issue + current_project context

### 5.3 Register new skills in `src/chat.py`

Wherever `_check_skills()` loads its skill list, add:
```python
from .skills.sdd_skill import SDDSkill
from .skills.code_skill import CodeSkill

# In skills list:
SDDSkill(),
CodeSkill(),
```

### 5.4 Natural next-step suggestions

After each completed action, Xochitl should suggest the logical next step:

| Completed action | Suggested next |
|---|---|
| BMAD artifacts all saved | "Want me to generate SDD requirements?" |
| Specs generated | "Ready to scaffold the code?" |
| Issue created | "Should I analyze this against your specs?" |
| Issue analyzed | "Want me to update the spec and fix the code?" |
| Code scaffolded | "Want me to generate tests for each acceptance criterion?" |

Implement as `SDDSkill._get_next_step_suggestion(project_id)` called after each successful execute().

### 5.5 End-to-end test criteria (Phase 5 done when)
- [ ] "I want to build a diet app" → guided through BMAD → `projects/diet-tracker/` created
- [ ] BMAD complete → specs generated → 10–15 FR-* in `specs/core-features.md`
- [ ] "Scaffold the backend" → FastAPI files written under `projects/diet-tracker/src/`
- [ ] "There's a bug: app accepts negative calories" → analyzed → spec updated → code fix applied → issue closed
- [ ] "Where is FR-CORE-001 implemented?" → Xochitl reads `traceability.json` and reports file/function
- [ ] All spec IDs traceable end-to-end: BMAD source → FR-* → AC-* → code file/function → test case

---

## Cross-Cutting Constraints

These apply to every phase:

1. **No direct LLM calls.** Always use `TieredRouter.route()`. Never import `ollama` or `google.generativeai` directly in new files.

2. **No raw `open()` for project files.** Use `FileTools.read_file()` / `write_file()` for user-visible artifacts, or `pathlib.Path` for internal reads. File writes to `projects/` need to pass through the security sandbox.

3. **No duplicate skill infrastructure.** New skills extend `Skill` ABC from `src/skills/base.py`. No new base classes.

4. **Conversation personality.** All `suggest()` return values and `execute()` result messages must match SOUL.md tone — direct, calm, slightly dry. No corporate boilerplate ("Certainly! I'd be happy to...").

5. **Deprecate, don't delete.** Requirement status goes to `deprecated`, issues move to `closed/`. Nothing is permanently removed.

6. **YAML safety.** Use `PyYAML` with `yaml.safe_load()` / `yaml.safe_dump()`. Never `yaml.load()` without Loader.

7. **JSON parse resilience.** LLM responses for spec/code generation must be validated. If parse fails, retry the LLM call once with an explicit "your previous response was not valid JSON, try again" prefix, then surface a human-readable error.

---

## Dependency Map

```
Phase 1 (Foundation)
  └── Phase 2 (SDD Core)          ← requires BMADSkill.init_project + save_bmad_artifact
        └── Phase 3 (Issues)      ← requires SDDSkill.generate_specs_from_bmad
              └── Phase 4 (Code)  ← requires SDDSkill.analyze_issue + update_requirement
                    └── Phase 5   ← requires all phases complete
```

Phases must be built in order. Do not start Phase 2 until Phase 1 integration tests pass.

---

## Files to Create

| File | Phase | Purpose |
|---|---|---|
| `projects/.gitkeep` | 1 | Track empty dir |
| `.sdd/config.yml` | 1 | SDD system config |
| `.sdd/prompts/spec-generation.md` | 1 | LLM prompt template |
| `.sdd/prompts/issue-analysis.md` | 1 | LLM prompt template |
| `.sdd/prompts/code-generation.md` | 1 | LLM prompt template |
| `.sdd/logs/.gitkeep` | 1 | Track empty log dir |
| `src/skills/sdd_skill.py` | 2 | SDDSkill class |
| `src/skills/code_skill.py` | 4 | CodeSkill class |

## Files to Modify

| File | Phase | Change |
|---|---|---|
| `src/skills/bmad_skill.py` | 1 | Add `init_project`, `save_bmad_artifact`, `get_bmad_artifacts`, `is_bmad_complete`, `list_projects` |
| `src/tools.py` | 1–4 | Add `_handle_*` functions + dispatch entries (across all phases) |
| `src/chat.py` | 5 | Add `current_project` field, `_detect_current_project()`, `_check_specs_exist()`, `_check_bmad_complete()`, new intent types, register new skills |

---

*Start with Phase 1. Test each phase before proceeding.*
