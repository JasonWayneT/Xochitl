"""Builds LLM context, verifies memory entries on use, and compresses conversation history."""
# Implements FR-MEM-007 (Verify-on-Call Protocol — hash check before LLM injection)

import hashlib
import json
import re
from pathlib import Path
from typing import Optional

GLOBAL_CONTEXT_PATH = Path(__file__).parent.parent / "config" / "global.md"
PROJECTS_CONTEXT_DIR = Path(__file__).parent.parent / "config" / "projects"
PROJECT_ROOT = Path(__file__).parent.parent


def _first_existing(paths: list[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def load_soul_text() -> str:
    """Load Xochitl's persona from project, user, or repo example paths."""
    path = _first_existing([
        Path.cwd() / ".xochitl" / "SOUL.md",
        Path.home() / ".xochitl" / "SOUL.md",
        PROJECT_ROOT / "SOUL.md.example",
    ])
    return path.read_text(encoding="utf-8") if path else ""


# ── FR-MEM-007: Verify-on-Call Protocol ──────────────────────────────────────

def verify_on_call(entry: dict) -> tuple[str, bool]:
    """Re-read and hash-verify a KB entry before LLM injection.

    Implements FR-MEM-007 — prevents stale or tampered entries from reaching the model.
    Returns (content, is_valid). If hash mismatch, content is prefixed with [STALE].
    """
    # Implements FR-MEM-007
    path_str = entry.get("path")
    if not path_str:
        return entry.get("content", ""), True

    path = Path(path_str)
    if not path.exists():
        return "", False

    try:
        current_content = path.read_text(encoding="utf-8")
    except Exception:
        return "", False

    current_hash = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
    hashes_file = path.parent / ".hashes.json"

    if hashes_file.exists():
        try:
            hashes = json.loads(hashes_file.read_text(encoding="utf-8"))
            stored_hash = hashes.get(path.name)
            if stored_hash and stored_hash != current_hash:
                return f"[STALE] {current_content[:500]}", False
        except Exception:
            pass

    return current_content, True


# ── Context assembly ──────────────────────────────────────────────────────────

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

    soul = soul_content or load_soul_text()  # Implements FR-UX-002

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

## Language
Always respond in English or Spanish only. Never use any other language unless the
user explicitly asks you to respond in a different language for that message.

## Important
You are a conversational assistant. Respond naturally in plain text or markdown.
Do NOT output XML tags, tool-call syntax, JSON function calls, any structured
markup that looks like code execution. If you need to perform an action, describe
what you are doing in plain language. The calling code handles all tool dispatch.
"""


# ── Context compression for cloud routing ─────────────────────────────────────

_LOCAL_HISTORY_KEEP = 10  # messages to keep verbatim; older ones become a summary block


def trim_history_for_local(history: list[dict], keep: int = _LOCAL_HISTORY_KEEP) -> list[dict]:
    """Keep the most recent `keep` messages verbatim; summarize older ones as a context block.

    Prevents local model context overflow on long sessions. Uses the same heuristic
    bullet summarizer as compress_context so no extra LLM call is needed before the
    actual routing call.
    """
    if len(history) <= keep:
        return history

    older = history[:-keep]
    recent = history[-keep:]

    summary = _summarize_older_history(older)
    if not summary:
        return recent

    return [
        {
            "role": "user",
            "content": f"[Earlier conversation — {len(older)} messages]\n{summary}",
        },
        {
            "role": "assistant",
            "content": "Understood, I have context from our earlier conversation.",
        },
    ] + recent


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
