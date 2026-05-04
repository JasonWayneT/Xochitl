"""Task CRUD, queue management (configurable WIP limit), rollover logic."""
# Implements FR-TASK-001 (SQLite state cache — CRUD over tasks/projects via database.py)
# Implements FR-TASK-002 (WIP limit read from config.get_wip_limit(), not hardcoded)
# Implements FR-TASK-004 (Backlog task suggestions — fill_queue() pulls eligible tasks by priority)

import uuid
from typing import Optional

from src import database as db
from src.config import get_wip_limit


# ── Queue management ──────────────────────────────────────────────────────────

def fill_queue() -> list[str]:
    """Pull eligible tasks into queue up to the configured WIP limit. Returns added task IDs."""
    # Implements FR-TASK-002
    added = []
    with db.get_connection() as conn:
        current_size = db.queue_size(conn)
        slots = get_wip_limit() - current_size
        if slots <= 0:
            return []

        # Fetch already-queued task IDs to exclude
        queued_ids = {row["task_id"] for row in conn.execute("SELECT task_id FROM queue").fetchall()}

        candidates = conn.execute("""
            SELECT t.id FROM tasks t
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
        """, (slots,)).fetchall()

        next_pos = current_size + 1
        for row in candidates:
            db.add_to_queue(conn, row["id"], next_pos)
            added.append(row["id"])
            next_pos += 1

    return added


def get_queue_display() -> list[dict]:
    with db.get_connection() as conn:
        rows = db.get_queue(conn)
        return [dict(r) for r in rows]


def mark_done(position: int) -> Optional[dict]:
    """Mark the task at queue position as done, remove from queue, fill gap."""
    with db.get_connection() as conn:
        row = conn.execute(
            "SELECT task_id FROM queue WHERE position=?", (position,)
        ).fetchone()
        if not row:
            return None

        task_id = row["task_id"]
        db.update_task_status(conn, task_id, "done")
        db.remove_from_queue(conn, task_id)
        _repack_queue_positions(conn)

    fill_queue()

    with db.get_connection() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(task) if task else None


def _repack_queue_positions(conn) -> None:
    rows = conn.execute("SELECT task_id FROM queue ORDER BY position").fetchall()
    conn.execute("DELETE FROM queue")
    for i, row in enumerate(rows, start=1):
        conn.execute(
            "INSERT INTO queue (task_id, position) VALUES (?, ?)",
            (row["task_id"], i)
        )


# ── Task CRUD ─────────────────────────────────────────────────────────────────

def create_task(
    project_id: str,
    description: str,
    time_estimate_minutes: int = 30,
    blocked_by: Optional[str] = None,
) -> str:
    task_id = str(uuid.uuid4())
    task = {
        "id": task_id,
        "project_id": project_id,
        "description": description,
        "time_estimate_minutes": time_estimate_minutes,
        "status": "todo",
        "blocked_by": blocked_by,
    }
    with db.get_connection() as conn:
        db.insert_task(conn, task)
    return task_id


def create_tasks_bulk(project_id: str, task_dicts: list[dict]) -> list[str]:
    """Insert multiple tasks from LLM decomposition output."""
    # Pass 1: assign all IDs so forward references resolve correctly
    id_map: dict[int, str] = {i: str(uuid.uuid4()) for i in range(len(task_dicts))}

    with db.get_connection() as conn:
        for i, t in enumerate(task_dicts):
            blocked_by_raw = t.get("blocked_by")
            blocked_by = id_map.get(blocked_by_raw) if isinstance(blocked_by_raw, int) else None

            task = {
                "id": id_map[i],
                "project_id": project_id,
                "description": t["description"],
                "time_estimate_minutes": t.get("time_estimate_minutes", 30),
                "status": "todo",
                "blocked_by": blocked_by,
            }
            db.insert_task(conn, task)

    return list(id_map.values())


def get_all_tasks(project_id: Optional[str] = None) -> list[dict]:
    with db.get_connection() as conn:
        if project_id:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE project_id=? ORDER BY created_at", (project_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]


# ── Rollover ──────────────────────────────────────────────────────────────────

def run_daily_rollover() -> list[dict]:
    """Increment rollover counter for all queued tasks. Returns rollover warnings."""
    with db.get_connection() as conn:
        db.increment_rollover(conn)
        warning_rows = db.get_rollover_candidates(conn)
        return [dict(r) for r in warning_rows]


def handle_rollover_task(task_id: str, action: str) -> None:
    """action: 'keep' | 'delete' | 'reschedule'"""
    with db.get_connection() as conn:
        if action == "delete":
            conn.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
            db.remove_from_queue(conn, task_id)
        elif action == "reschedule":
            conn.execute(
                "UPDATE tasks SET days_rolled_over=0 WHERE id=?", (task_id,)
            )
        # 'keep' is a no-op


# ── Project CRUD ──────────────────────────────────────────────────────────────

def create_project(
    name: str,
    priority: str = "medium",
    description: str = "",
    deadline: Optional[str] = None,
) -> str:
    import uuid as _uuid
    project_id = str(_uuid.uuid4())
    project = {
        "id": project_id,
        "name": name,
        "priority": priority,
        "status": "active",
        "description": description,
        "deadline": deadline,
    }
    with db.get_connection() as conn:
        db.upsert_project(conn, project)
    return project_id


def list_projects() -> list[dict]:
    with db.get_connection() as conn:
        rows = db.get_active_projects(conn)
        return [dict(r) for r in rows]
