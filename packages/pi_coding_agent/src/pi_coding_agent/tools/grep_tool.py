"""Grep tool implementation for searching file contents."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from re import Pattern
from typing import Any, Protocol

# Cache for compiled patterns with their flags
_pattern_cache: dict[tuple[str, int], Pattern[str]] = {}


def _get_compiled_pattern(pattern: str, flags: int) -> Pattern[str]:
    """Get a compiled regex pattern with caching."""
    cache_key = (pattern, flags)
    if cache_key not in _pattern_cache:
        _pattern_cache[cache_key] = re.compile(pattern, flags)
    return _pattern_cache[cache_key]


def clear_pattern_cache() -> None:
    """Clear the regex pattern cache."""
    _pattern_cache.clear()


class GrepOperations(Protocol):
    """Pluggable operations for the grep tool."""

    async def grep(
        self,
        pattern: str,
        cwd: str,
        options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Search for pattern in files."""
        ...


class LocalGrepOperations:
    """Default local filesystem operations for grep tool."""

    async def grep(
        self,
        pattern: str,
        cwd: str,
        options: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Search for pattern in files using Python."""
        paths = options.get("paths", ["."])
        include = options.get("include")
        exclude = options.get("exclude", [])
        case_sensitive = options.get("case_sensitive", False)
        max_results = options.get("max_results", 100)

        results: list[dict[str, Any]] = []
        flags = 0 if case_sensitive else re.IGNORECASE

        # Compile pattern once with caching
        try:
            regex = _get_compiled_pattern(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e

        # Pre-compile exclude patterns
        compiled_excludes: list[Pattern[str]] = []
        for exclude_pattern in exclude:
            try:
                compiled_excludes.append(_get_compiled_pattern(exclude_pattern, 0))
            except re.error:
                # Invalid regex, treat as literal string
                pass

        for path in paths:
            search_path = Path(cwd) / path

            files = [search_path] if search_path.is_file() else search_path.rglob("*")

            for file_path in files:
                if not file_path.is_file():
                    continue

                # Check include pattern
                if include and not fnmatch.fnmatch(file_path.name, include):
                    continue

                # Check exclude patterns (fast path)
                excluded = False
                file_name = file_path.name
                rel_path = str(file_path.relative_to(search_path if search_path.is_dir() else cwd))

                for exclude_pattern in exclude:
                    if fnmatch.fnmatch(file_name, exclude_pattern):
                        excluded = True
                        break
                    if exclude_pattern in rel_path:
                        excluded = True
                        break

                if excluded:
                    continue

                # Search file content using buffered reading
                try:
                    # Read in chunks for memory efficiency
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(
                                    {
                                        "path": str(file_path.relative_to(cwd)),
                                        "line": line_num,
                                        "content": line.rstrip("\n\r"),
                                    }
                                )

                                if len(results) >= max_results:
                                    return results
                except OSError:
                    continue

        return results


@dataclass
class GrepToolInput:
    """Input for grep tool."""

    pattern: str
    paths: list[str] | None = None
    include: str | None = None
    exclude: list[str] | None = None
    case_sensitive: bool = False
    max_results: int = 100


@dataclass
class GrepToolDetails:
    """Details from grep tool execution."""

    result_count: int
    truncated: bool = False


@dataclass
class GrepToolOptions:
    """Options for grep tool."""

    operations: GrepOperations | None = None


class GrepTool:
    """Grep tool for searching file contents."""

    def __init__(self, cwd: str, options: GrepToolOptions | None = None):
        self.cwd = cwd
        self.options = options or GrepToolOptions()
        self.operations = self.options.operations or LocalGrepOperations()

    async def execute(
        self,
        pattern: str,
        paths: list[str] | None = None,
        include: str | None = None,
        exclude: list[str] | None = None,
        case_sensitive: bool = False,
        max_results: int = 100,
        signal: Any = None,
    ) -> dict[str, Any]:
        """Execute the grep tool."""
        if signal and hasattr(signal, "aborted") and signal.aborted:
            raise RuntimeError("Operation aborted")

        search_paths = paths or ["."]
        exclude_list = exclude or [".git", "node_modules", "__pycache__", ".venv", "venv"]

        results = await self.operations.grep(
            pattern,
            self.cwd,
            {
                "paths": search_paths,
                "include": include,
                "exclude": exclude_list,
                "case_sensitive": case_sensitive,
                "max_results": max_results + 1,  # Check if there are more
            },
        )

        truncated = len(results) > max_results
        if truncated:
            results = results[:max_results]

        # Format results
        if not results:
            content_text = f"No matches found for pattern: {pattern}"
        else:
            lines = [f"{r['path']}:{r['line']}:{r['content']}" for r in results]
            content_text = "\n".join(lines)
            if truncated:
                content_text += f"\n\n[Results truncated. Found more than {max_results} matches.]"

        content = [{"type": "text", "text": content_text}]
        details = GrepToolDetails(result_count=len(results), truncated=truncated)

        return {"content": content, "details": details}


def create_grep_tool(cwd: str, options: GrepToolOptions | None = None):
    """Create a grep tool instance."""
    tool = GrepTool(cwd, options)

    async def execute(
        pattern: str,
        paths: list[str] | None = None,
        include: str | None = None,
        exclude: list[str] | None = None,
        case_sensitive: bool = False,
        max_results: int = 100,
        signal: Any = None,
    ):
        return await tool.execute(
            pattern, paths, include, exclude, case_sensitive, max_results, signal
        )

    return {
        "name": "grep",
        "description": (
            "Search for a regex pattern in file contents. "
            "Returns matching lines with file path and line number."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Paths to search (default: current directory)",
                },
                "include": {
                    "type": "string",
                    "description": "Glob pattern for files to include (e.g., '*.py')",
                },
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Patterns for files/directories to exclude",
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case-sensitive search (default: false)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default: 100)",
                },
            },
            "required": ["pattern"],
        },
        "execute": execute,
    }


def create_grep_tool_definition(cwd: str, options: GrepToolOptions | None = None) -> dict[str, Any]:
    """Create a grep tool definition for the agent."""
    return create_grep_tool(cwd, options)


grep_tool_definition = create_grep_tool_definition(Path.cwd())
grep_tool = grep_tool_definition
