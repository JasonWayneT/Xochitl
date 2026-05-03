# Xochitl Harness Engineering Implementation Plan

**Based on:** OpenAI Symphony, Martin Fowler's Guides & Sensors Framework  
**Date:** April 30, 2026  
**Status:** Prescriptive Implementation Guide

---

## EXECUTIVE SUMMARY: THE CORE PROBLEM

Your current Xochitl architecture has a **powerful CPU** (tiered LLM routing) but a **weak OS** (harness). You're focused on the model's capabilities when the real engineering is in the scaffolding around it.

**The Symphony Insight:** Teams saw 500% more PRs not by improving the model, but by shifting from "managing coding sessions" to "managing work that needs to get done."

**Your Shift:** Move from "managing Xochitl conversations" to "managing projects that need strategic execution."

---

## PART 1: THE ORCHESTRATOR LAYER (NEW - HIGHEST PRIORITY)

### Current State
- Xochitl is session-based: User opens terminal → chats → closes terminal → context lost
- Notion tasks exist separately from execution
- No autonomous task execution

### Target State (Symphony Pattern)
- **Task-to-Workspace Mapping:** Each Notion task gets an isolated execution environment
- **Autonomous Loop:** Xochitl polls the WIP queue, executes tasks, creates artifacts, waits for review
- **State Machine:** Tasks flow through defined states without manual supervision

### Implementation: `src/orchestrator.py`

```python
# src/orchestrator.py

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal
import time
from datetime import datetime
import subprocess

TaskState = Literal['queued', 'in_progress', 'review', 'done', 'blocked']

@dataclass
class TaskWorkspace:
    """Isolated workspace for each task - Symphony's key innovation"""
    task_id: str
    notion_task_id: Optional[str]
    workspace_dir: Path  # git worktree for this task
    state: TaskState
    started_at: datetime
    last_heartbeat: datetime
    agent_pid: Optional[int]
    branch_name: str
    artifacts: list[Path]
    
class TaskOrchestrator:
    """
    Symphony-style orchestrator that manages WORK, not SESSIONS.
    
    This is the missing layer between your Notion queue and your agent.
    """
    
    def __init__(
        self, 
        project_root: Path,
        notion_client,
        task_db,
        llm_router
    ):
        self.project_root = project_root
        self.workspaces_dir = project_root / ".xochitl/workspaces"
        self.notion = notion_client
        self.db = task_db
        self.router = llm_router
        self.active_workspaces: dict[str, TaskWorkspace] = {}
        
    def start(self):
        """
        Main orchestrator loop - runs continuously in background
        
        This is Symphony's core: guarantee that for every open task,
        an agent is running in its own workspace.
        """
        print("🌸 Xochitl Orchestrator starting...")
        
        while True:
            try:
                # 1. Poll Notion for new tasks in WIP Queue
                wip_tasks = self._poll_notion_queue()
                
                # 2. For each task, ensure workspace exists
                for task in wip_tasks:
                    if task.id not in self.active_workspaces:
                        self._spawn_workspace(task)
                
                # 3. Monitor active workspaces
                self._monitor_workspaces()
                
                # 4. Clean up completed workspaces
                self._cleanup_completed()
                
                time.sleep(30)  # Poll every 30s
                
            except KeyboardInterrupt:
                print("\n🌸 Orchestrator shutting down...")
                self._cleanup_all()
                break
            except Exception as e:
                print(f"⚠️  Orchestrator error: {e}")
                time.sleep(60)  # Back off on errors
    
    def _spawn_workspace(self, task) -> TaskWorkspace:
        """
        Create isolated workspace for task - git worktree pattern
        
        Each task gets:
        - Its own directory
        - Its own git branch
        - Its own agent process
        - Its own artifact folder
        """
        task_id = task.id
        branch_name = f"task/{task_id}"
        workspace_dir = self.workspaces_dir / task_id
        
        # Create git worktree
        subprocess.run([
            'git', 'worktree', 'add',
            str(workspace_dir),
            '-b', branch_name
        ], cwd=self.project_root)
        
        # Create artifacts directory
        artifacts_dir = workspace_dir / "task-artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        
        # Create progress file (critical for session bridging)
        progress_file = artifacts_dir / "progress.json"
        progress_file.write_text(self._initial_progress(task))
        
        # Spawn agent process
        agent_pid = self._spawn_agent(task, workspace_dir)
        
        # Register workspace
        workspace = TaskWorkspace(
            task_id=task_id,
            notion_task_id=task.notion_id,
            workspace_dir=workspace_dir,
            state='in_progress',
            started_at=datetime.now(),
            last_heartbeat=datetime.now(),
            agent_pid=agent_pid,
            branch_name=branch_name,
            artifacts=[]
        )
        
        self.active_workspaces[task_id] = workspace
        
        print(f"✨ Spawned workspace for task: {task.description[:50]}")
        return workspace
    
    def _spawn_agent(self, task, workspace_dir: Path) -> int:
        """
        Start Xochitl agent process for this task
        
        The agent runs autonomously until:
        - Task is complete
        - Task is blocked
        - Agent crashes (orchestrator restarts it)
        """
        # Build agent command
        cmd = [
            'xochitl', 'agent', 'run',
            '--task-id', task.id,
            '--workspace', str(workspace_dir),
            '--mode', 'autonomous'
        ]
        
        # Spawn process
        process = subprocess.Popen(
            cmd,
            cwd=workspace_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return process.pid
    
    def _monitor_workspaces(self):
        """
        Check health of active workspaces - restart crashed agents
        
        Symphony's resilience: agents will crash, orchestrator handles it
        """
        for task_id, workspace in list(self.active_workspaces.items()):
            # Check if agent is still running
            if not self._is_process_alive(workspace.agent_pid):
                print(f"🔄 Agent crashed for task {task_id}, restarting...")
                
                # Check progress file to see if we should retry
                progress = self._read_progress(workspace)
                
                if progress['retry_count'] < 3:
                    # Restart agent
                    new_pid = self._spawn_agent(
                        self.db.get_task(task_id),
                        workspace.workspace_dir
                    )
                    workspace.agent_pid = new_pid
                    
                    # Update progress
                    progress['retry_count'] += 1
                    self._write_progress(workspace, progress)
                else:
                    # Too many retries, mark as blocked
                    workspace.state = 'blocked'
                    self._notify_blocked(workspace)
            
            # Update heartbeat
            workspace.last_heartbeat = datetime.now()
    
    def _initial_progress(self, task) -> str:
        """
        Create initial progress file - critical for session bridging
        
        This is Anthropic's insight: structured progress files let
        a new agent pick up where the last one left off.
        """
        return json.dumps({
            'task_id': task.id,
            'description': task.description,
            'state': 'initialized',
            'completed_steps': [],
            'next_steps': self._decompose_task(task),
            'blocked_on': None,
            'retry_count': 0,
            'artifacts_created': [],
            'last_test_status': None,
            'notes': ''
        }, indent=2)
    
    def _decompose_task(self, task) -> list[str]:
        """
        Use LLM to break task into steps
        
        This is where the local model shines - fast decomposition
        """
        prompt = f"""
Task: {task.description}

Break this into 3-5 concrete, atomic steps.
Return ONLY a JSON array of strings.

Example: ["Step 1", "Step 2", "Step 3"]
"""
        
        response = self.router.route_local(prompt)
        steps = json.loads(response.content)
        return steps
```

### New CLI Commands

```python
# src/cli.py additions

@cli.command()
def orchestrate():
    """
    Start the Xochitl orchestrator (runs in background)
    
    This replaces manual task execution with autonomous loops.
    """
    orchestrator = TaskOrchestrator(
        project_root=Path.cwd(),
        notion_client=get_notion_client(),
        task_db=get_task_db(),
        llm_router=get_llm_router()
    )
    
    orchestrator.start()

@cli.command()
@click.argument('task_id')
def workspace(task_id: str):
    """
    Jump into a task's workspace
    
    Example: xochitl workspace task-123
    """
    workspace_dir = Path.home() / f".xochitl/workspaces/{task_id}"
    
    if not workspace_dir.exists():
        console.print(f"[red]No workspace found for task {task_id}[/red]")
        return
    
    # Open new terminal in workspace directory
    subprocess.run(['gnome-terminal', '--working-directory', str(workspace_dir)])

@cli.command()
def workspaces():
    """
    List all active task workspaces
    """
    workspaces_dir = Path.home() / ".xochitl/workspaces"
    
    table = Table(title="Active Task Workspaces")
    table.add_column("Task ID")
    table.add_column("State")
    table.add_column("Started")
    table.add_column("Branch")
    
    for workspace_dir in workspaces_dir.iterdir():
        if workspace_dir.is_dir():
            progress_file = workspace_dir / "task-artifacts/progress.json"
            if progress_file.exists():
                progress = json.loads(progress_file.read_text())
                table.add_row(
                    workspace_dir.name,
                    progress['state'],
                    progress.get('started_at', 'unknown'),
                    f"task/{workspace_dir.name}"
                )
    
    console.print(table)
```

---

## PART 2: GUIDES & SENSORS FRAMEWORK (CRITICAL FIX)

### Current State
- "Pushback Level 3" in SOUL.md (vague)
- Linguistic filters (reactive, not systematic)
- No deterministic checks before cloud escalation

### Target State (Fowler's Framework)
- **Guides (Feedforward):** Constraints that prevent bad outputs before they happen
- **Sensors (Feedback):** Validation that catches errors and triggers self-correction

### Implementation: `AGENTS.md` (The Guide Layer)

```markdown
# AGENTS.md
# This file is loaded into EVERY agent context - it's the harness guide layer

## Project Constraints

### Architecture Rules
- Database access ONLY through `src/database.py` - no raw SQL in business logic
- All LLM calls MUST go through `src/llm_router.py` - no direct API calls
- Task state changes MUST update both SQLite AND Notion - no partial writes

### File Organization
- Planning artifacts → `planning-artifacts/`
- Generated code → `src/`
- Agent workspaces → `.xochitl/workspaces/`
- Never write to `/tmp/` or `~/.cache/` - use `.xochitl/temp/`

### Coding Standards
- Type hints required for all public functions
- Docstrings required for all classes and non-trivial functions
- Maximum function length: 50 lines (force decomposition)
- No print statements - use `rich.console` or logging

### BMAD Projects
If `.clinerules/` exists:
- Read `CLAUDE.md` for project-specific context
- Save artifacts following BMAD folder structure
- Update progress.json after each step
- Generate clickable file:// URIs for all created files

### Task Decomposition
When breaking down a task:
- Aim for 30-60 minute atomic units
- Each step must be independently testable
- Mark dependencies explicitly (blocked_by field)
- Surface rollover warnings at 3 days

### Error Handling
- Network calls: 3 retries with exponential backoff
- LLM failures: fall back to local model, then prompt user
- File operations: check permissions before writing
- Database: use transactions, rollback on error

## Tools Available

### Core Tools
- `read_file(path)` - Read file contents
- `write_file(path, content)` - Write to file (asks confirmation if exists)
- `list_files(directory)` - List directory contents
- `run_shell(command)` - Execute shell command (sandboxed)

### Task Management
- `create_task(description, project_id, time_estimate)`
- `update_task_status(task_id, new_status)`
- `get_wip_queue()` - Returns top 3 priority tasks
- `rollover_task(task_id, action)` - Handle stuck tasks

### Memory
- `update_memory(section, content)` - Update MEMORY.md
- `recall(query, recency_bias=True)` - Semantic search vector DB
- `memorize(topic, summary, tags)` - Commit to long-term memory

### BMAD (if in BMAD project)
- `detect_bmad_project()` - Returns project metadata
- `load_workflow(name)` - Load BMAD workflow prompt
- `save_artifact(type, content)` - Save to correct BMAD folder

## Response Format Rules

### File References
ALWAYS return absolute paths as clickable links:
```
✅ Created: file:///home/user/project/src/module.py
❌ Created: src/module.py
```

### Code Blocks
Use syntax highlighting:
```python
# ✅ Good
def example():
    pass
```

### Task Lists
Use checkboxes for actionable items:
- [ ] Step 1
- [x] Step 2 (completed)

### Spanish Flavor
Occasional Spanish is fine, but:
- Keep it elementary (claro, bueno, mira)
- Natural placement only
- Don't force it every response

## Quality Checks (Run Before Returning)

1. **Link Check:** All file paths are absolute and clickable
2. **Completeness:** Did I answer the user's question?
3. **Brevity:** Is this response concise? (Default to 2-4 sentences)
4. **Tool Suggestion:** If user is stuck, did I suggest a concrete tool?
5. **Strategic Frame:** For decisions, did I apply JTBD or First Principles?
```

### Implementation: Computational Sensors (`src/sensors/`)

```python
# src/sensors/linter.py

class XochitlLinter:
    """
    Custom linter with LLM-optimized error messages
    
    Key insight from Fowler: sensor messages should include
    instructions for self-correction (prompt injection)
    """
    
    def __init__(self):
        self.rules = self._load_rules()
    
    def lint(self, file_path: Path) -> list[LintError]:
        """Run all linting rules"""
        errors = []
        content = file_path.read_text()
        
        # Computational rules
        errors.extend(self._check_architecture_violations(file_path, content))
        errors.extend(self._check_file_organization(file_path))
        errors.extend(self._check_type_hints(file_path, content))
        errors.extend(self._check_function_length(file_path, content))
        
        return errors
    
    def _check_architecture_violations(self, path: Path, content: str) -> list[LintError]:
        """
        Enforce architectural constraints from AGENTS.md
        """
        errors = []
        
        # Rule: No raw SQL outside database.py
        if path.name != 'database.py' and 'CREATE TABLE' in content:
            errors.append(LintError(
                file=str(path),
                line=content.find('CREATE TABLE'),
                rule='ARCH001',
                message=(
                    "Raw SQL detected outside database.py. "
                    "FIX: Move this query to src/database.py and call it via "
                    "the DatabaseManager class. Example:\n"
                    "  # In database.py\n"
                    "  def create_table_foo(self):\n"
                    "      self.execute('CREATE TABLE...')\n"
                    "  # In your file\n"
                    "  db.create_table_foo()"
                )
            ))
        
        # Rule: No direct API calls outside llm_router.py
        if path.name != 'llm_router.py':
            if 'openai.ChatCompletion' in content or 'anthropic.messages.create' in content:
                errors.append(LintError(
                    file=str(path),
                    line=0,
                    rule='ARCH002',
                    message=(
                        "Direct LLM API call detected. "
                        "FIX: Use the LLMRouter instead:\n"
                        "  from src.llm_router import get_router\n"
                        "  router = get_router()\n"
                        "  response = router.route(prompt, context)"
                    )
                ))
        
        return errors
    
    def _check_file_organization(self, path: Path) -> list[LintError]:
        """
        Enforce file organization rules
        """
        errors = []
        
        # Rule: Planning artifacts must be in planning-artifacts/
        if 'PRD' in path.name or 'architecture' in path.name:
            if 'planning-artifacts' not in path.parts:
                errors.append(LintError(
                    file=str(path),
                    line=0,
                    rule='ORG001',
                    message=(
                        "Planning document in wrong location. "
                        f"MOVE: {path} → planning-artifacts/{path.name}"
                    )
                ))
        
        return errors

@dataclass
class LintError:
    file: str
    line: int
    rule: str
    message: str  # Includes self-correction instructions
```

### Implementation: Inferential Sensors (`src/sensors/llm_judge.py`)

```python
# src/sensors/llm_judge.py

class LLMJudge:
    """
    LLM-as-judge pattern for validating outputs
    
    Use local model to validate before sending to user
    """
    
    def __init__(self, local_llm):
        self.llm = local_llm
    
    def validate_response(self, response: str, context: dict) -> tuple[bool, Optional[str]]:
        """
        Check if response meets quality standards
        
        Returns: (is_valid, feedback_for_agent)
        """
        prompt = f"""
You are validating an AI assistant's response for quality.

Context: {context.get('user_query', '')}

Response to validate:
{response}

Check for:
1. Completeness: Did it answer the question?
2. Brevity: Is it concise (2-4 sentences for simple queries)?
3. Actionability: For "stuck" queries, did it suggest a concrete tool?
4. File paths: Are all paths absolute and clickable (file://...)?
5. Strategic framing: For decisions, was JTBD or First Principles applied?

Return JSON:
{{
  "is_valid": true/false,
  "issues": ["issue1", "issue2"],
  "suggestion": "How to fix..."
}}
"""
        
        result = self.llm.generate(prompt)
        judgment = json.loads(result)
        
        if judgment['is_valid']:
            return True, None
        else:
            feedback = f"Quality issues detected:\n"
            for issue in judgment['issues']:
                feedback += f"  - {issue}\n"
            feedback += f"\nSuggestion: {judgment['suggestion']}"
            return False, feedback
    
    def detect_ralph_loop(self, recent_errors: list[str]) -> bool:
        """
        Detect if agent is stuck in a loop (Ralph Wiggum pattern)
        
        If same error appears 3+ times, agent is stuck
        """
        if len(recent_errors) < 3:
            return False
        
        # Check for repeated errors
        last_three = recent_errors[-3:]
        if len(set(last_three)) == 1:
            return True  # Same error 3 times in a row
        
        return False
```

### Sensor Integration Point

```python
# src/agent.py modifications

class XochitlAgent:
    def __init__(self):
        self.linter = XochitlLinter()
        self.judge = LLMJudge(local_llm)
        self.error_history = []
    
    def execute_task(self, task, workspace: TaskWorkspace):
        """
        Execute task with full sensor pipeline
        """
        # Generate response
        response = self.llm.generate(task.description)
        
        # SENSOR CHECKPOINT 1: Lint any code generated
        if self._contains_code(response):
            lint_errors = self.linter.lint(self._extract_code_files(response))
            
            if lint_errors:
                # Self-correct via sensor feedback
                correction_prompt = self._build_correction_prompt(
                    response, 
                    lint_errors
                )
                response = self.llm.generate(correction_prompt)
        
        # SENSOR CHECKPOINT 2: LLM-as-judge validation
        is_valid, feedback = self.judge.validate_response(
            response, 
            {'user_query': task.description}
        )
        
        if not is_valid:
            # Self-correct
            response = self.llm.generate(
                f"Previous response had issues:\n{feedback}\n\n"
                f"Please revise your response to address these issues."
            )
        
        # SENSOR CHECKPOINT 3: Ralph loop detection
        if self.judge.detect_ralph_loop(self.error_history):
            # Agent is stuck, escalate to human
            self._mark_task_blocked(task, "Stuck in error loop")
            return
        
        # Execute response
        self._execute_response(response, workspace)
```

---

## PART 3: CONTEXT ENGINEERING (REPLACE COMPRESSION)

### Current Problem
Your "context compression" (summarize 20 messages → 5 bullets) **loses signal**. 

The Symphony approach: Don't compress context, **curate it**.

### New Architecture: Dynamic Context Assembly

```python
# src/context_engine.py

class ContextEngine:
    """
    Replaces the context compressor with structured context curation
    
    Key insight: The model doesn't need "less" context, it needs
    "the right" context at "the right time"
    """
    
    def __init__(self, memory_manager, vector_db, bmad_detector):
        self.memory = memory_manager
        self.vector_db = vector_db
        self.bmad = bmad_detector
    
    def build_context(self, query: str, workspace: Optional[TaskWorkspace] = None) -> dict:
        """
        Assemble context based on query intent and workspace state
        
        This is NOT compression - it's intelligent selection
        """
        context = {
            'guides': self._load_guides(workspace),
            'memory': self._load_relevant_memory(query),
            'workspace_state': self._load_workspace_state(workspace),
            'recent_decisions': self._load_recent_decisions(query),
            'bmad_context': self._load_bmad_context(workspace)
        }
        
        return context
    
    def _load_guides(self, workspace: Optional[TaskWorkspace]) -> dict:
        """
        Load AGENTS.md and project-specific constraints
        """
        guides = {
            'global': self._read_agents_md(),
            'project': None,
            'bmad': None
        }
        
        if workspace:
            # Check for project-specific AGENTS.md
            project_guides = workspace.workspace_dir / "AGENTS.md"
            if project_guides.exists():
                guides['project'] = project_guides.read_text()
            
            # Check for BMAD CLAUDE.md
            bmad_project = self.bmad.detect_bmad_project(workspace.workspace_dir)
            if bmad_project:
                claude_md = bmad_project['root'] / "CLAUDE.md"
                if claude_md.exists():
                    guides['bmad'] = claude_md.read_text()
        
        return guides
    
    def _load_relevant_memory(self, query: str) -> dict:
        """
        Extract only relevant sections from MEMORY.md
        
        Instead of sending the whole file, parse it and inject
        only the sections that match the query intent
        """
        full_memory = self.memory.read()
        
        # Parse query for project references
        mentioned_projects = self._extract_project_names(query)
        
        # Build filtered memory
        filtered = {
            'user_prefs': full_memory.get('User Preferences', {}),
            'active_goals': full_memory.get('Active Goals', []),
            'project_context': {}
        }
        
        # Only include project context for mentioned projects
        for project in mentioned_projects:
            if project in full_memory.get('BMAD Project Context', {}):
                filtered['project_context'][project] = full_memory['BMAD Project Context'][project]
        
        return filtered
    
    def _load_workspace_state(self, workspace: Optional[TaskWorkspace]) -> Optional[dict]:
        """
        Load progress.json from workspace - critical for session bridging
        """
        if not workspace:
            return None
        
        progress_file = workspace.workspace_dir / "task-artifacts/progress.json"
        if not progress_file.exists():
            return None
        
        return json.loads(progress_file.read_text())
    
    def _load_recent_decisions(self, query: str) -> list[dict]:
        """
        Query vector DB for relevant past decisions
        
        This replaces "conversation history" with "relevant decisions"
        """
        # Semantic search for past decisions
        results = self.vector_db.query(
            query_text=query,
            n_results=3,
            where={'type': 'decision'}
        )
        
        return results
    
    def _load_bmad_context(self, workspace: Optional[TaskWorkspace]) -> Optional[dict]:
        """
        Load BMAD-specific context if in a BMAD project
        """
        if not workspace:
            return None
        
        bmad_project = self.bmad.detect_bmad_project(workspace.workspace_dir)
        if not bmad_project:
            return None
        
        return {
            'root': str(bmad_project['root']),
            'version': bmad_project['version'],
            'modules': bmad_project['modules'],
            'active_workflows': bmad_project['workflows']
        }
```

### Cloud Routing with Curated Context

```python
# src/llm_router.py modifications

class LLMRouter:
    def route_cloud(self, query: str, workspace: Optional[TaskWorkspace] = None) -> Response:
        """
        Route to cloud with curated context - NOT compressed history
        """
        # Build context (intelligent selection, not compression)
        context = self.context_engine.build_context(query, workspace)
        
        # Build system prompt from curated context
        system_prompt = self._build_system_prompt(context)
        
        # Build user message with workspace state
        user_message = self._build_user_message(query, context)
        
        # Call Claude with structured context
        message = self.cloud_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        return Response(
            content=message.content[0].text,
            route_type=RouteType.CLOUD,
            tokens_used=message.usage.input_tokens + message.usage.output_tokens,
            cost=self._calculate_cost(message.usage)
        )
    
    def _build_system_prompt(self, context: dict) -> str:
        """
        Construct system prompt from curated context
        """
        sections = []
        
        # Always include SOUL.md
        sections.append(Path("SOUL.md").read_text())
        
        # Include global guides (AGENTS.md)
        if context['guides']['global']:
            sections.append(f"# AGENTS.md\n\n{context['guides']['global']}")
        
        # Include BMAD guides if applicable
        if context['guides']['bmad']:
            sections.append(f"# BMAD Context\n\n{context['guides']['bmad']}")
        
        # Include filtered memory
        if context['memory']:
            sections.append(self._format_memory(context['memory']))
        
        # Include recent decisions
        if context['recent_decisions']:
            sections.append(self._format_decisions(context['recent_decisions']))
        
        return "\n\n---\n\n".join(sections)
    
    def _build_user_message(self, query: str, context: dict) -> str:
        """
        Build user message with workspace state
        """
        parts = []
        
        # Include workspace state if available
        if context['workspace_state']:
            parts.append(f"# Current Task State\n\n{json.dumps(context['workspace_state'], indent=2)}")
        
        # Include BMAD context if applicable
        if context['bmad_context']:
            parts.append(f"# BMAD Project\n\nRoot: {context['bmad_context']['root']}")
            parts.append(f"Modules: {', '.join(context['bmad_context']['modules'])}")
        
        # Include the actual query
        parts.append(f"# User Request\n\n{query}")
        
        return "\n\n".join(parts)
```

---

## PART 4: PROGRESS FILES (SESSION BRIDGING)

### Current Problem
When Xochitl restarts, she has no memory of the last session beyond MEMORY.md.

### Symphony Solution
Structured progress files let a new agent pick up exactly where the last one left off.

### Implementation: Progress Tracker

```python
# src/progress_tracker.py

from dataclasses import dataclass, asdict
from typing import Optional, Literal
import json
from datetime import datetime
from pathlib import Path

@dataclass
class TaskProgress:
    """
    Structured progress state - Anthropic's insight for session bridging
    
    This file is the "handoff document" between agent sessions.
    It must be:
    - Structured (JSON, not Markdown - agents won't accidentally edit it)
    - Complete (new agent can resume without asking questions)
    - Timestamped (know what's fresh vs stale)
    """
    task_id: str
    description: str
    state: Literal['initialized', 'in_progress', 'blocked', 'review', 'done']
    completed_steps: list[str]
    next_steps: list[str]
    blocked_on: Optional[str]
    retry_count: int
    artifacts_created: list[str]
    last_test_status: Optional[Literal['PASS', 'FAIL', 'SKIP']]
    last_error: Optional[str]
    notes: str
    started_at: str
    last_updated: str
    
class ProgressTracker:
    """
    Manages progress.json files in task workspaces
    """
    
    def __init__(self, workspace: TaskWorkspace):
        self.workspace = workspace
        self.progress_file = workspace.workspace_dir / "task-artifacts/progress.json"
    
    def initialize(self, task) -> TaskProgress:
        """
        Create initial progress file when task starts
        """
        progress = TaskProgress(
            task_id=task.id,
            description=task.description,
            state='initialized',
            completed_steps=[],
            next_steps=self._decompose_task(task),
            blocked_on=None,
            retry_count=0,
            artifacts_created=[],
            last_test_status=None,
            last_error=None,
            notes='',
            started_at=datetime.now().isoformat(),
            last_updated=datetime.now().isoformat()
        )
        
        self.save(progress)
        return progress
    
    def load(self) -> TaskProgress:
        """
        Load current progress state
        """
        data = json.loads(self.progress_file.read_text())
        return TaskProgress(**data)
    
    def save(self, progress: TaskProgress):
        """
        Save progress state
        """
        progress.last_updated = datetime.now().isoformat()
        
        self.progress_file.write_text(
            json.dumps(asdict(progress), indent=2)
        )
    
    def complete_step(self, step: str):
        """
        Mark a step as complete and advance to next
        """
        progress = self.load()
        
        if step in progress.next_steps:
            progress.next_steps.remove(step)
            progress.completed_steps.append(step)
            progress.state = 'in_progress'
            
            if not progress.next_steps:
                # All steps done, move to review
                progress.state = 'review'
        
        self.save(progress)
    
    def add_artifact(self, artifact_path: str):
        """
        Record an artifact was created
        """
        progress = self.load()
        progress.artifacts_created.append(artifact_path)
        self.save(progress)
    
    def record_test_result(self, status: Literal['PASS', 'FAIL', 'SKIP']):
        """
        Record test execution result
        """
        progress = self.load()
        progress.last_test_status = status
        
        if status == 'FAIL':
            progress.retry_count += 1
        
        self.save(progress)
    
    def block(self, reason: str):
        """
        Mark task as blocked
        """
        progress = self.load()
        progress.state = 'blocked'
        progress.blocked_on = reason
        self.save(progress)
    
    def get_handoff_summary(self) -> str:
        """
        Generate a handoff summary for a new agent session
        
        This is what gets injected into the new agent's context
        """
        progress = self.load()
        
        summary = f"""# Task Handoff

## Task: {progress.description}

## Current State: {progress.state}

## Completed Steps ({len(progress.completed_steps)})
{chr(10).join(f'- [x] {step}' for step in progress.completed_steps)}

## Remaining Steps ({len(progress.next_steps)})
{chr(10).join(f'- [ ] {step}' for step in progress.next_steps)}

## Artifacts Created
{chr(10).join(f'- {artifact}' for artifact in progress.artifacts_created)}

## Last Test Status: {progress.last_test_status or 'No tests run yet'}

## Notes
{progress.notes}

## Instructions for Next Agent
Continue from the first remaining step. Check the artifacts created so far.
If blocked, review the blocking reason and attempt to resolve it.
"""
        
        return summary
```

---

## PART 5: THE MISTAKE REGISTRY (HARNESS IMPROVEMENT LOOP)

### Current Problem
When Xochitl makes a mistake, you manually update SOUL.md or add a filter. No systematic learning.

### Symphony Pattern
Every mistake is logged and analyzed. The harness evolves to prevent that mistake class forever.

### Implementation: `src/mistake_registry.py`

```python
# src/mistake_registry.py

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
from typing import Optional, Literal

@dataclass
class Mistake:
    """
    Record of an agent failure
    """
    id: str
    timestamp: str
    task_id: str
    mistake_type: Literal['architectural', 'organizational', 'quality', 'persona']
    description: str
    what_sensor_caught_it: str
    what_guide_was_missing: Optional[str]
    proposed_fix: str
    fix_applied: bool
    fix_type: Literal['guide', 'sensor', 'both']
    
class MistakeRegistry:
    """
    Systematic mistake tracking and harness improvement
    
    Pattern from Symphony: when agents fail, improve the harness, not the model
    """
    
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.registry_path.mkdir(parents=True, exist_ok=True)
        self.mistakes_file = self.registry_path / "mistakes.jsonl"
    
    def record(self, mistake: Mistake):
        """
        Log a mistake
        """
        with open(self.mistakes_file, 'a') as f:
            f.write(json.dumps(asdict(mistake)) + '\n')
    
    def get_recent_mistakes(self, days: int = 7) -> list[Mistake]:
        """
        Get mistakes from last N days
        """
        if not self.mistakes_file.exists():
            return []
        
        cutoff = datetime.now().timestamp() - (days * 86400)
        recent = []
        
        with open(self.mistakes_file) as f:
            for line in f:
                mistake = Mistake(**json.loads(line))
                mistake_time = datetime.fromisoformat(mistake.timestamp).timestamp()
                
                if mistake_time > cutoff:
                    recent.append(mistake)
        
        return recent
    
    def analyze_patterns(self) -> dict:
        """
        Identify patterns in mistakes - which are recurring?
        """
        mistakes = self.get_recent_mistakes(days=30)
        
        if not mistakes:
            return {}
        
        patterns = {
            'by_type': {},
            'by_missing_guide': {},
            'unfixed_count': 0,
            'recommendations': []
        }
        
        for mistake in mistakes:
            # Count by type
            patterns['by_type'][mistake.mistake_type] = \
                patterns['by_type'].get(mistake.mistake_type, 0) + 1
            
            # Count by missing guide
            if mistake.what_guide_was_missing:
                patterns['by_missing_guide'][mistake.what_guide_was_missing] = \
                    patterns['by_missing_guide'].get(mistake.what_guide_was_missing, 0) + 1
            
            # Count unfixed
            if not mistake.fix_applied:
                patterns['unfixed_count'] += 1
        
        # Generate recommendations
        for guide, count in sorted(
            patterns['by_missing_guide'].items(), 
            key=lambda x: x[1], 
            reverse=True
        ):
            if count >= 3:  # If same guide missing 3+ times
                patterns['recommendations'].append({
                    'priority': 'high',
                    'action': f'Add guide rule: {guide}',
                    'reason': f'Missing {count} times in last 30 days'
                })
        
        return patterns
    
    def propose_harness_improvements(self) -> list[dict]:
        """
        Generate concrete harness improvements based on mistakes
        
        This is the self-optimizing loop
        """
        patterns = self.analyze_patterns()
        improvements = []
        
        # Propose new guide rules
        for recommendation in patterns.get('recommendations', []):
            improvements.append({
                'type': 'guide',
                'file': 'AGENTS.md',
                'section': self._infer_section(recommendation['action']),
                'content': recommendation['action'],
                'priority': recommendation['priority']
            })
        
        # Propose new sensor rules
        architectural_errors = patterns['by_type'].get('architectural', 0)
        if architectural_errors >= 5:
            improvements.append({
                'type': 'sensor',
                'file': 'src/sensors/linter.py',
                'section': 'architectural_checks',
                'content': 'Add linter rule for recurring architectural violation',
                'priority': 'high'
            })
        
        return improvements
    
    def _infer_section(self, action: str) -> str:
        """
        Infer which section of AGENTS.md to update
        """
        if 'database' in action.lower() or 'sql' in action.lower():
            return 'Architecture Rules'
        elif 'file' in action.lower() or 'folder' in action.lower():
            return 'File Organization'
        elif 'spanish' in action.lower() or 'tone' in action.lower():
            return 'Response Format Rules'
        else:
            return 'Project Constraints'

class HarnessEvolution:
    """
    Automated harness improvement based on mistake registry
    """
    
    def __init__(self, registry: MistakeRegistry, local_llm):
        self.registry = registry
        self.llm = local_llm
    
    def generate_improvement_pr(self) -> Optional[dict]:
        """
        Generate a PR with proposed harness improvements
        
        Returns: PR data or None if no improvements needed
        """
        improvements = self.registry.propose_harness_improvements()
        
        if not improvements:
            return None
        
        # Generate PR content
        pr_data = {
            'title': f'Harness Improvements - {len(improvements)} fixes',
            'description': self._generate_pr_description(improvements),
            'changes': []
        }
        
        for improvement in improvements:
            if improvement['type'] == 'guide':
                # Generate AGENTS.md update
                pr_data['changes'].append({
                    'file': improvement['file'],
                    'diff': self._generate_guide_diff(improvement)
                })
            elif improvement['type'] == 'sensor':
                # Generate linter rule
                pr_data['changes'].append({
                    'file': improvement['file'],
                    'diff': self._generate_sensor_diff(improvement)
                })
        
        return pr_data
    
    def _generate_guide_diff(self, improvement: dict) -> str:
        """
        Use LLM to generate the actual guide rule text
        """
        prompt = f"""
Generate a new rule for AGENTS.md based on this improvement:

Section: {improvement['section']}
Content: {improvement['content']}

Write a concrete, actionable rule in the same style as existing AGENTS.md rules.
Include a brief explanation and an example.

Return ONLY the rule text, no preamble.
"""
        
        return self.llm.generate(prompt)
```

### CLI Command for Harness Evolution

```python
# src/cli.py

@cli.command()
def harness_report():
    """
    Show harness health and improvement recommendations
    """
    registry = MistakeRegistry(Path.home() / ".xochitl/mistakes")
    patterns = registry.analyze_patterns()
    
    console.print("\n[bold]Harness Health Report[/bold]\n")
    
    # Mistakes by type
    table = Table(title="Mistakes by Type (Last 30 Days)")
    table.add_column("Type")
    table.add_column("Count")
    
    for mistake_type, count in patterns['by_type'].items():
        table.add_row(mistake_type, str(count))
    
    console.print(table)
    
    # Recommendations
    if patterns['recommendations']:
        console.print("\n[bold yellow]Recommended Improvements:[/bold yellow]\n")
        for rec in patterns['recommendations']:
            console.print(f"  • {rec['action']}")
            console.print(f"    Reason: {rec['reason']}\n")
    else:
        console.print("\n[green]✓ No critical issues detected[/green]\n")

@cli.command()
def harness_improve():
    """
    Generate harness improvement PR based on mistake patterns
    """
    registry = MistakeRegistry(Path.home() / ".xochitl/mistakes")
    evolution = HarnessEvolution(registry, get_local_llm())
    
    pr_data = evolution.generate_improvement_pr()
    
    if not pr_data:
        console.print("[green]✓ Harness is healthy, no improvements needed[/green]")
        return
    
    console.print(f"\n[bold]{pr_data['title']}[/bold]\n")
    console.print(pr_data['description'])
    console.print("\n[bold]Proposed Changes:[/bold]\n")
    
    for change in pr_data['changes']:
        console.print(f"  • {change['file']}")
        console.print(f"    {change['diff'][:200]}...\n")
    
    if Confirm.ask("Apply these improvements?"):
        # Apply changes
        for change in pr_data['changes']:
            # Write to file
            file_path = Path(change['file'])
            # ... apply diff logic ...
            pass
        
        console.print("[green]✓ Harness improvements applied[/green]")
```

---

## PART 6: SUMMARY - IMPLEMENTATION PRIORITY

### Week 1: Foundation (Orchestrator Layer)
1. ✅ Implement `TaskOrchestrator` class
2. ✅ Create git worktree workspace management
3. ✅ Implement `progress.json` tracker
4. ✅ Add CLI commands: `orchestrate`, `workspace`, `workspaces`
5. ✅ Test autonomous task loop with 1 simple task

### Week 2: Guides & Sensors
1. ✅ Write comprehensive `AGENTS.md`
2. ✅ Implement `XochitlLinter` with LLM-optimized messages
3. ✅ Implement `LLMJudge` for quality validation
4. ✅ Add sensor checkpoints to agent execution loop
5. ✅ Test self-correction with intentionally bad outputs

### Week 3: Context Engineering
1. ✅ Build `ContextEngine` to replace context compression
2. ✅ Implement dynamic context assembly
3. ✅ Update cloud routing to use curated context
4. ✅ Test token usage (should see 60-80% reduction)
5. ✅ Measure quality improvement (fewer retries)

### Week 4: Mistake Registry & Evolution
1. ✅ Implement `MistakeRegistry`
2. ✅ Add mistake logging to all sensor checkpoints
3. ✅ Implement `HarnessEvolution`
4. ✅ Add CLI commands: `harness-report`, `harness-improve`
5. ✅ Run for 1 week, collect data, generate first improvement PR

---

## CRITICAL SUCCESS METRICS

Track these to validate the improvements:

### Pre-Harness Engineering (Current State)
- **Task completion rate:** ~60% (rough estimate)
- **Average retries per task:** Unknown
- **Token cost per task:** High (full context every time)
- **Human intervention needed:** Frequent

### Post-Harness Engineering (Target State)
- **Task completion rate:** >85%
- **Average retries per task:** <2
- **Token cost per task:** 60-80% reduction (via context curation)
- **Human intervention needed:** <10% of tasks
- **Harness improvement PRs:** 1-2 per week initially, then <1 per month

---

## THE MINDSET SHIFT

**Before:** "How do I make Xochitl smarter?"  
**After:** "How do I make the environment around Xochitl more structured?"

**Before:** "This task failed, let me tweak the prompt"  
**After:** "This task failed, what guide or sensor was missing?"

**Before:** "Send full conversation history to the cloud"  
**After:** "Send only the relevant, structured context"

**Before:** "Manually manage Xochitl sessions"  
**After:** "Manage the work queue, let Xochitl execute autonomously"

This is the Symphony lesson: **The model is the CPU, the harness is the OS.**

You've been optimizing the CPU. Now optimize the OS.
