"""Query planning utilities for CR-053 — Perplexity-grade Research Pipeline.

Implements:
  FR-RES-011 — rewrite_for_search(): strip filler, produce 3-7 keyword search string
  FR-RES-012 — decompose_query(): split multi-part questions into 1-4 sub-queries
  FR-RES-013 — called by WebLookupSkill (rewrite) and ExplorerSkill (decompose)
  FR-RES-014 — route_to_specialized_index(): map intent to specialized endpoints
  FR-RES-015 — domain trust scoring (Tier 1–4 hardcoded constants)
  NFR-RES-003 — Tier 4 blocklist: hardcoded constant, max 30 entries, LLM cannot modify
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# ── Domain trust tiers (FR-RES-015) ─────────────────────────────────────────

_TIER1_DOMAINS: frozenset[str] = frozenset({
    ".gov",
    ".edu",
    "pubmed.ncbi.nlm.nih.gov",
    "arxiv.org",
    "who.int",
    "nature.com",
    "sciencedirect.com",
})

_TIER2_DOMAINS: frozenset[str] = frozenset({
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "npr.org",
    "wikipedia.org",
    "mayoclinic.org",
})

# NFR-RES-003: hardcoded constant, ≤30 entries, never modified by LLM output.
_TIER4_BLOCKLIST: frozenset[str] = frozenset({
    "dailymail.co.uk",
    "infowars.com",
    "naturalnews.com",
    "breitbart.com",
    "thegatewaypundit.com",
    "worldnewsdailyreport.com",
    "empirenews.net",
    "nationalreport.net",
    "huzlers.com",
    "theonion.com",
    "clickhole.com",
    "beforeitsnews.com",
    "yournewswire.com",
    "newspunch.com",
    "activistpost.com",
    "21stcenturywire.com",
    "abovetopsecret.com",
    "stormfront.org",
    "zerohedge.com",
    "sovereignman.com",
})

# ── Intent → specialized index mapping (FR-RES-014) ─────────────────────────

_ACADEMIC_PATTERNS = re.compile(
    r"\b(study|studies|research|clinical trial|meta-analysis|systematic review|"
    r"journal|paper|evidence|efficacy|mechanism|pathology|pharmacology)\b",
    re.I,
)
_MEDICAL_PATTERNS = re.compile(
    r"\b(disease|disorder|symptom|treatment|medication|drug|dose|therapy|"
    r"diagnosis|cancer|diabetes|heart|blood pressure|mental health|vaccine)\b",
    re.I,
)

_SPECIALIZED_ACADEMIC = [
    "https://pubmed.ncbi.nlm.nih.gov/?term={query}",
    "https://export.arxiv.org/find/all?query={query}",
]
_SPECIALIZED_MEDICAL = [
    "https://clinicaltrials.gov/ct2/results?cond={query}",
    "https://nih.gov/search/results?q={query}",
]
_GENERAL = ["duckduckgo"]  # sentinel — WebLookupSkill uses its own DDG search


def route_to_specialized_index(intent: str) -> list[str]:
    """Map detected query intent to preferred source endpoints.

    Implements FR-RES-014.  Returns free-API endpoint templates or ["duckduckgo"].

    Args:
        intent: The user query or a short description of the query intent.

    Returns:
        List of URL templates (with ``{query}`` placeholder) or ``["duckduckgo"]``.
    """
    if _ACADEMIC_PATTERNS.search(intent):
        return _SPECIALIZED_ACADEMIC
    if _MEDICAL_PATTERNS.search(intent):
        return _SPECIALIZED_MEDICAL
    return _GENERAL


def domain_trust_score(url: str) -> float:
    """Return a domain trust delta for ranking source candidates.

    Implements FR-RES-015.

    Returns:
        +0.40 for Tier 1, +0.20 for Tier 2, 0.00 for Tier 3, −0.30 for Tier 4.
    """
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower().lstrip("www.")
    except Exception:
        return 0.0

    # Tier 4 — blocked domains
    for blocked in _TIER4_BLOCKLIST:
        if host == blocked or host.endswith("." + blocked):
            return -0.30

    # Tier 1 — TLD checks first
    for t1 in _TIER1_DOMAINS:
        if t1.startswith("."):
            if host.endswith(t1):
                return 0.40
        elif host == t1 or host.endswith("." + t1):
            return 0.40

    # Tier 2
    for t2 in _TIER2_DOMAINS:
        if host == t2 or host.endswith("." + t2):
            return 0.20

    return 0.0


def rank_links_by_trust(
    links: list[tuple[str, str, str]],
) -> list[tuple[str, str, str, float]]:
    """Sort (title, url, snippet) links by domain trust score descending.

    Returns list of (title, url, snippet, trust_score) tuples.
    """
    scored = [(t, u, s, domain_trust_score(u)) for t, u, s in links]
    scored.sort(key=lambda x: x[3], reverse=True)
    return scored


# ── Query rewriting (FR-RES-011) ─────────────────────────────────────────────

_FILLER_WORDS = frozenset({
    "can you", "could you", "please", "tell me", "i want to know",
    "what is the", "what are the", "what is", "what are",
    "who is", "who was", "where is", "when did", "when was",
    "how does", "how do", "how much", "how many", "why does", "why is",
    "do you know", "can you tell me", "is it true", "i wonder",
    "give me", "show me", "find me", "look up",
})


def rewrite_for_search(user_query: str) -> str:
    """Strip filler and produce a 3-7 keyword search string.

    Implements FR-RES-011.  Uses simple_qa route for reliability.

    Args:
        user_query: Raw user question.

    Returns:
        Compact search keyword string.
    """
    q = user_query.strip()
    if not q:
        return q

    # Fast heuristic: strip leading filler phrases
    q_lower = q.lower()
    for phrase in sorted(_FILLER_WORDS, key=len, reverse=True):
        if q_lower.startswith(phrase):
            q = q[len(phrase):].strip(" ,?.")
            q_lower = q.lower()
            break

    # If still longer than 10 words, try LLM rewrite
    words = q.split()
    if len(words) <= 7:
        return q

    try:
        from src.router import get_router
        prompt = (
            f"Rewrite this question as a 3-7 keyword web search query. "
            f"Output ONLY the keywords, no explanation:\n\n{user_query}"
        )
        result = get_router().route(
            query=prompt,
            conversation_history=[],
            force_route="simple_qa",
        )
        rewritten = (result.content if hasattr(result, "content") else str(result)).strip()
        if rewritten and len(rewritten.split()) <= 10:
            return rewritten
    except Exception:
        pass

    # Fallback: first 7 words
    return " ".join(words[:7])


def decompose_query(user_query: str) -> list[str]:
    """Split multi-part questions into 1-4 sub-queries.

    Implements FR-RES-012.  Returns [original] when the query is simple.

    Args:
        user_query: Raw user question.

    Returns:
        List of 1-4 sub-query strings.
    """
    q = user_query.strip()
    if not q:
        return [q]

    # Heuristic: look for conjunctions that suggest multi-part questions
    multi_signals = [" and ", " as well as ", " also ", " plus ", " both "]
    has_multi_signal = any(sig in q.lower() for sig in multi_signals)

    # Short questions are almost always single-part
    if len(q.split()) < 8 or not has_multi_signal:
        return [q]

    try:
        from src.router import get_router
        prompt = (
            f"Split this question into 1-4 focused sub-questions if it has multiple parts. "
            f"If it is a single-focus question, output just the original. "
            f"Output ONLY the sub-questions, one per line, no numbering or explanation:\n\n{q}"
        )
        result = get_router().route(
            query=prompt,
            conversation_history=[],
            force_route="simple_qa",
        )
        content = (result.content if hasattr(result, "content") else str(result)).strip()
        parts = [line.strip() for line in content.splitlines() if line.strip()]
        if 1 <= len(parts) <= 4:
            return parts
    except Exception:
        pass

    return [q]
