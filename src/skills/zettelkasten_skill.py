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
]
_EXIT_PHRASES = [
    "exit zettel", "leave zettel", "done with zettles", "close the vault",
    "done for today", "back to normal", "exit vault",
]


def _get_vault() -> Optional[Path]:
    global _vault_path
    if _vault_path is None:
        raw = os.environ.get("VAULT_PATH", "")
        if raw:
            _vault_path = Path(raw)
    return _vault_path


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

def enter_mode() -> str:
    global _zettel_mode, _session_start, _literature_touched, _notes_processed
    _zettel_mode = True
    _session_start = datetime.now(timezone.utc)
    _literature_touched = []
    _notes_processed = []

    vault = _get_vault()
    if vault is None:
        return (
            "[ZETTEL MODE ON]\n"
            "No vault found. Set VAULT_PATH in .env or say 'scaffold vault here' "
            "to create one in the current directory."
        )

    scaffolded = _scan_and_scaffold(vault)
    status = _session_status(vault)
    scaffold_note = f" Scaffolded {scaffolded} unformatted note{'s' if scaffolded != 1 else ''}." if scaffolded else ""
    return f"[ZETTEL MODE]{scaffold_note} {status}"


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
            return enter_mode()
        if any(p in q for p in _EXIT_PHRASES):
            return exit_mode()

        # ── Accept / confirm pending process ─────────────────────────────────
        if q in ("accept", "yes", "confirm", "ok", "looks good") or q.startswith("accept "):
            edits = user_input[len("accept"):].strip() if q.startswith("accept ") else None
            return apply_pending(edits)

        # ── Vault status ──────────────────────────────────────────────────────
        if "vault status" in q or ("what should i do" in q and _zettel_mode):
            return vault_status()

        # ── Scaffold vault ────────────────────────────────────────────────────
        if "scaffold vault" in q or "create vault" in q:
            path_match = re.search(r"(?:scaffold|create) vault(?: (?:at|in|here))?\s*(.*)", q)
            path = path_match.group(1).strip() if path_match and path_match.group(1).strip() else None
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
                "User says 'let's work on zettles', 'zettel mode', 'open the vault', "
                "'new note', 'process my notes', 'what's connecting', or any vault/note command. "
                "Also handles 'inbox' and 'what should I do' when in zettel mode."
            ),
            "params": {
                "action": "enter_mode | exit_mode | vault_status | new_note | new_literature | process",
                "claim": "The claim title for a new permanent note (title-as-argument)",
                "source": "The source name for a new literature note",
            },
        }
