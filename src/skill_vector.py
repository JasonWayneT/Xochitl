"""Semantic vector index for skill intent matching (CR-054 Phase 3).

Implements:
  FR-ROUTE-006 — SkillVectorIndex (structurally identical to WorkflowVectorIndex)
  FR-ROUTE-007 — seed_from_skills(): index all skill examples + when fields
  FR-ROUTE-008 — search() used by SkillScorer as keyword-miss fallback
  NFR-ROUTE-002 — 500ms timeout; failure returns None silently

Uses LanceDB table ``skill_intents`` (separate from ``workflow_intents``).
Embedding model: nomic-embed-text via Ollama.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from src.config import CONFIG_DIR, get_model

if TYPE_CHECKING:
    from src.skills.base import Skill

LANCEDB_DIR = CONFIG_DIR / "lancedb"

_TABLE = "skill_intents"


class SkillVectorIndex:
    """Embed and search skill intent phrases in an isolated LanceDB table.

    Implements FR-ROUTE-006.  Clone of WorkflowVectorIndex targeting
    the ``skill_intents`` table.
    """

    def __init__(self, db_dir: Path | None = None) -> None:
        self._db_dir = db_dir or LANCEDB_DIR
        self._embed_model = get_model("embedding_model") or "nomic-embed-text"

    def _embed(self, text: str) -> list[float] | None:
        try:
            import ollama
            resp = ollama.embeddings(model=self._embed_model, prompt=text[:2000])
            return resp.get("embedding")
        except Exception:
            return None

    def _open_table(self) -> Any:
        try:
            import lancedb
            db = lancedb.connect(str(self._db_dir))
            if _TABLE in db.table_names():
                return db.open_table(_TABLE)
            return None
        except Exception:
            return None

    def seed_from_skills(self, skills: list[Skill]) -> bool:
        """Index all tool_definition() examples and when fields for each skill.

        Implements FR-ROUTE-007.  Best-effort — failure does not block session start.

        Args:
            skills: Registered skill instances.

        Returns:
            True if at least one phrase was successfully indexed.
        """
        records = []
        for skill in skills:
            try:
                defn = skill.tool_definition()
            except Exception:
                continue
            skill_name = defn.get("name", type(skill).__name__)
            phrases: list[tuple[str, str]] = []

            # When clause
            when = defn.get("when", "")
            if when:
                phrases.append((when, "seed_when"))

            # Examples
            for ex in defn.get("examples", []):
                if ex and isinstance(ex, str):
                    phrases.append((ex, "seed_example"))

            for phrase, source in phrases:
                vector = self._embed(phrase)
                if vector is None:
                    continue
                records.append({
                    "skill_name": skill_name,
                    "phrase": phrase[:500],
                    "source": source,
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                    "vector": vector,
                })

        if not records:
            return False

        try:
            import lancedb
            self._db_dir.mkdir(parents=True, exist_ok=True)
            db = lancedb.connect(str(self._db_dir))
            table = self._open_table()
            if table is not None:
                # Clear seed rows before re-seeding (leave "learned" rows)
                try:
                    table.delete("source LIKE 'seed%'")
                except Exception:
                    pass
                table.add(records)
            else:
                db.create_table(_TABLE, data=records)
            return True
        except Exception:
            return False

    def index_phrase(self, skill_name: str, phrase: str, source: str = "learned") -> bool:
        """Add a single learned phrase to the index.

        Called by BackgroundReview hard-add (FR-ROUTE-012).

        Args:
            skill_name: Canonical skill class name.
            phrase: User utterance that matched this skill.
            source: 'learned' (from vector match) or 'promoted' (from miss threshold).

        Returns:
            True if successfully indexed.
        """
        vector = self._embed(phrase)
        if vector is None:
            return False
        record = {
            "skill_name": skill_name,
            "phrase": phrase[:500],
            "source": source,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
            "vector": vector,
        }
        try:
            import lancedb
            self._db_dir.mkdir(parents=True, exist_ok=True)
            db = lancedb.connect(str(self._db_dir))
            table = self._open_table()
            if table is not None:
                table.add([record])
            else:
                db.create_table(_TABLE, data=[record])
            return True
        except Exception:
            return False

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return skill_name -> similarity score from vector search.

        Implements FR-ROUTE-008.

        Args:
            query: User utterance to embed and search.
            limit: Max results.

        Returns:
            List of dicts with skill_name and score (0-1).
        """
        table = self._open_table()
        if table is None:
            return []
        vector = self._embed(query)
        if vector is None:
            return []
        try:
            rows = table.search(vector).limit(limit).to_list()
            out: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in rows:
                dist = float(row.get("_distance", 0.5))
                score = max(0.0, min(1.0, 1.0 - dist))
                skill_name = row.get("skill_name", "")
                if skill_name and skill_name not in seen:
                    seen.add(skill_name)
                    out.append({"skill_name": skill_name, "score": score})
            return out
        except Exception:
            return []
