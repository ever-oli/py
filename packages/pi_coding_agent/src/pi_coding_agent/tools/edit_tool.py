"""Edit tool implementation for editing file contents with targeted replacements."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class EditOperations(Protocol):
    """Pluggable operations for the edit tool."""

    async def read_file(self, absolute_path: str) -> bytes:
        """Read file contents as bytes."""
        ...

    async def write_file(self, absolute_path: str, content: str) -> None:
        """Write content to a file."""
        ...

    async def access(self, absolute_path: str) -> None:
        """Check if file is readable and writable (throw if not)."""
        ...


class LocalEditOperations:
    """Default local filesystem operations for edit tool."""

    async def read_file(self, absolute_path: str) -> bytes:
        from aiofiles import open as aio_open

        async with aio_open(absolute_path, "rb") as f:
            return await f.read()

    async def write_file(self, absolute_path: str, content: str) -> None:
        from aiofiles import open as aio_open

        async with aio_open(absolute_path, "w", encoding="utf-8") as f:
            await f.write(content)

    async def access(self, absolute_path: str) -> None:
        import os

        if not Path(absolute_path).exists():
            raise FileNotFoundError(f"File not found: {absolute_path}")
        if not os.access(absolute_path, os.R_OK | os.W_OK):
            raise PermissionError(f"Permission denied: {absolute_path}")


@dataclass
class Edit:
    """A single edit operation."""

    old_text: str
    new_text: str


@dataclass
class EditToolInput:
    """Input for edit tool."""

    path: str
    edits: list[Edit]


@dataclass
class EditToolDetails:
    """Details from edit tool execution."""

    diff: str
    first_changed_line: int | None = None


@dataclass
class EditToolOptions:
    """Options for edit tool."""

    operations: EditOperations | None = None


def normalize_to_lf(content: str) -> str:
    """Normalize line endings to LF."""
    return content.replace("\r\n", "\n").replace("\r", "\n")


def detect_line_ending(content: str) -> str:
    """Detect the line ending style of the content."""
    if "\r\n" in content:
        return "\r\n"
    elif "\r" in content:
        return "\r"
    return "\n"


def strip_bom(content: str) -> str:
    """Strip UTF-8 BOM from content if present."""
    if content.startswith("\ufeff"):
        return content[1:]
    return content


def generate_diff_string(original: str, modified: str, path: str = "file") -> str:
    """Generate a unified diff between original and modified content."""
    import difflib

    original_lines = original.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)

    # Ensure lines end with newline for diff
    if original_lines and not original_lines[-1].endswith("\n"):
        original_lines[-1] += "\n"
    if modified_lines and not modified_lines[-1].endswith("\n"):
        modified_lines[-1] += "\n"

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )

    return "".join(diff)


def apply_edits_to_normalized_content(
    normalized_content: str,
    edits: list[Edit],
) -> tuple[str, int | None]:
    """Apply edits to normalized content.

    Args:
        normalized_content: Content with LF line endings
        edits: List of edit operations

    Returns:
        Tuple of (modified content, first changed line number or None)
    """
    result = normalized_content
    first_changed_line: int | None = None

    for edit in edits:
        # Find the old text
        index = result.find(edit.old_text)

        if index == -1:
            raise ValueError(f"Could not find text to replace: {edit.old_text[:50]}...")

        # Check for duplicate matches
        second_index = result.find(edit.old_text, index + 1)
        if second_index != -1:
            raise ValueError(
                f"Multiple matches found for: {edit.old_text[:50]}...\n"
                "Text must be unique in the file."
            )

        # Calculate line number of the change
        line_number = result[:index].count("\n") + 1
        if first_changed_line is None or line_number < first_changed_line:
            first_changed_line = line_number

        # Apply the replacement
        result = result[:index] + edit.new_text + result[index + len(edit.old_text) :]

    return result, first_changed_line


def restore_line_endings(content: str, line_ending: str) -> str:
    """Restore line endings to original style."""
    if line_ending == "\n":
        return content
    return content.replace("\n", line_ending)


class EditTool:
    """Edit tool for editing file contents."""

    def __init__(self, cwd: str, options: EditToolOptions | None = None):
        self.cwd = cwd
        self.options = options or EditToolOptions()
        self.operations = self.options.operations or LocalEditOperations()

    async def execute(
        self,
        path: str,
        edits: list[dict[str, str]],
        signal: Any = None,
    ) -> dict[str, Any]:
        """Execute the edit tool.

        Args:
            path: Path to the file to edit
            edits: List of edit dicts with 'oldText' and 'newText' keys
            signal: AbortSignal for cancellation

        Returns:
            Dict with content and details
        """
        if signal and hasattr(signal, "aborted") and signal.aborted:
            raise RuntimeError("Operation aborted")

        absolute_path = resolve_to_cwd(path, self.cwd)

        # Check file access
        await self.operations.access(absolute_path)

        # Read file
        buffer = await self.operations.read_file(absolute_path)
        original_content = buffer.decode("utf-8", errors="replace")

        # Strip BOM and detect line endings
        content = strip_bom(original_content)
        original_line_ending = detect_line_ending(content)
        normalized_content = normalize_to_lf(content)

        # Convert edit dicts to Edit objects
        edit_objects = [Edit(old_text=e["oldText"], new_text=e["newText"]) for e in edits]

        # Validate edits don't overlap
        self._validate_edits(normalized_content, edit_objects)

        # Apply edits
        modified_content, first_changed_line = apply_edits_to_normalized_content(
            normalized_content, edit_objects
        )

        # Restore line endings
        final_content = restore_line_endings(modified_content, original_line_ending)

        # Write back
        await self.operations.write_file(absolute_path, final_content)

        # Generate diff
        diff = generate_diff_string(content, modified_content, path)

        return {
            "content": [{"type": "text", "text": f"Successfully edited {path}"}],
            "details": EditToolDetails(diff=diff, first_changed_line=first_changed_line),
        }

    def _validate_edits(self, content: str, edits: list[Edit]) -> None:
        """Validate that edits don't overlap."""
        used_ranges = []

        for edit in edits:
            start = content.find(edit.old_text)
            if start == -1:
                raise ValueError(f"Could not find text to replace: {edit.old_text[:50]}...")

            end = start + len(edit.old_text)

            # Check for overlap with previous edits
            for used_start, used_end in used_ranges:
                if not (end <= used_start or start >= used_end):
                    raise ValueError(
                        f"Overlapping edits detected. "
                        f"Edit '{edit.old_text[:30]}...' overlaps with another edit."
                    )

            used_ranges.append((start, end))


def resolve_to_cwd(path: str, cwd: str) -> str:
    """Resolve a path relative to cwd."""
    if Path(path).is_absolute():
        return str(Path(path).resolve())
    return str(Path(cwd) / path)


def create_edit_tool(cwd: str, options: EditToolOptions | None = None):
    """Create an edit tool instance."""
    tool = EditTool(cwd, options)

    async def execute(path: str, edits: list[dict[str, str]], signal: Any = None):
        return await tool.execute(path, edits, signal)

    return {
        "name": "edit",
        "description": (
            "Edit a file by replacing exact text. Each edit must match exactly "
            "(including whitespace) and must be unique in the file. "
            "Edits are applied in order and must not overlap."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit (relative or absolute)",
                },
                "edits": {
                    "type": "array",
                    "description": (
                        "One or more targeted replacements. Each edit is matched against "
                        "the original file, not incrementally. Do not include overlapping or nested edits."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "oldText": {
                                "type": "string",
                                "description": (
                                    "Exact text for one targeted replacement. It must be unique "
                                    "in the original file and must not overlap with any other edits[].oldText."
                                ),
                            },
                            "newText": {
                                "type": "string",
                                "description": "Replacement text for this targeted edit.",
                            },
                        },
                        "required": ["oldText", "newText"],
                    },
                },
            },
            "required": ["path", "edits"],
        },
        "execute": execute,
    }


def create_edit_tool_definition(cwd: str, options: EditToolOptions | None = None) -> dict[str, Any]:
    """Create an edit tool definition for the agent."""
    return create_edit_tool(cwd, options)


# Default edit tool using current working directory
edit_tool_definition = create_edit_tool_definition(Path.cwd())
edit_tool = edit_tool_definition
