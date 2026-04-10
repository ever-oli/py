"""Chat page and components module.

Provides chat UI components and rendering utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from pi_agent_core import AgentMessage, AgentTool


@dataclass
class RenderOptions:
    """Options for rendering messages."""

    show_tool_calls: bool = True
    show_thinking: bool = True
    on_cost_click: Callable[[], None] | None = None


class MessageRenderer:
    """Renderer for chat messages.

    Converts internal message types to HTML or dict representations.
    """

    def __init__(self, options: RenderOptions | None = None):
        self.options = options or RenderOptions()

    def render_message(self, msg: AgentMessage) -> dict[str, Any]:
        """Render a message to a dictionary representation."""
        if isinstance(msg, dict):
            role = msg.get("role", "")
            if role == "user":
                return self._render_user_message(msg)
            elif role == "assistant":
                return self._render_assistant_message(msg)
            elif role == "toolResult":
                return self._render_tool_result(msg)
        return {"role": "unknown", "content": str(msg)}

    def _render_user_message(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Render a user message."""
        content = msg.get("content", "")

        # Handle different content types
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text_parts = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    text_parts.append(c.get("text", ""))
            text = " ".join(text_parts)
        else:
            text = str(content)

        return {
            "role": "user",
            "content": text,
            "timestamp": msg.get("timestamp"),
        }

    def _render_assistant_message(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Render an assistant message."""
        content = msg.get("content", "")

        # Parse content array
        rendered_content = []
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict):
                    if c.get("type") == "text":
                        rendered_content.append(
                            {
                                "type": "text",
                                "text": c.get("text", ""),
                            }
                        )
                    elif c.get("type") == "thinking":
                        rendered_content.append(
                            {
                                "type": "thinking",
                                "thinking": c.get("thinking", ""),
                            }
                        )
                    elif c.get("type") == "toolCall":
                        rendered_content.append(
                            {
                                "type": "toolCall",
                                "id": c.get("id", ""),
                                "name": c.get("name", ""),
                                "arguments": c.get("arguments", {}),
                            }
                        )
        elif isinstance(content, str):
            rendered_content.append({"type": "text", "text": content})

        return {
            "role": "assistant",
            "content": rendered_content,
            "usage": msg.get("usage"),
            "stop_reason": msg.get("stop_reason"),
            "error_message": msg.get("error_message"),
            "timestamp": msg.get("timestamp"),
        }

    def _render_tool_result(self, msg: dict[str, Any]) -> dict[str, Any]:
        """Render a tool result message."""
        return {
            "role": "toolResult",
            "tool_call_id": msg.get("tool_call_id"),
            "tool_name": msg.get("tool_name"),
            "content": msg.get("content"),
            "is_error": msg.get("is_error", False),
        }

    def render_messages(self, messages: list[AgentMessage]) -> list[dict[str, Any]]:
        """Render multiple messages."""
        return [self.render_message(msg) for msg in messages]


class ChatPage:
    """Chat page component.

    Manages the chat UI state and rendering.
    """

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id
        self.renderer = MessageRenderer()
        self.messages: list[AgentMessage] = []
        self.tools: list[AgentTool] = []
        self.is_streaming = False

    def add_message(self, msg: AgentMessage) -> None:
        """Add a message to the chat."""
        self.messages.append(msg)

    def update_message(self, index: int, msg: AgentMessage) -> None:
        """Update a message at the given index."""
        if 0 <= index < len(self.messages):
            self.messages[index] = msg

    def clear_messages(self) -> None:
        """Clear all messages."""
        self.messages = []

    def get_state(self) -> dict[str, Any]:
        """Get the current chat state."""
        return {
            "session_id": self.session_id,
            "messages": self.renderer.render_messages(self.messages),
            "is_streaming": self.is_streaming,
            "message_count": len(self.messages),
        }

    def to_json(self) -> str:
        """Serialize chat state to JSON."""
        import json

        return json.dumps(self.get_state(), default=str)
