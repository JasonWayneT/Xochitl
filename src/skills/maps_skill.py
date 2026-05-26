"""Google Maps skill — directions, travel time, and places search.

Implements CR-045: Google Maps integration for Xochitl.

Capabilities:
  - Directions between two locations (driving, walking, transit, bicycling)
  - Travel time estimates
  - Places search (restaurants, coffee shops, etc.) near a location
  - Falls back to user's saved home location when origin/location is omitted

API key configured via: xochitl secrets set GOOGLE_MAPS_API_KEY <value>
Required APIs: Directions, Places, Geocoding (enable in Google Cloud Console).
"""
# Implements FR-MAPS-001 (directions and travel time)
# Implements FR-MAPS-002 (places search)
# Implements CR-045

from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from src.http_utils import fetch_bytes
from src.secrets import get_secret
from src.skills.base import Skill

# ── Config ────────────────────────────────────────────────────────────────────

_DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"
_PLACES_URL     = "https://maps.googleapis.com/maps/api/place/textsearch/json"

_DIRECTIONS_KEYWORDS = (
    "directions to",
    "directions from",
    "how do i get to",
    "how do i get from",
    "navigate to",
    "route to",
    "drive to",
    "driving to",
    "take me to",
    "how long to drive",
    "how long to get",
    "travel time",
    "how far is",
    "how far to",
)

_PLACES_KEYWORDS = (
    "find a ",
    "find me a",
    "find some",
    "find nearby",
    "places near",
    "restaurants near",
    "coffee near",
    "near me",
    "close to me",
    "around me",
    "nearby",
    "look up a ",
)


class MapsSkill(Skill):
    """Directions, travel time, and nearby places via Google Maps APIs."""

    # ── Skill interface ───────────────────────────────────────────────────────

    def can_handle(self, user_input: str, context: dict) -> float:
        """Return confidence that this is a maps/directions/places query.

        Args:
            user_input: Raw user message.
            context: Assembled session context.

        Returns:
            0.95 for clear directions queries, 0.90 for places queries, 0.0 otherwise.
        """
        q = user_input.lower()
        if any(k in q for k in _DIRECTIONS_KEYWORDS):
            return 0.95
        if any(k in q for k in _PLACES_KEYWORDS):
            return 0.90
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        """Return the suggestion prompt shown before executing.

        Args:
            user_input: Raw user message.
            context: Assembled session context.

        Returns:
            Short offer string.
        """
        return "I can look up directions or find places nearby via Google Maps. Want me to?"

    def tool_definition(self) -> dict:
        """Return the LLM tool descriptor for system prompt injection.

        Returns:
            Dict with name, description, when, and params keys.
        """
        return {
            "name": "MapsSkill",
            "description": (
                "Gets driving/walking directions, travel time estimates, and "
                "nearby places (restaurants, coffee shops, etc.) via Google Maps."
            ),
            "when": (
                "user asks for directions to or from a location, how to get "
                "somewhere, how far or how long a drive is, or wants to find "
                "nearby places, restaurants, coffee shops, stores, etc."
            ),
            "params": {
                "intent": "'directions' or 'places'",
                "origin": "Starting location for directions (omit to use saved home location)",
                "destination": "End location for directions",
                "query": "Search query for places, e.g. 'Thai restaurant' or 'coffee shop'",
                "location": "Location to search near (omit to use saved home location)",
                "mode": "'driving' | 'walking' | 'transit' | 'bicycling'  (default: driving)",
            },
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        """Dispatch to directions or places based on detected intent.

        Args:
            user_input: Raw user message.
            context: Assembled session context.
            params: LLM-extracted params (intent, origin, destination, query, location, mode).

        Returns:
            Formatted result string or error message.
        """
        api_key = get_secret("GOOGLE_MAPS_API_KEY", "")
        if not api_key:
            return (
                "Google Maps API key is not configured. "
                "Set it with: `xochitl secrets set GOOGLE_MAPS_API_KEY <your-key>`"
            )

        intent = (params.get("intent") or "").lower()
        q = user_input.lower()

        if not intent:
            if any(k in q for k in _DIRECTIONS_KEYWORDS):
                intent = "directions"
            else:
                intent = "places"

        if intent == "directions":
            return self._directions(user_input, context, params, api_key)
        return self._places(user_input, context, params, api_key)

    # ── Directions ────────────────────────────────────────────────────────────

    def _directions(
        self, user_input: str, context: dict, params: dict, api_key: str
    ) -> str:
        """Fetch and format driving directions between two points.

        Args:
            user_input: Raw user message.
            context: Session context.
            params: Extracted params (origin, destination, mode).
            api_key: Google Maps API key.

        Returns:
            Formatted directions string or error message.
        """
        origin      = (params.get("origin") or "").strip()
        destination = (params.get("destination") or "").strip()
        mode        = (params.get("mode") or "driving").lower()

        if not destination:
            destination = self._extract_destination(user_input)
        if not origin:
            origin, destination = self._maybe_extract_origin(user_input, destination)
        if not origin:
            origin = _default_location()

        if not destination:
            return "I need a destination. Try: 'directions to [place]'."
        if not origin:
            return (
                "I need a starting point. Try: 'directions from [place] to [place]', "
                "or save your home address with: `remember my home address is [address]`."
            )

        try:
            data = _fetch_json(_DIRECTIONS_URL, {
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "key": api_key,
            })
        except Exception as exc:
            context["last_skill_success"] = False
            return f"Maps API error: {exc}"

        status = data.get("status", "")
        if status == "ZERO_RESULTS":
            return f"No route found from '{origin}' to '{destination}'."
        if status == "NOT_FOUND":
            return f"One of the locations wasn't recognised — check the spelling of '{origin}' or '{destination}'."
        if status != "OK":
            return f"Google Maps returned: {status}."

        context["last_skill_success"] = True
        return _format_directions(data, origin, destination, mode)

    # ── Places ────────────────────────────────────────────────────────────────

    def _places(
        self, user_input: str, context: dict, params: dict, api_key: str
    ) -> str:
        """Search for nearby places matching a query.

        Args:
            user_input: Raw user message.
            context: Session context.
            params: Extracted params (query, location).
            api_key: Google Maps API key.

        Returns:
            Formatted places list or error message.
        """
        query    = (params.get("query") or "").strip()
        location = (params.get("location") or "").strip()

        if not query:
            query = self._extract_place_query(user_input)
        if not location:
            location = _default_location()

        search_query = f"{query} near {location}" if location else query
        if not search_query.strip():
            return "I need a search term. Try: 'find a coffee shop near me'."

        try:
            data = _fetch_json(_PLACES_URL, {
                "query": search_query,
                "key": api_key,
            })
        except Exception as exc:
            context["last_skill_success"] = False
            return f"Maps API error: {exc}"

        status = data.get("status", "")
        if status == "ZERO_RESULTS":
            return f"No places found for '{search_query}'."
        if status != "OK":
            return f"Google Maps returned: {status}."

        context["last_skill_success"] = True
        return _format_places(data, search_query)

    # ── Extraction helpers ────────────────────────────────────────────────────

    @staticmethod
    def _extract_destination(query: str) -> str:
        """Pull a destination from a free-text directions query.

        Args:
            query: Raw user message.

        Returns:
            Destination string, or empty string if not found.
        """
        patterns = [
            r"(?:directions?\s+to|navigate\s+to|route\s+to|drive\s+to|take\s+me\s+to)\s+(.+?)(?:\s+from\b|$)",
            r"(?:how\s+(?:do\s+i\s+)?get\s+to)\s+(.+?)(?:\s+from\b|$)",
            r"(?:how\s+(?:long|far)\s+(?:is\s+it\s+)?(?:to\s+)?(?:drive\s+)?to\s+)\s*(.+?)(?:\s+from\b|$)",
            r"(?:travel\s+time\s+to)\s+(.+?)(?:\s+from\b|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.I)
            if match:
                return match.group(1).strip(" ?.")
        return ""

    @staticmethod
    def _maybe_extract_origin(query: str, destination: str) -> tuple[str, str]:
        """Try to pull an explicit 'from X to Y' origin out of the query.

        Args:
            query: Raw user message.
            destination: Already-extracted destination (may be updated).

        Returns:
            Tuple of (origin, destination) strings.
        """
        match = re.search(
            r"(?:from)\s+(.+?)\s+(?:to)\s+(.+?)(?:\s*\??\s*$)",
            query, re.I,
        )
        if match:
            return match.group(1).strip(), match.group(2).strip(" ?.")
        return "", destination

    @staticmethod
    def _extract_place_query(query: str) -> str:
        """Extract the search term from a places query.

        Args:
            query: Raw user message.

        Returns:
            Search term string.
        """
        patterns = [
            r"(?:find\s+(?:me\s+)?(?:a\s+)?|look\s+up\s+(?:a\s+)?)\s*(.+?)(?:\s+near\b|$)",
            r"(.+?)\s+near\s+(?:me|here|my\s+location)",
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.I)
            if match:
                term = match.group(1).strip(" ?.")
                # strip common filler words
                term = re.sub(r"\b(some|any|good|great|nearby)\b", "", term, flags=re.I)
                return re.sub(r"\s+", " ", term).strip()
        return query.strip(" ?.")


# ── Module-level helpers ──────────────────────────────────────────────────────

def _fetch_json(url: str, params: dict) -> dict:
    """Fetch a Google Maps API endpoint and return parsed JSON.

    Args:
        url: Base endpoint URL.
        params: Query parameters (including API key).

    Returns:
        Parsed JSON response dict.

    Raises:
        Exception: On HTTP or parsing errors.
    """
    full_url = f"{url}?{urlencode(params)}"
    raw = fetch_bytes(full_url, headers={"User-Agent": "Xochitl/1.0 (maps)"})
    return json.loads(raw.decode("utf-8", errors="ignore"))


def _default_location() -> str:
    """Return the user's saved home/default location from preferences.

    Returns:
        Location string, or empty string if none saved.
    """
    try:
        from src import database as db
        with db.get_connection() as conn:
            rows = db.search_preferences(conn, "home address location live", limit=10)
        for row in rows:
            key = str(row["preference_key"]).lower()
            val = str(row["preference_value"]).strip()
            if val and any(k in key for k in ("home", "address", "location", "live")):
                return val
    except Exception:
        pass
    return ""


def _format_directions(data: dict, origin: str, destination: str, mode: str) -> str:
    """Format a Directions API response into readable text.

    Args:
        data: Parsed Directions API response.
        origin: Origin string (used as fallback label).
        destination: Destination string (used as fallback label).
        mode: Travel mode string.

    Returns:
        Multi-line formatted directions string.
    """
    route = data["routes"][0]
    leg   = route["legs"][0]

    distance  = leg.get("distance", {}).get("text", "unknown distance")
    duration  = leg.get("duration", {}).get("text", "unknown duration")
    start_addr = leg.get("start_address", origin)
    end_addr   = leg.get("end_address", destination)
    steps      = leg.get("steps", [])

    mode_label = mode.capitalize()
    lines = [
        f"Directions from {start_addr} to {end_addr}:",
        f"  {mode_label}  ·  {distance}  ·  {duration}",
        "",
    ]

    for i, step in enumerate(steps[:8], 1):
        instruction = re.sub(r"<[^>]+>", "", step.get("html_instructions", "")).strip()
        step_dist   = step.get("distance", {}).get("text", "")
        lines.append(f"  {i}. {instruction}  ({step_dist})")

    if len(steps) > 8:
        lines.append(f"  … and {len(steps) - 8} more steps.")

    lines += ["", "Source: Google Maps."]
    return "\n".join(lines)


def _format_places(data: dict, query: str) -> str:
    """Format a Places API response into a readable list.

    Args:
        data: Parsed Places API response.
        query: Search query used (for the header line).

    Returns:
        Multi-line formatted places list string.
    """
    results = data.get("results", [])[:5]
    if not results:
        return f"No results found for '{query}'."

    lines = [f"Top results for '{query}':"]
    for place in results:
        name    = place.get("name", "Unknown")
        address = place.get("formatted_address", "")
        rating  = place.get("rating")
        n_reviews = place.get("user_ratings_total", 0)
        open_now  = place.get("opening_hours", {}).get("open_now")

        lines.append(f"\n• {name}")
        if address:
            lines.append(f"  {address}")
        if rating is not None:
            lines.append(f"  ★ {rating}  ({n_reviews} reviews)")
        if open_now is True:
            lines.append("  Open now")
        elif open_now is False:
            lines.append("  Closed")

    lines += ["", "Source: Google Maps."]
    return "\n".join(lines)


# ── Public utility (used by calendar_skill later) ─────────────────────────────

def get_travel_time(origin: str, destination: str, mode: str = "driving") -> str | None:
    """Return a plain travel-time string for use by other skills.

    Args:
        origin: Starting location string.
        destination: Ending location string.
        mode: Travel mode — 'driving' | 'walking' | 'transit' | 'bicycling'.

    Returns:
        Human-readable duration string (e.g. '23 mins') or None on failure.
    """
    api_key = get_secret("GOOGLE_MAPS_API_KEY", "")
    if not api_key or not origin or not destination:
        return None
    try:
        data = _fetch_json(_DIRECTIONS_URL, {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "key": api_key,
        })
        if data.get("status") != "OK":
            return None
        return data["routes"][0]["legs"][0]["duration"]["text"]
    except Exception:
        return None
