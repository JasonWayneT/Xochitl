"""Map of Content generation — vector clustering + contract labels, assembled by code."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.skills.zettelkasten_skill import _get_vault


def generate_moc(topic: str) -> str:
    vault = _get_vault()
    if vault is None:
        return "No vault configured."

    index_file = vault / "_System" / "vault-index.md"
    if not index_file.exists():
        return "Vault index is empty — process some notes first with 'process note'."

    # ── 1. Retrieve semantically related notes from vector DB ─────────────────
    candidates = _recall_candidates(topic, vault)
    if not candidates:
        return f"No notes found related to '{topic}' in the vault yet."

    if len(candidates) < 2:
        return f"Only {len(candidates)} note found for '{topic}' — need at least 2 to build a MOC."

    # ── 2. Cluster by cosine groups (code only, no LLM) ───────────────────────
    clusters = _cluster(candidates)

    # ── 3. Label each cluster via contract ────────────────────────────────────
    from src.skills.zettelkasten_contracts import get_loader
    loader = get_loader(vault)

    labelled_clusters: list[dict] = []
    for i, cluster in enumerate(clusters, 1):
        titles = [c["title"] for c in cluster]
        titles_str = "\n".join(f"- {t}" for t in titles)

        if loader is not None:
            result = loader.call("moc-cluster-label-v1", note_titles=titles_str, n=i)
            label = result[0] if isinstance(result, list) and result else result
            if not label or label == f"Cluster {i}":
                label = f"Cluster {i}"
        else:
            label = f"Cluster {i}"

        labelled_clusters.append({"label": label, "notes": cluster})

    # ── 4. Choose entry point via contract ────────────────────────────────────
    all_ids_and_titles = "\n".join(
        f"{c['id']} | {c['title']}"
        for cluster in labelled_clusters
        for c in cluster["notes"]
    )

    entry_point_id = None
    entry_point_title = None

    if loader is not None:
        result = loader.call("moc-entry-point-v1", note_ids_and_titles=all_ids_and_titles)
        if result and result != "__FIRST__":
            entry_point_id = result
            for cluster in labelled_clusters:
                for note in cluster["notes"]:
                    if note["id"] == entry_point_id:
                        entry_point_title = note["title"]
                        break

    if entry_point_title is None and labelled_clusters:
        first_note = labelled_clusters[0]["notes"][0]
        entry_point_id = first_note["id"]
        entry_point_title = first_note["title"]

    # ── 5. Assemble MOC file (code only) ─────────────────────────────────────
    moc_content = _assemble_moc(topic, labelled_clusters, entry_point_title)

    moc_file = vault / "_System" / f"MOC_{topic.replace(' ', '-').lower()}.md"
    moc_file.write_text(moc_content, encoding="utf-8")

    note_count = sum(len(c["notes"]) for c in labelled_clusters)
    return (
        f"Generated _System/MOC_{topic.replace(' ', '-').lower()}.md\n"
        f"  {note_count} notes · {len(labelled_clusters)} cluster{'s' if len(labelled_clusters) != 1 else ''} · "
        f"entry point: [[{entry_point_title}]]\n\n"
        f"Open it in Obsidian or say 'generate moc {topic}' to regenerate."
    )


# ── Retrieval ─────────────────────────────────────────────────────────────────

def _recall_candidates(topic: str, vault: Path) -> list[dict]:
    """Retrieve candidates from vector DB + supplement from vault-index."""
    candidates: list[dict] = []
    seen_titles: set[str] = set()

    # Vector DB recall
    try:
        from src import memory as mem
        results = mem.recall(query=topic, project="zettelkasten", n_results=20)
        for r in results:
            title = r["topic"]
            if title.lower() not in seen_titles:
                seen_titles.add(title.lower())
                candidates.append({
                    "title": title,
                    "id": _resolve_id(title, vault),
                    "summary": r.get("summary", "")[:80],
                    "score": float(r.get("score", r.get("distance", 0.5))),
                })
    except Exception:
        pass

    # Fallback: keyword scan of vault-index.md
    if not candidates:
        candidates = _index_candidates(topic, vault, seen_titles)

    return candidates[:20]


def _resolve_id(title: str, vault: Path) -> str:
    """Find note ID from vault-index or generate a placeholder."""
    index_file = vault / "_System" / "vault-index.md"
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        title_lower = title.lower()
        for line in content.splitlines():
            if title_lower in line.lower():
                match = re.search(r"\d{8}-\d{3}", line)
                if match:
                    return match.group(0)
    return "00000000-000"


def _index_candidates(topic: str, vault: Path, seen: set[str]) -> list[dict]:
    """Keyword scan of vault-index as fallback when vector DB has no results."""
    index_file = vault / "_System" / "vault-index.md"
    if not index_file.exists():
        return []
    topic_words = set(re.findall(r"\w{3,}", topic.lower()))
    candidates = []
    for line in index_file.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "id" in line.lower():
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) < 2:
            continue
        note_id = parts[0] if re.match(r"\d{8}-\d{3}", parts[0]) else "00000000-000"
        title = parts[1] if len(parts) > 1 else ""
        summary = parts[3] if len(parts) > 3 else ""
        if not title or title.lower() in seen:
            continue
        title_words = set(re.findall(r"\w{3,}", title.lower()))
        if topic_words & title_words:
            seen.add(title.lower())
            candidates.append({"title": title, "id": note_id, "summary": summary, "score": 0.5})
        if len(candidates) >= 15:
            break
    return candidates


# ── Clustering (code only, no LLM) ───────────────────────────────────────────

def _cluster(candidates: list[dict]) -> list[list[dict]]:
    """
    Simple greedy clustering by title word overlap.
    For small sets (< 6) returns a single cluster.
    For larger sets splits into 2–4 clusters.
    """
    if len(candidates) <= 5:
        return [candidates]

    # Build word sets per candidate
    word_sets = [
        set(re.findall(r"\w{4,}", c["title"].lower())) for c in candidates
    ]

    # Greedy: assign each note to the cluster whose centroid has most overlap
    n_clusters = min(4, max(2, len(candidates) // 4))
    cluster_indices = list(range(n_clusters))

    # Seed clusters with first N notes
    clusters: list[list[int]] = [[i] for i in cluster_indices]

    for i in range(n_clusters, len(candidates)):
        best_cluster = 0
        best_overlap = -1
        for j, cluster in enumerate(clusters):
            cluster_words: set[str] = set()
            for idx in cluster:
                cluster_words |= word_sets[idx]
            overlap = len(word_sets[i] & cluster_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_cluster = j
        clusters[best_cluster].append(i)

    # Remove empty clusters, convert indices to dicts
    return [[candidates[i] for i in cluster] for cluster in clusters if cluster]


# ── MOC file assembly (code only, no LLM writes to file) ─────────────────────

def _assemble_moc(topic: str, clusters: list[dict], entry_point_title: Optional[str]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    note_count = sum(len(c["notes"]) for c in clusters)

    lines = [
        "---",
        f"generated: {today}",
        f"topic: {topic}",
        f"note_count: {note_count}",
        "source: auto",
        "---",
        "",
        f"# {topic.title()}",
        "",
    ]

    for cluster in clusters:
        label = cluster["label"]
        notes = cluster["notes"]
        lines.append(f"## {label} ({len(notes)} note{'s' if len(notes) != 1 else ''})")
        for note in notes:
            summary = note.get("summary", "").strip()
            if summary:
                lines.append(f"- [[{note['title']}]] — {summary}")
            else:
                lines.append(f"- [[{note['title']}]]")
        lines.append("")

    if entry_point_title:
        lines.append("## Entry point")
        lines.append(f"[[{entry_point_title}]]")
        lines.append("")

    topic_slug = topic.replace(" ", "-").lower()
    lines.append("---")
    lines.append(f"*Auto-generated by Xochitl · {today} · `generate moc {topic}` to regenerate*")

    return "\n".join(lines)
