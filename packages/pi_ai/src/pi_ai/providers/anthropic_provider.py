"""
Anthropic provider for Claude models.
Python port of TypeScript providers/anthropic.ts
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types import (
        AssistantMessage,
        Context,
        ImageContent,
        Message,
        Model,
        SimpleStreamOptions,
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
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
    Usage,
)
from ..utils.env_api_keys import get_env_api_key
from ..utils.http_pool import get_http_client
from ..utils.json_parse import parse_streaming_json
from .simple_options import adjust_max_tokens_for_thinking, build_base_options
from .transform_messages import transform_messages


class AnthropicOptions:
    """Options for Anthropic API."""

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
        thinking_enabled: bool = True,
        thinking_budget_tokens: int | None = None,
        effort: str | None = None,  # "low", "medium", "high", "max"
        interleaved_thinking: bool = True,
        tool_choice: str | dict[str, Any] | None = None,
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
        self.thinking_enabled = thinking_enabled
        self.thinking_budget_tokens = thinking_budget_tokens
        self.effort = effort
        self.interleaved_thinking = interleaved_thinking
        self.tool_choice = tool_choice


# Stealth mode: Mimic Claude Code's tool naming exactly
CLAUDE_CODE_VERSION = "2.1.75"

CLADE_CODE_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Bash",
    "Grep",
    "Glob",
    "AskUserQuestion",
    "EnterPlanMode",
    "ExitPlanMode",
    "KillShell",
    "NotebookEdit",
    "Skill",
    "Task",
    "TaskOutput",
    "TodoWrite",
    "WebFetch",
    "WebSearch",
]

_CC_TOOL_LOOKUP = {t.lower(): t for t in CLADE_CODE_TOOLS}


def _to_claude_code_name(name: str) -> str:
    """Convert tool name to Claude Code canonical casing."""
    return _CC_TOOL_LOOKUP.get(name.lower(), name)


def _from_claude_code_name(name: str, tools: list[Tool] | None) -> str:
    """Convert from Claude Code name back to original."""
    if tools:
        lower_name = name.lower()
        matched = next((t for t in tools if t.name.lower() == lower_name), None)
        if matched:
            return matched.name
    return name


def _resolve_cache_retention(cache_retention: str | None) -> str:
    """Resolve cache retention preference."""
    if cache_retention:
        return cache_retention
    import os

    if os.environ.get("PI_CACHE_RETENTION") == "long":
        return "long"
    return "short"


def _get_cache_control(
    base_url: str, cache_retention: str | None
) -> tuple[str, dict[str, Any] | None]:
    """Get cache control configuration."""
    retention = _resolve_cache_retention(cache_retention)
    if retention == "none":
        return retention, None

    ttl = "1h" if retention == "long" and "api.anthropic.com" in base_url else None
    cache_control = {"type": "ephemeral"}
    if ttl:
        cache_control["ttl"] = ttl
    return retention, cache_control


def stream_anthropic(
    model: Model,
    context: Context,
    options: AnthropicOptions | StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream completions from Anthropic API."""
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
            api_key = getattr(options, "api_key", None) or get_env_api_key(model.provider) or ""

            # Create client configuration
            is_oauth = _is_oauth_token(api_key)
            client_config = _create_client(
                model,
                api_key,
                getattr(options, "interleaved_thinking", True),
                getattr(options, "headers", None),
            )

            params = _build_params(model, context, is_oauth, options)

            if options and hasattr(options, "on_payload") and options.on_payload:
                next_params = await options.on_payload(params, model)
                if next_params is not None:
                    params = next_params

            # Make streaming request using shared HTTP client with connection pooling
            headers = client_config["headers"]
            signal = getattr(options, "signal", None) if options else None

            stream.push(StartEvent(partial=output))

            # Use shared HTTP client with connection pooling
            http_client = await get_http_client()

            async with http_client.stream(
                "POST",
                f"{model.base_url.rstrip('/')}/v1/messages",
                headers=headers,
                json=params,
                timeout=300,
            ) as response:
                response.raise_for_status()

                # Track blocks
                blocks: list[Any] = []

                async for line in response.aiter_lines():
                    if signal and getattr(signal, "aborted", False):
                        raise asyncio.CancelledError("Request was aborted")

                    line = line.strip()
                    if not line.startswith("data: "):
                        continue

                    line = line[6:]
                    if line == "[DONE]":
                        break

                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type")

                    if event_type == "message_start":
                        msg = event.get("message", {})
                        output.response_id = msg.get("id")
                        usage = msg.get("usage", {})
                        output.usage.input = usage.get("input_tokens", 0)
                        output.usage.output = usage.get("output_tokens", 0)
                        output.usage.cache_read = usage.get("cache_read_input_tokens", 0)
                        output.usage.cache_write = usage.get("cache_creation_input_tokens", 0)
                        output.usage.total_tokens = (
                            output.usage.input
                            + output.usage.output
                            + output.usage.cache_read
                            + output.usage.cache_write
                        )
                        calculate_cost(model, output.usage)

                    elif event_type == "content_block_start":
                        block_type = event.get("content_block", {}).get("type")
                        index = event.get("index", 0)

                        if block_type == "text":
                            block = {"type": "text", "text": "", "index": index}
                            output.content.append(TextContent(text=""))
                            blocks.append(block)
                            stream.push(
                                TextStartEvent(
                                    content_index=len(output.content) - 1, partial=output
                                )
                            )

                        elif block_type == "thinking":
                            block = {
                                "type": "thinking",
                                "thinking": "",
                                "thinking_signature": "",
                                "index": index,
                            }
                            output.content.append(ThinkingContent(thinking=""))
                            blocks.append(block)
                            stream.push(
                                ThinkingStartEvent(
                                    content_index=len(output.content) - 1, partial=output
                                )
                            )

                        elif block_type == "redacted_thinking":
                            data = event.get("content_block", {}).get("data", "")
                            block = {
                                "type": "thinking",
                                "thinking": "[Reasoning redacted]",
                                "thinking_signature": data,
                                "redacted": True,
                                "index": index,
                            }
                            output.content.append(
                                ThinkingContent(
                                    thinking="[Reasoning redacted]",
                                    thinking_signature=data,
                                    redacted=True,
                                )
                            )
                            blocks.append(block)
                            stream.push(
                                ThinkingStartEvent(
                                    content_index=len(output.content) - 1, partial=output
                                )
                            )

                        elif block_type == "tool_use":
                            cb = event.get("content_block", {})
                            name = cb.get("name", "")
                            if is_oauth:
                                name = _from_claude_code_name(name, context.tools)
                            block = {
                                "type": "toolCall",
                                "id": cb.get("id", ""),
                                "name": name,
                                "arguments": cb.get("input", {}),
                                "partial_json": "",
                                "index": index,
                            }
                            output.content.append(
                                ToolCall(id=cb.get("id", ""), name=name, arguments={})
                            )
                            blocks.append(block)
                            stream.push(
                                ToolCallStartEvent(
                                    content_index=len(output.content) - 1, partial=output
                                )
                            )

                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        delta_type = delta.get("type")
                        index = event.get("index", 0)

                        if delta_type == "text_delta":
                            block_idx = next(
                                (i for i, b in enumerate(blocks) if b.get("index") == index), -1
                            )
                            if block_idx >= 0 and output.content[block_idx].type == "text":
                                text = delta.get("text", "")
                                output.content[block_idx].text += text
                                stream.push(
                                    TextDeltaEvent(
                                        content_index=block_idx, delta=text, partial=output
                                    )
                                )

                        elif delta_type == "thinking_delta":
                            block_idx = next(
                                (i for i, b in enumerate(blocks) if b.get("index") == index), -1
                            )
                            if block_idx >= 0 and output.content[block_idx].type == "thinking":
                                thinking = delta.get("thinking", "")
                                output.content[block_idx].thinking += thinking
                                stream.push(
                                    ThinkingDeltaEvent(
                                        content_index=block_idx, delta=thinking, partial=output
                                    )
                                )

                        elif delta_type == "input_json_delta":
                            block_idx = next(
                                (i for i, b in enumerate(blocks) if b.get("index") == index), -1
                            )
                            if block_idx >= 0 and output.content[block_idx].type == "toolCall":
                                partial_json = delta.get("partial_json", "")
                                blocks[block_idx]["partial_json"] += partial_json
                                output.content[block_idx].arguments = parse_streaming_json(
                                    blocks[block_idx]["partial_json"]
                                )
                                stream.push(
                                    ToolCallDeltaEvent(
                                        content_index=block_idx,
                                        delta=partial_json,
                                        partial=output,
                                    )
                                )

                        elif delta_type == "signature_delta":
                            block_idx = next(
                                (i for i, b in enumerate(blocks) if b.get("index") == index), -1
                            )
                            if block_idx >= 0 and output.content[block_idx].type == "thinking":
                                sig = delta.get("signature", "")
                                output.content[block_idx].thinking_signature = (
                                    output.content[block_idx].thinking_signature or ""
                                ) + sig

                    elif event_type == "content_block_stop":
                        index = event.get("index", 0)
                        block_idx = next(
                            (i for i, b in enumerate(blocks) if b.get("index") == index), -1
                        )

                        if block_idx >= 0:
                            block = blocks[block_idx]
                            block.pop("index", None)

                            if block["type"] == "text":
                                stream.push(
                                    TextEndEvent(
                                        content_index=block_idx,
                                        content=output.content[block_idx].text,
                                        partial=output,
                                    )
                                )
                            elif block["type"] == "thinking":
                                if block.get("redacted"):
                                    output.content[block_idx].redacted = True
                                stream.push(
                                    ThinkingEndEvent(
                                        content_index=block_idx,
                                        content=output.content[block_idx].thinking,
                                        partial=output,
                                    )
                                )
                            elif block["type"] == "toolCall":
                                output.content[block_idx].arguments = parse_streaming_json(
                                    block.get("partial_json", "")
                                )
                                stream.push(
                                    ToolCallEndEvent(
                                        content_index=block_idx,
                                        tool_call=output.content[block_idx],
                                        partial=output,
                                    )
                                )

                    elif event_type == "message_delta":
                        delta = event.get("delta", {})
                        if delta.get("stop_reason"):
                            output.stop_reason = _map_stop_reason(delta["stop_reason"])

                        usage = event.get("usage", {})
                        if usage.get("input_tokens") is not None:
                            output.usage.input = usage["input_tokens"]
                        if usage.get("output_tokens") is not None:
                            output.usage.output = usage["output_tokens"]
                        if usage.get("cache_read_input_tokens") is not None:
                            output.usage.cache_read = usage["cache_read_input_tokens"]
                        if usage.get("cache_creation_input_tokens") is not None:
                            output.usage.cache_write = usage["cache_creation_input_tokens"]

                        output.usage.total_tokens = (
                            output.usage.input
                            + output.usage.output
                            + output.usage.cache_read
                            + output.usage.cache_write
                        )
                        calculate_cost(model, output.usage)

            if signal and getattr(signal, "aborted", False):
                raise asyncio.CancelledError("Request was aborted")

            if output.stop_reason in (StopReason.ABORTED, StopReason.ERROR):
                raise Exception("An unknown error occurred")

            stream.push(DoneEvent(reason=output.stop_reason, message=output))
            stream.end()

        except Exception as error:
            # Clean up partial blocks
            for block in output.content:
                if hasattr(block, "index"):
                    delattr(block, "index")

            is_aborted = (
                options and hasattr(options, "signal") and getattr(options.signal, "aborted", False)
            ) or isinstance(error, asyncio.CancelledError)
            output.stop_reason = StopReason.ABORTED if is_aborted else StopReason.ERROR
            output.error_message = str(error)

            stream.push(ErrorEvent(reason=output.stop_reason, error=output))
            stream.end()

    asyncio.create_task(process())
    return stream


def stream_simple_anthropic(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple streaming interface for Anthropic."""
    api_key = (options.api_key if options else None) or get_env_api_key(model.provider)
    if not api_key:
        raise ValueError(f"No API key for provider: {model.provider}")

    base = build_base_options(model, options, api_key)

    if not options or not options.reasoning:
        return stream_anthropic(
            model,
            context,
            AnthropicOptions(
                **{k: v for k, v in base.__dict__.items() if v is not None},
                thinking_enabled=False,
            ),
        )

    # Check for adaptive thinking support
    if _supports_adaptive_thinking(model.id):
        effort = _map_thinking_level_to_effort(options.reasoning, model.id)
        return stream_anthropic(
            model,
            context,
            AnthropicOptions(
                **{k: v for k, v in base.__dict__.items() if v is not None},
                thinking_enabled=True,
                effort=effort,
            ),
        )

    # Budget-based thinking for older models
    adjusted = adjust_max_tokens_for_thinking(
        base.max_tokens or 0,
        model.max_tokens,
        options.reasoning,
        options.thinking_budgets,
    )

    return stream_anthropic(
        model,
        context,
        AnthropicOptions(
            **{k: v for k, v in base.__dict__.items() if v is not None},
            max_tokens=adjusted["max_tokens"],
            thinking_enabled=True,
            thinking_budget_tokens=adjusted["thinking_budget"],
        ),
    )


def _supports_adaptive_thinking(model_id: str) -> bool:
    """Check if model supports adaptive thinking (Opus 4.6 and Sonnet 4.6)."""
    mid = model_id.lower()
    return "opus-4-6" in mid or "opus-4.6" in mid or "sonnet-4-6" in mid or "sonnet-4.6" in mid


def _map_thinking_level_to_effort(level: str, model_id: str) -> str:
    """Map thinking level to Anthropic effort."""
    mapping = {
        "minimal": "low",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "xhigh": "max"
        if ("opus-4-6" in model_id.lower() or "opus-4.6" in model_id.lower())
        else "high",
    }
    return mapping.get(level, "high")


def _is_oauth_token(api_key: str) -> bool:
    """Check if API key is an OAuth token."""
    return "sk-ant-oat" in api_key


def _create_client(
    model: Model,
    api_key: str,
    interleaved_thinking: bool,
    options_headers: dict[str, str] | None,
    dynamic_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create Anthropic client configuration."""
    needs_interleaved_beta = interleaved_thinking and not _supports_adaptive_thinking(model.id)

    headers: dict[str, str] = {}

    # GitHub Copilot
    if model.provider == "github-copilot":
        beta_features = []
        if needs_interleaved_beta:
            beta_features.append("interleaved-thinking-2025-05-14")

        headers.update(
            {
                "accept": "application/json",
                "anthropic-dangerous-direct-browser-access": "true",
            }
        )
        if beta_features:
            headers["anthropic-beta"] = ",".join(beta_features)
        if model.headers:
            headers.update(model.headers)
        if dynamic_headers:
            headers.update(dynamic_headers)
        if options_headers:
            headers.update(options_headers)

        return {
            "api_key": None,
            "auth_token": api_key,
            "base_url": model.base_url,
            "headers": headers,
        }

    beta_features = ["fine-grained-tool-streaming-2025-05-14"]
    if needs_interleaved_beta:
        beta_features.append("interleaved-thinking-2025-05-14")

    # OAuth
    if _is_oauth_token(api_key):
        headers.update(
            {
                "accept": "application/json",
                "anthropic-dangerous-direct-browser-access": "true",
                "anthropic-beta": f"claude-code-20250219,oauth-2025-04-20,{','.join(beta_features)}",
                "user-agent": f"claude-cli/{CLAUDE_CODE_VERSION}",
                "x-app": "cli",
            }
        )
        if model.headers:
            headers.update(model.headers)
        if options_headers:
            headers.update(options_headers)

        return {
            "api_key": None,
            "auth_token": api_key,
            "base_url": model.base_url,
            "headers": headers,
        }

    # API key auth
    headers.update(
        {
            "accept": "application/json",
            "anthropic-dangerous-direct-browser-access": "true",
            "anthropic-beta": ",".join(beta_features),
            "x-api-key": api_key,
        }
    )
    if model.headers:
        headers.update(model.headers)
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
    is_oauth_token: bool,
    options: AnthropicOptions | StreamOptions | None,
) -> dict[str, Any]:
    """Build request parameters for Anthropic API."""
    _, cache_control = _get_cache_control(
        model.base_url, getattr(options, "cache_retention", None) if options else None
    )

    params: dict[str, Any] = {
        "model": model.id,
        "messages": _convert_messages(context.messages, model, is_oauth_token, cache_control),
        "max_tokens": getattr(options, "max_tokens", None) or (model.max_tokens // 3),
        "stream": True,
    }

    # System prompt
    if is_oauth_token:
        system = [
            {"type": "text", "text": "You are Claude Code, Anthropic's official CLI for Claude."},
        ]
        if cache_control:
            system[0]["cache_control"] = cache_control

        if context.system:
            sys_msg = {"type": "text", "text": context.system}
            if cache_control:
                sys_msg["cache_control"] = cache_control
            system.append(sys_msg)

        params["system"] = system
    elif context.system:
        sys_msg = {"type": "text", "text": context.system}
        if cache_control:
            sys_msg["cache_control"] = cache_control
        params["system"] = [sys_msg]

    # Temperature (incompatible with extended thinking)
    if options and hasattr(options, "temperature") and options.temperature is not None:
        if not (hasattr(options, "thinking_enabled") and options.thinking_enabled):
            params["temperature"] = options.temperature

    # Tools
    if context.tools:
        params["tools"] = _convert_tools(context.tools, is_oauth_token)

    # Thinking mode
    if model.reasoning:
        thinking_enabled = getattr(options, "thinking_enabled", None) if options else None
        if thinking_enabled:
            if _supports_adaptive_thinking(model.id):
                params["thinking"] = {"type": "adaptive"}
                effort = getattr(options, "effort", None)
                if effort:
                    params["output_config"] = {"effort": effort}
            else:
                budget = getattr(options, "thinking_budget_tokens", 1024)
                params["thinking"] = {"type": "enabled", "budget_tokens": budget}
        elif thinking_enabled is False:
            params["thinking"] = {"type": "disabled"}

    # Metadata
    if options and hasattr(options, "metadata") and options.metadata:
        user_id = options.metadata.get("user_id")
        if isinstance(user_id, str):
            params["metadata"] = {"user_id": user_id}

    # Tool choice
    if options and hasattr(options, "tool_choice") and options.tool_choice:
        tc = options.tool_choice
        if isinstance(tc, str):
            params["tool_choice"] = {"type": tc}
        else:
            params["tool_choice"] = tc

    return params


def _convert_messages(
    messages: list[Message],
    model: Model,
    is_oauth_token: bool,
    cache_control: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Convert messages to Anthropic format."""

    params: list[dict[str, Any]] = []

    def normalize_tool_call_id(id: str) -> str:
        """Normalize tool call ID to Anthropic format."""
        return "".join(c if c.isalnum() or c in "_-" else "_" for c in id)[:64]

    transformed = transform_messages(messages, model, normalize_tool_call_id)

    for i, msg in enumerate(transformed):
        if msg.role == "user":
            if isinstance(msg.content, str):
                if msg.content.strip():
                    params.append({"role": "user", "content": msg.content})
            else:
                blocks = []
                for item in msg.content:
                    if item.type == "text":
                        blocks.append({"type": "text", "text": item.text})
                    else:
                        blocks.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": item.mime_type,
                                    "data": item.data,
                                },
                            }
                        )

                if not model.input or "image" not in model.input:
                    blocks = [b for b in blocks if b.get("type") != "image"]
                blocks = [
                    b
                    for b in blocks
                    if not (b.get("type") == "text" and not b.get("text", "").strip())
                ]

                if blocks:
                    params.append({"role": "user", "content": blocks})

        elif msg.role == "assistant":
            blocks = []
            for block in msg.content:
                if block.type == "text":
                    if block.text.strip():
                        blocks.append({"type": "text", "text": block.text})
                elif block.type == "thinking":
                    if block.redacted:
                        blocks.append(
                            {"type": "redacted_thinking", "data": block.thinking_signature or ""}
                        )
                        continue
                    if not block.thinking.strip():
                        continue
                    if not block.thinking_signature:
                        blocks.append({"type": "text", "text": block.thinking})
                    else:
                        blocks.append(
                            {
                                "type": "thinking",
                                "thinking": block.thinking,
                                "signature": block.thinking_signature,
                            }
                        )
                elif block.type == "toolCall":
                    name = _to_claude_code_name(block.name) if is_oauth_token else block.name
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": name,
                            "input": block.arguments or {},
                        }
                    )

            if blocks:
                params.append({"role": "assistant", "content": blocks})

        elif msg.role == "toolResult":
            tool_results = []
            j = i
            while j < len(transformed) and transformed[j].role == "toolResult":
                tr = transformed[j]
                content = _convert_content_blocks(tr.content)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tr.tool_call_id,
                        "content": content,
                        "is_error": tr.is_error,
                    }
                )
                j += 1

            i = j - 1
            params.append({"role": "user", "content": tool_results})

    # Add cache_control to last user message
    if cache_control and params:
        last_msg = params[-1]
        if last_msg.get("role") == "user":
            content = last_msg.get("content")
            if isinstance(content, list) and content:
                last_block = content[-1]
                if last_block.get("type") in ("text", "image", "tool_result"):
                    last_block["cache_control"] = cache_control
            elif isinstance(content, str):
                last_msg["content"] = [
                    {"type": "text", "text": content, "cache_control": cache_control}
                ]

    return params


def _convert_content_blocks(
    content: list[TextContent | ImageContent],
) -> str | list[dict[str, Any]]:
    """Convert content blocks to Anthropic format."""
    has_images = any(c.type == "image" for c in content)

    if not has_images:
        return "\n".join(c.text for c in content if c.type == "text")

    blocks = []
    for block in content:
        if block.type == "text":
            blocks.append({"type": "text", "text": block.text})
        else:
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": block.mime_type,
                        "data": block.data,
                    },
                }
            )

    if not any(b.get("type") == "text" for b in blocks):
        blocks.insert(0, {"type": "text", "text": "(see attached image)"})

    return blocks


def _convert_tools(tools: list[Tool], is_oauth_token: bool) -> list[dict[str, Any]]:
    """Convert tools to Anthropic format."""
    return [
        {
            "name": _to_claude_code_name(tool.name) if is_oauth_token else tool.name,
            "description": tool.description,
            "input_schema": {
                "type": "object",
                "properties": tool.parameters.get("properties", {}),
                "required": tool.parameters.get("required", []),
            },
        }
        for tool in tools
    ]


def _map_stop_reason(reason: str) -> StopReason:
    """Map Anthropic stop reason to our stop reason."""
    mapping = {
        "end_turn": StopReason.STOP,
        "max_tokens": StopReason.LENGTH,
        "tool_use": StopReason.TOOL_USE,
        "refusal": StopReason.ERROR,
        "pause_turn": StopReason.STOP,
        "stop_sequence": StopReason.STOP,
        "sensitive": StopReason.ERROR,
    }
    return mapping.get(reason, StopReason.ERROR)


__all__ = [
    "stream_anthropic",
    "stream_simple_anthropic",
    "AnthropicOptions",
]
