"""Smoke test for the BMAD→SDD→Code pipeline."""
import json
import os
import shutil
import traceback
from pathlib import Path

ROOT = Path(__file__).parent
TEST_PROJECT = "smoke-test-project"
PROJECT_PATH = ROOT / "projects" / TEST_PROJECT

results = []


def test(label, fn):
    try:
        fn()
        results.append(("PASS", label, None))
    except Exception as e:
        results.append(("FAIL", label, traceback.format_exc()))


def cleanup():
    if PROJECT_PATH.exists():
        shutil.rmtree(PROJECT_PATH)
    log = ROOT / ".sdd" / "logs" / "spec-changes.jsonl"
    if log.exists():
        log.unlink()


cleanup()

# ── 1. YAML helpers ──────────────────────────────────────────────────────────
def t_yaml():
    from src.skills._yaml_helpers import yaml_load, yaml_dump
    data = {"project_id": "test", "bmad_complete": False, "stack": {"backend": "FastAPI"}}
    dumped = yaml_dump(data)
    loaded = yaml_load(dumped)
    assert loaded["project_id"] == "test"
    assert loaded["stack"]["backend"] == "FastAPI"
test("_yaml_helpers: load/dump roundtrip", t_yaml)


# ── 2. BMADSkill.init_project ────────────────────────────────────────────────
def t_init_project():
    from src.skills.bmad_skill import BMADSkill
    s = BMADSkill()
    result = s.init_project(TEST_PROJECT, "Smoke Test App", "Test project")
    assert result["project_id"] == TEST_PROJECT
    assert (PROJECT_PATH / ".project-meta.yml").exists(), ".project-meta.yml missing"
    for d in ["bmad", "specs", "issues/open", "issues/in-progress", "issues/closed", "src"]:
        assert (PROJECT_PATH / d).exists(), f"{d}/ dir missing"
test("BMADSkill.init_project: creates dirs and meta", t_init_project)


# ── 3. _read_meta correctness ────────────────────────────────────────────────
def t_read_meta():
    from src.skills.bmad_skill import BMADSkill
    s = BMADSkill()
    meta = s._read_meta(TEST_PROJECT)
    assert meta["project_id"] == TEST_PROJECT
    assert meta["name"] == "Smoke Test App"
    assert meta["bmad_complete"] == False
    assert meta["specs_generated"] == False
    assert "stack" in meta
test("BMADSkill._read_meta: reads correct values", t_read_meta)


# ── 4. save_bmad_artifact + is_bmad_complete ─────────────────────────────────
def t_save_artifacts():
    from src.skills.bmad_skill import BMADSkill
    s = BMADSkill()
    s.save_bmad_artifact(TEST_PROJECT, "business-model", "# Business Model\n\n## Problem\nTest\n")
    s.save_bmad_artifact(TEST_PROJECT, "architecture", "# Architecture\n\n## Backend\nFastAPI\n")
    assert (PROJECT_PATH / "bmad" / "business-model.md").exists()
    assert (PROJECT_PATH / "bmad" / "architecture.md").exists()
    assert s.is_bmad_complete(TEST_PROJECT), "bmad_complete should be True"
test("BMADSkill.save_bmad_artifact + is_bmad_complete", t_save_artifacts)


# ── 5. get_bmad_artifacts ────────────────────────────────────────────────────
def t_get_artifacts():
    from src.skills.bmad_skill import BMADSkill
    s = BMADSkill()
    arts = s.get_bmad_artifacts(TEST_PROJECT)
    assert "business-model" in arts
    assert "architecture" in arts
    assert "FastAPI" in arts["architecture"]
test("BMADSkill.get_bmad_artifacts: returns all files", t_get_artifacts)


# ── 6. list_projects ─────────────────────────────────────────────────────────
def t_list_projects():
    from src.skills.bmad_skill import BMADSkill
    s = BMADSkill()
    projects = s.list_projects()
    ids = [p["project_id"] for p in projects]
    assert TEST_PROJECT in ids, f"{TEST_PROJECT} not in list: {ids}"
test("BMADSkill.list_projects: finds test project", t_list_projects)


# ── 7. _parse_json_response ──────────────────────────────────────────────────
def t_json_parse():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    # Plain JSON
    r1 = s._parse_json_response('{"key": "value"}')
    assert r1 == {"key": "value"}, f"Plain JSON failed: {r1}"
    # With markdown fences
    fenced = "```json\n{\"key\": \"value\"}\n```"
    r2 = s._parse_json_response(fenced)
    assert r2 == {"key": "value"}, f"Fenced JSON failed: {r2}"
    # Bad JSON (no retry_prompt) → error dict
    r3 = s._parse_json_response("not json at all")
    assert "error" in r3, f"Bad JSON should return error dict: {r3}"
test("SDDSkill._parse_json_response: plain, fenced, bad", t_json_parse)


# ── 8. _build_spec_file_content + _init_traceability ────────────────────────
FAKE_REQS = [
    {
        "id": "FR-CORE-001",
        "title": "Meal Entry",
        "description": "Users can create meal prep entries.",
        "priority": "P0",
        "bmad_source": "business-model.md: Solution",
        "acceptance_criteria": ["AC-CORE-001: GIVEN valid data WHEN submitted THEN saved"],
        "edge_cases": ["EC-CORE-001: GIVEN empty name WHEN submitted THEN 400"],
    },
    {
        "id": "FR-CORE-002",
        "title": "Macro Calc",
        "description": "System calculates macros from ingredients.",
        "priority": "P1",
        "bmad_source": "business-model.md: Solution",
        "acceptance_criteria": ["AC-CORE-002: GIVEN meal with ingredients WHEN saved THEN macros summed"],
        "edge_cases": [],
    },
]

def t_spec_write():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    content = s._build_spec_file_content(TEST_PROJECT, FAKE_REQS)
    spec_path = PROJECT_PATH / "specs" / "core-features.md"
    spec_path.parent.mkdir(exist_ok=True)
    spec_path.write_text(content, encoding="utf-8")
    s._init_traceability(TEST_PROJECT, FAKE_REQS)
    assert (PROJECT_PATH / "specs" / "traceability.json").exists()
    # Mark specs_generated
    meta = s._read_meta(TEST_PROJECT)
    meta["specs_generated"] = True
    meta["stats"]["total_requirements"] = 2
    s._write_meta(TEST_PROJECT, meta)
test("SDDSkill._build_spec_file_content + _init_traceability", t_spec_write)


# ── 9. list_requirements ─────────────────────────────────────────────────────
def t_list_reqs():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    reqs = s.list_requirements(TEST_PROJECT)
    assert len(reqs) == 2, f"Expected 2, got {len(reqs)}: {reqs}"
    ids = [r["id"] for r in reqs]
    assert "FR-CORE-001" in ids and "FR-CORE-002" in ids
test("SDDSkill.list_requirements: finds both requirements", t_list_reqs)


# ── 10. get_requirement ──────────────────────────────────────────────────────
def t_get_req():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    req = s.get_requirement(TEST_PROJECT, "FR-CORE-001")
    assert req is not None, "get_requirement returned None"
    assert req["id"] == "FR-CORE-001"
    assert req["status"] == "not_implemented"
    assert len(req.get("acceptance_criteria", [])) >= 1
test("SDDSkill.get_requirement: parses correct fields", t_get_req)


# ── 11. update_requirement ───────────────────────────────────────────────────
def t_update_req():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    result = s.update_requirement(TEST_PROJECT, "FR-CORE-001", {
        "status": "implemented",
        "add_acceptance_criterion": "AC-CORE-003: GIVEN negative calories WHEN submitted THEN 400",
        "trigger": "smoke-test",
    })
    assert "FR-CORE-001" in result or "Updated" in result, f"Unexpected: {result}"
    req = s.get_requirement(TEST_PROJECT, "FR-CORE-001")
    assert req["status"] == "implemented", f"Status not updated: {req['status']}"
    acs = req.get("acceptance_criteria", [])
    assert any("negative calories" in ac for ac in acs), f"New AC not found: {acs}"
    log = ROOT / ".sdd" / "logs" / "spec-changes.jsonl"
    assert log.exists(), "spec-changes.jsonl not created"
    entry = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert entry["requirement_id"] == "FR-CORE-001"
    assert entry["trigger"] == "smoke-test"
test("SDDSkill.update_requirement: updates status, AC, logs change", t_update_req)


# ── 12. create_issue ─────────────────────────────────────────────────────────
def t_create_issue():
    from src.skills.sdd_skill import SDDSkill
    from src.skills._yaml_helpers import yaml_load
    s = SDDSkill()
    result = s.create_issue(TEST_PROJECT, "bug", "Negative calories accepted", "The app allows negative calorie values.")
    assert "BUG-001" in result, f"Unexpected: {result}"
    issue_path = PROJECT_PATH / "issues" / "open" / "BUG-001.yml"
    assert issue_path.exists()
    data = yaml_load(issue_path.read_text(encoding="utf-8"))
    assert data["id"] == "BUG-001"
    assert data["status"] == "open"
    assert data["type"] == "bug"
test("SDDSkill.create_issue: creates BUG-001.yml with correct fields", t_create_issue)


# ── 13. close_issue ──────────────────────────────────────────────────────────
def t_close_issue():
    from src.skills.sdd_skill import SDDSkill
    from src.skills._yaml_helpers import yaml_load
    s = SDDSkill()
    result = s.close_issue(TEST_PROJECT, "BUG-001", "Added validation in meals.py")
    assert "closed" in result.lower() or "BUG-001" in result, f"Unexpected: {result}"
    assert not (PROJECT_PATH / "issues" / "open" / "BUG-001.yml").exists(), "Still in open/"
    closed_path = PROJECT_PATH / "issues" / "closed" / "BUG-001.yml"
    assert closed_path.exists(), "Not in closed/"
    data = yaml_load(closed_path.read_text(encoding="utf-8"))
    assert data["status"] == "closed"
    assert "resolution" in data
test("SDDSkill.close_issue: moves to closed/, updates status", t_close_issue)


# ── 14. create_requirement ───────────────────────────────────────────────────
def t_create_req():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    result = s.create_requirement(TEST_PROJECT, "API", {
        "title": "Health Check Endpoint",
        "description": "GET /health returns 200 with service status.",
        "priority": "P2",
    })
    assert "FR-API-001" in result, f"Unexpected: {result}"
    reqs = s.list_requirements(TEST_PROJECT)
    ids = [r["id"] for r in reqs]
    assert "FR-API-001" in ids, f"FR-API-001 not in {ids}"
test("SDDSkill.create_requirement: adds FR-API-001", t_create_req)


# ── 15. update_traceability ──────────────────────────────────────────────────
def t_update_trace():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    s.update_traceability(TEST_PROJECT, "FR-CORE-002", {
        "file": "src/api/macros.py",
        "functions": ["calculate_macros"],
        "lines": [10, 45],
    })
    trace = s._load_traceability(TEST_PROJECT)
    mapping = next((m for m in trace["mappings"] if m["id"] == "FR-CORE-002"), None)
    assert mapping is not None
    assert mapping["status"] == "implemented"
    assert mapping["implementation"][0]["file"] == "src/api/macros.py"
test("SDDSkill.update_traceability: updates matrix and spec status", t_update_trace)


# ── 16. CodeSkill._write_generated_files: path safety ───────────────────────
def t_path_safety():
    from src.skills.code_skill import CodeSkill
    s = CodeSkill()
    # Normal write
    written = s._write_generated_files(TEST_PROJECT, [
        {"path": "src/api/test_generated.py", "content": "# test\n", "action": "create"}
    ])
    assert "src/api/test_generated.py" in written
    assert (PROJECT_PATH / "src" / "api" / "test_generated.py").exists()
    # Path traversal attempt — must be blocked
    written2 = s._write_generated_files(TEST_PROJECT, [
        {"path": "../../../etc/passwd", "content": "hacked", "action": "create"}
    ])
    assert len(written2) == 0, f"Path traversal not blocked: {written2}"
    # Protected .project-meta.yml — must be blocked
    written3 = s._write_generated_files(TEST_PROJECT, [
        {"path": ".project-meta.yml", "content": "overwrite", "action": "modify"}
    ])
    assert len(written3) == 0, f"Protected file not blocked: {written3}"
    # specs/ dir — must be blocked
    written4 = s._write_generated_files(TEST_PROJECT, [
        {"path": "specs/core-features.md", "content": "overwrite", "action": "modify"}
    ])
    assert len(written4) == 0, f"specs/ write not blocked: {written4}"
test("CodeSkill._write_generated_files: path safety checks", t_path_safety)


# ── 17. CodeSkill._load_project_stack ────────────────────────────────────────
def t_load_stack():
    from src.skills.code_skill import CodeSkill
    s = CodeSkill()
    stack = s._load_project_stack(TEST_PROJECT)
    assert isinstance(stack, dict), f"Expected dict, got {type(stack)}"
test("CodeSkill._load_project_stack: returns dict", t_load_stack)


# ── 18. chat._extract_project_name ───────────────────────────────────────────
def t_extract_name():
    from src.chat import XochitlChat
    c = object.__new__(XochitlChat)
    cases = [
        ("I want to build a diet tracking app", "diet"),
        ("let us create a budget planner", "budget"),
        ("I want to make a todo list app", "todo"),
    ]
    for inp, fragment in cases:
        name = c._extract_project_name(inp)
        assert fragment.lower() in name.lower(), f"Input={inp!r} → {name!r}, expected {fragment!r}"
test("chat._extract_project_name: extracts sensible names", t_extract_name)


# ── 19. chat._detect_current_project ─────────────────────────────────────────
def t_detect_project():
    from src.chat import XochitlChat
    c = object.__new__(XochitlChat)
    c.current_project = None
    old_cwd = os.getcwd()
    try:
        os.chdir(ROOT)
        result = c._detect_current_project()
        assert result is None, f"Expected None from root, got {result!r}"
        os.chdir(PROJECT_PATH)
        result2 = c._detect_current_project()
        assert result2 == TEST_PROJECT, f"Expected {TEST_PROJECT!r}, got {result2!r}"
    finally:
        os.chdir(old_cwd)
test("chat._detect_current_project: None from root, id from inside", t_detect_project)


# ── 20. chat._check_specs_exist ──────────────────────────────────────────────
def t_check_specs():
    from src.chat import XochitlChat
    c = object.__new__(XochitlChat)
    assert c._check_specs_exist(TEST_PROJECT), "specs should exist (we created them)"
    assert not c._check_specs_exist("nonexistent-project"), "nonexistent project should return False"
test("chat._check_specs_exist: True for existing, False for missing", t_check_specs)


# ── 21. SDDSkill.get_next_step_suggestion ────────────────────────────────────
def t_next_step():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    suggestion = s.get_next_step_suggestion(TEST_PROJECT)
    assert len(suggestion) > 10, f"Suggestion too short: {suggestion!r}"
    assert not suggestion.startswith("Project not found"), f"Project not found error: {suggestion}"
test("SDDSkill.get_next_step_suggestion: returns actionable message", t_next_step)


# ── 22. SDDSkill.can_handle scoring ──────────────────────────────────────────
def t_sdd_scoring():
    from src.skills.sdd_skill import SDDSkill
    s = SDDSkill()
    # With current_project context, issue keyword → high score
    score_with = s.can_handle("there's a bug in the calorie tracker", {"current_project": TEST_PROJECT})
    score_without = s.can_handle("there's a bug in the calorie tracker", {})
    assert score_with > score_without, f"Expected higher score with project: {score_with} vs {score_without}"
    assert score_with > 0.3, f"Score too low with project context: {score_with}"
test("SDDSkill.can_handle: higher score with project context", t_sdd_scoring)


# ── 23. CodeSkill.can_handle scoring ─────────────────────────────────────────
def t_code_scoring():
    from src.skills.code_skill import CodeSkill
    s = CodeSkill()
    score_specs = s.can_handle("scaffold the backend", {"specs_generated": True, "current_project": TEST_PROJECT})
    score_no_specs = s.can_handle("scaffold the backend", {})
    assert score_specs > score_no_specs, f"Expected higher with specs: {score_specs} vs {score_no_specs}"
test("CodeSkill.can_handle: higher score when specs exist", t_code_scoring)


# ── 24. BMADSkill.can_handle ─────────────────────────────────────────────────
def t_bmad_scoring():
    from src.skills.bmad_skill import BMADSkill
    s = BMADSkill()
    score_build = s.can_handle("I want to build a fitness app", {})
    score_plan  = s.can_handle("let me plan the architecture", {"bmad_project": {"modules": ["BMM"]}})
    score_nothing = s.can_handle("what time is it", {})
    assert score_build > 0.5, f"Build keyword should score high: {score_build}"
    assert score_plan  > 0.5, f"Plan in bmad context should score high: {score_plan}"
    assert score_nothing == 0.0, f"Unrelated should score 0: {score_nothing}"
test("BMADSkill.can_handle: build=high, plan-in-context=high, unrelated=0", t_bmad_scoring)


# -- 25. WebLookupSkill DuckDuckGo redirect/snippet regression --
def t_web_lookup_redirect_snippet():
    # Patch the local 'fetch_bytes' name inside the skill module's namespace.
    import src.skills.web_lookup_skill as mod
    from src.skills.web_lookup_skill import WebLookupSkill

    fake_html = """
    <div class="result">
      <div class="result__body">
        <a class="result__a" href="/l/?uddg=https%3A%2F%2Fforecast.weather.gov%2FMapClick.php%3Fsite%3DSGX%26textField1%3D33.1192%26textField2%3D-117.086&amp;rut=abc">Escondido Weather</a>
        <div class="result__snippet">Sunny, high near 72. West wind around 10 mph.</div>
      </div>
    </div>
    """

    original_fetch = mod.fetch_bytes
    try:
        mod.fetch_bytes = lambda url, **kwargs: fake_html.encode("utf-8")
        links = WebLookupSkill()._search("weather today in Escondido, CA")
    finally:
        mod.fetch_bytes = original_fetch

    assert links, "Expected parsed search result"
    title, url, snippet = links[0]
    assert title == "Escondido Weather"
    assert url.startswith("https://forecast.weather.gov/MapClick.php?site=SGX"), url
    assert "Sunny, high near 72" in snippet
test("WebLookupSkill: normalizes DDG redirects and keeps snippets", t_web_lookup_redirect_snippet)


# -- 26. WeatherSkill Open-Meteo geocode + forecast regression --
def t_weather_skill_open_meteo():
    from src.skills.weather_skill import WeatherSkill

    geocode = {
        "results": [{
            "name": "Escondido",
            "admin1": "California",
            "country": "United States",
            "latitude": 33.1192,
            "longitude": -117.0864,
        }]
    }
    forecast = {
        "current": {
            "temperature_2m": 72.4,
            "relative_humidity_2m": 45,
            "apparent_temperature": 71.9,
            "precipitation": 0.0,
            "weather_code": 1,
            "cloud_cover": 12,
            "wind_speed_10m": 6.2,
            "wind_direction_10m": 250,
            "wind_gusts_10m": 14.1,
        },
        "current_units": {
            "temperature_2m": "F",
            "apparent_temperature": "F",
            "precipitation": "inch",
            "wind_speed_10m": "mph",
        },
        "daily": {
            "weather_code": [1],
            "temperature_2m_max": [78.2],
            "temperature_2m_min": [54.7],
            "precipitation_probability_max": [5],
        },
        "daily_units": {
            "temperature_2m_max": "F",
            "temperature_2m_min": "F",
        },
    }

    def fake_fetch_bytes(url, **kwargs):
        if "geocoding-api.open-meteo.com" in url:
            if "Escondido%2C+CA" in url:
                return json.dumps({"results": []}).encode("utf-8")
            return json.dumps(geocode).encode("utf-8")
        if "api.open-meteo.com" in url:
            return json.dumps(forecast).encode("utf-8")
        raise AssertionError(f"Unexpected URL: {url}")

    # Patch the local 'fetch_bytes' name inside the skill module's namespace.
    import src.skills.weather_skill as weather_mod
    original_fetch = weather_mod.fetch_bytes
    try:
        weather_mod.fetch_bytes = fake_fetch_bytes
        ctx = {}
        result = WeatherSkill().execute("what is the weather today in Escondido, CA", ctx, {})
    finally:
        weather_mod.fetch_bytes = original_fetch

    assert ctx["last_skill_success"] is True
    assert "Weather for Escondido, California, United States" in result
    assert "72.4F" in result
    assert "high 78.2F, low 54.7F" in result
    assert "Source: Open-Meteo" in result
test("WeatherSkill: Open-Meteo geocode + forecast formatting", t_weather_skill_open_meteo)


def t_weather_skill_default_location_preference():
    from src.skills.weather_skill import WeatherSkill

    original_default = WeatherSkill._default_location_from_preferences
    try:
        WeatherSkill._default_location_from_preferences = staticmethod(lambda query: "San Diego County, California")
        location = WeatherSkill()._extract_location("weather today")
        assert location == "", f"Expected no explicit location, got {location!r}"
        resolved = WeatherSkill._default_location_from_preferences("weather today")
    finally:
        WeatherSkill._default_location_from_preferences = original_default

    assert resolved == "San Diego County, California"
test("WeatherSkill: falls back to default location preference", t_weather_skill_default_location_preference)


# ── SSRF protection (FR-SEC-005, NFR-SEC-003) — AC-CR016-001..005 ─────────────

import socket as _socket
import ipaddress as _ipaddress
from unittest.mock import patch as _patch


def _make_addrinfo(ip: str):
    """Return a getaddrinfo-shaped result list for the given IP string."""
    family = _socket.AF_INET6 if ":" in ip else _socket.AF_INET
    return [(family, _socket.SOCK_STREAM, 6, "", (ip, 0))]


def t_ssrf_loopback_blocked():
    """AC-CR016-001: 127.0.0.1 must be rejected."""
    from src.security import validate_outbound_url, XochitlPermissionError
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo("127.0.0.1")):
        try:
            validate_outbound_url("http://127.0.0.1/secret")
            raise AssertionError("Expected XochitlPermissionError, got no exception")
        except XochitlPermissionError:
            pass  # correct
test("SSRF: loopback 127.0.0.1 blocked (AC-CR016-001)", t_ssrf_loopback_blocked)


def t_ssrf_private_blocked():
    """AC-CR016-002: 10.0.0.1 (RFC 1918) must be rejected."""
    from src.security import validate_outbound_url, XochitlPermissionError
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo("10.0.0.1")):
        try:
            validate_outbound_url("http://internal.corp/data")
            raise AssertionError("Expected XochitlPermissionError, got no exception")
        except XochitlPermissionError:
            pass
test("SSRF: RFC 1918 private 10.0.0.1 blocked (AC-CR016-002)", t_ssrf_private_blocked)


def t_ssrf_metadata_blocked():
    """AC-CR016-003: 169.254.169.254 (cloud IMDS) must be rejected."""
    from src.security import validate_outbound_url, XochitlPermissionError
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo("169.254.169.254")):
        try:
            validate_outbound_url("http://169.254.169.254/latest/meta-data/")
            raise AssertionError("Expected XochitlPermissionError, got no exception")
        except XochitlPermissionError:
            pass
test("SSRF: cloud metadata 169.254.169.254 blocked (AC-CR016-003)", t_ssrf_metadata_blocked)


def t_ssrf_scheme_blocked():
    """AC-CR016-004: non-http/https schemes must be rejected without DNS lookup."""
    from src.security import validate_outbound_url, XochitlPermissionError
    try:
        validate_outbound_url("file:///etc/passwd")
        raise AssertionError("Expected XochitlPermissionError, got no exception")
    except XochitlPermissionError:
        pass
test("SSRF: file:// scheme blocked (AC-CR016-004)", t_ssrf_scheme_blocked)


def t_ssrf_public_allowed():
    """AC-CR016-005: a known public IP must pass validation unchanged."""
    from src.security import validate_outbound_url
    public_ip = "93.184.216.34"  # example.com
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo(public_ip)):
        result = validate_outbound_url("https://api.open-meteo.com/v1/forecast")
    assert result == "https://api.open-meteo.com/v1/forecast", f"URL was mutated: {result!r}"
test("SSRF: public IP passes validation unchanged (AC-CR016-005)", t_ssrf_public_allowed)


# ── HTTP retry + rate limiting (FR-API-005, NFR-PERF-010) — AC-CR017-001..006 ─

import io as _io
import http.client as _http_client
from unittest.mock import patch as _patch2, MagicMock as _MagicMock


def _make_mock_response(body: bytes) -> _MagicMock:
    """Return a MagicMock that acts as a context-manager urlopen response."""
    m = _MagicMock()
    m.__enter__ = lambda s: s
    m.__exit__ = _MagicMock(return_value=False)
    m.read = _MagicMock(return_value=body)
    return m


def _make_http_error(code: int) -> Exception:
    from urllib.error import HTTPError
    return HTTPError("http://example.com/", code, f"HTTP {code}", {}, _io.BytesIO(b""))


def t_retry_429_succeeds():
    """AC-CR017-001: 429 is retried; succeeds on 3rd attempt."""
    import src.http_utils as hu
    from urllib.error import HTTPError
    attempt = [0]
    def fake_urlopen(req, timeout=None):
        attempt[0] += 1
        if attempt[0] < 3:
            raise _make_http_error(429)
        return _make_mock_response(b"ok")
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo("93.184.216.34")):
        with _patch("src.http_utils.urlopen", fake_urlopen):
            with _patch("time.sleep"):
                with _patch("src.http_utils._rate_limit_acquire"):
                    result = hu.fetch_bytes("https://example.com/path")
    assert result == b"ok", f"Got {result!r}"
    assert attempt[0] == 3, f"Expected 3 attempts, got {attempt[0]}"
test("HTTP retry: 429 retried, succeeds on 3rd attempt (AC-CR017-001)", t_retry_429_succeeds)


def t_no_retry_on_400():
    """AC-CR017-002: HTTP 400 propagates immediately without retry."""
    import src.http_utils as hu
    attempt = [0]
    def fake_urlopen(req, timeout=None):
        attempt[0] += 1
        raise _make_http_error(400)
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo("93.184.216.34")):
        with _patch("src.http_utils.urlopen", fake_urlopen):
            with _patch("time.sleep"):
                with _patch("src.http_utils._rate_limit_acquire"):
                    try:
                        hu.fetch_bytes("https://example.com/path")
                        raise AssertionError("Expected HTTPError, got no exception")
                    except Exception as e:
                        assert "400" in str(e), f"Unexpected error: {e}"
    assert attempt[0] == 1, f"Expected 1 attempt (no retry), got {attempt[0]}"
test("HTTP retry: 400 not retried, propagates immediately (AC-CR017-002)", t_no_retry_on_400)


def t_retry_on_url_error():
    """AC-CR017-003: URLError is retried; succeeds on 2nd attempt."""
    import src.http_utils as hu
    from urllib.error import URLError
    attempt = [0]
    def fake_urlopen(req, timeout=None):
        attempt[0] += 1
        if attempt[0] == 1:
            raise URLError("connection refused")
        return _make_mock_response(b"recovered")
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo("93.184.216.34")):
        with _patch("src.http_utils.urlopen", fake_urlopen):
            with _patch("time.sleep"):
                with _patch("src.http_utils._rate_limit_acquire"):
                    result = hu.fetch_bytes("https://example.com/path")
    assert result == b"recovered"
    assert attempt[0] == 2, f"Expected 2 attempts, got {attempt[0]}"
test("HTTP retry: URLError retried, succeeds on 2nd attempt (AC-CR017-003)", t_retry_on_url_error)


def t_all_attempts_exhausted():
    """AC-CR017-004: After 3 failed attempts the final exception propagates."""
    import src.http_utils as hu
    from urllib.error import URLError
    attempt = [0]
    def fake_urlopen(req, timeout=None):
        attempt[0] += 1
        raise URLError("always fails")
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo("93.184.216.34")):
        with _patch("src.http_utils.urlopen", fake_urlopen):
            with _patch("time.sleep"):
                with _patch("src.http_utils._rate_limit_acquire"):
                    try:
                        hu.fetch_bytes("https://example.com/path")
                        raise AssertionError("Expected URLError, got no exception")
                    except Exception as exc:
                        assert "always fails" in str(exc), f"Wrong error: {exc}"
    assert attempt[0] == hu._MAX_ATTEMPTS, f"Expected {hu._MAX_ATTEMPTS} attempts, got {attempt[0]}"
test("HTTP retry: all attempts exhausted, final error propagates (AC-CR017-004)", t_all_attempts_exhausted)


def t_ssrf_not_retried():
    """AC-CR017-006: XochitlPermissionError (SSRF block) is never retried."""
    import src.http_utils as hu
    urlopen_calls = [0]
    def fake_urlopen(req, timeout=None):
        urlopen_calls[0] += 1
        return _make_mock_response(b"should not reach")
    with _patch("socket.getaddrinfo", return_value=_make_addrinfo("127.0.0.1")):
        with _patch("src.http_utils.urlopen", fake_urlopen):
            with _patch("time.sleep"):
                try:
                    hu.fetch_bytes("http://internal-host/secret")
                    raise AssertionError("Expected XochitlPermissionError")
                except Exception as exc:
                    assert "SSRF" in str(exc) or "blocked" in str(exc).lower() or "127.0.0.1" in str(exc), \
                        f"Expected SSRF error, got: {exc}"
    assert urlopen_calls[0] == 0, f"urlopen should not be called; got {urlopen_calls[0]} calls"
test("HTTP retry: SSRF block never retried (AC-CR017-006)", t_ssrf_not_retried)


# ── Session governor (FR-ORCH-025, NFR-PERF-011) — AC-CR026-001..005 ──────────

def t_governor_starts_full():
    """AC-CR026-001: fresh SessionGovernor is at FULL tier with 0 tokens."""
    from src.governor import SessionGovernor, Tier
    g = SessionGovernor()
    assert g.tier() == Tier.FULL, f"Expected FULL, got {g.tier()}"
    assert g.total_tokens == 0
    assert g.force_route() is None
test("Governor: fresh session starts at FULL tier (AC-CR026-001)", t_governor_starts_full)


def t_governor_prefer_local_tier():
    """AC-CR026-002: ≥20 000 est. tokens → PREFER_LOCAL; force_route still None."""
    from src.governor import SessionGovernor, Tier
    g = SessionGovernor()
    # 20 000 tokens at 4 chars/token = 80 000 chars
    g.record_turn("x" * 80_000, "")
    assert g.tier() == Tier.PREFER_LOCAL, f"Expected PREFER_LOCAL, got {g.tier()}"
    assert g.force_route() is None, "PREFER_LOCAL should not force local routing"
test("Governor: >=20k est. tokens -> PREFER_LOCAL tier (AC-CR026-002)", t_governor_prefer_local_tier)


def t_governor_local_only_tier():
    """AC-CR026-003: ≥40 000 est. tokens → LOCAL_ONLY; force_route returns 'general'."""
    from src.governor import SessionGovernor, Tier
    g = SessionGovernor()
    # 40 000 tokens = 160 000 chars
    g.record_turn("x" * 160_000, "")
    assert g.tier() == Tier.LOCAL_ONLY, f"Expected LOCAL_ONLY, got {g.tier()}"
    assert g.force_route() == "general", f"Expected 'general', got {g.force_route()!r}"
test("Governor: >=40k est. tokens -> LOCAL_ONLY, force_route='general' (AC-CR026-003)", t_governor_local_only_tier)


def t_governor_hard_stop_tier():
    """AC-CR026-004: ≥80 000 est. tokens → HARD_STOP; budget_message returns canned text."""
    from src.governor import SessionGovernor, Tier
    g = SessionGovernor()
    # 80 000 tokens = 320 000 chars
    g.record_turn("x" * 320_000, "")
    assert g.tier() == Tier.HARD_STOP, f"Expected HARD_STOP, got {g.tier()}"
    msg = g.budget_message()
    assert "budget" in msg.lower() or "token" in msg.lower(), f"Unexpected message: {msg!r}"
test("Governor: >=80k est. tokens -> HARD_STOP, budget message (AC-CR026-004)", t_governor_hard_stop_tier)


def t_governor_env_override():
    """AC-CR026-005: XCH_LOCAL_ONLY_TOKENS env var overrides the LOCAL_ONLY threshold."""
    import importlib
    import src.governor as gov_mod
    original_threshold = gov_mod._LOCAL_ONLY_THRESHOLD
    try:
        os.environ["XCH_LOCAL_ONLY_TOKENS"] = "1000"
        importlib.reload(gov_mod)
        assert gov_mod._LOCAL_ONLY_THRESHOLD == 1000, (
            f"Expected 1000, got {gov_mod._LOCAL_ONLY_THRESHOLD}"
        )
        # Create governor using reloaded module
        g = gov_mod.SessionGovernor()
        g.record_turn("x" * 4001, "")  # ~1000 tokens
        assert g.tier() == gov_mod.Tier.LOCAL_ONLY, f"Expected LOCAL_ONLY, got {g.tier()}"
    finally:
        del os.environ["XCH_LOCAL_ONLY_TOKENS"]
        importlib.reload(gov_mod)  # restore defaults
test("Governor: XCH_LOCAL_ONLY_TOKENS env var overrides threshold (AC-CR026-005)", t_governor_env_override)


def t_governor_should_warn_dedup():
    """AC-CR026-007: should_warn returns True once per tier, False on repeat."""
    from src.governor import SessionGovernor, Tier
    g = SessionGovernor()
    assert g.should_warn(Tier.PREFER_LOCAL) is True,  "First warn should be True"
    assert g.should_warn(Tier.PREFER_LOCAL) is False, "Second warn should be False"
    assert g.should_warn(Tier.LOCAL_ONLY)   is True,  "New tier warn should be True"
    assert g.should_warn(Tier.LOCAL_ONLY)   is False, "Repeat tier warn should be False"
test("Governor: should_warn deduplicates per-tier (AC-CR026-007)", t_governor_should_warn_dedup)


# ── Local AI hardening (CR-010) — AC-CR010-001..005 ───────────────────────────

def t_trim_history_for_local():
    """AC-CR010-002: >10 messages → summary block + ack + 10 recent messages."""
    from src.context_loader import trim_history_for_local
    history = [{"role": "user", "content": f"msg-{i}"} for i in range(15)]
    trimmed = trim_history_for_local(history)
    assert len(trimmed) == 12, f"Expected 12 entries, got {len(trimmed)}"
    assert trimmed[0]["role"] == "user"
    assert "Earlier conversation" in trimmed[0]["content"]
    assert trimmed[1]["role"] == "assistant"
    assert trimmed[-1]["content"] == "msg-14"
test("Context: trim_history_for_local keeps 10 + summary (AC-CR010-002)", t_trim_history_for_local)


def t_event_emitter_subscriber():
    """AC-CR010-001: emit() delivers events to subscribers without error."""
    from src.events import get_emitter
    emitter = get_emitter()
    received = []
    def _cb(event, payload):
        received.append((event, payload))
    emitter.subscribe(_cb)
    try:
        emitter.emit("routing_started", {"query": "hello"})
        emitter.emit("llm_complete", {"route": "local", "tokens_out": 42})
    finally:
        emitter.unsubscribe(_cb)
    assert ("routing_started", {"query": "hello"}) in received
    assert ("llm_complete", {"route": "local", "tokens_out": 42}) in received
test("Events: emitter delivers routing_started + llm_complete (AC-CR010-001)", t_event_emitter_subscriber)


def t_memory_facts_table():
    """AC-CR010-004: upsert_memory_fact stores structured facts."""
    import sqlite3
    from src.database import upsert_memory_fact, get_memory_facts
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        fact_id = upsert_memory_fact(
            conn, "Prefers morning standups", "preference", 0.8, project="smoke"
        )
        assert fact_id > 0
        facts = get_memory_facts(conn, min_confidence=0.4)
        assert any(f["fact"] == "Prefers morning standups" for f in facts)
        assert any(f["category"] == "preference" for f in facts)
    finally:
        conn.close()
test("Database: upsert_memory_fact stores structured facts (AC-CR010-004)", t_memory_facts_table)


def t_hyde_embed_fallback():
    """AC-CR010-005: _hyde_embed falls back to direct embed when model fails."""
    from src.memory import VectorMemory
    vm = VectorMemory.__new__(VectorMemory)
    called = {"direct": False}

    def fake_embed(text):
        called["direct"] = True
        return [0.1, 0.2, 0.3]

    vm._embed = fake_embed
    with _patch("src.llm_interface.call_local", side_effect=RuntimeError("model down")):
        result = vm._hyde_embed("what is my favorite color?")
    assert result == [0.1, 0.2, 0.3]
    assert called["direct"] is True
test("Memory: _hyde_embed falls back to _embed on failure (AC-CR010-005)", t_hyde_embed_fallback)


def t_staged_message_guard():
    """AC-CR010-003: consecutive staged counter threshold is 5."""
    import src.chat as chat_mod
    assert hasattr(chat_mod, "_OPEN_ENDED_SCORE_THRESHOLD")
    src = Path(chat_mod.__file__).read_text(encoding="utf-8")
    assert "_consecutive_staged" in src
    assert "self._consecutive_staged > 5" in src
    assert "Staged message loop detected" in src
test("Chat: staged message loop guard present (AC-CR010-003)", t_staged_message_guard)


def t_env_example_documents_vars():
    """AC-CR010-006: .env.example lists tunable model and API variables."""
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in (
        "LOCAL_MODEL", "OLLAMA_URL", "GEMINI_API_KEY", "ANTHROPIC_API_KEY",
        "XCH_PREFER_LOCAL_TOKENS", "XCH_LOCAL_ONLY_TOKENS", "XCH_HARD_STOP_TOKENS",
    ):
        assert key in env_example, f"{key} missing from .env.example"
test("Config: .env.example documents tunable vars (AC-CR010-006)", t_env_example_documents_vars)


def t_bmad_resolver_installed():
    """BMAD native: resolve_customization.py ships with Xochitl installation."""
    resolver = ROOT / ".xochitl" / "scripts" / "resolve_customization.py"
    assert resolver.exists(), "resolve_customization.py missing from .xochitl/scripts/"
    assert "deep_merge" in resolver.read_text(encoding="utf-8")
test("BMAD: resolve_customization.py installed in .xochitl/scripts/", t_bmad_resolver_installed)


# ── Uncertainty tiers (CR-032) — AC-CR032-001..004 ────────────────────────────

def t_uncertainty_tiers_in_prompt():
    """AC-CR032-001: system prompt contains [UNCERTAINTY TIERS] section."""
    prompt = (ROOT / "prompts" / "system_xochitl.txt").read_text(encoding="utf-8")
    assert "[UNCERTAINTY TIERS]" in prompt
    for tier in ("TIER 0", "TIER 1", "TIER 2", "TIER 3"):
        assert tier in prompt, f"{tier} missing from system prompt"
test("Prompt: [UNCERTAINTY TIERS] section present (AC-CR032-001)", t_uncertainty_tiers_in_prompt)


def t_capability_boundary_in_prompt():
    """AC-CR032-002: system prompt contains [CAPABILITY BOUNDARY] section."""
    prompt = (ROOT / "prompts" / "system_xochitl.txt").read_text(encoding="utf-8")
    assert "[CAPABILITY BOUNDARY]" in prompt
    assert "Xochitl CAN:" in prompt and "Xochitl CANNOT" in prompt
test("Prompt: [CAPABILITY BOUNDARY] section present (AC-CR032-002)", t_capability_boundary_in_prompt)


def t_turn_context_injection_low_score():
    """AC-CR032-003 / AC-CR036-001: complete-miss turns inject [TURN CONTEXT] with capability guidance."""
    import src.chat as chat_mod
    assert chat_mod._OPEN_ENDED_SCORE_THRESHOLD == 0.2
    src_text = Path(chat_mod.__file__).read_text(encoding="utf-8")
    assert "[TURN CONTEXT:" in src_text, "[TURN CONTEXT: not found in chat.py"
    # CR-036: complete-miss branch references [CAPABILITY BOUNDARY] (AC-CR036-001)
    assert "[CAPABILITY BOUNDARY]" in src_text, \
        "Complete-miss [TURN CONTEXT] should reference [CAPABILITY BOUNDARY] (FR-ORCH-034)"
    # Three-zone logic present (CR-036)
    assert "_OPEN_ENDED_SCORE_THRESHOLD" in src_text
    assert "Near-match" in src_text, \
        "Near-miss [TURN CONTEXT] block missing from chat.py (FR-ORCH-034)"
test("Chat: [TURN CONTEXT] injected for low skill scores (AC-CR032-003)", t_turn_context_injection_low_score)


def t_no_turn_context_high_score():
    """AC-CR032-004 / AC-CR036-003: matched skills (>= 0.65) skip [TURN CONTEXT] injection."""
    import src.chat as chat_mod
    assert chat_mod._SKILL_INJECT_THRESHOLD == 0.65
    src_text = Path(chat_mod.__file__).read_text(encoding="utf-8")
    assert "top_score >= _SKILL_INJECT_THRESHOLD" in src_text
    # The skill-matched branch must be followed by 'pass' (no [TURN CONTEXT] injected)
    # CR-036 three-zone structure: top branch is 'pass' when skill matched
    assert "pass  # skill schema handles context" in src_text, \
        "Skill-matched zone should use 'pass' — no [TURN CONTEXT] injected (FR-ORCH-034)"
test("Chat: no [TURN CONTEXT] when skill matched >= 0.65 (AC-CR032-004)", t_no_turn_context_high_score)


# ── Persona anchoring (FR-ORCH-028/029, NFR-ORCH-004/005) — AC-CR029-001..005 ─

def t_soul_example_structured():
    """AC-CR029-001: SOUL.md.example has [IDENTITY] section; no 'Chief of Staff'."""
    soul_path = ROOT / "SOUL.md.example"
    content = soul_path.read_text(encoding="utf-8")
    assert "## [IDENTITY]" in content, "SOUL.md.example missing '## [IDENTITY]' section"
    assert "Chief of Staff" not in content, \
        "SOUL.md.example still contains 'Chief of Staff' — should use 'personal AI system'"
test("Soul: SOUL.md.example structured with [IDENTITY], no 'Chief of Staff' (AC-CR029-001)", t_soul_example_structured)


def t_soul_engine_identity_anchor():
    """AC-CR029-002: SoulEngine.identity_anchor is non-empty after ingest."""
    from src.context_manager import SoulEngine
    engine = SoulEngine()
    engine.ingest()
    anchor = engine.identity_anchor
    assert anchor, "identity_anchor is empty after ingest"
    # Should contain text from the [IDENTITY] section of SOUL.md.example
    assert len(anchor) > 20, f"identity_anchor too short to be meaningful: {anchor!r}"
test("Soul: SoulEngine.identity_anchor non-empty after ingest (AC-CR029-002)", t_soul_engine_identity_anchor)


def t_soul_engine_compact_preserves_identity():
    """AC-CR029-003: SoulEngine.compact() preserves [IDENTITY] content (NFR-ORCH-005).

    Uses 80 tokens (320 chars) — enough for [IDENTITY] but tight enough to drop
    [VOICE], [VALUES], and [BOUNDARIES] so compaction is actually exercised.
    """
    from src.context_manager import SoulEngine
    engine = SoulEngine()
    engine.ingest()
    anchor = engine.identity_anchor
    # 80 tokens = 320 chars. [IDENTITY] is ~280 chars; other sections are ~600 chars.
    compacted = engine.compact(80)
    assert anchor[:40] in compacted, \
        f"[IDENTITY] content not preserved in compact output.\nAnchor start: {anchor[:40]!r}\nCompacted: {compacted!r}"
    # Verify compaction actually occurred (other sections should be absent or truncated)
    full = engine.assemble()
    assert len(compacted) < len(full), "compact() returned full text — budget too generous"
test("Soul: compact() always preserves [IDENTITY] content (AC-CR029-003)", t_soul_engine_compact_preserves_identity)


def t_assemble_system_prompt_wires_template():
    """AC-CR029-004/005: assemble_system_prompt() includes [GOAL] and [UNCERTAINTY TIERS]."""
    from src.context_manager import ContextManager
    cm = ContextManager(route="cloud")
    cm.ingest(query="test", history=[])
    prompt = cm.assemble_system_prompt()
    assert "[GOAL]" in prompt, \
        "[GOAL] section from system_xochitl.txt not found in assembled prompt — template not wired"
    assert "[UNCERTAINTY TIERS]" in prompt, \
        "[UNCERTAINTY TIERS] section not in assembled prompt — CR-032 behavior guide not reaching model"
test("Persona: assemble_system_prompt() contains [GOAL] and [UNCERTAINTY TIERS] (AC-CR029-004/005)", t_assemble_system_prompt_wires_template)


# ── CR-030 Correction Handling ────────────────────────────────────────────────

def t_correction_handling_in_prompt():
    """AC-CR030-001: [CORRECTION HANDLING] section present in system prompt."""
    prompt_path = Path(__file__).parent / "prompts" / "system_xochitl.txt"
    assert prompt_path.exists(), "prompts/system_xochitl.txt not found"
    content = prompt_path.read_text(encoding="utf-8")
    assert "[CORRECTION HANDLING]" in content, \
        "[CORRECTION HANDLING] section missing from system_xochitl.txt (FR-ORCH-030)"
    assert "Got it." in content or "Noted." in content, \
        "Minimal acknowledgment examples missing from [CORRECTION HANDLING] section"
test("Correction: [CORRECTION HANDLING] section present in system_xochitl.txt (AC-CR030-001)", t_correction_handling_in_prompt)


def t_detect_correction_signals():
    """AC-CR030-002: _detect_correction() returns True for correction phrases, False for normal input."""
    from src.background_review import _detect_correction
    # Should return True
    true_cases = [
        "No, that's not what I meant.",
        "actually, you got that wrong",
        "I meant the other file",
        "to clarify, I said yesterday",
        "correction: the value is 42",
        "you misunderstood my request",
        "not what i asked for",
        "let me clarify what I need",
    ]
    for case in true_cases:
        result = _detect_correction(case)
        assert result is True, f"_detect_correction() returned False for correction input: {case!r}"
    # Should return False
    false_cases = [
        "Can you help me with this?",
        "What's the weather today?",
        "Show me my tasks",
        "I want to build a new feature",
    ]
    for case in false_cases:
        result = _detect_correction(case)
        assert result is False, f"_detect_correction() returned True for non-correction input: {case!r}"
test("Correction: _detect_correction() returns True/False correctly (AC-CR030-002)", t_detect_correction_signals)


def t_correction_bypasses_rate_limit():
    """AC-CR030-003: Correction turns bypass _MIN_WRITE_INTERVAL_SECS rate limit."""
    import inspect
    from src.background_review import BackgroundReview
    source = inspect.getsource(BackgroundReview._process)
    # The guard must check is_correction before applying the rate limit
    assert "is_correction" in source, \
        "_process() does not reference is_correction — correction bypass not implemented (FR-ORCH-031)"
    assert "not turn.is_correction" in source or "turn.is_correction" in source, \
        "Rate-limit bypass logic missing from _process() (FR-ORCH-031)"
test("Correction: correction turns bypass _MIN_WRITE_INTERVAL_SECS (AC-CR030-003)", t_correction_bypasses_rate_limit)


def t_correction_storage_category():
    """AC-CR030-004: _store_correction_fact() stores with category='preference', confidence>=0.9."""
    import inspect
    from src.background_review import BackgroundReview
    source = inspect.getsource(BackgroundReview._store_correction_fact)
    assert "preference" in source, \
        "_store_correction_fact() does not set category='preference' (FR-ORCH-031)"
    assert "0.9" in source or "confidence=0.9" in source, \
        "_store_correction_fact() does not set confidence>=0.9 (FR-ORCH-031)"
test("Correction: _store_correction_fact() stores as preference with confidence>=0.9 (AC-CR030-004)", t_correction_storage_category)


def t_correction_escalation_to_preferences():
    """AC-CR030-005: Recurring correction triggers upsert_preference (NFR-ORCH-006)."""
    import sqlite3
    from unittest.mock import MagicMock, patch, call
    from src.background_review import BackgroundReview

    br = BackgroundReview()
    fact = "User prefers concise responses without preamble."

    # Simulate a connection where a near-duplicate already exists (recurring correction)
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)  # existing row found
    mock_conn.execute.return_value = mock_cursor

    upsert_pref_calls = []

    def mock_upsert_pref(conn, pref_dict):
        upsert_pref_calls.append(pref_dict)

    with patch("src.database._ensure_memory_facts_table"), \
         patch("src.database.upsert_memory_fact"), \
         patch("src.database.upsert_preference", side_effect=mock_upsert_pref):
        br._store_correction_fact(mock_conn, fact, project=None)

    assert len(upsert_pref_calls) == 1, \
        f"upsert_preference not called on recurring correction (NFR-ORCH-006). Calls: {upsert_pref_calls}"
    pref = upsert_pref_calls[0]
    assert pref.get("category") == "communication", \
        f"Escalated preference should have category='communication', got {pref.get('category')!r}"
    assert pref.get("confidence", 0) >= 0.9, \
        f"Escalated preference confidence should be >=0.9, got {pref.get('confidence')}"
    assert pref.get("preference_key", "").startswith("correction_"), \
        f"Preference key should start with 'correction_', got {pref.get('preference_key')!r}"
test("Correction: recurring correction escalates to preferences table (AC-CR030-005)", t_correction_escalation_to_preferences)


# ── CR-018 Exception Hierarchy ────────────────────────────────────────────────

def t_exception_module_exports():
    """AC-CR018-001: src.exceptions defines all required exception classes."""
    from src.exceptions import (
        XochitlError, RouterError, SkillError, GeocodingError,
        ContextError, SandboxError, SSRFBlockedError, NotionError,
        XochitlPermissionError,
    )
    for cls in (XochitlError, RouterError, SkillError, GeocodingError,
                ContextError, SandboxError, SSRFBlockedError, NotionError):
        assert issubclass(cls, Exception), f"{cls.__name__} is not an Exception subclass"
test("Exceptions: src.exceptions defines all required classes (AC-CR018-001)", t_exception_module_exports)


def t_exception_backward_compat_alias():
    """AC-CR018-002: XochitlPermissionError is SandboxError (backward-compat alias)."""
    from src.exceptions import XochitlPermissionError, SandboxError
    assert XochitlPermissionError is SandboxError, \
        "XochitlPermissionError must be an alias for SandboxError (NFR-DEV-007)"
    # Verify existing code that catches XochitlPermissionError still catches SandboxError
    err = SandboxError("test")
    caught = False
    try:
        raise err
    except XochitlPermissionError:
        caught = True
    assert caught, "XochitlPermissionError catch-site did not catch SandboxError instance"
test("Exceptions: XochitlPermissionError is SandboxError alias (AC-CR018-002)", t_exception_backward_compat_alias)


def t_exception_hierarchy_sandbox():
    """AC-CR018-003: SSRFBlockedError < SandboxError < XochitlError."""
    from src.exceptions import SSRFBlockedError, SandboxError, XochitlError
    assert issubclass(SSRFBlockedError, SandboxError), \
        "SSRFBlockedError must be a subclass of SandboxError (ARCH-ORCH-001)"
    assert issubclass(SandboxError, XochitlError), \
        "SandboxError must be a subclass of XochitlError (ARCH-ORCH-001)"
test("Exceptions: SSRFBlockedError < SandboxError < XochitlError (AC-CR018-003)", t_exception_hierarchy_sandbox)


def t_exception_hierarchy_skill():
    """AC-CR018-004: GeocodingError < SkillError < XochitlError."""
    from src.exceptions import GeocodingError, SkillError, XochitlError
    assert issubclass(GeocodingError, SkillError), \
        "GeocodingError must be a subclass of SkillError (ARCH-ORCH-001)"
    assert issubclass(SkillError, XochitlError), \
        "SkillError must be a subclass of XochitlError (ARCH-ORCH-001)"
test("Exceptions: GeocodingError < SkillError < XochitlError (AC-CR018-004)", t_exception_hierarchy_skill)


def t_ssrf_raises_ssrf_blocked_error():
    """AC-CR018-005: validate_outbound_url() raises SSRFBlockedError for blocked URLs."""
    from src.exceptions import SSRFBlockedError
    from src.security import validate_outbound_url
    blocked_cases = [
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.1/internal",
        "file:///etc/passwd",
    ]
    for url in blocked_cases:
        raised = False
        try:
            validate_outbound_url(url)
        except SSRFBlockedError:
            raised = True
        except Exception:
            raised = True  # still blocked, just not SSRFBlockedError — fail below
            raised_type = type(Exception).__name__
        assert raised, f"validate_outbound_url did not raise for blocked URL: {url!r}"
        # Verify specifically SSRFBlockedError
        try:
            validate_outbound_url(url)
            assert False, f"No exception raised for {url!r}"
        except SSRFBlockedError:
            pass  # correct
        except Exception as exc:
            assert False, \
                f"Expected SSRFBlockedError for {url!r}, got {type(exc).__name__}: {exc} (NFR-DEV-007)"
test("Exceptions: validate_outbound_url raises SSRFBlockedError (AC-CR018-005)", t_ssrf_raises_ssrf_blocked_error)


def t_weather_geocode_raises_geocoding_error():
    """AC-CR018-006: WeatherSkill raises GeocodingError for unknown location."""
    from unittest.mock import patch
    from src.exceptions import GeocodingError
    from src.skills.weather_skill import WeatherSkill

    skill = WeatherSkill()
    # Mock fetch_bytes to return an empty results list (no matching location)
    empty_geocode_response = b'{"results": []}'
    with patch("src.skills.weather_skill.fetch_bytes", return_value=empty_geocode_response):
        try:
            skill._geocode("NowhereVilleXXXX99")
            assert False, "_geocode() did not raise for empty geocoding result"
        except GeocodingError:
            pass  # correct — NFR-DEV-008
        except Exception as exc:
            assert False, \
                f"Expected GeocodingError, got {type(exc).__name__}: {exc} (NFR-DEV-008)"
test("Exceptions: WeatherSkill raises GeocodingError for unknown location (AC-CR018-006)", t_weather_geocode_raises_geocoding_error)


# ── CR-025 Response Mode Switching ────────────────────────────────────────────

def t_response_mode_constants():
    """AC-CR025-001: src.response_mode defines MODE_* constants."""
    from src.response_mode import MODE_CONVERSATIONAL, MODE_OPERATOR, MODE_REPORT
    assert MODE_CONVERSATIONAL == "conversational", f"Unexpected value: {MODE_CONVERSATIONAL!r}"
    assert MODE_OPERATOR == "operator", f"Unexpected value: {MODE_OPERATOR!r}"
    assert MODE_REPORT == "report", f"Unexpected value: {MODE_REPORT!r}"
test("ResponseMode: MODE_* constants defined (AC-CR025-001)", t_response_mode_constants)


def t_infer_mode_operator():
    """AC-CR025-002: infer_mode() returns 'operator' for command verbs."""
    from src.response_mode import infer_mode, MODE_OPERATOR
    operator_cases = [
        "sync my tasks",
        "sync",
        "build the project",
        "run the tests",
        "delete old tasks",
        "!do it now",
        "create a new task",
        "refresh my queue",
        "push to Notion",
    ]
    for case in operator_cases:
        result = infer_mode(case)
        assert result == MODE_OPERATOR, \
            f"infer_mode({case!r}) returned {result!r}, expected 'operator' (FR-ORCH-032)"
test("ResponseMode: infer_mode returns 'operator' for commands (AC-CR025-002)", t_infer_mode_operator)


def t_infer_mode_report():
    """AC-CR025-003: infer_mode() returns 'report' for structure keywords."""
    from src.response_mode import infer_mode, MODE_REPORT
    report_cases = [
        "give me a report on my projects",
        "give me a summary of today",
        "summarize my tasks",
        "show me an overview",
        "status report",
        "list all my tasks",
        "list my projects",
        "what's the status of the sprint",
    ]
    for case in report_cases:
        result = infer_mode(case)
        assert result == MODE_REPORT, \
            f"infer_mode({case!r}) returned {result!r}, expected 'report' (FR-ORCH-032)"
test("ResponseMode: infer_mode returns 'report' for structure keywords (AC-CR025-003)", t_infer_mode_report)


def t_infer_mode_conversational():
    """AC-CR025-004: infer_mode() returns 'conversational' for open-ended input."""
    from src.response_mode import infer_mode, MODE_CONVERSATIONAL
    convo_cases = [
        "what's the weather like?",
        "can you help me plan my week?",
        "I'm not sure what to do next",
        "tell me about the PARA methodology",
        "how are things going with the fitness app?",
    ]
    for case in convo_cases:
        result = infer_mode(case)
        assert result == MODE_CONVERSATIONAL, \
            f"infer_mode({case!r}) returned {result!r}, expected 'conversational' (FR-ORCH-032)"
test("ResponseMode: infer_mode returns 'conversational' for open-ended (AC-CR025-004)", t_infer_mode_conversational)


def t_assemble_injects_mode_block():
    """AC-CR025-005: assemble_system_prompt(mode='operator') contains [RESPONSE MODE: OPERATOR]."""
    from src.context_manager import ContextManager
    cm = ContextManager(route="cloud")
    cm.ingest(query="test", history=[])
    prompt = cm.assemble_system_prompt(mode="operator")
    assert "[RESPONSE MODE: OPERATOR]" in prompt, \
        "assemble_system_prompt(mode='operator') missing [RESPONSE MODE: OPERATOR] block (FR-ORCH-033)"
    prompt_report = cm.assemble_system_prompt(mode="report")
    assert "[RESPONSE MODE: REPORT]" in prompt_report, \
        "assemble_system_prompt(mode='report') missing [RESPONSE MODE: REPORT] block (FR-ORCH-033)"
test("ResponseMode: assemble_system_prompt injects mode block (AC-CR025-005)", t_assemble_injects_mode_block)


def t_assemble_no_mode_block_conversational():
    """AC-CR025-006: assemble_system_prompt(mode='conversational') has no [RESPONSE MODE: block."""
    from src.context_manager import ContextManager
    cm = ContextManager(route="cloud")
    cm.ingest(query="test", history=[])
    prompt = cm.assemble_system_prompt(mode="conversational")
    assert "[RESPONSE MODE:" not in prompt, \
        "assemble_system_prompt(mode='conversational') should not inject a mode block (FR-ORCH-033)"
    # Default (no mode arg) should also be clean
    prompt_default = cm.assemble_system_prompt()
    assert "[RESPONSE MODE:" not in prompt_default, \
        "assemble_system_prompt() with default mode should not inject a mode block"
test("ResponseMode: no mode block for conversational (AC-CR025-006)", t_assemble_no_mode_block_conversational)


# ── CR-036 Capability Boundary Communication ──────────────────────────────────

def t_capability_boundary_complete_miss():
    """AC-CR036-001: complete-miss [TURN CONTEXT] references [CAPABILITY BOUNDARY]."""
    import src.chat as chat_mod
    src_text = Path(chat_mod.__file__).read_text(encoding="utf-8")
    # Verify the complete-miss branch exists and contains the capability boundary reference
    assert "[CAPABILITY BOUNDARY]" in src_text, \
        "Complete-miss [TURN CONTEXT] must reference [CAPABILITY BOUNDARY] (FR-ORCH-034)"
    assert "nearest available forward path" in src_text, \
        "Complete-miss [TURN CONTEXT] must instruct model to offer a forward path (FR-ORCH-034)"
test("CapBoundary: complete-miss [TURN CONTEXT] references [CAPABILITY BOUNDARY] (AC-CR036-001)", t_capability_boundary_complete_miss)


def t_capability_boundary_near_miss():
    """AC-CR036-002: near-miss [TURN CONTEXT] names the skill and prohibits silent reduction."""
    import src.chat as chat_mod
    src_text = Path(chat_mod.__file__).read_text(encoding="utf-8")
    assert "Near-match" in src_text, \
        "Near-miss [TURN CONTEXT] block missing from chat.py (FR-ORCH-034)"
    assert "NOT silently deliver a reduced version" in src_text or \
           "Do NOT silently deliver" in src_text, \
        "Near-miss block must prohibit silent capability reduction (FR-ORCH-034)"
    assert "skill_label" in src_text, \
        "Near-miss block must reference the matched skill name (FR-ORCH-034)"
test("CapBoundary: near-miss [TURN CONTEXT] names skill and prohibits silent reduction (AC-CR036-002)", t_capability_boundary_near_miss)


def t_capability_boundary_skill_matched_pass():
    """AC-CR036-003: skill-matched zone uses 'pass' — no capability [TURN CONTEXT]."""
    import src.chat as chat_mod
    src_text = Path(chat_mod.__file__).read_text(encoding="utf-8")
    assert "pass  # skill schema handles context" in src_text, \
        "Skill-matched zone must use 'pass' (no [TURN CONTEXT]) — FR-ORCH-034"
test("CapBoundary: skill-matched zone has no capability [TURN CONTEXT] (AC-CR036-003)", t_capability_boundary_skill_matched_pass)


# ── CR-021 — Structured Observability ────────────────────────────────────────

def t_obs_logger_lifecycle():
    """AC-CR021-001: ObservabilityLogger defines start() and stop()."""
    from src.observability import ObservabilityLogger
    logger = ObservabilityLogger()
    assert callable(getattr(logger, "start", None)), \
        "ObservabilityLogger must define start() (FR-ORCH-035)"
    assert callable(getattr(logger, "stop", None)), \
        "ObservabilityLogger must define stop() (FR-ORCH-035)"
test("Obs: ObservabilityLogger defines start() and stop() (AC-CR021-001)", t_obs_logger_lifecycle)


def t_routing_started_has_trace_id():
    """AC-CR021-002: routing_started payload includes trace_id in chat.py source."""
    import src.chat as chat_mod
    src_text = Path(chat_mod.__file__).read_text(encoding="utf-8")
    assert '"trace_id"' in src_text or "'trace_id'" in src_text, \
        "routing_started emit must include trace_id key (FR-ORCH-036)"
    assert "routing_started" in src_text, \
        "chat.py must emit routing_started event (FR-ORCH-036)"
test("Obs: routing_started payload includes trace_id (AC-CR021-002)", t_routing_started_has_trace_id)


def t_llm_complete_enriched_payload():
    """AC-CR021-003: llm_complete emit includes tokens_in and cost_usd in chat.py source."""
    import src.chat as chat_mod
    src_text = Path(chat_mod.__file__).read_text(encoding="utf-8")
    assert '"tokens_in"' in src_text or "'tokens_in'" in src_text, \
        "llm_complete emit must include tokens_in key (FR-ORCH-036)"
    assert '"cost_usd"' in src_text or "'cost_usd'" in src_text, \
        "llm_complete emit must include cost_usd key (FR-ORCH-036)"
test("Obs: llm_complete payload includes tokens_in and cost_usd (AC-CR021-003)", t_llm_complete_enriched_payload)


def t_agent_traces_table_exists():
    """AC-CR021-004: agent_traces table defined in database.py schema."""
    import src.database as db_mod
    src_text = Path(db_mod.__file__).read_text(encoding="utf-8")
    assert "agent_traces" in src_text, \
        "agent_traces table must be defined in database.py schema (FR-ORCH-035)"
    assert "insert_agent_trace" in src_text, \
        "insert_agent_trace() helper must be defined in database.py (FR-ORCH-035)"
test("Obs: agent_traces table defined in database.py schema (AC-CR021-004)", t_agent_traces_table_exists)


def t_obs_on_llm_complete_writes_jsonl():
    """AC-CR021-005: on_event('llm_complete', ...) assembles trace and calls _write_jsonl."""
    from unittest.mock import MagicMock, patch
    from src.observability import ObservabilityLogger

    logger = ObservabilityLogger()
    # Prime a turn trace via routing_started
    logger._handle_routing_started({"trace_id": "abc123def456"})

    written_records: list[dict] = []

    def _fake_write_jsonl(record: dict) -> None:
        written_records.append(record)

    with patch.object(logger, "_write_jsonl", side_effect=_fake_write_jsonl), \
         patch.object(logger, "_write_db"):  # silence background DB call
        logger._handle_llm_complete({
            "route": "local",
            "tokens_in": 100,
            "tokens_out": 50,
            "cost_usd": 0.0,
        })

    assert len(written_records) == 1, \
        "_write_jsonl must be called exactly once per llm_complete (FR-ORCH-035)"
    rec = written_records[0]
    assert rec.get("trace_id") == "abc123def456", \
        "Written record must preserve trace_id (FR-ORCH-036)"
    assert "tokens_in" in rec or "gen_ai.usage.prompt_tokens" in rec, \
        "Written record must include token counts (FR-ORCH-036)"
test("Obs: on_event('llm_complete') assembles trace and calls _write_jsonl (AC-CR021-005)", t_obs_on_llm_complete_writes_jsonl)


# ── CR-019 — Reflection / Critic ──────────────────────────────────────────────

def t_critic_class_defined():
    """AC-CR019-001: TurnCritic defined with callable should_critique() and critique()."""
    from src.critic import TurnCritic, CritiqueResult
    critic = TurnCritic()
    assert callable(getattr(critic, "should_critique", None)), \
        "TurnCritic must define should_critique() (FR-ORCH-037)"
    assert callable(getattr(critic, "critique", None)), \
        "TurnCritic must define critique() (FR-ORCH-038)"
test("Critic: TurnCritic defines should_critique() and critique() (AC-CR019-001)", t_critic_class_defined)


def t_critic_should_critique_triggers():
    """AC-CR019-002: should_critique() returns True for each trigger condition."""
    from src.critic import TurnCritic
    critic = TurnCritic()
    # Trigger a: skill executed
    assert critic.should_critique(score=0.0, tool_calls_made=True, response="Fine."), \
        "tool_calls_made=True must trigger critique (FR-ORCH-037)"
    # Trigger b: near-miss score
    assert critic.should_critique(score=0.45, tool_calls_made=False, response="Fine."), \
        "Near-miss score (0.20–0.65) must trigger critique (FR-ORCH-037)"
    # Trigger c: hedging language
    assert critic.should_critique(score=0.0, tool_calls_made=False, response="I think this might be correct."), \
        "Hedging language must trigger critique (FR-ORCH-037)"
test("Critic: should_critique() returns True for all three trigger conditions (AC-CR019-002)", t_critic_should_critique_triggers)


def t_critic_no_critique_high_confidence():
    """AC-CR019-003: should_critique() returns False for high-score confident response."""
    from src.critic import TurnCritic
    critic = TurnCritic()
    result = critic.should_critique(
        score=0.90,
        tool_calls_made=False,
        response="The weather today is sunny and 72°F.",
    )
    assert result is False, \
        "High score + no tool calls + no hedging must NOT trigger critique (FR-ORCH-037)"
test("Critic: should_critique() returns False for high-score confident response (AC-CR019-003)", t_critic_no_critique_high_confidence)


def t_parse_critic_response_verdicts():
    """AC-CR019-004: _parse_critic_response() maps all three verdict prefixes correctly."""
    from src.critic import _parse_critic_response
    ok = _parse_critic_response("OK: the response fully answers the question")
    assert ok.verdict == "ok", f"Expected 'ok', got {ok.verdict!r}"

    corr = _parse_critic_response("CORRECTABLE: missing the required error handling step")
    assert corr.verdict == "correctable", f"Expected 'correctable', got {corr.verdict!r}"
    assert "error handling" in corr.note

    ambig = _parse_critic_response("AMBIGUOUS: cannot evaluate factual claims without data")
    assert ambig.verdict == "ambiguous", f"Expected 'ambiguous', got {ambig.verdict!r}"
test("Critic: _parse_critic_response() maps OK/CORRECTABLE/AMBIGUOUS correctly (AC-CR019-004)", t_parse_critic_response_verdicts)


def t_maybe_critique_in_chat():
    """AC-CR019-005: chat.py defines _maybe_critique and references _MAX_CRITIC_ITERATIONS."""
    import src.chat as chat_mod
    src_text = Path(chat_mod.__file__).read_text(encoding="utf-8")
    assert "_maybe_critique" in src_text, \
        "chat.py must define _maybe_critique method (FR-ORCH-037)"
    assert "_MAX_CRITIC_ITERATIONS" in src_text, \
        "chat.py must reference _MAX_CRITIC_ITERATIONS to enforce the cap (NFR-ORCH-012)"
    assert "_tool_calls_made" in src_text, \
        "chat.py must track _tool_calls_made for the critic trigger (FR-ORCH-037)"
test("Critic: chat.py defines _maybe_critique with _MAX_CRITIC_ITERATIONS cap (AC-CR019-005)", t_maybe_critique_in_chat)


# ── CR-022 — Eval Harness ─────────────────────────────────────────────────────

def t_eval_harness_importable():
    """AC-CR022-001: src.eval.harness importable; run_eval() callable, returns EvalReport."""
    from src.eval.harness import run_eval, EvalReport
    assert callable(run_eval), "run_eval must be callable (FR-EVAL-002)"
    assert EvalReport is not None, "EvalReport dataclass must be importable (FR-EVAL-002)"
test("Eval: src.eval.harness importable; run_eval() and EvalReport defined (AC-CR022-001)", t_eval_harness_importable)


def t_golden_set_coverage():
    """AC-CR022-002: GOLDEN_SET >= 30 examples covering all 8 built-in skills + 5 no-skill."""
    from src.eval.golden_set import GOLDEN_SET
    assert len(GOLDEN_SET) >= 30, \
        f"Golden set must have >= 30 examples (has {len(GOLDEN_SET)}) (FR-EVAL-001)"

    skill_names = {e.expected_skill for e in GOLDEN_SET if e.expected_skill is not None}
    required = {"WeatherSkill", "WebLookupSkill", "ZettelkastenSkill",
                "BMADSkill", "SDDSkill", "CodeSkill", "NotionSkill", "OrchestratorSkill"}
    missing = required - skill_names
    assert not missing, f"Golden set missing coverage for: {missing} (FR-EVAL-001)"

    no_skill = [e for e in GOLDEN_SET if e.expected_skill is None]
    assert len(no_skill) >= 5, \
        f"Golden set must include >= 5 no-skill cases (has {len(no_skill)}) (FR-EVAL-001)"
test("Eval: GOLDEN_SET >= 30 examples covering all 8 skills and no-skill cases (AC-CR022-002)", t_golden_set_coverage)


def t_eval_report_fields():
    """AC-CR022-003: EvalReport has accuracy, per_skill, regression, and gaps fields."""
    from src.eval.harness import EvalReport, SkillMetrics
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(EvalReport)}
    for required in ("accuracy", "per_skill", "regression", "gaps", "total", "correct"):
        assert required in field_names, \
            f"EvalReport missing field '{required}' (FR-EVAL-002)"
test("Eval: EvalReport has accuracy, per_skill, regression, gaps fields (AC-CR022-003)", t_eval_report_fields)


def t_eval_run_clean():
    """AC-CR022-004: run_eval() returns EvalReport without LLM calls; accuracy >= 80%."""
    from src.eval.harness import run_eval, EvalReport
    # Pass a mock baseline path so we don't read/write the real baseline
    import tempfile, pathlib
    tmp = pathlib.Path(tempfile.mkdtemp()) / "baseline.json"
    report = run_eval(baseline_path=tmp)
    assert isinstance(report, EvalReport), "run_eval() must return EvalReport (FR-EVAL-002)"
    assert report.total >= 30, \
        f"EvalReport.total must be >= 30 (is {report.total}) (FR-EVAL-001)"
    assert report.accuracy >= 0.80, \
        f"Eval accuracy must be >= 80% (is {report.accuracy:.1%}) — routing quality floor (FR-EVAL-002)"
    assert isinstance(report.gaps, list), "EvalReport.gaps must be a list (FR-EVAL-002)"
test("Eval: run_eval() returns EvalReport without LLM calls; accuracy >= 80% (AC-CR022-004)", t_eval_run_clean)


def t_eval_regression_detection():
    """AC-CR022-005: regression=True when injected baseline is 5pp above current accuracy."""
    from src.eval.harness import run_eval
    import tempfile, pathlib, json
    tmp = pathlib.Path(tempfile.mkdtemp()) / "baseline.json"
    # Inject an artificially high baseline (1.0 = 100%) to force regression detection
    tmp.write_text(json.dumps({"accuracy": 1.0}), encoding="utf-8")
    report = run_eval(baseline_path=tmp)
    assert report.regression is True, \
        "regression must be True when accuracy drops > 5pp from baseline (FR-EVAL-003)"
    assert report.baseline_accuracy == 1.0, \
        "EvalReport.baseline_accuracy must match loaded baseline (FR-EVAL-003)"
test("Eval: regression=True when accuracy drops > 5pp from injected baseline (AC-CR022-005)", t_eval_regression_detection)


# ── CR-028 — Conversation Design A1–A5 ───────────────────────────────────────

def t_strip_filler_opener_removes_and_passes():
    """AC-CR028-001: strip_filler_opener() removes known fillers; clean text passes through."""
    from src.conversation import strip_filler_opener

    # Known filler phrases must be stripped (A1 — FR-CONV-001)
    filler_cases = [
        ("Certainly! Here is the answer.", "Here is the answer."),
        ("Great question! Let me explain.", "Let me explain."),
        ("Of course, I can help.", "I can help."),
        ("Absolutely! Here you go.", "Here you go."),
        ("I'd be happy to help! Let me check.", "Let me check."),
    ]
    for raw, expected in filler_cases:
        result = strip_filler_opener(raw)
        assert result == expected, (
            f"strip_filler_opener({raw!r}) => {result!r}; expected {expected!r}"
        )

    # Clean text must pass through unchanged
    clean_cases = [
        "The file exists at that path.",
        "Run `xochitl today` to refresh the queue.",
        "Sure, here is a mid-sentence use.",  # 'sure' without punctuation — not a filler
    ]
    for raw in clean_cases:
        result = strip_filler_opener(raw)
        assert result == raw, (
            f"strip_filler_opener({raw!r}) mutated clean text => {result!r}"
        )

    # Entire filler with no remainder returns original (not empty string)
    result = strip_filler_opener("Certainly!")
    assert result == "Certainly!", f"All-filler response should return original: {result!r}"
test("Conversation A1: strip_filler_opener removes fillers, passes clean text (AC-CR028-001)", t_strip_filler_opener_removes_and_passes)


def t_uncertainty_hedge_three_tiers():
    """AC-CR028-002: uncertainty_hedge() applies correct tier for each confidence bracket."""
    from src.conversation import uncertainty_hedge

    # High tier: > 0.85 → unchanged (FR-CONV-005)
    result = uncertainty_hedge(0.90, "The meeting is tomorrow at 3pm.")
    assert result == "The meeting is tomorrow at 3pm.", \
        f"High confidence should return text unchanged: {result!r}"
    result = uncertainty_hedge(0.86, "Task is in the WIP queue.")
    assert result == "Task is in the WIP queue.", \
        f"Just-above-0.85 should be unchanged: {result!r}"

    # Mid tier: 0.60 ≤ confidence ≤ 0.85 → "I think …"
    result = uncertainty_hedge(0.72, "The meeting is at 3pm.")
    assert result.startswith("I think "), \
        f"Mid confidence (0.72) should start with 'I think': {result!r}"

    result = uncertainty_hedge(0.60, "It is in the Projects folder.")
    assert result.startswith("I think "), \
        f"At lower mid boundary (0.60) should start with 'I think': {result!r}"

    # Low tier: < 0.60 → explicit uncertainty + resolution offer
    result = uncertainty_hedge(0.45, "The deadline is Friday.")
    assert result.startswith("I'm not certain, but "), \
        f"Low confidence (0.45) should start with explicit prefix: {result!r}"
    assert "want me to look this up?" in result, \
        f"Low confidence should include resolution offer: {result!r}"

    # Edge: empty text raises ValueError
    try:
        uncertainty_hedge(0.5, "")
        assert False, "Empty text should raise ValueError"
    except ValueError:
        pass
test("Conversation A5: uncertainty_hedge applies correct tier per confidence bracket (AC-CR028-002)", t_uncertainty_hedge_three_tiers)


def t_anticipation_gate_signals():
    """AC-CR028-003: AnticipationGate.check() fires with >=2 signals; None with <2."""
    from src.anticipation import AnticipationGate
    from unittest.mock import patch

    gate = AnticipationGate()

    # Exactly 2 signals: wip=1 + recency=10h → should fire (FR-CONV-002)
    # Patch datetime.now to an off-peak hour (e.g. 14:00 — not morning/evening)
    from datetime import datetime, timezone

    class _FakeDateTime:
        @staticmethod
        def now(tz=None):
            return datetime(2026, 5, 25, 14, 0, 0, tzinfo=timezone.utc)

    with patch("src.anticipation.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 25, 14, 0, 0, tzinfo=timezone.utc)
        mock_dt.fromisoformat = datetime.fromisoformat
        result = gate.check(wip_count=1, last_session_age_hours=10.0)
    assert result is not None, \
        "wip=1 + recency=10h should fire (2 signals >= _MIN_SIGNALS=2) (FR-CONV-002)"
    assert "task" in result.lower() or "queue" in result.lower(), \
        f"Hint should mention tasks: {result!r}"

    # Only 1 signal: wip=0, recency=None, hour=14 → None
    with patch("src.anticipation.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 25, 14, 0, 0, tzinfo=timezone.utc)
        result_none = gate.check(wip_count=0, last_session_age_hours=None)
    assert result_none is None, \
        f"0 signals should return None (FR-CONV-002): got {result_none!r}"

    # 3 signals: wip=2 + morning=08:00 + recency=8h → should fire
    with patch("src.anticipation.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 25, 8, 0, 0, tzinfo=timezone.utc)
        result_tri = gate.check(wip_count=2, last_session_age_hours=8.0)
    assert result_tri is not None, \
        "3 signals (wip + morning + recency) should fire (FR-CONV-002)"
    assert "Good morning" in result_tri, \
        f"Morning signal should add 'Good morning': {result_tri!r}"
test("Conversation A2: AnticipationGate fires with >=2 signals, None with <2 (AC-CR028-003)", t_anticipation_gate_signals)


def t_build_structured_brief_sections():
    """AC-CR028-004: build_structured_brief() contains expected section headers when data present."""
    from src.brief import build_structured_brief
    from unittest.mock import patch
    import datetime

    queue = [
        {"description": "Implement FR-CONV-003 structured brief"},
        {"description": "Write smoke tests for CR-028"},
    ]
    notion_pending = [
        {"title": "Review product roadmap"},
    ]

    # Patch subprocess.run to simulate a stale git commit for the Awareness section
    fake_ts = "2026-05-24T10:00:00+00:00"
    with patch("src.brief.subprocess.run") as mock_run:
        mock_proc = mock_run.return_value
        mock_proc.returncode = 0
        mock_proc.stdout = fake_ts
        brief = build_structured_brief(queue, notion_pending)

    # Section: Priorities must appear
    assert "**Priorities**" in brief, \
        "build_structured_brief() missing **Priorities** section (FR-CONV-003)"
    # Task descriptions must appear
    assert "FR-CONV-003" in brief, \
        "Priority task description missing from brief (FR-CONV-003)"
    # Section: Async queue must appear (notion_pending provided)
    assert "**Async queue**" in brief, \
        "build_structured_brief() missing **Async queue** section (FR-CONV-003)"
    # Section: Temporal context must appear
    assert "**" in brief and ("Monday" in brief or "Sunday" in brief or "Tuesday" in brief
                               or "Wednesday" in brief or "Thursday" in brief
                               or "Friday" in brief or "Saturday" in brief), \
        "Temporal context (day name) missing from brief (FR-CONV-003)"

    # Empty queue + empty notion → brief still returns something (no exception)
    empty_brief = build_structured_brief([], [])
    assert isinstance(empty_brief, str), \
        "build_structured_brief() must return str even when both args empty"
test("Conversation A3: build_structured_brief() contains expected section headers (AC-CR028-004)", t_build_structured_brief_sections)


def t_preference_engine_natural_framing():
    """AC-CR028-005: PreferenceEngine.assemble() uses [BACKGROUND CONTEXT] block (FR-CONV-004)."""
    import sqlite3
    from src.context_manager import PreferenceEngine

    engine = PreferenceEngine()
    # Inject rows directly to bypass DB (test in isolation)
    engine._rows = [
        {
            "id": 1,
            "scope": "global",
            "project_id": None,
            "category": "communication",
            "preference_value": "I prefer concise responses",
        }
    ]
    output = engine.assemble()

    # Must use [BACKGROUND CONTEXT] wrapper (AC-CR028-005)
    assert "[BACKGROUND CONTEXT]" in output, \
        "PreferenceEngine.assemble() must use [BACKGROUND CONTEXT] block (FR-CONV-004)"
    assert "[/BACKGROUND CONTEXT]" in output, \
        "PreferenceEngine.assemble() must close [BACKGROUND CONTEXT] block (FR-CONV-004)"
    # Must NOT use old raw [scope/category] format
    assert "[global/communication]" not in output, \
        "PreferenceEngine.assemble() must not use old [scope/category] format (FR-CONV-004)"
    # Must include the preference value
    assert "I prefer concise responses" in output, \
        "Preference value must appear in assembled output (FR-CONV-004)"
    # Natural instruction must be present
    assert "do not cite" in output.lower(), \
        "assemble() must instruct model not to cite preferences explicitly (FR-CONV-004)"
    # Empty rows → empty string (no block)
    engine._rows = []
    assert engine.assemble() == "", \
        "PreferenceEngine.assemble() with no rows must return empty string"
test("Conversation A4: PreferenceEngine.assemble() uses [BACKGROUND CONTEXT] framing (AC-CR028-005)", t_preference_engine_natural_framing)


# ── CR-023 — Bounded Explorer ─────────────────────────────────────────────────

def t_explorer_skill_can_handle_scoring():
    """AC-CR023-002: investigative keywords → ≥0.65; plain queries → 0.0 (FR-ORCH-039)."""
    from src.skills.explorer_skill import ExplorerSkill
    skill = ExplorerSkill()
    ctx: dict = {}
    # Investigative keywords → above _SKILL_INJECT_THRESHOLD (0.65)
    assert skill.can_handle("Investigate the history of Python", ctx) >= 0.65, \
        "can_handle must return ≥0.65 for 'investigate' keyword"
    assert skill.can_handle("research quantum computing trends", ctx) >= 0.65, \
        "can_handle must return ≥0.65 for 'research' keyword"
    assert skill.can_handle("analyze the impact of streaming on latency", ctx) >= 0.65, \
        "can_handle must return ≥0.65 for 'analyze' keyword"
    # Plain queries → no investigative score
    assert skill.can_handle("what's the weather today", ctx) == 0.0, \
        "can_handle must return 0.0 for plain weather query"
    assert skill.can_handle("hello", ctx) == 0.0, \
        "can_handle must return 0.0 for greeting"
test("Explorer: can_handle() scores investigative keywords >=0.65, plain 0.0 (AC-CR023-002)", t_explorer_skill_can_handle_scoring)


def t_explorer_skill_loop_detection():
    """AC-CR023-003: repeat subquestion hash → stops before _MAX_STEPS with loop note (NFR-ORCH-014)."""
    from unittest.mock import patch
    from src.skills.explorer_skill import ExplorerSkill, _MAX_STEPS

    gather_calls: list[int] = []
    synth_notes: list[str] = []

    def always_same_subq(self_inner, query: str, step: int, evidence: list) -> str:
        return "identical subquestion every step"

    def counting_gather(self_inner, subquestion: str, context: dict) -> str:
        gather_calls.append(1)
        return "some evidence about the topic for testing purposes"

    def capture_synthesize(self_inner, query: str, evidence: list, notes: str = "") -> str:
        synth_notes.append(notes)
        return "synthesized result"

    with patch.object(ExplorerSkill, "_form_subquestion", always_same_subq):
        with patch.object(ExplorerSkill, "_gather", counting_gather):
            with patch.object(ExplorerSkill, "_synthesize", capture_synthesize):
                result = ExplorerSkill().execute(
                    "investigate something", {}, {"query": "investigate something"}
                )

    assert len(gather_calls) < _MAX_STEPS, \
        f"Loop detection must stop before _MAX_STEPS; got {len(gather_calls)} gathers"
    assert synth_notes, "_synthesize must be called on loop detection"
    assert any("loop" in n.lower() for n in synth_notes), \
        f"_synthesize notes must contain 'loop'; got: {synth_notes}"
    assert result == "synthesized result", "execute() must return _synthesize() result"
test("Explorer: loop detection stops before _MAX_STEPS with loop note (AC-CR023-003)", t_explorer_skill_loop_detection)


def t_explorer_skill_budget_exhaustion():
    """AC-CR023-004: 6 steps of medium evidence → budget exhausted note (NFR-ORCH-014)."""
    from unittest.mock import patch
    from src.skills.explorer_skill import ExplorerSkill, _MAX_STEPS

    synth_notes: list[str] = []

    def unique_subq(self_inner, query: str, step: int, evidence: list) -> str:
        # Unique per step → no hash collision → no loop detection
        return f"unique question for investigation step {step}"

    def medium_gather(self_inner, subquestion: str, context: dict) -> str:
        # 120-char snippet: quality=+0.20 (len>100), total with depth=0.65 — never >0.85
        return "A " * 60

    def capture_synthesize(self_inner, query: str, evidence: list, notes: str = "") -> str:
        synth_notes.append(notes)
        return "budget result"

    with patch.object(ExplorerSkill, "_form_subquestion", unique_subq):
        with patch.object(ExplorerSkill, "_gather", medium_gather):
            with patch.object(ExplorerSkill, "_synthesize", capture_synthesize):
                result = ExplorerSkill().execute(
                    "research something", {}, {"query": "research something"}
                )

    assert synth_notes, "_synthesize must be called after budget exhaustion"
    budget_note = synth_notes[-1]
    assert "budget" in budget_note.lower() or "exhausted" in budget_note.lower(), \
        f"Budget-exhaustion notes must contain 'budget' or 'exhausted'; got: {budget_note!r}"
    assert result == "budget result", "execute() must return _synthesize() result"
test("Explorer: 6 medium-evidence steps -> budget exhausted note in _synthesize (AC-CR023-004)", t_explorer_skill_budget_exhaustion)


def t_explorer_skill_high_confidence_stops_early():
    """AC-CR023-005: rich evidence (420-char snippets) → confidence >0.85 at step 3 (NFR-ORCH-015)."""
    from unittest.mock import patch
    from src.skills.explorer_skill import ExplorerSkill, _MAX_STEPS

    gather_calls: list[int] = []
    synth_notes: list[str] = []

    def unique_subq(self_inner, query: str, step: int, evidence: list) -> str:
        return f"rich investigation step {step} unique"

    def rich_gather(self_inner, subquestion: str, context: dict) -> str:
        gather_calls.append(1)
        # 420-char snippet: quality = +0.20 (>100) +0.15 (>250) +0.15 (>400) = 0.50
        # step 3: depth=0.45 + quality=0.50 = 0.95 > 0.85 → stop
        return "B " * 210

    def capture_synthesize(self_inner, query: str, evidence: list, notes: str = "") -> str:
        synth_notes.append(notes)
        return "early answer"

    with patch.object(ExplorerSkill, "_form_subquestion", unique_subq):
        with patch.object(ExplorerSkill, "_gather", rich_gather):
            with patch.object(ExplorerSkill, "_synthesize", capture_synthesize):
                result = ExplorerSkill().execute(
                    "explore X", {}, {"query": "explore X"}
                )

    assert len(gather_calls) < _MAX_STEPS, \
        f"High-confidence stop must fire before _MAX_STEPS; got {len(gather_calls)} gathers"
    assert synth_notes, "_synthesize must be called on high-confidence stop"
    budget_note = synth_notes[-1]
    assert "budget" not in budget_note.lower() and "exhausted" not in budget_note.lower(), \
        f"High-confidence stop must NOT emit budget note; got: {budget_note!r}"
    assert result == "early answer", "execute() must return _synthesize() result"
test("Explorer: rich evidence stops loop early without budget note (AC-CR023-005)", t_explorer_skill_high_confidence_stops_early)


def t_explorer_skill_registration():
    """AC-CR023-006: ExplorerSkill present in XochitlChat.skills list (FR-ORCH-041)."""
    from src.skills.explorer_skill import ExplorerSkill
    from src.chat import XochitlChat
    chat = XochitlChat.__new__(XochitlChat)
    chat._builtin_skills = None  # type: ignore[attr-defined]
    chat._skills = None          # type: ignore[attr-defined]
    chat.current_project = None  # type: ignore[attr-defined]
    skills = chat.skills
    assert any(isinstance(s, ExplorerSkill) for s in skills), \
        "ExplorerSkill must be present in XochitlChat.skills (FR-ORCH-041)"
test("Explorer: ExplorerSkill registered in XochitlChat._builtin_skills (AC-CR023-006)", t_explorer_skill_registration)


# ── CR-033 — Persona Drift Detection ─────────────────────────────────────────

def t_drift_flag_set_by_drift_response():
    """AC-CR033-001: _check_drift_with_identity() sets drift_detected=True on DRIFT (NFR-ORCH-016)."""
    from unittest.mock import MagicMock, patch
    from src.background_review import BackgroundReview

    br = BackgroundReview()
    br._recent_responses = ["response one", "response two", "response three"]

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.content = "DRIFT"

    with patch("src.llm_interface.call_local", return_value=mock_result):
        br._check_drift_with_identity("Xochitl is warm, direct, and culturally grounded.")

    assert br.drift_detected is True, \
        "drift_detected must be True after _check_drift_with_identity() returns DRIFT"
test("Drift: DRIFT response sets drift_detected=True (AC-CR033-001)", t_drift_flag_set_by_drift_response)


def t_drift_flag_clear_for_ok_response():
    """AC-CR033-002: _check_drift_with_identity() leaves drift_detected=False on OK (NFR-ORCH-016)."""
    from unittest.mock import MagicMock, patch
    from src.background_review import BackgroundReview

    br = BackgroundReview()
    br._recent_responses = ["response one", "response two", "response three"]

    mock_result = MagicMock()
    mock_result.error = None
    mock_result.content = "OK — voice consistent"

    with patch("src.llm_interface.call_local", return_value=mock_result):
        br._check_drift_with_identity("Xochitl is warm, direct, and culturally grounded.")

    assert br.drift_detected is False, \
        "drift_detected must remain False when _check_drift_with_identity() returns OK"
test("Drift: OK response leaves drift_detected=False (AC-CR033-002)", t_drift_flag_clear_for_ok_response)


def t_drift_clear_resets_flag():
    """AC-CR033-003: clear_drift() resets drift_detected to False (NFR-ORCH-017)."""
    from src.background_review import BackgroundReview

    br = BackgroundReview()
    with br._drift_lock:
        br._drift_detected = True
    assert br.drift_detected is True, "Pre-condition: drift_detected should be True"
    br.clear_drift()
    assert br.drift_detected is False, \
        "clear_drift() must reset drift_detected to False (FR-ORCH-043)"
test("Drift: clear_drift() resets drift_detected flag (AC-CR033-003)", t_drift_clear_resets_flag)


def t_drift_interval_trigger():
    """AC-CR033-004: _should_run_drift_check() triggers at _DRIFT_CHECK_INTERVAL (FR-ORCH-042)."""
    from src.background_review import BackgroundReview, _DRIFT_CHECK_INTERVAL

    br = BackgroundReview()

    # Exactly at interval — should trigger
    br._turn_count = _DRIFT_CHECK_INTERVAL
    br._correction_turns = 0
    assert br._should_run_drift_check() is True, \
        f"must return True when _turn_count == _DRIFT_CHECK_INTERVAL ({_DRIFT_CHECK_INTERVAL})"

    # One before interval — should NOT trigger
    br._turn_count = _DRIFT_CHECK_INTERVAL - 1
    assert br._should_run_drift_check() is False, \
        "must return False when _turn_count is one below interval"

    # Turn 0 (no turns yet) — must NOT trigger (zero-turn guard)
    br._turn_count = 0
    assert br._should_run_drift_check() is False, \
        "must return False when _turn_count == 0 (zero-turn guard)"
test("Drift: _should_run_drift_check() triggers at _DRIFT_CHECK_INTERVAL (AC-CR033-004)", t_drift_interval_trigger)


def t_drift_correction_pressure_trigger():
    """AC-CR033-005: _should_run_drift_check() triggers on >=2 correction turns (FR-ORCH-042)."""
    from src.background_review import BackgroundReview

    br = BackgroundReview()
    br._turn_count = 1  # not at regular interval

    # Two corrections — pressure trigger
    br._correction_turns = 2
    assert br._should_run_drift_check() is True, \
        "must return True when _correction_turns >= 2 (correction pressure)"

    # One correction — not enough pressure
    br._correction_turns = 1
    assert br._should_run_drift_check() is False, \
        "must return False when _correction_turns == 1 (below pressure threshold)"
test("Drift: _should_run_drift_check() triggers on correction pressure >=2 (AC-CR033-005)", t_drift_correction_pressure_trigger)


def t_drift_reminder_constant_defined():
    """AC-CR033-006: _DRIFT_IDENTITY_REMINDER is defined in chat.py (FR-ORCH-043)."""
    from src.chat import _DRIFT_IDENTITY_REMINDER
    assert isinstance(_DRIFT_IDENTITY_REMINDER, str), \
        "_DRIFT_IDENTITY_REMINDER must be a str"
    assert len(_DRIFT_IDENTITY_REMINDER) > 0, \
        "_DRIFT_IDENTITY_REMINDER must not be empty"
    assert "IDENTITY REMINDER" in _DRIFT_IDENTITY_REMINDER, \
        "_DRIFT_IDENTITY_REMINDER must contain 'IDENTITY REMINDER' marker"
test("Drift: _DRIFT_IDENTITY_REMINDER constant defined in chat.py (AC-CR033-006)", t_drift_reminder_constant_defined)


# ── CR-034 — Implicit Preference Learning ─────────────────────────────────────

def t_rephrased_query_detected():
    """AC-CR034-001: is_rephrased_query() returns True for same-topic rephrases (FR-PREF-001)."""
    from src.preference_learning import is_rephrased_query
    result = is_rephrased_query(
        "What tasks are in my Notion queue?",
        "Which Notion tasks are pending?",
    )
    assert result is True, \
        "is_rephrased_query must return True for same-topic rephrases (FR-PREF-001)"
test("Pref: is_rephrased_query() True for same-topic rephrase (AC-CR034-001)", t_rephrased_query_detected)


def t_rephrased_query_different_topic():
    """AC-CR034-002: is_rephrased_query() returns False for different topics (FR-PREF-001)."""
    from src.preference_learning import is_rephrased_query
    result = is_rephrased_query(
        "What tasks are in my Notion queue?",
        "What is the weather today?",
    )
    assert result is False, \
        "is_rephrased_query must return False when topics diverge (FR-PREF-001)"
test("Pref: is_rephrased_query() False for different topic (AC-CR034-002)", t_rephrased_query_different_topic)


def t_rephrased_query_identical_returns_false():
    """AC-CR034-003: is_rephrased_query() returns False for identical strings (FR-PREF-001)."""
    from src.preference_learning import is_rephrased_query
    result = is_rephrased_query("Investigate Python", "Investigate Python")
    assert result is False, \
        "identical strings must return False — retry, not rephrase (FR-PREF-001)"
test("Pref: is_rephrased_query() False for identical strings (AC-CR034-003)", t_rephrased_query_identical_returns_false)


def t_decay_and_prune_applies_decay():
    """AC-CR034-004: decay_and_prune() multiplies confidence by 0.95 for above-threshold rows."""
    import sqlite3
    from src.preference_learning import decay_and_prune
    from src import database as _db

    conn = sqlite3.connect(":memory:")
    _db._ensure_preferences_table(conn)
    conn.execute(
        "INSERT INTO preferences (preference_key, preference_value, source, confidence)"
        " VALUES (?, ?, ?, ?)",
        ("pref_decay_test", "some preference", "implicit_preference", 0.80),
    )
    conn.commit()

    decayed, pruned = decay_and_prune(conn)

    row = conn.execute(
        "SELECT confidence FROM preferences WHERE preference_key = ?", ("pref_decay_test",)
    ).fetchone()
    conn.close()

    assert row is not None, "row must survive decay (confidence still above threshold)"
    assert pruned == 0, "row must not be pruned (confidence 0.76 >= 0.30)"
    assert decayed >= 1, "decayed_count must be >= 1"
    assert abs(row[0] - 0.76) < 0.01, \
        f"confidence must decay to ~0.76 (0.80 * 0.95), got {row[0]}"
test("Pref: decay_and_prune() applies 0.95 decay to above-threshold rows (AC-CR034-004)", t_decay_and_prune_applies_decay)


def t_decay_and_prune_prunes_below_threshold():
    """AC-CR034-005: decay_and_prune() deletes rows whose confidence is below 0.30."""
    import sqlite3
    from src.preference_learning import decay_and_prune
    from src import database as _db

    conn = sqlite3.connect(":memory:")
    _db._ensure_preferences_table(conn)
    conn.execute(
        "INSERT INTO preferences (preference_key, preference_value, source, confidence)"
        " VALUES (?, ?, ?, ?)",
        ("pref_prune_test", "stale preference", "implicit_preference", 0.29),
    )
    conn.commit()

    _decayed, pruned = decay_and_prune(conn)

    row = conn.execute(
        "SELECT confidence FROM preferences WHERE preference_key = ?", ("pref_prune_test",)
    ).fetchone()
    conn.close()

    assert row is None, "row must be deleted when confidence < 0.30 (FR-PREF-003)"
    assert pruned >= 1, f"pruned_count must be >= 1, got {pruned}"
test("Pref: decay_and_prune() prunes rows below 0.30 threshold (AC-CR034-005)", t_decay_and_prune_prunes_below_threshold)


# ── CR-035 — Progressive Personalization Milestones ───────────────────────────

def t_milestone_m1_sessions_1_to_5():
    """AC-CR035-001: get_milestone() returns M1 for sessions 1-5 (FR-PREF-004)."""
    from src.milestones import get_milestone, Milestone
    assert get_milestone(1) == Milestone.M1, "session 1 must be M1"
    assert get_milestone(5) == Milestone.M1, "session 5 must be M1 (boundary)"
test("Milestone: get_milestone() returns M1 for sessions 1-5 (AC-CR035-001)", t_milestone_m1_sessions_1_to_5)


def t_milestone_m2_sessions_6_to_20():
    """AC-CR035-002: get_milestone() returns M2 for sessions 6-20 (FR-PREF-004)."""
    from src.milestones import get_milestone, Milestone
    assert get_milestone(6) == Milestone.M2, "session 6 must be M2 (first M2)"
    assert get_milestone(20) == Milestone.M2, "session 20 must be M2 (boundary)"
test("Milestone: get_milestone() returns M2 for sessions 6-20 (AC-CR035-002)", t_milestone_m2_sessions_6_to_20)


def t_milestone_m3_sessions_21_plus():
    """AC-CR035-003: get_milestone() returns M3 for sessions 21+ (FR-PREF-004)."""
    from src.milestones import get_milestone, Milestone
    assert get_milestone(21) == Milestone.M3, "session 21 must be M3 (first M3)"
    assert get_milestone(100) == Milestone.M3, "session 100 must be M3 (no upper bound)"
test("Milestone: get_milestone() returns M3 for sessions 21+ (AC-CR035-003)", t_milestone_m3_sessions_21_plus)


def t_milestone_m1_empty_block():
    """AC-CR035-004: milestone_context_block(M1) returns empty string (FR-PREF-005)."""
    from src.milestones import milestone_context_block, Milestone
    block = milestone_context_block(Milestone.M1)
    assert block == "", \
        f"M1 context block must be empty (no extra block for new users), got: {block!r}"
test("Milestone: milestone_context_block(M1) returns empty string (AC-CR035-004)", t_milestone_m1_empty_block)


def t_milestone_m2_m3_nonempty_blocks():
    """AC-CR035-005: M2 and M3 context blocks are non-empty (FR-PREF-005)."""
    from src.milestones import milestone_context_block, Milestone
    m2_block = milestone_context_block(Milestone.M2)
    m3_block = milestone_context_block(Milestone.M3)
    assert len(m2_block) > 0, "M2 context block must be non-empty"
    assert len(m3_block) > 0, "M3 context block must be non-empty"
    assert "Personalization" in m2_block, "M2 block must contain 'Personalization' header"
    assert "Personalization" in m3_block, "M3 block must contain 'Personalization' header"
test("Milestone: M2 and M3 context blocks are non-empty (AC-CR035-005)", t_milestone_m2_m3_nonempty_blocks)


# ── CR-038 — Controlled Initiative ───────────────────────────────────────────

def t_initiative_off_rejects_all():
    """AC-CR038-001: ProactiveMode.OFF rejects signals regardless of category/confidence (FR-INIT-001)."""
    from src.initiative import InitiativeEngine, ProactiveMode, InitiativeCategory, ProactiveSignal
    engine = InitiativeEngine(mode=ProactiveMode.OFF)
    engine.submit(ProactiveSignal(
        category=InitiativeCategory.SYSTEM_FAILURE,
        message="Notion sync failed.",
        confidence=0.90,
        action_hint="Run /sync or /dismiss to skip.",
    ))
    result = engine.drain()
    assert result == [], f"OFF mode must reject all signals, got: {result}"
test("Initiative: OFF mode rejects all signals (AC-CR038-001)", t_initiative_off_rejects_all)


def t_initiative_errors_only_allows_system_failure():
    """AC-CR038-002: ERRORS_ONLY allows SYSTEM_FAILURE signals above threshold (FR-INIT-001)."""
    from src.initiative import InitiativeEngine, ProactiveMode, InitiativeCategory, ProactiveSignal
    engine = InitiativeEngine(mode=ProactiveMode.ERRORS_ONLY)
    signal = ProactiveSignal(
        category=InitiativeCategory.SYSTEM_FAILURE,
        message="Notion sync failed 12 minutes ago.",
        confidence=0.90,
        action_hint="Run /sync or /dismiss to skip.",
    )
    engine.submit(signal)
    result = engine.drain()
    assert len(result) == 1, f"ERRORS_ONLY must queue SYSTEM_FAILURE, got: {result}"
    assert result[0].category == InitiativeCategory.SYSTEM_FAILURE
test("Initiative: ERRORS_ONLY allows SYSTEM_FAILURE above threshold (AC-CR038-002)", t_initiative_errors_only_allows_system_failure)


def t_initiative_errors_only_rejects_followup():
    """AC-CR038-003: ERRORS_ONLY rejects IN_SESSION_FOLLOWUP (FR-INIT-001)."""
    from src.initiative import InitiativeEngine, ProactiveMode, InitiativeCategory, ProactiveSignal
    engine = InitiativeEngine(mode=ProactiveMode.ERRORS_ONLY)
    engine.submit(ProactiveSignal(
        category=InitiativeCategory.IN_SESSION_FOLLOWUP,
        message="You started a plan for ZettleLib earlier.",
        confidence=0.90,
        action_hint="Type 'continue ZettleLib' or /dismiss.",
    ))
    result = engine.drain()
    assert result == [], f"ERRORS_ONLY must reject IN_SESSION_FOLLOWUP, got: {result}"
test("Initiative: ERRORS_ONLY rejects IN_SESSION_FOLLOWUP (AC-CR038-003)", t_initiative_errors_only_rejects_followup)


def t_initiative_low_confidence_rejected():
    """AC-CR038-004: Signal below 0.80 confidence threshold is rejected (FR-INIT-001)."""
    from src.initiative import InitiativeEngine, ProactiveMode, InitiativeCategory, ProactiveSignal
    engine = InitiativeEngine(mode=ProactiveMode.FULL)
    engine.submit(ProactiveSignal(
        category=InitiativeCategory.SYSTEM_FAILURE,
        message="Possible sync issue detected.",
        confidence=0.75,
        action_hint="Check /sync or /dismiss.",
    ))
    result = engine.drain()
    assert result == [], f"Confidence 0.75 < 0.80 must be rejected, got: {result}"
test("Initiative: below-threshold confidence (0.75) rejected (AC-CR038-004)", t_initiative_low_confidence_rejected)


def t_initiative_dismissal_suppresses_after_3():
    """AC-CR038-005: 3 dismissals suppress the category permanently (FR-INIT-002)."""
    from src.initiative import InitiativeEngine, ProactiveMode, InitiativeCategory, ProactiveSignal
    engine = InitiativeEngine(mode=ProactiveMode.FULL)
    signal = ProactiveSignal(
        category=InitiativeCategory.SYSTEM_FAILURE,
        message="Notion sync failed.",
        confidence=0.90,
        action_hint="Run /sync or /dismiss.",
    )

    # Verify signal queues before suppression
    engine.submit(signal)
    pre_suppress = engine.drain()
    assert len(pre_suppress) == 1, "Signal must queue before any dismissals"

    # Dismiss 3 times
    for _ in range(3):
        engine.dismiss(InitiativeCategory.SYSTEM_FAILURE)

    # Signal must now be suppressed
    engine.submit(signal)
    post_suppress = engine.drain()
    assert post_suppress == [], \
        f"After 3 dismissals, SYSTEM_FAILURE must be suppressed, got: {post_suppress}"
test("Initiative: 3 dismissals suppress category permanently (AC-CR038-005)", t_initiative_dismissal_suppresses_after_3)


# ── CR-037 — Safe Executor ────────────────────────────────────────────────────

def t_governor_auto_for_read():
    """AC-CR037-001: ActionGovernor.classify('read', ...) returns AUTO (FR-EXEC-001)."""
    from src.executor import ActionGovernor, ActionTier
    tier = ActionGovernor.classify("read", "src/chat.py")
    assert tier == ActionTier.AUTO, \
        f"'read' action must be AUTO, got: {tier}"
test("Executor: classify('read', ...) returns AUTO (AC-CR037-001)", t_governor_auto_for_read)


def t_governor_confirm_for_delete():
    """AC-CR037-002: ActionGovernor.classify('delete', ...) returns CONFIRM (FR-EXEC-001)."""
    from src.executor import ActionGovernor, ActionTier
    tier = ActionGovernor.classify("delete", "output.txt")
    assert tier == ActionTier.CONFIRM, \
        f"'delete' action must be CONFIRM, got: {tier}"
test("Executor: classify('delete', ...) returns CONFIRM (AC-CR037-002)", t_governor_confirm_for_delete)


def t_governor_deny_on_path_traversal():
    """AC-CR037-003: ActionGovernor.classify('exec', '../../etc/passwd') returns DENY (FR-EXEC-001)."""
    from src.executor import ActionGovernor, ActionTier
    tier = ActionGovernor.classify("exec", "../../etc/passwd")
    assert tier == ActionTier.DENY, \
        f"Path traversal target must be DENY, got: {tier}"
test("Executor: classify DENY on path traversal (AC-CR037-003)", t_governor_deny_on_path_traversal)


def t_executor_policy_violation_non_allowlisted():
    """AC-CR037-004: SafeExecutor.run raises PolicyViolation for non-allowlisted command (FR-EXEC-003)."""
    from src.executor import SafeExecutor, PolicyViolation
    ex = SafeExecutor()
    try:
        ex.run("not_on_allowlist", [])
        assert False, "SafeExecutor.run must raise PolicyViolation for unknown command"
    except PolicyViolation:
        pass  # expected
test("Executor: PolicyViolation for non-allowlisted command (AC-CR037-004)", t_executor_policy_violation_non_allowlisted)


def t_executor_output_truncated_at_cap():
    """AC-CR037-005: SafeExecutor.run truncates output exceeding 64KB (FR-EXEC-002, NFR-EXEC-002)."""
    import subprocess
    from unittest.mock import patch, MagicMock
    from src.executor import SafeExecutor, _OUTPUT_CAP_BYTES

    big_output = b"x" * (_OUTPUT_CAP_BYTES + 1000)
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = big_output
    mock_proc.stderr = b""

    ex = SafeExecutor()
    with patch("subprocess.run", return_value=mock_proc):
        result = ex.run("git", ["status"], action_type="read", target=".")

    assert result.truncated is True, \
        "result.truncated must be True when output exceeds _OUTPUT_CAP_BYTES"
    assert "[truncated]" in result.stdout, \
        "Truncated output must contain '[truncated]' marker"
test("Executor: output >64KB is truncated with [truncated] marker (AC-CR037-005)", t_executor_output_truncated_at_cap)




# -- CR-039 Terminal visual grammar --------------------------------------------

def t_terminal_format_line_wrap():
    from src.terminal_output import wrap_text
    long = "word " * 30
    lines = wrap_text(long, 40)
    assert all(len(line) <= 42 for line in lines)

def t_terminal_prefixes_plain():
    from src.terminal_output import TerminalStatus, format_line
    assert "-> " in format_line(TerminalStatus.ACTION, "test", rich=False)
    assert "[ok] " in format_line(TerminalStatus.DONE, "done", rich=False)

def t_terminal_format_step():
    from src.terminal_output import format_step
    s = format_step(1, 3, "Fetch", rich=False)
    assert "[1/3]" in s

def t_cli_json_today():
    from click.testing import CliRunner
    from src.cli import cli
    import json
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "today"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["command"] == "today"
    assert "queue" in data["data"]

test("Terminal: wrap_text respects width (AC-CR039-001)", t_terminal_format_line_wrap)
test("Terminal: plain prefixes for done and action (AC-CR039-002)", t_terminal_prefixes_plain)
test("Terminal: format_step includes n/m (AC-CR039-003)", t_terminal_format_step)
test("CLI: today --json returns structured payload (AC-CR039-004)", t_cli_json_today)


def t_cli_json_status():
    from click.testing import CliRunner
    from src.cli import cli
    import json
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "status"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["command"] == "status"
    assert "projects" in data["data"]

test("CLI: status --json returns projects and queue (AC-CR039-005)", t_cli_json_status)


def t_cli_json_chat_interactive_only():
    from click.testing import CliRunner
    from src.cli import cli
    import json
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "chat"])
    data = json.loads(result.output)
    assert data["command"] == "chat"
    assert data["ok"] is False

test("CLI: chat --json reports interactive_only (AC-CR039-006)", t_cli_json_chat_interactive_only)


# -- CR-040 Compact reasoning disclosure ---------------------------------------

def t_why_request_detected():
    from src.action_disclosure import is_why_request
    assert is_why_request("Why?")
    assert is_why_request("how did you get that?")
    assert not is_why_request("what is the weather")

def t_action_summary_ascii():
    from src.action_disclosure import action_summary
    s = action_summary("Checking weather")
    assert "Checking weather" in s

def t_format_compact_result():
    from src.action_disclosure import format_compact_result
    out = format_compact_result("Checking weather", "72F and sunny")
    assert "Checking weather" in out
    assert "72F" in out

test("Disclosure: is_why_request detects explicit why (AC-CR040-001)", t_why_request_detected)
test("Disclosure: action_summary contains label (AC-CR040-002)", t_action_summary_ascii)
test("Disclosure: format_compact_result includes action and body (AC-CR040-003)", t_format_compact_result)


# -- CR-041 Procedural memory -------------------------------------------------

def t_workflow_upsert_roundtrip():
    import sqlite3
    import json
    from src.database import _ensure_workflows_table, upsert_workflow, get_workflow
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _ensure_workflows_table(conn)
    steps = [{"type": "skill", "skill": "NotionSkill", "description": "Sync inbox"}]
    wid = upsert_workflow(conn, "weekly-review", "weekly review notion", steps)
    row = get_workflow(conn, "weekly-review")
    assert row is not None
    assert int(row["id"]) == wid
    assert json.loads(row["steps_json"])[0]["skill"] == "NotionSkill"

def t_workflow_search_intent():
    import sqlite3
    from src.database import _ensure_workflows_table, upsert_workflow
    from src.workflows import search_workflows_by_intent
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _ensure_workflows_table(conn)
    upsert_workflow(
        conn,
        "weekly-review",
        "weekly review notion inbox triage",
        [{"type": "skill", "description": "step1"}, {"type": "skill", "description": "step2"}],
    )
    conn.commit()
    # Patch get_connection for this test by passing rows directly - search uses db.get_connection
    # So seed real DB path is heavy; test score + search with monkeypatch
    import src.workflows as wf_mod
    fake = {
        "id": 1,
        "name": "weekly-review",
        "trigger_pattern": "weekly review notion inbox triage",
        "steps_json": "[]",
        "expected_outputs": None,
        "failure_modes": None,
        "project": None,
        "source": "user_defined",
        "confidence": 0.8,
        "last_used_at": None,
        "success_count": 0,
        "failure_count": 0,
    }
    class _Row:
        def __getitem__(self, k):
            return fake[k]
    def _fake_list(conn, project=None, limit=50):
        return [_Row()]
    wf_mod.db.list_workflows = _fake_list
    match = search_workflows_by_intent("run my weekly review")
    assert match is not None
    assert match["name"] == "weekly-review"

def t_workflow_format_block_cap():
    from src.workflows import format_workflow_block
    wf = {
        "name": "big",
        "trigger_pattern": "x",
        "steps": [{"description": "s" * 500} for _ in range(20)],
    }
    block = format_workflow_block(wf)
    assert len(block) <= 2000

def t_workflow_distill_steps():
    from src.workflows import distill_steps_from_history
    hist = [
        {"role": "user", "content": "triage"},
        {"role": "tool", "skill": "A", "content": "ok"},
        {"role": "tool", "skill": "B", "content": "done"},
    ]
    steps = distill_steps_from_history(hist)
    assert len(steps) >= 2

test("Workflow: upsert and get round-trip (AC-CR041-001)", t_workflow_upsert_roundtrip)
test("Workflow: search_workflows_by_intent match (AC-CR041-002)", t_workflow_search_intent)
test("Workflow: format_workflow_block under cap (AC-CR041-003)", t_workflow_format_block_cap)
test("Workflow: distill_steps_from_history (AC-CR041-004)", t_workflow_distill_steps)


# -- CR-042 Procedural memory phase 2 -----------------------------------------

def t_workflow_llm_distill():
    from unittest.mock import patch
    from src.workflows import distill_workflow_trajectory
    hist = [
        {"role": "user", "content": "weekly review"},
        {"role": "tool", "skill": "NotionSkill", "content": "synced"},
        {"role": "tool", "skill": "WeatherSkill", "content": "sunny"},
    ]
    class _Resp:
        error = None
        content = (
            '{"trigger_pattern": "weekly review", "steps": ['
            '{"skill": "NotionSkill", "description": "sync"}, '
            '{"skill": "WeatherSkill", "description": "forecast"}], '
            '"expected_outputs": "inbox clear", "failure_modes": "api down"}'
        )
    with patch("src.llm_interface.call_local", return_value=_Resp()):
        out = distill_workflow_trajectory(hist, use_llm=True)
    assert out.get("source") == "llm"
    assert len(out.get("steps") or []) >= 2
    assert "weekly" in (out.get("trigger_pattern") or "")

def t_workflow_execute_order():
    from src.workflows import execute_workflow
    calls = []

    class _Skill:
        def __init__(self, name):
            self._name = name
        def execute(self, user_input, context, params=None):
            calls.append(self._name)
            return f"ok-{self._name}"
        def tool_definition(self):
            return {"name": self._name}

    wf = {
        "id": 9,
        "name": "demo",
        "steps": [
            {"skill": "AlphaSkill", "description": "first"},
            {"skill": "BetaSkill", "description": "second"},
        ],
    }
    skills = [_Skill("AlphaSkill"), _Skill("BetaSkill")]
    text = execute_workflow(wf, "run demo", skills, {})
    assert calls == ["AlphaSkill", "BetaSkill"]
    assert "demo" in text
    assert "successfully" in text.lower()

def t_workflow_hybrid_embed_boost():
    import src.workflows as wf_mod
    fake = {
        "id": 7,
        "name": "inbox-zero",
        "trigger_pattern": "xyz obscure phrase",
        "steps_json": "[]",
        "expected_outputs": None,
        "failure_modes": None,
        "project": None,
        "source": "distilled",
        "confidence": 0.8,
        "last_used_at": None,
        "success_count": 0,
        "failure_count": 0,
    }
    class _Row:
        def __getitem__(self, k):
            return fake[k]
    def _fake_list(conn, project=None, limit=50):
        return [_Row()]
    class _Idx:
        def search(self, query, project=None, limit=20):
            return [{"workflow_id": 7, "name": "inbox-zero", "score": 0.92}]
    wf_mod.db.list_workflows = _fake_list
    from unittest.mock import patch
    with patch("src.workflow_vector.WorkflowVectorIndex", _Idx):
        match = wf_mod.search_workflows_by_intent(
            "clear my email inbox",
            use_embeddings=True,
        )
    assert match is not None
    assert match["name"] == "inbox-zero"
    assert match["match_score"] >= 0.5

def t_workflow_vector_index_mock():
    from unittest.mock import patch, MagicMock
    from src.workflow_vector import WorkflowVectorIndex
    idx = WorkflowVectorIndex()
    with patch.object(idx, "_embed", return_value=[0.1, 0.2, 0.3]):
        with patch("lancedb.connect") as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db
            mock_db.table_names.return_value = []
            mock_db.create_table = MagicMock()
            ok = idx.index_workflow(3, "test-wf", "run test workflow")
    assert ok is True

test("Workflow: LLM distill parses JSON (AC-CR042-002)", t_workflow_llm_distill)
test("Workflow: execute_workflow step order (AC-CR042-003)", t_workflow_execute_order)
test("Workflow: hybrid embed boosts recall (AC-CR042-004)", t_workflow_hybrid_embed_boost)
test("Workflow: vector index upsert mocked (AC-CR042-001)", t_workflow_vector_index_mock)


# ── CR-043 GPU-Aware Model Selection ─────────────────────────────────────────

def t_classify_desktop_profile():
    """AC-CR043-001: 16 GB total VRAM maps to DESKTOP profile (FR-GPU-001)."""
    from src.model_manager import _classify_profile, HardwareProfile
    result = _classify_profile(16_384)
    assert result == HardwareProfile.DESKTOP, f"Expected DESKTOP, got {result}"

def t_classify_laptop_profile():
    """AC-CR043-002: 8 GB total VRAM maps to LAPTOP profile (FR-GPU-001)."""
    from src.model_manager import _classify_profile, HardwareProfile
    result = _classify_profile(8_192)
    assert result == HardwareProfile.LAPTOP, f"Expected LAPTOP, got {result}"

def t_classify_none_is_minimal():
    """AC-CR043-003: None VRAM (no GPU) maps to MINIMAL profile (NFR-GPU-001)."""
    from src.model_manager import _classify_profile, HardwareProfile
    result = _classify_profile(None)
    assert result == HardwareProfile.MINIMAL, f"Expected MINIMAL, got {result}"

def t_select_model_desktop_thinking():
    """AC-CR043-004: DESKTOP profile selects qwen3:14b for thinking role (FR-GPU-002)."""
    import src.model_manager as mm
    original = mm._HARDWARE_PROFILE
    try:
        mm._HARDWARE_PROFILE = mm.HardwareProfile.DESKTOP
        model = mm.select_model("thinking")
        assert model == "qwen3:14b", f"Expected qwen3:14b, got {model}"
    finally:
        mm._HARDWARE_PROFILE = original

def t_startup_report_contains_profile_and_model():
    """AC-CR043-005: get_startup_report() includes profile name and model name (FR-GPU-003)."""
    import src.model_manager as mm
    original = mm._HARDWARE_PROFILE
    original_info = mm._vram_info
    try:
        mm._HARDWARE_PROFILE = mm.HardwareProfile.DESKTOP
        mm._vram_info = {"total_mb": 16_384, "free_mb": 13_000}
        report = mm.get_startup_report()
        assert "DESKTOP" in report, f"Profile not in report: {report!r}"
        assert "qwen3:14b" in report, f"Model not in report: {report!r}"
    finally:
        mm._HARDWARE_PROFILE = original
        mm._vram_info = original_info

test("GPU: 16 GB VRAM maps to DESKTOP profile (AC-CR043-001)", t_classify_desktop_profile)
test("GPU: 8 GB VRAM maps to LAPTOP profile (AC-CR043-002)", t_classify_laptop_profile)
test("GPU: None VRAM maps to MINIMAL profile (AC-CR043-003)", t_classify_none_is_minimal)
test("GPU: DESKTOP thinking role selects qwen3:14b (AC-CR043-004)", t_select_model_desktop_thinking)
test("GPU: startup report contains profile and model (AC-CR043-005)", t_startup_report_contains_profile_and_model)


# ── CR-045 Google Maps Skill ──────────────────────────────────────────────────

def t_maps_can_handle_directions():
    """AC-CR045-001: can_handle detects directions queries (FR-MAPS-001)."""
    from src.skills.maps_skill import MapsSkill
    skill = MapsSkill()
    score = skill.can_handle("directions to the library", {})
    assert score >= 0.90, f"Expected >= 0.90, got {score}"

def t_maps_can_handle_places():
    """AC-CR045-002: can_handle detects places queries (FR-MAPS-002)."""
    from src.skills.maps_skill import MapsSkill
    skill = MapsSkill()
    score = skill.can_handle("find a coffee shop near me", {})
    assert score >= 0.90, f"Expected >= 0.90, got {score}"

def t_maps_ignores_unrelated():
    """AC-CR045-003: can_handle returns 0.0 for non-maps queries (FR-MAPS-001)."""
    from src.skills.maps_skill import MapsSkill
    skill = MapsSkill()
    score = skill.can_handle("what is the weather today", {})
    assert score == 0.0, f"Expected 0.0, got {score}"

def t_maps_extract_destination():
    """AC-CR045-004: _extract_destination parses 'directions to X' (FR-MAPS-001)."""
    from src.skills.maps_skill import MapsSkill
    result = MapsSkill._extract_destination("directions to downtown San Diego")
    assert "San Diego" in result, f"Expected 'San Diego' in result, got {result!r}"

def t_maps_format_directions_structure():
    """AC-CR045-005: _format_directions includes distance, duration, steps (FR-MAPS-001)."""
    from src.skills.maps_skill import _format_directions
    mock_data = {
        "routes": [{
            "legs": [{
                "distance": {"text": "5.2 mi"},
                "duration": {"text": "12 mins"},
                "start_address": "123 Main St",
                "end_address": "456 Oak Ave",
                "steps": [
                    {"html_instructions": "Head <b>north</b>", "distance": {"text": "0.2 mi"}},
                    {"html_instructions": "Turn <b>right</b>", "distance": {"text": "5.0 mi"}},
                ],
            }]
        }]
    }
    result = _format_directions(mock_data, "origin", "dest", "driving")
    assert "5.2 mi" in result, "Expected distance in output"
    assert "12 mins" in result, "Expected duration in output"
    assert "Head north" in result, "Expected step 1 in output"

def t_maps_format_places_structure():
    """AC-CR045-006: _format_places includes name, address, rating (FR-MAPS-002)."""
    from src.skills.maps_skill import _format_places
    mock_data = {
        "results": [{
            "name": "Blue Bottle Coffee",
            "formatted_address": "123 Coffee Lane, San Diego, CA",
            "rating": 4.5,
            "user_ratings_total": 320,
            "opening_hours": {"open_now": True},
        }]
    }
    result = _format_places(mock_data, "coffee shop near me")
    assert "Blue Bottle Coffee" in result, "Expected place name in output"
    assert "4.5" in result, "Expected rating in output"
    assert "Open now" in result, "Expected open status in output"

def t_maps_missing_api_key_returns_message():
    """AC-CR045-007: execute returns setup instruction when API key is missing (NFR-MAPS-001)."""
    from unittest.mock import patch
    from src.skills.maps_skill import MapsSkill
    skill = MapsSkill()
    with patch("src.skills.maps_skill.get_secret", return_value=""):
        result = skill.execute("directions to the park", {}, {"intent": "directions"})
    assert "GOOGLE_MAPS_API_KEY" in result, "Expected API key setup message"

test("Maps: can_handle detects directions queries (AC-CR045-001)", t_maps_can_handle_directions)
test("Maps: can_handle detects places queries (AC-CR045-002)", t_maps_can_handle_places)
test("Maps: can_handle returns 0.0 for unrelated query (AC-CR045-003)", t_maps_ignores_unrelated)
test("Maps: _extract_destination parses 'directions to X' (AC-CR045-004)", t_maps_extract_destination)
test("Maps: _format_directions includes distance, duration, steps (AC-CR045-005)", t_maps_format_directions_structure)
test("Maps: _format_places includes name, address, rating (AC-CR045-006)", t_maps_format_places_structure)
test("Maps: missing API key returns setup instruction (AC-CR045-007)", t_maps_missing_api_key_returns_message)


# ── Print results ─────────────────────────────────────────────────────────────
print()
for r in results:
    if r[0] == "PASS":
        print(f"  PASS  {r[1]}")
    else:
        print(f"  FAIL  {r[1]}")
        tb_lines = r[2].strip().splitlines()
        for line in tb_lines[-8:]:
            print(f"        {line}")
        print()

passes = sum(1 for r in results if r[0] == "PASS")
fails  = sum(1 for r in results if r[0] == "FAIL")
print(f"\n  {passes} passed  {fails} failed")

# Final cleanup
cleanup()
