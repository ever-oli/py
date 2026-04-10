"""Write tool for Mom."""

from ..sandbox import Executor


def shell_escape(s: str) -> str:
    """Escape a string for shell."""
    return "'" + s.replace("'", "'\\''") + "'"


def create_write_tool(executor: Executor) -> dict:
    """Create the write tool."""

    async def execute(label: str, path: str, content: str) -> dict:
        """Write content to a file."""
        # Use heredoc to write content
        content.replace("\\", "\\\\").replace("'", "'\\''")
        cmd = f"cat > {shell_escape(path)} << 'EOF'\n{content}\nEOF"

        result = await executor.exec(cmd)

        if result.code != 0:
            raise Exception(result.stderr or f"Failed to write file: {path}")

        # Count lines and bytes
        stats_result = await executor.exec(
            f"wc -l < {shell_escape(path)} && stat -c%s {shell_escape(path)}"
        )
        lines = 0
        bytes_written = 0
        if stats_result.code == 0:
            parts = stats_result.stdout.strip().split("\n")
            if len(parts) >= 2:
                lines = int(parts[0])
                bytes_written = int(parts[1])

        return {
            "content": [
                {"type": "text", "text": f"Wrote {lines} lines ({bytes_written} bytes) to {path}"}
            ],
            "details": {"lines": lines, "bytes": bytes_written},
        }

    return {
        "name": "write",
        "description": "Write content to a file. Creates file if it doesn't exist, overwrites if it does.",
        "parameters": {
            "label": {"type": "string", "description": "Brief description"},
            "path": {"type": "string", "description": "Path to file"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "execute": execute,
    }
