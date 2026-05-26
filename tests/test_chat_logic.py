"""Test the conversational layer of XochitlChat."""
import unittest
from unittest.mock import patch
from pathlib import Path
from src.chat import XochitlChat

class TestChatLogic(unittest.TestCase):
    def setUp(self):
        self.chat = XochitlChat()

    def test_intent_classification(self):
        cases = [
            ("I want to build a fitness app", "new_project"),
            ("Show my tasks", "task_query"),
            ("What is in src/cli.py", "file_operation"),
            ("Sync from notion", "action_request"),
        ]
        for inp, expected in cases:
            intent = self.chat._classify_intent(inp)
            self.assertEqual(intent["type"], expected, f"Input: {inp}")

    def test_project_detection(self):
        # This will depend on current directory, but we can mock it
        with patch("src.chat.XochitlChat._detect_current_project", return_value="test-proj"):
            self.chat.current_project = self.chat._detect_current_project()
            self.assertEqual(self.chat.current_project, "test-proj")
            
            # Now test project-specific intents
            intent = self.chat._classify_intent("There's a bug in the calculator")
            self.assertEqual(intent["type"], "issue_tracking")
            
            intent = self.chat._classify_intent("Scaffold the backend")
            self.assertEqual(intent["type"], "code_generation_intent")
            
            intent = self.chat._classify_intent("List requirements")
            self.assertEqual(intent["type"], "sdd_workflow")

if __name__ == "__main__":
    unittest.main()
