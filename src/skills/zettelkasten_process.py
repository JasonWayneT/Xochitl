"""Note processing pipeline — word count, atomicity, tags, links, serendipity, coaching."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.skills.zettelkasten_skill import _get_vault, _next_id

# ── Pending confirmation state ────────────────────────────────────────────────

_pending: Optional[dict] = None


def get_pending() -> Optional[dict]:
    return _pending


def clear_pending() -> None:
    global _pending
    _pending = None


# ── File helpers ───────────────────────────────────────────────────────────────

def _word_count(text: str) -> int:
    body = re.sub(r"^---[\s\S]*?---\n", "", text, count=1).strip()
    return len(body.split())


def _read_note(filename: Optional[str], vault: Path) -> Optional[tuple[Path, str]]:
    perm_dir = vault / "Permanent"
    if not perm_dir.exists():
        return None
    if filename:
        note_file = perm_dir / filename
        if not note_file.exists():
            note_file = perm_dir / f"{filename}.md"
        if not note_file.exists():
            return None
    else:
        notes = sorted(perm_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not notes:
            return None
        note_file = notes[0]
    return note_file, note_file.read_text(encoding="utf-8")


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("---", 3)
    if end == -1:
        return {}, content
    fm_raw = content[3:end].strip()
    body = content[end + 3:].strip()
    fm: dict = {}
    for line in fm_raw.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def _write_frontmatter(note_file: Path, fm: dict, body: str) -> None:
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    note_file.write_text("\n".join(lines), encoding="utf-8")


def _read_taxonomy(vault: Path) -> list[str]:
    """Read vault-taxonomy.md (new) or Master Tag List.md (legacy)."""
    taxonomy_file = vault / "_System" / "vault-taxonomy.md"
    if taxonomy_file.exists():
        content = taxonomy_file.read_text(encoding="utf-8")
        return re.findall(r"(#[\w-]+)", content)
    legacy = vault / "_System" / "Master Tag List.md"
    if legacy.exists():
        content = legacy.read_text(encoding="utf-8")
        return re.findall(r"\| (#[\w-]+)", content)
    return []


def _append_to_index(vault: Path, note_id: str, title: str, tags: list[str], summary: str) -> None:
    index_file = vault / "_System" / "vault-index.md"
    if not index_file.exists():
        return
    tag_str = " ".join(tags) if tags else ""
    row = f"| {note_id} | {title} | {tag_str} | {summary[:80]} |\n"
    with open(index_file, "a", encoding="utf-8") as f:
        f.write(row)


def _log_action(vault: Path, note_path: Path, action: str, outcome: str) -> None:
    log_file = vault / "_System" / "Decision Log.md"
    if not log_file.exists():
        return
    ts = datetime.now(timezone.utc).isoformat()
    entry = f"\n## {ts}\n**Note:** {note_path.name}\n**Action:** {action}\n**Outcome:** {outcome}\n"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry)


def _find_note_body(title: str, vault: Path) -> str:
    """Find body text of a permanent note by matching its title."""
    perm_dir = vault / "Permanent"
    if not perm_dir.exists():
        return ""
    title_lower = title.lower()
    for note_file in perm_dir.glob("*.md"):
        candidate = note_file.stem.replace("-", " ").lower()
        if candidate == title_lower or candidate.startswith(title_lower[:20]):
            _, body = _parse_frontmatter(note_file.read_text(encoding="utf-8"))
            return re.sub(r"^# .+\n", "", body, count=1).strip()
    return ""


# ── Step 1: Word count ────────────────────────────────────────────────────────

def _check_word_count(body: str) -> Optional[str]:
    count = _word_count(body)
    if count < 100:
        return (
            f"This note is {count} words — it might be the edge of an idea "
            f"rather than the idea itself. What are you actually claiming?"
        )
    if count > 400:
        return (
            f"This note is {count} words — it might be covering more than one idea. "
            f"What's the core claim? Everything else could be a second note."
        )
    return None


# ── Step 2: Atomicity check ───────────────────────────────────────────────────

def _check_atomicity_heuristic(title: str, body: str) -> Optional[str]:
    title_lower = title.lower().lstrip("#").strip()
    words = title_lower.split()
    has_verb_signal = any(w in title_lower for w in [
        " is ", " are ", " makes ", " reveals ", " creates ", " enables ",
        " requires ", " depends ", " precedes ", " follows ", " causes ",
        "not ", "rather than", "more than", "better than", "instead of",
    ])
    if len(words) <= 3 and not has_verb_signal:
        return (
            f'"{title.lstrip("#").strip()}" reads as a topic heading rather than a claim. '
            f"What's the argument you'd make about it?"
        )
    sentences = [s.strip() for s in re.split(r"[.!?]", body) if len(s.strip()) > 20]
    if len(sentences) >= 4:
        return (
            "This note has several distinct points — I'm curious whether "
            "they're all supporting one claim or doing separate jobs."
        )
    return None


def _check_atomicity(title: str, body: str, loader) -> Optional[str]:
    """Contract-based atomicity check with heuristic fallback."""
    if loader is not None:
        result = loader.call("atomicity-check-v1", title=title, body=body)
        if result == "MULTIPLE":
            return (
                "I notice this might be doing two jobs — are these the same claim, "
                "or two separate ideas that each deserve their own note?"
            )
        if result == "ONE":
            return None
    return _check_atomicity_heuristic(title, body)


# ── Step 3: Context-collapse check ───────────────────────────────────────────

def _check_context_collapse(body: str) -> Optional[str]:
    patterns = [
        (r"\bthis argument\b", "this argument"),
        (r"\bthe above\b", "the above"),
        (r"\bas mentioned\b", "as mentioned"),
        (r"\bthe former\b", "the former"),
        (r"\bthe latter\b", "the latter"),
        (r"\bthis concept\b", "this concept"),
        (r"\bthis idea\b", "this idea"),
    ]
    found = [label for pattern, label in patterns if re.search(pattern, body, re.IGNORECASE)]
    if found:
        refs = ", ".join(f'"{f}"' for f in found[:2])
        return f"Context collapse: {refs} won't make sense to future-you without context. Name the thing directly."
    return None


# ── Step 4: Tag suggestion ────────────────────────────────────────────────────

def _suggest_tags_heuristic(body: str, existing_tags: list[str], vault: Path) -> list[str]:
    known_tags = _read_taxonomy(vault)
    body_lower = body.lower()
    suggestions = []
    for tag in known_tags:
        keyword = tag.lstrip("#").replace("-", " ")
        if keyword in body_lower and tag not in existing_tags:
            suggestions.append(tag)
    return suggestions[:3]


def _suggest_tags(title: str, body: str, existing_tags: list[str], vault: Path, loader) -> list[str]:
    """Contract-based tag suggestion grounded to vault-taxonomy.md, with keyword fallback."""
    if loader is not None:
        taxonomy_tags = _read_taxonomy(vault)
        if taxonomy_tags:
            taxonomy_str = ", ".join(taxonomy_tags)
            result = loader.call("tag-suggestion-v1", title=title, body=body, taxonomy=taxonomy_str)
            if result:
                # Strip leading # for comparison, keep for display
                return [t if t.startswith("#") else f"#{t}" for t in result
                        if t.lstrip("#") not in [e.lstrip("#") for e in existing_tags]]
    return _suggest_tags_heuristic(body, existing_tags, vault)


# ── Step 5–7: Link suggestion + tension confirmation ─────────────────────────

_LINK_VERBS = ["extends", "contradicts", "qualifies", "applies", "explains", "analogizes", "supports"]

_VERB_MAP = {
    "EXTENDS": "extends",
    "PARALLEL": "parallel",
    "TENSION": "tension",
    "UNRELATED": None,
}


def _infer_verb(title: str, candidate: str) -> str:
    t, c = title.lower(), candidate.lower()
    if any(w in t for w in ["not", "rather than", "instead", "against", "despite"]):
        return "contradicts"
    if any(w in c for w in ["not", "rather than", "instead", "against", "despite"]):
        return "contradicts"
    if any(w in t for w in ["condition", "unless", "except", "limit", "only when"]):
        return "qualifies"
    if any(w in t for w in ["example", "case", "instance", "applies"]):
        return "applies"
    if any(w in t for w in ["because", "mechanism", "explains", "causes", "why"]):
        return "explains"
    return "extends"


def _keyword_candidates(title: str, body: str, vault: Path) -> list[str]:
    """Fast keyword-overlap scan for obvious link candidates."""
    perm_dir = vault / "Permanent"
    if not perm_dir.exists():
        return []
    title_words = set(re.findall(r"\w{4,}", title.lower()))
    body_words = set(re.findall(r"\w{4,}", body.lower()))
    search_words = title_words | body_words
    candidates = []
    for note_file in perm_dir.glob("*.md"):
        candidate_title = note_file.stem.replace("-", " ")
        candidate_words = set(re.findall(r"\w{4,}", candidate_title.lower()))
        if len(search_words & candidate_words) >= 2:
            candidates.append(candidate_title.title())
        if len(candidates) >= 3:
            break
    return candidates


def _semantic_candidates(title: str, body: str) -> list[str]:
    """Vector DB semantic candidates."""
    try:
        from src import memory as mem
        query = f"{title} {body[:200]}"
        results = mem.recall(query=query, project="zettelkasten", n_results=5)
        return [r["topic"] for r in results if r["topic"].lower() != title.lower()][:3]
    except Exception:
        return []


def _suggest_links(title: str, body: str, vault: Path, loader) -> list[tuple[str, str]]:
    """
    Return (display_title, verb) pairs.
    Uses vector DB + link-label contract, falls back to keyword + heuristic verbs.
    Tension items are confirmed via tension-confirm contract before flagging ⚡.
    """
    # Gather candidates: keyword + semantic, deduped, capped at 3
    keyword_cands = _keyword_candidates(title, body, vault)
    semantic_cands = _semantic_candidates(title, body)
    seen: set[str] = set()
    candidates: list[str] = []
    for c in keyword_cands + semantic_cands:
        c_norm = c.lower()
        if c_norm not in seen and c.lower() != title.lower():
            seen.add(c_norm)
            candidates.append(c)
        if len(candidates) >= 3:
            break

    if not candidates:
        return []

    # No contracts — fall back to heuristic verbs
    if loader is None:
        return [(c, _infer_verb(title, c)) for c in candidates]

    results: list[tuple[str, str]] = []
    for candidate_title in candidates:
        label = loader.call("link-label-v1", title_a=title, title_b=candidate_title)
        if not label or label == "UNRELATED":
            continue

        verb = _VERB_MAP.get(label, "extends")

        # Tension confirmation pass
        if label == "TENSION":
            candidate_body = _find_note_body(candidate_title, vault)
            if candidate_body:
                confirm = loader.call(
                    "tension-confirm-v1",
                    title_a=title, body_a=body,
                    title_b=candidate_title, body_b=candidate_body,
                )
                if confirm == "ALIGNED":
                    verb = "parallel"

        results.append((candidate_title, verb))

    return results


# ── Embed + index ─────────────────────────────────────────────────────────────

def _embed_note(note_id: str, title: str, body: str) -> None:
    try:
        from src import memory as mem
        mem.memorize(
            topic=title,
            summary=f"{title}. {body[:300]}",
            tags=["zettelkasten", "permanent-note"],
            project="zettelkasten",
        )
    except Exception:
        pass


# ── Serendipity explanation ───────────────────────────────────────────────────

def _serendipity_explain(title_a: str, title_b: str, score: float, loader) -> str:
    """One-sentence explanation of non-obvious connection, via contract or fallback."""
    if loader is not None:
        result = loader.call(
            "serendipity-explain-v1",
            title_a=title_a, title_b=title_b, score=f"{score:.2f}",
        )
        if result and isinstance(result, list) and result[0]:
            return result[0]
    return f"both notes are touching related territory from different angles"


# ── Confirm process (apply pending suggestions) ───────────────────────────────

def apply_pending(edits: Optional[str] = None) -> str:
    """Write frontmatter from pending state. Called when user says 'accept'."""
    global _pending
    if _pending is None:
        return "Nothing pending — say 'process [note]' first."

    note_file: Path = _pending["note_file"]
    fm: dict = _pending["fm"]
    body: str = _pending["body"]
    tags: list[str] = _pending["tags"]
    links: list[tuple[str, str]] = _pending["links"]
    note_id: str = _pending["note_id"]
    title: str = _pending["title"]
    vault: Path = _pending["vault"]

    # Apply tags
    if tags:
        fm["tags"] = "[" + ", ".join(t.lstrip("#") for t in tags) + "]"

    # Apply links as wikilinks in body (append if not already present)
    link_additions = []
    for link_title, verb in links:
        wikilink = f"[[{link_title}]]"
        if wikilink not in body:
            link_additions.append(f"{wikilink} — {verb}")

    if link_additions:
        body = body.rstrip() + "\n\n" + "\n".join(link_additions)

    # Record which contract versions were used
    fm["processed_with"] = "atomicity-check-v1 tag-suggestion-v1 link-label-v1"

    _write_frontmatter(note_file, fm, body)

    # Embed + index
    _embed_note(note_id, title, body)
    first_sentence = re.split(r"[.!?]", body)[0].strip()
    _append_to_index(vault, note_id, title, tags, first_sentence)
    _log_action(vault, note_file, "process_note confirmed", f"tags={tags} links={[l for l,_ in links]}")

    try:
        from src.skills.zettelkasten_skill import record_note_processed
        record_note_processed(note_file.name)
    except Exception:
        pass

    _pending = None

    # Passive serendipity after confirmation
    serendipity_line = _passive_serendipity(title, body, vault)
    result = f"Done."
    if serendipity_line:
        result += f"\n\n{serendipity_line}"
    result += "\n\n→ Clarity check? (optional)"
    return result


def _passive_serendipity(title: str, body: str, vault: Path) -> str:
    """Surface one non-obvious connection via vector DB + serendipity-explain contract."""
    try:
        from src import memory as mem
        from src.skills.zettelkasten_contracts import get_loader
        results = mem.recall(query=f"{title} {body[:200]}", project="zettelkasten", n_results=6)
        # Find next closest not already surfaced in link suggestion (skip exact title match)
        for r in results:
            if r["topic"].lower() != title.lower():
                loader = get_loader(vault)
                score = r.get("score", r.get("distance", 0.5))
                explanation = _serendipity_explain(title, r["topic"], float(score), loader)
                return (
                    f"One non-obvious connection the vault surfaced:\n"
                    f"  [[{r['topic']}]] — {explanation} [{float(score):.2f}]\n\n"
                    f"Feel real or forced?"
                )
    except Exception:
        pass
    return ""


# ── Main process_note ─────────────────────────────────────────────────────────

def process_note(filename: Optional[str] = None) -> str:
    global _pending
    vault = _get_vault()
    if vault is None:
        return "No vault configured."

    result = _read_note(filename, vault)
    if result is None:
        return "No permanent note found. Create one with 'new note: [claim]'."

    note_file, content = result
    fm, body = _parse_frontmatter(content)

    if not body.strip():
        return f"{note_file.name} has no body yet — write the note in Obsidian first."

    title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else note_file.stem.replace("-", " ")
    body_text = re.sub(r"^# .+\n", "", body, count=1).strip()
    note_id = fm.get("id", _next_id(vault))

    from src.skills.zettelkasten_contracts import get_loader
    loader = get_loader(vault)

    output_lines: list[str] = []

    # ── 1. Word count ─────────────────────────────────────────────────────────
    wc_flag = _check_word_count(body_text)
    if wc_flag:
        output_lines.append(wc_flag)
        output_lines.append("")

    # ── 2. Atomicity ──────────────────────────────────────────────────────────
    atom_flag = _check_atomicity(title, body_text, loader)
    if atom_flag:
        output_lines.append(atom_flag)
        output_lines.append("")

    # ── 3. Context collapse ───────────────────────────────────────────────────
    ctx_flag = _check_context_collapse(body_text)
    if ctx_flag:
        output_lines.append(ctx_flag)
        output_lines.append("")

    # ── 4. Tags ───────────────────────────────────────────────────────────────
    existing_tags_raw = fm.get("tags", "[]")
    existing_tags = re.findall(r"[\w-]+", existing_tags_raw)
    suggested_tags = _suggest_tags(title, body_text, existing_tags, vault, loader)

    # ── 5–7. Links + tension ──────────────────────────────────────────────────
    suggested_links = _suggest_links(title, body_text, vault, loader)

    # ── Store pending state (written only on user confirmation) ───────────────
    _pending = {
        "note_file": note_file,
        "fm": dict(fm),
        "body": body,
        "body_text": body_text,
        "title": title,
        "note_id": note_id,
        "vault": vault,
        "tags": suggested_tags,
        "links": suggested_links,
    }

    # ── Build confirmation block ──────────────────────────────────────────────
    has_suggestions = bool(suggested_tags or suggested_links)

    word_count = _word_count(body_text)
    status = f"{word_count} words."
    if not output_lines and not has_suggestions:
        output_lines.append(f"{status} Looks clean.")
    else:
        if not output_lines:
            output_lines.append(status)

    if suggested_links:
        output_lines.append("")
        output_lines.append("Links:")
        for display, verb in suggested_links:
            if verb == "tension":
                output_lines.append(f"  ⚡ [[{display}]] — tension")
            else:
                output_lines.append(f"  [[{display}]] — {verb}")

    if suggested_tags:
        output_lines.append(f"Tags: {' '.join(suggested_tags)}")

    if has_suggestions:
        output_lines.append("")
        output_lines.append("Accept / Edit")

    return "\n".join(output_lines)


# ── Serendipity scan (on demand) ──────────────────────────────────────────────

def serendipity_scan() -> str:
    vault = _get_vault()
    if vault is None:
        return "No vault configured."

    try:
        from src import memory as mem
        from src.skills.zettelkasten_contracts import get_loader
        results = mem.recall(query="ideas connections patterns", project="zettelkasten", n_results=10)
        if len(results) < 2:
            return "Not enough notes yet to find surprising connections. Keep adding."

        loader = get_loader(vault)
        recent = results[:6]
        pairs: list[tuple[str, str, str]] = []
        seen_pairs: set[frozenset] = set()

        for i, a in enumerate(recent):
            for b in recent[i + 1:]:
                key = frozenset([a["topic"], b["topic"]])
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                score = a.get("score", a.get("distance", 0.5))
                explanation = _serendipity_explain(a["topic"], b["topic"], float(score), loader)
                pairs.append((a["topic"], b["topic"], explanation))
                if len(pairs) >= 3:
                    break
            if len(pairs) >= 3:
                break

        if not pairs:
            return "No surprising connections surfaced right now."

        lines = ["Across your recent notes, these haven't found each other yet:\n"]
        for a, b, explanation in pairs:
            lines.append(f"  [[{a}]] ←→ [[{b}]]")
            lines.append(f"  {explanation}\n")
        lines.append("Want to look at any of these together?")
        return "\n".join(lines)

    except Exception:
        return "Serendipity requires the vector DB to be running (Ollama with nomic-embed-text)."


# ── Fleeting triage ───────────────────────────────────────────────────────────

def process_fleeting() -> str:
    vault = _get_vault()
    if vault is None:
        return "No vault configured."

    fleeting_dir = vault / "Fleeting"
    if not fleeting_dir.exists():
        return "No Fleeting/ folder found."

    notes = [f for f in fleeting_dir.glob("*.md") if f.name != ".gitkeep"]
    if not notes:
        return "Fleeting/ is empty — nothing to triage."

    from src.skills.zettelkasten_contracts import get_loader
    loader = get_loader(vault)

    promote: list[tuple[int, str, str]] = []
    keep: list[tuple[int, str, str]] = []
    discard: list[tuple[int, str, str]] = []

    for i, note_file in enumerate(notes, 1):
        content = note_file.read_text(encoding="utf-8").strip()
        preview = content[:100].replace("\n", " ")
        title = note_file.stem.replace("-", " ")

        if loader is not None:
            decision = loader.call("fleeting-triage-v1", title=title, body=content)
        else:
            decision = "KEEP"

        if decision == "PROMOTE":
            promote.append((i, note_file.name, preview))
        elif decision == "DISCARD":
            discard.append((i, note_file.name, preview))
        else:
            keep.append((i, note_file.name, preview))

    lines = [f"{len(notes)} fleeting note{'s' if len(notes) != 1 else ''} triaged:\n"]

    if promote:
        lines.append("PROMOTE — looks permanent-ready:")
        for i, name, preview in promote:
            lines.append(f"  [{i}] {name}")
            lines.append(f"      {preview}")
            lines.append(f"      → say 'promote {i}: [claim title]' to create a permanent note")
        lines.append("")

    if discard:
        lines.append("DISCARD — looks ephemeral:")
        for i, name, preview in discard:
            lines.append(f"  [{i}] {name}")
            lines.append(f"      {preview}")
            lines.append(f"      → say 'discard {i}' to remove it")
        lines.append("")

    if keep:
        lines.append("KEEP — leaving in Fleeting/ for now:")
        for i, name, preview in keep:
            lines.append(f"  [{i}] {name}")
        lines.append("")

    lines.append("Say 'promote [N]: [claim]', 'discard [N]', or 'skip' to do it later.")
    return "\n".join(lines)


# ── Clarity coaching ──────────────────────────────────────────────────────────

def clarity_check(filename: Optional[str] = None) -> str:
    vault = _get_vault()
    if vault is None:
        return "No vault configured."

    # Use pending note if no filename given
    if filename is None and _pending is not None:
        title = _pending["title"]
        body_text = _pending["body_text"]
        note_name = _pending["note_file"].name
    else:
        result = _read_note(filename, vault)
        if result is None:
            return f"Note not found: {filename}"
        note_file, content = result
        fm, body = _parse_frontmatter(content)
        body_text = re.sub(r"^# .+\n", "", body, count=1).strip()
        title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else note_file.stem.replace("-", " ")
        note_name = note_file.name

    from src.skills.zettelkasten_contracts import get_loader
    loader = get_loader(vault)

    # Try contract first
    if loader is not None:
        result = loader.call("clarity-coaching-v1", title=title, body=body_text)
        if result and isinstance(result, list) and result:
            lines = [f"Clarity suggestions for {note_name}:\n"]
            for i, suggestion in enumerate(result, 1):
                lines.append(f"{i}. {suggestion}")
            lines.append("\nTake any of these / ignore all / let's work on one.")
            return "\n".join(lines)

    # Heuristic fallback
    suggestions = []
    has_verb = any(w in title.lower() for w in [
        " is ", " are ", " makes ", " reveals ", " creates ", "not ", "rather than", "more than",
    ])
    if not has_verb:
        suggestions.append(
            f'Title as claim: "{title}" reads as a topic. '
            f"State what you argue about it — something a reasonable person could disagree with."
        )
    vague = re.findall(r"\b(kind of|sort of|maybe|perhaps|somewhat|basically|generally)\b", body_text, re.I)
    if vague:
        suggestions.append(f"Precise language: found '{vague[0]}' — what's the more exact claim underneath it?")
    bullet_count = len(re.findall(r"^\s*[-*]\s", body_text, re.MULTILINE))
    if bullet_count >= 2:
        suggestions.append(f"Prose over bullets: {bullet_count} bullet points. Bullets list — prose argues.")

    if not suggestions:
        return "This note reads clearly."

    lines = [f"Clarity suggestions for {note_name}:\n"]
    for i, s in enumerate(suggestions, 1):
        lines.append(f"{i}. {s}")
    lines.append("\nTake any of these / ignore all / let's work on one.")
    return "\n".join(lines)
