"""Sandboxed file operations, permission gating, and JSONL decision logging."""
# Implements FR-SEC-001 (authorized directory registry via config.py)
# Implements FR-SEC-002 (permission-gated writes — ALL writes, not just overwrites)
# Implements FR-SEC-003 (JSONL decision log at ~/.xochitl/decision_log.jsonl)
# Implements FR-SEC-004 (directory access revocation)
# Implements FR-SEC-005 (SSRF protection — validate_outbound_url)
# Implements NFR-SEC-002 (100% of write operations gated)
# Implements NFR-SEC-003 (resolve-then-validate for outbound URL guard)
# Implements NFR-AUD-001 (log entry appended within 100ms of action)

import ipaddress
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from src.config import (
    is_authorized,
    authorize_directory,
    revoke_directory,
    get_authorized_paths,
    DECISION_LOG_PATH,
    CONFIG_DIR,
)


# ── SSRF protection (FR-SEC-005, NFR-SEC-003) ────────────────────────────────

_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

# Private, reserved, and infrastructure IP ranges that must never be fetched.
# Covers loopback, RFC 1918, link-local / cloud metadata (IMDS), CGN, documentation
# ranges, and IPv6 ULA / link-local.
_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("0.0.0.0/8"),        # "This" network (RFC 1122)
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918 private
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT (RFC 6598)
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / AWS·GCP·Azure IMDS
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918 private
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918 private
    ipaddress.ip_network("198.51.100.0/24"),   # Documentation TEST-NET-2 (RFC 5737)
    ipaddress.ip_network("203.0.113.0/24"),    # Documentation TEST-NET-3 (RFC 5737)
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 ULA (fc00::/8 + fd00::/8)
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]


def validate_outbound_url(url: str) -> str:
    """Validate that *url* is safe to fetch (SSRF guard).

    Checks:
    1. Scheme must be ``http`` or ``https``.
    2. Hostname must resolve (via ``socket.getaddrinfo``) to at least one IP.
    3. Every resolved IP must fall outside all private / reserved ranges.

    Returns the original *url* unchanged if all checks pass.
    Raises ``XochitlPermissionError`` on any violation.

    Implements FR-SEC-005, NFR-SEC-003.  See also ADR-002.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise XochitlPermissionError(
            f"SSRF: scheme '{parsed.scheme}' not allowed (only http/https)"
        )

    host = parsed.hostname
    if not host:
        raise XochitlPermissionError(f"SSRF: could not extract hostname from URL: {url!r}")

    # Resolve hostname → IP(s); raises on DNS failure (treated as blocked).
    try:
        addr_results = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise XochitlPermissionError(
            f"SSRF: hostname resolution failed for '{host}': {exc}"
        ) from exc

    for _family, _type, _proto, _canonname, sockaddr in addr_results:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue  # malformed address — skip rather than crash
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise XochitlPermissionError(
                    f"SSRF: host '{host}' resolves to blocked address {ip} (range {network})"
                )

    return url


# ── Exceptions ────────────────────────────────────────────────────────────────

class XochitlPermissionError(Exception):
    pass


# Keep old name as alias so existing catch-sites don't break
PermissionError = XochitlPermissionError


class RequiresConfirmation(Exception):
    def __init__(self, prompt: str):
        self.prompt = prompt
        super().__init__(prompt)


# ── JSONL Decision Log (FR-SEC-003, NFR-AUD-001) ─────────────────────────────

def log_decision(
    intent: str,
    tool: str,
    rationale: str,
    outcome: str,
    status: str,
    session_id: Optional[str] = None,
    path: Optional[str] = None,
) -> None:
    """Append one structured entry to the JSONL decision log.

    All keys use snake_case (NFR-AUD-001 / architecture naming standards).
    The write is a single append — atomic enough for append-mode files.
    """
    # Implements FR-SEC-003, NFR-AUD-001
    entry: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id or "",
        "intent": intent,
        "tool": tool,
        "rationale": rationale,
        "outcome": outcome,
        "status": status,  # success | blocked | cancelled | error | pending
    }
    if path:
        entry["path"] = path

    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with DECISION_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Log failures must never crash the caller (NFR-AUD-001)


# ── Path authorization (FR-SEC-001, NFR-SEC-002) ─────────────────────────────

def _is_allowed(path: Path) -> bool:
    """True if path falls under an authorized directory in config.toml."""
    # Implements FR-SEC-001 — delegates to config.py registry
    return is_authorized(path)


# ── File operations (FR-SEC-002) ──────────────────────────────────────────────

def read_file(path: Path) -> str:
    """Read a file — permitted for any authorized path without confirmation."""
    # Implements FR-SEC-002 (reads are open; writes are gated)
    if not _is_allowed(path):
        log_decision(
            intent="file_read",
            tool="read_file",
            rationale=f"Read requested on unauthorized path: {path}",
            outcome="blocked",
            status="blocked",
            path=str(path),
        )
        raise XochitlPermissionError(f"Access denied: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def write_file(path: Path, content: str, confirmed: bool = False) -> None:
    """Write a file — requires authorization AND explicit y/n confirmation.

    Every write attempt is logged regardless of outcome (NFR-AUD-001).
    Applies to both new files and overwrites (spec: ALL writes gated).
    """
    # Implements FR-SEC-002, NFR-SEC-002
    if not _is_allowed(path):
        log_decision(
            intent="file_write",
            tool="write_file",
            rationale=f"Write to unauthorized path: {path}",
            outcome="blocked — path not in authorized registry",
            status="blocked",
            path=str(path),
        )
        raise XochitlPermissionError(f"Access denied: {path}")

    if not confirmed:
        log_decision(
            intent="file_write",
            tool="write_file",
            rationale=f"Confirmation required before writing to {path}",
            outcome="awaiting user confirmation",
            status="pending",
            path=str(path),
        )
        raise RequiresConfirmation(f"Write to {path}?")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log_decision(
        intent="file_write",
        tool="write_file",
        rationale=f"User confirmed write to {path}",
        outcome="file written successfully",
        status="success",
        path=str(path),
    )


def delete_file(path: Path, confirmed: bool = False) -> None:
    """Delete a file — requires authorization AND explicit confirmation."""
    # Implements FR-SEC-002, NFR-SEC-002
    if not _is_allowed(path):
        log_decision(
            intent="file_delete",
            tool="delete_file",
            rationale=f"Delete on unauthorized path: {path}",
            outcome="blocked",
            status="blocked",
            path=str(path),
        )
        raise XochitlPermissionError(f"Access denied: {path}")

    if not confirmed:
        log_decision(
            intent="file_delete",
            tool="delete_file",
            rationale=f"Confirmation required to delete {path}",
            outcome="awaiting user confirmation",
            status="pending",
            path=str(path),
        )
        raise RequiresConfirmation(f"Delete {path}? This cannot be undone.")

    path.unlink()
    log_decision(
        intent="file_delete",
        tool="delete_file",
        rationale=f"User confirmed deletion of {path}",
        outcome="file deleted",
        status="success",
        path=str(path),
    )


def list_directory(path: Path) -> list[str]:
    """List a directory — permitted for any authorized path."""
    # Implements FR-SEC-002 (directory reads are open)
    if not _is_allowed(path):
        raise XochitlPermissionError(f"Access denied: {path}")
    return [str(p) for p in sorted(path.iterdir())]


# ── Terminal confirmation ─────────────────────────────────────────────────────

def confirm_in_terminal(prompt: str) -> bool:
    """Block and ask the user to type 'yes' before a destructive action."""
    print("\n  CONFIRMATION REQUIRED")
    print(f"  {prompt}")
    response = input("\n  Type 'yes' to proceed: ").strip().lower()
    confirmed = response in ("yes", "y")
    return confirmed


# ── Slash command handlers (FR-SEC-001, FR-SEC-004) ──────────────────────────

def cmd_authorize(path_str: str) -> str:
    """Handle /authorize <path> — add directory to persistent registry."""
    # Implements FR-SEC-001
    if not path_str.strip():
        return "Usage: /authorize <path>"
    path = Path(path_str.strip()).resolve()
    if not path.exists():
        return f"[bold red]✘[/bold red] Path does not exist: {path}"
    if not path.is_dir():
        return f"[bold red]✘[/bold red] Not a directory: {path}"
    try:
        authorize_directory(path)
        log_decision(
            intent="authorize_directory",
            tool="cmd_authorize",
            rationale=f"User authorized directory: {path}",
            outcome="added to registry",
            status="success",
            path=str(path),
        )
        return f"[bold green]✔[/bold green] Claro, authorized: {path}"
    except ValueError as e:
        return f"[bold red]✘[/bold red] Ay no, {e}"


def cmd_revoke(path_str: str) -> str:
    """Handle /revoke <path> — remove directory from registry immediately."""
    # Implements FR-SEC-004
    if not path_str.strip():
        return "Usage: /revoke <path>"
    path = Path(path_str.strip()).resolve()
    removed = revoke_directory(path)
    if removed:
        log_decision(
            intent="revoke_directory",
            tool="cmd_revoke",
            rationale=f"User revoked access to: {path}",
            outcome="removed from registry",
            status="success",
            path=str(path),
        )
        return f"[bold green]✔[/bold green] Access to {path} has been revoked."
    return f"That path was not in the registry."


def cmd_list_registry() -> str:
    """Handle /registry — show all authorized directories."""
    # Implements FR-SEC-001
    paths = get_authorized_paths()
    if not paths:
        return (
            "No authorized directories.\n"
            "Use [bold]/authorize <path>[/bold] to add one."
        )
    lines = ["[bold]Authorized directories:[/bold]"]
    for p in paths:
        marker = "[green]✓[/green]" if p.exists() else "[red]✗ (missing)[/red]"
        lines.append(f"  {marker} {p}")
    return "\n".join(lines)


def cmd_audit(n: int = 20) -> str:
    """Handle /audit [N] — tail the JSONL decision log."""
    # Implements FR-SEC-003
    if not DECISION_LOG_PATH.exists():
        return "[dim]No decision log yet — actions will appear here as they run.[/dim]"
    raw_lines = DECISION_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    recent = raw_lines[-n:] if len(raw_lines) > n else raw_lines
    rows = []
    for line in recent:
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            status = entry.get("status", "?")
            tool = entry.get("tool", "?")
            outcome = entry.get("outcome", "")[:60]
            color = "green" if status == "success" else "red" if status == "blocked" else "yellow"
            rows.append(f"  [{ts}] [[{color}]{status:9}[/{color}]] {tool}: {outcome}")
        except Exception:
            rows.append(f"  {line[:100]}")
    header = f"[bold]Last {len(rows)} of {len(raw_lines)} decisions:[/bold]"
    return header + "\n" + "\n".join(rows)
