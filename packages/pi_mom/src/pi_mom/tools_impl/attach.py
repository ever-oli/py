"""Attach tool for Mom."""

from collections.abc import Callable

_upload_function: Callable[[str, str | None], None] | None = None


def set_upload_function(fn: Callable[[str, str | None], None]) -> None:
    """Set the upload function for file attachments."""
    global _upload_function
    _upload_function = fn


async def execute(label: str, file_path: str, title: str | None = None) -> dict:
    """Attach a file to the Slack conversation."""
    if _upload_function is None:
        raise Exception("Upload function not set")

    _upload_function(file_path, title)

    return {"content": [{"type": "text", "text": f"Attached file: {file_path}"}], "details": None}


attach_tool = {
    "name": "attach",
    "description": "Share a file to the Slack conversation.",
    "parameters": {
        "label": {"type": "string", "description": "Brief description"},
        "file_path": {"type": "string", "description": "Path to file"},
        "title": {"type": "string", "description": "Optional title", "optional": True},
    },
    "execute": execute,
}
