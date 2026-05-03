# Xochitl Harness Engineering Implementation Plan (Revised)
## Conversational AI + Background Orchestrator Architecture

**Based on:** OpenAI Symphony + Claude.ai UX patterns  
**Date:** April 30, 2026  
**Status:** Prescriptive Implementation Guide (Conversational-First)

---

## EXECUTIVE SUMMARY: THE CORRECTED VISION

You're building **TWO modes** that work together, not replacing conversation with automation:

1. **Conversational Mode (Primary)** - Natural chat with Xochitl in terminal, just like talking to Claude
2. **Orchestrator Mode (Background)** - Optional autonomous task execution when you want it

**Key Principle:** The orchestrator is a **tool Xochitl can use**, not a replacement for Xochitl herself.

---

## ARCHITECTURE OVERVIEW: THE TWO-LAYER SYSTEM

```
┌─────────────────────────────────────────────────────────────┐
│  CONVERSATIONAL LAYER (You interact with THIS)             │
│                                                             │
│  Terminal: $ xochitl                                        │
│  > Hey Xochitl, what's on my plate today?                  │
│                                                             │
│  Xochitl: You've got 3 tasks in the queue. The JobAgent    │
│  auth flow is blocked on API docs. Want me to check if     │
│  those docs are ready, or should we tackle the email       │
│  parser instead?                                            │
│                                                             │
│  [Natural conversation, asks before acting, suggests tools] │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ (Xochitl can CHOOSE to use)
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR LAYER (Runs in background when asked)        │
│                                                             │
│  • Polls Notion for task updates                           │
│  • Manages task workspaces (git worktrees)                 │
│  • Runs autonomous agents on tasks you delegate            │
│  • Reports back to conversational layer                    │
│                                                             │
│  [Only active when you say "handle this for me"]           │
└─────────────────────────────────────────────────────────────┘
```

---

## PART 1: THE CONVERSATIONAL LAYER (PRIMARY INTERFACE)

### Design Philosophy

**Claude.ai-style UX:**
- Natural back-and-forth dialogue
- Asks permission before taking actions
- Suggests tools/skills but doesn't force them
- SOUL.md personality always active
- No "Are you sure?" for every small thing, but explicit consent for big actions

### Core Chat Loop

```python
# src/chat.py

class XochitlChat:
    """
    The conversational interface - this is what you interact with daily
    
    Design: Like chatting with Claude, not like issuing commands to a bot
    """
    
    def __init__(self):
        self.llm_router = LLMRouter()
        self.context_engine = ContextEngine()
        self.memory = MemoryManager()
        self.soul = Path("SOUL.md").read_text()
        
        # Access to tools and orchestrator
        self.orchestrator = None  # Only initialized if user starts it
        self.notion_sync = NotionSync()
        self.bmad_detector = BMADDetector()
        self.file_tools = FileTools()
        
        # Conversation state
        self.session_history = []
        self.current_context = {}
    
    def start(self):
        """
        Start conversational session
        """
        console.print("\n[bold]🌸 Xochitl[/bold]\n")
        
        # Check if orchestrator is running
        if self._orchestrator_is_running():
            console.print("[dim]Orchestrator running in background[/dim]\n")
        
        while True:
            try:
                # Get user input
                user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    console.print("\n[dim]Hasta luego 👋[/dim]\n")
                    break
                
                # Process message
                response = self.process_message(user_input)
                
                # Display response
                console.print(f"\n[bold]Xochitl[/bold]: {response}\n")
                
            except KeyboardInterrupt:
                console.print("\n[dim]Hasta luego 👋[/dim]\n")
                break
    
    def process_message(self, user_input: str) -> str:
        """
        Process user message with natural conversation flow
        
        Key difference from old approach:
        - Doesn't auto-execute tools
        - Suggests tools and asks permission
        - Maintains conversational tone from SOUL.md
        """
        # Add to session history
        self.session_history.append({
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now()
        })
        
        # Build context for this turn
        context = self.context_engine.build_chat_context(
            user_input=user_input,
            session_history=self.session_history,
            current_directory=Path.cwd(),
            orchestrator_status=self._get_orchestrator_status()
        )
        
        # Detect intent (but don't auto-execute)
        intent = self._classify_intent(user_input)
        
        # Route to appropriate handler
        if intent['type'] == 'simple_question':
            # Direct answer, no tools needed
            response = self._answer_question(user_input, context)
        
        elif intent['type'] == 'task_query':
            # Questions about tasks - might use Notion/DB
            response = self._handle_task_query(user_input, context)
        
        elif intent['type'] == 'action_request':
            # User wants something done - suggest approach, ask permission
            response = self._handle_action_request(user_input, context, intent)
        
        elif intent['type'] == 'file_operation':
            # File reading/writing
            response = self._handle_file_operation(user_input, context, intent)
        
        elif intent['type'] == 'bmad_workflow':
            # BMAD-related work
            response = self._handle_bmad_workflow(user_input, context, intent)
        
        else:
            # General conversation
            response = self._general_conversation(user_input, context)
        
        # Add response to history
        self.session_history.append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now()
        })
        
        return response
    
    def _handle_action_request(self, user_input: str, context: dict, intent: dict) -> str:
        """
        User wants an action - suggest approach, get permission
        
        Examples:
        - "Sync my Notion tasks"
        - "Start working on the auth flow task"
        - "Create a new project plan"
        """
        action = intent['action']
        
        if action == 'sync_notion':
            # Don't just sync - ask first
            return self._suggest_notion_sync(context)
        
        elif action == 'start_task':
            # Suggest using orchestrator or manual approach
            return self._suggest_task_approach(intent['task_id'], context)
        
        elif action == 'create_plan':
            # Suggest BMAD or simple planning
            return self._suggest_planning_approach(user_input, context)
        
        else:
            # Generic action - ask how they want to proceed
            return self._suggest_generic_action(action, user_input, context)
    
    def _suggest_notion_sync(self, context: dict) -> str:
        """
        Suggest syncing Notion - don't just do it
        
        Claude.ai pattern: show what would happen, ask if they want it
        """
        # Check last sync time
        last_sync = self.notion_sync.get_last_sync_time()
        pending_changes = self.notion_sync.get_pending_changes()
        
        if not pending_changes:
            return "Your Notion is already synced. Last update was {last_sync}."
        
        # Show what would sync
        summary = f"I can sync {len(pending_changes)} changes:\n"
        summary += "  • " + "\n  • ".join(pending_changes[:3])
        
        if len(pending_changes) > 3:
            summary += f"\n  • ... and {len(pending_changes) - 3} more"
        
        summary += "\n\nWant me to run the sync?"
        
        return summary
    
    def _suggest_task_approach(self, task_id: str, context: dict) -> str:
        """
        User wants to work on a task - suggest options
        
        Two approaches:
        1. Collaborative (you work together in chat)
        2. Autonomous (delegate to orchestrator)
        """
        task = self._get_task(task_id)
        
        response = f"Got it, the '{task.description}' task.\n\n"
        response += "Two ways we can tackle this:\n\n"
        response += "1. **Work together** - I help you step by step in chat\n"
        response += "2. **Delegate it** - I spin up an autonomous agent in the background "
        response += "(you can check progress later)\n\n"
        response += "Which sounds better?"
        
        return response
    
    def _suggest_planning_approach(self, user_input: str, context: dict) -> str:
        """
        User wants to plan something - check for BMAD, offer options
        """
        # Check if we're in a BMAD project
        bmad_project = self.bmad_detector.detect_bmad_project(Path.cwd())
        
        if bmad_project:
            # BMAD project - suggest using BMAD workflows
            response = "You're in a BMAD project. "
            response += f"I can run the {', '.join(bmad_project['modules'])} workflows.\n\n"
            response += "Want me to walk you through the planning process, or should I "
            response += "generate a draft for you to review?"
        else:
            # Not BMAD - offer simpler planning
            response = "I can help you plan this out. "
            response += "Want a structured breakdown (BMAD-style) or just a quick outline?"
        
        return response
    
    def _general_conversation(self, user_input: str, context: dict) -> str:
        """
        General conversation - maintain SOUL.md personality
        """
        # Build system prompt with SOUL.md
        system_prompt = self._build_conversational_prompt(context)
        
        # Route based on complexity
        if self._is_complex_query(user_input):
            response = self.llm_router.route_cloud(
                user_input, 
                system_prompt=system_prompt,
                context=context
            )
        else:
            response = self.llm_router.route_local(
                user_input,
                system_prompt=system_prompt,
                context=context
            )
        
        return response.content
    
    def _build_conversational_prompt(self, context: dict) -> str:
        """
        Build system prompt that maintains SOUL.md personality
        """
        sections = []
        
        # Always include SOUL.md
        sections.append(self.soul)
        
        # Include relevant memory
        memory_context = self.context_engine.get_relevant_memory(
            context.get('user_input', '')
        )
        if memory_context:
            sections.append(f"# Relevant Context\n\n{memory_context}")
        
        # Include orchestrator status if relevant
        if self.orchestrator and context.get('mention_tasks', False):
            status = self._get_orchestrator_status()
            sections.append(f"# Background Tasks\n\n{status}")
        
        # Add conversational guidelines
        sections.append("""
# Conversational Guidelines

- Be natural and conversational
- Ask before taking actions
- Suggest tools/approaches but don't force them
- Keep responses concise (2-4 sentences) unless detail is requested
- When offering options, present 2-3 clear choices
- Don't apologize excessively or over-explain
- Trust the user to ask follow-ups if they want more detail
""")
        
        return "\n\n---\n\n".join(sections)
```

### Example Conversation Flows

**Flow 1: Task Status Check**
```
You: What's on my plate today?

Xochitl: You've got 3 tasks in the queue:
  1. JobAgent auth flow (blocked - waiting on API docs)
  2. Email parser for resume extraction (ready to go)
  3. Xochitl Notion sync refactor (in progress)

Want details on any of these?

You: Yeah, what's blocking the auth flow?

Xochitl: The task notes say we need the OAuth endpoint docs from the API team. 
I can check your email or Slack for those docs, or we can skip to task 2 
while we wait. What works?
```

**Flow 2: Starting Work (Collaborative)**
```
You: Let's work on the email parser

Xochitl: Cool. Two approaches:
  1. Work together - I'll help you build it step by step
  2. Delegate it - I spin up a background agent and you check in later

Which one?

You: Let's work together

Xochitl: Bueno. First step: what's the input format? Are we parsing 
plain text emails or pulling from an API?
```

**Flow 3: Starting Work (Autonomous)**
```
You: Actually, delegate the email parser. I'll check on it later.

Xochitl: Got it. Spinning up a workspace for that task...

[Creates git worktree: .xochitl/workspaces/task-email-parser]
[Spawns autonomous agent]

Done. The agent is working on it now. I'll ping you when there's a PR ready 
for review. Want me to start the orchestrator daemon so it keeps running 
even when you close this chat?

You: Yeah, start it

Xochitl: Orchestrator running. You can check status anytime with 
`xochitl status` or just ask me "what are the background tasks doing?"
```

**Flow 4: BMAD Workflow (Guided)**
```
You: I need to plan a new feature for JobAgent

Xochitl: You're in the JobAgent BMAD project. I can run through the 
feature planning workflow with you. It's 5 steps:

  1. Define the job to be done
  2. Sketch user flows
  3. Break into implementation tasks
  4. Estimate complexity
  5. Generate PRD

Want to do this together (I'll ask questions) or should I draft 
something for you to review?

You: Draft it, I'll review

Xochitl: Cool. Give me the high-level: what's the feature?

You: Users should be able to save job searches and get email alerts

Xochitl: Got it. Let me draft the workflow artifacts...

[Uses local model for initial draft]
[Escalates to cloud for PRD generation]
[Saves to planning-artifacts/]

Done. Created:
  • file:///path/to/planning-artifacts/prd-saved-searches.md
  • file:///path/to/planning-artifacts/user-flow-saved-searches.md

Check those out and let me know what needs adjusting.
```

---

## PART 2: THE ORCHESTRATOR LAYER (BACKGROUND CAPABILITY)

### Design Philosophy

The orchestrator is **Xochitl's tool**, not a separate system. She can:
- Start it when you delegate tasks
- Query its status during conversation
- Stop it when you want manual control

### Orchestrator as a Skill

```python
# src/skills/orchestrator.py

class OrchestratorSkill:
    """
    Skill that Xochitl uses to manage autonomous task execution
    
    This is a TOOL for Xochitl, not a replacement for her
    """
    
    def __init__(self):
        self.daemon = None
        self.active_workspaces = {}
    
    def start_daemon(self) -> str:
        """
        Start background orchestrator process
        
        Called when user says: "handle this in the background"
        """
        if self.daemon and self.daemon.is_running():
            return "Orchestrator is already running."
        
        # Start daemon process
        self.daemon = subprocess.Popen(
            ['xochitl', 'orchestrator', '--daemon'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return "Orchestrator started. Background task execution is now active."
    
    def stop_daemon(self) -> str:
        """
        Stop background orchestrator
        
        Called when user says: "stop background tasks"
        """
        if not self.daemon or not self.daemon.is_running():
            return "Orchestrator isn't running."
        
        self.daemon.terminate()
        self.daemon.wait()
        
        return "Orchestrator stopped. All background tasks paused."
    
    def delegate_task(self, task_id: str, mode: str = 'autonomous') -> str:
        """
        Delegate a task to the orchestrator
        
        Called during conversation when user chooses "delegate it"
        """
        # Ensure daemon is running
        if not self.daemon or not self.daemon.is_running():
            self.start_daemon()
        
        # Create workspace for task
        workspace = self._create_workspace(task_id)
        
        # Spawn agent in workspace
        agent_pid = self._spawn_agent(task_id, workspace, mode)
        
        # Register workspace
        self.active_workspaces[task_id] = {
            'workspace_dir': workspace,
            'agent_pid': agent_pid,
            'started_at': datetime.now(),
            'mode': mode
        }
        
        return f"Task delegated. Workspace: {workspace}\nAgent running (PID: {agent_pid})"
    
    def get_status(self) -> dict:
        """
        Get status of all background tasks
        
        Called when user asks: "what are background tasks doing?"
        """
        if not self.active_workspaces:
            return {
                'active_count': 0,
                'tasks': []
            }
        
        tasks = []
        for task_id, workspace_info in self.active_workspaces.items():
            # Read progress file
            progress_file = workspace_info['workspace_dir'] / 'task-artifacts/progress.json'
            if progress_file.exists():
                progress = json.loads(progress_file.read_text())
                
                tasks.append({
                    'task_id': task_id,
                    'description': progress['description'],
                    'state': progress['state'],
                    'completed_steps': len(progress['completed_steps']),
                    'total_steps': len(progress['completed_steps']) + len(progress['next_steps']),
                    'runtime': self._calculate_runtime(workspace_info['started_at'])
                })
        
        return {
            'active_count': len(tasks),
            'tasks': tasks
        }
    
    def get_task_progress(self, task_id: str) -> Optional[dict]:
        """
        Get detailed progress for a specific task
        
        Called when user asks: "how's the email parser doing?"
        """
        if task_id not in self.active_workspaces:
            return None
        
        workspace_info = self.active_workspaces[task_id]
        progress_file = workspace_info['workspace_dir'] / 'task-artifacts/progress.json'
        
        if not progress_file.exists():
            return None
        
        return json.loads(progress_file.read_text())
```

### Conversational Access to Orchestrator

```python
# src/chat.py additions

class XochitlChat:
    
    def _handle_orchestrator_query(self, user_input: str) -> str:
        """
        User asks about background tasks
        
        Examples:
        - "What are the background tasks doing?"
        - "How's the email parser coming along?"
        - "Any tasks finished?"
        """
        if not self.orchestrator or not self.orchestrator.daemon:
            return "No background tasks running. Want to delegate something?"
        
        status = self.orchestrator.get_status()
        
        if status['active_count'] == 0:
            return "Orchestrator is running but no tasks are active."
        
        # Format status conversationally
        response = f"Running {status['active_count']} background tasks:\n\n"
        
        for task in status['tasks']:
            progress_pct = (task['completed_steps'] / task['total_steps']) * 100
            response += f"• {task['description'][:50]}...\n"
            response += f"  {task['state']} - {progress_pct:.0f}% done ({task['runtime']})\n\n"
        
        return response
    
    def _handle_task_delegation_choice(self, choice: str, task_id: str) -> str:
        """
        User chose how to work on a task (collaborative vs autonomous)
        """
        if 'together' in choice.lower() or 'collaborative' in choice.lower():
            # Stay in conversational mode
            return self._start_collaborative_work(task_id)
        
        elif 'delegate' in choice.lower() or 'autonomous' in choice.lower():
            # Hand off to orchestrator
            result = self.orchestrator.delegate_task(task_id)
            
            response = f"Got it. {result}\n\n"
            response += "I'll let you know when it's ready for review. "
            response += "You can check progress anytime by asking 'how's [task] doing?'"
            
            return response
        
        else:
            # Unclear choice, ask again
            return "Want to work together or delegate it? Just say which."
```

---

## PART 3: FILE SYSTEM ACCESS (SAFE & SCOPED)

### Design Philosophy

- Xochitl has read access to your project directories
- Write access requires explicit permission (just like Claude.ai)
- Dangerous operations (delete, overwrite) always ask confirmation
- MCP sandbox prevents access to system files

### File Tools with Permission Model

```python
# src/tools/file_tools.py

class FileTools:
    """
    File operations with Claude.ai-style permission model
    
    Read: automatic
    Write new: automatic
    Overwrite: ask permission
    Delete: ask permission + confirmation
    """
    
    def __init__(self, allowed_roots: list[Path]):
        self.allowed_roots = allowed_roots  # e.g., [~/Code, ~/Documents]
        self.pending_operations = {}
    
    def read_file(self, path: Path) -> str:
        """
        Read file - no permission needed
        """
        if not self._is_path_allowed(path):
            raise PermissionError(f"Cannot access {path} - outside allowed directories")
        
        return path.read_text()
    
    def write_file(self, path: Path, content: str) -> dict:
        """
        Write file - ask if exists, automatic if new
        
        Returns dict with:
        - 'status': 'written' | 'pending_permission'
        - 'message': what to show user
        - 'operation_id': if pending
        """
        if not self._is_path_allowed(path):
            raise PermissionError(f"Cannot write to {path} - outside allowed directories")
        
        if path.exists():
            # File exists - need permission to overwrite
            op_id = self._create_pending_operation('overwrite', path, content)
            
            return {
                'status': 'pending_permission',
                'message': f"File {path.name} already exists. Overwrite it?",
                'operation_id': op_id
            }
        else:
            # New file - write automatically
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            
            return {
                'status': 'written',
                'message': f"Created: file://{path.absolute()}",
                'operation_id': None
            }
    
    def delete_file(self, path: Path) -> dict:
        """
        Delete file - always ask permission
        """
        if not self._is_path_allowed(path):
            raise PermissionError(f"Cannot delete {path} - outside allowed directories")
        
        if not path.exists():
            return {
                'status': 'error',
                'message': f"File {path} doesn't exist"
            }
        
        # Always ask permission for deletes
        op_id = self._create_pending_operation('delete', path, None)
        
        return {
            'status': 'pending_permission',
            'message': f"Delete {path.name}? This cannot be undone.",
            'operation_id': op_id
        }
    
    def confirm_operation(self, operation_id: str) -> dict:
        """
        User confirmed a pending operation
        """
        if operation_id not in self.pending_operations:
            return {'status': 'error', 'message': 'Unknown operation'}
        
        op = self.pending_operations[operation_id]
        
        if op['type'] == 'overwrite':
            op['path'].write_text(op['content'])
            result = {
                'status': 'completed',
                'message': f"Overwrote: file://{op['path'].absolute()}"
            }
        
        elif op['type'] == 'delete':
            op['path'].unlink()
            result = {
                'status': 'completed',
                'message': f"Deleted: {op['path'].name}"
            }
        
        # Clean up
        del self.pending_operations[operation_id]
        
        return result
    
    def cancel_operation(self, operation_id: str) -> dict:
        """
        User cancelled a pending operation
        """
        if operation_id in self.pending_operations:
            del self.pending_operations[operation_id]
        
        return {
            'status': 'cancelled',
            'message': 'Operation cancelled'
        }
    
    def _is_path_allowed(self, path: Path) -> bool:
        """
        Check if path is within allowed roots
        """
        path = path.resolve()
        
        for allowed_root in self.allowed_roots:
            try:
                path.relative_to(allowed_root.resolve())
                return True
            except ValueError:
                continue
        
        return False
    
    def _create_pending_operation(self, op_type: str, path: Path, content: Optional[str]) -> str:
        """
        Create a pending operation that needs permission
        """
        op_id = str(uuid.uuid4())[:8]
        
        self.pending_operations[op_id] = {
            'type': op_type,
            'path': path,
            'content': content,
            'created_at': datetime.now()
        }
        
        return op_id
```

### Conversational File Operations

```python
# src/chat.py additions

class XochitlChat:
    
    def _handle_file_operation(self, user_input: str, context: dict, intent: dict) -> str:
        """
        Handle file operations conversationally
        """
        operation = intent['operation']
        
        if operation == 'read':
            # Read is automatic
            content = self.file_tools.read_file(intent['path'])
            
            # Don't dump entire file - summarize or ask what they want
            if len(content) > 1000:
                return self._summarize_file(intent['path'], content)
            else:
                return content
        
        elif operation == 'write':
            # Write (might need permission)
            result = self.file_tools.write_file(intent['path'], intent['content'])
            
            if result['status'] == 'pending_permission':
                # Store operation ID for when user confirms
                self.current_context['pending_file_operation'] = result['operation_id']
                return result['message']
            else:
                return result['message']
        
        elif operation == 'delete':
            # Delete (always needs permission)
            result = self.file_tools.delete_file(intent['path'])
            self.current_context['pending_file_operation'] = result['operation_id']
            return result['message']
    
    def _handle_permission_response(self, user_input: str) -> Optional[str]:
        """
        User responded to a permission request
        
        Check if there's a pending operation and handle yes/no
        """
        if 'pending_file_operation' not in self.current_context:
            return None
        
        op_id = self.current_context['pending_file_operation']
        
        if user_input.lower() in ['yes', 'y', 'ok', 'sure', 'yeah', 'yep']:
            result = self.file_tools.confirm_operation(op_id)
            del self.current_context['pending_file_operation']
            return result['message']
        
        elif user_input.lower() in ['no', 'n', 'nope', 'cancel', 'nevermind']:
            result = self.file_tools.cancel_operation(op_id)
            del self.current_context['pending_file_operation']
            return result['message']
        
        return None  # Not a yes/no response
```

---

## PART 4: SKILLS AS CONVERSATIONAL TOOLS

### Design Philosophy

Skills (like BMAD, Notion Sync) are tools Xochitl suggests and uses, not automatic processes.

### Skill Invocation Pattern

```python
# src/skills/base.py

class Skill:
    """
    Base class for all skills
    
    Skills are conversational tools, not background processes
    """
    
    def can_handle(self, user_input: str, context: dict) -> float:
        """
        Return confidence score (0.0-1.0) that this skill applies
        
        This is how Xochitl decides whether to suggest a skill
        """
        raise NotImplementedError
    
    def suggest(self, user_input: str, context: dict) -> str:
        """
        Generate a suggestion message
        
        This is what Xochitl says to suggest using this skill
        """
        raise NotImplementedError
    
    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """
        Execute the skill
        
        Only called after user confirms they want to use it
        """
        raise NotImplementedError

# src/skills/bmad_skill.py

class BMADSkill(Skill):
    """
    BMAD workflow skill
    """
    
    def can_handle(self, user_input: str, context: dict) -> float:
        """
        Check if BMAD is relevant
        """
        # Check if in BMAD project
        if not context.get('bmad_project'):
            return 0.0
        
        # Check for planning keywords
        planning_keywords = ['plan', 'design', 'architect', 'prd', 'feature', 'workflow']
        
        if any(keyword in user_input.lower() for keyword in planning_keywords):
            return 0.8
        
        return 0.0
    
    def suggest(self, user_input: str, context: dict) -> str:
        """
        Suggest using BMAD
        """
        bmad_project = context['bmad_project']
        modules = ', '.join(bmad_project['modules'])
        
        return (
            f"You're in a BMAD project with {modules} modules. "
            f"I can run through the planning workflow. Want to do that?"
        )
    
    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """
        Run BMAD workflow conversationally
        """
        mode = params.get('mode', 'guided')  # 'guided' or 'draft'
        
        if mode == 'guided':
            # Step-by-step Q&A
            return self._run_guided_workflow(context)
        else:
            # Generate draft from user input
            return self._generate_draft(user_input, context)

# src/skills/notion_skill.py

class NotionSkill(Skill):
    """
    Notion sync skill
    """
    
    def can_handle(self, user_input: str, context: dict) -> float:
        """
        Check if Notion sync is relevant
        """
        notion_keywords = ['notion', 'sync', 'tasks', 'queue', 'projects']
        
        if any(keyword in user_input.lower() for keyword in notion_keywords):
            return 0.7
        
        return 0.0
    
    def suggest(self, user_input: str, context: dict) -> str:
        """
        Suggest syncing Notion
        """
        pending = self._get_pending_changes()
        
        if not pending:
            return "Your Notion is already synced."
        
        return (
            f"I can sync {len(pending)} changes from Notion. "
            f"Last sync was {self._last_sync_time()}. Want me to pull the updates?"
        )
    
    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """
        Execute Notion sync
        """
        result = self._sync_notion()
        
        return (
            f"Synced {result['tasks_updated']} tasks and "
            f"{result['projects_updated']} projects from Notion."
        )
```

### Skill Suggestion in Chat

```python
# src/chat.py additions

class XochitlChat:
    
    def __init__(self):
        # ... existing init ...
        
        # Load skills
        self.skills = [
            BMADSkill(),
            NotionSkill(),
            OrchestratorSkill(),
            # ... more skills ...
        ]
    
    def _check_skills(self, user_input: str, context: dict) -> Optional[str]:
        """
        Check if any skills apply to this message
        
        Returns suggestion if a skill is relevant, None otherwise
        """
        # Score all skills
        skill_scores = [
            (skill, skill.can_handle(user_input, context))
            for skill in self.skills
        ]
        
        # Get highest scoring skill
        best_skill, score = max(skill_scores, key=lambda x: x[1])
        
        # If confidence is high enough, suggest it
        if score > 0.6:
            return best_skill.suggest(user_input, context)
        
        return None
    
    def process_message(self, user_input: str) -> str:
        """
        Process with skill suggestions
        """
        # ... existing code ...
        
        # Check if a skill applies
        skill_suggestion = self._check_skills(user_input, context)
        
        if skill_suggestion:
            # Add suggestion to response
            response = skill_suggestion
        else:
            # Continue with normal processing
            response = self._handle_intent(user_input, context, intent)
        
        return response
```

---

## PART 5: THE COMPLETE UX FLOW

### Example Session: Natural Conversation + Tool Usage

```
$ xochitl

🌸 Xochitl

You: Hey, what's up?

Xochitl: Hey! All good here. What are you working on?

You: Need to check my task queue

Xochitl: You've got 3 tasks:
  1. JobAgent auth flow (blocked)
  2. Email parser (ready)
  3. Notion sync refactor (in progress)

Want details on any?

You: What's blocking the auth one?

Xochitl: Notes say we're waiting on OAuth docs from the API team. 
I can check your email for those, or we skip to the email parser. 
Which sounds better?

You: Check email for the docs

Xochitl: [Checking email...]

Found them! "OAuth 2.0 Implementation Guide" from Sarah, sent yesterday. 
Want me to save it to the JobAgent docs folder?

You: Yeah

Xochitl: Done. Saved to:
  file:///Code/JobAgent/docs/oauth-implementation-guide.pdf

The auth flow is unblocked now. Want to start on it?

You: Nah, delegate it to a background agent

Xochitl: Got it. Two quick questions:
  1. Should the agent follow the OAuth guide exactly or adapt it?
  2. Any specific framework preference (express, fastify)?

You: Follow the guide, use express

Xochitl: Cool. Spinning up workspace...

Done. Agent is working on it. I'll let you know when there's a PR. 
Want me to start the orchestrator so it keeps running in the background?

You: Yeah

Xochitl: Orchestrator running. You can close this and check back later.

You: Actually, before I go, sync my Notion

Xochitl: I can sync 5 changes from Notion:
  • New project: "Newsletter automation"
  • Updated deadline: JobAgent (moved to end of month)
  • 3 new tasks in Email Parser

Pull these updates?

You: Yes

Xochitl: [Syncing...]

Done. Pulled 5 updates. Your local queue is current.

You: Thanks, bye

Xochitl: Hasta luego 👋
```

---

## PART 6: CONFIGURATION & SETUP

### Initial Setup: Defining Allowed Directories

```python
# ~/.xochitl/config.json

{
  "file_access": {
    "allowed_roots": [
      "~/Code",
      "~/Documents/Projects",
      "~/Work"
    ],
    "blocked_patterns": [
      "*.key",
      "*.pem",
      ".env",
      "credentials.json"
    ]
  },
  "orchestrator": {
    "enabled": true,
    "auto_start": false,
    "max_parallel_tasks": 3
  },
  "llm": {
    "local_model": "llama3.1:8b-instruct-q6_K",
    "cloud_model": "claude-sonnet-4-20250514",
    "token_budget_daily": 100000
  },
  "notion": {
    "api_key": "secret_...",
    "database_id": "...",
    "sync_interval_minutes": 30
  },
  "soul": {
    "personality_file": "~/.xochitl/SOUL.md",
    "spanish_frequency": "occasional",
    "verbosity": "concise"
  }
}
```

### CLI Commands (Conversational-First)

```bash
# Start conversational chat (primary interface)
xochitl

# Start chat with orchestrator running
xochitl --with-orchestrator

# Check status without entering chat
xochitl status

# Sync Notion (non-interactive)
xochitl sync

# List background tasks
xochitl tasks

# Jump into a task workspace
xochitl workspace task-123

# Harness health report
xochitl harness-report

# Update Xochitl
xochitl update
```

---

## IMPLEMENTATION PRIORITY (REVISED)

### Phase 1: Conversational Foundation (Week 1)
1. ✅ Build `XochitlChat` class with natural conversation loop
2. ✅ Implement intent classification (simple questions vs actions)
3. ✅ Add SOUL.md personality integration
4. ✅ Create `FileTools` with permission model
5. ✅ Test: Natural conversation about tasks without auto-execution

### Phase 2: Skills System (Week 2)
1. ✅ Build `Skill` base class
2. ✅ Implement `NotionSkill` (suggest sync, execute on permission)
3. ✅ Implement `BMADSkill` (detect projects, suggest workflows)
4. ✅ Add skill suggestion logic to chat loop
5. ✅ Test: Xochitl suggests skills appropriately, doesn't force them

### Phase 3: Orchestrator as Tool (Week 3)
1. ✅ Build `OrchestratorSkill`
2. ✅ Implement task delegation flow (ask collaborative vs autonomous)
3. ✅ Add workspace creation and progress tracking
4. ✅ Build conversational status queries
5. ✅ Test: Delegate task in chat, check status conversationally

### Phase 4: Harness Engineering (Week 4)
1. ✅ Add `AGENTS.md` guide layer
2. ✅ Implement computational sensors (linter)
3. ✅ Add mistake registry
4. ✅ Implement progress files for session bridging
5. ✅ Test: Agent self-corrects based on sensors

---

## THE KEY DIFFERENCES FROM FIRST VERSION

| Aspect | First Version | This Version |
|--------|---------------|--------------|
| **Primary Interface** | Orchestrator managing tasks | Natural conversation with Xochitl |
| **Task Execution** | Always autonomous | User chooses: collaborative or autonomous |
| **Tool Usage** | Auto-executed | Suggested, requires permission |
| **File Operations** | Direct execution | Permission model like Claude.ai |
| **BMAD** | Background process | Conversational workflow tool |
| **Orchestrator** | Core system | Optional background capability |
| **UX Metaphor** | "Task manager" | "Strategic partner you chat with" |

---

## CRITICAL SUCCESS METRICS (REVISED)

### Conversational Quality
- **Natural flow:** >90% of exchanges feel like chatting with a person
- **Permission friction:** <10% of operations require explicit confirmation
- **Suggestion accuracy:** >80% of skill suggestions are relevant

### Task Execution
- **Collaborative completion:** User + Xochitl together finishes tasks
- **Autonomous delegation:** User can hand off tasks and trust results
- **Mode switching:** Seamless transition between collaborative and autonomous

### System Reliability
- **Orchestrator uptime:** >99% when enabled
- **File operations:** Zero accidental overwrites/deletes
- **Context retention:** Conversation stays coherent across sessions

---

The core principle: **Xochitl is YOUR strategic partner who can ALSO manage autonomous work when you want that.**

You don't talk to the orchestrator. You talk to Xochitl. She uses the orchestrator when appropriate.
