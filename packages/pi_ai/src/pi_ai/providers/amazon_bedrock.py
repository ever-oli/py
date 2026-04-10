"""
Amazon Bedrock Converse API provider.
Python port of TypeScript providers/amazon-bedrock.ts
"""

from __future__ import annotations

import asyncio
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


class BedrockConverseOptions:
    """Options for Amazon Bedrock Converse API."""

    def __init__(
        self,
        temperature: float | None = None,
        max_tokens: int | None = None,
        signal: Any | None = None,
        api_key: str | None = None,  # Not used, but kept for consistency
        transport: str | None = None,
        cache_retention: str = "short",
        session_id: str | None = None,
        on_payload: Any = None,
        headers: dict[str, str] | None = None,
        max_retry_delay_ms: int = 60000,
        metadata: dict[str, Any] | None = None,
        reasoning_effort: str | None = None,
        # AWS-specific options
        aws_region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        aws_profile: str | None = None,
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
        self.aws_region = aws_region
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_session_token = aws_session_token
        self.aws_profile = aws_profile


# Retry configuration
MAX_RETRIES = 3
BASE_DELAY_MS = 1000


def _is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable."""
    error_str = str(error).lower()
    return (
        "throttling" in error_str
        or "serviceunavailable" in error_str
        or "internal server" in error_str
        or "provisioned throughput exceeded" in error_str
        or "model is not available" in error_str
    )


def _extract_error_message(error: Exception) -> str:
    """Extract error message from AWS error."""
    error_str = str(error)
    try:
        # Try to parse as JSON if it's an SDK error
        if hasattr(error, "response"):
            return error.response.get("Error", {}).get("Message", error_str)
    except Exception:
        pass
    return error_str


def _convert_messages(context: Context) -> list[dict[str, Any]]:
    """Convert messages to Bedrock format."""
    messages: list[dict[str, Any]] = []

    for msg in context.messages:
        if msg.role == "user":
            if isinstance(msg.content, str):
                messages.append(
                    {
                        "role": "user",
                        "content": [{"text": msg.content}],
                    }
                )
            else:
                content = []
                for item in msg.content:
                    if item.type == "text":
                        content.append({"text": item.text})
                    else:
                        content.append(
                            {
                                "image": {
                                    "format": item.mime_type.replace("image/", ""),
                                    "source": {"bytes": item.data},
                                }
                            }
                        )
                messages.append({"role": "user", "content": content})

        elif msg.role == "assistant":
            content = []

            for block in msg.content:
                if block.type == "text":
                    if block.text:
                        content.append({"text": block.text})
                elif block.type == "thinking":
                    # Bedrock doesn't support thinking natively for most models
                    # Some models like Claude support reasoning_text
                    if block.thinking:
                        content.append({"text": block.thinking})
                elif block.type == "toolCall":
                    content.append(
                        {
                            "toolUse": {
                                "toolUseId": block.id,
                                "name": block.name,
                                "input": block.arguments,
                            }
                        }
                    )

            if content:
                messages.append({"role": "assistant", "content": content})

        elif msg.role == "toolResult":
            text_parts = [c.text for c in msg.content if c.type == "text"]
            text_result = "\n".join(text_parts)

            content = [
                {
                    "toolResult": {
                        "toolUseId": msg.tool_call_id,
                        "content": [{"text": text_result}]
                        if text_result
                        else [{"text": "(see attached image)"}],
                        "status": "error" if msg.is_error else "success",
                    }
                }
            ]

            messages.append({"role": "user", "content": content})

    return messages


def _convert_tools(tools: list[Tool]) -> list[dict[str, Any]] | None:
    """Convert tools to Bedrock format."""
    if not tools:
        return None

    return [
        {
            "toolSpec": {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": {"json": tool.parameters},
            }
        }
        for tool in tools
    ]


def _map_stop_reason(reason: str) -> StopReason:
    """Map Bedrock stop reason to StopReason."""
    mapping = {
        "end_turn": StopReason.STOP,
        "tool_use": StopReason.TOOL_USE,
        "max_tokens": StopReason.LENGTH,
        "stop_sequence": StopReason.STOP,
        "content_filtered": StopReason.ERROR,
    }
    return mapping.get(reason, StopReason.ERROR)


def _build_request_body(
    model: Model,
    context: Context,
    options: BedrockConverseOptions | None,
) -> dict[str, Any]:
    """Build the request body for Bedrock Converse API."""
    messages = _convert_messages(context)

    inference_config: dict[str, Any] = {}
    if options and options.temperature is not None:
        inference_config["temperature"] = options.temperature
    if options and options.max_tokens is not None:
        inference_config["maxTokens"] = options.max_tokens

    request_body: dict[str, Any] = {
        "modelId": model.id,
        "messages": messages,
    }

    if context.system:
        request_body["system"] = [{"text": context.system}]

    if inference_config:
        request_body["inferenceConfig"] = inference_config

    if context.tools:
        tools_declarations = _convert_tools(context.tools)
        if tools_declarations:
            request_body["toolConfig"] = {"tools": tools_declarations}

    return request_body


def stream_bedrock_converse(
    model: Model,
    context: Context,
    options: BedrockConverseOptions | StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream completions from Amazon Bedrock Converse API."""
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
            signal = getattr(options, "signal", None) if options else None

            # Try to import boto3
            try:
                import boto3
                from botocore.exceptions import ClientError
            except ImportError:
                raise ImportError(
                    "boto3 is required for Amazon Bedrock support. "
                    "Install it with: pip install boto3"
                )

            # Configure boto3 client
            kwargs = {}

            # Get region from options, env, or model config
            region = (
                getattr(options, "aws_region", None)
                if options
                else None or model.compat.get("aws_region")
                if model.compat
                else None or get_env_api_key("aws_region") or "us-east-1"
            )
            kwargs["region_name"] = region

            # Get credentials from options or env
            access_key = getattr(options, "aws_access_key_id", None) if options else None
            secret_key = getattr(options, "aws_secret_access_key", None) if options else None
            session_token = getattr(options, "aws_session_token", None) if options else None

            if access_key and secret_key:
                kwargs["aws_access_key_id"] = access_key
                kwargs["aws_secret_access_key"] = secret_key
                if session_token:
                    kwargs["aws_session_token"] = session_token

            profile = getattr(options, "aws_profile", None) if options else None
            if profile:
                kwargs["profile_name"] = profile

            bedrock = boto3.client("bedrock-runtime", **kwargs)

            request_body = _build_request_body(model, context, options)

            if options and hasattr(options, "on_payload") and options.on_payload:
                next_body = await options.on_payload(request_body, model)
                if next_body is not None:
                    request_body = next_body

            stream.push(StartEvent(partial=output))

            current_block: TextContent | (ToolCallType & dict) | None = None
            blocks = output.content

            # Make streaming request
            response = None
            last_error = None

            for attempt in range(MAX_RETRIES + 1):
                if signal and getattr(signal, "aborted", False):
                    raise asyncio.CancelledError("Request was aborted")

                try:
                    response = bedrock.converse_stream(
                        modelId=request_body["modelId"],
                        messages=request_body.get("messages", []),
                        system=request_body.get("system"),
                        inferenceConfig=request_body.get("inferenceConfig"),
                        toolConfig=request_body.get("toolConfig"),
                    )
                    break
                except ClientError as e:
                    last_error = e
                    error_code = e.response.get("Error", {}).get("Code", "Unknown")

                    if error_code in ["ThrottlingException", "ServiceUnavailableException"]:
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(BASE_DELAY_MS * (2**attempt) / 1000)
                            continue
                    raise
                except Exception as e:
                    last_error = e
                    if _is_retryable_error(e) and attempt < MAX_RETRIES:
                        await asyncio.sleep(BASE_DELAY_MS * (2**attempt) / 1000)
                        continue
                    raise

            if not response:
                raise last_error or Exception("Failed to get response after retries")

            # Process streaming response
            stream_response = response.get("stream", [])

            for event in stream_response:
                if signal and getattr(signal, "aborted", False):
                    raise asyncio.CancelledError("Request was aborted")

                # Message start
                if "messageStart" in event:
                    event["messageStart"].get("role")

                # Content block start
                elif "contentBlockStart" in event:
                    block_start = event["contentBlockStart"]
                    block_start.get("contentBlockIndex", 0)
                    tool_use_start = block_start.get("start", {}).get("toolUse")

                    if tool_use_start:
                        current_block = {
                            "type": "toolCall",
                            "id": tool_use_start.get("toolUseId", ""),
                            "name": tool_use_start.get("name", ""),
                            "arguments": {},
                            "partial_input": "",
                        }
                        output.content.append(current_block)
                        stream.push(
                            ToolCallStartEvent(content_index=len(blocks) - 1, partial=output)
                        )
                    else:
                        current_block = TextContent(text="")
                        output.content.append(current_block)
                        stream.push(TextStartEvent(content_index=len(blocks) - 1, partial=output))

                # Content block delta
                elif "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]
                    delta_data = delta.get("delta", {})

                    if "text" in delta_data and current_block and current_block.type == "text":
                        text_delta = delta_data["text"]
                        current_block.text += text_delta
                        stream.push(
                            TextDeltaEvent(
                                content_index=len(blocks) - 1,
                                delta=text_delta,
                                partial=output,
                            )
                        )

                    elif (
                        "toolUse" in delta_data
                        and current_block
                        and current_block.get("type") == "toolCall"
                    ):
                        tool_use_delta = delta_data["toolUse"]
                        if tool_use_delta.get("input"):
                            input_delta = tool_use_delta["input"]
                            current_block["partial_input"] += input_delta
                            current_block["arguments"] = parse_streaming_json(
                                current_block["partial_input"]
                            )
                            stream.push(
                                ToolCallDeltaEvent(
                                    content_index=len(blocks) - 1,
                                    delta=input_delta,
                                    partial=output,
                                )
                            )

                # Content block stop
                elif "contentBlockStop" in event:
                    if current_block:
                        if current_block.type == "text":
                            stream.push(
                                TextEndEvent(
                                    content_index=len(blocks) - 1,
                                    content=current_block.text,
                                    partial=output,
                                )
                            )
                        elif current_block.get("type") == "toolCall":
                            current_block["arguments"] = parse_streaming_json(
                                current_block.get("partial_input", "{}")
                            )
                            current_block.pop("partial_input", None)
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

                # Message stop
                elif "messageStop" in event:
                    stop_reason = event["messageStop"].get("stopReason")
                    if stop_reason:
                        output.stop_reason = _map_stop_reason(stop_reason)

                # Metadata (usage)
                elif "metadata" in event:
                    metadata = event["metadata"]
                    usage_data = metadata.get("usage", {})
                    if usage_data:
                        output.usage = Usage(
                            input=usage_data.get("inputTokens", 0),
                            output=usage_data.get("outputTokens", 0),
                            cache_read=0,
                            cache_write=0,
                            total_tokens=usage_data.get("totalTokens", 0),
                            cost={
                                "input": 0,
                                "output": 0,
                                "cache_read": 0,
                                "cache_write": 0,
                                "total": 0,
                            },
                        )
                        calculate_cost(model, output.usage)

                    # Response ID from metadata
                    trace_id = metadata.get("traceId")
                    if trace_id:
                        output.response_id = trace_id

                # Exceptions (errors)
                elif "internalServerException" in event:
                    raise Exception(
                        f"Bedrock internal server error: {event['internalServerException']}"
                    )
                elif "modelStreamErrorException" in event:
                    raise Exception(
                        f"Bedrock model stream error: {event['modelStreamErrorException']}"
                    )
                elif "throttlingException" in event:
                    raise Exception(f"Bedrock throttling error: {event['throttlingException']}")
                elif "validationException" in event:
                    raise Exception(f"Bedrock validation error: {event['validationException']}")

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


def stream_simple_bedrock_converse(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple streaming interface for Amazon Bedrock."""
    return stream_bedrock_converse(
        model,
        context,
        BedrockConverseOptions(
            temperature=options.temperature if options else None,
            max_tokens=options.max_tokens if options else None,
            signal=options.signal if options else None,
            cache_retention=options.cache_retention if options else "short",
            session_id=options.session_id if options else None,
            on_payload=options.on_payload if options else None,
            headers=options.headers if options else None,
            max_retry_delay_ms=options.max_retry_delay_ms if options else 60000,
            metadata=options.metadata if options else None,
            reasoning_effort=options.reasoning if options else None,
        ),
    )


# Aliases for register_builtins compatibility
stream_bedrock = stream_bedrock_converse
stream_simple_bedrock = stream_simple_bedrock_converse


__all__ = [
    "stream_bedrock_converse",
    "stream_simple_bedrock_converse",
    "stream_bedrock",
    "stream_simple_bedrock",
    "BedrockConverseOptions",
]
