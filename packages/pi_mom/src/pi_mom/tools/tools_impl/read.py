"""Read tool for Mom."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...sandbox import Executor


def create_read_tool(executor: Executor) -> dict[str, Any]:
    """Create file read tool."""
    return {
        "name": "read",
        "description": "Read contents of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "offset": {
                    "type": "integer",
                    "description": "Line offset to start reading from",
                    "default": 0
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read",
                    "default": 100
                }
            },
            "required": ["file_path"]
        },
        "execute": lambda params: _read_file(executor, params)
    }


def _read_file(executor: Executor, params: dict) -> dict:
    """Read file via executor."""
    file_path = params.get("file_path", "")
    offset = params.get("offset", 0)
    limit = params.get("limit", 100)

    # Use cat with sed for offset/limit
    cmd = f"cat '{file_path}' 2>/dev/null | sed -n '{offset+1},{offset+limit}p'"
    result = asyncio.run(executor.exec(cmd))

    # Get total lines
    wc_result = asyncio.run(executor.exec(f"wc -l < '{file_path}' 2>/dev/null || echo 0"))
    total_lines = int(wc_result.stdout.strip() or 0)

    return {
        "content": result.stdout,
        "file_path": file_path,
        "offset": offset,
        "limit": limit,
        "total_lines": total_lines,
        "success": result.code == 0,
        "error": result.stderr if result.code != 0 else None
    }
