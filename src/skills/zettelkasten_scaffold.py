"""Vault scaffolding — creates folder structure and Obsidian config."""

import json
import os
from pathlib import Path
from typing import Optional

from src.skills.zettelkasten_skill import _get_vault

_GRAPH_JSON = {
    "collapse-filter": True,
    "search": "-path:_System -path:Fleeting -file:README -file:AGENTS -file:CLAUDE",
    "showTags": False,
    "showAttachments": False,
    "hideUnresolved": False,
    "showOrphans": True,
    "collapse-color-groups": True,
    "colorGroups": [],
    "collapse-display": True,
    "showArrow": True,
    "textFadeMultiplier": 0,
    "nodeSizeMultiplier": 1.2,
    "lineSizeMultiplier": 1,
    "collapse-forces": True,
    "centerStrength": 0.518,
    "repelStrength": 10,
    "linkStrength": 1,
    "linkDistance": 250,
    "scale": 1,
    "close": False,
}

_APP_JSON = {
    "legacyEditor": False,
    "livePreview": True,
    "defaultViewMode": "source",
    "foldHeading": False,
    "foldIndent": True,
    "showLineNumber": False,
    "readableLineLength": True,
    "strictLineBreaks": False,
    "showFrontmatter": False,
}

_CORE_PLUGINS = [
    "file-explorer", "global-search", "switcher", "graph",
    "backlink", "outgoing-link", "tag-pane", "page-preview",
    "daily-notes", "templates", "word-count", "outline",
]

_MASTER_TAG_LIST = """# Master Tag List

This file is managed by Xochitl. Add new tags here when they are approved during note processing.

## Tags

| tag | description |
|-----|-------------|
"""

_PARKED_QUESTIONS = """# Parked Questions

Questions surfaced during note processing that aren't dismissed but aren't ready to answer yet.

| date | note | question | status |
|------|------|----------|--------|
"""

_DECISION_LOG = """# Decision Log

Append-only log of all Xochitl actions on this vault.

---
"""

_VAULT_INDEX = """# Vault Index

Maintained by Xochitl. One row per processed permanent note.

| id | title | tags | summary |
|----|-------|------|---------|
"""


def scaffold_vault(path: Optional[str] = None) -> str:
    if path:
        vault = Path(path)
    else:
        vault = _get_vault()

    if vault is None:
        return (
            "No vault path provided and VAULT_PATH is not set in .env. "
            "Pass a path or set VAULT_PATH first."
        )

    vault = vault.resolve()

    if vault.exists() and any(vault.iterdir()):
        existing = [f.name for f in vault.iterdir()]
        if any(f in existing for f in ["Permanent", "Literature", "Fleeting", "_System"]):
            return f"Vault already scaffolded at {vault}."

    # ── Create folders ────────────────────────────────────────────────────────
    for folder in ["Fleeting", "Literature", "Permanent"]:
        (vault / folder).mkdir(parents=True, exist_ok=True)
        (vault / folder / ".gitkeep").touch()

    system_dir = vault / "_System" / "Prompt Library"
    system_dir.mkdir(parents=True, exist_ok=True)

    # ── Write _System files ───────────────────────────────────────────────────
    (vault / "_System" / "Master Tag List.md").write_text(_MASTER_TAG_LIST, encoding="utf-8")
    (vault / "_System" / "Parked Questions.md").write_text(_PARKED_QUESTIONS, encoding="utf-8")
    (vault / "_System" / "Decision Log.md").write_text(_DECISION_LOG, encoding="utf-8")
    (vault / "_System" / "vault-index.md").write_text(_VAULT_INDEX, encoding="utf-8")

    # ── Copy prompt contracts from ZettleLib if available ────────────────────
    _copy_prompt_library(vault)
    _copy_vault_taxonomy(vault)

    # ── Obsidian config ───────────────────────────────────────────────────────
    obsidian_dir = vault / ".obsidian"
    obsidian_dir.mkdir(exist_ok=True)

    (obsidian_dir / "graph.json").write_text(
        json.dumps(_GRAPH_JSON, indent=2), encoding="utf-8"
    )
    (obsidian_dir / "app.json").write_text(
        json.dumps(_APP_JSON, indent=2), encoding="utf-8"
    )
    (obsidian_dir / "core-plugins.json").write_text(
        json.dumps(_CORE_PLUGINS, indent=2), encoding="utf-8"
    )

    return (
        f"Vault scaffolded at {vault}\n"
        f"  Fleeting/  Literature/  Permanent/  _System/\n"
        f"  .obsidian/ — graph exclusions configured\n\n"
        f"Next: open Obsidian → 'Open folder as vault' → point to {vault}"
    )


def _copy_prompt_library(vault: Path) -> None:
    """Copy prompt contracts (.txt + .yaml) from ZettleLib _System/Prompt Library/."""
    # New v3 location first, legacy location as fallback
    candidates = [
        Path.home() / "Desktop" / "Jason" / "Resource" / "CodeProjects" / "ZettleLib" / "beta-vault" / "_System" / "Prompt Library",
        Path(__file__).parent.parent.parent.parent / "ZettleLib" / "beta-vault" / "_System" / "Prompt Library",
        Path.home() / "Desktop" / "Jason" / "Resource" / "CodeProjects" / "ZettleLib" / "beta-vault" / "80 System" / "Prompt Library",
        Path(__file__).parent.parent.parent.parent / "ZettleLib" / "beta-vault" / "80 System" / "Prompt Library",
    ]
    dest = vault / "_System" / "Prompt Library"
    for source in candidates:
        if source.exists():
            for prompt_file in source.glob("*"):
                if prompt_file.suffix in (".txt", ".yaml", ".md"):
                    (dest / prompt_file.name).write_text(
                        prompt_file.read_text(encoding="utf-8"), encoding="utf-8"
                    )
            return


def _copy_vault_taxonomy(vault: Path) -> None:
    """Copy vault-taxonomy.md seed from ZettleLib _System/ if available."""
    candidates = [
        Path.home() / "Desktop" / "Jason" / "Resource" / "CodeProjects" / "ZettleLib" / "beta-vault" / "_System" / "vault-taxonomy.md",
        Path(__file__).parent.parent.parent.parent / "ZettleLib" / "beta-vault" / "_System" / "vault-taxonomy.md",
    ]
    dest = vault / "_System" / "vault-taxonomy.md"
    if dest.exists():
        return
    for source in candidates:
        if source.exists():
            dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            return
    # Write a minimal seed if no source found
    dest.write_text(
        "# Vault Taxonomy\n\nOne approved tag per line.\n\n## Active Tags\n\n"
        "#strategy\n#systems-thinking\n#design-thinking\n#learning\n#communication\n"
        "#first-principles\n#mental-models\n#knowledge-management\n#writing\n#philosophy\n",
        encoding="utf-8",
    )
