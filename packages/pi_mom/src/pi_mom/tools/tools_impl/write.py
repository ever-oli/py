"""Write tool for Mom."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...sandbox import Executor


def create_write_tool(executor: Executor) -> dict[str, Any]:
    """Create file write tool."""
    return {
        "name": "write",
        "description": "Write content to a file (creates or overwrites)",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write"
                }
            },
            "required": ["file_path", "content"]
        },
        "execute": lambda params: _write_file(executor, params)
    }


def _write_file(executor: Executor, params: dict) -> dict:
    """Write file via executor using here-doc."""
    file_path = params.get("file_path", "")
    content = params.get("content", "")

    # Escape single quotes in content
    escaped = content.replace("'", "'\\''")

    cmd = f"mkdir -p '$(dirname {file_path})' && cat > '{file_path}' << 'EOF_MOM_WRITE'\n{escaped}\nEOF_MOM_WRITE"
    result = asyncio.run(executor.exec(cmd))

    return {
        "file_path": file_path,
        "success": result.code == 0,
        "error": result.stderr if result.code != 0 else None
    }
