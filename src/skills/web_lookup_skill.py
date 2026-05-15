"""General web lookup skill for live internet answers (no dedicated weather API)."""

from __future__ import annotations

import html
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

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
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        query = (params.get("query") or user_input).strip()
        if not query:
            return "I need a query to search."

        links = self._search(query)
        if not links:
            return "I couldn't find results right now. Please try again in a moment."

        snippets: list[str] = []
        for title, url in links[:3]:
            body = self._fetch_text(url)
            if body:
                snippets.append(f"- {title}: {body[:260].strip()}...")

        if not snippets:
            return "I found links, but couldn't read their content right now."

        return "I checked the internet and found:\n" + "\n".join(snippets)

    def _search(self, query: str) -> list[tuple[str, str]]:
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 Xochitl/1.0"})
        with urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        pairs = re.findall(r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>', raw, re.I | re.S)
        out: list[tuple[str, str]] = []
        for href, title_html in pairs[:8]:
            title = self._clean_text(title_html)
            if href.startswith("http"):
                out.append((title, href))
        return out

    def _fetch_text(self, url: str) -> str:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 Xochitl/1.0"})
        with urlopen(req, timeout=8) as resp:
            raw = resp.read(22000).decode("utf-8", errors="ignore")
        text = self._clean_text(raw)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _clean_text(s: str) -> str:
        s = re.sub(r"<script.*?</script>", " ", s, flags=re.I | re.S)
        s = re.sub(r"<style.*?</style>", " ", s, flags=re.I | re.S)
        s = re.sub(r"<[^>]+>", " ", s)
        return html.unescape(s)
