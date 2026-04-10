"""JSON parsing with error recovery.
Python port of TypeScript json-parse.ts
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

from .regex_cache import TRAILING_COMMA_BRACE, TRAILING_COMMA_BRACKET

T = TypeVar("T")


def parse_streaming_json(partial_json: str | None) -> dict[str, Any]:
    """
    Attempts to parse potentially incomplete JSON during streaming.
    Always returns a valid object, even if the JSON is incomplete.

    Args:
        partial_json: The partial JSON string from streaming

    Returns:
        Parsed object or empty dict if parsing fails
    """
    if not partial_json:
        return {}

    # Fast path: check if empty after strip
    stripped = partial_json.strip()
    if not stripped:
        return {}

    # Try standard parsing first (fastest for complete JSON)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Try partial JSON parsing using a simple heuristic
    try:
        return _parse_partial_json(stripped)
    except Exception:
        pass

    # If all parsing fails, return empty dict
    return {}


def _parse_partial_json(partial: str) -> dict[str, Any]:
    """
    Simple partial JSON parser that handles incomplete objects.

    This is a basic implementation that attempts to complete incomplete JSON.
    For more robust handling, consider using a library like `json5`.
    """
    # If it starts with {, try to complete the object
    if partial.startswith("{"):
        # Count braces
        open_count = partial.count("{")
        close_count = partial.count("}")

        # Add missing closing braces
        if open_count > close_count:
            partial += "}" * (open_count - close_count)

        # Try parsing again
        try:
            return json.loads(partial)
        except json.JSONDecodeError:
            # Try removing trailing commas and incomplete values
            return _fix_and_parse_json(partial)

    # If it starts with [, try to complete the array
    if partial.startswith("["):
        open_count = partial.count("[")
        close_count = partial.count("]")

        if open_count > close_count:
            partial += "]" * (open_count - close_count)

        try:
            return json.loads(partial)
        except json.JSONDecodeError:
            pass

    return {}


def _fix_and_parse_json(partial: str) -> dict[str, Any]:
    """
    Attempt to fix common JSON issues and parse.
    Uses pre-compiled regex patterns for performance.
    """
    # Remove trailing commas using cached patterns
    partial = TRAILING_COMMA_BRACE.sub("}", partial)
    partial = TRAILING_COMMA_BRACKET.sub("]", partial)

    # Try to close unclosed strings
    # Count unescaped quotes
    quote_count = 0
    escaped = False
    for char in partial:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quote_count += 1

    if quote_count % 2 == 1:
        partial += '"'

    # Try to close incomplete key-value pairs
    stripped = partial.rstrip()
    if stripped.endswith(":"):
        partial += "null"
    elif stripped.endswith('"'):
        # Check if we need a value
        last_colon = partial.rfind(":")
        last_quote = partial.rfind('"')
        if last_colon > last_quote:
            partial += '"value"'

    try:
        return json.loads(partial)
    except json.JSONDecodeError:
        return {}


__all__ = ["parse_streaming_json"]
