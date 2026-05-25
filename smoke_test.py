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
