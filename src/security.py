"""Sandboxed file operations, confirmation gates, and audit logging."""

from pathlib import Path
from typing import Optional

from src import database as db

_BASE = Path(__file__).parent.parent

ALLOWED_ROOTS = [
    Path.home(),
    Path.home() / "Desktop" / "Jason" / "Resource" / "Code Projects",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    _BASE,
]

FORBIDDEN_ROOTS = [
    Path.home() / ".ssh",
    Path.home() / ".aws",
    Path("C:/Windows"),
    Path("C:/Program Files"),
]


class PermissionError(Exception):
    pass


class RequiresConfirmation(Exception):
    def __init__(self, prompt: str):
        self.prompt = prompt
        super().__init__(prompt)


def _is_allowed(path: Path) -> bool:
    resolved = path.resolve()
    for forbidden in FORBIDDEN_ROOTS:
        try:
            resolved.relative_to(forbidden.resolve())
            return False
        except ValueError:
            pass
    for allowed in ALLOWED_ROOTS:
        try:
            resolved.relative_to(allowed.resolve())
            return True
        except ValueError:
            pass
    return False


def read_file(path: Path) -> str:
    if not _is_allowed(path):
        raise PermissionError(f"Access denied: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def write_file(path: Path, content: str, confirmed: bool = False) -> None:
    if not _is_allowed(path):
        raise PermissionError(f"Access denied: {path}")
    if path.exists() and not confirmed:
        raise RequiresConfirmation(f"File exists: {path}. Confirm overwrite?")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _audit("write", path)


def delete_file(path: Path, confirmed: bool = False) -> None:
    if not _is_allowed(path):
        raise PermissionError(f"Access denied: {path}")
    if not confirmed:
        raise RequiresConfirmation(f"Delete {path}? This cannot be undone.")
    path.unlink()
    _audit("delete", path)


def list_directory(path: Path) -> list[str]:
    if not _is_allowed(path):
        raise PermissionError(f"Access denied: {path}")
    return [str(p) for p in sorted(path.iterdir())]


def _audit(operation: str, path: Path) -> None:
    try:
        with db.get_connection() as conn:
            db.audit(conn, operation, str(path))
    except Exception:
        pass


def confirm_in_terminal(prompt: str) -> bool:
    """Pause and ask the user to type 'yes' to proceed."""
    print(f"\n  CONFIRMATION REQUIRED")
    print(f"  {prompt}")
    response = input("\n  Type 'yes' to proceed: ").strip().lower()
    return response in ("yes", "y")
