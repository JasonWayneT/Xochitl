"""Shared research data types for CR-053 (Perplexity-grade Research Pipeline).

Implements FR-RES-008 — SourceRecord dataclass used by WebLookupSkill,
ExplorerSkill, ResearchSkill, and research.synthesize().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SourceRecord:
    """One fetched and scored research source.

    Args:
        title: Page title (from <title> or result anchor).
        url: Canonical page URL.
        domain: Extracted domain (e.g., "pubmed.ncbi.nlm.nih.gov").
        body: Main article prose — navigation garbage stripped, >40-char paragraphs only.
        fetched_at: ISO-8601 UTC timestamp of when the page was fetched.
        trust_score: Domain trust tier score (−0.30 to +0.40); set by query_planner.
        search_snippet: DuckDuckGo search snippet (fallback when fetch fails).
    """

    title: str
    url: str
    domain: str
    body: str
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    trust_score: float = 0.0
    search_snippet: str = ""

    def label(self, index: int) -> str:
        """Return the [N] citation label string for this source."""
        return f"[{index}]"

    def sources_line(self, index: int) -> str:
        """Return a numbered sources-block line: '[N] Title — domain'."""
        return f"[{index}] {self.title} — {self.domain}"

    @property
    def best_body(self) -> str:
        """Return body if non-empty, else search_snippet."""
        return self.body.strip() or self.search_snippet.strip()
