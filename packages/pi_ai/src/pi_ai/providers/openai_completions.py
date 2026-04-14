"""
OpenAI Completions provider with OpenRouter support.
Python port of TypeScript providers/openai-completions.ts
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types import (
        Context,
        Model,
        SimpleStreamOptions,
        StreamOptions,
        Tool,
    )

from ..event_stream import AssistantMessageEventStream
from ..models import calculate_cost, supports_xhigh
from ..types import (
    AssistantMessage,
    Cost,
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
from ..utils.http_pool import get_http_client
from ..utils.json_parse import parse_streaming_json
from .simple_options import build_base_options, clamp_reasoning
from .transform_messages import transform_messages


class OpenAICompletionsOptions:
    """Options for OpenAI Completions API."""

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
        tool_choice: str | dict[str, Any] | None = None,
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


def stream_openai_completions(
    model: Model,
    context: Context,
    options: OpenAICompletionsOptions | StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """
    Stream completions from OpenAI-compatible API.

    Supports OpenRouter, Vercel AI Gateway, and other OpenAI-compatible providers.
    """
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
                cost=Cost(),
            ),
            stop_reason=StopReason.STOP,
        )

        signal = None  # Initialize for exception handling

        try:
            import httpx

            api_key = getattr(options, "api_key", None) or get_env_api_key(model.provider) or ""
            _create_client(model, context, api_key, getattr(options, "headers", None))

            params = _build_params(model, context, options)

            if options and hasattr(options, "on_payload") and options.on_payload:
                next_params = await options.on_payload(params, model)
                if next_params is not None:
                    params = next_params

            # Make streaming request
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost",
                "X-Title": "PyHybrid",
            }
            if getattr(model, "headers", None):
                headers.update(model.headers)
            if getattr(options, "headers", None):
                headers.update(options.headers)

            signal = getattr(options, "signal", None) if options else None

            # Use shared HTTP client with connection pooling
            http_client = await get_http_client()

            async with http_client.stream(
                "POST",
                f"{model.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=params,
                timeout=300,
            ) as response:
                response.raise_for_status()

                stream.push(StartEvent(partial=output))

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
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Extract response ID
                    if chunk.get("id") and not output.response_id:
                        output.response_id = chunk["id"]

                    # Parse usage
                    if chunk.get("usage"):
                        output.usage = _parse_chunk_usage(chunk["usage"], model)

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    choice = choices[0]

                    # Check for usage in choice (some providers like Moonshot)
                    if not chunk.get("usage") and choice.get("usage"):
                        output.usage = _parse_chunk_usage(choice["usage"], model)

                    # Handle finish reason
                    finish_reason = choice.get("finish_reason")
                    if finish_reason:
                        stop_result = _map_stop_reason(finish_reason)
                        output.stop_reason = stop_result["stop_reason"]
                        if stop_result.get("error_message"):
                            output.error_message = stop_result["error_message"]

                    # Handle delta
                    delta = choice.get("delta", {})
                    if delta:
                        # Text content
                        content = delta.get("content")
                        if content:
                            if not current_block or current_block.type != "text":
                                _finish_current_block(stream, current_block, blocks, output)
                                current_block = TextContent(text="")
                                output.content.append(current_block)
                                stream.push(
                                    TextStartEvent(content_index=len(blocks) - 1, partial=output)
                                )

                            current_block.text += content
                            stream.push(
                                TextDeltaEvent(
                                    content_index=len(blocks) - 1,
                                    delta=content,
                                    partial=output,
                                )
                            )

                        # Reasoning content
                        reasoning = (
                            delta.get("reasoning_content")
                            or delta.get("reasoning")
                            or delta.get("reasoning_text")
                        )
                        if reasoning:
                            if not current_block or current_block.type != "thinking":
                                _finish_current_block(stream, current_block, blocks, output)
                                current_block = ThinkingContent(
                                    thinking="",
                                    thinking_signature="reasoning_content",
                                )
                                output.content.append(current_block)
                                stream.push(
                                    ThinkingStartEvent(
                                        content_index=len(blocks) - 1, partial=output
                                    )
                                )

                            current_block.thinking += reasoning
                            stream.push(
                                ThinkingDeltaEvent(
                                    content_index=len(blocks) - 1,
                                    delta=reasoning,
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
                                        ToolCallStartEvent(
                                            content_index=len(blocks) - 1, partial=output
                                        )
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

                        # Reasoning details (for encrypted reasoning)
                        reasoning_details = delta.get("reasoning_details")
                        if reasoning_details and isinstance(reasoning_details, list):
                            for detail in reasoning_details:
                                if (
                                    detail.get("type") == "reasoning.encrypted"
                                    and detail.get("id")
                                    and detail.get("data")
                                ):
                                    matching_tc = next(
                                        (
                                            b
                                            for b in output.content
                                            if b.type == "toolCall" and b.id == detail["id"]
                                        ),
                                        None,
                                    )
                                    if matching_tc:
                                        matching_tc.thought_signature = json.dumps(detail)

                _finish_current_block(stream, current_block, blocks, output)

            if signal and getattr(signal, "aborted", False):
                raise asyncio.CancelledError("Request was aborted")

            if output.stop_reason == StopReason.ABORTED:
                raise asyncio.CancelledError("Request was aborted")

            if output.stop_reason == StopReason.ERROR:
                raise Exception(output.error_message or "Provider returned an error stop reason")

            stream.push(DoneEvent(reason=output.stop_reason, message=output))
            stream.end()

        except Exception as error:
            # Clean up partial blocks
            for block in output.content:
                if hasattr(block, "index"):
                    delattr(block, "index")

            is_aborted = (signal and getattr(signal, "aborted", False)) or isinstance(
                error, asyncio.CancelledError
            )
            output.stop_reason = StopReason.ABORTED if is_aborted else StopReason.ERROR
            output.error_message = str(error)

            # Add raw metadata if available (from OpenRouter)
            if hasattr(error, "error") and hasattr(error.error, "metadata"):
                raw_metadata = error.error.metadata.get("raw")
                if raw_metadata:
                    output.error_message += f"\n{raw_metadata}"

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
    elif block.type == "thinking":
        stream.push(
            ThinkingEndEvent(
                content_index=block_index,
                content=block.thinking,
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


def stream_simple_openai_completions(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple streaming interface for OpenAI completions."""
    api_key = (options.api_key if options else None) or get_env_api_key(model.provider)
    if not api_key:
        raise ValueError(f"No API key for provider: {model.provider}")

    base = build_base_options(model, options, api_key)
    reasoning_effort = (
        options.reasoning
        if supports_xhigh(model)
        else clamp_reasoning(options.reasoning)
        if options
        else None
    )

    # Get tool_choice from options if it's OpenAICompletionsOptions
    tool_choice = getattr(options, "tool_choice", None)

    return stream_openai_completions(
        model,
        context,
        OpenAICompletionsOptions(
            **{k: v for k, v in base.__dict__.items() if v is not None},
            reasoning_effort=reasoning_effort,
            tool_choice=tool_choice,
        ),
    )


def _create_client(
    model: Model,
    context: Context,
    api_key: str | None,
    options_headers: dict[str, str] | None,
) -> dict[str, Any]:
    """Create client configuration."""
    if not api_key:
        api_key = __import__("os").environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY or pass it as an argument."
            )

    headers = dict(model.headers) if getattr(model, "headers", None) else {}

    # GitHub Copilot headers
    if model.provider == "github-copilot":
        has_images = any(
            isinstance(msg.content, list) and any(c.type == "image" for c in msg.content)
            for msg in context.messages
            if msg.role == "user"
        )
        # Import and use copilot headers if available
        try:
            from .github_copilot_headers import (
                build_copilot_dynamic_headers,
                has_copilot_vision_input,
            )

            copilot_headers = build_copilot_dynamic_headers(
                messages=context.messages,
                has_images=has_images,
            )
            headers.update(copilot_headers)
        except ImportError:
            pass

    if options_headers:
        headers.update(options_headers)

    return {
        "api_key": api_key,
        "base_url": model.base_url,
        "headers": headers,
    }


def _build_params(
    model: Model,
    context: Context,
    options: OpenAICompletionsOptions | StreamOptions | None,
) -> dict[str, Any]:
    """Build request parameters."""

    compat = _get_compat(model)
    messages = _convert_messages(model, context, compat)
    _maybe_add_openrouter_anthropic_cache_control(model, messages)

    params: dict[str, Any] = {
        "model": model.id,
        "messages": messages,
        "stream": True,
    }

    if compat.get("supports_usage_in_streaming", True):
        params["stream_options"] = {"include_usage": True}

    if compat.get("supports_store", True):
        params["store"] = False

    if options and hasattr(options, "max_tokens") and options.max_tokens:
        if compat.get("max_tokens_field") == "max_tokens":
            params["max_tokens"] = options.max_tokens
        else:
            params["max_completion_tokens"] = options.max_tokens

    if options and hasattr(options, "temperature") and options.temperature is not None:
        params["temperature"] = options.temperature

    if context.tools:
        params["tools"] = _convert_tools(context.tools, compat)
        if compat.get("zai_tool_stream"):
            params["tool_stream"] = True
    elif _has_tool_history(context.messages):
        params["tools"] = []

    if options and hasattr(options, "tool_choice") and options.tool_choice:
        params["tool_choice"] = options.tool_choice

    # Handle reasoning/thinking
    reasoning_effort = getattr(options, "reasoning_effort", None) if options else None

    thinking_format = compat.get("thinking_format", "openai")
    if (
        thinking_format == "zai"
        and model.reasoning
        or thinking_format == "qwen"
        and model.reasoning
    ):
        params["enable_thinking"] = bool(reasoning_effort)
    elif thinking_format == "qwen-chat-template" and model.reasoning:
        params["chat_template_kwargs"] = {"enable_thinking": bool(reasoning_effort)}
    elif thinking_format == "openrouter" and model.reasoning:
        # OpenRouter nested reasoning object
        if reasoning_effort:
            params["reasoning"] = {
                "effort": _map_reasoning_effort(
                    reasoning_effort, compat.get("reasoning_effort_map")
                ),
            }
        else:
            params["reasoning"] = {"effort": "none"}
    elif reasoning_effort and model.reasoning and compat.get("supports_reasoning_effort", True):
        params["reasoning_effort"] = _map_reasoning_effort(
            reasoning_effort, compat.get("reasoning_effort_map")
        )

    # OpenRouter provider routing
    if (
        "openrouter.ai" in model.base_url
        and model.compat
        and hasattr(model.compat, "open_router_routing")
    ):
        routing = model.compat.open_router_routing
        if routing:
            params["provider"] = {k: v for k, v in routing.__dict__.items() if v is not None}

    # Vercel AI Gateway routing
    if (
        "ai-gateway.vercel.sh" in model.base_url
        and model.compat
        and hasattr(model.compat, "vercel_gateway_routing")
    ):
        routing = model.compat.vercel_gateway_routing
        if routing:
            gateway_options = {}
            if routing.only:
                gateway_options["only"] = routing.only
            if routing.order:
                gateway_options["order"] = routing.order
            if gateway_options:
                params["providerOptions"] = {"gateway": gateway_options}

    return params


def _convert_messages(
    model: Model,
    context: Context,
    compat: dict[str, Any],
) -> list[dict[str, Any]]:
    """Convert messages to OpenAI format."""

    params: list[dict[str, Any]] = []

    def normalize_tool_call_id(id: str) -> str:
        """Normalize tool call ID."""
        if "|" in id:
            call_id = id.split("|")[0]
            return "".join(c if c.isalnum() or c in "_-" else "_" for c in call_id)[:40]
        if model.provider == "openai":
            return id[:40] if len(id) > 40 else id
        return id

    transformed = transform_messages(context.messages, model, normalize_tool_call_id)

    # Add system prompt
    if context.system:
        use_developer = model.reasoning and compat.get("supports_developer_role", True)
        role = "developer" if use_developer else "system"
        params.append({"role": role, "content": context.system})

    last_role: str | None = None

    for i, msg in enumerate(transformed):
        # Some providers don't allow user messages directly after tool results
        if (
            compat.get("requires_assistant_after_tool_result")
            and last_role == "tool"
            and msg.role == "user"
        ):
            params.append(
                {
                    "role": "assistant",
                    "content": "I have processed the tool results.",
                }
            )

        if msg.role == "user":
            if isinstance(msg.content, str):
                params.append({"role": "user", "content": msg.content})
            else:
                content = []
                for item in msg.content:
                    if item.type == "text":
                        content.append({"type": "text", "text": item.text})
                    else:
                        content.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{item.mime_type};base64,{item.data}"},
                            }
                        )
                if not model.input or "image" not in model.input:
                    content = [c for c in content if c.get("type") != "image_url"]
                if content:
                    params.append({"role": "user", "content": content})

        elif msg.role == "assistant":
            assistant_msg: dict[str, Any] = {"role": "assistant"}

            if compat.get("requires_assistant_after_tool_result"):
                assistant_msg["content"] = ""
            else:
                assistant_msg["content"] = None

            # Text blocks
            text_blocks = [b for b in msg.content if b.type == "text"]
            non_empty_text = [b for b in text_blocks if b.text and b.text.strip()]
            if non_empty_text:
                assistant_msg["content"] = "".join(b.text for b in non_empty_text)

            # Thinking blocks
            thinking_blocks = [b for b in msg.content if b.type == "thinking"]
            non_empty_thinking = [b for b in thinking_blocks if b.thinking and b.thinking.strip()]
            if non_empty_thinking:
                if compat.get("requires_thinking_as_text"):
                    thinking_text = "\n\n".join(b.thinking for b in non_empty_thinking)
                    if assistant_msg.get("content"):
                        assistant_msg["content"] = thinking_text + "\n\n" + assistant_msg["content"]
                    else:
                        assistant_msg["content"] = thinking_text
                else:
                    signature = non_empty_thinking[0].thinking_signature
                    if signature:
                        assistant_msg[signature] = "\n".join(b.thinking for b in non_empty_thinking)

            # Tool calls
            tool_calls = [b for b in msg.content if b.type == "toolCall"]
            if tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in tool_calls
                ]
                reasoning_details = [
                    json.loads(tc.thought_signature) for tc in tool_calls if tc.thought_signature
                ]
                if reasoning_details:
                    assistant_msg["reasoning_details"] = reasoning_details

            # Skip empty assistant messages
            content = assistant_msg.get("content")
            has_content = content and (
                isinstance(content, str)
                and len(content) > 0
                or isinstance(content, list)
                and len(content) > 0
            )
            if not has_content and not assistant_msg.get("tool_calls"):
                continue

            params.append(assistant_msg)

        elif msg.role == "toolResult":
            image_blocks = []
            j = i

            while j < len(transformed) and transformed[j].role == "toolResult":
                tool_msg = transformed[j]

                text_result = "\n".join(c.text for c in tool_msg.content if c.type == "text")
                has_images = any(c.type == "image" for c in tool_msg.content)

                tool_result_msg: dict[str, Any] = {
                    "role": "tool",
                    "content": text_result if text_result else "(see attached image)",
                    "tool_call_id": tool_msg.tool_call_id,
                }
                if compat.get("requires_tool_result_name") and tool_msg.tool_name:
                    tool_result_msg["name"] = tool_msg.tool_name

                params.append(tool_result_msg)

                if has_images and model.input and "image" in model.input:
                    for block in tool_msg.content:
                        if block.type == "image":
                            image_blocks.append(
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{block.mime_type};base64,{block.data}"
                                    },
                                }
                            )

                j += 1

            i = j - 1

            if image_blocks:
                if compat.get("requires_assistant_after_tool_result"):
                    params.append(
                        {
                            "role": "assistant",
                            "content": "I have processed the tool results.",
                        }
                    )
                params.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Attached image(s) from tool result:"},
                            *image_blocks,
                        ],
                    }
                )
                last_role = "user"
            else:
                last_role = "tool"

            continue

        last_role = msg.role

    return params


def _convert_tools(tools: list[Tool], compat: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert tools to OpenAI format."""
    result = []
    for tool in tools:
        tool_def: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        if compat.get("supports_strict_mode", True):
            tool_def["function"]["strict"] = False
        result.append(tool_def)
    return result


def _parse_chunk_usage(
    raw_usage: dict[str, Any],
    model: Model,
) -> Usage:
    """Parse usage from chunk."""
    prompt_tokens = raw_usage.get("prompt_tokens", 0)
    reported_cached = raw_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
    cache_write = raw_usage.get("prompt_tokens_details", {}).get("cache_write_tokens", 0)
    reasoning_tokens = raw_usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)

    # Normalize cache read (remove cache write from reported cached tokens)
    cache_read = max(0, reported_cached - cache_write) if cache_write > 0 else reported_cached

    input_tokens = max(0, prompt_tokens - cache_read - cache_write)
    output_tokens = raw_usage.get("completion_tokens", 0) + reasoning_tokens

    usage = Usage(
        input=input_tokens,
        output=output_tokens,
        cache_read=cache_read,
        cache_write=cache_write,
        total_tokens=input_tokens + output_tokens + cache_read + cache_write,
        cost={"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0},
    )
    calculate_cost(model, usage)
    return usage


def _map_stop_reason(reason: str | None) -> dict[str, Any]:
    """Map provider stop reason to our stop reason."""
    if reason is None:
        return {"stop_reason": StopReason.STOP}

    mapping = {
        "stop": {"stop_reason": StopReason.STOP},
        "end": {"stop_reason": StopReason.STOP},
        "length": {"stop_reason": StopReason.LENGTH},
        "function_call": {"stop_reason": StopReason.TOOL_USE},
        "tool_calls": {"stop_reason": StopReason.TOOL_USE},
        "content_filter": {
            "stop_reason": StopReason.ERROR,
            "error_message": "Provider finish_reason: content_filter",
        },
        "network_error": {
            "stop_reason": StopReason.ERROR,
            "error_message": "Provider finish_reason: network_error",
        },
    }

    return mapping.get(
        reason,
        {"stop_reason": StopReason.ERROR, "error_message": f"Provider finish_reason: {reason}"},
    )


def _detect_compat(model: Model) -> dict[str, Any]:
    """Detect compatibility settings from provider and baseUrl."""
    provider = model.provider
    base_url = model.base_url.lower()

    is_zai = provider == "zai" or "api.z.ai" in base_url

    is_non_standard = (
        provider == "cerebras"
        or "cerebras.ai" in base_url
        or provider == "xai"
        or "api.x.ai" in base_url
        or "chutes.ai" in base_url
        or "deepseek.com" in base_url
        or is_zai
        or provider == "opencode"
        or "opencode.ai" in base_url
    )

    use_max_tokens = "chutes.ai" in base_url
    is_grok = provider == "xai" or "api.x.ai" in base_url
    is_groq = provider == "groq" or "groq.com" in base_url

    reasoning_effort_map = {}
    if is_groq and "qwen/qwen3-32b" in model.id:
        reasoning_effort_map = {
            "minimal": "default",
            "low": "default",
            "medium": "default",
            "high": "default",
            "xhigh": "default",
        }

    thinking_format = (
        "zai"
        if is_zai
        else "openrouter"
        if provider == "openrouter" or "openrouter.ai" in base_url
        else "openai"
    )

    return {
        "supports_store": not is_non_standard,
        "supports_developer_role": not is_non_standard,
        "supports_reasoning_effort": not is_grok and not is_zai,
        "reasoning_effort_map": reasoning_effort_map,
        "supports_usage_in_streaming": True,
        "max_tokens_field": "max_tokens" if use_max_tokens else "max_completion_tokens",
        "requires_tool_result_name": False,
        "requires_assistant_after_tool_result": False,
        "requires_thinking_as_text": False,
        "thinking_format": thinking_format,
        "open_router_routing": {},
        "vercel_gateway_routing": {},
        "zai_tool_stream": False,
        "supports_strict_mode": True,
    }


def _get_compat(model: Model) -> dict[str, Any]:
    """Get resolved compatibility settings for a model."""
    detected = _detect_compat(model)

    if not model.compat:
        return detected

    # Override with explicit compat settings
    compat_dict = model.compat.__dict__ if hasattr(model.compat, "__dict__") else {}

    return {
        "supports_store": compat_dict.get("supports_store")
        if compat_dict.get("supports_store") is not None
        else detected["supports_store"],
        "supports_developer_role": compat_dict.get("supports_developer_role")
        if compat_dict.get("supports_developer_role") is not None
        else detected["supports_developer_role"],
        "supports_reasoning_effort": compat_dict.get("supports_reasoning_effort")
        if compat_dict.get("supports_reasoning_effort") is not None
        else detected["supports_reasoning_effort"],
        "reasoning_effort_map": compat_dict.get("reasoning_effort_map")
        or detected["reasoning_effort_map"],
        "supports_usage_in_streaming": compat_dict.get("supports_usage_in_streaming")
        if compat_dict.get("supports_usage_in_streaming") is not None
        else detected["supports_usage_in_streaming"],
        "max_tokens_field": compat_dict.get("max_tokens_field") or detected["max_tokens_field"],
        "requires_tool_result_name": compat_dict.get("requires_tool_result_name")
        if compat_dict.get("requires_tool_result_name") is not None
        else detected["requires_tool_result_name"],
        "requires_assistant_after_tool_result": compat_dict.get(
            "requires_assistant_after_tool_result"
        )
        if compat_dict.get("requires_assistant_after_tool_result") is not None
        else detected["requires_assistant_after_tool_result"],
        "requires_thinking_as_text": compat_dict.get("requires_thinking_as_text")
        if compat_dict.get("requires_thinking_as_text") is not None
        else detected["requires_thinking_as_text"],
        "thinking_format": compat_dict.get("thinking_format") or detected["thinking_format"],
        "open_router_routing": compat_dict.get("open_router_routing")
        or detected["open_router_routing"],
        "vercel_gateway_routing": compat_dict.get("vercel_gateway_routing")
        or detected["vercel_gateway_routing"],
        "zai_tool_stream": compat_dict.get("zai_tool_stream")
        if compat_dict.get("zai_tool_stream") is not None
        else detected["zai_tool_stream"],
        "supports_strict_mode": compat_dict.get("supports_strict_mode")
        if compat_dict.get("supports_strict_mode") is not None
        else detected["supports_strict_mode"],
    }


def _map_reasoning_effort(
    effort: str,
    reasoning_effort_map: dict[str, str] | None,
) -> str:
    """Map reasoning effort using provider-specific mapping."""
    if reasoning_effort_map and effort in reasoning_effort_map:
        return reasoning_effort_map[effort]
    return effort


def _maybe_add_openrouter_anthropic_cache_control(
    model: Model,
    messages: list[dict[str, Any]],
) -> None:
    """Add cache control for OpenRouter Anthropic models."""
    if model.provider != "openrouter" or not model.id.startswith("anthropic/"):
        return

    # Walk backwards to find last user/assistant message with text content
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") not in ("user", "assistant"):
            continue

        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = [
                {**{"type": "text", "text": content}, "cache_control": {"type": "ephemeral"}}
            ]
            return

        if not isinstance(content, list):
            continue

        for j in range(len(content) - 1, -1, -1):
            part = content[j]
            if isinstance(part, dict) and part.get("type") == "text":
                part["cache_control"] = {"type": "ephemeral"}
                return


__all__ = [
    "stream_openai_completions",
    "stream_simple_openai_completions",
    "OpenAICompletionsOptions",
]
