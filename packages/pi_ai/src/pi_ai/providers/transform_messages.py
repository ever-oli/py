"""
Message transformation for cross-provider compatibility.
Python port of TypeScript providers/transform-messages.ts
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import (
        Message,
        Model,
        ToolCall,
    )


def transform_messages(
    messages: list[Message],
    model: Model,
    normalize_tool_call_id: Callable[[str], str] | None = None,
) -> list[Message]:
    """
    Normalize tool call ID for cross-provider compatibility.

    OpenAI Responses API generates IDs that are 450+ chars with special characters like `|`.
    Anthropic APIs require IDs matching ^[a-zA-Z0-9_-]+$ (max 64 chars).

    Args:
        messages: The messages to transform
        model: The target model
        normalize_tool_call_id: Optional function to normalize tool call IDs

    Returns:
        Transformed messages
    """
    # Build a map of original tool call IDs to normalized IDs
    tool_call_id_map: dict[str, str] = {}

    # First pass: transform messages (thinking blocks, tool call ID normalization)
    transformed: list[Message] = []
    for msg in messages:
        # User messages pass through unchanged
        if msg.role == "user":
            transformed.append(msg)
            continue

        # Handle toolResult messages - normalize toolCallId if we have a mapping
        if msg.role == "toolResult":
            normalized_id = tool_call_id_map.get(msg.tool_call_id)
            if normalized_id and normalized_id != msg.tool_call_id:
                from dataclasses import replace

                transformed.append(replace(msg, tool_call_id=normalized_id))
            else:
                transformed.append(msg)
            continue

        # Assistant messages need transformation check
        if msg.role == "assistant":
            assistant_msg = msg
            is_same_model = (
                assistant_msg.provider == model.provider
                and assistant_msg.api == model.api
                and assistant_msg.model == model.id
            )

            transformed_content = []
            for block in assistant_msg.content:
                if block.type == "thinking":
                    # Redacted thinking is opaque encrypted content, only valid for the same model.
                    # Drop it for cross-model to avoid API errors.
                    if block.redacted:
                        if is_same_model:
                            transformed_content.append(block)
                        continue

                    # For same model: keep thinking blocks with signatures (needed for replay)
                    # even if the thinking text is empty (OpenAI encrypted reasoning)
                    if is_same_model and block.thinking_signature:
                        transformed_content.append(block)
                        continue

                    # Skip empty thinking blocks, convert others to plain text
                    if not block.thinking or block.thinking.strip() == "":
                        continue

                    if is_same_model:
                        transformed_content.append(block)
                    else:
                        from ..types import TextContent

                        transformed_content.append(TextContent(text=block.thinking))
                    continue

                if block.type == "text":
                    if is_same_model:
                        transformed_content.append(block)
                    else:
                        from ..types import TextContent

                        transformed_content.append(TextContent(text=block.text))
                    continue

                if block.type == "toolCall":
                    tool_call = block
                    normalized_tool_call = tool_call

                    if not is_same_model and tool_call.thought_signature:
                        from dataclasses import replace

                        normalized_tool_call = replace(tool_call, thought_signature=None)

                    if not is_same_model and normalize_tool_call_id:
                        normalized_id = normalize_tool_call_id(tool_call.id)
                        if normalized_id != tool_call.id:
                            tool_call_id_map[tool_call.id] = normalized_id
                            from dataclasses import replace

                            normalized_tool_call = replace(normalized_tool_call, id=normalized_id)

                    transformed_content.append(normalized_tool_call)
                    continue

                transformed_content.append(block)

            from dataclasses import replace

            transformed.append(replace(assistant_msg, content=transformed_content))
            continue

        transformed.append(msg)

    # Second pass: insert synthetic empty tool results for orphaned tool calls
    # This preserves thinking signatures and satisfies API requirements
    result: list[Message] = []
    pending_tool_calls: list[ToolCall] = []
    existing_tool_result_ids: set[str] = set()

    for _i, msg in enumerate(transformed):
        if msg.role == "assistant":
            # If we have pending orphaned tool calls from a previous assistant, insert synthetic results now
            if pending_tool_calls:
                for tc in pending_tool_calls:
                    if tc.id not in existing_tool_result_ids:
                        from ..types import TextContent, ToolResultMessage

                        result.append(
                            ToolResultMessage(
                                role="toolResult",
                                tool_call_id=tc.id,
                                tool_name=tc.name,
                                content=[TextContent(text="No result provided")],
                                is_error=True,
                            )
                        )
                pending_tool_calls = []
                existing_tool_result_ids = set()

            assistant_msg = msg
            # Skip errored/aborted assistant messages entirely.
            # These are incomplete turns that shouldn't be replayed.
            if assistant_msg.stop_reason in ("error", "aborted"):
                continue

            # Track tool calls from this assistant message
            tool_calls = [b for b in assistant_msg.content if b.type == "toolCall"]
            if tool_calls:
                pending_tool_calls = tool_calls
                existing_tool_result_ids = set()

            result.append(msg)

        elif msg.role == "toolResult":
            existing_tool_result_ids.add(msg.tool_call_id)
            result.append(msg)

        elif msg.role == "user":
            # User message interrupts tool flow - insert synthetic results for orphaned calls
            if pending_tool_calls:
                for tc in pending_tool_calls:
                    if tc.id not in existing_tool_result_ids:
                        from ..types import TextContent, ToolResultMessage

                        result.append(
                            ToolResultMessage(
                                role="toolResult",
                                tool_call_id=tc.id,
                                tool_name=tc.name,
                                content=[TextContent(text="No result provided")],
                                is_error=True,
                            )
                        )
                pending_tool_calls = []
                existing_tool_result_ids = set()
            result.append(msg)

        else:
            result.append(msg)

    return result


__all__ = ["transform_messages"]
