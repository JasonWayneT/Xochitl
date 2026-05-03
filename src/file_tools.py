"""FileTools — conversational file operations with a permission model.

Read: automatic.
Write new file: automatic.
Overwrite existing: returns pending_permission, requires confirm_operation().
Delete: returns pending_permission, requires confirm_operation().
"""

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

        if path.exists():
            op_id = self._create_pending("overwrite", path, content)
            return {
                "status": "pending_permission",
                "message": f"File {path.name} already exists. Overwrite it?",
                "operation_id": op_id,
            }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {
            "status": "written",
            "message": f"Created: file:///{path.absolute().as_posix()}",
            "operation_id": None,
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

        if op["type"] == "overwrite":
            op["path"].write_text(op["content"], encoding="utf-8")
            msg = f"Overwrote: file:///{op['path'].absolute().as_posix()}"
        elif op["type"] == "delete":
            op["path"].unlink()
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
