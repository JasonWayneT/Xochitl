"""General web lookup skill — deep content extraction with citation support.

Implements:
  FR-API-003  — web lookup skill registration
  FR-RES-005  — fetch up to 6 sources, body capped at 5,000 chars
  FR-RES-006  — _extract_main_content() strips nav/footer/aside/header; ≥40-char paras only
  FR-RES-007  — execute() returns structured SourceRecord tuples in context["research_sources"]
  NFR-RES-002 — evidence cap raised to 3,000 chars per step for ExplorerSkill
  FR-RES-011  — call rewrite_for_search() before DuckDuckGo fetch
  FR-ROUTE-004 — context-aware follow-up boost (CR-054 Phase 2)
"""
from __future__ import annotations

import html
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from src.http_utils import fetch_bytes  # FR-API-005, NFR-API-002 (retry + rate limit)
from src.research_types import SourceRecord
from src.security import XochitlPermissionError  # caught in _fetch_text
from src.skills.base import Skill


_WEB_KEYWORDS = (
    "look it up",
    "search the web",
    "search for",
    "internet",
    "online",
    "latest news",
    "current news",
    "look up",
    "find out",
    "research",
)

_FACTUAL_PREFIXES = (
    "how much",
    "how many",
    "what is the",
    "what are the",
    "who is",
    "who was",
    "when did",
    "when was",
    "where is",
    "why does",
    "why is",
    "how does",
    "how do",
    "what does",
    "is it true",
    "can you tell me",
    "do you know",
)

# FR-ROUTE-004: follow-up phrases that trigger context-aware boost
_FOLLOWUP_PHRASES = (
    "what about",
    "and in",
    "how about",
    "same for",
    "what about in",
)

_LOG_DIR = Path(".sdd") / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "web_lookup.log"

_logger = logging.getLogger("xochitl.web_lookup")
if not _logger.handlers:
    _handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

# FR-RES-005: source count and body limits
_MAX_SOURCES = 6
_BODY_CAP = 5_000
_EVIDENCE_CAP = 3_000  # NFR-RES-002: per-step cap for ExplorerSkill


class WebLookupSkill(Skill):
    """Search the web and return deep, cited content extracts.

    Implements FR-API-003, FR-RES-005 through FR-RES-007, NFR-RES-002.
    """

    def can_handle(self, user_input: str, context: dict) -> float:
        """Score web-lookup intent, with follow-up boost per FR-ROUTE-004.

        Args:
            user_input: Raw user message.
            context: Session context dict.

        Returns:
            0.85 for keyword match, 0.75 for context-aware follow-up,
            0.60 for factual prefix, 0.0 otherwise.
        """
        q = user_input.lower()
        # FR-ROUTE-004: context-aware follow-up boost
        if (
            len(user_input.split()) <= 8
            and any(phrase in q for phrase in _FOLLOWUP_PHRASES)
            and context.get("last_skill_fired") == "WebLookupSkill"
        ):
            return 0.75
        if any(k in q for k in _WEB_KEYWORDS):
            return 0.85
        if any(q.startswith(p) or f" {p}" in q for p in _FACTUAL_PREFIXES):
            return 0.60
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        return "I can check the internet and summarize what I find. Want me to look it up?"

    def tool_definition(self) -> dict:
        return {
            "name": "WebLookupSkill",
            "description": "Searches the public internet and summarizes results for any factual, current-events, or research question.",
            "when": "user asks a factual question, wants to look something up, asks about current events, products, people, places, or any topic that benefits from a live internet search",
            "domain": "research",
            "params": {
                "query": "Search query text",
            },
            "examples": [
                "how much alcohol does Bud Light Platinum have?",
                "search the web for latest AI news",
                "look up how to fix a Python import error",
                "who is the current CEO of Apple?",
                "what's happening in the news today?",
                "how many calories are in a Big Mac?",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Fetch up to 6 sources with deep content extraction.

        Implements FR-RES-005, FR-RES-007, FR-RES-011.

        Args:
            user_input: Raw user message.
            context: Session context dict; writes context["research_sources"].
            params: Skill params; expects {"query": "..."}.

        Returns:
            Formatted string with source snippets, or error message.
        """
        query = (params.get("query") or user_input).strip()
        _logger.info("execute query=%r", query)
        if not query:
            return "I need a query to search."

        # FR-RES-011: rewrite query for search before fetching
        try:
            from src.query_planner import rewrite_for_search
            search_query = rewrite_for_search(query)
        except Exception:
            search_query = query

        try:
            links = self._search(search_query)
        except Exception as e:
            _logger.exception("search_failed query=%r error=%s", search_query, e)
            return "I couldn't search the web right now."

        _logger.info("search_results query=%r count=%d", search_query, len(links))
        if not links:
            context["last_skill_success"] = False
            return "I couldn't find results right now. Please try again in a moment."

        # FR-RES-015: rank links by domain trust before selecting top 6
        try:
            from src.query_planner import rank_links_by_trust
            ranked = rank_links_by_trust(links[:8])
        except Exception:
            ranked = [(t, u, s, 0.0) for t, u, s in links[:8]]

        # FR-RES-005: fetch up to _MAX_SOURCES sources
        sources: list[SourceRecord] = []
        for title, url, search_snippet, trust in ranked[:_MAX_SOURCES]:
            parsed = urlparse(url)
            domain = parsed.netloc.lstrip("www.")
            body = self._fetch_text(url)
            rec = SourceRecord(
                title=title,
                url=url,
                domain=domain,
                body=body[:_BODY_CAP] if body else "",
                trust_score=trust,
                search_snippet=search_snippet,
            )
            sources.append(rec)

        if not sources:
            context["last_skill_success"] = False
            return "I found links, but couldn't read their content right now."

        # FR-RES-007: store structured tuples for downstream synthesizers
        context["research_sources"] = sources
        context["last_skill_success"] = True

        # Build human-readable result
        snippets: list[str] = []
        for i, rec in enumerate(sources, 1):
            excerpt = rec.best_body[:260].strip()
            if excerpt:
                snippets.append(f"- [{i}] {rec.title} ({rec.domain}): {excerpt}...")

        return "I checked the internet and found:\n" + "\n".join(snippets)

    def _search(self, query: str) -> list[tuple[str, str, str]]:
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        raw = fetch_bytes(url, headers={"User-Agent": "Mozilla/5.0 Xochitl/1.0"}).decode("utf-8", errors="ignore")
        out: list[tuple[str, str, str]] = []
        title_matches = list(re.finditer(r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>', raw, re.I | re.S))

        for idx, title_match in enumerate(title_matches[:8]):
            href, title_html = title_match.groups()
            title = self._clean_text(title_html)
            real_url = self._normalize_result_url(href)
            next_start = title_matches[idx + 1].start() if idx + 1 < len(title_matches) else len(raw)
            result_tail = raw[title_match.end():next_start]
            snippet_match = re.search(
                r'<(?:a|div|span)[^>]*class="[^"]*\bresult__snippet\b[^"]*"[^>]*>(.*?)</(?:a|div|span)>',
                result_tail,
                re.I | re.S,
            )
            snippet = self._clean_text(snippet_match.group(1) if snippet_match else "")
            if real_url.startswith("http"):
                out.append((title, real_url, snippet))
        return out

    def _fetch_text(self, url: str) -> str:
        """Fetch URL and return main-content prose.

        Implements FR-RES-006: strips nav/footer/aside/header, keeps ≥40-char paragraphs.
        """
        try:
            raw = fetch_bytes(
                url,
                headers={"User-Agent": "Mozilla/5.0 Xochitl/1.0"},
                read_limit=22000,
            )
            html_text = raw.decode("utf-8", errors="ignore")
            text = self._extract_main_content(html_text)
            text = re.sub(r"\s+", " ", text).strip()
            _logger.info("fetch_ok url=%r chars=%d", url, len(text))
            return text
        except XochitlPermissionError as e:
            _logger.warning("ssrf_blocked url=%r reason=%s", url, e)
            return ""
        except Exception as e:
            _logger.warning("fetch_failed url=%r error=%s", url, e)
            return ""

    @staticmethod
    def _extract_main_content(raw_html: str) -> str:
        """Strip boilerplate blocks and return only meaningful paragraph text.

        Implements FR-RES-006: removes <nav>, <footer>, <aside>, <header>,
        <script>, <style>; retains only paragraphs with ≥40 characters.
        """
        s = raw_html
        # Remove structural boilerplate
        for tag in ("script", "style", "nav", "footer", "aside", "header"):
            s = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", " ", s, flags=re.I | re.S)

        # Extract paragraph content before stripping all tags
        paras = re.findall(r"<p[^>]*>(.*?)</p>", s, re.I | re.S)
        if paras:
            cleaned = []
            for p in paras:
                text = re.sub(r"<[^>]+>", " ", p)
                text = html.unescape(text).strip()
                if len(text) >= 40:
                    cleaned.append(text)
            if cleaned:
                return " ".join(cleaned)

        # Fallback: strip all remaining tags
        s = re.sub(r"<[^>]+>", " ", s)
        return html.unescape(s)

    @staticmethod
    def _clean_text(s: str) -> str:
        s = re.sub(r"<script.*?</script>", " ", s, flags=re.I | re.S)
        s = re.sub(r"<style.*?</style>", " ", s, flags=re.I | re.S)
        s = re.sub(r"<[^>]+>", " ", s)
        return html.unescape(s)

    @staticmethod
    def _normalize_result_url(href: str) -> str:
        """Resolve DuckDuckGo redirect-style links to real destination URLs."""
        href = html.unescape(href)
        if href.startswith("http://") or href.startswith("https://"):
            parsed = urlparse(href)
            if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
                qs = parse_qs(parsed.query)
                uddg = qs.get("uddg", [""])[0]
                if uddg:
                    return unquote(uddg)
            return href
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/l/?") or href.startswith("/l/"):
            parsed = urlparse(href)
            qs = parse_qs(parsed.query)
            uddg = qs.get("uddg", [""])[0]
            if uddg:
                return unquote(uddg)
        return href
