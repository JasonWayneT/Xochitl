"""Secret store for Xochitl — Doppler first, DB second, env var fallback.

Load order at boot (via load()):
  1. Doppler CLI  — if installed and project configured, injects into os.environ
  2. .env file    — loaded into os.environ for backward compat

Per-key read order (via get_secret()):
  1. SQLite DB    — set via `xochitl secrets set KEY`
  2. os.environ   — populated by Doppler or .env above
  3. default      — caller-supplied fallback

This means CI/cloud environments that inject env vars continue to work,
the DB wins on a synced device, and Doppler is invisible to the rest of
the codebase — secrets just appear in os.environ before anything reads them.
"""
# Implements NFR-SEC-001 (secrets never committed to git)
# Implements CR-044 — Doppler-first portable secrets loading

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent


# ── Boot loader ───────────────────────────────────────────────────────────────

def load() -> str:
    """Load secrets into os.environ at boot — Doppler first, .env fallback.

    Called once from cli._boot() before any skill reads credentials.
    Silent regardless of which path is taken.

    Returns:
        'doppler' | 'dotenv' | 'env'
    """
    if _try_doppler():
        return "doppler"
    if _try_dotenv():
        return "dotenv"
    return "env"


def _try_doppler() -> bool:
    """Inject secrets from Doppler CLI into os.environ.

    Returns:
        True if Doppler was available and returned at least one secret.
    """
    try:
        result = subprocess.run(
            ["doppler", "secrets", "download", "--no-file", "--format", "env"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return False

        count = 0
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                count += 1

        logger.debug("secrets: loaded %d keys from Doppler", count)
        return count > 0

    except FileNotFoundError:
        return False  # doppler not installed — silent
    except Exception as exc:
        logger.debug("secrets: Doppler unavailable: %s", exc)
        return False


def _try_dotenv() -> bool:
    """Load .env from project root into os.environ.

    Returns:
        True if .env was found and loaded.
    """
    try:
        from dotenv import load_dotenv
        env_path = _PROJECT_ROOT / ".env"
        if not env_path.exists():
            return False
        load_dotenv(env_path, override=False)
        logger.debug("secrets: loaded from .env at %s", env_path)
        return True
    except Exception as exc:
        logger.debug("secrets: .env load failed: %s", exc)
        return False


# ── Per-key API (DB → env → default) ─────────────────────────────────────────

def get_secret(key: str, default: str = "") -> str:
    """Read a secret — DB first, then os.environ, then default.

    Args:
        key: Secret name e.g. 'ANTHROPIC_API_KEY'.
        default: Value returned if key is not found anywhere.

    Returns:
        Secret value string.
    """
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
    """Store a secret in the local SQLite DB.

    Args:
        key: Secret name.
        value: Secret value.
    """
    from src.database import get_connection, set_secret_db
    with get_connection() as conn:
        set_secret_db(conn, key, value)


def delete_secret(key: str) -> bool:
    """Remove a secret from the local SQLite DB.

    Args:
        key: Secret name.

    Returns:
        True if the key existed and was deleted.
    """
    from src.database import get_connection, delete_secret_db
    with get_connection() as conn:
        return delete_secret_db(conn, key)


def list_secrets() -> list[dict]:
    """Return all secrets stored in the local SQLite DB (keys only, no values).

    Returns:
        List of dicts with 'key' and metadata fields.
    """
    from src.database import get_connection, list_secrets_db
    with get_connection() as conn:
        return [dict(r) for r in list_secrets_db(conn)]


def migrate_from_env(env_path: Path) -> list[str]:
    """Import all KEY=VALUE pairs from a .env file into the secret store.

    Args:
        env_path: Path to the .env file to import.

    Returns:
        List of key names that were migrated.
    """
    if not env_path.exists():
        return []
    migrated: list[str] = []
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key   = key.strip()
        value = value.strip()
        if key and value:
            set_secret(key, value)
            migrated.append(key)
    return migrated
