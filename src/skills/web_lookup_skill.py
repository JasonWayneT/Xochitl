"""General web lookup skill for live internet answers (no dedicated weather API)."""

from __future__ import annotations

import html
import logging
import re
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from src.http_utils import fetch_bytes  # FR-API-005, NFR-API-002 (retry + rate limit)
from src.security import XochitlPermissionError  # caught in _fetch_text
from src.skills.base import Skill


_WEB_KEYWORDS = (
    "weather",
    "forecast",
    "temperature",
    "look it up",
    "search the web",
    "internet",
    "online",
    "latest news",
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


class WebLookupSkill(Skill):
    # Implements FR-API-003
    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()
        if any(k in q for k in _WEB_KEYWORDS):
            return 0.85
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        return "I can check the internet and summarize what I find. Want me to look it up?"

    def tool_definition(self) -> dict:
        return {
            "name": "WebLookupSkill",
            "description": "Searches the public internet and summarizes results for live questions like weather and current events.",
            "when": "user asks for weather, forecast, latest/current information, or explicitly asks to search online",
            "params": {
                "query": "Search query text",
            },
            "examples": [
                "search the web for latest AI news",
                "look up how to fix a Python import error",
                "find current information about climate change",
                "what's happening in the news today?",
                "search online for the best Python testing frameworks",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        query = (params.get("query") or user_input).strip()
        _logger.info("execute query=%r", query)
        if not query:
            return "I need a query to search."

        try:
            links = self._search(query)
        except Exception as e:
            _logger.exception("search_failed query=%r error=%s", query, e)
            return "I couldn't search the web right now."

        _logger.info("search_results query=%r count=%d", query, len(links))
        if not links:
            context["last_skill_success"] = False
            return "I couldn't find results right now. Please try again in a moment."

        snippets: list[str] = []
        for title, url, search_snippet in links[:3]:
            body = self._fetch_text(url)
            if body:
                snippets.append(f"- {title}: {body[:260].strip()}...")
            elif search_snippet:
                snippets.append(f"- {title}: {search_snippet[:220].strip()}...")

        if not snippets:
            _logger.warning("no_snippets query=%r links_considered=%d", query, min(3, len(links)))
            context["last_skill_success"] = False
            return "I found links, but couldn't read their content right now."

        context["last_skill_success"] = True
        return "I checked the internet and found:\n" + "\n".join(snippets)

    def _search(self, query: str) -> list[tuple[str, str, str]]:
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        # fetch_bytes handles SSRF validation, rate limiting, and retry (FR-API-005).
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
        # fetch_bytes: SSRF validation, rate limiting, retry (FR-API-005, FR-SEC-005).
        try:
            raw = fetch_bytes(
                url,
                headers={"User-Agent": "Mozilla/5.0 Xochitl/1.0"},
                read_limit=22000,
            )
            text = self._clean_text(raw.decode("utf-8", errors="ignore"))
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
