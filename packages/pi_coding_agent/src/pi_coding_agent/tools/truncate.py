"""Truncation utilities for file content handling."""

from dataclasses import dataclass
from typing import Literal

# Default limits
DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024  # 50KB


@dataclass
class TruncationResult:
    """Result of a truncation operation."""

    content: str
    truncated: bool
    total_lines: int
    output_lines: int
    truncated_by: Literal["lines", "bytes"] | None = None
    max_lines: int | None = None
    max_bytes: int | None = None
    first_line_exceeds_limit: bool = False


@dataclass
class TruncationOptions:
    """Options for truncation operations."""

    max_lines: int = DEFAULT_MAX_LINES
    max_bytes: int = DEFAULT_MAX_BYTES


def format_size(bytes_size: int) -> str:
    """Format a byte size as human-readable string."""
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size // 1024}KB"
    else:
        return f"{bytes_size // (1024 * 1024)}MB"


def truncate_head(
    content: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TruncationResult:
    """Truncate content from the head (beginning).

    Keeps the beginning of the content up to the limits.

    Args:
        content: Content to truncate
        max_lines: Maximum number of lines to keep
        max_bytes: Maximum bytes to keep

    Returns:
        Truncation result with metadata
    """
    if not content:
        return TruncationResult(
            content="",
            truncated=False,
            total_lines=0,
            output_lines=0,
        )

    lines = content.split("\n")
    total_lines = len(lines)

    # Check if first line alone exceeds byte limit
    first_line_bytes = len(lines[0].encode("utf-8"))
    if first_line_bytes > max_bytes:
        return TruncationResult(
            content=lines[0],
            truncated=True,
            total_lines=total_lines,
            output_lines=1,
            truncated_by="bytes",
            max_bytes=max_bytes,
            first_line_exceeds_limit=True,
        )

    # Apply line limit
    line_limited = lines[:max_lines]
    line_limited_content = "\n".join(line_limited)

    # Apply byte limit
    content_bytes = line_limited_content.encode("utf-8")
    if len(content_bytes) <= max_bytes:
        # No byte truncation needed
        truncated = len(lines) > max_lines
        return TruncationResult(
            content=line_limited_content,
            truncated=truncated,
            total_lines=total_lines,
            output_lines=len(line_limited),
            truncated_by="lines" if truncated else None,
            max_lines=max_lines if truncated else None,
        )

    # Byte truncation needed
    # Find how many lines fit within the byte limit
    current_bytes = 0
    output_line_count = 0
    result_lines = []

    for line in line_limited:
        line_bytes = len(line.encode("utf-8"))
        # Add 1 for newline (except for first line)
        additional_bytes = line_bytes if output_line_count == 0 else line_bytes + 1

        if current_bytes + additional_bytes > max_bytes:
            break

        result_lines.append(line)
        current_bytes += additional_bytes
        output_line_count += 1

    return TruncationResult(
        content="\n".join(result_lines),
        truncated=True,
        total_lines=total_lines,
        output_lines=output_line_count,
        truncated_by="bytes",
        max_bytes=max_bytes,
    )


def truncate_tail(
    content: str,
    max_lines: int = DEFAULT_MAX_LINES,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> TruncationResult:
    """Truncate content from the tail (end).

    Keeps the end of the content up to the limits.

    Args:
        content: Content to truncate
        max_lines: Maximum number of lines to keep
        max_bytes: Maximum bytes to keep

    Returns:
        Truncation result with metadata
    """
    if not content:
        return TruncationResult(
            content="",
            truncated=False,
            total_lines=0,
            output_lines=0,
        )

    lines = content.split("\n")
    total_lines = len(lines)

    # Apply byte limit first to get approximate content
    content_bytes = content.encode("utf-8")
    if len(content_bytes) <= max_bytes and total_lines <= max_lines:
        # No truncation needed
        return TruncationResult(
            content=content,
            truncated=False,
            total_lines=total_lines,
            output_lines=total_lines,
        )

    # Start from the end and work backwards
    current_bytes = 0
    lines_kept = 0

    for line in reversed(lines):
        line_bytes = len(line.encode("utf-8"))
        # Add 1 for newline (except for last line which is at the beginning when reversed)
        additional_bytes = line_bytes if lines_kept == 0 else line_bytes + 1

        if current_bytes + additional_bytes > max_bytes or lines_kept >= max_lines:
            break

        current_bytes += additional_bytes
        lines_kept += 1

    result_lines = lines[-lines_kept:]
    return TruncationResult(
        content="\n".join(result_lines),
        truncated=True,
        total_lines=total_lines,
        output_lines=lines_kept,
        truncated_by="bytes" if lines_kept < min(total_lines, max_lines) else "lines",
        max_bytes=max_bytes,
        max_lines=max_lines,
    )


def truncate_line(content: str, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    """Truncate a single line to max bytes.

    Args:
        content: Line content
        max_bytes: Maximum bytes

    Returns:
        Truncated line
    """
    content_bytes = content.encode("utf-8")
    if len(content_bytes) <= max_bytes:
        return content

    # Truncate to byte limit (may cut in middle of multi-byte char)
    truncated = content_bytes[:max_bytes]
    try:
        return truncated.decode("utf-8", errors="ignore")
    except UnicodeDecodeError:
        # Fallback: remove last byte and try again
        return truncated[:-1].decode("utf-8", errors="replace")
