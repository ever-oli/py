"""Regex pattern caching for performance optimization.

Caches compiled regex patterns to avoid recompilation overhead.
"""

from __future__ import annotations

import functools
import re
from re import Pattern


@functools.lru_cache(maxsize=512)
def compile_pattern(pattern: str, flags: int = 0) -> Pattern[str]:
    """Compile a regex pattern with caching.

    This function caches compiled patterns to avoid the overhead
    of recompiling the same pattern multiple times.

    Args:
        pattern: The regex pattern string
        flags: Regex flags (e.g., re.IGNORECASE)

    Returns:
        Compiled regex pattern

    Example:
        >>> regex = compile_pattern(r'\\d+', re.IGNORECASE)
        >>> regex.match('123')
        <Match object>
    """
    return re.compile(pattern, flags)


def compile_pattern_with_fallback(pattern: str, flags: int = 0) -> Pattern[str] | None:
    """Compile a regex pattern with error handling.

    Args:
        pattern: The regex pattern string
        flags: Regex flags

    Returns:
        Compiled pattern or None if invalid
    """
    try:
        return compile_pattern(pattern, flags)
    except re.error:
        return None


def clear_pattern_cache() -> None:
    """Clear the pattern cache.

    Useful for testing or when memory is constrained.
    """
    compile_pattern.cache_clear()


def get_cache_info() -> dict[str, int]:
    """Get cache statistics.

    Returns:
        Dictionary with hits, misses, maxsize, and currsize
    """
    info = compile_pattern.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
    }


# Pre-compile common patterns for immediate use
TRAILING_COMMA_BRACE = compile_pattern(r",\s*}")
TRAILING_COMMA_BRACKET = compile_pattern(r",\s*]")
WHITESPACE = compile_pattern(r"\s+")
NEWLINES = compile_pattern(r"[\r\n]+")


__all__ = [
    "compile_pattern",
    "compile_pattern_with_fallback",
    "clear_pattern_cache",
    "get_cache_info",
    # Pre-compiled patterns
    "TRAILING_COMMA_BRACE",
    "TRAILING_COMMA_BRACKET",
    "WHITESPACE",
    "NEWLINES",
]
