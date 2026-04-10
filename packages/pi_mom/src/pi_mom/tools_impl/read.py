"""Read tool for Mom."""

from pathlib import Path

from ..sandbox import Executor
from . import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES, format_size, truncate_head

IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def is_image_file(file_path: str) -> Optional[str]:
    """Check if file is an image."""
    ext = Path(file_path).suffix.lower()
    return IMAGE_MIME_TYPES.get(ext)


def shell_escape(s: str) -> str:
    """Escape a string for shell."""
    return "'" + s.replace("'", "'\\''") + "'"


def create_read_tool(executor: Executor) -> dict:
    """Create the read tool."""

    async def execute(
        label: str, path: str, offset: int | None = None, limit: int | None = None
    ) -> dict:
        """Read a file."""
        mime_type = is_image_file(path)

        if mime_type:
            # Read as image (binary)
            result = await executor.exec(f"base64 < {shell_escape(path)}")
            if result.code != 0:
                raise Exception(result.stderr or f"Failed to read file: {path}")
            base64 = result.stdout.replace("\\s", "")

            return {
                "content": [
                    {"type": "text", "text": f"Read image file [{mime_type}]"},
                    {"type": "image", "data": base64, "mime_type": mime_type},
                ],
                "details": None,
            }

        # Get total line count
        count_result = await executor.exec(f"wc -l < {shell_escape(path)}")
        if count_result.code != 0:
            raise Exception(count_result.stderr or f"Failed to read file: {path}")
        total_file_lines = int(count_result.stdout.strip()) + 1

        start_line = max(1, offset) if offset else 1

        if start_line > total_file_lines:
            raise Exception(
                f"Offset {offset} is beyond end of file ({total_file_lines} lines total)"
            )

        # Read content with offset
        if start_line == 1:
            cmd = f"cat {shell_escape(path)}"
        else:
            cmd = f"tail -n +{start_line} {shell_escape(path)}"

        result = await executor.exec(cmd)
        if result.code != 0:
            raise Exception(result.stderr or f"Failed to read file: {path}")

        selected_content = result.stdout
        user_limited_lines = None

        # Apply user limit
        if limit is not None:
            lines = selected_content.split("\n")
            end_line = min(limit, len(lines))
            selected_content = "\n".join(lines[:end_line])
            user_limited_lines = end_line

        # Apply truncation
        truncation = truncate_head(selected_content)

        if truncation.first_line_exceeds_limit:
            first_line_size = format_size(len(selected_content.split("\n")[0].encode("utf-8")))
            output_text = f"[Line {start_line} is {first_line_size}, exceeds {format_size(DEFAULT_MAX_BYTES)} limit. Use bash: sed -n '{start_line}p' {path} | head -c {DEFAULT_MAX_BYTES}]"
            details = {"truncation": truncation}
        elif truncation.truncated:
            end_line_display = start_line + truncation.output_lines - 1
            next_offset = end_line_display + 1

            output_text = truncation.content
            if truncation.truncated_by == "lines":
                output_text += f"\n\n[Showing lines {start_line}-{end_line_display} of {total_file_lines}. Use offset={next_offset} to continue]"
            else:
                output_text += f"\n\n[Showing lines {start_line}-{end_line_display} of {total_file_lines} ({format_size(DEFAULT_MAX_BYTES)} limit). Use offset={next_offset} to continue]"
            details = {"truncation": truncation}
        elif user_limited_lines is not None:
            lines_from_start = start_line - 1 + user_limited_lines
            if lines_from_start < total_file_lines:
                remaining = total_file_lines - lines_from_start
                next_offset = start_line + user_limited_lines
                output_text = truncation.content
                output_text += (
                    f"\n\n[{remaining} more lines in file. Use offset={next_offset} to continue]"
                )
            else:
                output_text = truncation.content
            details = None
        else:
            output_text = truncation.content
            details = None

        return {"content": [{"type": "text", "text": output_text}], "details": details}

    return {
        "name": "read",
        "description": f"Read file contents. Images sent as attachments. Text truncated to {DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_BYTES // 1024}KB.",
        "parameters": {
            "label": {"type": "string", "description": "Brief description"},
            "path": {"type": "string", "description": "Path to file"},
            "offset": {
                "type": "integer",
                "description": "Line to start from (1-indexed)",
                "optional": True,
            },
            "limit": {"type": "integer", "description": "Max lines to read", "optional": True},
        },
        "execute": execute,
    }


# Import at end
