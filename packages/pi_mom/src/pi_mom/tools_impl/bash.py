"""Bash tool for Mom."""

import secrets
import tempfile
from pathlib import Path

from ..sandbox import Executor
from . import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES, format_size, truncate_tail


def create_bash_tool(executor: Executor) -> dict:
    """Create the bash tool."""

    async def execute(label: str, command: str, timeout: int | None = None) -> dict:
        """Execute a bash command."""
        result = await executor.exec(command, timeout)

        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr

        total_bytes = len(output.encode("utf-8"))

        # Write to temp file if too large
        temp_path = None
        if total_bytes > DEFAULT_MAX_BYTES:
            temp_id = secrets.token_hex(8)
            temp_path = Path(tempfile.gettempdir()) / f"mom-bash-{temp_id}.log"
            with open(temp_path, "w") as f:
                f.write(output)

        # Apply tail truncation
        truncation = truncate_tail(output)
        output_text = truncation.content or "(no output)"

        if truncation.truncated:
            start_line = truncation.total_lines - truncation.output_lines + 1
            end_line = truncation.total_lines

            if truncation.last_line_partial:
                last_line_size = format_size(len(output.split("\n")[-1].encode("utf-8")))
                output_text += f"\n\n[Showing last {format_size(truncation.output_bytes)} of line {end_line} (line is {last_line_size}). Full output: {temp_path}]"
            elif truncation.truncated_by == "lines":
                output_text += f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines}. Full output: {temp_path}]"
            else:
                output_text += f"\n\n[Showing lines {start_line}-{end_line} of {truncation.total_lines} ({format_size(DEFAULT_MAX_BYTES)} limit). Full output: {temp_path}]"

        if result.code != 0:
            raise Exception(f"{output_text}\n\nCommand exited with code {result.code}".strip())

        return {
            "content": [{"type": "text", "text": output_text}],
            "details": {"truncation": truncation, "full_output_path": temp_path}
            if truncation.truncated
            else None,
        }

    return {
        "name": "bash",
        "description": f"Execute a bash command. Output truncated to last {DEFAULT_MAX_LINES} lines or {DEFAULT_MAX_BYTES // 1024}KB.",
        "parameters": {
            "label": {"type": "string", "description": "Brief description"},
            "command": {"type": "string", "description": "Bash command"},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "optional": True},
        },
        "execute": execute,
    }


# Import at end
