"""
Google Generative AI provider for Gemini API.
Python port of TypeScript providers/google.ts
"""

from __future__ import annotations

import asyncio
import json
import re
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
from .simple_options import build_base_options, clamp_reasoning


class GoogleGenerativeAIOptions:
    """Options for Google Generative AI API."""

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
        thinking: dict[str, Any] | None = None,
        search: bool = False,
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
        self.thinking = thinking
        self.search = search


# Default API endpoint
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY_MS = 1000


def _extract_retry_delay(error_text: str, headers: dict[str, str] | None = None) -> int | None:
    """Extract retry delay from Gemini error response (in milliseconds)."""

    def normalize_delay(ms: float) -> int | None:
        return int(ms + 1000) if ms > 0 else None

    if headers:
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            try:
                retry_after_seconds = int(retry_after)
                delay = normalize_delay(retry_after_seconds * 1000)
                if delay:
                    return delay
            except ValueError:
                pass
            try:
                retry_after_date = int(retry_after)  # Assume it's a timestamp
                delay = normalize_delay(
                    retry_after_date * 1000 - int(asyncio.get_event_loop().time() * 1000)
                )
                if delay:
                    return delay
            except ValueError:
                pass

        rate_limit_reset = headers.get("x-ratelimit-reset")
        if rate_limit_reset:
            try:
                reset_seconds = int(rate_limit_reset)
                delay = normalize_delay(
                    reset_seconds * 1000 - int(asyncio.get_event_loop().time() * 1000)
                )
                if delay:
                    return delay
            except ValueError:
                pass

    # Pattern: "Your quota will reset after ..."
    duration_match = re.search(
        r"reset after (?:(\d+)h)?(?:(\d+)m)?(\d+(?:\.\d+)?)s", error_text, re.I
    )
    if duration_match:
        hours = int(duration_match.group(1) or 0)
        minutes = int(duration_match.group(2) or 0)
        seconds = float(duration_match.group(3))
        total_ms = ((hours * 60 + minutes) * 60 + seconds) * 1000
        delay = normalize_delay(total_ms)
        if delay:
            return delay

    # Pattern: "Please retry in X[ms|s]"
    retry_in_match = re.search(r"Please retry in ([0-9.]+)(ms|s)", error_text, re.I)
    if retry_in_match:
        value = float(retry_in_match.group(1))
        if value > 0:
            ms = value if retry_in_match.group(2).lower() == "ms" else value * 1000
            delay = normalize_delay(ms)
            if delay:
                return delay

    return None


def _is_retryable_error(status: int, error_text: str) -> bool:
    """Check if an error is retryable."""
    if status in (429, 500, 502, 503, 504):
        return True
    return bool(
        re.search(
            r"resource.?exhausted|rate.?limit|overloaded|service.?unavailable", error_text, re.I
        )
    )


def _extract_error_message(error_text: str) -> str:
    """Extract a clean error message from Google API error response."""
    try:
        parsed = json.loads(error_text)
        if parsed.get("error", {}).get("message"):
            return parsed["error"]["message"]
    except json.JSONDecodeError:
        pass
    return error_text


def _is_gemini_15_or_later(model_id: str) -> bool:
    """Check if model is Gemini 1.5 or later."""
    model_lower = model_id.lower()
    match = re.search(r"gemini(?:-live)?-(\d+)\.?(\d+)?", model_lower)
    if match:
        major = int(match.group(1))
        minor = int(match.group(2)) if match.group(2) else 0
        return major > 1 or (major == 1 and minor >= 5)
    return False


def _is_gemini_2_or_later(model_id: str) -> bool:
    """Check if model is Gemini 2.0 or later."""
    model_lower = model_id.lower()
    match = re.search(r"gemini(?:-live)?-(\d+)\.?(\d+)?", model_lower)
    if match:
        major = int(match.group(1))
        return major >= 2
    return False


def _requires_tool_call_id(model_id: str) -> bool:
    """Check if model requires explicit tool call IDs."""
    return model_id.startswith("claude-") or model_id.startswith("gpt-oss-")


def _is_valid_thought_signature(signature: str | None) -> bool:
    """Check if thought signature is valid base64."""
    if not signature:
        return False
    if len(signature) % 4 != 0:
        return False
    # Base64 pattern
    return bool(re.match(r"^[A-Za-z0-9+/]+={0,2}$", signature))


def _convert_messages(
    model: Model,
    context: Context,
) -> list[dict[str, Any]]:
    """Convert messages to Gemini Content[] format."""
    from .transform_messages import transform_messages

    contents: list[dict[str, Any]] = []

    def normalize_tool_call_id(id: str) -> str:
        if not _requires_tool_call_id(model.id):
            return id
        # Replace special chars with underscore, max 64 chars
        return re.sub(r"[^a-zA-Z0-9_-]", "_", id)[:64]

    transformed = transform_messages(context.messages, model, normalize_tool_call_id)

    for msg in transformed:
        if msg.role == "user":
            if isinstance(msg.content, str):
                contents.append(
                    {
                        "role": "user",
                        "parts": [{"text": msg.content}],
                    }
                )
            else:
                parts = []
                for item in msg.content:
                    if item.type == "text":
                        parts.append({"text": item.text})
                    else:
                        parts.append(
                            {
                                "inlineData": {
                                    "mimeType": item.mime_type,
                                    "data": item.data,
                                }
                            }
                        )
                # Filter out images if model doesn't support them
                if not model.capabilities.supports_vision:
                    parts = [p for p in parts if "text" in p]
                if parts:
                    contents.append({"role": "user", "parts": parts})

        elif msg.role == "assistant":
            parts = []
            is_same_model = msg.provider == model.provider and msg.model == model.id

            for block in msg.content:
                if block.type == "text":
                    if not block.text or block.text.strip() == "":
                        continue
                    part = {"text": block.text}
                    signature = (
                        block.text_signature
                        if is_same_model and _is_valid_thought_signature(block.text_signature)
                        else None
                    )
                    if signature:
                        part["thoughtSignature"] = signature
                    parts.append(part)

                elif block.type == "thinking":
                    if not block.thinking or block.thinking.strip() == "":
                        continue
                    if is_same_model:
                        signature = (
                            block.thinking_signature
                            if _is_valid_thought_signature(block.thinking_signature)
                            else None
                        )
                        part = {
                            "thought": True,
                            "text": block.thinking,
                        }
                        if signature:
                            part["thoughtSignature"] = signature
                        parts.append(part)
                    else:
                        parts.append({"text": block.thinking})

                elif block.type == "toolCall":
                    signature = (
                        block.thought_signature
                        if is_same_model and _is_valid_thought_signature(block.thought_signature)
                        else None
                    )
                    part = {
                        "functionCall": {
                            "name": block.name,
                            "args": block.arguments or {},
                        }
                    }
                    if _requires_tool_call_id(model.id):
                        part["functionCall"]["id"] = block.id

                    # Use skip_thought_signature_validator sentinel for unsigned function calls on Gemini 3
                    is_gemini_3 = "gemini-3" in model.id.lower()
                    effective_signature = signature or (
                        "skip_thought_signature_validator" if is_gemini_3 else None
                    )
                    if effective_signature:
                        part["thoughtSignature"] = effective_signature

                    parts.append(part)

            if parts:
                contents.append({"role": "model", "parts": parts})

        elif msg.role == "toolResult":
            text_content = [c for c in msg.content if c.type == "text"]
            text_result = "\n".join(c.text for c in text_content)
            image_content = (
                [c for c in msg.content if c.type == "image"]
                if model.capabilities.supports_vision
                else []
            )

            has_text = len(text_result) > 0
            has_images = len(image_content) > 0

            # Check if model supports multimodal function responses
            gemini_major = None
            match = re.search(r"^gemini(?:-live)?-(\d+)", model.id.lower())
            if match:
                gemini_major = int(match.group(1))
            supports_multimodal = (gemini_major is None) or (gemini_major >= 3)

            response_value = (
                text_result if has_text else "(see attached image)" if has_images else ""
            )

            image_parts = [
                {"inlineData": {"mimeType": img.mime_type, "data": img.data}}
                for img in image_content
            ]

            include_id = _requires_tool_call_id(model.id)
            function_response_part = {
                "functionResponse": {
                    "name": msg.tool_name,
                    "response": {"output": response_value}
                    if not msg.is_error
                    else {"error": response_value},
                }
            }
            if has_images and supports_multimodal:
                function_response_part["functionResponse"]["parts"] = image_parts
            if include_id:
                function_response_part["functionResponse"]["id"] = msg.tool_call_id

            # Merge with previous user turn if it has function responses
            if (
                contents
                and contents[-1].get("role") == "user"
                and any("functionResponse" in p for p in contents[-1].get("parts", []))
            ):
                contents[-1]["parts"].append(function_response_part)
            else:
                contents.append({"role": "user", "parts": [function_response_part]})

            # For Gemini < 3, add images in a separate user message
            if has_images and not supports_multimodal:
                contents.append(
                    {
                        "role": "user",
                        "parts": [{"text": "Tool result image:"}, *image_parts],
                    }
                )

    return contents


def _convert_tools(tools: list[Any]) -> list[dict[str, Any]] | None:
    """Convert tools to Gemini function declarations format."""
    if not tools:
        return None

    return [
        {
            "functionDeclarations": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parametersJsonSchema": tool.parameters,
                }
                for tool in tools
            ]
        }
    ]


def _map_stop_reason(reason: str) -> StopReason:
    """Map Gemini FinishReason to StopReason."""
    mapping = {
        "STOP": StopReason.STOP,
        "MAX_TOKENS": StopReason.LENGTH,
        "BLOCKLIST": StopReason.ERROR,
        "PROHIBITED_CONTENT": StopReason.ERROR,
        "SPII": StopReason.ERROR,
        "SAFETY": StopReason.ERROR,
        "IMAGE_SAFETY": StopReason.ERROR,
        "IMAGE_PROHIBITED_CONTENT": StopReason.ERROR,
        "IMAGE_RECITATION": StopReason.ERROR,
        "IMAGE_OTHER": StopReason.ERROR,
        "RECITATION": StopReason.ERROR,
        "FINISH_REASON_UNSPECIFIED": StopReason.ERROR,
        "OTHER": StopReason.ERROR,
        "LANGUAGE": StopReason.ERROR,
        "MALFORMED_FUNCTION_CALL": StopReason.ERROR,
        "UNEXPECTED_TOOL_CALL": StopReason.ERROR,
        "NO_IMAGE": StopReason.ERROR,
    }
    return mapping.get(reason, StopReason.ERROR)


def _build_request_body(
    model: Model,
    context: Context,
    options: GoogleGenerativeAIOptions | None,
) -> dict[str, Any]:
    """Build the request body for Gemini API."""
    contents = _convert_messages(model, context)

    generation_config: dict[str, Any] = {}
    if options and options.temperature is not None:
        generation_config["temperature"] = options.temperature
    if options and options.max_tokens is not None:
        generation_config["maxOutputTokens"] = options.max_tokens

    # Handle thinking configuration
    if options and options.thinking and options.thinking.get("enabled") and model.reasoning:
        generation_config["thinkingConfig"] = {"includeThoughts": True}
        if options.thinking.get("budgetTokens") is not None:
            generation_config["thinkingConfig"]["thinkingBudget"] = options.thinking["budgetTokens"]
    elif model.reasoning and options and options.thinking and not options.thinking.get("enabled"):
        # Disable thinking
        if _is_gemini_2_or_later(model.id):
            generation_config["thinkingConfig"] = {"thinkingBudget": 0}

    request_body: dict[str, Any] = {
        "contents": contents,
    }

    if context.system:
        request_body["systemInstruction"] = {"parts": [{"text": context.system}]}

    if generation_config:
        request_body["generationConfig"] = generation_config

    if context.tools:
        tools_declarations = _convert_tools(context.tools)
        if tools_declarations:
            request_body["tools"] = tools_declarations

    # Add search tool if enabled (for Gemini 2.0+ models)
    if options and options.search and _is_gemini_2_or_later(model.id):
        request_body["tools"] = request_body.get("tools", []) + [{"googleSearch": {}}]

    return request_body


def stream_google_generative_ai(
    model: Model,
    context: Context,
    options: GoogleGenerativeAIOptions | StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream completions from Google Generative AI API."""
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

            url = f"{base_url}/v1beta/models/{model.id}:streamGenerateContent?alt=sse&key={api_key}"

            headers = {
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
                                server_delay = _extract_retry_delay(error_str, dict(resp.headers))
                                delay_ms = server_delay or (BASE_DELAY_MS * (2**attempt))
                                max_delay = (
                                    getattr(options, "max_retry_delay_ms", 60000)
                                    if options
                                    else 60000
                                )
                                if max_delay > 0 and server_delay and server_delay > max_delay:
                                    raise Exception(
                                        f"Server requested {server_delay // 1000}s retry delay (max: {max_delay // 1000}s). {_extract_error_message(error_str)}"
                                    )
                                await asyncio.sleep(delay_ms / 1000)
                                continue

                            raise Exception(
                                f"Gemini API error ({resp.status_code}): {_extract_error_message(error_str)}"
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

            current_block: TextContent | ThinkingContent | (ToolCallType & dict) | None = None
            blocks = output.content
            tool_call_counter = 0

            async for line in response.aiter_lines():
                if signal and getattr(signal, "aborted", False):
                    raise asyncio.CancelledError("Request was aborted")

                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue

                data = line[6:].strip()
                if not data:
                    continue

                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                # Extract response ID
                if chunk.get("responseId") and not output.response_id:
                    output.response_id = chunk["responseId"]

                candidate = chunk.get("candidates", [{}])[0] if chunk.get("candidates") else None
                if not candidate:
                    continue

                content = candidate.get("content", {})
                parts = content.get("parts", [])

                for part in parts:
                    # Text content
                    if "text" in part:
                        text = part["text"]
                        is_thinking = part.get("thought") is True

                        if is_thinking:
                            if not current_block or current_block.type != "thinking":
                                _finish_current_block(stream, current_block, blocks, output)
                                current_block = ThinkingContent(
                                    thinking="",
                                    thinking_signature=part.get("thoughtSignature"),
                                )
                                output.content.append(current_block)
                                stream.push(
                                    ThinkingStartEvent(
                                        content_index=len(blocks) - 1, partial=output
                                    )
                                )

                            current_block.thinking += text
                            current_block.thinking_signature = (
                                part.get("thoughtSignature") or current_block.thinking_signature
                            )
                            stream.push(
                                ThinkingDeltaEvent(
                                    content_index=len(blocks) - 1,
                                    delta=text,
                                    partial=output,
                                )
                            )
                        else:
                            if not current_block or current_block.type != "text":
                                _finish_current_block(stream, current_block, blocks, output)
                                current_block = TextContent(
                                    text="", text_signature=part.get("thoughtSignature")
                                )
                                output.content.append(current_block)
                                stream.push(
                                    TextStartEvent(content_index=len(blocks) - 1, partial=output)
                                )

                            current_block.text += text
                            current_block.text_signature = (
                                part.get("thoughtSignature") or current_block.text_signature
                            )
                            stream.push(
                                TextDeltaEvent(
                                    content_index=len(blocks) - 1,
                                    delta=text,
                                    partial=output,
                                )
                            )

                    # Function call (tool call)
                    if "functionCall" in part:
                        func_call = part["functionCall"]
                        if current_block:
                            _finish_current_block(stream, current_block, blocks, output)
                            current_block = None

                        provided_id = func_call.get("id")
                        name = func_call.get("name", "")
                        tool_call_id = (
                            provided_id
                            or f"{name}_{int(asyncio.get_event_loop().time() * 1000)}_{tool_call_counter}"
                        )
                        tool_call_counter += 1

                        tc = {
                            "type": "toolCall",
                            "id": tool_call_id,
                            "name": name,
                            "arguments": func_call.get("args", {}),
                            "thought_signature": part.get("thoughtSignature"),
                        }
                        output.content.append(tc)
                        stream.push(
                            ToolCallStartEvent(content_index=len(blocks) - 1, partial=output)
                        )
                        stream.push(
                            ToolCallDeltaEvent(
                                content_index=len(blocks) - 1,
                                delta=json.dumps(tc["arguments"]),
                                partial=output,
                            )
                        )
                        tool_call_obj = ToolCallType(
                            type="toolCall",
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"],
                            thought_signature=tc.get("thought_signature"),
                        )
                        stream.push(
                            ToolCallEndEvent(
                                content_index=len(blocks) - 1,
                                tool_call=tool_call_obj,
                                partial=output,
                            )
                        )

                # Handle finish reason
                finish_reason = candidate.get("finishReason")
                if finish_reason:
                    output.stop_reason = _map_stop_reason(finish_reason)
                    if any(b.type == "toolCall" for b in output.content):
                        output.stop_reason = StopReason.TOOL_USE

                # Parse usage
                usage_metadata = chunk.get("usageMetadata", {})
                if usage_metadata:
                    prompt_tokens = usage_metadata.get("promptTokenCount", 0)
                    cache_read_tokens = usage_metadata.get("cachedContentTokenCount", 0)
                    output.usage = Usage(
                        input=prompt_tokens - cache_read_tokens,
                        output=usage_metadata.get("candidatesTokenCount", 0)
                        + usage_metadata.get("thoughtsTokenCount", 0),
                        cache_read=cache_read_tokens,
                        cache_write=0,
                        total_tokens=usage_metadata.get("totalTokenCount", 0),
                        cost={
                            "input": 0,
                            "output": 0,
                            "cache_read": 0,
                            "cache_write": 0,
                            "total": 0,
                        },
                    )
                    calculate_cost(model, output.usage)

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
    elif block.type == "thinking":
        stream.push(
            ThinkingEndEvent(
                content_index=block_index,
                content=block.thinking,
                partial=output,
            )
        )


def stream_simple_google_generative_ai(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple streaming interface for Google Generative AI."""
    api_key = (options.api_key if options else None) or get_env_api_key(model.provider)
    if not api_key:
        raise ValueError(f"No API key for provider: {model.provider}")

    base = build_base_options(model, options, api_key)

    thinking_config = None
    if options and options.reasoning and model.reasoning:
        budgets = options.thinking_budgets
        default_budgets = {"minimal": 1024, "low": 2048, "medium": 8192, "high": 16384}
        thinking_budget = default_budgets.get(clamp_reasoning(options.reasoning) or "medium", 8192)
        if budgets:
            if budgets.minimal is not None:
                default_budgets["minimal"] = budgets.minimal
            if budgets.low is not None:
                default_budgets["low"] = budgets.low
            if budgets.medium is not None:
                default_budgets["medium"] = budgets.medium
            if budgets.high is not None:
                default_budgets["high"] = budgets.high
            thinking_budget = default_budgets.get(
                clamp_reasoning(options.reasoning) or "medium", 8192
            )

        thinking_config = {
            "enabled": True,
            "budgetTokens": thinking_budget,
        }
    elif model.reasoning:
        thinking_config = {"enabled": False}

    return stream_google_generative_ai(
        model,
        context,
        GoogleGenerativeAIOptions(
            **{k: v for k, v in base.__dict__.items() if v is not None},
            thinking=thinking_config,
        ),
    )


# Aliases for register_builtins compatibility
stream_google = stream_google_generative_ai
stream_simple_google = stream_simple_google_generative_ai


__all__ = [
    "stream_google_generative_ai",
    "stream_simple_google_generative_ai",
    "stream_google",
    "stream_simple_google",
    "GoogleGenerativeAIOptions",
]
