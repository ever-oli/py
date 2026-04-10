"""Pi Agent Core - Agent runtime and tool framework.

Ported from TypeScript: agent package
"""

__version__ = "0.1.0"

# Core classes
from .agent import Agent, AgentOptions
from .agent_loop import (
    AgentEventStream,
    agent_loop,
    agent_loop_continue,
    run_agent_loop,
    run_agent_loop_continue,
)

# Types
from .types import (
    AfterToolCallContext,
    AfterToolCallResult,
    AgentContext,
    AgentEndEvent,
    AgentEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentStartEvent,
    AgentState,
    AgentTool,
    AgentToolCall,
    AgentToolResult,
    AgentToolUpdateCallback,
    BeforeToolCallContext,
    BeforeToolCallResult,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    QueueMode,
    StreamFn,
    ToolExecutionEndEvent,
    ToolExecutionMode,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    ToolResultMessage,
    TurnEndEvent,
    TurnStartEvent,
    TypedAgentEvent,
)

__all__ = [
    # Version
    "__version__",
    # Agent
    "Agent",
    "AgentOptions",
    # Agent loop
    "agent_loop",
    "agent_loop_continue",
    "run_agent_loop",
    "run_agent_loop_continue",
    "AgentEventStream",
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
    "ToolResultMessage",
    # Event types
    "AgentStartEvent",
    "AgentEndEvent",
    "TurnStartEvent",
    "TurnEndEvent",
    "MessageStartEvent",
    "MessageUpdateEvent",
    "MessageEndEvent",
    "ToolExecutionStartEvent",
    "ToolExecutionUpdateEvent",
    "ToolExecutionEndEvent",
    "TypedAgentEvent",
]
