"""3-tier memory system: MEMORY.md (active), SQLite sessions (working), ChromaDB (long-term)."""

import re
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

MEMORY_PATH = Path(__file__).parent.parent / "MEMORY.md"
CHROMA_PATH = Path(__file__).parent.parent / "data" / "chroma"


# ── Tier 1: MEMORY.md ────────────────────────────────────────────────────────

def read_memory() -> str:
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8")
    return _default_memory()


def _default_memory() -> str:
    return f"""# MEMORY.md

## Meta
version: 1
last_updated: {datetime.now().isoformat()}

## User Preferences

## Active Goals

## Active BMAD Workflows

## Context Shortcuts
"""


def update_memory_section(section: str, content: str) -> None:
    current = read_memory()

    header = f"## {section}"
    if header in current:
        pattern = rf"(## {re.escape(section)}\n)(.*?)(?=\n## |\Z)"
        replacement = rf"\g<1>{content}\n"
        updated = re.sub(pattern, replacement, current, flags=re.DOTALL)
    else:
        updated = current.rstrip() + f"\n\n## {section}\n{content}\n"

    updated = _inject_timestamp(updated)
    MEMORY_PATH.write_text(updated, encoding="utf-8")
    _git_commit_memory(f"Updated {section}")


def _inject_timestamp(content: str) -> str:
    now = datetime.now().isoformat()
    return re.sub(
        r"(last_updated:).*",
        f"\\1 {now}",
        content
    )


def _git_commit_memory(message: str) -> None:
    try:
        repo = MEMORY_PATH.parent
        subprocess.run(
            ["git", "-C", str(repo), "add", "MEMORY.md"],
            capture_output=True, check=False
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", message],
            capture_output=True, check=False
        )
    except Exception:
        pass


def rollback_memory(versions_back: int = 1) -> bool:
    try:
        repo = MEMORY_PATH.parent
        result = subprocess.run(
            ["git", "-C", str(repo), "checkout", f"HEAD~{versions_back}", "MEMORY.md"],
            capture_output=True, check=True
        )
        return result.returncode == 0
    except Exception:
        return False


def detect_preference_conflict(section: str, new_content: str) -> Optional[str]:
    """Returns conflicting old content if found, else None."""
    current = read_memory()
    header = f"## {section}"
    if header not in current:
        return None

    pattern = rf"## {re.escape(section)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, current, re.DOTALL)
    if not match:
        return None

    old = match.group(1).strip()
    if old and old != new_content.strip():
        return old
    return None


# ── Tier 3: ChromaDB vector memory ───────────────────────────────────────────

def _get_collection():
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        return client.get_or_create_collection(
            name="xochitl_memories",
            metadata={"hnsw:space": "cosine"}
        )
    except Exception:
        return None


def memorize(topic: str, summary: str, tags: list[str] = None, project: str = None) -> bool:
    collection = _get_collection()
    if not collection:
        return False

    doc_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{topic[:20].replace(' ', '_')}"
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "topic": topic,
        "tags": json.dumps(tags or []),
        "project": project or "",
    }

    try:
        collection.add(documents=[summary], ids=[doc_id], metadatas=[metadata])
        return True
    except Exception:
        return False


def recall(query: str, n_results: int = 5, project: str = None) -> list[dict]:
    collection = _get_collection()
    if not collection:
        return []

    where = {"project": project} if project else None

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(n_results, collection.count() or 1),
            where=where,
        )
        memories = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            memories.append({
                "summary": doc,
                "topic": meta.get("topic"),
                "timestamp": meta.get("timestamp"),
                "tags": json.loads(meta.get("tags", "[]")),
                "project": meta.get("project"),
            })
        return memories
    except Exception:
        return []


def vector_db_count() -> int:
    collection = _get_collection()
    if not collection:
        return 0
    try:
        return collection.count()
    except Exception:
        return 0
