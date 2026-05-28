"""Structured weather lookup skill backed by Open-Meteo."""

from __future__ import annotations

import json
import re
from urllib.parse import quote_plus, urlencode

from src.exceptions import GeocodingError  # ARCH-ORCH-001 (CR-018)
from src.http_utils import fetch_bytes  # FR-API-005, NFR-API-002 (retry + rate limit)
from src.skills.base import Skill


_WEATHER_KEYWORDS = (
    "weather",
    "forecast",
    "temperature",
    "how hot",
    "how cold",
    "rain today",
    "is it raining",
)

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Maps common country names / aliases → ISO 3166-1 alpha-2 codes.
# "Georgia" is intentionally absent — it's also a US state, so we let the
# US-state disambiguation path handle ambiguous cases (Tbilisi is prominent
# enough to be found without a country filter).
_COUNTRY_CODES: dict[str, str] = {
    "afghanistan": "AF", "albania": "AL", "algeria": "DZ", "angola": "AO",
    "argentina": "AR", "armenia": "AM", "australia": "AU", "austria": "AT",
    "azerbaijan": "AZ", "bahrain": "BH", "bangladesh": "BD", "belarus": "BY",
    "belgium": "BE", "bolivia": "BO", "brazil": "BR", "bulgaria": "BG",
    "cambodia": "KH", "cameroon": "CM", "canada": "CA", "chile": "CL",
    "china": "CN", "colombia": "CO", "costa rica": "CR", "croatia": "HR",
    "cuba": "CU", "czech republic": "CZ", "czechia": "CZ", "denmark": "DK",
    "dominican republic": "DO", "ecuador": "EC", "egypt": "EG",
    "el salvador": "SV", "estonia": "EE", "ethiopia": "ET", "finland": "FI",
    "france": "FR", "germany": "DE", "ghana": "GH", "greece": "GR",
    "guatemala": "GT", "haiti": "HT", "honduras": "HN", "hong kong": "HK",
    "hungary": "HU", "iceland": "IS", "india": "IN", "indonesia": "ID",
    "iran": "IR", "iraq": "IQ", "ireland": "IE", "israel": "IL",
    "italy": "IT", "ivory coast": "CI", "jamaica": "JM", "japan": "JP",
    "jordan": "JO", "kazakhstan": "KZ", "kenya": "KE", "kuwait": "KW",
    "laos": "LA", "latvia": "LV", "lebanon": "LB", "libya": "LY",
    "lithuania": "LT", "luxembourg": "LU", "malaysia": "MY", "mali": "ML",
    "mexico": "MX", "moldova": "MD", "mongolia": "MN", "morocco": "MA",
    "mozambique": "MZ", "myanmar": "MM", "burma": "MM", "namibia": "NA",
    "nepal": "NP", "netherlands": "NL", "holland": "NL", "new zealand": "NZ",
    "nicaragua": "NI", "nigeria": "NG", "norway": "NO", "oman": "OM",
    "pakistan": "PK", "panama": "PA", "paraguay": "PY", "peru": "PE",
    "philippines": "PH", "poland": "PL", "portugal": "PT", "qatar": "QA",
    "romania": "RO", "russia": "RU", "rwanda": "RW", "saudi arabia": "SA",
    "senegal": "SN", "serbia": "RS", "singapore": "SG", "slovakia": "SK",
    "slovenia": "SI", "somalia": "SO", "south africa": "ZA",
    "south korea": "KR", "korea": "KR", "spain": "ES", "sri lanka": "LK",
    "sudan": "SD", "sweden": "SE", "switzerland": "CH", "syria": "SY",
    "taiwan": "TW", "tanzania": "TZ", "thailand": "TH", "tunisia": "TN",
    "turkey": "TR", "turkiye": "TR", "uganda": "UG", "ukraine": "UA",
    "united arab emirates": "AE", "uae": "AE",
    "united kingdom": "GB", "uk": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "united states": "US", "usa": "US", "america": "US",
    "uruguay": "UY", "uzbekistan": "UZ", "venezuela": "VE", "vietnam": "VN",
    "yemen": "YE", "zambia": "ZM", "zimbabwe": "ZW",
}

_US_STATE_ABBREVIATIONS = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}

_WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow",
    73: "moderate snow",
    75: "heavy snow",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


class WeatherSkill(Skill):
    # Implements FR-API-004
    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()
        if any(k in q for k in _WEATHER_KEYWORDS):
            return 0.95
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        return "I can check current weather through Open-Meteo. Want me to look it up?"

    def tool_definition(self) -> dict:
        # Implements FR-ORCH-005
        return {
            "name": "WeatherSkill",
            "description": "Gets current weather and today's forecast from Open-Meteo without an API key.",
            "when": "user asks for weather, forecast, current conditions, rain, heat, cold, or temperature in a location",
            "params": {
                "location": "City/state/country location text, for example 'Escondido, CA'",
                "query": "Original weather question when location is not extracted",
            },
            "timeout_secs": 15,
            "examples": [
                "what's the weather in San Diego?",
                "is it going to rain today?",
                "how cold is it outside?",
                "weather forecast for this week",
                "what's the temperature right now?",
            ],
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        location = (params.get("location") or "").strip()
        query = (params.get("query") or user_input).strip()
        if not location:
            location = self._extract_location(query)
        if not location:
            location = self._default_location_from_preferences(query)

        if not location:
            context["last_skill_success"] = False
            context["weather_error_type"] = "missing_location"
            return "I can check the weather, but I need a location first. You can say something like `remember that my default weather location is San Diego County, CA`."

        try:
            place = self._geocode(location)
            forecast = self._forecast(place["latitude"], place["longitude"])
        except Exception as exc:
            context["last_skill_success"] = False
            context["weather_error_type"] = "api"
            return f"I couldn't get structured weather from Open-Meteo right now: {exc}"

        context["last_skill_success"] = True
        context["last_weather_location"] = self._format_place(place)
        context.pop("weather_error_type", None)
        return self._format_weather(place, forecast)

    def _geocode(self, location: str) -> dict:
        city_part, country_code = self._split_country(location)
        for candidate in self._geocode_candidates(city_part):
            url = f"{_GEOCODE_URL}?name={quote_plus(candidate)}&count=10&language=en&format=json"
            if country_code:
                url += f"&countrycode={country_code}"
            data = self._fetch_json(url)
            results = data.get("results") or []
            first = self._best_geocode_result(results, city_part, country_code)
            if first:
                break
        else:
            raise GeocodingError(f"no matching location found for {location!r}")
        if "latitude" not in first or "longitude" not in first:
            raise GeocodingError(f"location result for {location!r} did not include coordinates")
        return first

    def _forecast(self, latitude: float, longitude: float) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join((
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "cloud_cover",
                "wind_speed_10m",
                "wind_direction_10m",
                "wind_gusts_10m",
            )),
            "daily": ",".join((
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
            )),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "auto",
            "forecast_days": 1,
        }
        return self._fetch_json(f"{_FORECAST_URL}?{urlencode(params)}")

    @staticmethod
    def _fetch_json(url: str) -> dict:
        # fetch_bytes handles SSRF validation, rate limiting, and retry (FR-API-005).
        raw = fetch_bytes(url, headers={"User-Agent": "Xochitl/1.0 (weather lookup)"})
        return json.loads(raw.decode("utf-8", errors="ignore"))

    @staticmethod
    def _extract_location(query: str) -> str:
        text = query.strip().strip("?!.")
        patterns = (
            r"\b(?:in|for|near|at)\s+(.+)$",
            r"\bweather\s+(.+)$",
            r"\bforecast\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return WeatherSkill._clean_location(match.group(1))
        return WeatherSkill._clean_location(text)

    @staticmethod
    def _clean_location(text: str) -> str:
        cleaned = re.sub(
            r"\b(?:today|tomorrow|tonight|right now|now|currently|current|weather|forecast|temperature|what is|what's|please|can you tell me|tell me|show me|check|look up)\b",
            " ",
            text,
            flags=re.I,
        )
        # Strip "the" only when NOT followed by a capital letter — preserves "The Hague", "The Bronx", etc.
        cleaned = re.sub(r"\bthe\b(?!\s+[A-Z])", " ", cleaned)
        # Strip standalone "in" only when NOT followed by a capital letter — preserves "Indiana", "In-cheon".
        cleaned = re.sub(r"\bin\b(?!\s+[A-Z])", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
        return cleaned

    @staticmethod
    def _default_location_from_preferences(query: str) -> str:
        # Implements AC-CR007-004 via DATA-DATA-004 structured preferences.
        try:
            from src import database as db

            with db.get_connection() as conn:
                rows = db.search_preferences(conn, f"{query} weather default geography location", limit=10)
            weather_rows = [row for row in rows if "weather" in str(row["preference_key"]).lower()]
            fallback_rows = [row for row in rows if row not in weather_rows]
            for row in weather_rows + fallback_rows:
                key = str(row["preference_key"]).lower()
                category = str(row["category"]).lower()
                value = str(row["preference_value"]).strip()
                if value and ("weather" in key or "geograph" in key or category in {"location", "weather"}):
                    return WeatherSkill._extract_location_from_preference(value)
        except Exception:
            return ""
        return ""

    @staticmethod
    def _extract_location_from_preference(value: str) -> str:
        match = re.search(r"(?:default geographic context|default weather location|home region|location)\s*(?:is|:)\s*(.+)$", value, re.I)
        if match:
            return WeatherSkill._clean_location(match.group(1))
        return WeatherSkill._clean_location(value)

    @staticmethod
    def _geocode_candidates(location: str) -> list[str]:
        cleaned = re.sub(r"\s+", " ", location).strip(" ,")
        candidates = [cleaned]
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]
        if len(parts) >= 2:
            city = parts[0]
            region = parts[1].upper().replace(".", "")
            expanded = _US_STATE_ABBREVIATIONS.get(region)
            if expanded:
                candidates.append(f"{city} {expanded}")
            candidates.append(city)
        elif " " in cleaned:
            # "Tijuana Mexico" style (no comma) — Open-Meteo's name param is city-only,
            # so strip trailing words one at a time as fallback candidates.
            words = cleaned.split()
            for i in range(len(words) - 1, 0, -1):
                candidates.append(" ".join(words[:i]))
        return list(dict.fromkeys(c for c in candidates if c))

    @staticmethod
    def _split_country(location: str) -> tuple[str, str | None]:
        """Return (city_part, iso2_code) by stripping a recognized country suffix."""
        for name in sorted(_COUNTRY_CODES, key=len, reverse=True):
            pattern = r",?\s+" + re.escape(name) + r"\s*$"
            match = re.search(pattern, location, re.I)
            if match:
                city = location[:match.start()].strip(", ")
                if city:
                    return city, _COUNTRY_CODES[name]
        return location, None

    @staticmethod
    def _best_geocode_result(
        results: list[dict],
        original_location: str,
        country_code: str | None = None,
    ) -> dict | None:
        if not results:
            return None
        # Prefer the result whose country_code matches the one we searched with.
        if country_code:
            for result in results:
                if str(result.get("country_code", "")).upper() == country_code.upper():
                    return result
        # Fall back to US-state matching when region is a known abbreviation.
        parts = [p.strip().lower() for p in original_location.split(",") if p.strip()]
        region = parts[1].upper().replace(".", "") if len(parts) >= 2 else ""
        expanded = _US_STATE_ABBREVIATIONS.get(region, "").lower()
        if expanded:
            for result in results:
                if str(result.get("admin1", "")).lower() == expanded:
                    return result
        return results[0]

    @staticmethod
    def _format_place(place: dict) -> str:
        parts = [str(place.get("name", "")).strip()]
        admin = str(place.get("admin1", "")).strip()
        country = str(place.get("country", "")).strip()
        if admin:
            parts.append(admin)
        if country:
            parts.append(country)
        return ", ".join(p for p in parts if p)

    def _format_weather(self, place: dict, forecast: dict) -> str:
        current = forecast.get("current") or {}
        daily = forecast.get("daily") or {}
        current_units = forecast.get("current_units") or {}
        daily_units = forecast.get("daily_units") or {}

        condition = _WEATHER_CODES.get(int(current.get("weather_code", -1)), "weather code unknown")
        today_code = self._first(daily.get("weather_code"))
        today_condition = _WEATHER_CODES.get(int(today_code), condition) if today_code is not None else condition

        temp_unit = current_units.get("temperature_2m", "F")
        wind_unit = self._normalize_unit(current_units.get("wind_speed_10m", "mph"))
        precip_unit = self._normalize_unit(current_units.get("precipitation", "in"))
        high_unit = daily_units.get("temperature_2m_max", temp_unit)

        lines = [
            f"Weather for {self._format_place(place)}:",
            f"- Current: {self._fmt(current.get('temperature_2m'))}{temp_unit}, {condition}; feels like {self._fmt(current.get('apparent_temperature'))}{temp_unit}.",
            f"- Today: high {self._fmt(self._first(daily.get('temperature_2m_max')))}{high_unit}, low {self._fmt(self._first(daily.get('temperature_2m_min')))}{high_unit}; {today_condition}.",
            f"- Wind: {self._fmt(current.get('wind_speed_10m'))} {wind_unit} {self._compass(current.get('wind_direction_10m'))}, gusts to {self._fmt(current.get('wind_gusts_10m'))} {wind_unit}.",
            f"- Humidity: {self._fmt(current.get('relative_humidity_2m'), decimals=0)}%; cloud cover {self._fmt(current.get('cloud_cover'), decimals=0)}%.",
            f"- Precipitation: {self._fmt(current.get('precipitation'))} {precip_unit}; today chance {self._fmt(self._first(daily.get('precipitation_probability_max')), decimals=0)}%.",
            "",
            "Source: Open-Meteo.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _first(value):
        if isinstance(value, list) and value:
            return value[0]
        return value

    @staticmethod
    def _fmt(value, decimals: int = 1) -> str:
        if value is None:
            return "unknown"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if decimals == 0:
                return str(round(value))
            return f"{value:.{decimals}f}".rstrip("0").rstrip(".")
        return str(value)

    @staticmethod
    def _normalize_unit(unit: str) -> str:
        return {"mp/h": "mph", "inch": "in"}.get(unit, unit)

    @staticmethod
    def _compass(degrees) -> str:
        if degrees is None:
            return ""
        directions = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
        idx = int((float(degrees) + 22.5) // 45) % 8
        return directions[idx]
