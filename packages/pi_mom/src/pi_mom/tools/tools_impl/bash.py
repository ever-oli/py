"""Bash tool for Mom."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...sandbox import Executor


def create_bash_tool(executor: Executor) -> dict[str, Any]:
    """Create bash execution tool."""
    return {
        "name": "bash",
        "description": "Execute bash commands in the sandbox",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 60)",
                    "default": 60
                }
            },
            "required": ["command"]
        },
        "execute": lambda params: _run_bash(executor, params)
    }


def _run_bash(executor: Executor, params: dict) -> dict:
    """Execute bash command via executor."""
    command = params.get("command", "")
    timeout = params.get("timeout", 60)

    result = asyncio.run(executor.exec(command, timeout))

    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.code,
        "success": result.code == 0
    }
