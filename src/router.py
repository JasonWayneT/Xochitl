"""Tiered router: classifies queries and dispatches to local model, cloud, or BMAD."""
# Implements FR-ORCH-002 (Dynamic Skill Invocation — route() dispatches to local/cloud/hybrid based on intent)
# Implements FR-ORCH-003 (PreFlight Fact Injection — SYSTEM_FACTS block prepended to every prompt)
# Implements NFR-PERF-003 (Intent routing latency < 500ms)
# Implements NFR-PERF-005 (Rolling latency tracking per provider)

import os
import re
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.llm_interface import (
    LLMResponse, RouteType,
    call_local, call_cloud, call_with_retry,
    estimate_confidence, CLOUD_MODEL,
    CLOUD_MODEL_PRO, CLOUD_MODEL_FLASH, ROUTER_MODEL
)
from src.model_manager import select_model
from src.context_loader import build_system_prompt, compress_context
from src.memory import read_memory
from src.config import get_confidence_threshold
from src import database as db


_PROJECT_ROOT = Path(__file__).parent.parent

# Phrases that mean "your own directory" without naming an explicit path
_SELF_DIR_PHRASES = [
    "your directory", "your folder", "your files", "the directory you're in",
    "the directory you are in", "the folder you're in", "the folder you are in",
    "this directory", "this folder", "current directory", "current folder",
    "read through the folder", "read through the directory", "read through the files",
    "look through the folder", "look through the directory", "browse the folder",
    "browse the directory", "what's in your folder", "whats in your folder",
    "what files do you have", "what's in your directory", "whats in your directory",
    "the directory i opened", "the folder i opened", "directory you opened",
    "files in the directory", "files in the folder", "files in your directory",
    "read the files", "show me the files", "what files are", "files do you see",
    "read all files", "look at all files", "look at your files",
    "what folder are you in", "what directory are you in", "where are you",
    "what folder is this", "what directory is this"
]


def _build_preflight_facts(project: str | None = None) -> str:
    """Build a [SYSTEM_FACTS] block with hard environment facts.

    Implements FR-ORCH-003 — PreFlight Fact Injection.
    Prepended to every system prompt so the LLM cannot hallucinate its location.
    """
    cwd = str(Path.cwd())
    project_line = f"Active Project: {project}" if project else "Active Project: none"
    try:
        wip_count = 0
        from src import database as _db
        with _db.get_connection() as _conn:
            _wip = _db.get_queue(_conn)
        wip_count = len(_wip)
    except Exception:
        wip_count = 0
    return (
        f"[SYSTEM_FACTS]\n"
        f"Current Directory: {cwd}\n"
        f"{project_line}\n"
        f"WIP Queue: {wip_count}/3 items\n"
        f"Platform: Windows (win32)\n"
        f"[/SYSTEM_FACTS]"
    )


def _dir_tree(root: Path, depth: int = 2, _indent: int = 0) -> list[str]:
    """Return an indented tree of a directory up to `depth` levels."""
    lines = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return lines
    for entry in entries:
        if entry.name.startswith(".") and entry.name not in (".env",):
            continue
        prefix = "  " * _indent
        if entry.is_dir():
            lines.append(f"{prefix}{entry.name}/")
            if _indent < depth - 1:
                lines.extend(_dir_tree(entry, depth, _indent + 1))
        else:
            lines.append(f"{prefix}{entry.name}")
    return lines


def _resolve_file_context(query: str, history: list[dict] | None = None) -> str:
    """
    Find files or folders mentioned in the query (or recent history) and return
    their content for prompt injection.
    """
    import re
    from src import security

    q_lower = query.lower()
    combined_query = query
    if history:
        # Scan last 3 messages for context-dropping prevention (BUG-ORCH-001)
        recent = [m.get("content", "") for m in history[-3:]]
        combined_query = "\n".join(recent + [query])
        q_lower = combined_query.lower()

    parts = []

    # ── Self-referential directory browse ────────────────────────────────────
    if any(phrase in q_lower for phrase in _SELF_DIR_PHRASES) or re.search(r'\b(?:what|show|list|where|see|read|view|browse|look|check)\b.*\b(?:folder|dir|directory|files|path)\b', q_lower):
        cwd = Path.cwd()
        tree = _dir_tree(cwd, depth=2)
        parts.append(
            f"## Your current working directory: {cwd}\n" + "\n".join(tree)
        )
        # Also check if they want file contents (e.g. "read through the files")
        read_words = ["read", "look at", "show me", "open", "browse"]
        if not any(w in q_lower for w in read_words):
            return "## File Context\n\n" + "\n\n".join(parts)

    # ── Explicit Windows absolute paths ──────────────────────────────────────
    explicit = re.findall(r'[A-Za-z]:[/\\][\w/\\\-. ]+', combined_query)

    # ── Filenames with known extensions ──────────────────────────────────────
    ext_pattern = r'[\w][\w\-]*\.(?:md|txt|py|js|ts|json|yaml|yml|toml|csv|html|pdf|env)'
    bare_names = re.findall(ext_pattern, combined_query, re.IGNORECASE)

    # ── Quoted strings (may be filenames or folder names) ────────────────────
    quoted = [m[0] or m[1] for m in re.findall(r'"([^"]+)"|\'([^\']+)\'', combined_query)]

    # ── Potential named folders (words in the query that might be directories) ──
    # BUG-ORCH-003: find folders like 'zettlelib' even if not quoted.
    potential_names = re.findall(r'\b\w{3,}\b', query)

    search_roots = [
        Path.cwd(),
        _PROJECT_ROOT,
        Path.home() / "Desktop" / "Jason" / "Resource" / "CodeProjects",
        Path.home() / "Documents",
        Path.home() / "Desktop",
    ]

    def _find_by_name(name: str) -> Optional[Path]:
        name_clean = name.strip().lower()
        # 1. Fast check: immediate children of search roots
        for root in search_roots:
            if not root.exists():
                continue
            # Check immediate children first (O(N) where N is number of files in root)
            try:
                for p in root.iterdir():
                    if name_clean in p.name.lower() and security._is_allowed(p):
                        return p
            except PermissionError:
                continue

        # 2. Limited depth search (O(N^2) but restricted)
        for root in search_roots:
            if not root.exists():
                continue
            try:
                # Only look 2 levels deep to avoid the "rglob hang"
                for p in root.glob("*/*"):
                    if name_clean in p.name.lower() and security._is_allowed(p):
                        return p
            except PermissionError:
                continue
        return None

    resolved_files: set[Path] = set()
    resolved_dirs: set[Path] = set()

    for raw in explicit + bare_names + quoted + potential_names:
        raw = raw.strip()
        if not raw or raw.lower() in {"the", "and", "read", "folder", "directory", "file"}:
            continue
        # Try as absolute path
        p = Path(raw)
        if p.exists():
            if p.is_file() and security._is_allowed(p):
                resolved_files.add(p)
            elif p.is_dir() and security._is_allowed(p):
                resolved_dirs.add(p)
            continue
        # Try relative to project root
        rel = _PROJECT_ROOT / raw
        if rel.exists():
            if rel.is_file() and security._is_allowed(rel):
                resolved_files.add(rel)
            elif rel.is_dir() and security._is_allowed(rel):
                resolved_dirs.add(rel)
            continue
        # Fuzzy name search (files and directories)
        found = _find_by_name(raw)
        if found:
            if found.is_dir():
                resolved_dirs.add(found)
            else:
                resolved_files.add(found)

    # Directory listings
    for d in sorted(resolved_dirs):
        tree = _dir_tree(d, depth=2)
        parts.append(f"## Directory: {d}\n" + "\n".join(tree))

    # File contents
    for path in sorted(resolved_files):
        try:
            content = security.read_file(path)
            if len(content) > 10_000:
                content = content[:10_000] + f"\n\n[truncated — {len(content)} chars total]"
            parts.append(f"## {path.name} ({path})\n```\n{content}\n```")
        except Exception:
            pass

    if not parts:
        return ""

    return "## File Context\n\n" + "\n\n".join(parts)


def _live_db_context() -> str:
    """Return a text snapshot of current projects and queue for injection into prompts."""
    lines = []
    try:
        with db.get_connection() as conn:
            projects = conn.execute(
                "SELECT name, priority, status, description FROM projects WHERE status='active' ORDER BY priority DESC"
            ).fetchall()
            if projects:
                lines.append("## Active Projects (from local database)")
                for p in projects:
                    desc = (p["description"] or "")[:80]
                    lines.append(f"  [{p['priority'].upper()}] {p['name']} — {desc}")
            else:
                lines.append("## Active Projects\n  (none — run `xochitl pull` to sync from Notion)")

            queue = conn.execute("""
                SELECT t.description, t.time_estimate_minutes, p.name as project_name, q.position
                FROM queue q
                JOIN tasks t ON q.task_id = t.id
                JOIN projects p ON t.project_id = p.id
                ORDER BY q.position
            """).fetchall()
            if queue:
                lines.append("\n## Current WIP Queue")
                for r in queue:
                    lines.append(f"  [{r['position']}] {r['description']} ({r['time_estimate_minutes']}m | {r['project_name']})")
            else:
                lines.append("\n## Current WIP Queue\n  (empty — run `xochitl today` to fill)")
    except Exception as e:
        lines.append(f"## DB unavailable: {e}")
    return "\n".join(lines)

# Categories that stay local vs go to cloud
_LOCAL_CATEGORIES = {
    "simple_qa", "task_management", "file_operations",
    "memory_recall", "xochitl_help", "bmad_simple",
}

# Categories that use specialized local models before cloud fallback.
# Values are model_manager roles — select_model() resolves to the right
# model tag at call time based on available VRAM.
_LOCAL_SPECIALIZED_CATEGORIES = {
    "code_generation":    "coding",
    "code_review":        "coding",
    "architecture_planning": "thinking",
    "bmad_complex":       "thinking",
    "zettelkasten_mode":  "thinking",
}

_CLOUD_CATEGORIES = {
    "creative_writing", "data_analysis", "bmad_party_mode",
}

# Categories that MUST stay local (never fall back to cloud automatically)
# BUG-ORCH-007: bmad_simple added — file+BMAD combined requests were hitting cloud quota (429)
_FORCE_LOCAL_CATEGORIES = {
    "file_operations", "task_management", "xochitl_help",
    "memory_recall", "simple_qa", "bmad_simple", "zettelkasten_mode",
}

_CLASSIFICATION_PROMPT = """Classify the user query into EXACTLY ONE category from this list:

simple_qa          - Factual question, definition, general explanation
task_management    - Mark task done, show tasks, update task status
file_operations    - Read, write, or list files
memory_recall      - "What did we discuss about X?" or recall past conversations
xochitl_help       - "What can you do?" or capability introspection
code_generation    - Write code, create scripts, implement features
architecture_planning - Design systems, plan architecture, database schemas
creative_writing   - Write posts, draft emails, create content
data_analysis      - Analyse data, create reports, statistics
bmad_simple        - bmad-help, bug fix planning, simple BMAD tasks
bmad_complex       - BMAD architecture, PRD creation, sprint planning
bmad_party_mode    - Start party mode, multi-agent BMAD session
code_review        - Review code, check for bugs
zettelkasten_mode  - Initiate, scaffold, or work with a Zettelkasten vault or notes

Query: {query}

Respond with EXACTLY this format: <category>|<confidence>
The confidence is a decimal between 0.0 and 1.0 reflecting how certain you are.
Example: task_management|0.92
No other text."""

_ALL_CATEGORIES = (
    set(_LOCAL_CATEGORIES)
    | set(_LOCAL_SPECIALIZED_CATEGORIES)
    | set(_CLOUD_CATEGORIES)
)


_KEYWORD_MAP = {
    # file_operations first — extensions are unambiguous and must win over keywords like "project"
    "file_operations":  [
        ".md", ".txt", ".py", ".js", ".ts", ".json", ".yaml", ".pdf", ".env", ".toml", ".csv",
        "read the file", "read file", "read the files", "read all the files",
        "open the file", "look at the file", "can you see", "do you see",
        "show me the file", "what's in the file", "whats in the file",
        "list files", "list directory", "list folder", "show files",
        "check the file", "find the file", "load the file",
        "files in the", "folder contents", "directory contents",
        "look at the folder", "look at the directory", "see the folder",
        "read through", "read my files", "see my files",
    ],
    # bmad before task_management — "run through bmad" must not route to task mgmt
    "bmad_simple":      [
        "bmad", "b-mad", "sdd", "spec driven", "run it through", "run through bmad",
        "bmad method", "bmad workflow", "bmad skill", "create a prd", "write a prd",
        "create epics", "create stories", "sprint planning", "bmad help",
        "bmad agent", "intake", "product brief", "feature spec", "create spec",
    ],
    "bmad_complex":     [
        "full bmad", "full sdd", "create architecture", "create the architecture",
        "architecture spec", "design spec", "traceability matrix", "requirements registry",
    ],
    "bmad_party_mode":  ["party mode", "multi-agent", "roundtable", "agent discussion"],
    "simple_qa":        ["hello", "hi", "hey", "hola", "good morning", "good afternoon", "good evening", "sup", "what's up", "whats up"],
    "task_management":  ["done", "queue", "task", "today", "mark", "complete", "blocked", "in progress", "my work"],
    "xochitl_help":     ["help", "what can you", "capabilities", "commands"],
    "memory_recall":    ["remember", "recall", "what did we", "earlier", "last time"],
    "code_generation":  ["write code", "implement", "create a script", "function that"],
    "code_review":      ["review", "check this code", "bug in"],
    "zettelkasten_mode": [
        "zettelkasten", "zettel", "zettle", "zettl", "vault", "fleeting note",
        "permanent note", "literature note", "scaffold vault", "initiate a zettle",
        "initiate zettel", "open zettelkasten", "zettle project", "zettle vault",
        "zettelkasten project", "zettelkasten vault",
    ],
}

_ZETTEL_RE = re.compile(
    r'\bzettel(?:kasten)?\b|\bzettle\b|\bzettl\b|'
    r'\bfleeting note\b|\bpermanent note\b|\bliterature note\b|'
    r'\bscaffold vault\b|\bzettle (?:project|vault)\b|\bzettelkasten (?:project|vault)\b',
    re.IGNORECASE,
)


def _fast_classify(query: str) -> Optional[tuple[str, float]]:
    """Keyword-based classification — always returns confidence 1.0 on match."""
    q = query.lower()
    # Zettelkasten check first — a path like C:\Vaults\... must not override zettel intent
    if _ZETTEL_RE.search(query):
        return "zettelkasten_mode", 1.0
    # Bare absolute path (Windows or Unix) → file operation
    if re.search(r'^[a-z]:[/\\]|^/(?:home|users|tmp|var|etc)/', q.strip()):
        return "file_operations", 1.0
    # Any self-referential directory phrase → file operation
    if any(phrase in q for phrase in _SELF_DIR_PHRASES):
        return "file_operations", 1.0
    # Fuzzy self-ref match: (what|show|list|see|read|view|browse|look|check) ... (folder|dir|files)
    if re.search(r'\b(?:what|show|list|where|see|read|view|browse|look|check)\b.*\b(?:folder|dir|directory|files|path)\b', q):
        return "file_operations", 1.0
    # Top-priority BMAD check — before task_management so "run through bmad" never hijacked
    if re.search(r'\bbmad\b|\bsdd\b|spec.driven|run.*through.*bmad|bmad.*method|bmad.*workflow', q):
        # Distinguish complex from simple based on depth keywords
        if any(w in q for w in ["architecture", "traceability", "design spec", "full bmad", "full sdd"]):
            return "bmad_complex", 1.0
        if any(w in q for w in ["party", "multi-agent", "roundtable"]):
            return "bmad_party_mode", 1.0
        return "bmad_simple", 1.0
    for category, keywords in _KEYWORD_MAP.items():
        for kw in keywords:
            if len(kw) <= 4 and kw.isalpha():
                if re.search(r'\b' + re.escape(kw) + r'\b', q):
                    return category, 1.0
            elif kw in q:
                return category, 1.0
    return None


def _parse_classification(raw: str) -> tuple[str, float]:
    """Parse 'category|confidence' from router model response. Robust to noisy output."""
    text = raw.strip().lower().replace("-", "_")

    confidence = 0.5
    if "|" in text:
        parts = text.split("|", 1)
        raw_cat = parts[0].strip().split()[-1]  # last word handles any leading filler
        try:
            confidence = max(0.0, min(1.0, float(parts[1].strip().split()[0])))
        except (ValueError, IndexError):
            confidence = 0.5
    else:
        raw_cat = text.split()[0] if text.split() else "simple_qa"
        confidence = 0.5

    # Validate and fuzzy-match to known categories
    if raw_cat in _ALL_CATEGORIES:
        return raw_cat, confidence

    for cat in _ALL_CATEGORIES:
        if raw_cat in cat or cat in raw_cat:
            return cat, confidence

    return "simple_qa", 0.3


class TieredRouter:
    def __init__(self):
        self._consecutive_local_failures = 0
        self._failure_threshold = 2
        # NFR-PERF-005: rolling latency tracking (exponential moving average)
        self._local_avg_ms: float = 9999.0
        self._cloud_avg_ms: float = 9999.0

    def _update_latency(self, route: str, duration_ms: float) -> None:
        """Exponential moving average update for latency tracking."""
        alpha = 0.3
        if route == "local":
            self._local_avg_ms = alpha * duration_ms + (1 - alpha) * self._local_avg_ms
        else:
            self._cloud_avg_ms = alpha * duration_ms + (1 - alpha) * self._cloud_avg_ms

    def route(
        self,
        query: str,
        conversation_history: list[dict],
        system_prompt: str = "",
        current_task: Optional[str] = None,
        bmad_context: Optional[str] = None,
        force_route: Optional[str] = None,
    ) -> LLMResponse:
        # Implements FR-ORCH-001 (intent classification with 85% confidence gate)
        # Implements NFR-PERF-003 (intent routing < 500ms — fast_classify is O(1))
        if not system_prompt:
            system_prompt = build_system_prompt(read_memory())

        if force_route:
            category, confidence = force_route, 1.0
        else:
            # Single LLM-based classification — eliminates the keyword/LLM conflict
            # that occurred when _fast_classify (confidence always 1.0) overrode
            # the LLM classifier's result. ContextManager already injects SYSTEM_FACTS
            # and file context via FactsEngine / FileContextEngine, so we do not
            # duplicate those injections here.
            category, confidence = self._classify(query)

        threshold = get_confidence_threshold()
        if confidence < threshold:
            return LLMResponse(
                content=(
                    f"Fíjate, I wasn't sure how to interpret that — I read it as "
                    f"*{category.replace('_', ' ')}* ({confidence:.0%} confident), "
                    f"which is below my {threshold:.0%} threshold.\n\n"
                    f"Could you say more about what you'd like help with?"
                ),
                route=RouteType.LOCAL,
            )

        # Inject live DB snapshot for task/project-data queries.
        # (SYSTEM_FACTS and file context are already in system_prompt via ContextManager.)
        if category in {"task_management", "simple_qa", "memory_recall"}:
            system_prompt = system_prompt + "\n\n" + _live_db_context()

        if category in _LOCAL_CATEGORIES:
            return self._route_local(
                query, conversation_history, system_prompt,
                model=select_model("general"), category=category,
            )
        elif category in _LOCAL_SPECIALIZED_CATEGORIES:
            model = select_model(_LOCAL_SPECIALIZED_CATEGORIES[category])
            return self._route_hybrid(
                query, conversation_history, system_prompt,
                category=category, current_task=current_task,
                bmad_context=bmad_context, model=model
            )
        elif category in _CLOUD_CATEGORIES:
            return self._route_cloud(
                query, conversation_history, system_prompt,
                category=category, current_task=current_task, bmad_context=bmad_context
            )
        else:
            # Hybrid: try local, fall back if confidence low
            return self._route_hybrid(
                query, conversation_history, system_prompt,
                category=category, current_task=current_task, bmad_context=bmad_context
            )

    def _classify(self, query: str) -> tuple[str, float]:
        """Implements FR-ORCH-001 — returns (category, confidence) from router model."""
        prompt = _CLASSIFICATION_PROMPT.format(query=query)
        result = call_local(
            messages=[{"role": "user", "content": prompt}],
            model=ROUTER_MODEL,
        )
        if result.error:
            return "simple_qa", 0.0
        return _parse_classification(result.content)

    def _route_local(
        self,
        query: str,
        history: list[dict],
        system: str,
        model: str = "",
        category: str = "",
    ) -> LLMResponse:
        messages = history + [{"role": "user", "content": query}]
        t0 = time.monotonic()
        result = call_with_retry(call_local, messages=messages, system=system, model=model)
        elapsed_ms = (time.monotonic() - t0) * 1000

        if result.error:
            self._consecutive_local_failures += 1
            # BUG-ORCH-004 fix: don't fall back to cloud for local-first categories
            # if the error is a systemic failure (like Ollama being down).
            if category in _FORCE_LOCAL_CATEGORIES:
                return result

            if self._consecutive_local_failures >= self._failure_threshold:
                return self._route_cloud(query, history, system, category=category)
            return result

        self._consecutive_local_failures = 0
        self._update_latency("local", elapsed_ms)
        confidence = estimate_confidence(result.content)
        if confidence < 0.7 and category not in _FORCE_LOCAL_CATEGORIES:
            return self._route_cloud(query, history, system, category=category)

        return result

    def _route_cloud(
        self,
        query: str,
        history: list[dict],
        system: str,
        category: str = "",
        current_task: Optional[str] = None,
        bmad_context: Optional[str] = None,
    ) -> LLMResponse:
        from src.memory import read_memory
        compressed = compress_context(
            query=query,
            conversation_history=history,
            current_task=current_task,
            memory_sections=read_memory(),
            bmad_context=bmad_context,
        )

        heavy_tasks = {"code_generation", "architecture_planning", "bmad_complex", "code_review"}
        selected_model = CLOUD_MODEL_PRO if category in heavy_tasks else CLOUD_MODEL_FLASH

        messages = [{"role": "user", "content": compressed}]
        t0 = time.monotonic()
        result = call_with_retry(call_cloud, messages=messages, system=system, model=selected_model)
        elapsed_ms = (time.monotonic() - t0) * 1000

        if not result.error:
            self._update_latency("cloud", elapsed_ms)
            self._log_cloud_usage(result)

        return result

    def _route_hybrid(
        self,
        query: str,
        history: list[dict],
        system: str,
        category: str = "",
        model: str = "",
        **kwargs,
    ) -> LLMResponse:
        local_result = self._route_local(query, history, system, model=model, category=category)
        if local_result.error:
            return self._route_cloud(query, history, system, category=category, **kwargs)

        confidence = estimate_confidence(local_result.content)
        if confidence < 0.7:
            return self._route_cloud(query, history, system, category=category, **kwargs)

        return local_result

    def _log_cloud_usage(self, result: LLMResponse) -> None:
        try:
            with db.get_connection() as conn:
                db.record_token_usage(
                    conn,
                    route="cloud",
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    cost_usd=result.cost_usd,
                )
        except Exception:
            pass


# Module-level singleton
_router: Optional[TieredRouter] = None


def get_router() -> TieredRouter:
    global _router
    if _router is None:
        _router = TieredRouter()
    return _router
