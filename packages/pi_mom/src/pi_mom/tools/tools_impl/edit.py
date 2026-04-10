"""Edit tool for Mom."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...sandbox import Executor


def create_edit_tool(executor: Executor) -> dict[str, Any]:
    """Create file edit tool."""
    return {
        "name": "edit",
        "description": "Edit a file by replacing text",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit"
                },
                "old_string": {
                    "type": "string",
                    "description": "String to find and replace"
                },
                "new_string": {
                    "type": "string",
                    "description": "Replacement string"
                }
            },
            "required": ["file_path", "old_string", "new_string"]
        },
        "execute": lambda params: _edit_file(executor, params)
    }


def _edit_file(executor: Executor, params: dict) -> dict:
    """Edit file via executor using sed."""
    file_path = params.get("file_path", "")
    old_string = params.get("old_string", "")
    new_string = params.get("new_string", "")

    # Escape for sed
    old_escaped = old_string.replace("'", "'\\''").replace("/", "\\/")
    new_escaped = new_string.replace("'", "'\\''").replace("/", "\\/")

    cmd = f"sed -i 's/{old_escaped}/{new_escaped}/g' '{file_path}'"
    result = asyncio.run(executor.exec(cmd))

    return {
        "file_path": file_path,
        "success": result.code == 0,
        "error": result.stderr if result.code != 0 else None
    }
