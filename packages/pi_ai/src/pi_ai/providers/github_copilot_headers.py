"""
GitHub Copilot headers helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import Message


def build_copilot_dynamic_headers(
    messages: list[Message],
    has_images: bool,
) -> dict[str, str]:
    """Build dynamic headers for GitHub Copilot."""
    # Stub implementation
    return {}


def has_copilot_vision_input(messages: list[Message]) -> bool:
    """Check if messages contain vision input for Copilot."""
    for msg in messages:
        if msg.role == "user" and isinstance(msg.content, list):
            for item in msg.content:
                if item.type == "image":
                    return True
    return False


__all__ = [
    "build_copilot_dynamic_headers",
    "has_copilot_vision_input",
]
