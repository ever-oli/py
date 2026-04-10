"""Find tool implementation for finding files by name/pattern."""

import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class FindOperations(Protocol):
    """Pluggable operations for the find tool."""

    async def find(
        self,
        cwd: str,
        options: dict[str, Any],
    ) -> list[str]:
        """Find files matching criteria."""
        ...


class LocalFindOperations:
    """Default local filesystem operations for find tool."""

    async def find(
        self,
        cwd: str,
        options: dict[str, Any],
    ) -> list[str]:
        """Find files matching criteria."""
        paths = options.get("paths", ["."])
        name_pattern = options.get("name_pattern")
        exclude = options.get("exclude", [".git", "node_modules", "__pycache__", ".venv", "venv"])
        max_results = options.get("max_results", 100)

        results = []

        for path in paths:
            search_path = Path(cwd) / path

            if not search_path.exists():
                continue

            if search_path.is_file():
                # Single file
                if name_pattern and not fnmatch.fnmatch(search_path.name, name_pattern):
                    continue
                results.append(str(search_path.relative_to(cwd)))
            else:
                # Directory - walk recursively
                for root, dirs, files in search_path.walk():
                    # Filter out excluded directories
                    dirs[:] = [
                        d
                        for d in dirs
                        if d not in exclude
                        and not any(fnmatch.fnmatch(d, pattern) for pattern in exclude)
                    ]

                    for filename in files:
                        # Check exclude patterns
                        excluded = False
                        for pattern in exclude:
                            if fnmatch.fnmatch(filename, pattern):
                                excluded = True
                                break

                        if excluded:
                            continue

                        # Check name pattern
                        if name_pattern and not fnmatch.fnmatch(filename, name_pattern):
                            continue

                        file_path = Path(root) / filename
                        results.append(str(file_path.relative_to(cwd)))

                        if len(results) >= max_results:
                            return results

        return results


@dataclass
class FindToolInput:
    """Input for find tool."""

    paths: list[str] | None = None
    name_pattern: str | None = None
    exclude: list[str] | None = None
    max_results: int = 100


@dataclass
class FindToolDetails:
    """Details from find tool execution."""

    result_count: int
    truncated: bool = False


@dataclass
class FindToolOptions:
    """Options for find tool."""

    operations: FindOperations | None = None


class FindTool:
    """Find tool for finding files."""

    def __init__(self, cwd: str, options: FindToolOptions | None = None):
        self.cwd = cwd
        self.options = options or FindToolOptions()
        self.operations = self.options.operations or LocalFindOperations()

    async def execute(
        self,
        paths: list[str] | None = None,
        name_pattern: str | None = None,
        exclude: list[str] | None = None,
        max_results: int = 100,
        signal: Any = None,
    ) -> dict[str, Any]:
        """Execute the find tool."""
        if signal and hasattr(signal, "aborted") and signal.aborted:
            raise RuntimeError("Operation aborted")

        search_paths = paths or ["."]
        exclude_list = exclude or [".git", "node_modules", "__pycache__", ".venv", "venv"]

        results = await self.operations.find(
            self.cwd,
            {
                "paths": search_paths,
                "name_pattern": name_pattern,
                "exclude": exclude_list,
                "max_results": max_results + 1,  # Check if there are more
            },
        )

        truncated = len(results) > max_results
        if truncated:
            results = results[:max_results]

        # Format results
        if not results:
            content_text = "No files found"
            if name_pattern:
                content_text += f" matching pattern: {name_pattern}"
        else:
            content_text = "\n".join(sorted(results))
            if truncated:
                content_text += f"\n\n[Results truncated. Found more than {max_results} files.]"

        content = [{"type": "text", "text": content_text}]
        details = FindToolDetails(result_count=len(results), truncated=truncated)

        return {"content": content, "details": details}


def create_find_tool(cwd: str, options: FindToolOptions | None = None):
    """Create a find tool instance."""
    tool = FindTool(cwd, options)

    async def execute(
        paths: list[str] | None = None,
        name_pattern: str | None = None,
        exclude: list[str] | None = None,
        max_results: int = 100,
        signal: Any = None,
    ):
        return await tool.execute(paths, name_pattern, exclude, max_results, signal)

    return {
        "name": "find",
        "description": (
            "Find files by name pattern. Supports glob patterns like '*.py' or 'test_*.js'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths to search (default: current directory)",
                },
                "name_pattern": {
                    "type": "string",
                    "description": "Glob pattern for file names (e.g., '*.py')",
                },
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Patterns for directories/files to exclude",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 100)",
                },
            },
            "required": [],
        },
        "execute": execute,
    }


def create_find_tool_definition(cwd: str, options: FindToolOptions | None = None) -> dict[str, Any]:
    """Create a find tool definition for the agent."""
    return create_find_tool(cwd, options)


find_tool_definition = create_find_tool_definition(Path.cwd())
find_tool = find_tool_definition
