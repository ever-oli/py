"""Attach tool for Mom.

Handles file attachments from Slack messages.
"""

from __future__ import annotations

from typing import Callable

# Global upload function (set by bot)
_upload_func: Callable | None = None


def set_upload_function(func: Callable | None) -> None:
    """Set the global upload function."""
    global _upload_func
    _upload_func = func


def attach_tool(params: dict) -> dict:
    """Handle file attachment.
    
    In Slack context, this is mainly informational since
    files are already downloaded by the bot.
    """
    file_path = params.get("file_path", "")
    
    return {
        "file_path": file_path,
        "success": True,
        "message": f"File attached: {file_path}"
    }


attach_tool.name = "attach"  # type: ignore
attach_tool.description = "Reference an attached file"  # type: ignore
attach_tool.parameters = {  # type: ignore
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Path to the attached file"
        }
    },
    "required": ["file_path"]
}
