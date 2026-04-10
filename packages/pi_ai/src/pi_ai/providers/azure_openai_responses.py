"""
Azure OpenAI Responses API provider.
Python port of TypeScript providers/azure-openai-responses.ts
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
        ThinkingContent,
        Tool,
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
    ThinkingContent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingStartEvent,
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


class AzureOpenAIResponsesOptions:
    """Options for Azure OpenAI Responses API."""

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
        reasoning_effort: str | None = None,
        reasoning_summary: str | None = None,
        text_verbosity: str | None = None,
        azure_api_version: str = "2025-03-01-preview",
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
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
        self.text_verbosity = text_verbosity
        self.azure_api_version = azure_api_version


# Retry configuration
MAX_RETRIES = 3
BASE_DELAY_MS = 1000

# Tool call providers that are allowed to use tool calls with this API
ALLOWED_TOOL_CALL_PROVIDERS = {"azure-openai-responses"}


def _is_retryable_error(status: int, error_text: str) -> bool:
    """Check if an error is retryable."""
    if status in (429, 500, 502, 503, 504):
        return True
    return bool(
        ("rate" in error_text.lower() and "limit" in error_text.lower())
        or "overloaded" in error_text.lower()
        or "service unavailable" in error_text.lower()
    )


def _extract_error_message(error_text: str) -> str:
    """Extract error message from Azure error response."""
    try:
        parsed = json.loads(error_text)
        if parsed.get("error", {}).get("message"):
            return parsed["error"]["message"]
        if parsed.get("error") and isinstance(parsed["error"], str):
            return parsed["error"]
    except json.JSONDecodeError:
        pass
    return error_text


def _normalize_id(id: str) -> str:
    """Normalize ID for OpenAI Responses API (max 64 chars)."""
    import re

    normalized = re.sub(r"[^a-zA-Z0-9_-]", "_", id)
    if len(normalized) > 64:
        import hashlib

        return f"fc_{hashlib.md5(normalized.encode()).hexdigest()[:16]}"
    return normalized


def _build_foreign_responses_item_id(item_id: str) -> str:
    """Build foreign responses item ID."""
    import hashlib

    normalized = f"fc_{hashlib.md5(item_id.encode()).hexdigest()[:16]}"
    return normalized[:64]


def _normalize_tool_call_id(id: str, model: Model, source: AssistantMessage) -> str:
    """Normalize tool call ID for Responses API."""
    if model.provider not in ALLOWED_TOOL_CALL_PROVIDERS:
        return _normalize_id(id)
    if "|" not in id:
        return _normalize_id(id)

    parts = id.split("|")
    call_id = parts[0]
    item_id = parts[1] if len(parts) > 1 else ""

    normalized_call_id = _normalize_id(call_id)
    is_foreign = source.provider != model.provider or source.api != model.api
    normalized_item_id = (
        _build_foreign_responses_item_id(item_id) if is_foreign else _normalize_id(item_id)
    )

    # OpenAI requires item id to start with "fc"
    if not normalized_item_id.startswith("fc_"):
        normalized_item_id = _normalize_id(f"fc_{normalized_item_id}")

    return f"{normalized_call_id}|{normalized_item_id}"


def _convert_messages(
    model: Model,
    context: Context,
    options: AzureOpenAIResponsesOptions | None = None,
) -> list[dict[str, Any]]:
    """Convert messages to Azure OpenAI Responses API format."""

    from .transform_messages import transform_messages

    messages: list[dict[str, Any]] = []

    # Add system/developer prompt
    if context.system:
        role = "developer" if model.reasoning else "system"
        messages.append(
            {
                "role": role,
                "content": context.system,
            }
        )

    transformed = transform_messages(
        context.messages, model, lambda id: _normalize_tool_call_id(id, model, None)
    )

    for msg in transformed:
        if msg.role == "user":
            if isinstance(msg.content, str):
                messages.append(
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": msg.content}],
                    }
                )
            else:
                content = []
                for item in msg.content:
                    if item.type == "text":
                        content.append(
                            {
                                "type": "input_text",
                                "text": item.text,
                            }
                        )
                    else:
                        content.append(
                            {
                                "type": "input_image",
                                "detail": "auto",
                                "image_url": f"data:{item.mime_type};base64,{item.data}",
                            }
                        )
                if not model.capabilities.supports_vision:
                    content = [c for c in content if c.get("type") != "input_image"]
                if content:
                    messages.append({"role": "user", "content": content})

        elif msg.role == "assistant":
            is_different_model = (
                msg.model != model.id and msg.provider == model.provider and msg.api == model.api
            )

            for block in msg.content:
                if block.type == "thinking":
                    if block.thinking_signature:
                        try:
                            reasoning_item = json.loads(block.thinking_signature)
                            messages.append(reasoning_item)
                        except json.JSONDecodeError:
                            pass

                elif block.type == "text":
                    msg_id = None
                    phase = None
                    if block.text_signature:
                        try:
                            parsed = json.loads(block.text_signature)
                            if parsed.get("v") == 1 and "id" in parsed:
                                msg_id = parsed["id"]
                                phase = parsed.get("phase")
                        except json.JSONDecodeError:
                            msg_id = block.text_signature

                    if not msg_id:
                        msg_id = f"msg_{len(messages)}"
                    elif len(msg_id) > 64:
                        import hashlib

                        msg_id = f"msg_{hashlib.md5(msg_id.encode()).hexdigest()[:16]}"

                    output_msg = {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": block.text, "annotations": []}],
                        "status": "completed",
                        "id": msg_id,
                    }
                    if phase:
                        output_msg["phase"] = phase
                    messages.append(output_msg)

                elif block.type == "toolCall":
                    parts = block.id.split("|")
                    call_id = parts[0]
                    item_id_raw = parts[1] if len(parts) > 1 else None

                    item_id = item_id_raw
                    # For different-model messages, set id to undefined to avoid pairing validation
                    if is_different_model and item_id and item_id.startswith("fc_"):
                        item_id = None

                    messages.append(
                        {
                            "type": "function_call",
                            "id": item_id,
                            "call_id": call_id,
                            "name": block.name,
                            "arguments": json.dumps(block.arguments),
                        }
                    )

        elif msg.role == "toolResult":
            text_parts = [c.text for c in msg.content if c.type == "text"]
            text_result = "\n".join(text_parts)
            has_images = any(c.type == "image" for c in msg.content)

            parts = msg.tool_call_id.split("|")
            call_id = parts[0]

            if has_images and model.capabilities.supports_vision:
                output_parts = []
                if text_result:
                    output_parts.append({"type": "input_text", "text": text_result})
                for block in msg.content:
                    if block.type == "image":
                        output_parts.append(
                            {
                                "type": "input_image",
                                "detail": "auto",
                                "image_url": f"data:{block.mime_type};base64,{block.data}",
                            }
                        )
                messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": output_parts,
                    }
                )
            else:
                messages.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": text_result if text_result else "(see attached image)",
                    }
                )

    return messages


def _convert_tools(tools: list[Tool]) -> list[dict[str, Any]] | None:
    """Convert tools to OpenAI Responses API format."""
    if not tools:
        return None

    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "strict": False,
        }
        for tool in tools
    ]


def _map_stop_reason(status: str | None) -> StopReason:
    """Map Azure response status to StopReason."""
    if status is None:
        return StopReason.STOP

    mapping = {
        "completed": StopReason.STOP,
        "incomplete": StopReason.LENGTH,
        "failed": StopReason.ERROR,
        "cancelled": StopReason.ERROR,
        "queued": StopReason.STOP,
        "in_progress": StopReason.STOP,
    }
    return mapping.get(status, StopReason.ERROR)


def _build_request_body(
    model: Model,
    context: Context,
    options: AzureOpenAIResponsesOptions | None,
) -> dict[str, Any]:
    """Build the request body for Azure OpenAI Responses API."""
    messages = _convert_messages(model, context, options)

    request_body: dict[str, Any] = {
        "model": model.id,
        "stream": True,
        "input": messages,
    }

    if context.system:
        request_body["instructions"] = context.system

    if options and options.temperature is not None:
        request_body["temperature"] = options.temperature

    if options and options.max_tokens is not None:
        request_body["max_output_tokens"] = options.max_tokens

    if context.tools:
        tools_declarations = _convert_tools(context.tools)
        if tools_declarations:
            request_body["tools"] = tools_declarations

    if options and options.reasoning_effort is not None:
        request_body["reasoning"] = {"effort": options.reasoning_effort}
        if options.reasoning_summary is not None:
            request_body["reasoning"]["summary"] = options.reasoning_summary

    if options and options.text_verbosity is not None:
        request_body["text"] = {"verbosity": options.text_verbosity}

    if options and options.session_id:
        request_body["prompt_cache_key"] = options.session_id

    return request_body


def stream_azure_openai_responses(
    model: Model,
    context: Context,
    options: AzureOpenAIResponsesOptions | StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream completions from Azure OpenAI Responses API."""
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

            base_url = model.base_url
            if not base_url:
                raise ValueError("Azure OpenAI requires a base_url (endpoint)")

            base_url = base_url.rstrip("/")
            request_body = _build_request_body(model, context, options)

            if options and hasattr(options, "on_payload") and options.on_payload:
                next_body = await options.on_payload(request_body, model)
                if next_body is not None:
                    request_body = next_body

            api_version = (
                getattr(options, "azure_api_version", "2025-03-01-preview")
                if options
                else "2025-03-01-preview"
            )
            url = f"{base_url}/openai/responses?api-version={api_version}"

            headers = {
                "api-key": api_key,
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
                    async with httpx.AsyncClient() as client:
                        async with client.stream(
                            "POST",
                            url,
                            headers=headers,
                            json=request_body,
                            timeout=300,
                        ) as resp:
                            if resp.status_code < 400:
                                response = resp
                                break

                            error_text = await resp.aread()
                            error_str = error_text.decode("utf-8", errors="replace")

                            if attempt < MAX_RETRIES and _is_retryable_error(
                                resp.status_code, error_str
                            ):
                                await asyncio.sleep(BASE_DELAY_MS * (2**attempt) / 1000)
                                continue

                            raise Exception(
                                f"Azure OpenAI API error ({resp.status_code}): {_extract_error_message(error_str)}"
                            )

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

            current_item = None
            current_block: TextContent | ThinkingContent | (ToolCallType & dict) | None = None
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
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type")

                if event_type == "response.created":
                    output.response_id = event.get("response", {}).get("id")

                elif event_type == "response.output_item.added":
                    item = event.get("item", {})
                    item_type = item.get("type")

                    if item_type == "reasoning":
                        current_item = item
                        current_block = ThinkingContent(thinking="")
                        output.content.append(current_block)
                        stream.push(
                            ThinkingStartEvent(content_index=len(blocks) - 1, partial=output)
                        )

                    elif item_type == "message":
                        current_item = item
                        current_block = TextContent(text="")
                        output.content.append(current_block)
                        stream.push(TextStartEvent(content_index=len(blocks) - 1, partial=output))

                    elif item_type == "function_call":
                        current_item = item
                        current_block = {
                            "type": "toolCall",
                            "id": f"{item.get('call_id')}|{item.get('id')}",
                            "name": item.get("name", ""),
                            "arguments": {},
                            "partial_json": item.get("arguments", ""),
                        }
                        output.content.append(current_block)
                        stream.push(
                            ToolCallStartEvent(content_index=len(blocks) - 1, partial=output)
                        )

                elif event_type == "response.reasoning_summary_text.delta":
                    if (
                        current_item
                        and current_item.get("type") == "reasoning"
                        and current_block
                        and current_block.type == "thinking"
                    ):
                        delta = event.get("delta", "")
                        current_block.thinking += delta
                        stream.push(
                            ThinkingDeltaEvent(
                                content_index=len(blocks) - 1,
                                delta=delta,
                                partial=output,
                            )
                        )

                elif event_type == "response.output_text.delta":
                    if (
                        current_item
                        and current_item.get("type") == "message"
                        and current_block
                        and current_block.type == "text"
                    ):
                        delta = event.get("delta", "")
                        current_block.text += delta
                        stream.push(
                            TextDeltaEvent(
                                content_index=len(blocks) - 1,
                                delta=delta,
                                partial=output,
                            )
                        )

                elif event_type == "response.function_call_arguments.delta":
                    if (
                        current_item
                        and current_item.get("type") == "function_call"
                        and current_block
                        and current_block.get("type") == "toolCall"
                    ):
                        delta = event.get("delta", "")
                        current_block["partial_json"] += delta
                        current_block["arguments"] = parse_streaming_json(
                            current_block["partial_json"]
                        )
                        stream.push(
                            ToolCallDeltaEvent(
                                content_index=len(blocks) - 1,
                                delta=delta,
                                partial=output,
                            )
                        )

                elif event_type == "response.function_call_arguments.done":
                    if (
                        current_item
                        and current_item.get("type") == "function_call"
                        and current_block
                        and current_block.get("type") == "toolCall"
                    ):
                        current_block["arguments"] = parse_streaming_json(
                            event.get("arguments", "{}")
                        )

                elif event_type == "response.output_item.done":
                    item = event.get("item", {})
                    item_type = item.get("type")

                    if (
                        item_type == "reasoning"
                        and current_block
                        and current_block.type == "thinking"
                    ):
                        summary = item.get("summary", [])
                        current_block.thinking = "\n\n".join(s.get("text", "") for s in summary)
                        current_block.thinking_signature = json.dumps(item)
                        stream.push(
                            ThinkingEndEvent(
                                content_index=len(blocks) - 1,
                                content=current_block.thinking,
                                partial=output,
                            )
                        )
                        current_block = None

                    elif item_type == "message" and current_block and current_block.type == "text":
                        content = item.get("content", [])
                        current_block.text = "".join(
                            c.get("text", c.get("refusal", "")) for c in content
                        )
                        msg_id = item.get("id", "")
                        phase = item.get("phase")
                        current_block.text_signature = json.dumps(
                            {"v": 1, "id": msg_id, "phase": phase}
                            if phase
                            else {"v": 1, "id": msg_id}
                        )
                        stream.push(
                            TextEndEvent(
                                content_index=len(blocks) - 1,
                                content=current_block.text,
                                partial=output,
                            )
                        )
                        current_block = None

                    elif item_type == "function_call":
                        if current_block and current_block.get("type") == "toolCall":
                            tc = ToolCallType(
                                type="toolCall",
                                id=current_block["id"],
                                name=current_block["name"],
                                arguments=current_block["arguments"],
                            )
                            stream.push(
                                ToolCallEndEvent(
                                    content_index=len(blocks) - 1,
                                    tool_call=tc,
                                    partial=output,
                                )
                            )
                        current_block = None

                elif event_type == "response.completed":
                    response_data = event.get("response", {})

                    if response_data.get("id"):
                        output.response_id = response_data["id"]

                    usage_data = response_data.get("usage", {})
                    if usage_data:
                        cached_tokens = usage_data.get("input_tokens_details", {}).get(
                            "cached_tokens", 0
                        )
                        output.usage = Usage(
                            input=usage_data.get("input_tokens", 0) - cached_tokens,
                            output=usage_data.get("output_tokens", 0),
                            cache_read=cached_tokens,
                            cache_write=0,
                            total_tokens=usage_data.get("total_tokens", 0),
                            cost={
                                "input": 0,
                                "output": 0,
                                "cache_read": 0,
                                "cache_write": 0,
                                "total": 0,
                            },
                        )
                        calculate_cost(model, output.usage)

                    output.stop_reason = _map_stop_reason(response_data.get("status"))
                    if (
                        any(b.type == "toolCall" for b in output.content)
                        and output.stop_reason == StopReason.STOP
                    ):
                        output.stop_reason = StopReason.TOOL_USE

                elif event_type == "error":
                    error = event.get("error", {})
                    raise Exception(
                        f"Azure OpenAI error: {error.get('code')}: {error.get('message', 'Unknown error')}"
                    )

                elif event_type == "response.failed":
                    error = event.get("response", {}).get("error", {})
                    if error:
                        raise Exception(
                            f"Azure OpenAI response failed: {error.get('code')}: {error.get('message', 'Unknown error')}"
                        )
                    details = event.get("response", {}).get("incomplete_details", {})
                    if details:
                        raise Exception(
                            f"Azure OpenAI response incomplete: {details.get('reason', 'Unknown reason')}"
                        )
                    raise Exception("Azure OpenAI response failed: Unknown error")

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


def stream_simple_azure_openai_responses(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple streaming interface for Azure OpenAI Responses API."""
    api_key = (options.api_key if options else None) or get_env_api_key(model.provider)
    if not api_key:
        raise ValueError(f"No API key for provider: {model.provider}")

    base = build_base_options(model, options, api_key)
    reasoning_effort = options.reasoning if options else None

    return stream_azure_openai_responses(
        model,
        context,
        AzureOpenAIResponsesOptions(
            **{k: v for k, v in base.__dict__.items() if v is not None},
            reasoning_effort=reasoning_effort,
            reasoning_summary="auto",
        ),
    )


__all__ = [
    "stream_azure_openai_responses",
    "stream_simple_azure_openai_responses",
    "AzureOpenAIResponsesOptions",
]
