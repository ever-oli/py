"""Read tool implementation for reading file contents."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    pass

# Image magic numbers for detection
IMAGE_MAGIC = {
    b'\xff\xd8\xff': "image/jpeg",
    b'\x89PNG\r\n\x1a\n': "image/png",
    b'GIF87a': "image/gif",
    b'GIF89a': "image/gif",
    b'RIFF': "image/webp",  # Need to check bytes 8-12 for WEBP
    b'BM': "image/bmp",
}


def detect_image_mime_type_sync(header: bytes) -> str | None:
    """Detect image MIME type from file header (synchronous)."""
    # Check for WebP special case
    if header.startswith(b'RIFF') and len(header) >= 12 and header[8:12] == b'WEBP':
        return "image/webp"
    
    # Check other formats
    for magic, mime_type in IMAGE_MAGIC.items():
        if magic != b'RIFF' and header.startswith(magic):
            return mime_type
    
    return None


class ReadOperations(Protocol):
    """Pluggable operations for the read tool.

    Override these to delegate file reading to remote systems (for example SSH).
    """

    async def read_file(self, absolute_path: str) -> bytes:
        """Read file contents as bytes."""
        ...

    async def access(self, absolute_path: str) -> None:
        """Check if file is readable (throw if not)."""
        ...

    async def detect_image_mime_type(self, absolute_path: str) -> str | None:
        """Detect image MIME type, return None for non-images."""
        ...


class LocalReadOperations:
    """Default local filesystem operations for read tool."""

    async def read_file(self, absolute_path: str) -> bytes:
        """Read file contents as bytes using memory-efficient streaming."""
        from aiofiles import open as aio_open
        async with aio_open(absolute_path, "rb") as f:
            return await f.read()

    async def access(self, absolute_path: str) -> None:
        """Check if file exists and is readable."""
        import os
        if not Path(absolute_path).exists():
            raise FileNotFoundError(f"File not found: {absolute_path}")
        if not os.access(absolute_path, os.R_OK):
            raise PermissionError(f"Permission denied: {absolute_path}")

    async def detect_image_mime_type(self, absolute_path: str) -> str | None:
        """Detect if file is an image and return MIME type."""
        from aiofiles import open as aio_open
        try:
            async with aio_open(absolute_path, "rb") as f:
                header = await f.read(16)
            return detect_image_mime_type_sync(header)
        except Exception:
            return None


@dataclass
class ReadToolDetails:
    """Details from read tool execution."""
    truncation: TruncationResult | None = None


@dataclass
class ReadToolInput:
    """Input for read tool."""
    path: str
    offset: int | None = None
    limit: int | None = None


@dataclass
class ReadToolOptions:
    """Options for read tool."""
    auto_resize_images: bool = True
    operations: ReadOperations | None = None


def resolve_read_path(path: str, cwd: str) -> str:
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


# Default limits (matching truncate.py)
DEFAULT_MAX_LINES = 2000
DEFAULT_MAX_BYTES = 50 * 1024  # 50KB


@dataclass
class TruncationResult:
    """Result of a truncation operation."""
    content: str
    truncated: bool
    total_lines: int
    output_lines: int
    truncated_by: str | None = None
    max_lines: int | None = None
    max_bytes: int | None = None
    first_line_exceeds_limit: bool = False


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


def format_size(bytes_size: int) -> str:
    """Format a byte size as human-readable string."""
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size // 1024}KB"
    else:
        return f"{bytes_size // (1024 * 1024)}MB"


class ReadTool:
    """Read tool for reading file contents."""

    def __init__(self, cwd: str, options: ReadToolOptions | None = None):
        self.cwd = cwd
        self.options = options or ReadToolOptions()
        self.operations = self.options.operations or LocalReadOperations()

    async def execute(
        self,
        path: str,
        offset: int | None = None,
        limit: int | None = None,
        signal: Any = None,
    ) -> dict[str, Any]:
        """Execute the read tool.

        Args:
            path: Path to the file to read
            offset: Line number to start reading from (1-indexed)
            limit: Maximum number of lines to read
            signal: AbortSignal for cancellation

        Returns:
            Dict with content and details
        """
        absolute_path = resolve_read_path(path, self.cwd)

        # Check if aborted
        if signal and hasattr(signal, 'aborted') and signal.aborted:
            raise RuntimeError("Operation aborted")

        # Check if file exists and is readable
        await self.operations.access(absolute_path)

        # Detect if it's an image
        mime_type = await self.operations.detect_image_mime_type(absolute_path)

        if mime_type:
            # Read image as binary
            buffer = await self.operations.read_file(absolute_path)
            base64_data = base64.b64encode(buffer).decode("ascii")

            content: list[dict[str, Any]] = [
                {"type": "text", "text": f"Read image file [{mime_type}]"},
                {"type": "image", "data": base64_data, "mimeType": mime_type},
            ]

            return {"content": content, "details": None}

        # Read text content with memory-efficient line-by-line reading
        from aiofiles import open as aio_open
        
        all_lines: list[str] = []
        total_file_lines = 0
        
        async with aio_open(absolute_path, "r", encoding="utf-8", errors="replace") as f:
            async for line in f:
                total_file_lines += 1
                # Only store lines we might need (optimization for very large files)
                # We collect all lines for now, but could be optimized further
                all_lines.append(line.rstrip("\n"))

        # Apply offset if specified (1-indexed to 0-indexed)
        start_line = max(0, (offset or 1) - 1)
        start_line_display = start_line + 1

        # Check if offset is out of bounds
        if start_line >= len(all_lines):
            raise ValueError(f"Offset {offset} is beyond end of file ({len(all_lines)} lines total)")

        # Apply limit if specified by user
        if limit is not None:
            end_line = min(start_line + limit, len(all_lines))
            selected_content = "\n".join(all_lines[start_line:end_line])
            user_limited_lines = end_line - start_line
        else:
            selected_content = "\n".join(all_lines[start_line:])
            user_limited_lines = None

        # Apply truncation
        truncation = truncate_head(selected_content)

        if truncation.first_line_exceeds_limit:
            # First line alone exceeds byte limit
            first_line_size = format_size(len(all_lines[start_line].encode("utf-8")))
            output_text = (
                f"[Line {start_line_display} is {first_line_size}, exceeds {format_size(DEFAULT_MAX_BYTES)} limit. "
                f"Use bash: sed -n '{start_line_display}p' {path} | head -c {DEFAULT_MAX_BYTES}]"
            )
            details = ReadToolDetails(truncation=truncation)
        elif truncation.truncated:
            # Truncation occurred
            end_line_display = start_line_display + truncation.output_lines - 1
            next_offset = end_line_display + 1
            output_text = truncation.content
            if truncation.truncated_by == "lines":
                output_text += f"\n\n[Showing lines {start_line_display}-{end_line_display} of {total_file_lines}. Use offset={next_offset} to continue.]"
            else:
                output_text += f"\n\n[Showing lines {start_line_display}-{end_line_display} of {total_file_lines} ({format_size(DEFAULT_MAX_BYTES)} limit). Use offset={next_offset} to continue.]"
            details = ReadToolDetails(truncation=truncation)
        elif user_limited_lines is not None and start_line + user_limited_lines < len(all_lines):
            # User-specified limit stopped early, but file has more content
            remaining = len(all_lines) - (start_line + user_limited_lines)
            next_offset = start_line + user_limited_lines + 1
            output_text = f"{truncation.content}\n\n[{remaining} more lines in file. Use offset={next_offset} to continue.]"
            details = None
        else:
            # No truncation
            output_text = truncation.content
            details = None

        content = [{"type": "text", "text": output_text}]

        return {"content": content, "details": details}


def create_read_tool(cwd: str, options: ReadToolOptions | None = None):
    """Create a read tool instance."""
    tool = ReadTool(cwd, options)

    async def execute(path: str, offset: int | None = None, limit: int | None = None, signal: Any = None):
        return await tool.execute(path, offset, limit, signal)

    return {
        "name": "read",
        "description": (
            f"Read the contents of a file. Supports text files and images (jpg, png, gif, webp). "
            f"Images are sent as attachments. For text files, output is truncated to {DEFAULT_MAX_LINES} lines "
            f"or {DEFAULT_MAX_BYTES // 1024}KB (whichever is hit first). Use offset/limit for large files. "
            f"When you need the full file, continue with offset until complete."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read (relative or absolute)"},
                "offset": {"type": "integer", "description": "Line number to start reading from (1-indexed)"},
                "limit": {"type": "integer", "description": "Maximum number of lines to read"},
            },
            "required": ["path"],
        },
        "execute": execute,
    }


def create_read_tool_definition(cwd: str, options: ReadToolOptions | None = None) -> dict[str, Any]:
    """Create a read tool definition for the agent."""
    return create_read_tool(cwd, options)


# Default read tool using current working directory
read_tool_definition = create_read_tool_definition(Path.cwd())
read_tool = read_tool_definition