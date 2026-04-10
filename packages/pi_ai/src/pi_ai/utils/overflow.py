"""
Token overflow handling utilities.
Python port of TypeScript utils/overflow.ts
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import Message


def estimate_token_count(text: str) -> int:
    """Estimate token count from text."""
    return max(1, len(text) // 4)


def truncate_messages(
    messages: list[Message],
    max_tokens: int,
    preserve_recent: int = 2,
) -> list[Message]:
    """
    Truncate messages to fit within max_tokens.

    Args:
        messages: The messages to truncate
        max_tokens: Maximum tokens allowed
        preserve_recent: Number of most recent messages to preserve

    Returns:
        Truncated message list
    """
    if not messages:
        return []

    # Calculate total tokens
    total_tokens = sum(estimate_token_count(str(m.content)) for m in messages)

    if total_tokens <= max_tokens:
        return messages

    # Keep system messages and recent messages
    result = []

    # Add messages from the start (usually system prompts)
    for msg in messages:
        if msg.role == "system":
            result.append(msg)

    # Calculate remaining budget
    system_tokens = sum(estimate_token_count(str(m.content)) for m in result)
    remaining_budget = max_tokens - system_tokens

    # Add recent messages that fit within budget
    recent_messages = [m for m in messages if m.role != "system"][-preserve_recent:]
    recent_tokens = sum(estimate_token_count(str(m.content)) for m in recent_messages)

    if recent_tokens <= remaining_budget:
        # Add intermediate messages
        intermediate = [m for m in messages if m.role != "system"][:-preserve_recent]
        current_tokens = recent_tokens

        # Add intermediate messages from the end backwards
        for msg in reversed(intermediate):
            msg_tokens = estimate_token_count(str(msg.content))
            if current_tokens + msg_tokens <= remaining_budget:
                result.insert(len(result), msg)
                current_tokens += msg_tokens
            else:
                break

        # Add recent messages
        result.extend(recent_messages)
    else:
        # Just add what fits from recent
        current_tokens = 0
        for msg in recent_messages:
            msg_tokens = estimate_token_count(str(msg.content))
            if current_tokens + msg_tokens <= remaining_budget:
                result.append(msg)
                current_tokens += msg_tokens
            else:
                break

    return result


__all__ = [
    "estimate_token_count",
    "truncate_messages",
]
