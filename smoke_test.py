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


# ── 3. read_project_meta correctness ─────────────────────────────────────────
def t_read_meta():
    from src.skills._skill_helpers import read_project_meta
    meta = read_project_meta(TEST_PROJECT)
    assert meta["project_id"] == TEST_PROJECT
    assert meta["name"] == "Smoke Test App"
    assert meta["bmad_complete"] == False
    assert meta["specs_generated"] == False
    assert "stack" in meta
test("read_project_meta: reads correct values", t_read_meta)


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


# ── 7. parse_skill_json ──────────────────────────────────────────────────────
def t_json_parse():
    from src.skills._skill_helpers import parse_skill_json
    # Plain JSON
    r1 = parse_skill_json('{"key": "value"}')
    assert r1 == {"key": "value"}, f"Plain JSON failed: {r1}"
    # With markdown fences
    fenced = "```json\n{\"key\": \"value\"}\n```"
    r2 = parse_skill_json(fenced)
    assert r2 == {"key": "value"}, f"Fenced JSON failed: {r2}"
    # Bad JSON (no retry_prompt) → error dict
    r3 = parse_skill_json("not json at all")
    assert "error" in r3, f"Bad JSON should return error dict: {r3}"
test("parse_skill_json: plain, fenced, bad", t_json_parse)


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
    from src.skills._skill_helpers import read_project_meta, write_project_meta
    meta = read_project_meta(TEST_PROJECT)
    meta["specs_generated"] = True
    meta["stats"]["total_requirements"] = 2
    write_project_meta(TEST_PROJECT, meta)
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
