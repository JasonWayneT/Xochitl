"""End-to-end integration test for the BMAD→SDD→Code pipeline."""
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.skills.bmad_skill import BMADSkill
from src.skills.sdd_skill import SDDSkill
from src.skills.code_skill import CodeSkill

ROOT = Path(__file__).parent
TEST_PROJECT = "e2e-test-project"
PROJECT_PATH = ROOT / "projects" / TEST_PROJECT

class TestPipelineE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if PROJECT_PATH.exists():
            shutil.rmtree(PROJECT_PATH)
        
    def setUp(self):
        self.bmad = BMADSkill()
        self.sdd = SDDSkill()
        self.code = CodeSkill()

    def tearDown(self):
        if PROJECT_PATH.exists():
            shutil.rmtree(PROJECT_PATH)
        log = ROOT / ".sdd" / "logs" / "spec-changes.jsonl"
        if log.exists():
            log.unlink()

    @patch("src.router.TieredRouter.route")
    def test_full_pipeline(self, mock_route):
        # 1. Init Project
        self.bmad.init_project(TEST_PROJECT, "E2E App", "A test app for E2E validation")
        self.assertTrue((PROJECT_PATH / ".project-meta.yml").exists())
        
        # 2. Save BMAD Artifacts
        self.bmad.save_bmad_artifact(TEST_PROJECT, "business-model", "# Business Model\n\nProblem: Manual macro tracking is hard.")
        self.bmad.save_bmad_artifact(TEST_PROJECT, "architecture", "# Architecture\n\nBackend: FastAPI\nFrontend: React")
        self.assertTrue(self.bmad.is_bmad_complete(TEST_PROJECT))
        
        # 3. Generate Specs (Mock LLM)
        mock_route.return_value = MagicMock(
            content=json.dumps({
                "requirements": [
                    {
                        "id": "FR-CORE-001",
                        "title": "Log Meal",
                        "description": "Users can log their meals.",
                        "priority": "P0",
                        "acceptance_criteria": ["AC-CORE-001: Meal saved to DB"],
                        "edge_cases": ["EC-CORE-001: Invalid calories rejected"],
                        "bmad_source": "business-model.md"
                    }
                ]
            }),
            error=None
        )
        
        result = self.sdd.generate_specs_from_bmad(TEST_PROJECT)
        self.assertIn("Generated 1 requirements", result)
        self.assertTrue((PROJECT_PATH / "specs" / "core-features.md").exists())
        self.assertTrue((PROJECT_PATH / "specs" / "traceability.json").exists())
        
        # 4. Create and Analyze Issue (Mock LLM)
        issue_id = "BUG-001"
        self.sdd.create_issue(TEST_PROJECT, "bug", "Negative calories allowed", "The app allows negative calorie values.")
        
        mock_route.return_value = MagicMock(
            content=json.dumps({
                "analysis_type": "spec_gap",
                "affected_requirements": ["FR-CORE-001"],
                "spec_changes_needed": [
                    {
                        "requirement_id": "FR-CORE-001",
                        "change_type": "modify",
                        "proposed_text": "Updated validation to reject negative calories.",
                        "rationale": "Security and data integrity."
                    }
                ],
                "confidence": 0.9
            }),
            error=None
        )
        
        analysis = self.sdd.analyze_issue(TEST_PROJECT, issue_id)
        self.assertEqual(analysis["analysis_type"], "spec_gap")
        
        # 5. Update Requirement
        self.sdd.update_requirement(TEST_PROJECT, "FR-CORE-001", {
            "status": "in_progress",
            "add_acceptance_criterion": "AC-CORE-002: Reject negative values",
            "trigger": issue_id
        })
        
        req = self.sdd.get_requirement(TEST_PROJECT, "FR-CORE-001")
        self.assertEqual(req["status"], "in_progress")
        self.assertTrue(any("Reject negative values" in ac for ac in req["acceptance_criteria"]))
        
        # 6. Scaffold Code (Mock LLM)
        mock_route.return_value = MagicMock(
            content=json.dumps({
                "files": [
                    {"path": "src/api/meals.py", "content": "# Implements FR-CORE-001\ndef create_meal(): pass", "action": "create"}
                ],
                "tests": [
                    {"path": "tests/test_meals.py", "content": "def test_create_meal(): pass", "action": "create"}
                ],
                "traceability_updates": [
                    {
                        "requirement_id": "FR-CORE-001",
                        "implementation": {"file": "src/api/meals.py", "functions": ["create_meal"]}
                    }
                ]
            }),
            error=None
        )
        
        scaffold_result = self.code.scaffold_from_specs(TEST_PROJECT, "backend")
        self.assertIn("Scaffolded 1 source file(s)", scaffold_result)
        self.assertTrue((PROJECT_PATH / "src" / "api" / "meals.py").exists())
        
        # 7. Final Verification
        trace = self.sdd._load_traceability(TEST_PROJECT)
        mapping = next(m for m in trace["mappings"] if m["id"] == "FR-CORE-001")
        self.assertEqual(mapping["status"], "implemented")
        self.assertEqual(mapping["implementation"][0]["file"], "src/api/meals.py")
        
        meta = self.sdd._read_meta(TEST_PROJECT)
        self.assertTrue(meta["code_scaffolded"])
        self.assertEqual(meta["stats"]["implemented_requirements"], 1)

if __name__ == "__main__":
    unittest.main()
