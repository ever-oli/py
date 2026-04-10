"""Ls tool implementation for listing directory contents."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class LsOperations(Protocol):
    """Pluggable operations for the ls tool."""

    async def list_dir(self, path: str) -> dict[str, Any]:
        """List directory contents."""
        ...


class LocalLsOperations:
    """Default local filesystem operations for ls tool."""

    async def list_dir(self, path: str) -> dict[str, Any]:
        """List directory contents."""
        dir_path = Path(path)

        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {path}")

        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")

        entries = []

        try:
            for entry in dir_path.iterdir():
                try:
                    stat = entry.stat()
                    is_dir = entry.is_dir()

                    entries.append(
                        {
                            "name": entry.name,
                            "is_dir": is_dir,
                            "size": stat.st_size if not is_dir else None,
                        }
                    )
                except (OSError, PermissionError):
                    # Skip entries we can't stat
                    continue
        except PermissionError:
            raise PermissionError(f"Permission denied: {path}")

        # Sort: directories first, then alphabetically
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))

        return {
            "path": str(dir_path),
            "entries": entries,
        }


@dataclass
class LsToolInput:
    """Input for ls tool."""

    path: str | None = None


@dataclass
class LsEntry:
    """A directory entry."""

    name: str
    is_dir: bool
    size: int | None = None


@dataclass
class LsToolDetails:
    """Details from ls tool execution."""

    entries: list[LsEntry]


@dataclass
class LsToolOptions:
    """Options for ls tool."""

    operations: LsOperations | None = None


def format_size(size: int) -> str:
    """Format a size in bytes as human-readable string."""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size // 1024}KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size // (1024 * 1024)}MB"
    else:
        return f"{size // (1024 * 1024 * 1024)}GB"


class LsTool:
    """Ls tool for listing directory contents."""

    def __init__(self, cwd: str, options: LsToolOptions | None = None):
        self.cwd = cwd
        self.options = options or LsToolOptions()
        self.operations = self.options.operations or LocalLsOperations()

    async def execute(
        self,
        path: str | None = None,
        signal: Any = None,
    ) -> dict[str, Any]:
        """Execute the ls tool."""
        if signal and hasattr(signal, "aborted") and signal.aborted:
            raise RuntimeError("Operation aborted")

        target_path = path or "."

        if Path(target_path).is_absolute():
            absolute_path = str(Path(target_path).resolve())
        else:
            absolute_path = str(Path(self.cwd) / target_path)

        result = await self.operations.list_dir(absolute_path)

        # Format output
        lines = []
        lines.append(f"Directory: {result['path']}")
        lines.append("")

        if not result["entries"]:
            lines.append("(empty directory)")
        else:
            for entry in result["entries"]:
                if entry["is_dir"]:
                    lines.append(f"📁 {entry['name']}/")
                else:
                    size_str = format_size(entry["size"]) if entry["size"] is not None else ""
                    lines.append(f"📄 {entry['name']:<40} {size_str:>10}")

        content_text = "\n".join(lines)
        content = [{"type": "text", "text": content_text}]

        ls_entries = [
            LsEntry(name=e["name"], is_dir=e["is_dir"], size=e["size"]) for e in result["entries"]
        ]
        details = LsToolDetails(entries=ls_entries)

        return {"content": content, "details": details}


def create_ls_tool(cwd: str, options: LsToolOptions | None = None):
    """Create an ls tool instance."""
    tool = LsTool(cwd, options)

    async def execute(path: str | None = None, signal: Any = None):
        return await tool.execute(path, signal)

    return {
        "name": "ls",
        "description": (
            "List the contents of a directory. Shows files and subdirectories with sizes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the directory to list (relative or absolute, default: current directory)",
                },
            },
            "required": [],
        },
        "execute": execute,
    }


def create_ls_tool_definition(cwd: str, options: LsToolOptions | None = None) -> dict[str, Any]:
    """Create an ls tool definition for the agent."""
    return create_ls_tool(cwd, options)


ls_tool_definition = create_ls_tool_definition(Path.cwd())
ls_tool = ls_tool_definition
