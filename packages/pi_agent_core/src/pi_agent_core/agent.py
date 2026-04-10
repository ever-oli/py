"""Agent class for pi-agent-core.

Ported from TypeScript: agent/src/agent.ts
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pi_ai import (
    Message,
    Model,
    TextContent,
    ThinkingBudgets,
    ThinkingLevel,
    stream_simple,
)

from .agent_loop import convert_to_llm_messages, run_agent_loop
from .types import (
    AfterToolCallContext,
    AfterToolCallResult,
    AgentMessage,
    AgentState,
    AgentTool,
    BeforeToolCallContext,
    BeforeToolCallResult,
    QueueMode,
    StreamFn,
    ToolExecutionMode,
)

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable, Coroutine

DEFAULT_MODEL = Model(
    id="unknown",
    name="unknown",
    api="openai-completions",
    provider="unknown",
)

EMPTY_USAGE = {
    "input": 0,
    "output": 0,
    "cacheRead": 0,
    "cacheWrite": 0,
    "totalTokens": 0,
    "cost": {
        "input": 0,
        "output": 0,
        "cacheRead": 0,
        "cacheWrite": 0,
        "total": 0,
    },
}


@dataclass
class AgentOptions:
    """Options for constructing an Agent."""

    initialState: AgentState | None = None
    convertToLlm: Callable[[list[AgentMessage]], list[Message]] | None = None
    streamFn: StreamFn | None = None
    getApiKey: Callable[[str], str | None] | None = None
    onPayload: Callable[[Any], None] | None = None
    beforeToolCall: (
        Callable[[BeforeToolCallContext], Coroutine[Any, Any, BeforeToolCallResult | None]] | None
    ) = None
    afterToolCall: (
        Callable[[AfterToolCallContext], Coroutine[Any, Any, AfterToolCallResult | None]] | None
    ) = None
    steeringMode: QueueMode = "all"
    followUpMode: QueueMode = "one-at-a-time"
    sessionId: str | None = None
    thinkingBudgets: ThinkingBudgets | None = None
    toolExecution: ToolExecutionMode = "sequential"


class PendingMessageQueue:
    """Queue for pending user messages."""

    def __init__(self, mode: QueueMode):
        self.mode = mode
        self.messages: list[AgentMessage] = []

    def enqueue(self, message: AgentMessage) -> None:
        self.messages.append(message)

    def has_items(self) -> bool:
        return len(self.messages) > 0

    def drain(self) -> list[AgentMessage]:
        if self.mode == "all":
            drained = self.messages.copy()
            self.messages = []
            return drained

        if not self.messages:
            return []
        first = self.messages[0]
        self.messages = self.messages[1:]
        return [first]

    def clear(self) -> None:
        self.messages = []


@dataclass
class ActiveRun:
    """Active agent run."""

    promise: asyncio.Task
    resolve: Callable[[], None]
    abortController: asyncio.Event


class Agent:
    """Agent for running conversational AI with tools."""

    def __init__(self, options: AgentOptions | None = None):
        opts = options or AgentOptions()

        self._tools: list[AgentTool] = opts.initialState.tools.copy() if opts.initialState else []
        self._messages: list[AgentMessage] = (
            opts.initialState.messages.copy() if opts.initialState else []
        )
        self._systemPrompt = opts.initialState.system_prompt if opts.initialState else ""
        self._model = opts.initialState.model if opts.initialState else DEFAULT_MODEL
        self._thinkingLevel = opts.initialState.thinking_level if opts.initialState else ThinkingLevel.OFF

        self._convertToLlm = opts.convertToLlm or convert_to_llm_messages
        self._streamFn = opts.streamFn or stream_simple
        self._getApiKey = opts.getApiKey
        self._onPayload = opts.onPayload
        self._beforeToolCall = opts.beforeToolCall
        self._afterToolCall = opts.afterToolCall
        self._steeringMode = opts.steeringMode
        self._followUpMode = opts.followUpMode
        self._sessionId = opts.sessionId
        self._thinkingBudgets = opts.thinkingBudgets
        self._toolExecution = opts.toolExecution

        self._steeringQueue = PendingMessageQueue(opts.steeringMode)
        self._followUpQueue = PendingMessageQueue(opts.followUpMode)
        self._isStreaming = False
        self._streamingMessage: AgentMessage | None = None
        self._pendingToolCalls: set[str] = set()
        self._errorMessage: str | None = None
        self._activeRun: ActiveRun | None = None

    @property
    def tools(self) -> list[AgentTool]:
        return self._tools.copy()

    @tools.setter
    def tools(self, value: list[AgentTool]) -> None:
        self._tools = value.copy()

    @property
    def messages(self) -> list[AgentMessage]:
        return self._messages.copy()

    @messages.setter
    def messages(self, value: list[AgentMessage]) -> None:
        self._messages = value.copy()

    @property
    def systemPrompt(self) -> str:
        return self._systemPrompt

    @systemPrompt.setter
    def systemPrompt(self, value: str) -> None:
        self._systemPrompt = value

    @property
    def model(self) -> Model:
        return self._model

    @model.setter
    def model(self, value: Model) -> None:
        self._model = value

    @property
    def state(self) -> AgentState:
        return AgentState(
            system_prompt=self._systemPrompt,
            model=self._model,
            thinking_level=self._thinkingLevel,
            _tools=self._tools.copy(),
            _messages=self._messages.copy(),
            _is_streaming=self._isStreaming,
            _streaming_message=self._streamingMessage,
            _pending_tool_calls=self._pendingToolCalls.copy(),
            _error_message=self._errorMessage,
        )

    def steer(self, message: str) -> None:
        """Send a steering message to the agent."""
        self._steeringQueue.enqueue(
            AgentMessage(
                role="user",
                content=[TextContent(type="text", text=message)],
            )
        )

    async def run(self, message: str | None = None) -> list[AgentMessage]:
        """Run the agent with an optional message.

        Args:
            message: Optional user message to start the conversation

        Returns:
            Updated message history
        """
        if message:
            self._messages.append(
                AgentMessage(
                    role="user",
                    content=[TextContent(type="text", text=message)],
                )
            )

        # Build loop config
        from .agent_loop import AgentLoopConfig

        config = AgentLoopConfig(
            model=self._model,
            convertToLlm=self._convertToLlm,
            streamFn=self._streamFn,
            tools=self._tools,
            systemPrompt=self._systemPrompt,
            toolExecution=self._toolExecution,
            beforeToolCall=self._beforeToolCall,
            afterToolCall=self._afterToolCall,
            onPayload=self._onPayload,
        )

        # Run the loop
        loop_state = await run_agent_loop(config, self._messages)

        self._messages = loop_state.messages
        return self._messages

    async def run_stream(self, message: str | None = None):
        """Run the agent with streaming output."""
        if message:
            self._messages.append(
                AgentMessage(
                    role="user",
                    content=[TextContent(type="text", text=message)],
                )
            )

        self._isStreaming = True

        try:
            from .agent_loop import AgentLoopConfig, run_agent_loop

            config = AgentLoopConfig(
                model=self._model,
                convertToLlm=self._convertToLlm,
                streamFn=self._streamFn,
                tools=self._tools,
                systemPrompt=self._systemPrompt,
                toolExecution=self._toolExecution,
                beforeToolCall=self._beforeToolCall,
                afterToolCall=self._afterToolCall,
                onPayload=self._onPayload,
            )

            loop_state = await run_agent_loop(config, self._messages)
            self._messages = loop_state.messages

            for msg in self._messages:
                yield msg

        finally:
            self._isStreaming = False

    def abort(self) -> None:
        """Abort the current run."""
        if self._activeRun:
            self._activeRun.abortController.set()


def create_agent(options: AgentOptions | None = None) -> Agent:
    """Create a new agent."""
    return Agent(options)
