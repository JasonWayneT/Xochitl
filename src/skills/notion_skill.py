"""Notion sync skill — suggests syncing when task/project keywords appear."""

from src.skills.base import Skill


# Specific Notion keywords only — "projects" is too generic and hijacks BMAD/file queries
_NOTION_KEYWORDS = ["notion", "sync notion", "pull from notion", "push to notion", "notion tasks"]

# If any of these are present, Notion should never intercept (higher-priority intent)
_NOTION_EXCLUSIONS = ["bmad", "sdd", "spec", "read", "folder", "file", "zettle", "zettlelib"]


class NotionSkill(Skill):

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()
        # Never intercept BMAD/file/spec workflows
        if any(ex in q for ex in _NOTION_EXCLUSIONS):
            return 0.0
        if any(kw in q for kw in _NOTION_KEYWORDS):
            return 0.7
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        q = user_input.lower()
        if "sync" in q or "pull" in q:
            return (
                "I can pull the latest updates from Notion — projects, deadlines, new tasks. "
                "Want me to run the sync?"
            )
        if "push" in q:
            return (
                "I can push your completed tasks to Notion. Want me to do that?"
            )
        return (
            "I can sync with Notion to get the latest project and task data. "
            "Want me to pull updates or push completed tasks?"
        )

    def tool_definition(self) -> dict:
        # Implements FR-ORCH-005
        return {
            "name": "NotionSkill",
            "description": "Syncs tasks and projects between Xochitl and Notion (pull latest or push completed).",
            "when": "user mentions 'notion', 'sync', 'pull from notion', 'push to notion', or wants to update their task list from Notion",
            "params": {
                "direction": "pull | push",
            },
        }

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        direction = params.get("direction", "pull")

        if direction == "push":
            return self._push()
        return self._pull()

    def _pull(self) -> str:
        try:
            from src import notion_sync
            result = notion_sync.pull_and_sync()
            return (
                f"Pulled {result['projects']} projects, {result['areas']} areas, "
                f"{result['resources']} resources. "
                f"Conflicts resolved: {result['conflicts']}."
            )
        except RuntimeError as e:
            return f"Notion unavailable: {e}"
        except Exception as e:
            return f"Sync error: {e}"

    def _push(self) -> str:
        try:
            from src import notion_sync
            result = notion_sync.sync_completed_to_notion()
            return f"Pushed {result['pushed']} completed tasks to Notion."
        except RuntimeError as e:
            return f"Notion unavailable: {e}"
        except Exception as e:
            return f"Push error: {e}"
