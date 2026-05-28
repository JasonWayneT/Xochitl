"""SQLite schema initialization and all raw query helpers."""
# Implements FR-TASK-001 (SQLite state cache with PARA mapping — projects/tasks/areas/resources tables)
# Implements NFR-REL-001 (Atomic write before embedding — conn used as context manager, commits on exit)
# Implements NFR-REL-002 (State recovery < 1 second — SQLite WAL mode; DB_PATH resolved at import time)

import sqlite3
from pathlib import Path
from typing import Optional
import json

DB_PATH = Path(__file__).parent.parent / "data" / "tasks.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                priority TEXT NOT NULL CHECK(priority IN ('high','medium','low')),
                status TEXT DEFAULT 'active' CHECK(status IN ('active','archived')),
                description TEXT,
                deadline DATE,
                last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                description TEXT NOT NULL,
                time_estimate_minutes INTEGER,
                status TEXT DEFAULT 'todo' CHECK(status IN ('todo','in_progress','done','blocked')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                notion_task_id TEXT,
                blocked_by TEXT,
                days_rolled_over INTEGER DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS queue (
                task_id TEXT PRIMARY KEY,
                position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 3),
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            );

            CREATE TABLE IF NOT EXISTS areas (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS resources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                url TEXT,
                tags TEXT,
                last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tasks_completed INTEGER,
                projects_updated INTEGER,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                conversation_json TEXT DEFAULT '[]',
                context_summary TEXT
            );

            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                route TEXT NOT NULL,
                tokens_in INTEGER DEFAULT 0,
                tokens_out INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                operation TEXT NOT NULL,
                path TEXT,
                details TEXT
            );

            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope TEXT NOT NULL DEFAULT 'global' CHECK(scope IN ('global','project')),
                project_id TEXT,
                category TEXT NOT NULL DEFAULT 'general',
                preference_key TEXT NOT NULL,
                preference_value TEXT NOT NULL,
                source TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS secrets (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS memory_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                category TEXT NOT NULL CHECK(category IN
                    ('preference','context','project','skill','constraint','goal')),
                confidence REAL DEFAULT 0.5 CHECK(confidence BETWEEN 0.0 AND 1.0),
                source TEXT DEFAULT 'background_review',
                project TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                superseded_by INTEGER REFERENCES memory_facts(id)
            );

            CREATE TABLE IF NOT EXISTS agent_traces (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id     TEXT NOT NULL,
                ts           TEXT NOT NULL,
                route        TEXT,
                tokens_in    INTEGER DEFAULT 0,
                tokens_out   INTEGER DEFAULT 0,
                cost_usd     REAL DEFAULT 0.0,
                latency_ms   INTEGER DEFAULT 0,
                top_skill    TEXT,
                top_score    REAL DEFAULT 0.0,
                tool_calls   TEXT,
                failure_reason TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_agent_traces_ts
                ON agent_traces(ts DESC);

            CREATE TABLE IF NOT EXISTS workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                trigger_pattern TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                expected_outputs TEXT,
                failure_modes TEXT,
                project TEXT,
                source TEXT NOT NULL DEFAULT 'user_defined'
                    CHECK(source IN ('user_defined', 'distilled')),
                confidence REAL DEFAULT 0.8
                    CHECK(confidence BETWEEN 0.0 AND 1.0),
                last_used_at TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                superseded_by INTEGER REFERENCES workflows(id)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_workflows_name_active
                ON workflows(name) WHERE superseded_by IS NULL;
        """)


def _ensure_preferences_table(conn: sqlite3.Connection) -> None:
    """Create the CR-004 structured preferences table for upgraded databases."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope TEXT NOT NULL DEFAULT 'global' CHECK(scope IN ('global','project')),
            project_id TEXT,
            category TEXT NOT NULL DEFAULT 'general',
            preference_key TEXT NOT NULL,
            preference_value TEXT NOT NULL,
            source TEXT,
            confidence REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used_at TIMESTAMP
        )
    """)


# ── Projects ──────────────────────────────────────────────────────────────────

def upsert_project(conn: sqlite3.Connection, project: dict) -> None:
    conn.execute("""
        INSERT INTO projects (id, name, priority, status, description, deadline, last_synced)
        VALUES (:id, :name, :priority, :status, :description, :deadline, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, priority=excluded.priority, status=excluded.status,
            description=excluded.description, deadline=excluded.deadline,
            last_synced=CURRENT_TIMESTAMP
    """, project)


def get_active_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM projects WHERE status='active' ORDER BY "
        "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END"
    ).fetchall()


def get_project(conn: sqlite3.Connection, project_id: str) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()


# ── Areas ─────────────────────────────────────────────────────────────────────

def upsert_area(conn: sqlite3.Connection, area: dict) -> None:
    conn.execute("""
        INSERT INTO areas (id, name, description, status, last_synced)
        VALUES (:id, :name, :description, :status, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, description=excluded.description,
            status=excluded.status, last_synced=CURRENT_TIMESTAMP
    """, area)


def get_areas(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM areas WHERE status='active' ORDER BY name"
    ).fetchall()


# ── Resources ─────────────────────────────────────────────────────────────────

def upsert_resource(conn: sqlite3.Connection, resource: dict) -> None:
    conn.execute("""
        INSERT INTO resources (id, name, description, url, tags, last_synced)
        VALUES (:id, :name, :description, :url, :tags, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, description=excluded.description,
            url=excluded.url, tags=excluded.tags, last_synced=CURRENT_TIMESTAMP
    """, resource)


def get_resources(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM resources ORDER BY name").fetchall()


# ── Tasks ─────────────────────────────────────────────────────────────────────

def insert_task(conn: sqlite3.Connection, task: dict) -> None:
    conn.execute("""
        INSERT OR IGNORE INTO tasks
            (id, project_id, description, time_estimate_minutes, status, blocked_by)
        VALUES (:id, :project_id, :description, :time_estimate_minutes, :status, :blocked_by)
    """, task)


def update_task_status(conn: sqlite3.Connection, task_id: str, status: str) -> None:
    if status == "done":
        conn.execute(
            "UPDATE tasks SET status=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, task_id)
        )
    else:
        conn.execute(
            "UPDATE tasks SET status=?, completed_at=NULL WHERE id=?",
            (status, task_id)
        )


def get_next_eligible_tasks(conn: sqlite3.Connection, limit: int = 10) -> list[sqlite3.Row]:
    """Tasks that are todo, not blocked, ordered by project priority then created_at."""
    return conn.execute("""
        SELECT t.* FROM tasks t
        JOIN projects p ON t.project_id = p.id
        WHERE t.status = 'todo'
          AND p.status = 'active'
          AND t.id NOT IN (SELECT task_id FROM queue)
          AND (
              t.blocked_by IS NULL
              OR t.blocked_by NOT IN (
                  SELECT id FROM tasks WHERE status != 'done'
              )
          )
        ORDER BY
            CASE p.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            t.created_at ASC
        LIMIT ?
    """, (limit,)).fetchall()


def get_rollover_candidates(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM tasks WHERE days_rolled_over >= 3 AND status='todo'"
    ).fetchall()


def increment_rollover(conn: sqlite3.Connection) -> None:
    conn.execute("""
        UPDATE tasks SET days_rolled_over = days_rolled_over + 1
        WHERE status = 'todo'
          AND id IN (SELECT task_id FROM queue)
    """)


# ── Queue ─────────────────────────────────────────────────────────────────────

def get_queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("""
        SELECT q.position, t.id, t.description, t.time_estimate_minutes,
               t.days_rolled_over, p.name AS project_name, p.priority
        FROM queue q
        JOIN tasks t ON q.task_id = t.id
        JOIN projects p ON t.project_id = p.id
        ORDER BY q.position
    """).fetchall()


def queue_size(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]


def add_to_queue(conn: sqlite3.Connection, task_id: str, position: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO queue (task_id, position) VALUES (?, ?)",
        (task_id, position)
    )


def remove_from_queue(conn: sqlite3.Connection, task_id: str) -> None:
    conn.execute("DELETE FROM queue WHERE task_id=?", (task_id,))


def clear_queue(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM queue")


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        "INSERT INTO sessions (conversation_json) VALUES ('[]')"
    )
    return cursor.lastrowid


def get_session(conn: sqlite3.Connection, session_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()


def get_session_count(conn: sqlite3.Connection) -> int:
    """Return the total number of sessions ever started (FR-PREF-004).

    Used by the milestone engine to determine the current personalization tier.
    Includes the current session — count is checked after create_session().

    Args:
        conn: Active SQLite connection to the Xochitl database.

    Returns:
        Total row count of the sessions table; 0 if the table is empty.
    """
    row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
    return int(row[0]) if row else 0


def update_session_conversation(
    conn: sqlite3.Connection, session_id: int, messages: list
) -> None:
    conn.execute(
        "UPDATE sessions SET conversation_json=?, last_active=CURRENT_TIMESTAMP WHERE id=?",
        (json.dumps(messages), session_id)
    )


def update_session_summary(
    conn: sqlite3.Connection, session_id: int, summary: str
) -> None:
    conn.execute(
        "UPDATE sessions SET context_summary=? WHERE id=?",
        (summary, session_id)
    )


# ── Token Usage ───────────────────────────────────────────────────────────────

# Preferences

def upsert_preference(conn: sqlite3.Connection, preference: dict) -> int:
    """Persist a structured user preference.

    Implements DATA-DATA-004 for CR-004. Preferences are intentionally separate
    from semantic memory so stable user instructions can be recalled cheaply.
    """
    _ensure_preferences_table(conn)
    scope = preference.get("scope", "global")
    project_id = preference.get("project_id")
    key = preference["preference_key"]
    existing = conn.execute(
        """
        SELECT id FROM preferences
        WHERE scope=?
          AND COALESCE(project_id, '')=COALESCE(?, '')
          AND preference_key=?
        """,
        (scope, project_id, key),
    ).fetchone()
    values = {
        "scope": scope,
        "project_id": project_id,
        "category": preference.get("category", "general"),
        "preference_key": key,
        "preference_value": preference["preference_value"],
        "source": preference.get("source", "chat"),
        "confidence": float(preference.get("confidence", 1.0)),
    }
    if existing:
        conn.execute(
            """
            UPDATE preferences
            SET category=:category,
                preference_value=:preference_value,
                source=:source,
                confidence=:confidence,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=:id
            """,
            {**values, "id": existing["id"]},
        )
        return int(existing["id"])

    cursor = conn.execute(
        """
        INSERT INTO preferences
            (scope, project_id, category, preference_key, preference_value, source, confidence)
        VALUES
            (:scope, :project_id, :category, :preference_key, :preference_value, :source, :confidence)
        """,
        values,
    )
    return int(cursor.lastrowid)


def search_preferences(
    conn: sqlite3.Connection,
    query: str = "",
    *,
    project_id: str | None = None,
    limit: int = 5,
) -> list[sqlite3.Row]:
    """Return relevant global and project-scoped preferences for a turn."""
    _ensure_preferences_table(conn)
    normalized = " ".join(query.lower().split())
    tokens = [
        t for t in normalized.replace("-", " ").replace("_", " ").split()
        if len(t) >= 4
    ][:6]
    scope_filter = (
        "(scope='global' OR (scope='project' AND project_id=?))"
        if project_id else "scope='global'"
    )
    params: list = [project_id] if project_id else []

    if not tokens:
        params.append(limit)
        return conn.execute(
            f"""
            SELECT * FROM preferences
            WHERE {scope_filter}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    like_clauses = []
    for token in tokens:
        like_clauses.append(
            "(LOWER(category) LIKE ? OR LOWER(preference_key) LIKE ? OR LOWER(preference_value) LIKE ?)"
        )
        like = f"%{token}%"
        params.extend([like, like, like])
    params.append(limit)
    return conn.execute(
        f"""
        SELECT * FROM preferences
        WHERE {scope_filter}
          AND ({' OR '.join(like_clauses)})
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        params,
    ).fetchall()


def mark_preferences_used(conn: sqlite3.Connection, preference_ids: list[int]) -> None:
    """Record that preference rows were injected into context."""
    if not preference_ids:
        return
    _ensure_preferences_table(conn)
    placeholders = ",".join("?" for _ in preference_ids)
    conn.execute(
        f"UPDATE preferences SET last_used_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
        preference_ids,
    )


# Token Usage

def record_token_usage(
    conn: sqlite3.Connection,
    route: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
) -> None:
    conn.execute(
        "INSERT INTO token_usage (route, tokens_in, tokens_out, cost_usd) VALUES (?,?,?,?)",
        (route, tokens_in, tokens_out, cost_usd)
    )


def get_token_stats(conn: sqlite3.Connection, days: int = 7) -> dict:
    row = conn.execute("""
        SELECT
            SUM(CASE WHEN route='local' THEN 1 ELSE 0 END) as local_calls,
            SUM(CASE WHEN route='cloud' THEN 1 ELSE 0 END) as cloud_calls,
            SUM(tokens_in + tokens_out) as total_tokens,
            SUM(cost_usd) as total_cost
        FROM token_usage
        WHERE recorded_at >= datetime('now', ?)
    """, (f"-{days} days",)).fetchone()
    return dict(row) if row else {}


# ── Audit Log ─────────────────────────────────────────────────────────────────

def audit(conn: sqlite3.Connection, operation: str, path: str = None, details: str = None) -> None:
    conn.execute(
        "INSERT INTO audit_log (operation, path, details) VALUES (?,?,?)",
        (operation, path, details)
    )


# ── Secrets ───────────────────────────────────────────────────────────────────

def get_secret_db(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM secrets WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_secret_db(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("""
        INSERT INTO secrets (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
    """, (key, value))


def delete_secret_db(conn: sqlite3.Connection, key: str) -> bool:
    cursor = conn.execute("DELETE FROM secrets WHERE key=?", (key,))
    return cursor.rowcount > 0


def list_secrets_db(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT key, updated_at FROM secrets ORDER BY key").fetchall()


# ── Memory Facts (structured long-term memory) ────────────────────────────────

def _ensure_memory_facts_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT NOT NULL,
            category TEXT NOT NULL CHECK(category IN
                ('preference','context','project','skill','constraint','goal')),
            confidence REAL DEFAULT 0.5 CHECK(confidence BETWEEN 0.0 AND 1.0),
            source TEXT DEFAULT 'background_review',
            project TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            superseded_by INTEGER REFERENCES memory_facts(id)
        )
    """)


def upsert_memory_fact(
    conn: sqlite3.Connection,
    fact: str,
    category: str,
    confidence: float,
    source: str = "background_review",
    project: Optional[str] = None,
) -> int:
    """Insert a structured memory fact, or update confidence if near-duplicate exists.

    Near-duplicate detection is a simple 80-char prefix match — good enough to
    avoid storing the same fact twice without requiring a vector call at write time.
    """
    _ensure_memory_facts_table(conn)
    existing = conn.execute(
        """SELECT id, confidence FROM memory_facts
           WHERE LOWER(SUBSTR(fact, 1, 80)) = LOWER(SUBSTR(?, 1, 80))
             AND superseded_by IS NULL
           LIMIT 1""",
        (fact,),
    ).fetchone()

    if existing:
        if confidence >= existing["confidence"]:
            conn.execute(
                "UPDATE memory_facts SET confidence=?, last_seen_at=CURRENT_TIMESTAMP WHERE id=?",
                (confidence, existing["id"]),
            )
        return int(existing["id"])

    cursor = conn.execute(
        "INSERT INTO memory_facts (fact, category, confidence, source, project) VALUES (?,?,?,?,?)",
        (fact, category, confidence, source, project),
    )
    return int(cursor.lastrowid)


def get_memory_facts(
    conn: sqlite3.Connection,
    category: Optional[str] = None,
    min_confidence: float = 0.5,
    limit: int = 20,
) -> list[sqlite3.Row]:
    _ensure_memory_facts_table(conn)
    if category:
        return conn.execute(
            """SELECT * FROM memory_facts
               WHERE category=? AND confidence>=? AND superseded_by IS NULL
               ORDER BY confidence DESC, last_seen_at DESC LIMIT ?""",
            (category, min_confidence, limit),
        ).fetchall()
    return conn.execute(
        """SELECT * FROM memory_facts
           WHERE confidence>=? AND superseded_by IS NULL
           ORDER BY confidence DESC, last_seen_at DESC LIMIT ?""",
        (min_confidence, limit),
    ).fetchall()


# ── Procedural memory (workflows) — CR-041 ───────────────────────────────────

def _ensure_workflows_table(conn: sqlite3.Connection) -> None:
    """Create workflows table for upgraded databases (FR-MEM-008)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            trigger_pattern TEXT NOT NULL,
            steps_json TEXT NOT NULL,
            expected_outputs TEXT,
            failure_modes TEXT,
            project TEXT,
            source TEXT NOT NULL DEFAULT 'user_defined'
                CHECK(source IN ('user_defined', 'distilled')),
            confidence REAL DEFAULT 0.8
                CHECK(confidence BETWEEN 0.0 AND 1.0),
            last_used_at TIMESTAMP,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            superseded_by INTEGER REFERENCES workflows(id)
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_workflows_name_active
            ON workflows(name) WHERE superseded_by IS NULL
    """)


def upsert_workflow(
    conn: sqlite3.Connection,
    name: str,
    trigger_pattern: str,
    steps: list[dict],
    *,
    expected_outputs: Optional[str] = None,
    failure_modes: Optional[str] = None,
    project: Optional[str] = None,
    source: str = "user_defined",
    confidence: float = 0.8,
) -> int:
    """Insert or update an active workflow by name (FR-MEM-008).

    Args:
        conn: SQLite connection.
        name: Unique workflow slug/display name.
        trigger_pattern: Phrases that should recall this workflow.
        steps: Ordered step dicts (skill/tool descriptions).
        expected_outputs: Optional expected outcome text.
        failure_modes: Optional known failure notes.
        project: Optional project scope.
        source: ``user_defined`` or ``distilled``.
        confidence: Match confidence prior (0-1).

    Returns:
        Row id of the workflow.
    """
    _ensure_workflows_table(conn)
    steps_json = json.dumps(steps, ensure_ascii=False)
    existing = conn.execute(
        "SELECT id FROM workflows WHERE LOWER(name)=LOWER(?) AND superseded_by IS NULL",
        (name,),
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE workflows SET trigger_pattern=?, steps_json=?,
               expected_outputs=?, failure_modes=?, project=?, source=?,
               confidence=?
               WHERE id=?""",
            (
                trigger_pattern,
                steps_json,
                expected_outputs,
                failure_modes,
                project,
                source,
                confidence,
                existing["id"],
            ),
        )
        return int(existing["id"])
    cursor = conn.execute(
        """INSERT INTO workflows
           (name, trigger_pattern, steps_json, expected_outputs, failure_modes,
            project, source, confidence)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            name,
            trigger_pattern,
            steps_json,
            expected_outputs,
            failure_modes,
            project,
            source,
            confidence,
        ),
    )
    return int(cursor.lastrowid)


def get_workflow(conn: sqlite3.Connection, name: str) -> Optional[sqlite3.Row]:
    """Fetch an active workflow by name (FR-MEM-008)."""
    _ensure_workflows_table(conn)
    return conn.execute(
        "SELECT * FROM workflows WHERE LOWER(name)=LOWER(?) AND superseded_by IS NULL",
        (name,),
    ).fetchone()


def list_workflows(
    conn: sqlite3.Connection,
    project: Optional[str] = None,
    limit: int = 50,
) -> list[sqlite3.Row]:
    """List active workflows, optionally filtered by project (FR-MEM-008)."""
    _ensure_workflows_table(conn)
    if project:
        return conn.execute(
            """SELECT * FROM workflows WHERE superseded_by IS NULL AND project=?
               ORDER BY last_used_at IS NULL, last_used_at DESC, name ASC LIMIT ?""",
            (project, limit),
        ).fetchall()
    return conn.execute(
        """SELECT * FROM workflows WHERE superseded_by IS NULL
           ORDER BY last_used_at IS NULL, last_used_at DESC, name ASC LIMIT ?""",
        (limit,),
    ).fetchall()


def record_workflow_run(
    conn: sqlite3.Connection,
    workflow_id: int,
    *,
    success: bool,
) -> None:
    """Increment success or failure count and touch last_used_at (FR-MEM-008, FR-HARD-002).

    Args:
        conn: Active SQLite connection.
        workflow_id: Primary key of the workflow to update.
        success: True increments success_count; False increments failure_count.
    """
    _ensure_workflows_table(conn)
    if success:
        conn.execute(
            "UPDATE workflows SET success_count=success_count+1, "
            "last_used_at=CURRENT_TIMESTAMP WHERE id=?",
            (workflow_id,),
        )
    else:
        conn.execute(
            "UPDATE workflows SET failure_count=failure_count+1, "
            "last_used_at=CURRENT_TIMESTAMP WHERE id=?",
            (workflow_id,),
        )


def supersede_workflow(conn: sqlite3.Connection, name: str) -> bool:
    """Mark a workflow superseded (soft delete) by name."""
    _ensure_workflows_table(conn)
    row = get_workflow(conn, name)
    if not row:
        return False
    conn.execute(
        "UPDATE workflows SET superseded_by=id WHERE id=?",
        (row["id"],),
    )
    return True


# ── Observability ─────────────────────────────────────────────────────────────

def insert_agent_trace(conn: sqlite3.Connection, trace: dict) -> int:
    """Insert one structured turn trace into the agent_traces table.

    Called by ObservabilityLogger on llm_complete (FR-ORCH-035, CR-021).
    The table is created lazily via init_db(); init_db() is called on session
    start so the table is always available by the time this runs.

    Args:
        conn:  Active SQLite connection (used as context manager by caller).
        trace: OTel-aligned record dict from ``_TurnTrace.to_record()``.

    Returns:
        The rowid of the newly inserted row.
    """
    tool_calls_json = json.dumps(trace.get("tool_calls") or [])
    cursor = conn.execute(
        """
        INSERT INTO agent_traces
            (trace_id, ts, route, tokens_in, tokens_out, cost_usd,
             latency_ms, top_skill, top_score, tool_calls, failure_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trace.get("trace_id", ""),
            trace.get("ts", ""),
            trace.get("gen_ai.request.model", ""),
            int(trace.get("gen_ai.usage.prompt_tokens", 0)),
            int(trace.get("gen_ai.usage.completion_tokens", 0)),
            float(trace.get("cost_usd", 0.0)),
            int(trace.get("latency_ms", 0)),
            trace.get("top_skill"),
            float(trace.get("top_score", 0.0)),
            tool_calls_json,
            trace.get("failure_reason"),
        ),
    )
    return int(cursor.lastrowid)
