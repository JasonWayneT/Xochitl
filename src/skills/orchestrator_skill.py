"""Orchestrator skill — manages background autonomous task execution.

This is both a detectable Skill (Xochitl suggests it when delegation is
requested) and a task workspace manager. The daemon subprocess is the Phase 4
full orchestrator; here we implement workspace creation and progress tracking
so the chat layer has something real to query.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.skills.base import Skill

_WORKSPACE_ROOT = Path(__file__).parent.parent.parent / ".xochitl" / "workspaces"
_DELEGATE_KEYWORDS = ["delegate", "background", "handle it", "spin up", "autonomous", "agent"]
_STATUS_KEYWORDS = ["background task", "delegated", "how is the", "what is the agent", "progress"]


class OrchestratorSkill(Skill):

    def __init__(self):
        self._daemon_pid: Optional[int] = None
        self._active_workspaces: dict[str, dict] = {}

    # ── Skill interface ───────────────────────────────────────────────────────

    def can_handle(self, user_input: str, context: dict) -> float:
        q = user_input.lower()
        if any(kw in q for kw in _DELEGATE_KEYWORDS + _STATUS_KEYWORDS):
            return 0.75
        return 0.0

    def suggest(self, user_input: str, context: dict) -> str:
        q = user_input.lower()
        if any(kw in q for kw in _STATUS_KEYWORDS):
            return self._format_status()
        return (
            "I can hand this off to a background agent while you keep working on other things. "
            "It'll run in its own workspace and I'll flag you when it's ready for review. "
            "Want to delegate it?"
        )

    def execute(self, user_input: str, context: dict, params: dict) -> str:
        task_id = params.get("task_id")
        if task_id:
            return self.delegate_task(task_id)
        return self._format_status()

    # ── Daemon management ─────────────────────────────────────────────────────

    def start_daemon(self) -> str:
        if self._daemon_pid and self._is_pid_alive(self._daemon_pid):
            return "Orchestrator is already running."

        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "src.orchestrator_daemon"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._daemon_pid = proc.pid
            _write_pid_file(proc.pid)
            return f"Orchestrator started (PID {proc.pid}). Background task execution is active."
        except Exception as e:
            # Daemon module doesn't exist yet — just track in-process
            self._daemon_pid = -1
            return "Orchestrator running (in-process mode)."

    def stop_daemon(self) -> str:
        if not self._daemon_pid:
            return "Orchestrator isn't running."
        try:
            import os, signal
            os.kill(self._daemon_pid, signal.SIGTERM)
        except Exception:
            pass
        self._daemon_pid = None
        _remove_pid_file()
        return "Orchestrator stopped. Background tasks paused."

    def is_running(self) -> bool:
        if not self._daemon_pid:
            return False
        return self._is_pid_alive(self._daemon_pid)

    # ── Task delegation ───────────────────────────────────────────────────────

    def delegate_task(self, task_id: str) -> str:
        if not self._daemon_pid:
            self.start_daemon()

        workspace = self._create_workspace(task_id)
        self._active_workspaces[task_id] = {
            "workspace_dir": workspace,
            "started_at": datetime.now().isoformat(),
            "state": "running",
        }

        return (
            f"Workspace created: {workspace}\n"
            "Agent is working on it. Ask me 'how's the background task doing?' to check in."
        )

    def get_status(self) -> dict:
        tasks = []
        for task_id, info in self._active_workspaces.items():
            progress = self._read_progress(Path(info["workspace_dir"]))
            tasks.append({
                "task_id": task_id,
                "description": progress.get("description", task_id),
                "state": progress.get("state", info["state"]),
                "completed_steps": len(progress.get("completed_steps", [])),
                "total_steps": max(len(progress.get("completed_steps", [])) + len(progress.get("next_steps", [])), 1),
                "runtime": _elapsed(info["started_at"]),
            })
        return {"active_count": len(tasks), "tasks": tasks}

    # ── Internals ─────────────────────────────────────────────────────────────

    def _create_workspace(self, task_id: str) -> Path:
        workspace = _WORKSPACE_ROOT / f"task-{task_id}"
        workspace.mkdir(parents=True, exist_ok=True)
        artifacts = workspace / "task-artifacts"
        artifacts.mkdir(exist_ok=True)

        initial_progress = {
            "description": task_id,
            "state": "initializing",
            "completed_steps": [],
            "next_steps": ["gather context", "implement", "test", "submit for review"],
            "started_at": datetime.now().isoformat(),
        }
        (artifacts / "progress.json").write_text(
            json.dumps(initial_progress, indent=2), encoding="utf-8"
        )
        return workspace

    def _read_progress(self, workspace: Path) -> dict:
        progress_file = workspace / "task-artifacts" / "progress.json"
        if progress_file.exists():
            try:
                return json.loads(progress_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _format_status(self) -> str:
        status = self.get_status()
        if status["active_count"] == 0:
            return "No background tasks running. Want to delegate something?"
        lines = [f"Running {status['active_count']} background task(s):\n"]
        for t in status["tasks"]:
            pct = int(t["completed_steps"] / t["total_steps"] * 100)
            lines.append(f"• {t['description'][:50]} — {t['state']} ({pct}%, {t['runtime']})")
        return "\n".join(lines)

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        try:
            import os, signal
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


# ── PID file helpers ──────────────────────────────────────────────────────────

_PID_FILE = Path(__file__).parent.parent.parent / ".xochitl" / "orchestrator.pid"


def _write_pid_file(pid: int) -> None:
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(pid))


def _remove_pid_file() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _elapsed(started_at: str) -> str:
    try:
        delta = datetime.now() - datetime.fromisoformat(started_at)
        minutes = int(delta.total_seconds() / 60)
        if minutes < 60:
            return f"{minutes}m"
        return f"{minutes // 60}h {minutes % 60}m"
    except Exception:
        return "?"
