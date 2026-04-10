"""Edit tool for Mom."""

from ..sandbox import Executor


def shell_escape(s: str) -> str:
    """Escape a string for shell."""
    return "'" + s.replace("'", "'\\''") + "'"


def escape_for_sed(s: str) -> str:
    """Escape a string for sed replacement."""
    return s.replace("\\", "\\\\").replace("/", "\\/").replace("&", "\\&").replace("\n", "\\n")


def create_edit_tool(executor: Executor) -> dict:
    """Create the edit tool."""

    async def execute(label: str, file_path: str, old_string: str, new_string: str) -> dict:
        """Edit a file by replacing old_string with new_string."""
        # First check if the file contains the old_string
        check_result = await executor.exec(
            f"grep -F {shell_escape(old_string)} {shell_escape(file_path)}"
        )
        if check_result.code != 0:
            raise Exception(f"old_string not found in file: {file_path}")

        # Use sed to replace
        old_escaped = escape_for_sed(old_string)
        new_escaped = escape_for_sed(new_string)
        cmd = f"sed -i 's/{old_escaped}/{new_escaped}/g' {shell_escape(file_path)}"

        result = await executor.exec(cmd)

        if result.code != 0:
            raise Exception(result.stderr or f"Failed to edit file: {file_path}")

        return {"content": [{"type": "text", "text": f"Edited {file_path}"}], "details": None}

    return {
        "name": "edit",
        "description": "Edit a file by replacing old_string with new_string. The old_string must match exactly.",
        "parameters": {
            "label": {"type": "string", "description": "Brief description"},
            "file_path": {"type": "string", "description": "Path to file"},
            "old_string": {"type": "string", "description": "Exact text to replace"},
            "new_string": {"type": "string", "description": "New text to insert"},
        },
        "execute": execute,
    }
