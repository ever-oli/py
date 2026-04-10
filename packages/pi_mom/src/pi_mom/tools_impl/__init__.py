"""Tool implementations for Mom."""

DEFAULT_MAX_LINES = 100
DEFAULT_MAX_BYTES = 50 * 1024


def format_size(bytes_val: int) -> str:
    """Format bytes as human readable string."""
    if bytes_val < 1024:
        return f"{bytes_val}B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val // 1024}KB"
    return f"{bytes_val // (1024 * 1024)}MB"


class TruncationResult:
    """Result of truncation operation."""

    def __init__(
        self,
        content: str,
        truncated: bool = False,
        total_lines: int = 0,
        output_lines: int = 0,
        truncated_by: str = "",
        first_line_exceeds_limit: bool = False,
        last_line_partial: bool = False,
    ):
        self.content = content
        self.truncated = truncated
        self.total_lines = total_lines
        self.output_lines = output_lines
        self.truncated_by = truncated_by
        self.first_line_exceeds_limit = first_line_exceeds_limit
        self.last_line_partial = last_line_partial


def truncate_tail(
    text: str, max_lines: int = DEFAULT_MAX_LINES, max_bytes: int = DEFAULT_MAX_BYTES
) -> TruncationResult:
    """Truncate text from the tail (keep last lines)."""
    lines = text.split("\n")
    total_lines = len(lines)

    # Check byte limit
    text_bytes = text.encode("utf-8")
    if len(text_bytes) <= max_bytes and len(lines) <= max_lines:
        return TruncationResult(text, False, total_lines, total_lines)

    # Truncate by lines first
    if len(lines) > max_lines:
        kept = lines[-max_lines:]
        result = "\n".join(kept)
        return TruncationResult(result, True, total_lines, len(kept), "lines")

    # Truncate by bytes
    kept_bytes = text_bytes[-max_bytes:]
    result = kept_bytes.decode("utf-8", errors="replace")
    output_lines = len(result.split("\n"))
    return TruncationResult(result, True, total_lines, output_lines, "bytes")


def truncate_head(
    text: str, max_lines: int = DEFAULT_MAX_LINES, max_bytes: int = DEFAULT_MAX_BYTES
) -> TruncationResult:
    """Truncate text from the head (keep first lines)."""
    lines = text.split("\n")
    total_lines = len(lines)

    # Check if first line exceeds limit
    if lines:
        first_line_bytes = lines[0].encode("utf-8")
        if len(first_line_bytes) > max_bytes:
            return TruncationResult(
                "", True, total_lines, 0, "bytes", first_line_exceeds_limit=True
            )

    # Check byte limit
    text_bytes = text.encode("utf-8")
    if len(text_bytes) <= max_bytes and len(lines) <= max_lines:
        return TruncationResult(text, False, total_lines, total_lines)

    # Truncate by lines first
    if len(lines) > max_lines:
        kept = lines[:max_lines]
        result = "\n".join(kept)
        return TruncationResult(result, True, total_lines, len(kept), "lines")

    # Truncate by bytes
    kept_bytes = text_bytes[:max_bytes]
    result = kept_bytes.decode("utf-8", errors="replace")
    output_lines = len(result.split("\n"))
    return TruncationResult(result, True, total_lines, output_lines, "bytes")
