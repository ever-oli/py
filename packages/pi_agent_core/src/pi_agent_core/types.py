"""Pi Agent Core - Core types for agent framework.

Ported from pi-mono/packages/agent/src/types.ts
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import (
    Any,
    Literal,
)

from pi_ai.event_stream import AssistantMessageEventStream

# Import from pi_ai
from pi_ai.types import (
    Api,
    AssistantMessage,
    ImageContent,
    Message,
    Model,
    Provider,
    SimpleStreamOptions,
    StopReason,
    TextContent,
    ThinkingBudgets,
    ThinkingLevel,
    Tool,
    ToolCall,
    Transport,
    Usage,
)

# ============================================================================
# Re-exports from pi_ai
# ============================================================================

__all__ = [
    # Types
    "AgentContext",
    "AgentEvent",
    "AgentLoopConfig",
    "AgentMessage",
    "AgentState",
    "AgentTool",
    "AgentToolCall",
    "AgentToolResult",
    "AgentToolUpdateCallback",
    "AfterToolCallContext",
    "AfterToolCallResult",
    "BeforeToolCallContext",
    "BeforeToolCallResult",
    "QueueMode",
    "StreamFn",
    "ToolExecutionMode",
    # Re-exports from pi_ai
    "Api",
    "AssistantMessage",
    "ImageContent",
    "Message",
    "Model",
    "Provider",
    "SimpleStreamOptions",
    "StopReason",
    "TextContent",
    "ThinkingLevel",
    "ThinkingBudgets",
    "Tool",
    "ToolCall",
    "ToolResultMessage",
    "Transport",
    "Usage",
    "UserMessage",
]

# ============================================================================
# Type Aliases
# ============================================================================

ToolExecutionMode = Literal["sequential", "parallel"]
QueueMode = Literal["all", "one-at-a-time"]

# AgentToolCall is a ToolCall from assistant messages
AgentToolCall = ToolCall

# AgentMessage can be extended with custom types
AgentMessage = Message


# ============================================================================
# Tool Result
# ============================================================================


@dataclass
class AgentToolResult:
    """Final or partial result produced by a tool."""

    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: Any = None


# ============================================================================
# Tool Update Callback
# ============================================================================

AgentToolUpdateCallback = Callable[[AgentToolResult], None]


# ============================================================================
# Tool Definition
# ============================================================================


@dataclass
class AgentTool:
    """Tool definition used by the agent runtime."""

    name: str
    label: str
    description: str
    parameters: dict[str, Any]  # JSON Schema

    # Optional compatibility shim for raw tool-call arguments before schema validation
    prepare_arguments: Callable[[dict[str, Any]], dict[str, Any]] | None = None

    # Execute the tool call
    execute: Callable[
        [str, dict[str, Any], Any | None, AgentToolUpdateCallback | None],
        Coroutine[Any, Any, AgentToolResult],
    ] = field(default_factory=lambda: lambda *args, **kwargs: AgentToolResult())


# ============================================================================
# Tool Result Message
# ============================================================================


@dataclass
class ToolResultMessage:
    """Tool result message."""

    role: Literal["toolResult"] = "toolResult"
    tool_call_id: str = ""
    tool_name: str = ""
    content: list[TextContent | ImageContent] = field(default_factory=list)
    details: Any = None
    is_error: bool = False
    timestamp: int = 0


# ============================================================================
# Before/After Tool Call Contexts and Results
# ============================================================================


@dataclass
class BeforeToolCallResult:
    """Result returned from before_tool_call."""

    block: bool = False
    reason: str = ""


@dataclass
class AfterToolCallResult:
    """Partial override returned from after_tool_call."""

    content: list[TextContent | ImageContent] | None = None
    details: Any = None
    is_error: bool | None = None


@dataclass
class AgentContext:
    """Context snapshot passed into the low-level agent loop."""

    system_prompt: str = ""
    messages: list[AgentMessage] = field(default_factory=list)
    tools: list[AgentTool] = field(default_factory=list)


@dataclass
class BeforeToolCallContext:
    """Context passed to before_tool_call."""

    assistant_message: AssistantMessage
    tool_call: AgentToolCall
    args: Any
    context: AgentContext


@dataclass
class AfterToolCallContext:
    """Context passed to after_tool_call."""

    assistant_message: AssistantMessage
    tool_call: AgentToolCall
    args: Any
    result: AgentToolResult
    is_error: bool
    context: AgentContext


# ============================================================================
# Agent Events
# ============================================================================

AgentEvent = (
    # Agent lifecycle
    dict[Literal["type"], Literal["agent_start"]]
    | dict[Literal["type"], Literal["agent_end"]]
    # Turn lifecycle
    | dict[Literal["type"], Literal["turn_start"]]
    | dict[Literal["type"], Literal["turn_end"]]
    # Message lifecycle
    | dict[Literal["type"], Literal["message_start"]]
    | dict[Literal["type"], Literal["message_update"]]
    | dict[Literal["type"], Literal["message_end"]]
    # Tool execution lifecycle
    | dict[Literal["type"], Literal["tool_execution_start"]]
    | dict[Literal["type"], Literal["tool_execution_update"]]
    | dict[Literal["type"], Literal["tool_execution_end"]]
)


# TypedDict versions for better type safety
class AgentStartEvent:
    """Agent started event."""

    type: Literal["agent_start"] = "agent_start"


@dataclass
class AgentEndEvent:
    """Agent ended event."""

    type: Literal["agent_end"] = "agent_end"
    messages: list[AgentMessage] = field(default_factory=list)


@dataclass
class TurnStartEvent:
    """Turn started event."""

    type: Literal["turn_start"] = "turn_start"


@dataclass
class TurnEndEvent:
    """Turn ended event."""

    type: Literal["turn_end"] = "turn_end"
    message: AgentMessage = field(default_factory=lambda: AssistantMessage())
    tool_results: list[ToolResultMessage] = field(default_factory=list)


@dataclass
class MessageStartEvent:
    """Message started event."""

    type: Literal["message_start"] = "message_start"
    message: AgentMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class MessageUpdateEvent:
    """Message updated event (only for assistant messages during streaming)."""

    type: Literal["message_update"] = "message_update"
    message: AgentMessage = field(default_factory=lambda: AssistantMessage())
    assistant_message_event: Any = None


@dataclass
class MessageEndEvent:
    """Message ended event."""

    type: Literal["message_end"] = "message_end"
    message: AgentMessage = field(default_factory=lambda: AssistantMessage())


@dataclass
class ToolExecutionStartEvent:
    """Tool execution started event."""

    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call_id: str = ""
    tool_name: str = ""
    args: Any = None


@dataclass
class ToolExecutionUpdateEvent:
    """Tool execution update event."""

    type: Literal["tool_execution_update"] = "tool_execution_update"
    tool_call_id: str = ""
    tool_name: str = ""
    args: Any = None
    partial_result: Any = None


@dataclass
class ToolExecutionEndEvent:
    """Tool execution ended event."""

    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str = ""
    tool_name: str = ""
    result: Any = None
    is_error: bool = False


# Union type for all events
TypedAgentEvent = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | ToolExecutionStartEvent
    | ToolExecutionUpdateEvent
    | ToolExecutionEndEvent
)


# ============================================================================
# Agent Loop Config
# ============================================================================


@dataclass
class AgentLoopConfig:
    """Configuration for the agent loop."""

    model: Model
    convert_to_llm: Callable[
        [list[AgentMessage]], list[Message] | Coroutine[Any, Any, list[Message]]
    ]

    # Optional transforms
    transform_context: (
        Callable[
            [list[AgentMessage], Any | None],
            list[AgentMessage] | Coroutine[Any, Any, list[AgentMessage]],
        ]
        | None
    ) = None

    # API key resolution
    get_api_key: Callable[[str], str | None | Coroutine[Any, Any, str | None]] | None = None

    # Queued message callbacks
    get_steering_messages: (
        Callable[[], list[AgentMessage] | Coroutine[Any, Any, list[AgentMessage]]] | None
    ) = None
    get_follow_up_messages: (
        Callable[[], list[AgentMessage] | Coroutine[Any, Any, list[AgentMessage]]] | None
    ) = None

    # Tool execution mode
    tool_execution: ToolExecutionMode = "parallel"

    # Hooks
    before_tool_call: (
        Callable[
            [BeforeToolCallContext, Any | None],
            BeforeToolCallResult | None | Coroutine[Any, Any, BeforeToolCallResult | None],
        ]
        | None
    ) = None
    after_tool_call: (
        Callable[
            [AfterToolCallContext, Any | None],
            AfterToolCallResult | None | Coroutine[Any, Any, AfterToolCallResult | None],
        ]
        | None
    ) = None

    # Forwarded from SimpleStreamOptions
    reasoning: ThinkingLevel | None = None
    thinking_budgets: ThinkingBudgets | None = None
    on_payload: Callable[[dict, Model], dict | None] | None = None
    transport: Transport = Transport.SSE
    session_id: str | None = None
    max_retry_delay_ms: int = 60000
    api_key: str | None = None


# ============================================================================
# Stream Function Type
# ============================================================================

StreamFn = Callable[
    [Model, Any, SimpleStreamOptions],
    AssistantMessageEventStream | Coroutine[Any, Any, AssistantMessageEventStream],
]


# ============================================================================
# Agent State
# ============================================================================


@dataclass
class AgentState:
    """Public agent state."""

    system_prompt: str = ""
    model: Model = field(
        default_factory=lambda: Model(
            id="unknown",
            api="openai-responses",
            provider="openai",
        )
    )
    thinking_level: ThinkingLevel = ThinkingLevel.OFF
    _tools: list[AgentTool] = field(default_factory=list, repr=False)
    _messages: list[AgentMessage] = field(default_factory=list, repr=False)
    _is_streaming: bool = False
    _streaming_message: AgentMessage | None = None
    _pending_tool_calls: set[str] = field(default_factory=set)
    _error_message: str | None = None

    @property
    def tools(self) -> list[AgentTool]:
        """Get tools (returns copy)."""
        return self._tools.copy()

    @tools.setter
    def tools(self, value: list[AgentTool]) -> None:
        """Set tools (copies the list)."""
        self._tools = value.copy()

    @property
    def messages(self) -> list[AgentMessage]:
        """Get messages (returns copy)."""
        return self._messages.copy()

    @messages.setter
    def messages(self, value: list[AgentMessage]) -> None:
        """Set messages (copies the list)."""
        self._messages = value.copy()

    @property
    def is_streaming(self) -> bool:
        """True while the agent is processing."""
        return self._is_streaming

    @property
    def streaming_message(self) -> AgentMessage | None:
        """Partial assistant message for current streamed response."""
        return self._streaming_message

    @property
    def pending_tool_calls(self) -> frozenset[str]:
        """Tool call IDs currently executing."""
        return frozenset(self._pending_tool_calls)

    @property
    def error_message(self) -> str | None:
        """Error message from most recent failed turn."""
        return self._error_message
