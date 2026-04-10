"""Faux/mock provider for testing.

Ported from pi-mono/packages/ai/src/providers/faux.ts
"""

from __future__ import annotations

import asyncio

from pi_ai.event_stream import AssistantMessageEventStream
from pi_ai.types import (
    AssistantMessage,
    Context,
    Cost,
    EndEvent,
    ErrorEvent,
    Model,
    SimpleStreamOptions,
    StartEvent,
    StopReason,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextEvent,
    TextStartEvent,
    Usage,
)


def stream_faux(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream a faux/mock response.

    Echoes back the user's last message with a faux prefix.
    """
    stream = AssistantMessageEventStream()

    async def process():
        try:
            # Get the last user message
            last_user_msg = None
            for msg in reversed(context.messages):
                if msg.role == "user":
                    last_user_msg = msg
                    break

            content = "Hello from faux provider!"
            if last_user_msg:
                if isinstance(last_user_msg.content, str):
                    content = f"[FAUX] You said: {last_user_msg.content[:100]}"
                elif last_user_msg.content:
                    first = last_user_msg.content[0]
                    if hasattr(first, "text"):
                        content = f"[FAUX] You said: {first.text[:100]}"

            # Build the message
            message = AssistantMessage(
                role="assistant",
                content=[TextContent(type="text", text=content)],
                api="faux",
                provider="faux",
                model=model.id,
                usage=Usage(
                    input=10,
                    output=len(content),
                    cache_read=0,
                    cache_write=0,
                    total_tokens=10 + len(content),
                    cost=Cost(input=0, output=0, cache_read=0, cache_write=0, total=0),
                ),
                stop_reason=StopReason.STOP,
            )

            # Push start event
            stream.push(StartEvent(partial=message))

            # Stream the response word by word
            words = content.split()
            text_block = TextContent(text="")
            message.content = [text_block]

            stream.push(TextStartEvent(content_index=0, partial=message))

            for i, word in enumerate(words):
                text = word if i == 0 else f" {word}"
                text_block.text += text
                stream.push(TextDeltaEvent(content_index=0, delta=text, partial=message))
                # Also emit legacy TextEvent for backward compatibility
                stream.push(TextEvent(text=text))

            stream.push(TextEndEvent(content_index=0, content=text_block.text, partial=message))

            # Push done and end
            stream.push(EndEvent(message=message))
            stream.end(message)

        except Exception as e:
            message = AssistantMessage(
                role="assistant",
                content=[],
                api="faux",
                provider="faux",
                model=model.id,
                usage=Usage(
                    input=0,
                    output=0,
                    cache_read=0,
                    cache_write=0,
                    total_tokens=0,
                    cost={"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0},
                ),
                stop_reason=StopReason.ERROR,
                error_message=str(e),
            )
            stream.push(ErrorEvent(reason=StopReason.ERROR, error=message))
            stream.end(message)

    asyncio.create_task(process())
    return stream


def stream_simple_faux(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple stream version of faux provider."""
    return stream_faux(model, context, options)


__all__ = [
    "stream_faux",
    "stream_simple_faux",
]
