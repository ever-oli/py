"""Write tool implementation for writing file contents."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class WriteOperations(Protocol):
    """Pluggable operations for the write tool."""

    async def write_file(self, absolute_path: str, content: str) -> None:
        """Write content to a file."""
        ...

    async def mkdir(self, dir_path: str) -> None:
        """Create directory recursively."""
        ...


class LocalWriteOperations:
    """Default local filesystem operations for write tool."""

    async def write_file(self, absolute_path: str, content: str) -> None:
        from aiofiles import open as aio_open

        async with aio_open(absolute_path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def mkdir(self, dir_path: str) -> None:
        Path(dir_path).mkdir(parents=True, exist_ok=True)


@dataclass
class WriteToolInput:
    """Input for write tool."""

    path: str
    content: str


@dataclass
class WriteToolOptions:
    """Options for write tool."""

    operations: WriteOperations | None = None


def resolve_to_cwd(path: str, cwd: str) -> str:
    """Resolve a path relative to cwd.

    Args:
        path: Path (relative or absolute)
        cwd: Current working directory

    Returns:
        Absolute path
    """
    if Path(path).is_absolute():
        return str(Path(path).resolve())
    return str(Path(cwd) / path)


class WriteTool:
    """Write tool for writing file contents."""

    def __init__(self, cwd: str, options: WriteToolOptions | None = None):
        self.cwd = cwd
        self.options = options or WriteToolOptions()
        self.operations = self.options.operations or LocalWriteOperations()

    async def execute(
        self,
        path: str,
        content: str,
        signal: Any = None,
    ) -> dict[str, Any]:
        """Execute the write tool.

        Args:
            path: Path to the file to write
            content: Content to write to the file
            signal: AbortSignal for cancellation

        Returns:
            Dict with content
        """
        if signal and hasattr(signal, "aborted") and signal.aborted:
            raise RuntimeError("Operation aborted")

        absolute_path = resolve_to_cwd(path, self.cwd)

        # Create parent directories if needed
        parent_dir = Path(absolute_path).parent
        if parent_dir and not parent_dir.exists():
            await self.operations.mkdir(str(parent_dir))

        # Write the file
        await self.operations.write_file(absolute_path, content)

        # Return success message
        return {
            "content": [{"type": "text", "text": f"Successfully wrote to {path}"}],
            "details": None,
        }


def create_write_tool(cwd: str, options: WriteToolOptions | None = None):
    """Create a write tool instance."""
    tool = WriteTool(cwd, options)

    async def execute(path: str, content: str, signal: Any = None):
        return await tool.execute(path, content, signal)

    return {
        "name": "write",
        "description": (
            "Write content to a file. Creates the file if it doesn't exist, "
            "overwrites if it does. Automatically creates parent directories."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write (relative or absolute)",
                },
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        },
        "execute": execute,
    }


def create_write_tool_definition(
    cwd: str, options: WriteToolOptions | None = None
) -> dict[str, Any]:
    """Create a write tool definition for the agent."""
    return create_write_tool(cwd, options)


# Default write tool using current working directory
write_tool_definition = create_write_tool_definition(Path.cwd())
write_tool = write_tool_definition
