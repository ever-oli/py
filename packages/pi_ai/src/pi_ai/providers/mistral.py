"""
Mistral AI provider.
Python port of TypeScript providers/mistral.ts
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types import (
        AssistantMessage,
        Context,
        Model,
        SimpleStreamOptions,
        StopReason,
        StreamOptions,
        TextContent,
    )

from ..event_stream import AssistantMessageEventStream
from ..models import calculate_cost
from ..types import (
    DoneEvent,
    ErrorEvent,
    StartEvent,
    StopReason,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextStartEvent,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    Usage,
)
from ..types import (
    ToolCall as ToolCallType,
)
from ..utils.env_api_keys import get_env_api_key
from ..utils.json_parse import parse_streaming_json
from .simple_options import build_base_options


class MistralConversationsOptions:
    """Options for Mistral Conversations API."""

    def __init__(
        self,
        temperature: float | None = None,
        max_tokens: int | None = None,
        signal: Any | None = None,
        api_key: str | None = None,
        transport: str | None = None,
        cache_retention: str = "short",
        session_id: str | None = None,
        on_payload: Any = None,
        headers: dict[str, str] | None = None,
        max_retry_delay_ms: int = 60000,
        metadata: dict[str, Any] | None = None,
        tool_choice: str | None = None,
        reasoning_effort: str | None = None,
    ):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.signal = signal
        self.api_key = api_key
        self.transport = transport
        self.cache_retention = cache_retention
        self.session_id = session_id
        self.on_payload = on_payload
        self.headers = headers
        self.max_retry_delay_ms = max_retry_delay_ms
        self.metadata = metadata
        self.tool_choice = tool_choice
        self.reasoning_effort = reasoning_effort


# Default API endpoint
DEFAULT_BASE_URL = "https://api.mistral.ai"

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY_MS = 1000


def _is_retryable_error(status: int) -> bool:
    """Check if an error is retryable."""
    return status in (429, 500, 502, 503, 504)


def _convert_messages(context: Context) -> list[dict[str, Any]]:
    """Convert messages to Mistral format."""
    messages: list[dict[str, Any]] = []

    for msg in context.messages:
        if msg.role == "user":
            if isinstance(msg.content, str):
                messages.append({"role": "user", "content": msg.content})
            else:
                content = []
                for item in msg.content:
                    if item.type == "text":
                        content.append(
                            {
                                "type": "text",
                                "text": item.text,
                            }
                        )
                    else:
                        content.append(
                            {
                                "type": "image_url",
                                "image_url": f"data:{item.mime_type};base64,{item.data}",
                            }
                        )
                messages.append({"role": "user", "content": content})

        elif msg.role == "assistant":
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": None}
            text_parts = []
            tool_calls = []

            for block in msg.content:
                if block.type == "text":
                    if block.text:
                        text_parts.append(block.text)
                elif block.type == "thinking":
                    # Mistral doesn't support thinking natively, add as text
                    if block.thinking:
                        text_parts.append(block.thinking)
                elif block.type == "toolCall":
                    tool_calls.append(
                        {
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": json.dumps(block.arguments),
                            },
                        }
                    )

            if text_parts:
                assistant_msg["content"] = "".join(text_parts)

            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls

            if assistant_msg["content"] or assistant_msg.get("tool_calls"):
                messages.append(assistant_msg)

        elif msg.role == "toolResult":
            text_parts = [c.text for c in msg.content if c.type == "text"]
            text_result = "\n".join(text_parts)

            messages.append(
                {
                    "role": "tool",
                    "content": text_result if text_result else "(see attached image)",
                    "tool_call_id": msg.tool_call_id,
                }
            )

    return messages


def _convert_tools(tools: list[Any]) -> list[dict[str, Any]] | None:
    """Convert tools to Mistral format."""
    if not tools:
        return None

    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def _map_stop_reason(reason: str | None) -> StopReason:
    """Map Mistral stop reason to StopReason."""
    if reason is None:
        return StopReason.STOP

    mapping = {
        "stop": StopReason.STOP,
        "length": StopReason.LENGTH,
        "tool_calls": StopReason.TOOL_USE,
    }
    return mapping.get(reason, StopReason.ERROR)


def _has_tool_history(messages: list[Any]) -> bool:
    """Check if messages contain tool calls or tool results."""
    for msg in messages:
        if msg.role == "toolResult":
            return True
        if msg.role == "assistant":
            for block in msg.content:
                if block.type == "toolCall":
                    return True
    return False


def _build_request_body(
    model: Model,
    context: Context,
    options: MistralConversationsOptions | None,
) -> dict[str, Any]:
    """Build the request body for Mistral API."""
    messages = _convert_messages(context)

    request_body: dict[str, Any] = {
        "model": model.id,
        "messages": messages,
        "stream": True,
    }

    if options and options.temperature is not None:
        request_body["temperature"] = options.temperature

    if options and options.max_tokens is not None:
        request_body["max_tokens"] = options.max_tokens

    if context.tools:
        tools_declarations = _convert_tools(context.tools)
        if tools_declarations:
            request_body["tools"] = tools_declarations
    elif _has_tool_history(context.messages):
        # Mistral requires empty tools array if there's tool history
        request_body["tools"] = []

    if options and options.tool_choice:
        request_body["tool_choice"] = options.tool_choice

    if context.system:
        request_body["system"] = context.system

    return request_body


def stream_mistral_conversations(
    model: Model,
    context: Context,
    options: MistralConversationsOptions | StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream completions from Mistral API."""
    stream = AssistantMessageEventStream()

    async def process():
        output = AssistantMessage(
            role="assistant",
            content=[],
            api=model.api,
            provider=model.provider,
            model=model.id,
            usage=Usage(
                input=0,
                output=0,
                cache_read=0,
                cache_write=0,
                total_tokens=0,
                cost={"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0},
            ),
            stop_reason=StopReason.STOP,
        )

        try:
            import httpx

            api_key = getattr(options, "api_key", None) or get_env_api_key(model.provider) or ""
            if not api_key:
                raise ValueError(f"No API key for provider: {model.provider}")

            base_url = (model.base_url or DEFAULT_BASE_URL).rstrip("/")
            request_body = _build_request_body(model, context, options)

            if options and hasattr(options, "on_payload") and options.on_payload:
                next_body = await options.on_payload(request_body, model)
                if next_body is not None:
                    request_body = next_body

            url = f"{base_url}/v1/chat/completions"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            if options and hasattr(options, "headers") and options.headers:
                headers.update(options.headers)

            signal = getattr(options, "signal", None) if options else None

            # Retry loop
            response = None
            last_error = None

            for attempt in range(MAX_RETRIES + 1):
                if signal and getattr(signal, "aborted", False):
                    raise asyncio.CancelledError("Request was aborted")

                try:
                    async with (
                        httpx.AsyncClient() as client,
                        client.stream(
                            "POST",
                            url,
                            headers=headers,
                            json=request_body,
                            timeout=300,
                        ) as resp,
                    ):
                        if resp.status_code < 400:
                            response = resp
                            break

                        error_text = await resp.aread()
                        error_str = error_text.decode("utf-8", errors="replace")

                        if attempt < MAX_RETRIES and _is_retryable_error(resp.status_code):
                            await asyncio.sleep(BASE_DELAY_MS * (2**attempt) / 1000)
                            continue

                        raise Exception(f"Mistral API error ({resp.status_code}): {error_str}")

                except Exception as e:
                    last_error = e
                    if "aborted" in str(e).lower():
                        raise
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(BASE_DELAY_MS * (2**attempt) / 1000)
                        continue
                    raise

            if not response:
                raise last_error or Exception("Failed to get response after retries")

            stream.push(StartEvent(partial=output))

            current_block: TextContent | (ToolCallType & dict) | None = None
            blocks = output.content

            async for line in response.aiter_lines():
                if signal and getattr(signal, "aborted", False):
                    raise asyncio.CancelledError("Request was aborted")

                line = line.strip()
                if not line or line == "data: [DONE]":
                    continue

                if line.startswith("data: "):
                    line = line[6:]

                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Extract response ID
                if chunk.get("id") and not output.response_id:
                    output.response_id = chunk["id"]

                # Parse usage
                if chunk.get("usage"):
                    usage = chunk["usage"]
                    output.usage = Usage(
                        input=usage.get("prompt_tokens", 0),
                        output=usage.get("completion_tokens", 0),
                        cache_read=0,
                        cache_write=0,
                        total_tokens=usage.get("total_tokens", 0),
                        cost={
                            "input": 0,
                            "output": 0,
                            "cache_read": 0,
                            "cache_write": 0,
                            "total": 0,
                        },
                    )
                    calculate_cost(model, output.usage)

                choices = chunk.get("choices", [])
                if not choices:
                    continue

                choice = choices[0]
                delta = choice.get("delta", {})

                # Handle finish reason
                finish_reason = choice.get("finish_reason")
                if finish_reason:
                    output.stop_reason = _map_stop_reason(finish_reason)
                    if any(b.type == "toolCall" for b in output.content):
                        output.stop_reason = StopReason.TOOL_USE

                # Text content
                content = delta.get("content")
                if content:
                    if not current_block or current_block.type != "text":
                        _finish_current_block(stream, current_block, blocks, output)
                        current_block = TextContent(text="")
                        output.content.append(current_block)
                        stream.push(TextStartEvent(content_index=len(blocks) - 1, partial=output))

                    current_block.text += content
                    stream.push(
                        TextDeltaEvent(
                            content_index=len(blocks) - 1,
                            delta=content,
                            partial=output,
                        )
                    )

                # Tool calls
                tool_calls = delta.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        tc_id = tc.get("id")
                        if (
                            not current_block
                            or current_block.type != "toolCall"
                            or (tc_id and current_block.get("id") != tc_id)
                        ):
                            _finish_current_block(stream, current_block, blocks, output)
                            current_block = {
                                "type": "toolCall",
                                "id": tc_id or "",
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": {},
                                "partial_args": "",
                            }
                            output.content.append(current_block)
                            stream.push(
                                ToolCallStartEvent(content_index=len(blocks) - 1, partial=output)
                            )

                        if current_block.get("type") == "toolCall":
                            if tc_id:
                                current_block["id"] = tc_id
                            func = tc.get("function", {})
                            if func.get("name"):
                                current_block["name"] = func["name"]
                            if func.get("arguments"):
                                delta_args = func["arguments"]
                                current_block["partial_args"] += delta_args
                                current_block["arguments"] = parse_streaming_json(
                                    current_block["partial_args"]
                                )
                                stream.push(
                                    ToolCallDeltaEvent(
                                        content_index=len(blocks) - 1,
                                        delta=delta_args,
                                        partial=output,
                                    )
                                )

            _finish_current_block(stream, current_block, blocks, output)

            if signal and getattr(signal, "aborted", False):
                raise asyncio.CancelledError("Request was aborted")

            stream.push(DoneEvent(reason=output.stop_reason, message=output))
            stream.end()

        except Exception as error:
            is_aborted = (signal and getattr(signal, "aborted", False)) or isinstance(
                error, asyncio.CancelledError
            )
            output.stop_reason = StopReason.ABORTED if is_aborted else StopReason.ERROR
            output.error_message = str(error)
            stream.push(ErrorEvent(reason=output.stop_reason, error=output))
            stream.end()

    asyncio.create_task(process())
    return stream


def _finish_current_block(
    stream: AssistantMessageEventStream,
    block: Any,
    blocks: list[Any],
    output: AssistantMessage,
) -> None:
    """Finish the current content block and emit end event."""
    if not block:
        return

    block_index = len(blocks) - 1

    if block.type == "text":
        stream.push(
            TextEndEvent(
                content_index=block_index,
                content=block.text,
                partial=output,
            )
        )
    elif isinstance(block, dict) and block.get("type") == "toolCall":
        block["arguments"] = parse_streaming_json(block.get("partial_args", ""))
        block.pop("partial_args", None)
        tc = ToolCallType(
            type="toolCall",
            id=block["id"],
            name=block["name"],
            arguments=block["arguments"],
        )
        stream.push(
            ToolCallEndEvent(
                content_index=block_index,
                tool_call=tc,
                partial=output,
            )
        )


def stream_simple_mistral_conversations(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple streaming interface for Mistral."""
    api_key = (options.api_key if options else None) or get_env_api_key(model.provider)
    if not api_key:
        raise ValueError(f"No API key for provider: {model.provider}")

    base = build_base_options(model, options, api_key)
    reasoning_effort = options.reasoning if options else None

    return stream_mistral_conversations(
        model,
        context,
        MistralConversationsOptions(
            **{k: v for k, v in base.__dict__.items() if v is not None},
            reasoning_effort=reasoning_effort,
        ),
    )


# Aliases for register_builtins compatibility
stream_mistral = stream_mistral_conversations
stream_simple_mistral = stream_simple_mistral_conversations


__all__ = [
    "stream_mistral_conversations",
    "stream_simple_mistral_conversations",
    "stream_mistral",
    "stream_simple_mistral",
    "MistralConversationsOptions",
]
