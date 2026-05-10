# Xochitl Architecture Improvements & Implementation Guide

**Document Version:** 1.0  
**Date:** April 29, 2026  
**Status:** Ready for Implementation

---

## Executive Summary

This document consolidates all architectural improvements, corrections, and implementation recommendations for Xochitl, your terminal-native AI Chief of Staff. All suggestions have been reviewed and approved for implementation.

---

## Table of Contents

1. [Critical Architecture Corrections](#critical-architecture-corrections)
2. [Memory System Refinements](#memory-system-refinements)
3. [BMAD Integration Architecture](#bmad-integration-architecture)
4. [Local Model Strategy](#local-model-strategy)
5. [Security & Sandboxing](#security--sandboxing)
6. [Error Handling & Degradation](#error-handling--degradation)
7. [Context Compression Pipeline](#context-compression-pipeline)
8. [Tiered Routing System](#tiered-routing-system)
9. [File Generation Protocol](#file-generation-protocol)
10. [Observability & Introspection](#observability--introspection)
11. [Implementation Phases](#implementation-phases)
12. [Critical Tests to Run Early](#critical-tests-to-run-early)
13. [Code Examples](#code-examples)

---

## Critical Architecture Corrections

### BMAD is NOT a Separate Agent

**Original Misconception:**
> "She runs the BMAD workflows in the background, gathers the output, and discusses the results"

**Correction:**
BMAD is a **structured prompt framework**, not a separate AI process. Xochitl doesn't "call BMAD" — she **becomes the BMAD agent** when needed by loading workflow prompts.

**How It Actually Works:**
1. User is in a BMAD-managed project (detected via `.clinerules/`)
2. User says: "Help me plan a new feature"
3. Xochitl detects intent → maps to BMAD workflow: `feature-planning`
4. Xochitl loads the BMAD prompt template from `.clinerules/workflows/`
5. Xochitl augments the prompt with current project context
6. Xochitl routes to local or cloud model based on complexity
7. Xochitl saves artifacts following BMAD folder conventions
8. Xochitl seamlessly returns to normal personality

---

## Memory System Refinements

### Proposed Memory Hierarchy

Replace the simple two-tier system with a structured three-tier architecture:

#### 1. Active Context (`MEMORY.md`)
- **Max Size:** 2000 tokens
- **Content:** Current preferences, active goals, context shortcuts
- **Eviction Policy:** Auto-summarize when approaching limit
- **Versioning:** Git-tracked for rollback capability
- **Update Frequency:** Real-time via `update_core_memory` tool

**Structure:**
```markdown
# MEMORY.md

## Meta (Last Updated: 2024-01-15)
version: 3

## User Preferences
- writing_style: concise, active voice
- priority_project: Xochitl
- notification_preference: minimal

## Active Goals
- [ ] Complete Xochitl MVP by Feb 1
- [ ] Launch JobAgent beta by March

## Active BMAD Workflows
- feature-planning (Step 3/5: User Stories)
- architecture-design (Complete, artifacts in planning-artifacts/)

## BMAD Project Context
- current_project: JobAgent
- bmad_version: 6.0
- active_modules: BMM, TEA

## Paused Workflows
- workflow: architecture-design
  step: 3/5
  context_snapshot: "User was defining API contracts..."
  last_active: 2024-01-15T14:30:00

## Context Shortcuts
@current_sprint -> tasks.db WHERE sprint='2024-W03'
@recent_decisions -> vector_db.query(last_7_days, tag='decision')
```

#### 2. Working Memory (Session-based)
- **Storage:** SQLite database
- **Scope:** Current conversation only
- **Retention:** 24 hours of inactivity
- **Purpose:** Feed into vector DB on explicit save
- **Schema:**
  ```sql
  CREATE TABLE sessions (
      id INTEGER PRIMARY KEY,
      started_at TIMESTAMP,
      last_active TIMESTAMP,
      conversation_json TEXT,
      context_summary TEXT
  );
  ```

#### 3. Long-Term Memory (Vector Database)
- **Engine:** ChromaDB or LanceDB (local, privacy-first)
- **Metadata Fields:**
  - `timestamp` (for recency weighting)
  - `project` (e.g., "JobAgent", "Xochitl")
  - `tags` (#decision, #preference, #brainstorm)
  - `workflow` (if from BMAD session)
- **Scoring Formula:** `score = similarity * recency_weight`
- **Maintenance:** Monthly auto-summarization of old memories
- **Tools:**
  - `memorize(topic, summary, tags)` - Commit to vector DB
  - `recall(query, recency_bias=True)` - Semantic search with temporal weighting

### Conflict Resolution Protocol

When preferences change:
```markdown
**Scenario:** User previously said "I prefer detailed explanations" 
             Now says "Keep responses concise"

**Xochitl's Response:**
1. Detect conflict via semantic similarity in MEMORY.md
2. Confirm with user: "I notice you previously preferred detailed explanations. 
   Should I update that to concise responses?"
3. If YES → Update MEMORY.md, archive old preference to vector DB with deprecation tag
4. If NO → Create context-specific rule: "Detailed for technical, concise for creative"
```

---

## BMAD Integration Architecture

### Detection & Loading System

```python
class BMADDetector:
    """
    Detects BMAD installation and active modules
    """
    
    @staticmethod
    def detect_bmad_project(cwd: Path) -> Optional[dict]:
        """
        Walks up from current directory to find .clinerules/
        """
        current = cwd
        while current != current.parent:
            clinerules = current / ".clinerules"
            if clinerules.exists():
                return {
                    'root': current,
                    'version': BMADDetector._parse_version(clinerules),
                    'modules': BMADDetector._detect_modules(clinerules),
                    'workflows': BMADDetector._list_workflows(clinerules)
                }
            current = current.parent
        return None
    
    @staticmethod
    def _detect_modules(clinerules: Path) -> list[str]:
        """
        Reads installed BMAD modules (BMM, TEA, BMGD, CIS, etc.)
        """
        modules = ['BMM']  # Core always present
        
        if (clinerules / 'test-architecture').exists():
            modules.append('TEA')
        if (clinerules / 'game-dev').exists():
            modules.append('BMGD')
        if (clinerules / 'creative-intelligence').exists():
            modules.append('CIS')
        if (clinerules / 'builder').exists():
            modules.append('BMB')
        
        return modules
```

### Workflow Integration Pattern

```python
class XochitlBMADIntegration:
    """
    Xochitl loads BMAD skills/workflows as needed
    """
    
    def __init__(self, bmad_install_path: Path):
        self.bmad_path = bmad_install_path
        self.workflows = self._load_workflows()
        
    def invoke_workflow(self, workflow_name: str, context: dict) -> str:
        """
        Loads BMAD prompt, augments Xochitl's context, runs locally or cloud
        """
        # 1. Load the BMAD workflow prompt from .clinerules/workflows/
        workflow_prompt = self._read_workflow(workflow_name)
        
        # 2. Inject user context
        full_prompt = self._merge_context(workflow_prompt, context)
        
        # 3. Route based on complexity
        if self._is_complex(workflow_name):
            # Use cloud model with BMAD prompt
            return self.cloud_llm.generate(full_prompt)
        else:
            # Use local model with BMAD prompt
            return self.local_llm.generate(full_prompt)
            
    def _merge_context(self, workflow_prompt: str, user_context: dict) -> str:
        """
        Combines BMAD template with current project state
        """
        context_items = {
            'current_files': self._get_relevant_files(user_context),
            'memory_sections': self._get_memory_sections(user_context),
            'active_tasks': self._get_tasks_from_db(user_context),
            'user_requirements': user_context.get('requirements', '')
        }
        
        return workflow_prompt.format(**context_items)
```

### BMAD Workflow Routing Table

| BMAD Workflow | Xochitl Trigger | Routing | Estimated Tokens |
|---------------|-----------------|---------|------------------|
| `bmad-help` | "what should I do next?" | Local | ~500 |
| Feature Planning | "plan this feature" | Cloud (Claude) | 5k-15k |
| Architecture Design | "design the architecture" | Cloud (Claude) | 10k-30k |
| Sprint Planning | "create sprint stories" | Cloud | 3k-10k |
| Code Review | "review this code" | Local → Cloud if complex | 2k-8k |
| Bug Fix Planning | "help fix this bug" | Local | 1k-3k |
| Party Mode | "start party mode" | Cloud only + Warning | 15k-50k |

### BMAD-Aware Help System

When user asks "what should I do next?", Xochitl checks:

1. **Is this a BMAD project?**
   - YES → Load `bmad-help` skill, provide BMAD-aware guidance
   - NO → Provide general Xochitl capabilities

2. **Contextual BMAD Help:**
   - In `/planning-artifacts/` → "You're in planning phase. Run architecture design next?"
   - In `/implementation-artifacts/` → "Ready to generate sprint stories?"
   - No BMAD folder detected → "Want to initialize a BMAD project here?"

3. **Workflow State Awareness:**
   - Check MEMORY.md for paused workflows
   - "You were on Step 3 of feature-planning. Resume or start fresh?"

### Party Mode Handling

BMAD's Party Mode (multiple agent personas) is token-expensive:

```markdown
**Party Mode Protocol:**

1. **Warning Before Invocation:**
   Xochitl: "Party Mode brings multiple BMAD agents into one session. 
            This uses significant cloud tokens (~$0.50-2.00 per session). 
            Proceed?"

2. **User Confirmation Required:**
   - User types: "yes" or "proceed"
   - Xochitl routes to cloud-only execution

3. **Post-Session Summarization:**
   - After Party Mode completes, Xochitl extracts key decisions
   - Commits summary to vector DB with tags: #party-mode, #decisions
   - Updates MEMORY.md with action items
```

### Unified Skill System

Xochitl's capabilities come from TWO sources:

#### 1. Custom Xochitl Skills
Location: `~/.openclaw/skills/xochitl/`

- `voice_editor/` - LinkedIn post matching your style
- `memory_manager/` - Vector DB operations
- `notion_sync/` - Task queue integration
- `xochitl_help/` - Introspection and capability listing

#### 2. BMAD Workflows
Location: `~/CodeProjects/*/​.clinerules/workflows/`

- Automatically detected when working in BMAD projects
- Loaded on-demand based on user intent
- Xochitl acts as the BMAD agent during these workflows

**Auto-Detection Logic:**
```python
def get_available_skills(current_directory: Path) -> list[str]:
    """
    Combines Xochitl skills + BMAD workflows if detected
    """
    skills = load_xochitl_skills()  # Always available
    
    bmad_project = BMADDetector.detect_bmad_project(current_directory)
    if bmad_project:
        skills.extend(bmad_project['workflows'])
    
    return skills
```

---

## Local Model Strategy

### Recommended Models (8GB VRAM)

**Original Plan:** Gemma 2 9B or Llama 3 8B

**Improved Recommendations:**

1. **Llama 3.1 8B Instruct** (BEST for tool use)
   - Significantly better function calling
   - Better instruction following
   - Download: `ollama pull llama3.1:8b-instruct-q6_K`

2. **Qwen 2.5 7B** (BEST for reasoning)
   - Excellent at planning and decision-making
   - Strong coding capabilities
   - Download: `ollama pull qwen2.5:7b`

3. **Quantized Larger Model:** Llama 3.1 70B Q4
   - If you can fit it (requires ~40GB RAM)
   - Vastly superior orchestration
   - Download: `ollama pull llama3.1:70b-instruct-q4_K_M`

### Orchestration Capability Testing

**CRITICAL: Test this in Week 1 before building everything else**

```python
# test_local_orchestration.py

def test_tool_routing():
    """
    Test if local model can reliably route to correct tools
    """
    test_cases = [
        ("mark task 1 done", "task_management_tool"),
        ("what did we discuss about the JobAgent app last month?", "vector_db_recall"),
        ("help me design the architecture", "bmad_workflow:architecture"),
        ("sync my Notion tasks", "notion_sync_tool"),
    ]
    
    results = []
    for query, expected_tool in test_cases:
        actual_tool = local_model.route(query)
        results.append((query, expected_tool == actual_tool))
    
    accuracy = sum(r[1] for r in results) / len(results)
    
    if accuracy < 0.85:
        print(f"⚠️  Local model accuracy: {accuracy*100}%")
        print("RECOMMENDATION: Use quantized 70B or increase cloud routing")
    else:
        print(f"✅ Local model accuracy: {accuracy*100}%")
        
    return results
```

### Routing Decision Tree with Confidence Scores

```python
class XochitlRouter:
    """
    Routes queries to local or cloud based on confidence
    """
    
    def route_query(self, user_input: str) -> Route:
        """
        Local model assigns confidence score to its own response
        """
        # Step 1: Local model attempts to generate response
        local_response, confidence = self.local_llm.generate_with_confidence(user_input)
        
        # Step 2: Route based on confidence threshold
        if confidence < 0.7:
            # Low confidence = complex query
            compressed_context = self.compress_context(user_input)
            return CloudRoute(user_input, compressed_context)
        else:
            # High confidence = simple query
            return LocalRoute(local_response)
    
    def compress_context(self, query: str) -> str:
        """
        Extract only relevant context before sending to cloud
        """
        # 1. Extract files mentioned in last 5 messages
        recent_files = self.get_recent_files(n=5)
        
        # 2. Summarize conversation history into bullet points
        conversation_summary = self.summarize_history()
        
        # 3. Include current task from tasks.db
        current_task = self.get_current_task()
        
        # 4. Include relevant MEMORY.md sections (semantic search)
        memory_sections = self.search_memory(query)
        
        # Result: 50k token conversation → 2k token compressed context
        return self.format_compressed_context(
            recent_files, 
            conversation_summary, 
            current_task, 
            memory_sections
        )
```

### Fallback Strategy

```python
class RouterWithFallback:
    """
    Handles local model failures gracefully
    """
    
    def __init__(self):
        self.consecutive_failures = 0
        self.failure_threshold = 2
    
    def route(self, query: str) -> str:
        try:
            result = self.local_model.generate(query)
            self.consecutive_failures = 0  # Reset on success
            return result
            
        except Exception as e:
            self.consecutive_failures += 1
            
            if self.consecutive_failures >= self.failure_threshold:
                # Auto-escalate to cloud after 2 failures
                return self.cloud_model.generate(query)
            else:
                # Retry once before escalating
                return self.route(query)
```

### Few-Shot Examples for Tool Routing

Add explicit routing examples to local model's system prompt:

```markdown
## Tool Routing Examples

Query: "mark task 1 done"
Tool: task_management → mark_complete(1)

Query: "what did we discuss about JobAgent last month?"
Tool: vector_db → recall("JobAgent", recency=30days)

Query: "help me plan this new feature"
Detected: BMAD project
Tool: bmad_workflow → feature-planning

Query: "sync my Notion queue"
Tool: notion_sync → sync_tasks()

Query: "design the database schema for user authentication"
Complexity: HIGH
Tool: cloud_expert → claude-sonnet
```

---

## Security & Sandboxing

### MCP Server Restrictions

**Problem:** Giving AI full filesystem access is risky.

**Solution: Scope-Based Permissions**

```python
class SecureMCPServer:
    """
    MCP server with enforced directory restrictions
    """
    
    ALLOWED_PATHS = [
        Path.home() / "CodeProjects",
        Path.home() / "Documents/Xochitl",
        Path.home() / "Downloads"  # Read-only
    ]
    
    FORBIDDEN_PATHS = [
        Path.home() / ".ssh",
        Path.home() / ".aws",
        Path("/etc"),
        Path("/System")
    ]
    
    def read_file(self, path: Path) -> str:
        """
        Read file with permission check
        """
        if not self._is_allowed(path):
            raise PermissionError(f"Access denied: {path}")
        
        return path.read_text()
    
    def write_file(self, path: Path, content: str, confirm: bool = False):
        """
        Write file with confirmation for destructive operations
        """
        if not self._is_allowed(path):
            raise PermissionError(f"Access denied: {path}")
        
        if path.exists() and not confirm:
            # Requires user confirmation before overwriting
            raise RequiresConfirmation(f"File exists: {path}. Confirm overwrite?")
        
        path.write_text(content)
        self._log_operation("write", path)
    
    def delete_file(self, path: Path):
        """
        Delete file - ALWAYS requires confirmation
        """
        if not self._is_allowed(path):
            raise PermissionError(f"Access denied: {path}")
        
        raise RequiresConfirmation(f"Delete {path}? This cannot be undone.")
    
    def _log_operation(self, operation: str, path: Path):
        """
        Audit log for all file operations
        """
        log_path = Path.home() / ".xochitl/audit.log"
        timestamp = datetime.now().isoformat()
        log_path.append_text(f"{timestamp} | {operation} | {path}\n")
```

### Confirmation Prompts

```python
class ConfirmationHandler:
    """
    Handles user confirmations for destructive operations
    """
    
    def require_confirmation(self, action: str, details: str) -> bool:
        """
        Pauses execution and asks user to confirm
        """
        print(f"\n⚠️  CONFIRMATION REQUIRED")
        print(f"Action: {action}")
        print(f"Details: {details}")
        print(f"\nType 'yes' to proceed, anything else to cancel: ", end="")
        
        response = input().strip().lower()
        return response in ['yes', 'y', 'confirm']
```

### Dry-Run Mode

```python
class DryRunMode:
    """
    Preview commands before execution
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
    
    def execute_command(self, command: str) -> str:
        """
        Shows what would happen without actually doing it
        """
        if self.enabled:
            print(f"\n[DRY RUN] Would execute: {command}")
            print("Proceed? (yes/no): ", end="")
            
            if input().strip().lower() != 'yes':
                return "Command cancelled by user"
        
        # Actually execute
        return subprocess.run(command, shell=True, capture_output=True)
```

### Remote Access Security

```python
class RemoteAccessGateway:
    """
    Secure gateway for laptop/phone connections
    """
    
    def __init__(self):
        self.sessions = {}
        self.rate_limiter = RateLimiter(max_requests=100, window=3600)
    
    def authenticate(self, client_id: str, token: str) -> Session:
        """
        Authenticate remote client
        """
        # Verify API key or biometric token
        if not self._verify_token(token):
            raise AuthenticationError("Invalid credentials")
        
        # Create session with 1-hour expiry
        session = Session(
            client_id=client_id,
            expires_at=datetime.now() + timedelta(hours=1),
            capabilities=self._get_capabilities(client_id)
        )
        
        self.sessions[session.id] = session
        return session
    
    def _get_capabilities(self, client_id: str) -> list[str]:
        """
        Restrict capabilities based on client type
        """
        if client_id.startswith("mobile_"):
            # Mobile clients have restricted permissions
            return [
                "read_files",
                "query_tasks",
                "recall_memory",
                "brainstorm",
                # CANNOT delete files or modify MEMORY.md
            ]
        elif client_id.startswith("laptop_"):
            # Laptop gets full permissions
            return ["all"]
        else:
            return ["read_only"]
    
    def check_rate_limit(self, session_id: str):
        """
        Prevent runaway API calls
        """
        if not self.rate_limiter.allow(session_id):
            raise RateLimitExceeded("Too many requests. Try again in 1 hour.")
```

---

## Error Handling & Degradation

### Comprehensive Failure Modes

```python
class XochitlErrorHandler:
    """
    Graceful degradation for all failure scenarios
    """
    
    def handle_local_model_failure(self):
        """
        Local GPU unresponsive or crashed
        """
        print("⚠️  Desktop GPU busy, switching to cloud mode temporarily...")
        
        # Fall back to cloud with cached context
        cached_context = self.load_cached_context()
        response = self.cloud_model.generate(cached_context)
        
        # Log incident for later review
        self.log_incident("local_model_failure")
        
        return response
    
    def handle_vector_db_corruption(self):
        """
        ChromaDB database corrupted or inaccessible
        """
        print("⚠️  Memory database unavailable. Using short-term memory only...")
        
        # Fall back to MEMORY.md only
        memory = self.read_memory_md()
        
        # Attempt repair on next startup
        self.schedule_repair("vector_db")
        
        return memory
    
    def handle_notion_api_failure(self):
        """
        Notion API down or rate limited
        """
        print("⚠️  Notion sync unavailable. Queueing operations locally...")
        
        # Queue operations in local SQLite
        self.queue_manager.store_pending_sync()
        
        # Auto-retry every 5 minutes
        self.schedule_retry("notion_sync", interval=300)
        
        return "Operations queued. Will sync when Notion is available."
    
    def handle_cloud_rate_limit(self):
        """
        Claude/Gemini API rate limited
        """
        print("⚠️  Cloud API rate limit hit. Using cached responses...")
        
        # Try to find similar cached response
        cached = self.response_cache.find_similar(self.current_query)
        
        if cached:
            print("(Using cached response from similar query)")
            return cached
        else:
            print("Suggestion: Wait 60 seconds or switch to local-only mode?")
            return self.suggest_local_mode()
    
    def handle_bmad_workflow_interruption(self):
        """
        User interrupts mid-workflow (Ctrl+C, connection lost)
        """
        print("\n⚠️  Workflow paused. Saving state...")
        
        # Save current state to MEMORY.md
        self.save_workflow_state(
            workflow=self.current_workflow,
            step=self.current_step,
            context=self.current_context
        )
        
        print("Resume anytime with: 'xochitl resume'")
```

### Automatic Retry Logic

```python
class RetryHandler:
    """
    Exponential backoff for transient failures
    """
    
    def retry_with_backoff(self, func, max_retries=3):
        """
        Retry with exponential backoff: 1s, 2s, 4s
        """
        for attempt in range(max_retries):
            try:
                return func()
            except TransientError as e:
                if attempt == max_retries - 1:
                    raise  # Give up after max retries
                
                wait_time = 2 ** attempt
                print(f"Retrying in {wait_time}s... (attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
```

---

## Context Compression Pipeline

### Before Sending to Cloud

**Problem:** Sending entire conversation history wastes tokens

**Solution: Smart Context Extraction**

```python
class ContextCompressor:
    """
    Extracts minimal relevant context before cloud routing
    """
    
    def compress(self, query: str, conversation_history: list) -> str:
        """
        Reduces 50k token history → 2k token compressed context
        """
        # Step 1: Extract files mentioned in last 5 messages
        recent_files = self._extract_recent_files(conversation_history[-5:])
        
        # Step 2: Summarize older conversation into bullet points
        conversation_summary = self._summarize_history(conversation_history[:-5])
        
        # Step 3: Get current task from database
        current_task = self.task_db.get_current()
        
        # Step 4: Semantic search MEMORY.md for relevant sections
        memory_sections = self._search_memory(query)
        
        # Step 5: If BMAD project, include project context
        bmad_context = self._get_bmad_context() if self.in_bmad_project else ""
        
        # Assemble compressed context
        compressed = f"""
# Current Task
{current_task}

# Relevant Memory
{memory_sections}

# Recent Conversation Summary
{conversation_summary}

# Referenced Files
{recent_files}

# BMAD Project Context
{bmad_context}

# Current Query
{query}
"""
        
        return compressed
    
    def _summarize_history(self, messages: list) -> str:
        """
        Use local model to create bullet-point summary
        """
        prompt = f"""
Summarize this conversation into 5-10 bullet points capturing key decisions and context:

{messages}

Format as:
- Decision/fact 1
- Decision/fact 2
...
"""
        return self.local_model.generate(prompt)
    
    def _extract_recent_files(self, messages: list) -> str:
        """
        Find file paths mentioned in recent messages
        """
        file_paths = []
        for msg in messages:
            # Regex to find file paths
            paths = re.findall(r'(/[^\s]+\.\w+)', msg)
            file_paths.extend(paths)
        
        # Read content of mentioned files (up to 1000 tokens each)
        file_contents = []
        for path in set(file_paths):
            try:
                content = self.mcp_server.read_file(path)
                truncated = content[:4000]  # ~1000 tokens
                file_contents.append(f"## {path}\n{truncated}")
            except:
                continue
        
        return "\n\n".join(file_contents)
```

### Token Budget Tracking

```python
class TokenBudget:
    """
    Tracks and enforces token usage limits
    """
    
    def __init__(self, daily_budget: int = 100000):
        self.daily_budget = daily_budget
        self.used_today = 0
        self.last_reset = datetime.now().date()
    
    def check_budget(self, estimated_tokens: int) -> bool:
        """
        Returns True if request fits in budget
        """
        self._reset_if_new_day()
        
        if self.used_today + estimated_tokens > self.daily_budget:
            remaining = self.daily_budget - self.used_today
            print(f"⚠️  Token budget warning: {remaining} tokens remaining today")
            print(f"This request needs ~{estimated_tokens} tokens")
            print("Proceed? (yes/no): ", end="")
            
            return input().strip().lower() == 'yes'
        
        return True
    
    def record_usage(self, tokens_used: int):
        """
        Records actual token usage
        """
        self.used_today += tokens_used
        
        # Save to persistent storage
        self._save_usage()
    
    def _reset_if_new_day(self):
        """
        Reset counter at midnight
        """
        today = datetime.now().date()
        if today > self.last_reset:
            self.used_today = 0
            self.last_reset = today
```

---

## Tiered Routing System

### Replace Generic `consult_cloud_expert` with Specific Routes

```python
class TieredRouter:
    """
    Routes queries to appropriate model/workflow based on category
    """
    
    ROUTING_RULES = {
        # Simple queries → Local model
        'simple_qa': LocalModel(),
        'task_management': LocalModel(),
        'file_operations': LocalModel(),
        'memory_recall': LocalModel(),
        
        # Complex queries → Cloud models
        'code_generation': CloudModel('claude-sonnet-4'),
        'architecture_planning': CloudModel('claude-sonnet-4'),
        'creative_writing': CloudModel('claude-opus-4'),
        'data_analysis': CloudModel('claude-sonnet-4'),
        
        # BMAD workflows → Specific routing
        'bmad_simple': LocalModel(),  # bmad-help, bug-fix
        'bmad_complex': CloudModel('claude-sonnet-4'),  # architecture, PRD
        'bmad_party_mode': CloudModel('claude-opus-4'),  # Multi-agent
        
        # Hybrid workflows
        'code_review': HybridRoute(
            simple_threshold=100,  # lines of code
            local=LocalModel(),
            cloud=CloudModel('claude-sonnet-4')
        ),
    }
    
    def route(self, query: str, context: dict) -> Response:
        """
        Determine appropriate route and execute
        """
        # Step 1: Classify query category
        category = self._classify_query(query, context)
        
        # Step 2: Get routing rule
        route = self.ROUTING_RULES.get(category)
        
        # Step 3: Execute
        if isinstance(route, HybridRoute):
            return route.execute_with_fallback(query, context)
        else:
            return route.execute(query, context)
    
    def _classify_query(self, query: str, context: dict) -> str:
        """
        Use local model to classify query category
        """
        classification_prompt = f"""
Classify this query into ONE category:

Categories:
- simple_qa: Factual question, definition, explanation
- task_management: Mark task done, show tasks, update status
- file_operations: Read, write, list files
- memory_recall: "What did we discuss about X?"
- code_generation: Write code, create script, implement feature
- architecture_planning: Design system, plan architecture
- creative_writing: Write post, draft email, create content
- code_review: Review this code, check for bugs
- bmad_simple: bmad-help, simple BMAD workflow
- bmad_complex: BMAD architecture, PRD, party mode

Query: {query}
Context: {context}

Category:"""
        
        return self.local_model.generate(classification_prompt).strip()
```

### Hybrid Routes with Fallback

```python
class HybridRoute:
    """
    Tries local first, falls back to cloud if needed
    """
    
    def __init__(self, simple_threshold: int, local: Model, cloud: Model):
        self.threshold = simple_threshold
        self.local = local
        self.cloud = cloud
    
    def execute_with_fallback(self, query: str, context: dict) -> Response:
        """
        Try local, assess quality, fallback if needed
        """
        # Try local model first
        local_response = self.local.generate(query, context)
        
        # Assess quality (confidence score or heuristics)
        quality = self._assess_quality(local_response)
        
        if quality > 0.8:
            # Local response is good enough
            return local_response
        else:
            # Fall back to cloud
            print("🔄 Upgrading to cloud model for better quality...")
            return self.cloud.generate(query, context)
    
    def _assess_quality(self, response: str) -> float:
        """
        Simple heuristics for response quality
        """
        # Check for hallucination markers
        if "I'm not sure" in response or "I don't have" in response:
            return 0.5
        
        # Check for code completeness
        if "```" in response:
            # Count opening vs closing code blocks
            opens = response.count("```")
            if opens % 2 != 0:  # Unclosed code block
                return 0.6
        
        # Default: assume good quality
        return 0.85
```

---

## File Generation Protocol

### BMAD-Aware File Saver

```python
class BMADAwareFiler:
    """
    Xochitl's file generation respects BMAD conventions
    """
    
    BMAD_STRUCTURE = {
        'planning': 'planning-artifacts/',
        'implementation': 'implementation-artifacts/',
        'architecture': 'planning-artifacts/architecture/',
        'tests': 'implementation-artifacts/tests/',
        'docs': 'docs/',
        'sprint': 'implementation-artifacts/sprints/',
        'ux': 'planning-artifacts/ux/',
    }
    
    def save_artifact(
        self, 
        content: str, 
        artifact_type: str, 
        filename: str,
        explicit_path: Optional[Path] = None
    ) -> Path:
        """
        Auto-routes to correct folder based on context
        """
        # 1. Check for explicit path override
        if explicit_path:
            filepath = explicit_path / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
            return filepath
        
        # 2. Detect project root
        project_root = self._detect_project_root()
        
        if not project_root:
            # No BMAD project detected, use Xochitl's workspace
            target = Path.home() / "CodeProjects/Xochitl/data/generated"
            target.mkdir(parents=True, exist_ok=True)
        else:
            # BMAD project detected, use proper structure
            folder = self.BMAD_STRUCTURE.get(artifact_type, 'docs/')
            target = project_root / folder
            target.mkdir(parents=True, exist_ok=True)
        
        # 3. Save file
        filepath = target / filename
        filepath.write_text(content)
        
        # 4. Log to audit trail
        self._log_file_creation(filepath, artifact_type)
        
        return filepath
    
    def _detect_project_root(self) -> Optional[Path]:
        """
        Look for .clinerules/ to identify BMAD project
        """
        cwd = Path.cwd()
        current = cwd
        
        while current != current.parent:
            if (current / ".clinerules").exists():
                return current
            current = current.parent
        
        return None
    
    def provide_clickable_link(self, filepath: Path) -> str:
        """
        Generate terminal-friendly link message
        """
        # Most terminals support file:// URLs
        file_url = filepath.as_uri()
        
        return f"""
✅ File saved successfully!

📄 {filepath.name}
📁 Location: {filepath.parent}
🔗 Open: {file_url}

You can click the link above or run: `open "{filepath}"`
"""
```

### Smart Filename Generation

```python
class FilenameGenerator:
    """
    Generates descriptive, collision-free filenames
    """
    
    def generate(
        self, 
        artifact_type: str, 
        user_description: Optional[str] = None
    ) -> str:
        """
        Creates filename from context
        """
        # Get base name from type
        base_names = {
            'planning': 'prd',
            'architecture': 'architecture',
            'sprint': 'sprint-stories',
            'ux': 'wireframes',
            'tests': 'test-plan',
            'docs': 'documentation',
        }
        
        base = base_names.get(artifact_type, 'document')
        
        # Add user description if provided
        if user_description:
            # Slugify description
            slug = user_description.lower()
            slug = re.sub(r'[^\w\s-]', '', slug)
            slug = re.sub(r'[-\s]+', '-', slug)
            base = f"{base}-{slug}"
        
        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d")
        
        # Check for collisions
        filename = f"{base}-{timestamp}.md"
        counter = 1
        
        while self._file_exists(filename):
            filename = f"{base}-{timestamp}-{counter}.md"
            counter += 1
        
        return filename
```

---

## Observability & Introspection

### `xochitl stats` Command

```python
class XochitlStats:
    """
    Provides usage statistics and health metrics
    """
    
    def generate_stats(self) -> str:
        """
        Comprehensive usage report
        """
        stats = {
            'local_calls': self._count_local_calls(days=7),
            'cloud_calls': self._count_cloud_calls(days=7),
            'cloud_cost': self._calculate_cloud_cost(days=7),
            'vector_db_size': self._get_vector_db_size(),
            'active_tasks': self._count_active_tasks(),
            'memory_usage': self._get_memory_usage(),
            'bmad_projects': self._count_bmad_projects(),
            'uptime': self._calculate_uptime(),
        }
        
        return f"""
╔══════════════════════════════════════════╗
║        Xochitl Usage Statistics          ║
╚══════════════════════════════════════════╝

📊 Last 7 Days
   Local model calls:     {stats['local_calls']}
   Cloud API calls:       {stats['cloud_calls']}
   Cloud cost:           ${stats['cloud_cost']:.2f}

🧠 Memory System
   Vector DB memories:    {stats['vector_db_size']:,}
   Active context size:   {self._format_bytes(stats['memory_usage'])}
   
📋 Task Management
   Active tasks:          {stats['active_tasks']}
   
🏗️  BMAD Integration
   Tracked projects:      {stats['bmad_projects']}
   
⏱️  System Health
   Uptime:               {stats['uptime']}
   Status:               {'🟢 Healthy' if self._is_healthy() else '🔴 Issues detected'}

Run 'xochitl stats --detailed' for breakdown by project.
"""
    
    def _format_bytes(self, bytes: int) -> str:
        """
        Human-readable byte sizes
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024
        return f"{bytes:.1f} TB"
```

### Enhanced Help System

```python
class XochitlHelp:
    """
    Context-aware help and capability listing
    """
    
    def provide_help(self, context: Optional[str] = None) -> str:
        """
        Generate help based on current context
        """
        # Detect current context
        in_bmad_project = self._detect_bmad_project()
        current_workflow = self._get_active_workflow()
        
        if current_workflow:
            return self._workflow_specific_help(current_workflow)
        elif in_bmad_project:
            return self._bmad_project_help()
        else:
            return self._general_help()
    
    def _general_help(self) -> str:
        """
        General Xochitl capabilities
        """
        return """
╔══════════════════════════════════════════╗
║         Xochitl Capabilities             ║
╚══════════════════════════════════════════╝

💬 Conversation
   • Natural conversation and brainstorming
   • Context-aware responses using MEMORY.md
   • Long-term recall from vector database
   
📋 Task Management
   • "show my tasks" - View task queue
   • "mark task 1 done" - Update task status
   • "sync Notion" - Pull latest from Notion
   
🧠 Memory
   • "remember that I prefer X" - Update preferences
   • "what did we discuss about Y?" - Recall past conversations
   
📁 File Generation
   • "draft a PRD for X" - Create planning documents
   • "write a LinkedIn post about Y" - Match your writing style
   
🏗️  BMAD Integration
   • Initialize BMAD in project: "bmad init"
   • Available when working in BMAD projects
   
Need specific guidance? Ask:
   • "help with task management"
   • "help with memory"
   • "what can we do with BMAD?"
"""
    
    def _bmad_project_help(self) -> str:
        """
        BMAD-specific help
        """
        bmad_info = self.bmad_detector.detect_bmad_project(Path.cwd())
        
        return f"""
╔══════════════════════════════════════════╗
║      BMAD Project Detected               ║
╚══════════════════════════════════════════╝

📁 Project: {bmad_info['root'].name}
🔧 Version: {bmad_info['version']}
📦 Modules: {', '.join(bmad_info['modules'])}

🏗️  Available BMAD Workflows
   • "help me plan a feature" → Feature Planning
   • "design the architecture" → Architecture Design
   • "create sprint stories" → Sprint Planning
   • "review this code" → Code Review
   • "start party mode" → Multi-Agent Discussion
   
📄 BMAD Artifacts
   • planning-artifacts/ - PRDs, wireframes, architecture
   • implementation-artifacts/ - Sprint stories, code
   
❓ BMAD Help
   • "bmad-help" - Context-aware guidance
   • "bmad-help what's next?" - Workflow recommendations
   
💡 Tip: I'll automatically save artifacts in the right BMAD folders
"""
    
    def _workflow_specific_help(self, workflow: dict) -> str:
        """
        Help during active workflow
        """
        return f"""
╔══════════════════════════════════════════╗
║      Active Workflow                     ║
╚══════════════════════════════════════════╝

🔄 {workflow['name']}
📍 Step {workflow['current_step']}/{workflow['total_steps']}

Current: {workflow['step_description']}

⏭️  Next Steps:
   1. {workflow['next_action']}
   2. Type "continue" to proceed
   3. Type "pause" to save and exit

💡 You can ask me questions anytime without interrupting the workflow
"""
```

### Proactive Tool Suggestions

```python
class ProactiveSuggester:
    """
    Suggests tools/workflows based on vague queries
    """
    
    def analyze_and_suggest(self, query: str) -> Optional[str]:
        """
        Detects vague queries and suggests concrete actions
        """
        vague_patterns = {
            r"i'm stuck|stuck on|not sure|help me": self._suggest_for_stuck,
            r"new feature|new project|start building": self._suggest_for_new_project,
            r"organize|clean up|refactor": self._suggest_for_organization,
        }
        
        for pattern, suggester in vague_patterns.items():
            if re.search(pattern, query, re.IGNORECASE):
                return suggester(query)
        
        return None
    
    def _suggest_for_stuck(self, query: str) -> str:
        """
        User is stuck, suggest debugging options
        """
        options = []
        
        # Check if in code file
        if self._in_code_file():
            options.append("• Read your current file to understand context")
            options.append("• Review recent changes with git")
        
        # Check if BMAD project
        if self._in_bmad_project():
            options.append("• Review planning artifacts for requirements")
            options.append("• Start a BMAD code review workflow")
        
        # Always offer
        options.append("• Search my memory for similar past problems")
        options.append("• Break down the problem with me step-by-step")
        
        return f"""
I can help! Here are some options:

{chr(10).join(options)}

What sounds most useful right now?
"""
```

---

## Implementation Phases

### Phase 1: Core MVP (2-3 weeks)

**Goal:** Basic working Xochitl with local model

**Deliverables:**
1. ✅ CLI command `xochitl` launches chat
2. ✅ Local model integration (Llama 3.1 8B)
3. ✅ Basic MEMORY.md system with `update_core_memory` tool
4. ✅ File generation with BMAD folder detection
5. ✅ Single MCP server (filesystem read-only)
6. ✅ Simple task database (SQLite) integration

**Success Criteria:**
- Can launch Xochitl from any terminal
- Can have basic conversation using local model
- Can save files to correct BMAD folders
- MEMORY.md persists preferences across sessions

**Week 1 Tasks:**
```bash
# Setup
- Install Ollama and pull Llama 3.1 8B
- Initialize OpenClaw project structure
- Create basic CLI wrapper

# Test local model capability
- Run orchestration tests (CRITICAL - see "Critical Tests" section)
- Verify tool routing accuracy
- Benchmark token efficiency

# MEMORY.md implementation
- Create MEMORY.md schema
- Implement update_core_memory tool
- Test persistence across restarts
```

**Week 2-3 Tasks:**
```bash
# MCP Integration
- Set up filesystem MCP server with restrictions
- Implement BMAD project detection
- Create file generation tools

# Task Management
- Create SQLite schema for tasks
- Implement basic task CRUD operations
- Test Notion sync (read-only first)

# Testing
- Integration tests for all components
- User acceptance testing with real workflows
```

### Phase 2: Enhanced Capabilities (2-3 weeks)

**Goal:** Cloud routing, vector DB, advanced features

**Deliverables:**
1. ✅ Cloud routing with context compression
2. ✅ ChromaDB vector database integration
3. ✅ `memorize` and `recall` tools
4. ✅ Enhanced help system with introspection
5. ✅ BMAD workflow loading and execution
6. ✅ Confidence-based routing

**Success Criteria:**
- Successfully routes complex queries to cloud
- Vector DB stores and retrieves memories
- BMAD workflows execute correctly
- Context compression reduces token usage by 90%+

**Week 1 Tasks:**
```bash
# Cloud Integration
- Set up Claude API client
- Implement context compression pipeline
- Test token usage and costs

# Vector Database
- Install and configure ChromaDB
- Implement memorize/recall tools
- Migrate sample conversations for testing
```

**Week 2-3 Tasks:**
```bash
# BMAD Integration
- Implement workflow detection
- Create workflow loader
- Test all major BMAD workflows

# Advanced Features
- Build confidence scoring system
- Implement tiered routing
- Add help system with capability listing
```

### Phase 3: Full System (3-4 weeks)

**Goal:** Remote access, advanced memory, production-ready

**Deliverables:**
1. ✅ Tailscale remote access from laptop
2. ✅ OpenClaw mobile app pairing
3. ✅ Advanced memory management (summarization, eviction)
4. ✅ Security hardening (sandboxing, audit logs)
5. ✅ Error handling and graceful degradation
6. ✅ Observability (stats, health checks)

**Success Criteria:**
- Can access Xochitl from laptop and phone
- Memory system handles 10k+ conversations
- All security features enabled
- Comprehensive error recovery

**Week 1-2 Tasks:**
```bash
# Remote Access
- Install Tailscale on desktop and laptop
- Configure OpenClaw Gateway
- Test remote CLI access
- Set up mobile app and test pairing
```

**Week 3-4 Tasks:**
```bash
# Production Hardening
- Implement all security restrictions
- Add comprehensive error handling
- Create audit logging system
- Build stats and monitoring dashboard

# Memory Optimization
- Implement auto-summarization
- Add eviction policies
- Test with large conversation volumes
```

### Phase 4: Polish & Optimization (Ongoing)

**Goal:** Refinement, optimization, new features

**Deliverables:**
1. ✅ Voice input on mobile (OpenClaw feature)
2. ✅ Notion sync automation (bidirectional)
3. ✅ Custom skill creation and refinement
4. ✅ Performance optimization
5. ✅ User feedback incorporation

**Continuous Improvements:**
```bash
# Weekly Reviews
- Analyze token usage patterns
- Optimize routing decisions
- Refine MEMORY.md structure based on usage

# Monthly Improvements
- Add new skills based on needs
- Expand BMAD workflow coverage
- Performance benchmarking and optimization
```

---

## Critical Tests to Run Early

### Test 1: Local Model Orchestration (WEEK 1, DAY 1)

**This is the most important test. If this fails, the entire architecture needs adjustment.**

```python
# test_orchestration.py

def test_tool_routing_accuracy():
    """
    Can local model route to correct tools?
    Target: >85% accuracy
    """
    test_cases = [
        ("mark task 1 done", "task_management"),
        ("what did we discuss about JobAgent?", "vector_db_recall"),
        ("help me design this architecture", "bmad_workflow"),
        ("sync my Notion tasks", "notion_sync"),
        ("read the file main.py", "mcp_filesystem"),
        ("what can you do?", "xochitl_help"),
    ]
    
    results = run_routing_tests(test_cases)
    
    if results['accuracy'] < 0.85:
        print("❌ CRITICAL: Local model routing accuracy too low")
        print("DECISION REQUIRED:")
        print("  Option 1: Switch to quantized 70B model")
        print("  Option 2: Route more queries to cloud")
        print("  Option 3: Add more few-shot examples")
    else:
        print("✅ Local model routing: PASSED")
```

### Test 2: BMAD Workflow Detection (WEEK 2)

```python
def test_bmad_detection():
    """
    Does Xochitl correctly detect BMAD projects?
    """
    # Create test BMAD project
    test_project = create_test_bmad_project()
    
    # Navigate to project
    os.chdir(test_project)
    
    # Ask Xochitl to detect
    result = xochitl.detect_bmad_project(Path.cwd())
    
    assert result is not None, "Failed to detect BMAD project"
    assert 'BMM' in result['modules'], "Failed to detect BMM module"
    assert len(result['workflows']) > 0, "No workflows detected"
    
    print("✅ BMAD detection: PASSED")
```

### Test 3: Context Compression Efficiency (WEEK 3)

```python
def test_context_compression():
    """
    Does compression reduce tokens by >90%?
    """
    # Generate large conversation history
    large_conversation = generate_test_conversation(messages=100, avg_tokens=200)
    # Total: ~20k tokens
    
    # Compress for cloud routing
    compressed = context_compressor.compress("help me with X", large_conversation)
    
    original_tokens = count_tokens(large_conversation)
    compressed_tokens = count_tokens(compressed)
    
    reduction = (1 - compressed_tokens / original_tokens) * 100
    
    assert reduction > 90, f"Only {reduction}% compression (target: >90%)"
    assert compressed_tokens < 2000, f"Compressed size {compressed_tokens} (target: <2000)"
    
    print(f"✅ Context compression: {reduction:.1f}% reduction")
```

### Test 4: Vector DB Performance (WEEK 3)

```python
def test_vector_db_scale():
    """
    Can ChromaDB handle 10k+ memories efficiently?
    """
    # Insert 10k test memories
    for i in range(10000):
        vector_db.memorize(
            topic=f"test_topic_{i}",
            summary=f"Test memory {i} about various topics",
            tags=['test']
        )
    
    # Test retrieval speed
    start = time.time()
    results = vector_db.recall("test_topic_5000")
    elapsed = time.time() - start
    
    assert elapsed < 1.0, f"Recall too slow: {elapsed}s (target: <1s)"
    assert len(results) > 0, "No results returned"
    
    print(f"✅ Vector DB at scale: {elapsed*1000:.0f}ms for 10k memories")
```

### Test 5: Remote Access Reliability (WEEK 5)

```python
def test_remote_access():
    """
    Can laptop connect to desktop reliably?
    """
    # From laptop terminal
    result = subprocess.run(
        ['openclaw', 'agent', '--host', '<desktop-tailscale-ip>'],
        timeout=10,
        capture_output=True
    )
    
    assert result.returncode == 0, "Connection failed"
    assert "Xochitl" in result.stdout.decode(), "Wrong agent connected"
    
    print("✅ Remote access: PASSED")
```

### Test 6: Token Cost Reality Check (WEEK 4)

```python
def test_actual_token_costs():
    """
    Measure real-world token usage over 1 week of simulated use
    """
    # Simulate typical usage pattern
    daily_queries = [
        # Morning: 5 simple task queries (local)
        *["show my tasks"] * 5,
        
        # Midday: 3 complex queries (cloud)
        "help me design this API architecture",
        "review this 500-line code file",
        "create a PRD for new feature X",
        
        # Evening: 2 memory recalls (local)
        "what did we decide about Y?",
        "remember I prefer Z style"
    ]
    
    total_cloud_tokens = 0
    total_cost = 0
    
    for day in range(7):
        for query in daily_queries:
            route = router.route(query)
            if route.is_cloud:
                total_cloud_tokens += route.tokens_used
                total_cost += route.cost
    
    print(f"📊 7-Day Simulation Results:")
    print(f"   Cloud tokens: {total_cloud_tokens:,}")
    print(f"   Estimated cost: ${total_cost:.2f}")
    print(f"   Daily average: ${total_cost/7:.2f}")
    
    # Sanity check: Should be <$5/week for typical usage
    assert total_cost < 5.00, f"Weekly cost too high: ${total_cost}"
```

---

## Code Examples

### Complete Router Implementation

```python
# xochitl/routing.py

from typing import Union, Optional
from enum import Enum
import anthropic
import ollama

class RouteType(Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    BMAD = "bmad"
    HYBRID = "hybrid"

class XochitlRouter:
    """
    Main routing logic for Xochitl
    """
    
    def __init__(self, config: dict):
        self.local_model = ollama.Client()
        self.cloud_client = anthropic.Anthropic(api_key=config['anthropic_api_key'])
        self.context_compressor = ContextCompressor()
        self.token_budget = TokenBudget(daily_budget=100000)
        self.bmad_detector = BMADDetector()
        
    def route(self, query: str, context: dict) -> Response:
        """
        Main routing decision tree
        """
        # Step 1: Check if in BMAD project
        bmad_project = self.bmad_detector.detect_bmad_project(Path.cwd())
        
        # Step 2: Classify query
        category = self._classify_query(query, context, bmad_project)
        
        # Step 3: Route based on category
        if category.startswith('bmad_'):
            return self._route_bmad(category, query, context, bmad_project)
        elif category in ['simple_qa', 'task_management', 'file_operations']:
            return self._route_local(query, context)
        elif category in ['code_generation', 'architecture_planning']:
            return self._route_cloud(query, context)
        else:
            # Hybrid: try local first
            return self._route_hybrid(query, context)
    
    def _route_local(self, query: str, context: dict) -> Response:
        """
        Execute on local model
        """
        response = self.local_model.chat(
            model='llama3.1:8b-instruct-q6_K',
            messages=[
                {'role': 'system', 'content': self._build_system_prompt()},
                {'role': 'user', 'content': query}
            ]
        )
        
        return Response(
            content=response['message']['content'],
            route_type=RouteType.LOCAL,
            tokens_used=0,  # Local = free
            cost=0.0
        )
    
    def _route_cloud(self, query: str, context: dict) -> Response:
        """
        Execute on cloud model with context compression
        """
        # Compress context
        compressed = self.context_compressor.compress(query, context)
        
        # Check token budget
        estimated_tokens = len(compressed.split()) * 1.3  # Rough estimate
        if not self.token_budget.check_budget(int(estimated_tokens)):
            return Response(
                content="Token budget exceeded. Use local mode or wait until tomorrow.",
                route_type=RouteType.CLOUD,
                tokens_used=0,
                cost=0.0
            )
        
        # Call Claude
        message = self.cloud_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": compressed}
            ]
        )
        
        # Record usage
        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        cost = (message.usage.input_tokens * 0.003 / 1000) + \
               (message.usage.output_tokens * 0.015 / 1000)  # Sonnet pricing
        
        self.token_budget.record_usage(tokens_used)
        
        return Response(
            content=message.content[0].text,
            route_type=RouteType.CLOUD,
            tokens_used=tokens_used,
            cost=cost
        )
    
    def _route_bmad(
        self, 
        workflow_category: str, 
        query: str, 
        context: dict,
        bmad_project: dict
    ) -> Response:
        """
        Execute BMAD workflow
        """
        # Load workflow prompt
        workflow_name = workflow_category.replace('bmad_', '')
        workflow_prompt = self._load_bmad_workflow(bmad_project, workflow_name)
        
        # Augment with context
        full_prompt = self._merge_bmad_context(workflow_prompt, context)
        
        # Route based on complexity
        if workflow_category == 'bmad_simple':
            return self._route_local(full_prompt, context)
        else:
            return self._route_cloud(full_prompt, context)
    
    def _build_system_prompt(self) -> str:
        """
        Constructs system prompt with MEMORY.md
        """
        memory = Path.home() / ".xochitl/MEMORY.md"
        
        if memory.exists():
            memory_content = memory.read_text()
        else:
            memory_content = "# MEMORY.md\n\nNo preferences set yet."
        
        return f"""
You are Xochitl, a terminal-native AI Chief of Staff. You are helpful, efficient, and speak with personality.

{memory_content}

Remember:
- Keep responses concise unless detail is requested
- Always provide file paths as clickable links
- Suggest tools proactively when users are stuck
- Use BMAD workflows when in BMAD projects
"""
```

### MEMORY.md Manager

```python
# xochitl/memory.py

class MemoryManager:
    """
    Manages MEMORY.md with versioning and conflict resolution
    """
    
    def __init__(self, memory_path: Path):
        self.path = memory_path
        self.max_tokens = 2000
        self.git_repo = self._init_git()
    
    def update(self, section: str, content: str, user_confirmed: bool = False):
        """
        Update a section of MEMORY.md
        """
        current = self.read()
        
        # Check for conflicts
        if section in current and not user_confirmed:
            if self._has_conflict(current[section], content):
                # Ask for confirmation
                raise ConflictDetected(
                    f"Conflicting preference detected in {section}.\n"
                    f"Old: {current[section]}\n"
                    f"New: {content}\n"
                    f"Confirm update?"
                )
        
        # Update section
        current[section] = content
        
        # Check size
        if self._estimate_tokens(current) > self.max_tokens:
            current = self._auto_summarize(current)
        
        # Write and commit
        self.write(current)
        self._git_commit(f"Updated {section}")
    
    def _auto_summarize(self, memory: dict) -> dict:
        """
        Summarize old content to free space
        """
        # Identify least-recently-used sections
        old_sections = self._get_old_sections(memory)
        
        # Summarize them
        for section in old_sections:
            summary = self._summarize_section(memory[section])
            memory[section] = f"[Summarized] {summary}"
        
        return memory
    
    def _git_commit(self, message: str):
        """
        Version control for rollback
        """
        subprocess.run(['git', '-C', self.path.parent, 'add', 'MEMORY.md'])
        subprocess.run(['git', '-C', self.path.parent, 'commit', '-m', message])
    
    def rollback(self, version: int = 1):
        """
        Rollback to previous version
        """
        subprocess.run([
            'git', '-C', self.path.parent, 
            'checkout', f'HEAD~{version}', 'MEMORY.md'
        ])
```

---

## Summary & Next Steps

### Key Takeaways

1. **BMAD is a prompt framework, not a separate agent** - Integration is simpler than originally planned
2. **Local model choice is critical** - Test orchestration capabilities in Week 1
3. **Memory system needs structure** - Three-tier architecture with eviction policies
4. **Security cannot be an afterthought** - Implement sandboxing from day 1
5. **Context compression is essential** - 90%+ reduction in cloud token usage

### Immediate Action Items

**This Week:**
1. ✅ Install Ollama and test Llama 3.1 8B orchestration
2. ✅ Run critical routing tests (target >85% accuracy)
3. ✅ Set up basic project structure
4. ✅ Create initial MEMORY.md schema

**Next Week:**
1. ✅ Implement MCP filesystem server with restrictions
2. ✅ Build BMAD project detector
3. ✅ Create file generation system
4. ✅ Test end-to-end workflow

**Month 1 Goal:**
Have Phase 1 MVP working - basic Xochitl that can chat, manage tasks, and save files correctly.

### Decision Points

**Week 1:** If local model routing accuracy < 85%
- **Option A:** Switch to Llama 3.1 70B Q4 (if RAM allows)
- **Option B:** Route more queries to cloud (increase costs but maintain UX)
- **Option C:** Add extensive few-shot examples to system prompt

**Week 3:** After vector DB stress testing
- **Option A:** ChromaDB performs well → proceed
- **Option B:** ChromaDB too slow → switch to LanceDB or Qdrant

**Week 5:** After remote access testing
- **Option A:** Tailscale works reliably → production ready
- **Option B:** Connectivity issues → implement retry logic or alternative

---

**Document End**

*This architecture guide is a living document. Update as implementation proceeds and new insights emerge.*

**Version History:**
- v1.0 (2026-04-29): Initial comprehensive architecture
