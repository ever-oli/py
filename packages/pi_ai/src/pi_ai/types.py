"""Pi AI - Core types for LLM provider abstraction layer.

Ported from pi-mono/packages/ai/src/types.ts
"""

from __future__ import annotations

from collections.abc import AsyncIterable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import (
    Any,
    Generic,
    Literal,
    TypeVar,
)

# ============================================================================
# API and Provider Identifiers
# ============================================================================

KnownApi = Literal[
    "openai-completions",
    "mistral-conversations",
    "openai-responses",
    "azure-openai-responses",
    "openai-codex-responses",
    "anthropic-messages",
    "bedrock-converse-stream",
    "google-generative-ai",
    "google-gemini-cli",
    "google-vertex",
]

Api = str  # KnownApi or any string

KnownProvider = Literal[
    "amazon-bedrock",
    "anthropic",
    "google",
    "google-gemini-cli",
    "google-antigravity",
    "google-vertex",
    "openai",
    "azure-openai-responses",
    "openai-codex",
    "github-copilot",
    "xai",
    "groq",
    "cerebras",
    "openrouter",
    "vercel-ai-gateway",
    "zai",
    "mistral",
    "minimax",
    "minimax-cn",
    "huggingface",
    "opencode",
    "opencode-go",
    "kimi-coding",
]

Provider = str  # KnownProvider or any string

# Type variable for Model generic
TApi = TypeVar("TApi", bound=str)


class ThinkingLevel(StrEnum):
    """Reasoning/thinking effort levels."""

    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


class CacheRetention(StrEnum):
    """Prompt cache retention preferences."""

    NONE = "none"
    SHORT = "short"
    LONG = "long"


class Transport(StrEnum):
    """Transport protocols for streaming."""

    SSE = "sse"
    WEBSOCKET = "websocket"
    AUTO = "auto"


# ============================================================================
# Thinking Budgets
# ============================================================================


@dataclass
class ThinkingBudgets:
    """Token budgets for each thinking level (token-based providers only)."""

    minimal: int | None = None
    low: int | None = None
    medium: int | None = None
    high: int | None = None


# ============================================================================
# Stream Options
# ============================================================================


@dataclass
class StreamOptions:
    """Base options for all providers."""

    temperature: float | None = None
    max_tokens: int | None = None
    signal: Callable[[], bool] | None = None  # Cancellation check
    api_key: str | None = None
    transport: Transport = Transport.AUTO
    cache_retention: CacheRetention = CacheRetention.SHORT
    session_id: str | None = None
    # Callback for inspecting/modifying payload
    on_payload: Callable[[dict, Model], dict | None] | None = None
    headers: dict[str, str] | None = None
    max_retry_delay_ms: int = 60000
    metadata: dict[str, Any] | None = None


@dataclass
class SimpleStreamOptions(StreamOptions):
    """Options for simple stream API with reasoning."""

    reasoning: ThinkingLevel | None = None
    thinking_budgets: ThinkingBudgets | None = None


# ============================================================================
# Content Types
# ============================================================================


@dataclass
class TextSignatureV1:
    """Text signature for OpenAI responses."""

    v: Literal[1] = 1
    id: str = ""
    phase: Literal["commentary", "final_answer"] | None = None


@dataclass
class TextContent:
    """Text content block."""

    type: Literal["text"] = "text"
    text: str = ""
    text_signature: str | None = None  # JSON of TextSignatureV1 or legacy ID


@dataclass
class ThinkingContent:
    """Thinking/reasoning content block."""

    type: Literal["thinking"] = "thinking"
    thinking: str = ""
    thinking_signature: str | None = None
    redacted: bool = False


@dataclass
class ImageContent:
    """Image content block (base64 encoded)."""

    type: Literal["image"] = "image"
    data: str = ""  # base64 encoded
    mime_type: str = ""  # e.g., "image/jpeg"


@dataclass
class ToolCall:
    """Tool call from assistant."""

    type: Literal["toolCall"] = "toolCall"
    id: str = ""
    name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    thought_signature: str | None = None  # Google-specific


Content = TextContent | ThinkingContent | ImageContent | ToolCall


# ============================================================================
# Usage and Stop Reasons
# ============================================================================


@dataclass
class Cost:
    """Cost breakdown for API call."""

    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0
    total: float = 0.0


@dataclass
class Usage:
    """Token usage statistics."""

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0
    cost: Cost = field(default_factory=Cost)


class StopReason(StrEnum):
    """Reason for stream completion."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_USE = "toolUse"
    ERROR = "error"
    ABORTED = "aborted"


# ============================================================================
# Messages
# ============================================================================


@dataclass
class UserMessage:
    """User input message."""

    role: Literal["user"] = "user"
    content: str | list[TextContent | ImageContent] = field(default_factory=str)
    timestamp: int = 0  # Unix ms


@dataclass
class AssistantMessage:
    """Assistant response message."""

    role: Literal["assistant"] = "assistant"
    content: list[TextContent | ThinkingContent | ToolCall] = field(default_factory=list)
    api: Api = ""
    provider: Provider = ""
    model: str = ""
    response_id: str | None = None
    usage: Usage = field(default_factory=Usage)
    stop_reason: StopReason = StopReason.STOP
    error_message: str | None = None
    timestamp: int = 0  # Unix ms


@dataclass
class ToolResultMessage:
    """Tool result message for function calling results."""

    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: Any | None = None
    is_error: bool = False
    timestamp: int = 0  # Unix ms


Message = UserMessage | AssistantMessage | ToolResultMessage


# ============================================================================
# Context
# ============================================================================


@dataclass
class Context:
    """Conversation context for API calls."""

    messages: list[Message] = field(default_factory=list)
    tools: list[Tool] = field(default_factory=list)
    system: str | None = None


# ============================================================================
# Tool Definition
# ============================================================================


@dataclass
class Tool:
    """Tool definition for function calling."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema


# ============================================================================
# Model Definition
# ============================================================================


@dataclass
class ModelCapabilities:
    """Model capability flags."""

    supports_tools: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    supports_streaming: bool = True
    supports_reasoning: bool = False
    supports_cache_control: bool = False


@dataclass
class ModelPricing:
    """Per-token pricing."""

    input: float = 0.0
    output: float = 0.0
    cache_read: float = 0.0
    cache_write: float = 0.0


@dataclass
class Model(Generic[TApi]):
    """Model configuration."""

    id: str
    api: TApi
    provider: Provider
    name: str = ""
    base_url: str | None = None
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    pricing: ModelPricing = field(default_factory=ModelPricing)
    context_window: int = 8192
    compat: dict[str, Any] | None = None  # Provider-specific compatibility options
    reasoning: bool = False  # Supports reasoning/thinking


# ============================================================================
# Stream Events
# ============================================================================


class EventType(StrEnum):
    """Stream event types."""

    TEXT = "text"
    THINKING = "thinking"
    TOOL_CALL = "toolCall"
    USAGE = "usage"
    ERROR = "error"
    END = "end"
    START = "start"
    DONE = "done"


# ============================================================================
# Base Events
# ============================================================================


@dataclass
class StartEvent:
    """Stream start event."""

    type: Literal[EventType.START] = EventType.START
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class DoneEvent:
    """Stream done event."""

    type: Literal[EventType.DONE] = EventType.DONE
    reason: StopReason = StopReason.STOP
    message: AssistantMessage = field(default_factory=lambda: AssistantMessage())


# ============================================================================
# Text Events
# ============================================================================


@dataclass
class TextStartEvent:
    """Text block start event."""

    type: Literal[EventType.TEXT] = EventType.TEXT
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class TextDeltaEvent:
    """Text delta event."""

    type: Literal[EventType.TEXT] = EventType.TEXT
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class TextEndEvent:
    """Text block end event."""

    type: Literal[EventType.TEXT] = EventType.TEXT
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


# ============================================================================
# Thinking Events
# ============================================================================


@dataclass
class ThinkingStartEvent:
    """Thinking block start event."""

    type: Literal[EventType.THINKING] = EventType.THINKING
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class ThinkingDeltaEvent:
    """Thinking delta event."""

    type: Literal[EventType.THINKING] = EventType.THINKING
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class ThinkingEndEvent:
    """Thinking block end event."""

    type: Literal[EventType.THINKING] = EventType.THINKING
    content_index: int = 0
    content: str = ""
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


# ============================================================================
# Tool Call Events
# ============================================================================


@dataclass
class ToolCallStartEvent:
    """Tool call block start event."""

    type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    content_index: int = 0
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class ToolCallDeltaEvent:
    """Tool call delta event."""

    type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    content_index: int = 0
    delta: str = ""
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class ToolCallEndEvent:
    """Tool call block end event."""

    type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    content_index: int = 0
    tool_call: ToolCall = field(default_factory=lambda: ToolCall())
    partial: AssistantMessage = field(default_factory=lambda: AssistantMessage())


# ============================================================================
# Legacy Events (for backward compatibility)
# ============================================================================


@dataclass
class TextEvent:
    """Text delta event (legacy)."""

    type: Literal[EventType.TEXT] = EventType.TEXT
    text: str = ""


@dataclass
class ThinkingEvent:
    """Thinking delta event (legacy)."""

    type: Literal[EventType.THINKING] = EventType.THINKING
    thinking: str = ""


@dataclass
class ToolCallEvent:
    """Tool call event (legacy)."""

    type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    tool_call: ToolCall = field(default_factory=lambda: ToolCall())


@dataclass
class UsageEvent:
    """Usage update event."""

    type: Literal[EventType.USAGE] = EventType.USAGE
    usage: Usage = field(default_factory=Usage)


@dataclass
class ErrorEvent:
    """Error event."""

    type: Literal[EventType.ERROR] = EventType.ERROR
    reason: StopReason = StopReason.ERROR
    error: AssistantMessage | None = None


@dataclass
class EndEvent:
    """Stream end event."""

    type: Literal[EventType.END] = EventType.END
    message: AssistantMessage | None = None


AssistantMessageEvent = (
    TextEvent
    | ThinkingEvent
    | ToolCallEvent
    | UsageEvent
    | ErrorEvent
    | EndEvent
    | StartEvent
    | DoneEvent
    | TextStartEvent
    | TextDeltaEvent
    | TextEndEvent
    | ThinkingStartEvent
    | ThinkingDeltaEvent
    | ThinkingEndEvent
    | ToolCallStartEvent
    | ToolCallDeltaEvent
    | ToolCallEndEvent
)


# ============================================================================
# Stream Function Protocol
# ============================================================================


class AssistantMessageEventStream(AsyncIterable[AssistantMessageEvent]):
    """Async stream of assistant message events."""

    def __init__(self):
        self._events: list[AssistantMessageEvent] = []
        self._ended = False
        self._error: Exception | None = None

    def push(self, event: AssistantMessageEvent) -> None:
        """Push an event to the stream."""
        if self._ended:
            raise RuntimeError("Cannot push to ended stream")
        self._events.append(event)

    def end(self, message: AssistantMessage | None = None) -> None:
        """End the stream with optional final message."""
        if not self._ended:
            self._ended = True
            # Don't use push() here since _ended is already True
            if message:
                self._events.append(EndEvent(message=message))
            else:
                self._events.append(EndEvent())

    def set_error(self, error: Exception) -> None:
        """Set error state."""
        self._error = error
        self._ended = True

    def __aiter__(self) -> AssistantMessageEventStream:
        self._index = 0
        return self

    async def __anext__(self) -> AssistantMessageEvent:
        if self._error:
            raise self._error
        if self._index >= len(self._events) and self._ended:
            raise StopAsyncIteration
        # Wait for more events if not ended
        while self._index >= len(self._events) and not self._ended:
            import asyncio

            await asyncio.sleep(0.01)
        if self._index < len(self._events):
            event = self._events[self._index]
            self._index += 1
            return event
        raise StopAsyncIteration


StreamFunction = Callable[[Model[Any], Context, StreamOptions], AssistantMessageEventStream]
