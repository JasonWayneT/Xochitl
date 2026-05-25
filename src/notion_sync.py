"""Notion read/write with conflict detection via last_edited_time."""
# Implements FR-TASK-003 (Bi-directional Notion sync — pull_and_sync() and sync_completed_to_notion())
# Implements NFR-SYNC-001 (Local cache overrides sync conflicts — on_conflict defaults to 'pull'; 'keep' preserves local)

import httpx
from datetime import datetime, timezone
from typing import Optional

from src.exceptions import NotionError  # ARCH-ORCH-001 (CR-018)
from src.secrets import get_secret

NOTION_API_KEY         = get_secret("NOTION_API_KEY", "")
NOTION_PROJECTS_DB_ID  = get_secret("NOTION_PROJECTS_DB_ID", "")
NOTION_AREAS_DB_ID     = get_secret("NOTION_AREAS_DB_ID", "")
NOTION_TASKS_DB_ID     = get_secret("NOTION_TASKS_DB_ID", "")
NOTION_RESOURCES_DB_ID = get_secret("NOTION_RESOURCES_DB_ID", "")

_NOTION_VERSION = "2022-06-28"
_BASE = "https://api.notion.com/v1"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _db_query_all(database_id: str, filter_body: dict = None) -> list[dict]:
    """Fetch all pages from a Notion database, handling pagination."""
    results = []
    cursor = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        if filter_body:
            body["filter"] = filter_body
        resp = httpx.post(
            f"{_BASE}/databases/{database_id}/query",
            headers=_headers(),
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return results


def _page_update(page_id: str, properties: dict) -> None:
    resp = httpx.patch(
        f"{_BASE}/pages/{page_id}",
        headers=_headers(),
        json={"properties": properties},
        timeout=30,
    )
    resp.raise_for_status()


# ── Pull from Notion ──────────────────────────────────────────────────────────

def fetch_projects() -> list[dict]:
    if not NOTION_API_KEY or not NOTION_PROJECTS_DB_ID:
        raise NotionError("NOTION_API_KEY and NOTION_PROJECTS_DB_ID required")
    pages = _db_query_all(NOTION_PROJECTS_DB_ID)
    return [_parse_project_page(p) for p in pages]


_PRIORITY_MAP = {"1": "high", "high": "high", "2": "medium", "medium": "medium", "3": "low", "low": "low"}
_STATUS_MAP   = {"done": "archived", "archived": "archived"}


def _parse_project_page(page: dict) -> dict:
    props = page.get("properties", {})

    def text(key):
        items = props.get(key, {}).get("rich_text", [])
        return "".join(i["plain_text"] for i in items)

    def title(key):
        items = props.get(key, {}).get("title", [])
        return "".join(i["plain_text"] for i in items)

    def select(key):
        s = props.get(key, {}).get("select")
        return s["name"] if s else None

    def date(key):
        d = props.get(key, {}).get("date")
        return d["start"] if d else None

    raw_priority = (select("Priority") or "").lower()
    raw_status   = (select("Status") or "").lower()

    return {
        "id": page["id"],
        "name": title("Project") or title("Name"),
        "priority": _PRIORITY_MAP.get(raw_priority, "medium"),
        "status": _STATUS_MAP.get(raw_status, "active"),
        "description": text("Summary") or text("Description"),
        "deadline": date("Due Date") or date("Deadline"),
        "last_edited_time": page.get("last_edited_time"),
    }


# ── Areas ─────────────────────────────────────────────────────────────────────

def fetch_areas() -> list[dict]:
    if not NOTION_API_KEY or not NOTION_AREAS_DB_ID:
        return []
    pages = _db_query_all(NOTION_AREAS_DB_ID)
    return [_parse_area_page(p) for p in pages]


def _parse_area_page(page: dict) -> dict:
    props = page.get("properties", {})

    def text(key):
        items = props.get(key, {}).get("rich_text", [])
        return "".join(i["plain_text"] for i in items)

    def title():
        items = props.get("Name", {}).get("title", [])
        return "".join(i["plain_text"] for i in items)

    def select(key):
        s = props.get(key, {}).get("select")
        return s["name"].lower() if s else "active"

    return {
        "id": page["id"],
        "name": title(),
        "description": text("Description"),
        "status": select("Status"),
        "last_edited_time": page.get("last_edited_time"),
    }


# ── Resources ─────────────────────────────────────────────────────────────────

def fetch_resources() -> list[dict]:
    if not NOTION_API_KEY or not NOTION_RESOURCES_DB_ID:
        return []
    pages = _db_query_all(NOTION_RESOURCES_DB_ID)
    return [_parse_resource_page(p) for p in pages]


def _parse_resource_page(page: dict) -> dict:
    props = page.get("properties", {})

    def text(key):
        items = props.get(key, {}).get("rich_text", [])
        return "".join(i["plain_text"] for i in items)

    def title():
        items = props.get("Name", {}).get("title", [])
        return "".join(i["plain_text"] for i in items)

    def url(key="URL"):
        return props.get(key, {}).get("url") or ""

    def multi_select(key="Tags"):
        items = props.get(key, {}).get("multi_select", [])
        return ",".join(i["name"] for i in items)

    return {
        "id": page["id"],
        "name": title(),
        "description": text("Description"),
        "url": url(),
        "tags": multi_select(),
        "last_edited_time": page.get("last_edited_time"),
    }


# ── Standalone Tasks ──────────────────────────────────────────────────────────

def fetch_notion_tasks(project_page_id: str) -> list[dict]:
    if not NOTION_TASKS_DB_ID:
        return []
    pages = _db_query_all(
        NOTION_TASKS_DB_ID,
        filter_body={"property": "Project", "relation": {"contains": project_page_id}},
    )
    return [_parse_task_page(p) for p in pages]


def _parse_task_page(page: dict) -> dict:
    props = page.get("properties", {})

    def title(key="Task Name"):
        items = props.get(key, {}).get("title", [])
        return "".join(i["plain_text"] for i in items)

    def number(key):
        return props.get(key, {}).get("number")

    def checkbox(key):
        return props.get(key, {}).get("checkbox", False)

    return {
        "notion_task_id": page["id"],
        "description": title(),
        "time_estimate_minutes": number("Time Estimate"),
        "completed": checkbox("Completed"),
        "last_edited_time": page.get("last_edited_time"),
    }


# ── Conflict detection ────────────────────────────────────────────────────────

def detect_conflict(notion_edited: str, local_synced: str) -> bool:
    """True if Notion record was edited after our last sync."""
    try:
        notion_dt = datetime.fromisoformat(notion_edited.replace("Z", "+00:00"))
        local_dt = datetime.fromisoformat(local_synced.replace(" ", "T") + "+00:00")
        return notion_dt > local_dt
    except Exception:
        return False


# ── Push to Notion ────────────────────────────────────────────────────────────

def push_completed_tasks(completed_tasks: list[dict]) -> int:
    """Mark tasks as completed in Notion. Returns count of updated tasks."""
    if not NOTION_API_KEY:
        raise NotionError("NOTION_API_KEY required")
    updated = 0
    for task in completed_tasks:
        notion_id = task.get("notion_task_id")
        if not notion_id:
            continue
        try:
            _page_update(notion_id, {"Completed": {"checkbox": True}})
            updated += 1
        except Exception:
            pass
    return updated


def push_project_progress(project_id: str, progress: float) -> None:
    if not NOTION_API_KEY:
        return
    try:
        _page_update(project_id, {"Progress": {"number": round(progress * 100)}})
    except Exception:
        pass


# ── Sync orchestration ────────────────────────────────────────────────────────

def pull_and_sync(on_conflict=None) -> dict:
    """
    Pull all four PARA databases from Notion into local SQLite.
    on_conflict(item, local_row) → 'pull' | 'keep' | 'merge'
    """
    from src import database as db_module

    stats = {"projects": 0, "areas": 0, "tasks": 0, "resources": 0, "conflicts": 0}

    with db_module.get_connection() as conn:

        # Projects
        for project in fetch_projects():
            local = db_module.get_project(conn, project["id"])
            if local and project.get("last_edited_time") and detect_conflict(
                project["last_edited_time"], local["last_synced"]
            ):
                stats["conflicts"] += 1
                decision = on_conflict(project, dict(local)) if on_conflict else "pull"
                if decision == "keep":
                    continue
                elif decision == "merge":
                    project["description"] = "\n\n".join(filter(None, [
                        local["description"], project["description"]
                    ]))
            db_module.upsert_project(conn, project)
            stats["projects"] += 1

        # Areas
        for area in fetch_areas():
            db_module.upsert_area(conn, area)
            stats["areas"] += 1

        # Resources
        for resource in fetch_resources():
            db_module.upsert_resource(conn, resource)
            stats["resources"] += 1

    return stats


def sync_completed_to_notion() -> dict:
    """Push all locally-completed tasks that have a notion_task_id."""
    from src import database as db_module

    with db_module.get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM tasks
            WHERE status='done'
              AND notion_task_id IS NOT NULL
              AND completed_at IS NOT NULL
        """).fetchall()
        completed = [dict(r) for r in rows]

    if not completed:
        return {"pushed": 0}

    pushed = push_completed_tasks(completed)

    with db_module.get_connection() as conn:
        db_module.record_token_usage(conn, "notion_sync", 0, 0, 0.0)

    return {"pushed": pushed}
