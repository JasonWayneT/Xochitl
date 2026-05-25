"""Separate vector index for procedural workflow intent recall (CR-042 / FR-MEM-012).

Uses LanceDB table ``workflow_intents`` — not the semantic ``memories`` table.
"""
# Implements FR-MEM-012

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.config import CONFIG_DIR, get_model

LANCEDB_DIR = CONFIG_DIR / "lancedb"

_TABLE = "workflow_intents"


class WorkflowVectorIndex:
    """Embed and search workflow trigger text in an isolated LanceDB table."""

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

    def index_workflow(
        self,
        workflow_id: int,
        name: str,
        trigger_pattern: str,
        *,
        project: str = "",
    ) -> bool:
        """Upsert one workflow row in the intent index.

        Args:
            workflow_id: SQLite workflows.id.
            name: Workflow name.
            trigger_pattern: Recall phrases.
            project: Optional project id string.

        Returns:
            True if embedding was stored.
        """
        trigger_text = f"{name}. {trigger_pattern}".strip()
        vector = self._embed(trigger_text)
        if vector is None:
            return False
        record = {
            "workflow_id": str(workflow_id),
            "name": name,
            "trigger_text": trigger_text,
            "project": project or "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vector": vector,
        }
        try:
            import lancedb
            self._db_dir.mkdir(parents=True, exist_ok=True)
            db = lancedb.connect(str(self._db_dir))
            table = self._open_table()
            if table is not None:
                try:
                    table.delete(f"workflow_id = '{workflow_id}'")
                except Exception:
                    pass
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
        project: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Return workflow_id -> similarity score from vector search.

        Args:
            query: User utterance.
            project: Optional project filter.
            limit: Max results.

        Returns:
            List of dicts with workflow_id (int), name, score (0-1).
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
            for row in rows:
                if project and row.get("project") not in ("", project):
                    continue
                dist = float(row.get("_distance", 0.5))
                score = max(0.0, min(1.0, 1.0 - dist))
                try:
                    wid = int(row.get("workflow_id", 0))
                except (TypeError, ValueError):
                    continue
                out.append({
                    "workflow_id": wid,
                    "name": row.get("name", ""),
                    "score": score,
                })
            return out
        except Exception:
            return []

    def remove_workflow(self, workflow_id: int) -> None:
        """Remove a workflow from the index when superseded."""
        table = self._open_table()
        if table is None:
            return
        try:
            table.delete(f"workflow_id = '{workflow_id}'")
        except Exception:
            pass
