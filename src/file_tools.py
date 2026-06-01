"""FileTools — conversational file operations with a permission model.

Read: automatic.
Write new file: returns pending_permission, requires confirm_operation().
Overwrite existing: returns pending_permission, requires confirm_operation().
Delete: returns pending_permission, requires confirm_operation().
"""
# Implements FR-SEC-002 (Permission-Gated File Writes — overwrites/deletes require confirm_operation() before proceeding)

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src import security


class FileTools:
    def __init__(self):
        self.pending_operations: dict[str, dict] = {}

    def read_file(self, path: Path) -> str:
        return security.read_file(Path(path))

    def write_file(self, path: Path, content: str) -> dict:
        path = Path(path)
        if not security._is_allowed(path):
            raise security.PermissionError(f"Cannot write to {path} — outside allowed directories")

        # FR-UI-011 (CR-052): show a diff (overwrite) or content preview (new file)
        # so the user can see exactly what they are approving.
        from src.diff_preview import make_diff_preview, make_new_file_preview

        op_type = "overwrite" if path.exists() else "write"
        if op_type == "overwrite":
            try:
                old = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                old = ""
            preview = make_diff_preview(old, content, str(path.name))
            headline = f"Overwrite {path.name}?"
        else:
            preview = make_new_file_preview(content, str(path.name))
            headline = f"Create {path.name}?"

        op_id = self._create_pending(op_type, path, content)
        return {
            "status": "pending_permission",
            "message": f"{headline}\n\n{preview}",
            "operation_id": op_id,
        }

    def delete_file(self, path: Path) -> dict:
        path = Path(path)
        if not security._is_allowed(path):
            raise security.PermissionError(f"Cannot delete {path} — outside allowed directories")

        if not path.exists():
            return {"status": "error", "message": f"File {path} doesn't exist"}

        op_id = self._create_pending("delete", path, None)
        return {
            "status": "pending_permission",
            "message": f"Delete {path.name}? This cannot be undone.",
            "operation_id": op_id,
        }

    def confirm_operation(self, operation_id: str) -> dict:
        op = self.pending_operations.get(operation_id)
        if not op:
            return {"status": "error", "message": "Unknown operation"}

        # FR-MEM-015 (CR-052): record the edit in the session ring buffer.
        from src.recent_edits import record_edit

        if op["type"] in {"write", "overwrite"}:
            old_lines = 0
            if op["type"] == "overwrite" and op["path"].exists():
                try:
                    old_lines = len(op["path"].read_text(encoding="utf-8", errors="replace").splitlines())
                except Exception:
                    old_lines = 0
            op["path"].parent.mkdir(parents=True, exist_ok=True)
            op["path"].write_text(op["content"], encoding="utf-8")
            new_lines = len((op["content"] or "").splitlines())
            record_edit(str(op["path"]), op["type"], line_delta=new_lines - old_lines)
            verb = "Overwrote" if op["type"] == "overwrite" else "Created"
            msg = f"{verb}: file:///{op['path'].absolute().as_posix()}"
        elif op["type"] == "delete":
            op["path"].unlink()
            record_edit(str(op["path"]), "delete", line_delta=0)
            msg = f"Deleted: {op['path'].name}"
        else:
            msg = "Unknown operation type"

        del self.pending_operations[operation_id]
        return {"status": "completed", "message": msg}

    def cancel_operation(self, operation_id: str) -> dict:
        self.pending_operations.pop(operation_id, None)
        return {"status": "cancelled", "message": "Operation cancelled"}

    def _create_pending(self, op_type: str, path: Path, content: Optional[str]) -> str:
        op_id = str(uuid.uuid4())[:8]
        self.pending_operations[op_id] = {
            "type": op_type,
            "path": path,
            "content": content,
            "created_at": datetime.now(),
        }
        return op_id
