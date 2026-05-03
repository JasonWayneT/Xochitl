"""Notion sync skill — suggests syncing when task/project keywords appear."""

from src.skills.base import Skill


_NOTION_KEYWORDS = ["notion", "sync", "pull", "push", "projects", "tasks", "queue"]


class NotionSkill(Skill):

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()
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
