"""
OpenAI Codex CLI Responses provider.
Python port of TypeScript providers/openai-codex-responses.ts
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types import (
        AssistantMessage,
        Context,
        Model,
        SimpleStreamOptions,
        StreamOptions,
    )

import contextlib

from ..event_stream import AssistantMessageEventStream
from ..models import calculate_cost, supports_xhigh
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
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    Usage,
)
from ..utils.env_api_keys import get_env_api_key
from .simple_options import build_base_options, clamp_reasoning


class OpenAICodexResponsesOptions:
    """Options for OpenAI Codex Responses API."""

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
        text_verbosity: str = "medium",
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


# Constants
DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api"
JWT_CLAIM_PATH = "https://api.openai.com/auth"
MAX_RETRIES = 3
BASE_DELAY_MS = 1000

CODEX_TOOL_CALL_PROVIDERS = {"openai", "openai-codex", "opencode"}

CODEX_RESPONSE_STATUSES = {
    "completed",
    "incomplete",
    "failed",
    "cancelled",
    "queued",
    "in_progress",
}


def _is_retryable_error(status: int, error_text: str) -> bool:
    """Check if an error is retryable."""
    if status in (429, 500, 502, 503, 504):
        return True
    pattern = r"rate.?limit|overloaded|service.?unavailable|upstream.?connect|connection.?refused"
    return bool(re.search(pattern, error_text, re.IGNORECASE))


def _sleep(ms: float, signal: Any | None = None) -> asyncio.Future[None]:
    """Sleep for a given number of milliseconds, respecting abort signal."""

    async def do_sleep():
        if signal and getattr(signal, "aborted", False):
            raise asyncio.CancelledError("Request was aborted")

        future: asyncio.Future[None] = asyncio.get_event_loop().create_future()

        def on_timeout():
            if not future.done():
                future.set_result(None)

        timeout_handle = asyncio.get_event_loop().call_later(ms / 1000, on_timeout)

        def on_abort():
            if not future.done():
                timeout_handle.cancel()
                future.set_exception(asyncio.CancelledError("Request was aborted"))

        if signal:
            # Note: signal is a callable that returns bool, not an AbortSignal with addEventListener
            pass

        try:
            await future
        finally:
            timeout_handle.cancel()

    return asyncio.ensure_future(do_sleep())


def _extract_account_id(token: str) -> str:
    """Extract account ID from JWT token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token")
        payload = json.loads(base64.b64decode(parts[1] + "=="))
        account_id = payload.get(JWT_CLAIM_PATH, {}).get("chatgpt_account_id")
        if not account_id:
            raise ValueError("No account ID in token")
        return account_id
    except Exception as e:
        raise ValueError(f"Failed to extract accountId from token: {e}")


def _create_codex_request_id() -> str:
    """Create a unique request ID for Codex."""
    import uuid

    try:
        return str(uuid.uuid4())
    except Exception:
        return f"codex_{int(asyncio.get_event_loop().time() * 1000)}_{hash(str(os.urandom(16))) % 1000000000}"


def _build_base_codex_headers(
    init_headers: dict[str, str] | None,
    additional_headers: dict[str, str] | None,
    account_id: str,
    token: str,
) -> dict[str, str]:
    """Build base headers for Codex requests."""
    headers = dict(init_headers or {})
    if additional_headers:
        headers.update(additional_headers)

    headers["Authorization"] = f"Bearer {token}"
    headers["chatgpt-account-id"] = account_id
    headers["originator"] = "pi"

    try:
        platform = os.uname().sysname
        release = os.uname().release
        machine = os.uname().machine
        user_agent = f"pi ({platform} {release}; {machine})"
    except AttributeError:
        user_agent = "pi (browser)"

    headers["User-Agent"] = user_agent
    return headers


def _build_sse_headers(
    init_headers: dict[str, str] | None,
    additional_headers: dict[str, str] | None,
    account_id: str,
    token: str,
    session_id: str | None = None,
) -> dict[str, str]:
    """Build SSE headers for Codex requests."""
    headers = _build_base_codex_headers(init_headers, additional_headers, account_id, token)
    headers["OpenAI-Beta"] = "responses=experimental"
    headers["accept"] = "text/event-stream"
    headers["content-type"] = "application/json"

    if session_id:
        headers["session_id"] = session_id

    return headers


def _resolve_codex_url(base_url: str | None) -> str:
    """Resolve the Codex API URL."""
    raw = base_url.strip() if base_url and base_url.strip() else DEFAULT_CODEX_BASE_URL
    normalized = raw.rstrip("/")

    if normalized.endswith("/codex/responses"):
        return normalized
    if normalized.endswith("/codex"):
        return f"{normalized}/responses"
    return f"{normalized}/codex/responses"


def _clamp_reasoning_effort(model_id: str, effort: str) -> str:
    """Clamp reasoning effort for specific models."""
    id_part = model_id.split("/")[-1] if "/" in model_id else model_id

    if (
        id_part.startswith("gpt-5.2")
        or id_part.startswith("gpt-5.3")
        or id_part.startswith("gpt-5.4")
    ) and effort == "minimal":
        return "low"
    if id_part == "gpt-5.1" and effort == "xhigh":
        return "high"
    if id_part == "gpt-5.1-codex-mini":
        return "high" if effort in ("high", "xhigh") else "medium"
    return effort


def _convert_responses_messages(
    model: Model,
    context: Context,
) -> list[dict[str, Any]]:
    """Convert messages to OpenAI Responses API format."""
    messages: list[dict[str, Any]] = []

    for msg in context.messages:
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
                        content.append({"type": "input_text", "text": item.text})
                    elif item.type == "image":
                        content.append(
                            {
                                "type": "input_image",
                                "image_url": f"data:{item.mime_type};base64,{item.data}",
                            }
                        )
                if content:
                    messages.append({"role": "user", "content": content})

        elif msg.role == "assistant":
            content = []
            for block in msg.content:
                if block.type == "text":
                    content.append({"type": "output_text", "text": block.text})
                elif block.type == "thinking":
                    # Thinking is handled separately via reasoning fields
                    pass
                elif block.type == "toolCall":
                    content.append(
                        {
                            "type": "function_call",
                            "call_id": block.id,
                            "name": block.name,
                            "arguments": json.dumps(block.arguments),
                        }
                    )
            if content:
                messages.append({"role": "assistant", "content": content})

        elif msg.role == "toolResult":
            text_content = [c for c in msg.content if c.type == "text"]
            text_result = "\n".join(c.text for c in text_content)
            messages.append(
                {
                    "role": "system",  # Function results go as system messages in responses API
                    "content": [{"type": "input_text", "text": f"Tool result: {text_result}"}],
                }
            )

    return messages


def _convert_responses_tools(tools: list[Any]) -> list[dict[str, Any]]:
    """Convert tools to OpenAI Responses API format."""
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in tools
    ]


def _build_request_body(
    model: Model,
    context: Context,
    options: OpenAICodexResponsesOptions | None,
) -> dict[str, Any]:
    """Build the request body for Codex API."""
    messages = _convert_responses_messages(model, context)

    body: dict[str, Any] = {
        "model": model.id,
        "store": False,
        "stream": True,
        "instructions": context.system,
        "input": messages,
        "text": {"verbosity": options.text_verbosity if options else "medium"},
        "include": ["reasoning.encrypted_content"],
        "prompt_cache_key": options.session_id if options else None,
        "tool_choice": "auto",
        "parallel_tool_calls": True,
    }

    if options and options.temperature is not None:
        body["temperature"] = options.temperature

    if context.tools:
        body["tools"] = _convert_responses_tools(context.tools)

    if options and options.reasoning_effort is not None:
        body["reasoning"] = {
            "effort": _clamp_reasoning_effort(model.id, options.reasoning_effort),
            "summary": options.reasoning_summary or "auto",
        }

    # Remove None values
    body = {k: v for k, v in body.items() if v is not None}

    return body


async def _parse_error_response(response: Any) -> dict[str, str]:
    """Parse error response from Codex API."""
    raw = (
        await response.aread()
        if hasattr(response, "aread")
        else response.text
        if hasattr(response, "text")
        else str(response)
    )
    message = raw or "Request failed"
    friendly_message = None

    try:
        parsed = json.loads(raw)
        err = parsed.get("error", {})
        if err:
            code = err.get("code") or err.get("type") or ""
            if re.search(
                r"usage_limit_reached|usage_not_included|rate_limit_exceeded", code, re.IGNORECASE
            ):
                plan = f" ({err.get('plan_type', '').lower()} plan)" if err.get("plan_type") else ""
                resets_at = err.get("resets_at")
                mins = (
                    max(
                        0,
                        round(
                            (resets_at * 1000 - int(asyncio.get_event_loop().time() * 1000)) / 60000
                        ),
                    )
                    if resets_at
                    else None
                )
                when = f" Try again in ~{mins} min." if mins is not None else ""
                friendly_message = f"You have hit your ChatGPT usage limit{plan}.{when}".strip()
            message = err.get("message") or friendly_message or message
    except Exception:
        pass

    return {"message": message, "friendly_message": friendly_message}


def _process_responses_stream(
    events: Any,
    output: AssistantMessage,
    stream: AssistantMessageEventStream,
    model: Model,
) -> asyncio.Future[None]:
    """Process the responses stream."""

    async def process():
        current_block: TextContent | ThinkingContent | None = None
        blocks = output.content

        async for event in events:
            event_type = event.get("type")
            if not event_type:
                continue

            if event_type == "error":
                code = event.get("code", "")
                message = event.get("message", "")
                raise Exception(f"Codex error: {message or code or json.dumps(event)}")

            if event_type == "response.failed":
                msg = event.get("response", {}).get("error", {}).get("message")
                raise Exception(msg or "Codex response failed")

            if event_type in ("response.done", "response.completed", "response.incomplete"):
                response = event.get("response", {})
                status = response.get("status")
                if status in CODEX_RESPONSE_STATUSES:
                    if status == "completed":
                        output.stop_reason = StopReason.STOP
                    elif status == "incomplete":
                        output.stop_reason = StopReason.LENGTH
                    elif status in ("failed", "cancelled"):
                        output.stop_reason = StopReason.ERROR
                break

            # Handle output text
            if event_type == "response.output_text.delta":
                delta = event.get("delta", "")
                if not current_block or current_block.type != "text":
                    if current_block and current_block.type == "thinking":
                        stream.push(
                            ThinkingEndEvent(
                                content_index=len(blocks) - 1,
                                content=current_block.thinking,
                                partial=output,
                            )
                        )
                    current_block = TextContent(text="")
                    output.content.append(current_block)
                    stream.push(TextStartEvent(content_index=len(blocks) - 1, partial=output))

                current_block.text += delta
                stream.push(
                    TextDeltaEvent(
                        content_index=len(blocks) - 1,
                        delta=delta,
                        partial=output,
                    )
                )

            elif event_type == "response.output_text.done":
                if current_block and current_block.type == "text":
                    stream.push(
                        TextEndEvent(
                            content_index=len(blocks) - 1,
                            content=current_block.text,
                            partial=output,
                        )
                    )
                    current_block = None

            # Handle reasoning/thinking
            elif event_type == "response.reasoning.delta":
                delta = event.get("delta", "")
                if not current_block or current_block.type != "thinking":
                    if current_block and current_block.type == "text":
                        stream.push(
                            TextEndEvent(
                                content_index=len(blocks) - 1,
                                content=current_block.text,
                                partial=output,
                            )
                        )
                    current_block = ThinkingContent(thinking="")
                    output.content.append(current_block)
                    stream.push(ThinkingStartEvent(content_index=len(blocks) - 1, partial=output))

                current_block.thinking += delta
                stream.push(
                    ThinkingDeltaEvent(
                        content_index=len(blocks) - 1,
                        delta=delta,
                        partial=output,
                    )
                )

            elif event_type == "response.reasoning.done":
                if current_block and current_block.type == "thinking":
                    stream.push(
                        ThinkingEndEvent(
                            content_index=len(blocks) - 1,
                            content=current_block.thinking,
                            partial=output,
                        )
                    )
                    current_block = None

            # Handle function calls (tool calls)
            elif event_type == "response.function_call_arguments.delta":
                call_id = event.get("call_id", "")
                delta = event.get("delta", "")

                # Find existing tool call or create new one
                existing = None
                for block in output.content:
                    if block.type == "toolCall" and block.id == call_id:
                        existing = block
                        break

                if not existing:
                    existing = ToolCall(type="toolCall", id=call_id, name="", arguments={})
                    output.content.append(existing)
                    stream.push(ToolCallStartEvent(content_index=len(blocks) - 1, partial=output))

                # Accumulate arguments as string and parse
                if not hasattr(existing, "_arguments_str"):
                    existing._arguments_str = ""
                existing._arguments_str += delta

                with contextlib.suppress(json.JSONDecodeError):
                    existing.arguments = json.loads(existing._arguments_str)

                stream.push(
                    ToolCallDeltaEvent(
                        content_index=len(blocks) - 1,
                        delta=delta,
                        partial=output,
                    )
                )

            elif event_type == "response.function_call_arguments.done":
                call_id = event.get("call_id", "")
                for i, block in enumerate(output.content):
                    if block.type == "toolCall" and block.id == call_id:
                        stream.push(
                            ToolCallEndEvent(
                                content_index=i,
                                tool_call=block,
                                partial=output,
                            )
                        )
                        break

            # Handle usage
            elif event_type == "response.usage":
                usage = event.get("usage", {})
                output.usage = Usage(
                    input=usage.get("input_tokens", 0),
                    output=usage.get("output_tokens", 0),
                    cache_read=usage.get("cache_read_tokens", 0),
                    cache_write=usage.get("cache_write_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    cost={"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0},
                )
                calculate_cost(model, output.usage)

        # Finish any remaining block
        if current_block:
            if current_block.type == "text":
                stream.push(
                    TextEndEvent(
                        content_index=len(blocks) - 1,
                        content=current_block.text,
                        partial=output,
                    )
                )
            elif current_block.type == "thinking":
                stream.push(
                    ThinkingEndEvent(
                        content_index=len(blocks) - 1,
                        content=current_block.thinking,
                        partial=output,
                    )
                )

    return asyncio.ensure_future(process())


def stream_openai_codex_responses(
    model: Model,
    context: Context,
    options: OpenAICodexResponsesOptions | StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream completions from OpenAI Codex Responses API."""
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
            api_key = (getattr(options, "api_key", None) if options else None) or get_env_api_key(
                model.provider
            )
            if not api_key:
                raise ValueError(f"No API key for provider: {model.provider}")

            account_id = _extract_account_id(api_key)

            body = _build_request_body(model, context, options)
            if options and hasattr(options, "on_payload") and options.on_payload:
                next_body = await options.on_payload(body, model)
                if next_body is not None:
                    body = next_body

            body_json = json.dumps(body)

            sse_headers = _build_sse_headers(
                model.headers if hasattr(model, "headers") else None,
                getattr(options, "headers", None) if options else None,
                account_id,
                api_key,
                getattr(options, "session_id", None) if options else None,
            )

            url = _resolve_codex_url(model.base_url if hasattr(model, "base_url") else None)

            signal = getattr(options, "signal", None) if options else None

            # Fetch with retry logic
            import httpx

            response = None
            last_error = None

            for attempt in range(MAX_RETRIES + 1):
                if signal and getattr(signal, "aborted", False):
                    raise asyncio.CancelledError("Request was aborted")

                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(
                            url,
                            headers=sse_headers,
                            content=body_json,
                            timeout=300,
                        )

                        if resp.status_code < 400:
                            response = resp
                            break

                        error_text = resp.text
                        if attempt < MAX_RETRIES and _is_retryable_error(
                            resp.status_code, error_text
                        ):
                            delay_ms = BASE_DELAY_MS * (2**attempt)
                            await _sleep(delay_ms, signal)
                            continue

                        error_info = await _parse_error_response(resp)
                        raise Exception(error_info.get("friendly_message") or error_info["message"])

                except Exception as e:
                    last_error = e
                    if "aborted" in str(e).lower():
                        raise
                    if attempt < MAX_RETRIES:
                        delay_ms = BASE_DELAY_MS * (2**attempt)
                        await _sleep(delay_ms, signal)
                        continue
                    raise

            if not response:
                raise last_error or Exception("Failed after retries")

            stream.push(StartEvent(partial=output))

            # Parse SSE stream
            async def parse_sse(response: httpx.Response):
                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        idx = buffer.index("\n\n")
                        data_chunk = buffer[:idx]
                        buffer = buffer[idx + 2 :]

                        data_lines = []
                        for line in data_chunk.split("\n"):
                            if line.startswith("data:"):
                                data_lines.append(line[5:].strip())

                        if data_lines:
                            data = "\n".join(data_lines).strip()
                            if data and data != "[DONE]":
                                with contextlib.suppress(json.JSONDecodeError):
                                    yield json.loads(data)

            await _process_responses_stream(parse_sse(response), output, stream, model)

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


def stream_simple_openai_codex_responses(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple streaming interface for OpenAI Codex Responses."""
    api_key = (options.api_key if options else None) or get_env_api_key(model.provider)
    if not api_key:
        raise ValueError(f"No API key for provider: {model.provider}")

    base = build_base_options(model, options, api_key)

    reasoning_effort = None
    if options and options.reasoning:
        reasoning_effort = (
            options.reasoning if supports_xhigh(model) else clamp_reasoning(options.reasoning)
        )

    return stream_openai_codex_responses(
        model,
        context,
        OpenAICodexResponsesOptions(
            **{k: v for k, v in base.__dict__.items() if v is not None},
            reasoning_effort=reasoning_effort,
        ),
    )


__all__ = [
    "stream_openai_codex_responses",
    "stream_simple_openai_codex_responses",
    "OpenAICodexResponsesOptions",
]
