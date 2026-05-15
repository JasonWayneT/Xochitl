"""Secret store backed by SQLite — falls back to env vars for compatibility.

Load order: DB → env var → default
This means CI/Docker environments that inject env vars continue to work,
and the DB wins on a synced device where secrets have been migrated.
"""
# Implements NFR-SEC-001 (secrets never committed to git — stored in gitignored DB)

import os
from pathlib import Path
from typing import Optional


def get_secret(key: str, default: str = "") -> str:
    try:
        from src.database import get_connection, get_secret_db
        with get_connection() as conn:
            val = get_secret_db(conn, key)
            if val is not None:
                return val
    except Exception:
        pass
    return os.getenv(key, default)


def set_secret(key: str, value: str) -> None:
    from src.database import get_connection, set_secret_db
    with get_connection() as conn:
        set_secret_db(conn, key, value)


def delete_secret(key: str) -> bool:
    from src.database import get_connection, delete_secret_db
    with get_connection() as conn:
        return delete_secret_db(conn, key)


def list_secrets() -> list[dict]:
    from src.database import get_connection, list_secrets_db
    with get_connection() as conn:
        return [dict(r) for r in list_secrets_db(conn)]


def migrate_from_env(env_path: Path) -> list[str]:
    """Import all KEY=VALUE pairs from a .env file into the secret store."""
    if not env_path.exists():
        return []
    migrated: list[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            set_secret(key, value)
            migrated.append(key)
    return migrated
