"""User profile and system configuration — backed by ~/.xochitl/config.toml.

All persistent settings live here. No other module may hardcode paths, limits,
or model names — read them from this module instead.
"""
# Implements FR-SEC-001 (authorized directory registry)
# Implements FR-MEM-002 (Tier 1 user profile)

import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

CONFIG_DIR = Path.home() / ".xochitl"
CONFIG_PATH = CONFIG_DIR / "config.toml"
DECISION_LOG_PATH = CONFIG_DIR / "decision_log.jsonl"
STATE_DB_PATH = CONFIG_DIR / "state.db"
SESSIONS_DIR = CONFIG_DIR / "sessions"

# Hardcoded — never overridable by the user (NFR-SEC-002 hard boundary)
_FORBIDDEN_ROOTS: list[Path] = [
    Path.home() / ".ssh",
    Path.home() / ".aws",
    Path("C:/Windows"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path("/etc"),
    Path("/sys"),
    Path("/proc"),
]

# Project root — auto-authorized on first boot
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()

_DEFAULT: dict[str, Any] = {
    "profile": {
        "name": "Jason",
        "persona": "Matriarca",
        "language": "en",
    },
    "limits": {
        "wip_limit": 3,
        "intent_confidence_threshold": 0.85,
        "research_time_limit_minutes": 5,
    },
    "models": {
        "router_model": "gemma-4-e2b",
        "reasoning_model": "gemma-4-26b",
        "reranker_model": "qwen3-reranker-0.6b",
        "embedding_model": "nomic-embed-text",
    },
    "authorized_directories": {
        "paths": [
            str(_PROJECT_ROOT),
            str(Path.home() / "Desktop" / "Jason" / "Resource" / "CodeProjects"),
            str(Path.home() / "Documents"),
            str(Path.home() / "Downloads"),
        ],
    },
}


# ── TOML serialization (stdlib tomllib reads; we write manually) ──────────────

def _serialize_toml(config: dict) -> str:
    """Minimal TOML writer for our config structure (flat sections only)."""
    lines: list[str] = [
        "# Xochitl configuration — ~/.xochitl/config.toml",
        f"# Generated {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    for section, values in config.items():
        if not isinstance(values, dict):
            continue
        lines.append(f"[{section}]")
        for key, value in values.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, int):
                lines.append(f"{key} = {value}")
            elif isinstance(value, float):
                lines.append(f"{key} = {value}")
            elif isinstance(value, str):
                escaped = value.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key} = "{escaped}"')
            elif isinstance(value, list):
                items = []
                for item in value:
                    esc = str(item).replace("\\", "\\\\").replace('"', '\\"')
                    items.append(f'"{esc}"')
                if items:
                    lines.append(f"{key} = [")
                    for item in items:
                        lines.append(f"  {item},")
                    lines.append("]")
                else:
                    lines.append(f"{key} = []")
        lines.append("")
    return "\n".join(lines)


# ── Load / write ──────────────────────────────────────────────────────────────

def _load() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        _write(_DEFAULT)
        return _DEFAULT.copy()
    try:
        with open(CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return _DEFAULT.copy()


def _write(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(_serialize_toml(config), encoding="utf-8")


def reload() -> dict[str, Any]:
    """Force a fresh read from disk (use after writes)."""
    return _load()


def get(section: str, key: str, default: Any = None) -> Any:
    return _load().get(section, {}).get(key, default)


# ── Authorized Directory Registry (FR-SEC-001) ───────────────────────────────

def _is_forbidden(path: Path) -> bool:
    resolved = path.resolve()
    for forbidden in _FORBIDDEN_ROOTS:
        try:
            resolved.relative_to(forbidden.resolve())
            return True
        except ValueError:
            pass
    return False


def get_authorized_paths() -> list[Path]:
    # Implements FR-SEC-001
    cfg = _load()
    raw = cfg.get("authorized_directories", {}).get("paths", [])
    return [Path(p) for p in raw]


def is_authorized(path: Path) -> bool:
    """True if path is under an authorized directory and not forbidden."""
    # Implements FR-SEC-001, NFR-SEC-002
    resolved = path.resolve()
    if _is_forbidden(resolved):
        return False
    for auth in get_authorized_paths():
        try:
            resolved.relative_to(auth.resolve())
            return True
        except ValueError:
            pass
    return False


def authorize_directory(path: Path) -> None:
    """Add a directory to the persistent authorized registry."""
    # Implements FR-SEC-001
    resolved = path.resolve()
    if _is_forbidden(resolved):
        raise ValueError(f"Cannot authorize system-protected path: {resolved}")
    cfg = _load()
    paths: list = cfg.setdefault("authorized_directories", {}).setdefault("paths", [])
    str_path = str(resolved)
    if str_path not in paths:
        paths.append(str_path)
        _write(cfg)


def revoke_directory(path: Path) -> bool:
    """Remove a directory from the authorized registry. Returns True if found."""
    # Implements FR-SEC-004
    resolved = str(path.resolve())
    cfg = _load()
    paths: list = cfg.get("authorized_directories", {}).get("paths", [])
    if resolved in paths:
        paths.remove(resolved)
        _write(cfg)
        return True
    return False


# ── Profile accessors (FR-MEM-002) ───────────────────────────────────────────

def get_profile() -> dict[str, Any]:
    # Implements FR-MEM-002
    return _load().get("profile", _DEFAULT["profile"].copy())


def get_wip_limit() -> int:
    # Implements FR-TASK-002
    return int(get("limits", "wip_limit", 3))


def get_confidence_threshold() -> float:
    # Implements FR-ORCH-001
    return float(get("limits", "intent_confidence_threshold", 0.85))


def get_research_time_limit() -> int:
    # Implements FR-RES-001
    return int(get("limits", "research_time_limit_minutes", 5))


def get_model(role: str) -> Optional[str]:
    """role: 'router_model' | 'reasoning_model' | 'reranker_model'"""
    return get("models", role)
