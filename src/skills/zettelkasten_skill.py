"""Zettelkasten skill — vault mode switching, note creation, processing pipeline."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.skills.base import Skill

# ── Module-level session state ────────────────────────────────────────────────

_zettel_mode: bool = False
_vault_path: Optional[Path] = None
_session_start: Optional[datetime] = None
_literature_touched: list[str] = []   # filenames touched this session
_notes_processed: list[str] = []      # permanent notes processed this session

_ENTER_PHRASES = [
    "let's work on zettles", "lets work on zettles",
    "zettel mode", "open the vault", "work on notes",
    "work on my notes", "let's do some zettles", "lets do some zettles",
    "work on zettelkasten", "open zettelkasten",
    "initiate a zettle", "initiate zettel", "initiate a zettelkasten",
    "start a zettel", "start zettel", "create a zettel", "set up a zettel",
    "set up zettel", "new zettel", "new zettelkasten",
]
_EXIT_PHRASES = [
    "exit zettel", "leave zettel", "done with zettles", "close the vault",
    "done for today", "back to normal", "exit vault",
]


_VAULT_CONFIG = Path.home() / ".xochitl" / "vault_config.json"

# Folders that signal a zettelkasten vault structure
_VAULT_MARKERS = {"Fleeting", "Permanent", "Literature", "_System", ".obsidian"}

# Well-known roots to scan for vaults (most specific first)
_SCAN_ROOTS = [
    Path.home() / "Desktop" / "Jason" / "Resource" / "Vaults",
    Path.home() / "Documents" / "Vaults",
    Path.home() / "Documents",
    Path.home() / "Desktop",
    Path.home(),
]


def _looks_like_vault(path: Path) -> bool:
    """Return True if the folder contains at least 2 zettelkasten marker subdirs."""
    if not path.is_dir():
        return False
    try:
        children = {p.name for p in path.iterdir()}
    except PermissionError:
        return False
    return len(_VAULT_MARKERS & children) >= 2


def _scan_for_vaults(root: Path) -> list[Path]:
    """Return immediate children of root that look like vaults."""
    if not root.exists():
        return []
    try:
        return [p for p in root.iterdir() if _looks_like_vault(p)]
    except PermissionError:
        return []


def _load_saved_vault() -> Optional[Path]:
    """Return the last vault path saved by Xochitl, if it still exists."""
    try:
        if _VAULT_CONFIG.exists():
            data = json.loads(_VAULT_CONFIG.read_text(encoding="utf-8"))
            p = Path(data.get("last_vault", ""))
            if p and p.exists():
                return p
    except Exception:
        pass
    return None


def _save_vault(path: Path) -> None:
    """Persist vault path so Xochitl remembers it across sessions."""
    try:
        _VAULT_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if _VAULT_CONFIG.exists():
            existing = json.loads(_VAULT_CONFIG.read_text(encoding="utf-8"))
        existing["last_vault"] = str(path)
        # Keep a short history (most recent 5)
        history: list[str] = existing.get("history", [])
        if str(path) not in history:
            history.insert(0, str(path))
        existing["history"] = history[:5]
        _VAULT_CONFIG.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        pass


def _get_vault() -> Optional[Path]:
    """Resolve vault path using a priority chain:

    1. Already set this session (module-level _vault_path)
    2. VAULT_PATH env var
    3. Last vault saved by Xochitl (~/.xochitl/vault_config.json)
    4. Auto-scan of well-known locations for vault-like folder structures
    """
    global _vault_path
    if _vault_path is not None:
        return _vault_path

    # 1. Env var
    raw = os.environ.get("VAULT_PATH", "").strip()
    if raw:
        _vault_path = Path(raw)
        return _vault_path

    # 2. Remembered from last session
    saved = _load_saved_vault()
    if saved:
        _vault_path = saved
        return _vault_path

    # 3. Auto-scan known locations
    for root in _SCAN_ROOTS:
        found = _scan_for_vaults(root)
        if found:
            # Prefer the most recently modified vault
            found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            _vault_path = found[0]
            return _vault_path

    return None


def is_zettel_mode() -> bool:
    return _zettel_mode


def record_literature_touch(filename: str) -> None:
    if filename not in _literature_touched:
        _literature_touched.append(filename)


def record_note_processed(filename: str) -> None:
    if filename not in _notes_processed:
        _notes_processed.append(filename)


# ── Vault helpers ─────────────────────────────────────────────────────────────

def _count_folder(folder: Path) -> int:
    if not folder.exists():
        return 0
    return sum(1 for f in folder.iterdir() if f.suffix == ".md")


def _scan_and_scaffold(vault: Path) -> int:
    """Find permanent notes missing frontmatter and scaffold them. Returns count."""
    perm_dir = vault / "Permanent"
    if not perm_dir.exists():
        return 0
    scaffolded = 0
    for note_file in perm_dir.glob("*.md"):
        content = note_file.read_text(encoding="utf-8")
        if not content.startswith("---"):
            _scaffold_existing(note_file, content)
            scaffolded += 1
    return scaffolded


def _scaffold_existing(note_file: Path, existing_content: str) -> None:
    """Prepend frontmatter to an unscaffolded permanent note."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    note_id = _next_id(note_file.parent.parent)
    frontmatter = f"""---
id: {note_id}
created: {today}
source:
tags: []
status: seedling
---

"""
    note_file.write_text(frontmatter + existing_content, encoding="utf-8")


def _next_id(vault: Path) -> str:
    """Generate next YYYYMMDD-NNN id by counting existing permanent notes."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    perm_dir = vault / "Permanent"
    if not perm_dir.exists():
        return f"{today}-001"
    existing = [
        f for f in perm_dir.glob("*.md")
        if f.read_text(encoding="utf-8").startswith("---")
    ]
    n = len(existing) + 1
    return f"{today}-{n:03d}"


def _count_parked_questions(vault: Path) -> int:
    pq = vault / "_System" / "Parked Questions.md"
    if not pq.exists():
        return 0
    content = pq.read_text(encoding="utf-8")
    return content.count("| open |")


def _session_status(vault: Path) -> str:
    fleeting = _count_folder(vault / "Fleeting")
    permanent = _count_folder(vault / "Permanent")
    parked = _count_parked_questions(vault)
    today = datetime.now()
    sunday_note = " It's Sunday — say 'weekly review' when ready." if today.weekday() == 6 else ""

    parts = []
    if fleeting:
        parts.append(f"{fleeting} fleeting note{'s' if fleeting != 1 else ''}")
    if permanent:
        parts.append(f"{permanent} permanent note{'s' if permanent != 1 else ''}")
    if parked:
        parts.append(f"{parked} parked question{'s' if parked != 1 else ''}")

    if not parts:
        summary = "Vault is clean. Capture something new."
    else:
        summary = ", ".join(parts) + "."

    return summary + sunday_note


# ── Mode entry / exit ─────────────────────────────────────────────────────────

def enter_mode(path: Optional[str] = None) -> str:
    global _zettel_mode, _vault_path, _session_start, _literature_touched, _notes_processed
    _zettel_mode = True
    _session_start = datetime.now(timezone.utc)
    _literature_touched = []
    _notes_processed = []

    # Explicit path overrides everything — resolve and save it
    if path:
        _vault_path = Path(path).resolve()
        _save_vault(_vault_path)

    vault = _get_vault()
    if vault is None:
        # Offer to scaffold in cwd
        cwd = Path.cwd()
        return (
            "[ZETTEL MODE ON]\n"
            f"No vault found. I checked your known Vaults folders and didn't find "
            f"a zettelkasten structure.\n\n"
            f"Options:\n"
            f"  • Say 'scaffold vault here' → create one in {cwd}\n"
            f"  • Say 'scaffold vault at [path]' → create one at a specific location\n"
            f"  • Set VAULT_PATH in .env to always point here"
        )

    # Save so next session finds it automatically
    _save_vault(vault)

    scaffolded = _scan_and_scaffold(vault)
    status = _session_status(vault)
    scaffold_note = f" Scaffolded {scaffolded} unformatted note{'s' if scaffolded != 1 else ''}." if scaffolded else ""
    discovered = "" if os.environ.get("VAULT_PATH") else f" (auto-discovered: {vault})"
    return f"[ZETTEL MODE]{scaffold_note}{discovered}\n{status}"


def exit_mode() -> str:
    global _zettel_mode
    _zettel_mode = False

    _write_session_record()

    # Session-close trigger: if literature was touched and no permanent
    # note was processed, ask for one claim before exiting.
    if _literature_touched and not _notes_processed:
        sources = ", ".join(_literature_touched)
        return (
            f"[ZETTEL MODE OFF]\n\n"
            f"You read from {sources} this session but didn't process a permanent note.\n"
            f"What claim survived this session? (skip to exit cleanly)"
        )

    return "[ZETTEL MODE OFF] Back to normal."


def _write_session_record() -> None:
    """Append a session record to _System/Decision Log for metrics tracking."""
    vault = _get_vault()
    if vault is None or _session_start is None:
        return
    log_file = vault / "_System" / "Decision Log.md"
    if not log_file.exists():
        return
    end = datetime.now(timezone.utc)
    duration = int((end - _session_start).total_seconds() // 60)
    entry = (
        f"\n## SESSION {_session_start.strftime('%Y-%m-%dT%H:%M')}Z\n"
        f"**Duration:** {duration}m\n"
        f"**Literature touched:** {', '.join(_literature_touched) or 'none'}\n"
        f"**Notes processed:** {len(_notes_processed)}\n"
        f"**Outcome:** {'permanent note created' if _notes_processed else 'capture only'}\n"
    )
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


# ── Vault status ──────────────────────────────────────────────────────────────

def vault_status() -> str:
    vault = _get_vault()
    if vault is None:
        return "No vault configured. Set VAULT_PATH in .env."
    if not vault.exists():
        return f"Vault path not found: {vault}"
    return _session_status(vault)


# ── Note creation ─────────────────────────────────────────────────────────────

def new_literature_note(source: str) -> str:
    vault = _get_vault()
    if vault is None:
        return "No vault configured."

    lit_dir = vault / "Literature"
    lit_dir.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^\w\s-]", "", source.lower()).strip()
    slug = re.sub(r"[\s]+", "-", slug)
    note_file = lit_dir / f"{slug}.md"

    if note_file.exists():
        return f"Literature note already exists: Literature/{note_file.name}"

    today = datetime.now(timezone.utc).strftime("%B %-d").replace("-0", "-") if os.name != "nt" else datetime.now(timezone.utc).strftime("%B %d").replace(" 0", " ")
    content = f"# {source}\n\n## {today}\n"
    note_file.write_text(content, encoding="utf-8")
    return f"Created Literature/{note_file.name} — open it in Obsidian and start capturing."


def new_permanent_note(claim: str) -> str:
    vault = _get_vault()
    if vault is None:
        return "No vault configured."

    perm_dir = vault / "Permanent"
    perm_dir.mkdir(parents=True, exist_ok=True)

    slug = re.sub(r"[^\w\s-]", "", claim.lower()).strip()
    slug = re.sub(r"[\s]+", "-", slug)[:80]
    note_file = perm_dir / f"{slug}.md"

    if note_file.exists():
        return f"A note with that name already exists: Permanent/{note_file.name}"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    note_id = _next_id(vault)

    content = f"""---
id: {note_id}
created: {today}
source:
tags: []
status: seedling
---

# {claim}

"""
    note_file.write_text(content, encoding="utf-8")
    return f"Created Permanent/{note_file.name} — open it in Obsidian and write the body."


def _extract_path_hint(user_input: str) -> Optional[str]:
    """Pull a vault path from a natural-language message.

    Handles:
      - Absolute Windows/Unix paths   → "at C:\\Vaults\\Vault-001"
      - "in this folder" / "here"     → cwd
      - "in [folder name]"            → scan known roots for that name
      - Named vault in history        → matched by partial name
    Returns None if nothing useful found (caller uses auto-detect).
    """
    # 1. Explicit absolute path in the message
    m = re.search(r'([A-Za-z]:[/\\][\w/\\\-. ]+|/(?:home|Users)/[\w/\-. ]+)', user_input)
    if m:
        return m.group(1).strip()

    q = user_input.lower()

    # 2. "here" / "this folder" / "current folder" → cwd
    if re.search(r'\b(here|this folder|this directory|current folder|current directory)\b', q):
        return str(Path.cwd())

    # 3. "in [name]" / "at [name]" — try to find a matching vault in known roots
    m = re.search(r'\b(?:in|at|inside|from)\s+(?:my\s+)?(["\']?)(\w[\w\- ]{1,40})\1', q)
    if m:
        hint = m.group(2).strip()
        for root in _SCAN_ROOTS:
            if not root.exists():
                continue
            try:
                for child in root.iterdir():
                    if hint in child.name.lower() and _looks_like_vault(child):
                        return str(child)
                    # Match even if not yet scaffolded — user may mean a bare folder
                    if hint in child.name.lower() and child.is_dir():
                        return str(child)
            except PermissionError:
                continue

    # 4. Check vault history for a name match
    try:
        if _VAULT_CONFIG.exists():
            data = json.loads(_VAULT_CONFIG.read_text(encoding="utf-8"))
            for saved in data.get("history", []):
                p = Path(saved)
                if hint_in_history := re.search(r'\b(?:in|at|inside|from)\s+(?:my\s+)?(["\']?)(\w[\w\- ]{1,40})\1', q):
                    hint = hint_in_history.group(2).strip()
                    if hint in p.name.lower() and p.exists():
                        return str(p)
    except Exception:
        pass

    return None


# ── Skill class ───────────────────────────────────────────────────────────────

class ZettelkastenSkill(Skill):

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()

        # Explicit mode entry/exit — high confidence
        if any(p in q for p in _ENTER_PHRASES):
            return 0.95
        if any(p in q for p in _EXIT_PHRASES):
            return 0.95 if _zettel_mode else 0.0

        # Already in zettel mode — handle note/vault commands
        if _zettel_mode:
            if any(kw in q for kw in [
                "new note", "new permanent", "new literature", "process",
                "what's in my inbox", "inbox", "fleeting", "vault status",
                "what should i do", "connecting", "serendipity", "weekly review",
            ]):
                return 0.9
            return 0.3

        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        q = user_input.lower()
        if any(p in q for p in _ENTER_PHRASES):
            return "Entering zettelkasten mode — scanning vault."
        if any(p in q for p in _EXIT_PHRASES):
            return "Leaving zettelkasten mode."
        return "Working in your vault."

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        from src.skills.zettelkasten_process import (
            process_note, process_fleeting, serendipity_scan,
            clarity_check, apply_pending, get_pending,
        )
        from src.skills.zettelkasten_scaffold import scaffold_vault
        from src.skills.zettelkasten_moc import generate_moc

        q = user_input.lower().strip()

        # ── Mode switching ────────────────────────────────────────────────────
        if any(p in q for p in _ENTER_PHRASES):
            path = _extract_path_hint(user_input)
            return enter_mode(path)
        if any(p in q for p in _EXIT_PHRASES):
            return exit_mode()

        # ── Accept / confirm pending process ─────────────────────────────────
        if q in ("accept", "yes", "confirm", "ok", "looks good") or q.startswith("accept "):
            edits = user_input[len("accept"):].strip() if q.startswith("accept ") else None
            return apply_pending(edits)

        # ── Vault status ──────────────────────────────────────────────────────
        if "vault status" in q or ("what should i do" in q and _zettel_mode):
            return vault_status()

        # ── Scaffold / initiate vault ─────────────────────────────────────────
        _scaffold_triggers = (
            "scaffold vault", "create vault", "initiate a zettle", "initiate zettel",
            "initiate a zettelkasten", "start a zettel", "start zettel",
            "create a zettel", "set up a zettel", "set up zettel",
            "new zettel", "new zettelkasten",
        )
        if any(t in q for t in _scaffold_triggers):
            # Extract a Windows or Unix absolute path from the original user input
            path_match = re.search(
                r'([A-Za-z]:[/\\][\w/\\\-. ]+|/(?:home|Users)/[\w/\-. ]+)',
                user_input,
            )
            if not path_match:
                # Fallback: anything after "at", "in", or "project at"
                path_match = re.search(
                    r'(?:scaffold|create|initiate|start|set up|new)'
                    r'.*?(?:vault|zettel(?:kasten)?)'
                    r'(?:\s+(?:at|in|project at|project in|here))?\s+([\w/\\\-. :]+)',
                    user_input, re.IGNORECASE,
                )
            path = path_match.group(1).strip() if path_match else None
            return scaffold_vault(path)

        # ── New permanent note ────────────────────────────────────────────────
        if "new note:" in q or "new permanent" in q:
            claim_match = re.search(r"new (?:note|permanent(?: note)?):\s*(.+)", user_input, re.IGNORECASE)
            if claim_match:
                return new_permanent_note(claim_match.group(1).strip())
            return "Usage: 'new note: [your claim here]'"

        # ── New literature note ───────────────────────────────────────────────
        if "new literature" in q or "literature note" in q:
            source_match = re.search(r"(?:new )?literature(?: note)?:\s*(.+)", user_input, re.IGNORECASE)
            if source_match:
                return new_literature_note(source_match.group(1).strip())
            return "Usage: 'new literature: [source title]'"

        # ── Process note ──────────────────────────────────────────────────────
        if any(kw in q for kw in ["process note", "process that", "process this", "process my note"]):
            fname_match = re.search(r"process (?:note|that|this|my note)?\s*([\w-]+(?:\.md)?)?", q)
            fname = fname_match.group(1) if fname_match and fname_match.group(1) else None
            return process_note(fname)

        if q == "process" and _zettel_mode:
            return process_note()

        # ── Process fleeting ──────────────────────────────────────────────────
        if "process fleeting" in q or ("inbox" in q and _zettel_mode) or "what's in my inbox" in q:
            return process_fleeting()

        # ── Clarity check ─────────────────────────────────────────────────────
        if "clarity check" in q or "clarity" in q and _zettel_mode and get_pending():
            fname_match = re.search(r"clarity(?: check)?\s*([\w-]+(?:\.md)?)?", q)
            fname = fname_match.group(1) if fname_match and fname_match.group(1) else None
            return clarity_check(fname)

        # ── Serendipity ───────────────────────────────────────────────────────
        if any(kw in q for kw in ["serendipity", "what's connecting", "what is connecting", "connections"]):
            return serendipity_scan()

        # ── Generate MOC ──────────────────────────────────────────────────────
        if "generate moc" in q or "moc " in q or q.startswith("moc"):
            topic_match = re.search(r"(?:generate )?moc\s+(.+)", q)
            if topic_match:
                return generate_moc(topic_match.group(1).strip())
            return "Usage: 'generate moc [topic]'"

        if _zettel_mode:
            return (
                "In zettel mode. Commands:\n"
                "  new note: [claim]        — create a permanent note\n"
                "  new literature: [source] — create a literature note\n"
                "  process note             — run pipeline on latest/named note\n"
                "  accept                   — confirm pending suggestions\n"
                "  process fleeting         — triage inbox\n"
                "  clarity check            — clarity coaching on current note\n"
                "  what's connecting        — serendipity scan\n"
                "  generate moc [topic]     — build a Map of Content\n"
                "  vault status             — current counts\n"
                "  done for today           — exit zettel mode"
            )

        return "Say 'let's work on zettles' to enter zettel mode."

    def tool_definition(self) -> dict:
        return {
            "name": "ZettelkastenSkill",
            "description": "Manages a Zettelkasten vault — mode switching, note creation, processing, and serendipity.",
            "when": (
                "User mentions zettelkasten, zettel, or vault in any form — including "
                "'initiate a zettle project', 'set up a zettelkasten', 'create a zettel vault', "
                "'let's work on zettles', 'zettel mode', 'open the vault', "
                "'new note', 'process my notes', 'what's connecting', or any vault/note command. "
                "Also handles 'inbox' and 'what should I do' when in zettel mode."
            ),
            "params": {
                "action": "enter_mode | exit_mode | vault_status | new_note | new_literature | process",
                "claim": "The claim title for a new permanent note (title-as-argument)",
                "source": "The source name for a new literature note",
            },
        }
