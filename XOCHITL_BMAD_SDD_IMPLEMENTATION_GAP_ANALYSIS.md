# Xochitl BMAD-SDD Implementation Gap Analysis

**Purpose:** This document identifies what needs to be added to the existing Xochitl codebase to support full BMAD → SDD → Code Generation workflows for building new applications.

**Audience:** Claude Code reading this to implement missing pieces.

---

## Current State (What Exists)

### ✅ Already Implemented

**Core Infrastructure:**
- `src/chat.py` — XochitlChat with conversational loop, intent classification, tool routing
- `src/router.py` — TieredRouter for local (gemma4-e4b) vs cloud (Gemini/Claude) routing
- `src/context_loader.py` — System prompt building from MEMORY.md + global.md
- `src/memory.py` — 3-tier memory (MEMORY.md, SQLite sessions, ChromaDB)
- `src/database.py` — SQLite schema for tasks/projects/queue
- `src/task_manager.py` — Task CRUD, queue management, WIP limit enforcement
- `src/notion_sync.py` — Notion integration with conflict detection
- `src/security.py` — Path sandboxing for file operations

**Skills System:**
- `src/skills/base.py` — Skill ABC with `can_handle()`, `suggest()`, `execute()`
- `src/skills/bmad_skill.py` — BMADSkill (PARTIAL — needs expansion)
- `src/skills/notion_skill.py` — NotionSkill for Notion sync
- `src/skills/orchestrator_skill.py` — Background task orchestration

**BMAD Support (Partial):**
- `src/bmad.py` — Detects BMAD projects (looks for `.clinerules/`)
- BMAD context loading into system prompts
- Artifact save locations defined (`planning-artifacts/`, `implementation-artifacts/`)

**Existing Directory Structure:**
```
./
├── src/              # All source code
├── config/
│   ├── global.md     # PARA philosophy
│   └── projects/     # Per-project context
├── data/
│   ├── tasks.db      # SQLite
│   └── queue.md      # WIP queue
├── .xochitl/
│   └── workspaces/   # Background task workspaces
├── MEMORY.md
├── SOUL.md
└── CLAUDE.md
```

---

## What's Missing (Gaps to Fill)

### 🔴 Missing: Project-Based BMAD-SDD Workflow

**Current limitation:** BMAD support only detects existing BMAD projects (`.clinerules/`). There's no flow for:
1. Initializing NEW projects with BMAD structure
2. Saving BMAD artifacts (business-model.md, architecture.md, design-specs.md)
3. Generating SDD specs FROM BMAD artifacts
4. Creating traceable requirements (FR-*, AC-*, EC-*)
5. Managing issues/bugs against specs
6. Generating code from specs
7. Updating specs when code changes

**What needs to be built:** A complete project lifecycle system.

---

## Implementation Plan

### Part 1: Project Structure Extension

**Add this to existing structure:**

```
./
├── projects/                      # NEW: Apps being built WITH Xochitl
│   └── <project-id>/              # e.g., "diet-tracker"
│       ├── .project-meta.yml      # Project metadata
│       ├── bmad/                  # BMAD artifacts
│       │   ├── business-model.md
│       │   ├── architecture.md
│       │   ├── design-specs.md
│       │   └── constraints.md
│       ├── specs/                 # SDD requirements
│       │   ├── core-features.md   # FR-CORE-001, AC-CORE-001, etc.
│       │   ├── api-contracts.md   # FR-API-001, etc.
│       │   └── traceability.json  # Requirement → code mapping
│       ├── issues/                # Bug/feature tracking
│       │   ├── open/
│       │   │   └── BUG-001.yml
│       │   ├── in-progress/
│       │   └── closed/
│       └── src/                   # Generated application code
│           ├── api/
│           ├── models/
│           └── tests/
│
├── .sdd/                          # NEW: SDD system config
│   ├── config.yml                 # SDD settings
│   ├── prompts/                   # LLM prompts for SDD workflows
│   │   ├── spec-generation.md
│   │   ├── issue-analysis.md
│   │   └── code-generation.md
│   └── logs/
│       ├── spec-changes.jsonl
│       └── decisions.jsonl
```

### Part 2: Data Schemas

**File: `projects/<project-id>/.project-meta.yml`**

```yaml
project_id: "diet-tracker"
name: "Diet Tracking App"
description: "Meal prep macro tracker"
created: "2024-05-02T10:00:00Z"
status: "active"  # active | paused | archived

bmad_complete: true
specs_generated: true
code_scaffolded: false

stack:
  backend: "FastAPI"
  frontend: "React"
  database: "PostgreSQL"

stats:
  total_requirements: 12
  implemented_requirements: 0
  open_issues: 0

last_worked: "2024-05-02T15:30:00Z"
```

**File: `projects/<project-id>/bmad/business-model.md`**

```markdown
# Business Model — <Project Name>

## Problem Space
**Who:** [Target users]
**Struggle:** [Core problem]
**Current Solutions:** [Existing alternatives]
**Pain:** [Key frustration]

## Solution
**Job to be Done:** [JTBD statement]
**Core Value:** [Value proposition]
**Differentiation:** [Unique angle]

## Success Metrics
- [Metric 1]
- [Metric 2]

## Business Model
[Revenue model, distribution, etc.]

## Risk Assessment
- **Risk:** [Description]
  **Mitigation:** [How to address]
```

**File: `projects/<project-id>/specs/core-features.md`**

```markdown
---
feature: core
owner: you
last_updated: 2024-05-02
---

# Core Features — <Project Name>

## FR-CORE-001: [Feature Name]
**Status:** active | not_implemented | deprecated
**Priority:** P0 | P1 | P2 | P3
**BMAD Source:** `bmad/business-model.md` section X

**Description:**
[What this requirement does]

**Acceptance Criteria:**
- AC-CORE-001: GIVEN [context] WHEN [action] THEN [expected result]
- AC-CORE-002: [Another criterion]

**Edge Cases:**
- EC-CORE-001: GIVEN [unusual input] WHEN [action] THEN [expected behavior]

**Implementation:**
- File: `src/api/endpoint.py::function_name()`
- Tests: `tests/test_endpoint.py::test_case`

**Traceability:**
- Maps to: BMAD `business-model.md` lines 45-60
- Issue: BUG-003
- Modified: 2024-05-02 by [reason]

---

## FR-CORE-002: [Next Requirement]
...
```

**File: `projects/<project-id>/specs/traceability.json`**

```json
{
  "project": "diet-tracker",
  "version": "1.0",
  "last_updated": "2024-05-02T15:00:00Z",
  "mappings": [
    {
      "id": "FR-CORE-001",
      "type": "functional",
      "spec_file": "specs/core-features.md",
      "spec_section": "## FR-CORE-001",
      "bmad_sources": [
        {
          "file": "bmad/business-model.md",
          "section": "Solution",
          "relevance": "primary"
        }
      ],
      "implementation": [
        {
          "file": "src/api/meals.py",
          "functions": ["create_meal"],
          "lines": [45, 89]
        }
      ],
      "tests": [
        {
          "file": "tests/test_meals.py",
          "cases": ["test_create_meal_success"]
        }
      ],
      "issues": [],
      "status": "implemented"
    }
  ]
}
```

**File: `projects/<project-id>/issues/open/BUG-001.yml`**

```yaml
id: BUG-001
type: bug  # bug | feature | enhancement
project: diet-tracker
created: 2024-05-02T16:00:00Z
status: open  # open | in-progress | closed

title: "Short description"
description: |
  Detailed description of the issue.

reproduction:
  - Step 1
  - Step 2
  - Observe problem

expected: "What should happen"
actual: "What actually happens"

environment:
  version: "0.1.0"
  platform: "API"

affected_requirements:
  - FR-CORE-002

analysis: null  # Filled by SDD analysis
spec_impact: null
priority: P2  # P0 | P1 | P2 | P3
```

**File: `.sdd/config.yml`**

```yaml
# Simplified SDD configuration for solo developer

llm:
  # Use existing router.py for routing
  provider: "tiered"  # Uses TieredRouter
  
workflow:
  auto_analyze_issues: true
  require_manual_approval: false  # Solo dev, no approvals needed
  auto_update_specs: true
  
confidence:
  min_for_auto_action: 0.75
  
directories:
  projects: "projects"
  sdd_config: ".sdd"
  logs: ".sdd/logs"
```

---

### Part 3: New Skills to Implement

**Expand `src/skills/bmad_skill.py`:**

Current state: Only detects BMAD projects and loads context.

**Add these methods:**

```python
class BMADSkill(Skill):
    # EXISTING (keep these)
    def can_handle(user_input, context) -> float
    def suggest(user_input, context) -> str
    def execute(user_input, context, params) -> str
    
    # NEW: Add these
    def init_project(project_id: str, name: str, description: str) -> dict
    def save_business_model(project_id: str, content: dict) -> str
    def save_architecture(project_id: str, content: dict) -> str
    def save_design_specs(project_id: str, content: dict) -> str
    def get_bmad_artifacts(project_id: str) -> dict
```

**Create `src/skills/sdd_skill.py` (NEW FILE):**

```python
from .base import Skill

class SDDSkill(Skill):
    """Spec-Driven Development workflow skill."""
    
    def can_handle(self, user_input: str, context: dict) -> float:
        """Detect SDD-related requests."""
        sdd_keywords = [
            'spec', 'requirement', 'analyze', 'bug', 'issue',
            'traceability', 'FR-', 'AC-', 'EC-'
        ]
        
        score = 0.0
        lower = user_input.lower()
        
        for keyword in sdd_keywords:
            if keyword.lower() in lower:
                score += 0.2
        
        # Boost if in a project directory
        if context.get('current_project'):
            score += 0.3
        
        return min(score, 1.0)
    
    def suggest(self, user_input: str, context: dict) -> str:
        if 'spec' in user_input.lower() and not context.get('specs_generated'):
            return "I can generate SDD requirements from your BMAD artifacts. Want me to do that?"
        
        if 'bug' in user_input.lower() or 'issue' in user_input.lower():
            return "I can analyze this against your specs and suggest updates. Should I?"
        
        return "I can help with spec-driven development tasks."
    
    def execute(self, user_input: str, context: dict, params: dict = None) -> str:
        # Route to appropriate handler
        if params and params.get('action') == 'generate_specs':
            return self.generate_specs_from_bmad(context['current_project'])
        elif params and params.get('action') == 'analyze_issue':
            return self.analyze_issue(context['current_project'], params['issue_id'])
        # ... more handlers
    
    # Core SDD methods
    def generate_specs_from_bmad(self, project_id: str) -> str:
        """Generate SDD requirements from BMAD artifacts using LLM."""
        pass
    
    def analyze_issue(self, project_id: str, issue_id: str) -> str:
        """Analyze bug/feature against specs."""
        pass
    
    def update_requirement(self, project_id: str, requirement_id: str, updates: dict) -> str:
        """Update a requirement and traceability matrix."""
        pass
    
    def create_requirement(self, project_id: str, req_type: str, content: dict) -> str:
        """Create new requirement."""
        pass
    
    def get_requirement(self, project_id: str, requirement_id: str) -> dict:
        """Retrieve requirement details."""
        pass
    
    def update_traceability(self, project_id: str, requirement_id: str, impl_data: dict) -> str:
        """Update traceability matrix after code changes."""
        pass
```

**Create `src/skills/code_skill.py` (NEW FILE):**

```python
from .base import Skill

class CodeSkill(Skill):
    """Code generation from SDD specs."""
    
    def can_handle(self, user_input: str, context: dict) -> float:
        """Detect code generation requests."""
        code_keywords = [
            'generate', 'scaffold', 'implement', 'code',
            'build', 'create app', 'fix'
        ]
        
        score = 0.0
        lower = user_input.lower()
        
        for keyword in code_keywords:
            if keyword in lower:
                score += 0.2
        
        # Need specs to exist
        if context.get('specs_generated'):
            score += 0.3
        
        return min(score, 1.0)
    
    def suggest(self, user_input: str, context: dict) -> str:
        if not context.get('specs_generated'):
            return "You'll need to generate specs first before I can scaffold code."
        
        return "I can generate code from your specs. Which component should I start with?"
    
    def execute(self, user_input: str, context: dict, params: dict = None) -> str:
        # Route to handlers
        pass
    
    # Core code generation methods
    def scaffold_from_specs(self, project_id: str, component: str) -> str:
        """Generate initial code structure from specs."""
        pass
    
    def generate_code_for_requirement(self, project_id: str, requirement_id: str) -> str:
        """Implement a specific requirement."""
        pass
    
    def fix_issue(self, project_id: str, issue_id: str) -> str:
        """Fix a bug using spec context."""
        pass
    
    def generate_tests(self, project_id: str, requirement_id: str) -> str:
        """Generate tests from acceptance criteria."""
        pass
```

---

### Part 4: Project Context Detection

**Modify `src/chat.py` to detect project context:**

Add to `XochitlChat.__init__()`:

```python
self.current_project = None  # Current project if in projects/ directory
```

Add to `process_message()` before intent classification:

```python
# Detect if in a project directory
self.current_project = self._detect_current_project()
if self.current_project:
    self.current_context['current_project'] = self.current_project
    self.current_context['specs_generated'] = self._check_specs_exist(self.current_project)
```

Add new methods:

```python
def _detect_current_project(self) -> str | None:
    """Detect if currently in a projects/ subdirectory."""
    import os
    from pathlib import Path
    
    cwd = Path.cwd()
    projects_root = Path("projects")
    
    # Check if CWD is inside projects/
    try:
        relative = cwd.relative_to(projects_root.resolve())
        # Extract project ID (first directory level)
        project_id = str(relative).split('/')[0]
        
        # Verify .project-meta.yml exists
        meta_file = projects_root / project_id / ".project-meta.yml"
        if meta_file.exists():
            return project_id
    except ValueError:
        pass
    
    return None

def _check_specs_exist(self, project_id: str) -> bool:
    """Check if specs have been generated for project."""
    from pathlib import Path
    
    specs_dir = Path("projects") / project_id / "specs"
    return specs_dir.exists() and any(specs_dir.glob("*-features.md"))
```

---

### Part 5: Conversation Flow Examples

**Example 1: New Project Initialization**

```
User: I want to build a diet tracking app

Xochitl: Let's break this down with BMAD. I'll create a new project structure for you.

[calls: bmad_skill.init_project("diet-tracker", "Diet Tracking App")]

Created projects/diet-tracker/. Now, starting with the business model—what's the core struggle this solves?

User: Meal preppers who lose track of macros mid-week

Xochitl: Got it. What outcome do they want?

User: Confidence that their prep is working without manual logging

Xochitl: Perfect. [saves business model]

Now let's talk architecture. Mobile, web, or both?

[... continues BMAD conversation ...]

Xochitl: BMAD complete. Want me to generate SDD requirements now?

User: Yes

Xochitl: [calls: sdd_skill.generate_specs_from_bmad("diet-tracker")]

Generated 12 requirements in projects/diet-tracker/specs/core-features.md:
- FR-CORE-001: Meal prep entry
- FR-CORE-002: Macro calculation
[...]

Ready to scaffold the code?
```

**Example 2: Bug Fix**

```
User: There's a bug - the app accepts negative calories

Xochitl: Let me analyze this against your specs.

[calls: sdd_skill.analyze_issue("diet-tracker", current_bug_context)]

Found the issue. FR-CORE-001 says "accept meal data" but doesn't specify validation. This is a spec gap.

I can:
1. Update FR-CORE-001 to add validation requirement
2. Create new FR-CORE-006 for input validation

Which makes more sense?

User: Update FR-CORE-001

Xochitl: [calls: sdd_skill.update_requirement(...)]

Updated FR-CORE-001 with:
"AC-CORE-001: Given negative calorie value, system returns 400 with error"

Want me to fix the code too?

User: Yes

Xochitl: [calls: code_skill.fix_issue("diet-tracker", "BUG-001")]

Added validation in src/api/meals.py. Updated traceability matrix.
Created test: tests/test_meals.py::test_negative_calories_rejected
```

---

### Part 6: Integration with Existing Router

**Use existing `TieredRouter` for LLM calls:**

Don't create new LLM clients. Use what exists:

```python
# In sdd_skill.py or code_skill.py

from ..router import TieredRouter

def generate_specs_from_bmad(self, project_id: str):
    router = TieredRouter()
    
    # Load BMAD content
    business_model = self._load_bmad_file(project_id, "business-model.md")
    architecture = self._load_bmad_file(project_id, "architecture.md")
    
    # Build prompt
    prompt = f"""Generate SDD requirements from BMAD artifacts.

BMAD Business Model:
{business_model}

BMAD Architecture:
{architecture}

Output JSON with requirements in this format:
{{
  "requirements": [
    {{
      "id": "FR-CORE-001",
      "description": "...",
      "acceptance_criteria": ["AC-CORE-001: ..."],
      "bmad_source": "business-model.md section X"
    }}
  ]
}}
"""
    
    # Route to appropriate model
    response = router.route(
        query=prompt,
        route_type="bmad_complex",  # Uses cloud model
        system_context="You are generating SDD requirements."
    )
    
    # Parse and save specs
    # ...
```

---

### Part 7: Prompts to Create

**File: `.sdd/prompts/spec-generation.md`**

```markdown
# Spec Generation Prompt

You are generating SDD (Spec-Driven Development) requirements from BMAD artifacts.

## Input
You will receive:
1. BMAD Business Model
2. BMAD Architecture
3. BMAD Design Specs (optional)

## Output Format

Output ONLY JSON. No markdown wrapping. Pure JSON.

```json
{
  "requirements": [
    {
      "id": "FR-CORE-001",
      "feature_area": "CORE",
      "description": "One-sentence description",
      "acceptance_criteria": [
        "AC-CORE-001: GIVEN [context] WHEN [action] THEN [result]",
        "AC-CORE-002: ..."
      ],
      "edge_cases": [
        "EC-CORE-001: GIVEN [unusual case] WHEN [action] THEN [behavior]"
      ],
      "bmad_source": "business-model.md: Solution section"
    }
  ]
}
```

## Requirements Guidelines

1. **IDs:** Format is `FR-<AREA>-<NUM>` where AREA = CORE|API|UI|DATA|AUTH
2. **Descriptions:** One clear sentence. No fluff.
3. **Acceptance Criteria:** Use GIVEN/WHEN/THEN format. Must be testable.
4. **Coverage:** Extract 8-15 requirements from BMAD. Focus on core features.
5. **Traceability:** Link each requirement to specific BMAD section

## Example

Good:
```
"id": "FR-CORE-001",
"description": "Users can create meal prep entries with ingredients and macros",
"acceptance_criteria": [
  "AC-CORE-001: GIVEN valid meal data, WHEN user submits, THEN system saves to database within 200ms",
  "AC-CORE-002: GIVEN duplicate meal name, WHEN user submits, THEN system returns 409 conflict"
]
```

Bad:
```
"description": "The system should allow users to create meals in a user-friendly way"
"acceptance_criteria": ["System should be fast and reliable"]
```
```

**File: `.sdd/prompts/issue-analysis.md`**

```markdown
# Issue Analysis Prompt

Analyze a bug or feature request against existing SDD specifications.

## Input
- Issue description (bug report or feature request)
- Current specification sections
- Traceability data

## Task
Determine:
1. Is this a spec bug (spec is wrong) or implementation bug (code doesn't match spec)?
2. Which requirements are affected?
3. What spec changes are needed?

## Output Format

```json
{
  "analysis_type": "spec_bug | implementation_bug | spec_gap | both",
  "affected_requirements": ["FR-CORE-001", "AC-CORE-003"],
  "spec_changes_needed": [
    {
      "requirement_id": "FR-CORE-001",
      "change_type": "modify | create | deprecate",
      "current_text": "existing text or null",
      "proposed_text": "new text",
      "rationale": "why this change is needed"
    }
  ],
  "implementation_guidance": [
    "Update validation in src/api/meals.py",
    "Add test case for negative values"
  ],
  "confidence": 0.85
}
```

## Guidelines
- Be specific about what's wrong
- Proposed text must be testable (GIVEN/WHEN/THEN)
- Confidence < 0.75 means human review needed
```

**File: `.sdd/prompts/code-generation.md`**

```markdown
# Code Generation Prompt

Generate implementation code from SDD specifications.

## Input
- Requirement ID and full spec text
- Tech stack from BMAD architecture
- Existing code structure (if any)

## Task
Generate code that:
1. Implements the requirement
2. Satisfies all acceptance criteria
3. Handles edge cases
4. Includes inline comments referencing requirement IDs

## Output Format

```json
{
  "files": [
    {
      "path": "src/api/meals.py",
      "content": "# Full file content...",
      "action": "create | modify"
    }
  ],
  "tests": [
    {
      "path": "tests/test_meals.py",
      "content": "# Test file content...",
      "action": "create | modify"
    }
  ],
  "traceability_updates": [
    {
      "requirement_id": "FR-CORE-001",
      "implementation": {
        "file": "src/api/meals.py",
        "functions": ["create_meal"],
        "lines": [45, 89]
      }
    }
  ]
}
```

## Code Quality
- Follow Python conventions (PEP 8)
- Include docstrings
- Reference requirement IDs in comments: `# Implements FR-CORE-001`
- Type hints required
- No TODOs or placeholders
```

---

### Part 8: Skills Registration

**Modify `src/tools.py` (or wherever skills are registered):**

```python
from .skills.bmad_skill import BMADSkill
from .skills.sdd_skill import SDDSkill  # NEW
from .skills.code_skill import CodeSkill  # NEW
from .skills.notion_skill import NotionSkill
from .skills.orchestrator_skill import OrchestratorSkill

# Register all skills
SKILLS = [
    BMADSkill(),
    SDDSkill(),      # NEW
    CodeSkill(),     # NEW
    NotionSkill(),
    OrchestratorSkill()
]
```

---

### Part 9: CLI Commands (Optional Extensions)

**Add to `src/cli.py` if you want direct commands:**

```python
@click.command()
@click.argument('project_id')
def init_project(project_id):
    """Initialize new BMAD-SDD project."""
    # Delegates to BMADSkill.init_project()
    pass

@click.command()
@click.argument('project_id')
def generate_specs(project_id):
    """Generate SDD specs from BMAD artifacts."""
    # Delegates to SDDSkill.generate_specs_from_bmad()
    pass

@click.command()
@click.argument('project_id')
@click.argument('issue_id')
def analyze_issue(project_id, issue_id):
    """Analyze issue against specs."""
    # Delegates to SDDSkill.analyze_issue()
    pass
```

**But prioritize conversational interface over CLI commands.** The point is to talk to Xochitl, not type commands.

---

## Implementation Priority

**Phase 1: Foundation (Weekend 1)**
1. Create directory structure (`projects/`, `.sdd/`)
2. Implement data schemas (`.project-meta.yml`, spec format, traceability.json)
3. Expand `BMADSkill` with project init + BMAD artifact saving
4. Test: "I want to build X" → creates project structure + saves BMAD

**Phase 2: SDD Core (Weekend 2)**
1. Create `SDDSkill` class
2. Implement `generate_specs_from_bmad()` using existing TieredRouter
3. Create prompts in `.sdd/prompts/`
4. Test: BMAD complete → generates specs

**Phase 3: Issue Analysis (Weekend 3)**
1. Implement `analyze_issue()` in SDDSkill
2. Implement `update_requirement()` and traceability updates
3. Test: Create issue → analyze → update spec

**Phase 4: Code Generation (Weekend 4)**
1. Create `CodeSkill` class
2. Implement `scaffold_from_specs()` using qwen2.5-coder
3. Implement `fix_issue()` with spec context
4. Test: Specs → scaffolded code

**Phase 5: Integration (Weekend 5)**
1. Project context detection in `chat.py`
2. Skill scoring and suggestions
3. End-to-end test: New project → BMAD → specs → code → bug fix
4. Documentation and examples

---

## Key Design Decisions

### 1. **Don't Duplicate What Exists**

✅ Use existing `TieredRouter` for LLM calls
✅ Use existing `SOUL.md` personality
✅ Use existing skill system pattern
✅ Store conversation in existing SQLite sessions table

❌ Don't create new LLM clients
❌ Don't create separate chat loop
❌ Don't reinvent tool routing

### 2. **Lightweight, Not Enterprise**

This is for solo development, not a team of 50.

✅ Simplified config (no tiers, no approvals)
✅ Auto-update specs (no human-in-loop gates)
✅ Simple requirement IDs (FR-CORE-001, not FR-AUTH-API-GATEWAY-001)
✅ ~10-20 requirements per project, not 500

❌ No approval workflows
❌ No metrics dashboards
❌ No elaborate traceability (just JSON file)

### 3. **Conversational First**

The primary interface is chat, not commands.

✅ Detect project context automatically
✅ Suggest next steps naturally
✅ Ask before overwriting files
✅ Offer options, don't force decisions

❌ Don't make the user type `xochitl sdd analyze BUG-001`
✅ Instead: "There's a bug with negative calories" → Xochitl analyzes it

### 4. **BMAD → SDD → Code Flow**

Always follow this order:

```
Business Model → Architecture → Design Specs
  ↓
Generate SDD Requirements
  ↓
Scaffold Code from Specs
  ↓
Bug Found → Analyze Against Specs → Update Spec → Fix Code
```

Never skip BMAD. Never code without specs.

---

## What Claude Code Should Do

1. **Read this entire document**
2. **Check existing codebase** (especially `src/chat.py`, `src/skills/`, `src/router.py`)
3. **Implement missing pieces** in this order:
   - Project directory structure
   - Data schemas (YAML, JSON, Markdown templates)
   - Expand `BMADSkill` with new methods
   - Create `SDDSkill` class
   - Create `CodeSkill` class
   - Create prompts in `.sdd/prompts/`
   - Add project context detection to `chat.py`
   - Register new skills in `tools.py`
4. **Test each phase** before moving to next
5. **Follow existing patterns** (don't reinvent what works)

---

## Success Criteria

You'll know it's working when:

✅ User says "I want to build a diet app" → Xochitl guides through BMAD
✅ BMAD complete → Xochitl generates 10-15 requirements in `specs/`
✅ User says "scaffold the backend" → Xochitl generates FastAPI code from specs
✅ User reports bug → Xochitl analyzes against specs, updates requirement, fixes code
✅ All artifacts traceable: BMAD → Spec → Code → Tests
✅ User can ask "where is FR-CORE-001 implemented?" → Xochitl shows file/function

---

## Files to Create

**New Files:**
- `src/skills/sdd_skill.py`
- `src/skills/code_skill.py`
- `.sdd/config.yml`
- `.sdd/prompts/spec-generation.md`
- `.sdd/prompts/issue-analysis.md`
- `.sdd/prompts/code-generation.md`

**Files to Modify:**
- `src/skills/bmad_skill.py` (expand with project init methods)
- `src/chat.py` (add project context detection)
- `src/tools.py` (register new skills)

**Template Files to Create:**
- Templates for `.project-meta.yml`
- Templates for spec files
- Templates for issue files

---

## Notes for Implementation

- **Use existing imports** — don't duplicate. Import from `..router`, `..database`, etc.
- **Match existing style** — look at `orchestrator_skill.py` as reference
- **Error handling** — wrap LLM calls in try/except, log failures
- **Logging** — use `.sdd/logs/` for decisions and spec changes
- **File operations** — respect `src/security.py` sandboxing rules
- **LLM calls** — always go through `TieredRouter`, never direct API calls
- **Conversation flow** — maintain Xochitl's personality from `SOUL.md`

---

## Questions? Edge Cases?

**Q: What if user is already in existing code project (not BMAD)?**
A: Xochitl can still help but won't auto-detect as "project". User would need to say "treat this as a project" or "initialize BMAD here."

**Q: What if BMAD artifacts are incomplete?**
A: `generate_specs_from_bmad()` should check for required files and prompt user to complete BMAD first.

**Q: What if spec and code diverge?**
A: That's expected. When user reports bug or makes changes, `analyze_issue()` detects divergence and suggests spec update.

**Q: Should specs be updated before or after code changes?**
A: Before. Workflow is: Bug → Analyze → Update Spec → Generate Code Fix → Update Traceability.

**Q: What if user wants to delete a requirement?**
A: Mark as `status: deprecated` rather than deleting. Keep history.

---

## Final Checklist for Claude Code

Before saying "done":

- [ ] All new skills follow `Skill` ABC pattern
- [ ] All LLM calls go through `TieredRouter`
- [ ] Project context detection works in `chat.py`
- [ ] Skills registered and scoring works
- [ ] Can create new project from conversation
- [ ] Can save BMAD artifacts
- [ ] Can generate specs from BMAD
- [ ] Can analyze issues against specs
- [ ] Can scaffold code from specs
- [ ] Traceability matrix updates correctly
- [ ] All prompts created in `.sdd/prompts/`
- [ ] Example conversation flows work end-to-end
- [ ] Follows existing code style and patterns
- [ ] No duplicate LLM clients or routers
- [ ] Respects Xochitl's personality (SOUL.md)

---

**End of Gap Analysis**

Claude Code: You now have everything you need to implement BMAD-SDD tools in Xochitl. Start with Phase 1, test thoroughly, then proceed through phases 2-5. Follow existing patterns. Ask questions if anything is unclear.
