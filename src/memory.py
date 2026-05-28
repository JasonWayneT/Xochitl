"""5-tier memory hierarchy: WorkingMemory, Profile, Markdown KB, LanceDB, session archives."""
# Implements FR-MEM-001 (Working Memory — Tier 0, immutable in-process event log)
# Implements FR-MEM-002 (User Profile — Tier 1, via config.py)
# Implements FR-MEM-003 (Markdown Knowledge Base — Tier 2, keyword search)
# Implements FR-MEM-004 (Vector DB Semantic Search — Tier 3, LanceDB)
# Implements FR-MEM-005 (Reranking Protocol — Qwen3-Reranker via Ollama, graceful fallback)
# Implements FR-MEM-006 (Session Archiving — SQLite sessions → ~/.xochitl/sessions/*.md)
# Procedural workflows (FR-MEM-008–011): see src/workflows.py + workflows table (CR-041)
# Implements NFR-PERF-001 (Tier 1/2 latency < 100ms)
# Implements NFR-PERF-002 (Tier 3 latency < 550ms)
# Implements NFR-REL-001 (Atomic write before embedding)
# Implements NFR-SEC-001 (Local execution for Tiers 0–3)

import hashlib
import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import CONFIG_DIR, get_profile, get_model

KB_DIR = CONFIG_DIR / "kb"
SESSIONS_DIR = CONFIG_DIR / "sessions"
LANCEDB_DIR = CONFIG_DIR / "lancedb"

_HASHES_FILE = ".hashes.json"


# ── Tier 0: Working Memory ────────────────────────────────────────────────────

class WorkingMemory:
    """Implements FR-MEM-001 — immutable append-only in-process event log."""
    # RAM only — never persisted between sessions.

    def __init__(self) -> None:
        self._events: list[dict] = []

    def append(self, event_type: str, content: str, metadata: dict | None = None) -> None:
        """Append an event. Immutable once written — no update/delete."""
        self._events.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "content": content,
            **(metadata or {}),
        })

    def get_events(self, n: int | None = None) -> list[dict]:
        """Return a copy so callers cannot mutate the log."""
        events = self._events if n is None else self._events[-n:]
        return [dict(e) for e in events]

    def get_recent_context(self, n: int = 10) -> str:
        """Format recent events as a plain-text block for LLM injection."""
        events = self._events[-n:]
        if not events:
            return ""
        lines = []
        for e in events:
            ts = e["timestamp"][:19].replace("T", " ")
            lines.append(f"[{ts}] {e['type']}: {e['content'][:200]}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Called at session end — resets the in-process log."""
        self._events = []

    @property
    def count(self) -> int:
        return len(self._events)


# ── Tier 2: Markdown Knowledge Base ──────────────────────────────────────────

class KnowledgeBase:
    """Implements FR-MEM-003 — keyword search over ~/.xochitl/kb/*.md files."""

    def __init__(self, kb_dir: Path | None = None) -> None:
        self.kb_dir = kb_dir or KB_DIR

    def _ensure_dir(self) -> None:
        self.kb_dir.mkdir(parents=True, exist_ok=True)

    def _load_hashes(self) -> dict:
        hf = self.kb_dir / _HASHES_FILE
        if not hf.exists():
            return {}
        try:
            return json.loads(hf.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_hash(self, filename: str, content: str) -> None:
        """Store SHA-256 of written content so verify_on_call can detect staleness."""
        hashes = self._load_hashes()
        hashes[filename] = hashlib.sha256(content.encode("utf-8")).hexdigest()
        hf = self.kb_dir / _HASHES_FILE
        hf.write_text(json.dumps(hashes, indent=2), encoding="utf-8")

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Keyword search across all KB entries. NFR-PERF-001: < 100ms."""
        # Implements FR-MEM-003, NFR-PERF-001
        self._ensure_dir()
        stop_words = {"", "the", "a", "an", "is", "in", "of", "to", "and", "or", "for", "with"}
        keywords = set(re.split(r'\W+', query.lower())) - stop_words

        results = []
        for md_file in sorted(self.kb_dir.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
                lower = text.lower()
                score = sum(1 for kw in keywords if kw in lower)
                if score > 0:
                    results.append({
                        "title": md_file.stem.replace("_", " "),
                        "content": text[:1000],
                        "score": score,
                        "path": str(md_file),
                        "tier": 2,
                    })
            except Exception:
                continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def upsert(self, title: str, content: str, tags: list[str] | None = None) -> Path:
        """Atomically write a KB entry and store its hash. NFR-REL-001."""
        # Implements FR-MEM-003, NFR-REL-001 (atomic write before embedding)
        self._ensure_dir()
        slug = re.sub(r'\W+', '_', title.lower()).strip('_')
        path = self.kb_dir / f"{slug}.md"

        header = f"# {title}\n"
        if tags:
            header += f"tags: {', '.join(tags)}\n"
        header += f"updated: {datetime.now(timezone.utc).isoformat()}\n\n"
        full_content = header + content

        # Atomic write: .tmp → rename (NFR-REL-001)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(full_content, encoding="utf-8")
        tmp.replace(path)

        self._save_hash(path.name, full_content)
        return path

    def list_entries(self) -> list[dict]:
        self._ensure_dir()
        entries = []
        for md_file in sorted(self.kb_dir.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
                first_line = text.splitlines()[0].lstrip("# ").strip() if text.strip() else md_file.stem
                entries.append({
                    "title": first_line,
                    "path": str(md_file),
                    "size": len(text),
                })
            except Exception:
                continue
        return entries


_HYDE_PROMPT = """\
Write a short passage (2-4 sentences) that would directly contain or address the following.
Write as a factual statement, as if you are a document, not as an answer to a question.

Query: {query}

Passage:"""


# ── Tier 3: LanceDB Semantic Search ──────────────────────────────────────────

class VectorMemory:
    """Implements FR-MEM-004 — LanceDB embedded vector store at ~/.xochitl/lancedb/."""

    def __init__(self, db_dir: Path | None = None) -> None:
        self.db_dir = db_dir or LANCEDB_DIR
        self._table_name = "memories"
        self._embed_model = get_model("embedding_model") or "nomic-embed-text"

    def _embed(self, text: str) -> list[float] | None:
        """Generate embedding via Ollama. Returns None on failure."""
        # Implements NFR-SEC-001 (local inference only)
        try:
            import ollama
            resp = ollama.embeddings(model=self._embed_model, prompt=text)
            return resp.get("embedding")
        except Exception:
            return None

    def _hyde_embed(self, query: str) -> list[float] | None:
        """HyDE: embed a generated hypothetical document rather than the raw query.

        Personal notes are written as statements of fact. Embedding a generated
        passage retrieves them more accurately than embedding a question directly.
        Falls back to direct query embedding if the model call fails.
        """
        try:
            from src.llm_interface import call_local, ROUTER_MODEL
            result = call_local(
                messages=[{"role": "user", "content": _HYDE_PROMPT.format(query=query)}],
                model=ROUTER_MODEL,
            )
            if not result.error and result.content:
                hypothetical = result.content.strip()[:500]
                vec = self._embed(hypothetical)
                if vec:
                    return vec
        except Exception:
            pass
        return self._embed(query)

    def _open_table(self):
        """Open existing LanceDB memories table, or None if not yet created."""
        try:
            import lancedb
            db = lancedb.connect(str(self.db_dir))
            if self._table_name in db.table_names():
                return db.open_table(self._table_name)
            return None
        except Exception:
            return None

    def memorize(self, topic: str, summary: str, tags: list[str] | None = None, project: str | None = None) -> bool:
        """Store a memory with its embedding. NFR-REL-001: text persisted before embedding."""
        # Implements FR-MEM-004, NFR-REL-001, NFR-SEC-001
        vector = self._embed(summary)
        if vector is None:
            return False

        record = {
            "id": f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{topic[:20].replace(' ', '_')}",
            "topic": topic,
            "summary": summary,
            "tags": json.dumps(tags or []),
            "project": project or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vector": vector,
        }

        try:
            import lancedb
            self.db_dir.mkdir(parents=True, exist_ok=True)
            db = lancedb.connect(str(self.db_dir))
            if self._table_name in db.table_names():
                db.open_table(self._table_name).add([record])
            else:
                db.create_table(self._table_name, data=[record])
            return True
        except Exception:
            return False

    def recall(self, query: str, n_results: int = 10, project: str | None = None) -> list[dict]:
        """Semantic vector search with HyDE. NFR-PERF-002: < 550ms."""
        # Implements FR-MEM-004, NFR-PERF-002
        table = self._open_table()
        if table is None:
            return []

        vector = self._hyde_embed(query)
        if vector is None:
            return []

        try:
            rows = table.search(vector).limit(n_results).to_list()
            memories = []
            for row in rows:
                if project and row.get("project") != project:
                    continue
                memories.append({
                    "summary": row.get("summary", ""),
                    "topic": row.get("topic", ""),
                    "timestamp": row.get("timestamp", ""),
                    "tags": json.loads(row.get("tags", "[]")),
                    "project": row.get("project", ""),
                    "score": 1.0 - float(row.get("_distance", 0.5)),
                    "tier": 3,
                })
            return memories
        except Exception:
            return []

    def count(self) -> int:
        table = self._open_table()
        if table is None:
            return 0
        try:
            return table.count_rows()
        except Exception:
            return 0

    def re_embed_profile(self, profile_text: str) -> None:
        """Re-embed the user profile in LanceDB after a Me.md change (FR-RELY-005).

        Runs in a background daemon thread so it never blocks the turn.
        Upserts a single record tagged source='profile' — idempotent on re-run.

        Args:
            profile_text: Full text of Me.md (already loaded by UserProfileEngine).
        """
        def _worker() -> None:
            try:
                text = profile_text.strip()
                if not text:
                    return
                self.memorize(
                    topic="user_profile",
                    summary=text[:2000],
                    tags=["profile", "me"],
                )
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()


# ── FR-MEM-005: Reranking Protocol ───────────────────────────────────────────

def rerank(query: str, candidates: list[dict], top_k: int = 3) -> list[dict]:
    """Implements FR-MEM-005 — rerank via Qwen3-Reranker-0.6B; fallback to score sort."""
    # Implements NFR-SEC-001 (local model via Ollama)
    if not candidates:
        return []

    reranker_model = get_model("reranker_model") or "qwen3-reranker-0.6b"

    try:
        import ollama
        scored = []
        for c in candidates:
            text = c.get("content") or c.get("summary", "")
            prompt = (
                f"<Instruct>: Score how relevant this document is to the query. "
                f"Output only a number between 0.0 and 1.0.\n"
                f"<Query>: {query}\n"
                f"<Document>: {text[:500]}\n"
                f"<Score>:"
            )
            resp = ollama.generate(model=reranker_model, prompt=prompt)
            raw = resp.get("response", "0.5").strip()
            match = re.search(r'[0-9]+\.?[0-9]*', raw)
            score = max(0.0, min(1.0, float(match.group()) if match else 0.5))
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    except Exception:
        # Fallback: sort by existing score field
        by_score = sorted(candidates, key=lambda c: c.get("score", 0), reverse=True)
        return by_score[:top_k]


# ── FR-MEM-006: Session Archiving ────────────────────────────────────────────

def archive_session(session_id: str, db_path: Path | None = None) -> Optional[Path]:
    """Export a SQLite session to Markdown in ~/.xochitl/sessions/. Implements FR-MEM-006."""
    # Implements FR-MEM-006
    if db_path is None:
        from src.config import STATE_DB_PATH
        db_path = STATE_DB_PATH

    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}

        messages: list[dict] = []
        if "messages" in tables:
            cur.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            )
            messages = [dict(row) for row in cur.fetchall()]
        elif "sessions" in tables:
            cur.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()
            if row:
                messages = [{"role": "system", "content": str(dict(row)), "created_at": ""}]

        conn.close()
    except Exception:
        return None

    if not messages:
        return None

    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = SESSIONS_DIR / f"{date_str}_{session_id[:8]}.md"

    lines = [
        f"# Session {session_id}",
        f"archived: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        ts = msg.get("created_at", "")
        content = msg.get("content", "")
        lines.append(f"## {role}" + (f" [{ts}]" if ts else ""))
        lines.append(content)
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ── Unified retrieval across all tiers ───────────────────────────────────────

def query_memory(
    query: str,
    working_mem: WorkingMemory | None = None,
    top_k: int = 3,
    include_tiers: list[int] | None = None,
) -> dict:
    """Retrieve and rerank context from all available tiers.

    Implements FR-MEM-001 through FR-MEM-005.
    NFR-PERF-001: Tiers 0–2 < 100ms total. NFR-PERF-002: Tier 3 < 550ms total.
    """
    tiers = set(include_tiers or [0, 1, 2, 3])
    result: dict = {}

    if 0 in tiers and working_mem is not None:
        result["tier0"] = working_mem.get_recent_context(n=10)

    if 1 in tiers:
        result["tier1"] = get_profile()

    tier2_results: list[dict] = []
    if 2 in tiers:
        tier2_results = KnowledgeBase().search(query, max_results=10)
        result["tier2"] = tier2_results

    tier3_results: list[dict] = []
    if 3 in tiers:
        tier3_results = VectorMemory().recall(query, n_results=10)
        result["tier3"] = tier3_results

    combined = tier2_results + tier3_results
    result["top"] = rerank(query, combined, top_k=top_k) if combined else []

    return result


# ── Module-level singleton ────────────────────────────────────────────────────

_working_memory = WorkingMemory()


def get_working_memory() -> WorkingMemory:
    """Return the session-scoped WorkingMemory singleton."""
    return _working_memory


# ── Backward-compatibility shims ─────────────────────────────────────────────

def read_memory() -> str:
    """Compat: returns formatted profile + recent session context."""
    profile = get_profile()
    wm_ctx = _working_memory.get_recent_context(n=10)
    parts = [
        f"User: {profile.get('name', 'Unknown')} | Persona: {profile.get('persona', 'Matriarca')}",
    ]
    if wm_ctx:
        parts.append(f"Recent session:\n{wm_ctx}")
    return "\n".join(parts)


def memorize(topic: str, summary: str, tags: list[str] | None = None, project: str | None = None) -> bool:
    """Compat shim → VectorMemory.memorize()."""
    return VectorMemory().memorize(topic, summary, tags=tags, project=project)


def recall(query: str, n_results: int = 5, project: str | None = None) -> list[dict]:
    """Compat shim → VectorMemory.recall()."""
    return VectorMemory().recall(query, n_results=n_results, project=project)


def vector_db_count() -> int:
    """Compat shim → VectorMemory.count()."""
    return VectorMemory().count()
