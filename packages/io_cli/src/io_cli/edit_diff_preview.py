"""Edit diff preview utilities for showing code changes."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FileSnapshot:
    """Snapshot of a file's state before editing."""

    path: str
    content: str
    line_count: int

    @classmethod
    def capture(cls, file_path: str | Path) -> FileSnapshot | None:
        """Capture a snapshot of a file.

        Args:
            file_path: Path to the file

        Returns:
            Snapshot or None if file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            return cls(path=str(path), content="", line_count=0)

        try:
            content = path.read_text()
            return cls(
                path=str(path),
                content=content,
                line_count=len(content.splitlines()),
            )
        except Exception:
            return None


@dataclass
class DiffLine:
    """A single line in a diff."""

    type: str  # 'context', 'add', 'remove'
    old_lineno: int | None
    new_lineno: int | None
    content: str


@dataclass
class FileDiff:
    """Diff between two file states."""

    path: str
    old_line_count: int
    new_line_count: int
    lines: list[DiffLine]

    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return any(line.type in ("add", "remove") for line in self.lines)

    def summary(self) -> str:
        """Get a summary of changes."""
        added = sum(1 for line in self.lines if line.type == "add")
        removed = sum(1 for line in self.lines if line.type == "remove")
        return f"+{added}/-{removed} lines"


def compute_diff(
    old_content: str,
    new_content: str,
    file_path: str = "file",
    context_lines: int = 3,
) -> FileDiff:
    """Compute diff between two file contents.

    Args:
        old_content: Original content
        new_content: New content
        file_path: File path for display
        context_lines: Number of context lines around changes

    Returns:
        FileDiff with changes
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # Normalize line endings for comparison
    old_lines_normalized = [line.rstrip("\n\r") for line in old_lines]
    new_lines_normalized = [line.rstrip("\n\r") for line in new_lines]

    # Generate unified diff
    diff_lines = list(difflib.unified_diff(
        old_lines_normalized,
        new_lines_normalized,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=context_lines,
    ))

    lines: list[DiffLine] = []
    old_lineno = 0
    new_lineno = 0

    for diff_line in diff_lines[2:] if len(diff_lines) > 2 else diff_lines:  # Skip header
        if diff_line.startswith("@@"):
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            parts = diff_line.split(" ")
            old_range = parts[1][1:]  # Remove leading -
            new_range = parts[2][1:]  # Remove leading +

            if "," in old_range:
                old_lineno = int(old_range.split(",")[0])
            else:
                old_lineno = int(old_range)

            if "," in new_range:
                new_lineno = int(new_range.split(",")[0])
            else:
                new_lineno = int(new_range)

        elif diff_line.startswith("-"):
            lines.append(DiffLine(
                type="remove",
                old_lineno=old_lineno,
                new_lineno=None,
                content=diff_line[1:],
            ))
            old_lineno += 1

        elif diff_line.startswith("+"):
            lines.append(DiffLine(
                type="add",
                old_lineno=None,
                new_lineno=new_lineno,
                content=diff_line[1:],
            ))
            new_lineno += 1

        elif diff_line.startswith(" "):
            lines.append(DiffLine(
                type="context",
                old_lineno=old_lineno,
                new_lineno=new_lineno,
                content=diff_line[1:],
            ))
            old_lineno += 1
            new_lineno += 1

        else:
            # Context line without prefix
            lines.append(DiffLine(
                type="context",
                old_lineno=old_lineno,
                new_lineno=new_lineno,
                content=diff_line,
            ))
            old_lineno += 1
            new_lineno += 1

    return FileDiff(
        path=file_path,
        old_line_count=len(old_lines),
        new_line_count=len(new_lines),
        lines=lines,
    )


def format_diff_line(line: DiffLine, use_color: bool = True) -> str:
    """Format a single diff line for display.

    Args:
        line: DiffLine to format
        use_color: Whether to use ANSI colors

    Returns:
        Formatted line string
    """
    if line.type == "context":
        prefix = " "
        color_code = ""
        reset_code = ""
    elif line.type == "add":
        prefix = "+"
        color_code = "\033[92m" if use_color else ""  # Green
        reset_code = "\033[0m" if use_color else ""
    elif line.type == "remove":
        prefix = "-"
        color_code = "\033[91m" if use_color else ""  # Red
        reset_code = "\033[0m" if use_color else ""
    else:
        prefix = "?"
        color_code = ""
        reset_code = ""

    return f"{color_code}{prefix}{line.content}{reset_code}"


def format_diff(diff: FileDiff, use_color: bool = True, max_lines: int = 100) -> str:
    """Format a FileDiff for display.

    Args:
        diff: FileDiff to format
        use_color: Whether to use ANSI colors
        max_lines: Maximum number of lines to show

    Returns:
        Formatted diff string
    """
    lines = []

    header = f"--- {diff.path} ({diff.old_line_count} lines)"
    if use_color:
        header = f"\033[1m{header}\033[0m"  # Bold
    lines.append(header)

    if diff.has_changes():
        lines.append(f"+++ {diff.path} ({diff.new_line_count} lines)")
    else:
        lines.append("(no changes)")
        return "\n".join(lines)

    # Truncate if too many lines
    diff_lines = diff.lines
    if len(diff_lines) > max_lines:
        half = max_lines // 2
        diff_lines = diff_lines[:half] + [
            DiffLine("context", None, None, f"... ({len(diff.lines) - max_lines} more lines) ...")
        ] + diff_lines[-half:]

    for line in diff_lines:
        lines.append(format_diff_line(line, use_color))

    return "\n".join(lines)


def summarize_diff_lines(diff: FileDiff, max_context: int = 3) -> list[str]:
    """Summarize diff lines for compact display.

    Args:
        diff: FileDiff to summarize
        max_context: Maximum context lines to include

    Returns:
        List of summary strings
    """
    if not diff.has_changes():
        return [f"{diff.path}: no changes"]

    added = sum(1 for line in diff.lines if line.type == "add")
    removed = sum(1 for line in diff.lines if line.type == "remove")

    summary = [f"{diff.path}: +{added}/-{removed} lines"]

    # Show sample of changes
    changes = [line for line in diff.lines if line.type in ("add", "remove")]
    if changes:
        summary.append("Changes:")
        for line in changes[:max_context]:
            prefix = "+" if line.type == "add" else "-"
            content = line.content[:60] + "..." if len(line.content) > 60 else line.content
            summary.append(f"  {prefix} {content}")
        if len(changes) > max_context:
            summary.append(f"  ... and {len(changes) - max_context} more")

    return summary


class EditPreviewManager:
    """Manages file snapshots and diff generation for edits."""

    _snapshots: dict[str, FileSnapshot]

    def __init__(self):
        """Initialize the preview manager."""
        self._snapshots = {}

    def capture_snapshot(self, file_path: str | Path) -> FileSnapshot | None:
        """Capture a snapshot of a file before editing.

        Args:
            file_path: Path to the file

        Returns:
            Captured snapshot
        """
        snapshot = FileSnapshot.capture(file_path)
        if snapshot:
            self._snapshots[str(file_path)] = snapshot
        return snapshot

    def get_snapshot(self, file_path: str | Path) -> FileSnapshot | None:
        """Get a previously captured snapshot."""
        return self._snapshots.get(str(file_path))

    def compute_edit_diff(
        self,
        file_path: str | Path,
        new_content: str,
    ) -> FileDiff:
        """Compute diff between snapshot and new content.

        Args:
            file_path: Path to the file
            new_content: New file content

        Returns:
            FileDiff showing changes
        """
        snapshot = self.get_snapshot(file_path)
        old_content = snapshot.content if snapshot else ""

        return compute_diff(old_content, new_content, str(file_path))

    def clear_snapshot(self, file_path: str | Path | None = None) -> None:
        """Clear snapshot(s).

        Args:
            file_path: Specific file to clear, or None to clear all
        """
        if file_path is None:
            self._snapshots.clear()
        else:
            self._snapshots.pop(str(file_path), None)


# Convenience functions
def capture_local_edit_snapshot(file_path: str | Path) -> FileSnapshot | None:
    """Capture a snapshot of a file before editing.

    This is the main function that was being imported in the error trace.

    Args:
        file_path: Path to the file

    Returns:
        Captured snapshot or None
    """
    return FileSnapshot.capture(file_path)


def compute_file_diff(
    file_path: str | Path,
    old_content: str | None = None,
    new_content: str | None = None,
) -> FileDiff:
    """Compute diff for a file.

    Args:
        file_path: Path to the file
        old_content: Original content (read from file if None)
        new_content: New content (read from file if None)

    Returns:
        FileDiff showing changes
    """
    path = Path(file_path)

    if old_content is None:
        old_content = path.read_text() if path.exists() else ""

    if new_content is None:
        new_content = path.read_text() if path.exists() else ""

    return compute_diff(old_content, new_content, str(path))
