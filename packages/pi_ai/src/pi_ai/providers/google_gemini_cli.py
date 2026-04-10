"""
Google Gemini CLI provider - CLI-based interface to Gemini.
Python port of TypeScript providers/google-gemini-cli.ts
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

import contextlib

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
    Usage,
)
from .simple_options import build_base_options


class GoogleGeminiCLIStreamOptions:
    """Options for Google Gemini CLI."""

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
        gemini_cli_path: str | None = None,
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
        self.gemini_cli_path = gemini_cli_path


def _find_gemini_cli(path: str | None = None) -> str:
    """Find the Gemini CLI executable."""
    import os
    import shutil

    if path:
        return path

    # Check common locations
    cli_names = ["gemini", "gemini-cli", "google-gemini"]
    for name in cli_names:
        cli_path = shutil.which(name)
        if cli_path:
            return cli_path

    # Check npm global
    npm_bin = os.path.expanduser("~/.npm/bin/gemini")
    if os.path.exists(npm_bin):
        return npm_bin

    raise FileNotFoundError(
        "Gemini CLI not found. Please install it with: npm install -g @google/gemini-cli"
    )


def _convert_messages(context: Context) -> list[dict[str, Any]]:
    """Convert messages to Gemini CLI format."""
    messages: list[dict[str, Any]] = []

    for msg in context.messages:
        if msg.role == "user":
            if isinstance(msg.content, str):
                messages.append(
                    {
                        "role": "user",
                        "content": msg.content,
                    }
                )
            else:
                content_parts = []
                for item in msg.content:
                    if item.type == "text":
                        content_parts.append(item.text)
                    else:
                        content_parts.append(f"[Image: {item.mime_type}]")
                messages.append({"role": "user", "content": "\n".join(content_parts)})

        elif msg.role == "assistant":
            for block in msg.content:
                if block.type == "text":
                    if block.text:
                        messages.append(
                            {
                                "role": "model",
                                "content": block.text,
                            }
                        )
                elif block.type == "thinking":
                    # CLI doesn't support thinking natively
                    if block.thinking:
                        messages.append(
                            {
                                "role": "model",
                                "content": block.thinking,
                            }
                        )
                elif block.type == "toolCall":
                    # CLI doesn't support tool calls in chat format
                    pass

        elif msg.role == "toolResult":
            text_parts = [c.text for c in msg.content if c.type == "text"]
            text_result = "\n".join(text_parts)
            if text_result:
                messages.append(
                    {
                        "role": "user",
                        "content": f"Tool result: {text_result}",
                    }
                )

    return messages


def _convert_tools(tools: list[Any]) -> list[dict[str, Any]] | None:
    """Convert tools to Gemini CLI format."""
    if not tools:
        return None

    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in tools
    ]


def stream_google_gemini_cli(
    model: Model,
    context: Context,
    options: GoogleGeminiCLIStreamOptions | StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Stream completions from Google Gemini CLI."""
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
            import os
            import tempfile

            signal = getattr(options, "signal", None) if options else None
            cli_path = getattr(options, "gemini_cli_path", None) if options else None

            gemini_cli = _find_gemini_cli(cli_path)

            messages = _convert_messages(context)

            # Build CLI arguments
            args = [
                gemini_cli,
                "--model",
                model.id,
                "--format",
                "json",
            ]

            if options and hasattr(options, "temperature") and options.temperature is not None:
                args.extend(["--temperature", str(options.temperature)])

            if options and hasattr(options, "max_tokens") and options.max_tokens is not None:
                args.extend(["--max-output-tokens", str(options.max_tokens)])

            # Create a temporary file with the conversation
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(
                    {
                        "messages": messages,
                        "system": context.system,
                        "tools": _convert_tools(context.tools) if context.tools else None,
                    },
                    f,
                )
                temp_file = f.name

            args.extend(["--input", temp_file])

            stream.push(StartEvent(partial=output))

            # Run the CLI
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            current_block: TextContent | None = None
            blocks = output.content

            # Read output line by line
            buffer = ""
            while True:
                if signal and getattr(signal, "aborted", False):
                    process.terminate()
                    await process.wait()
                    raise asyncio.CancelledError("Request was aborted")

                try:
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=0.1)
                except TimeoutError:
                    if process.returncode is not None:
                        break
                    continue

                if not line:
                    if process.returncode is not None:
                        break
                    continue

                line_str = line.decode("utf-8", errors="replace")
                buffer += line_str

                # Try to parse JSON chunks
                try:
                    # Look for complete JSON objects
                    while True:
                        start = buffer.find("{")
                        if start == -1:
                            buffer = ""
                            break

                        # Find matching brace
                        depth = 0
                        end = start
                        for i, char in enumerate(buffer[start:]):
                            if char == "{":
                                depth += 1
                            elif char == "}":
                                depth -= 1
                                if depth == 0:
                                    end = start + i + 1
                                    break

                        if depth != 0:
                            break  # Incomplete JSON

                        json_str = buffer[start:end]
                        try:
                            chunk = json.loads(json_str)

                            if chunk.get("type") == "text":
                                text = chunk.get("text", "")
                                if not current_block or current_block.type != "text":
                                    if current_block:
                                        stream.push(
                                            TextEndEvent(
                                                content_index=len(blocks) - 1,
                                                content=current_block.text,
                                                partial=output,
                                            )
                                        )
                                    current_block = TextContent(text="")
                                    output.content.append(current_block)
                                    stream.push(
                                        TextStartEvent(
                                            content_index=len(blocks) - 1, partial=output
                                        )
                                    )

                                current_block.text += text
                                stream.push(
                                    TextDeltaEvent(
                                        content_index=len(blocks) - 1,
                                        delta=text,
                                        partial=output,
                                    )
                                )

                            elif chunk.get("type") == "usage":
                                usage_data = chunk.get("usage", {})
                                output.usage = Usage(
                                    input=usage_data.get("input_tokens", 0),
                                    output=usage_data.get("output_tokens", 0),
                                    cache_read=0,
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

                        except json.JSONDecodeError:
                            pass

                        buffer = buffer[end:]

                except Exception:
                    pass

            # Clean up temp file
            with contextlib.suppress(Exception):
                os.unlink(temp_file)

            if current_block:
                stream.push(
                    TextEndEvent(
                        content_index=len(blocks) - 1,
                        content=current_block.text,
                        partial=output,
                    )
                )

            # Check for errors
            stderr = await process.stderr.read()
            if stderr:
                error_str = stderr.decode("utf-8", errors="replace")
                if error_str and process.returncode != 0:
                    raise Exception(f"Gemini CLI error: {error_str}")

            if process.returncode != 0:
                raise Exception(f"Gemini CLI exited with code {process.returncode}")

            # Estimate usage if not provided
            if output.usage.total_tokens == 0:
                input_text = "\n".join(
                    msg.get("content", "") if isinstance(msg.get("content"), str) else ""
                    for msg in messages
                )
                output_text = "".join(
                    block.text for block in output.content if block.type == "text"
                )
                # Rough estimate: 1 token ≈ 4 characters
                input_tokens = len(input_text) // 4
                output_tokens = len(output_text) // 4
                output.usage = Usage(
                    input=input_tokens,
                    output=output_tokens,
                    cache_read=0,
                    cache_write=0,
                    total_tokens=input_tokens + output_tokens,
                    cost={"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0},
                )
                calculate_cost(model, output.usage)

            stream.push(DoneEvent(reason=StopReason.STOP, message=output))
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


def stream_simple_google_gemini_cli(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """Simple streaming interface for Google Gemini CLI."""
    base = build_base_options(model, options, None)

    thinking_config = None
    if options and options.reasoning and model.reasoning:
        thinking_config = {"enabled": True}
    elif model.reasoning:
        thinking_config = {"enabled": False}

    return stream_google_gemini_cli(
        model,
        context,
        GoogleGeminiCLIStreamOptions(
            **{k: v for k, v in base.__dict__.items() if v is not None},
            thinking=thinking_config,
        ),
    )


__all__ = [
    "stream_google_gemini_cli",
    "stream_simple_google_gemini_cli",
    "GoogleGeminiCLIStreamOptions",
]
