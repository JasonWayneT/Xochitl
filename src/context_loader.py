"""Builds 3-layer LLM context and compresses conversation history for cloud routing."""

import re
import json
from pathlib import Path
from typing import Optional

GLOBAL_CONTEXT_PATH = Path(__file__).parent.parent / "config" / "global.md"
PROJECTS_CONTEXT_DIR = Path(__file__).parent.parent / "config" / "projects"


# ── 3-layer context assembly ──────────────────────────────────────────────────

def load_global_context() -> str:
    if GLOBAL_CONTEXT_PATH.exists():
        return GLOBAL_CONTEXT_PATH.read_text(encoding="utf-8")
    return ""


def load_project_context(project_name: str) -> str:
    slug = project_name.lower().replace(" ", "_")
    candidates = [
        PROJECTS_CONTEXT_DIR / f"{slug}.md",
        PROJECTS_CONTEXT_DIR / f"{project_name}.md",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def build_decompose_context(project_name: str) -> tuple[str, str]:
    """Returns (global_context, project_context) for the DECOMPOSE_PROMPT."""
    return load_global_context(), load_project_context(project_name)


def build_system_prompt(memory_content: str, soul_content: str = "") -> str:
    from src.memory import read_memory
    memory = memory_content or read_memory()

    soul_path = Path(__file__).parent.parent / "SOUL.md"
    soul = soul_content or (soul_path.read_text(encoding="utf-8") if soul_path.exists() else "")

    project_root = Path(__file__).parent.parent.resolve()

    return f"""{soul}

---

{memory}

---

## Runtime Location
- My project root: `{project_root}`
- I can read files and folders anywhere under `{Path.home()}` (except .ssh, .aws, system dirs)
- When asked "what path are you at" or similar, answer with the project root above

---

## Tool Routing Examples
Query: "mark task 1 done" → task_management
Query: "what did we discuss about JobAgent?" → vector_db_recall
Query: "help me plan this feature" → bmad_workflow
Query: "sync Notion tasks" → notion_sync
Query: "design the database schema" → cloud_expert
Query: "read file main.py" → file_read
Query: "what can you do?" → xochitl_help
"""


# ── Context compression for cloud routing ─────────────────────────────────────

def compress_context(
    query: str,
    conversation_history: list[dict],
    current_task: Optional[str] = None,
    memory_sections: Optional[str] = None,
    bmad_context: Optional[str] = None,
) -> str:
    """Reduces a long conversation history to a dense 2k-token context packet."""

    recent = conversation_history[-5:]
    older = conversation_history[:-5]

    recent_files = _extract_file_references(recent)
    history_summary = _summarize_older_history(older)

    parts = []

    if current_task:
        parts.append(f"# Current Task\n{current_task}")

    if memory_sections:
        parts.append(f"# Relevant Memory\n{memory_sections}")

    if history_summary:
        parts.append(f"# Conversation Summary\n{history_summary}")

    if recent_files:
        parts.append(f"# Referenced Files\n{recent_files}")

    if bmad_context:
        parts.append(f"# BMAD Project Context\n{bmad_context}")

    # Always include the last 3 exchanges verbatim
    if recent:
        recent_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in recent[-3:]
        )
        parts.append(f"# Recent Exchange\n{recent_text}")

    parts.append(f"# Current Query\n{query}")

    return "\n\n".join(parts)


def _extract_file_references(messages: list[dict]) -> str:
    file_paths = []
    for msg in messages:
        content = msg.get("content", "")
        # Match Unix and Windows file paths with extensions
        found = re.findall(r'[A-Za-z]?:?[/\\][\w/\\.:-]+\.\w+', content)
        file_paths.extend(found)

    contents = []
    seen = set()
    for raw_path in file_paths:
        if raw_path in seen:
            continue
        seen.add(raw_path)
        try:
            p = Path(raw_path)
            if p.exists() and p.is_file():
                text = p.read_text(encoding="utf-8", errors="ignore")
                contents.append(f"## {raw_path}\n{text[:3000]}")
        except Exception:
            continue

    return "\n\n".join(contents)


def _summarize_older_history(messages: list[dict]) -> str:
    if not messages:
        return ""

    # Heuristic bullet-point summary without an LLM call
    # (real summarization happens via local model in router.py)
    bullets = []
    for msg in messages[-10:]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if len(content) > 120:
            content = content[:117] + "..."
        bullets.append(f"- [{role}] {content}")

    return "\n".join(bullets)
