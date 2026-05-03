"""SQLite schema initialization and all raw query helpers."""

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
