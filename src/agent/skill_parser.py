"""skill_parser — parse <skill_call> XML blocks from LLM responses.

Pure function module: no state, no I/O.  Extracted from chat._parse_skill_calls
so the parsing logic can be tested independently.

FR-PERF-007 (CR-050 C3): returns ALL skill calls, not just the first.
"""
from __future__ import annotations

import json
import re

# Mirrors the regex in chat.py exactly so extraction behaviour is unchanged.
_SKILL_CALL_RE = re.compile(
    r'<skill_call\s+name=["\'](\w+)["\']>(.*?)</skill_call>',
    re.DOTALL | re.IGNORECASE,
)


def parse_skill_calls(response: str) -> list[tuple[str, dict]]:
    """Extract all <skill_call name="X">{...}</skill_call> blocks.

    Tolerant of missing or malformed JSON in the call body — bad JSON yields
    an empty params dict rather than raising.

    Args:
        response: Full LLM response text, may contain multiple skill calls.

    Returns:
        Ordered list of (skill_name, params_dict) tuples; empty when none found.
    """
    results: list[tuple[str, dict]] = []
    for skill_name, body in _SKILL_CALL_RE.findall(response):
        body = body.strip()
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            # Body is not valid JSON (e.g. model emitted bare "systeminfo" instead of
            # {"command": "systeminfo"}).  Store raw text so skills can recover.
            params = {"_raw": body} if body else {}
        results.append((skill_name, params))
    return results


def parse_skill_call(response: str) -> tuple[str, dict] | None:
    """Return the first skill call, or None.

    Backward-compatible wrapper around parse_skill_calls().

    Args:
        response: Full LLM response text.

    Returns:
        (skill_name, params_dict) for the first match, or None.
    """
    calls = parse_skill_calls(response)
    return calls[0] if calls else None


def strip_skill_calls(response: str) -> str:
    """Remove all <skill_call> XML blocks from response text.

    Args:
        response: LLM response that may contain skill_call tags.

    Returns:
        Clean response with all skill_call blocks removed and whitespace trimmed.
    """
    return _SKILL_CALL_RE.sub("", response).strip()
