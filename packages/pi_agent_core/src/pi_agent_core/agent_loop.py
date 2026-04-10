"""Agent loop for pi-agent-core.

Ported from TypeScript: agent/src/agent-loop.ts
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pi_ai.types import (
    ToolCall,
)

from pi_ai import (
    AssistantMessage,
    Message,
    TextContent,
    ToolResultMessage,
)

from .types import (
    AfterToolCallContext,
    AfterToolCallResult,
    AgentContext,
    AgentEndEvent,
    AgentLoopConfig,
    AgentMessage,
    AgentStartEvent,
    AgentTool,
    AgentToolCall,
    AgentToolResult,
    BeforeToolCallContext,
    BeforeToolCallResult,
    MessageEndEvent,
    MessageStartEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    ToolExecutionUpdateEvent,
    TurnEndEvent,
    TurnStartEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

T = TypeVar("T")
R = TypeVar("R")


class EventStream(Generic[T, R]):
    """Generic event stream for async iteration."""

    def __init__(
        self,
        is_complete: Callable[[T], bool],
        extract_result: Callable[[T], R],
    ):
        self._is_complete = is_complete
        self._extract_result = extract_result
        self._queue: deque[T] = deque()
        self._waiting: list[asyncio.Future[tuple[T | None, bool]]] = []
        self._done = False
        self._result: R | None = None
        self._result_event = asyncio.Event()
        self._error: Exception | None = None

    def push(self, event: T) -> None:
        """Push an event to the stream."""
        if self._done:
            return

        if self._is_complete(event):
            self._done = True
            self._result = self._extract_result(event)
            self._result_event.set()

        # Deliver to waiting consumer or queue it
        if self._waiting:
            waiter = self._waiting.pop(0)
            waiter.set_result((event, False))
        else:
            self._queue.append(event)

    def end(self, result: R | None = None) -> None:
        """End the stream with an optional result."""
        self._done = True
        if result is not None:
            self._result = result
            self._result_event.set()

        # Notify all waiting consumers that we're done
        for waiter in self._waiting:
            waiter.set_result((None, True))
        self._waiting.clear()

    def set_error(self, error: Exception) -> None:
        """Set an error on the stream."""
        self._error = error
        self._done = True
        self._result_event.set()

        for waiter in self._waiting:
            waiter.set_exception(error)
        self._waiting.clear()

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        while True:
            if self._queue:
                return self._queue.popleft()
            elif self._done:
                if self._error:
                    raise self._error
                raise StopAsyncIteration
            else:
                waiter: asyncio.Future[tuple[T | None, bool]] = (
                    asyncio.get_event_loop().create_future()
                )
                self._waiting.append(waiter)
                value, done = await waiter
                if done:
                    if self._error:
                        raise self._error
                    raise StopAsyncIteration
                if value is not None:
                    return value

    async def result(self) -> R:
        """Get the final result of the stream."""
        await self._result_event.wait()
        if self._error:
            raise self._error
        if self._result is None:
            raise RuntimeError("Stream ended without a result")
        return self._result


class AgentEventStream(EventStream[Any, list[AgentMessage]]):
    """Event stream for agent events."""

    def __init__(self):
        super().__init__(
            is_complete=lambda event: isinstance(event, AgentEndEvent),
            extract_result=lambda event: event.messages if isinstance(event, AgentEndEvent) else [],
        )


def _now_ms() -> int:
    """Get current time in milliseconds."""
    import time

    return int(time.time() * 1000)


async def _maybe_await(value: Any) -> Any:
    """Await if value is a coroutine, otherwise return it."""
    if asyncio.iscoroutine(value):
        return await value
    return value


class Literal:
    """Placeholder for Literal type - will be handled by Python 3.8+ typing."""

    pass


def default_convert_to_llm(messages: list[AgentMessage]) -> list[Any]:
    """Default converter: filter to user, assistant, and toolResult messages."""
    result: list[Any] = []
    for m in messages:
        if m.role in ("user", "assistant", "toolResult"):
            result.append(m)
    return result


def create_error_tool_result(message: str) -> AgentToolResult:
    """Create an error tool result."""
    return AgentToolResult(
        content=[TextContent(type="text", text=message)],
        details={},
    )


@dataclass
class PreparedToolCall:
    """A prepared tool call ready for execution."""

    kind: str = "prepared"
    tool_call: AgentToolCall = field(default_factory=lambda: ToolCall(type="toolCall"))
    tool: AgentTool = field(
        default_factory=lambda: AgentTool(name="", label="", description="", parameters={})
    )
    args: Any = None


@dataclass
class ImmediateToolCallOutcome:
    """Immediate outcome (no execution needed)."""

    kind: str = "immediate"
    result: AgentToolResult = field(default_factory=AgentToolResult)
    is_error: bool = False


@dataclass
class ExecutedToolCallOutcome:
    """Outcome after execution."""

    result: AgentToolResult = field(default_factory=AgentToolResult)
    is_error: bool = False


async def prepare_tool_call(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    tool_call: AgentToolCall,
    config: AgentLoopConfig,
    signal: Any | None,
) -> PreparedToolCall | ImmediateToolCallOutcome:
    """Prepare a tool call for execution."""
    tool = None
    for t in current_context.tools or []:
        if t.name == tool_call.name:
            tool = t
            break

    if tool is None:
        return ImmediateToolCallOutcome(
            kind="immediate",
            result=create_error_tool_result(f"Tool {tool_call.name} not found"),
            is_error=True,
        )

    try:
        # Prepare arguments
        prepared_args = (
            tool_call.arguments.copy()
            if hasattr(tool_call.arguments, "copy")
            else dict(tool_call.arguments)
        )
        if tool.prepare_arguments:
            prepared_args = tool.prepare_arguments(prepared_args)

        # Validate arguments - simplified, would need actual validation
        validated_args = prepared_args

        # Call before_tool_call hook
        if config.before_tool_call:
            before_result = await _maybe_await(
                config.before_tool_call(
                    BeforeToolCallContext(
                        assistant_message=assistant_message,
                        tool_call=tool_call,
                        args=validated_args,
                        context=current_context,
                    ),
                    signal,
                )
            )
            if isinstance(before_result, BeforeToolCallResult) and before_result.block:
                return ImmediateToolCallOutcome(
                    kind="immediate",
                    result=create_error_tool_result(
                        before_result.reason or "Tool execution was blocked"
                    ),
                    is_error=True,
                )

        return PreparedToolCall(
            kind="prepared",
            tool_call=tool_call,
            tool=tool,
            args=validated_args,
        )
    except Exception as e:
        return ImmediateToolCallOutcome(
            kind="immediate",
            result=create_error_tool_result(str(e)),
            is_error=True,
        )


async def execute_prepared_tool_call(
    prepared: PreparedToolCall,
    signal: Any | None,
    emit: Callable[[Any], Any],
) -> ExecutedToolCallOutcome:
    """Execute a prepared tool call."""
    update_events: list[asyncio.Task] = []

    def on_update(partial_result: AgentToolResult) -> None:
        """Callback for tool execution updates."""
        task = asyncio.create_task(
            _maybe_await(
                emit(
                    ToolExecutionUpdateEvent(
                        type="tool_execution_update",
                        tool_call_id=prepared.tool_call.id,
                        tool_name=prepared.tool_call.name,
                        args=prepared.args,
                        partial_result=partial_result,
                    )
                )
            )
        )
        update_events.append(task)

    try:
        # Execute the tool
        if asyncio.iscoroutinefunction(prepared.tool.execute):
            result = await prepared.tool.execute(
                prepared.tool_call.id,
                prepared.args,
                signal,
                on_update,
            )
        else:
            result = prepared.tool.execute(
                prepared.tool_call.id,
                prepared.args,
                signal,
                on_update,
            )
        # Wait for all update events to complete
        if update_events:
            await asyncio.gather(*update_events, return_exceptions=True)
        return ExecutedToolCallOutcome(result=result, is_error=False)
    except Exception as e:
        if update_events:
            await asyncio.gather(*update_events, return_exceptions=True)
        return ExecutedToolCallOutcome(
            result=create_error_tool_result(str(e)),
            is_error=True,
        )


async def finalize_executed_tool_call(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    prepared: PreparedToolCall,
    executed: ExecutedToolCallOutcome,
    config: AgentLoopConfig,
    signal: Any | None,
    emit: Callable[[Any], Any],
) -> ToolResultMessage:
    """Finalize a tool call after execution."""
    result = executed.result
    is_error = executed.is_error

    # Call after_tool_call hook
    if config.after_tool_call:
        after_result = await _maybe_await(
            config.after_tool_call(
                AfterToolCallContext(
                    assistant_message=assistant_message,
                    tool_call=prepared.tool_call,
                    args=prepared.args,
                    result=result,
                    is_error=is_error,
                    context=current_context,
                ),
                signal,
            )
        )
        if isinstance(after_result, AfterToolCallResult):
            if after_result.content is not None:
                result = AgentToolResult(
                    content=after_result.content,
                    details=result.details,
                )
            if after_result.details is not None:
                result = AgentToolResult(
                    content=result.content,
                    details=after_result.details,
                )
            if after_result.is_error is not None:
                is_error = after_result.is_error

    return await emit_tool_call_outcome(prepared.tool_call, result, is_error, emit)


async def emit_tool_call_outcome(
    tool_call: AgentToolCall,
    result: AgentToolResult,
    is_error: bool,
    emit: Callable[[Any], Any],
) -> ToolResultMessage:
    """Emit the outcome of a tool call."""
    await _maybe_await(
        emit(
            ToolExecutionEndEvent(
                type="tool_execution_end",
                tool_call_id=tool_call.id,
                tool_name=tool_call.name,
                result=result,
                is_error=is_error,
            )
        )
    )

    tool_result_message = ToolResultMessage(
        role="toolResult",
        tool_call_id=tool_call.id,
        tool_name=tool_call.name,
        content=result.content,
        details=result.details,
        is_error=is_error,
        timestamp=_now_ms(),
    )

    await _maybe_await(emit(MessageStartEvent(type="message_start", message=tool_result_message)))
    await _maybe_await(emit(MessageEndEvent(type="message_end", message=tool_result_message)))

    return tool_result_message


async def execute_tool_calls_sequential(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    tool_calls: list[AgentToolCall],
    config: AgentLoopConfig,
    signal: Any | None,
    emit: Callable[[Any], Any],
) -> list[ToolResultMessage]:
    """Execute tool calls sequentially."""
    results: list[ToolResultMessage] = []

    for tool_call in tool_calls:
        await _maybe_await(
            emit(
                ToolExecutionStartEvent(
                    type="tool_execution_start",
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    args=tool_call.arguments,
                )
            )
        )

        preparation = await prepare_tool_call(
            current_context, assistant_message, tool_call, config, signal
        )

        if isinstance(preparation, ImmediateToolCallOutcome):
            results.append(
                await emit_tool_call_outcome(
                    tool_call, preparation.result, preparation.is_error, emit
                )
            )
        else:
            executed = await execute_prepared_tool_call(preparation, signal, emit)
            results.append(
                await finalize_executed_tool_call(
                    current_context, assistant_message, preparation, executed, config, signal, emit
                )
            )

    return results


async def execute_tool_calls_parallel(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    tool_calls: list[AgentToolCall],
    config: AgentLoopConfig,
    signal: Any | None,
    emit: Callable[[Any], Any],
) -> list[ToolResultMessage]:
    """Execute tool calls in parallel."""
    results: list[ToolResultMessage] = []
    runnable_calls: list[PreparedToolCall] = []

    # Phase 1: Prepare all tool calls
    for tool_call in tool_calls:
        await _maybe_await(
            emit(
                ToolExecutionStartEvent(
                    type="tool_execution_start",
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    args=tool_call.arguments,
                )
            )
        )

        preparation = await prepare_tool_call(
            current_context, assistant_message, tool_call, config, signal
        )

        if isinstance(preparation, ImmediateToolCallOutcome):
            results.append(
                await emit_tool_call_outcome(
                    tool_call, preparation.result, preparation.is_error, emit
                )
            )
        else:
            runnable_calls.append(preparation)

    # Phase 2: Execute all runnable calls in parallel
    async def execute_single(running: dict) -> tuple[PreparedToolCall, ExecutedToolCallOutcome]:
        executed = await execute_prepared_tool_call(running["prepared"], signal, emit)
        return running["prepared"], executed

    running_calls = [{"prepared": prepared} for prepared in runnable_calls]

    executed_results = await asyncio.gather(*[execute_single(running) for running in running_calls])

    # Phase 3: Finalize in order
    for prepared, executed in executed_results:
        results.append(
            await finalize_executed_tool_call(
                current_context,
                assistant_message,
                prepared,
                executed,
                config,
                signal,
                emit,
            )
        )

    return results


async def execute_tool_calls(
    current_context: AgentContext,
    assistant_message: AssistantMessage,
    config: AgentLoopConfig,
    signal: Any | None,
    emit: Callable[[Any], Any],
) -> list[ToolResultMessage]:
    """Execute tool calls from an assistant message."""
    tool_calls = [c for c in assistant_message.content if c.type == "toolCall"]

    if config.tool_execution == "sequential":
        return await execute_tool_calls_sequential(
            current_context, assistant_message, tool_calls, config, signal, emit
        )
    else:
        return await execute_tool_calls_parallel(
            current_context, assistant_message, tool_calls, config, signal, emit
        )


async def stream_assistant_response(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Any | None,
    emit: Callable[[Any], Any],
) -> AssistantMessage:
    """Stream an assistant response from the LLM."""
    # Apply context transform if configured
    messages = context.messages
    if config.transform_context:
        messages = await _maybe_await(config.transform_context(messages, signal))

    # Convert to LLM-compatible messages
    if asyncio.iscoroutinefunction(config.convert_to_llm):
        llm_messages = await config.convert_to_llm(messages)
    else:
        llm_messages = config.convert_to_llm(messages)

    # Build LLM context
    from pi_ai.types import Context as LlmContext
    from pi_ai.types import Tool as LlmTool

    llm_context = LlmContext(
        system=context.system_prompt,
        messages=llm_messages,
        tools=[],
    )
    # Add tools from context
    for tool in context.tools or []:
        llm_context.tools.append(
            LlmTool(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
            )
        )

    config.stream_fn if hasattr(config, "stream_fn") else None

    # Resolve API key
    resolved_api_key = config.api_key
    if config.get_api_key:
        resolved_api_key = (
            await _maybe_await(config.get_api_key(config.model.provider)) or config.api_key
        )

    # Create stream options
    from pi_ai.types import SimpleStreamOptions

    SimpleStreamOptions(
        reasoning=config.reasoning,
        thinking_budgets=config.thinking_budgets,
        on_payload=config.on_payload,
        transport=config.transport,
        session_id=config.session_id,
        max_retry_delay_ms=config.max_retry_delay_ms,
        api_key=resolved_api_key,
    )

    # For now, return a mock response since we don't have the actual stream function
    final_message = AssistantMessage(
        role="assistant",
        content=[TextContent(type="text", text="Mock response")],
        api=config.model.api,
        provider=config.model.provider,
        model=config.model.id,
        usage={
            "input": 0,
            "output": 0,
            "cache_read": 0,
            "cache_write": 0,
            "total_tokens": 0,
            "cost": {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "total": 0},
        },
        stop_reason="stop",
        timestamp=_now_ms(),
    )

    return final_message


async def run_loop(
    current_context: AgentContext,
    new_messages: list[AgentMessage],
    config: AgentLoopConfig,
    signal: Any | None,
    emit: Callable[[Any], Any],
) -> None:
    """Main loop logic shared by agent_loop and agent_loop_continue."""
    first_turn = True

    # Check for steering messages at start
    pending_messages: list[AgentMessage] = []
    if config.get_steering_messages:
        pending_messages = await _maybe_await(config.get_steering_messages())

    # Outer loop: continues when queued follow-up messages arrive
    while True:
        has_more_tool_calls = True

        # Inner loop: process tool calls and steering messages
        while has_more_tool_calls or pending_messages:
            if not first_turn:
                await _maybe_await(emit(TurnStartEvent(type="turn_start")))
            else:
                first_turn = False

            # Process pending messages
            if pending_messages:
                for message in pending_messages:
                    await _maybe_await(
                        emit(MessageStartEvent(type="message_start", message=message))
                    )
                    await _maybe_await(emit(MessageEndEvent(type="message_end", message=message)))
                    current_context.messages.append(message)
                    new_messages.append(message)
                pending_messages = []

            # Stream assistant response
            message = await stream_assistant_response(current_context, config, signal, emit)
            new_messages.append(message)

            # Check for error/aborted
            from pi_ai.types import StopReason

            if message.stop_reason in (StopReason.ERROR, StopReason.ABORTED):
                await _maybe_await(
                    emit(
                        TurnEndEvent(
                            type="turn_end",
                            message=message,
                            tool_results=[],
                        )
                    )
                )
                await _maybe_await(emit(AgentEndEvent(type="agent_end", messages=new_messages)))
                return

            # Check for tool calls
            tool_calls = [c for c in message.content if c.type == "toolCall"]
            has_more_tool_calls = len(tool_calls) > 0

            tool_results: list[ToolResultMessage] = []
            if has_more_tool_calls:
                tool_results = await execute_tool_calls(
                    current_context, message, config, signal, emit
                )
                for result in tool_results:
                    current_context.messages.append(result)
                    new_messages.append(result)

            await _maybe_await(
                emit(
                    TurnEndEvent(
                        type="turn_end",
                        message=message,
                        tool_results=tool_results,
                    )
                )
            )

            # Get steering messages for next iteration
            if config.get_steering_messages:
                pending_messages = await _maybe_await(config.get_steering_messages())

        # Check for follow-up messages
        follow_up_messages: list[AgentMessage] = []
        if config.get_follow_up_messages:
            follow_up_messages = await _maybe_await(config.get_follow_up_messages())

        if follow_up_messages:
            pending_messages = follow_up_messages
            continue

        # No more messages, exit
        break

    await _maybe_await(emit(AgentEndEvent(type="agent_end", messages=new_messages)))


async def run_agent_loop(
    prompts: list[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[Any], Any],
    signal: Any | None = None,
) -> list[AgentMessage]:
    """Start an agent loop with a new prompt message."""
    new_messages: list[AgentMessage] = list(prompts)
    current_context = AgentContext(
        system_prompt=context.system_prompt,
        messages=list(context.messages) + list(prompts),
        tools=list(context.tools),
    )

    await _maybe_await(emit(AgentStartEvent(type="agent_start")))
    await _maybe_await(emit(TurnStartEvent(type="turn_start")))

    for prompt in prompts:
        await _maybe_await(emit(MessageStartEvent(type="message_start", message=prompt)))
        await _maybe_await(emit(MessageEndEvent(type="message_end", message=prompt)))

    await run_loop(current_context, new_messages, config, signal, emit)
    return new_messages


async def run_agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    emit: Callable[[Any], Any],
    signal: Any | None = None,
) -> list[AgentMessage]:
    """Continue an agent loop from the current context without adding a new message."""
    if not context.messages:
        raise ValueError("Cannot continue: no messages in context")

    if context.messages[-1].role == "assistant":
        raise ValueError("Cannot continue from message role: assistant")

    new_messages: list[AgentMessage] = []
    current_context = AgentContext(
        system_prompt=context.system_prompt,
        messages=list(context.messages),
        tools=list(context.tools),
    )

    await _maybe_await(emit(AgentStartEvent(type="agent_start")))
    await _maybe_await(emit(TurnStartEvent(type="turn_start")))

    await run_loop(current_context, new_messages, config, signal, emit)
    return new_messages


def agent_loop(
    prompts: list[AgentMessage],
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Any | None = None,
) -> AgentEventStream:
    """Start an agent loop with a new prompt message."""
    stream = AgentEventStream()

    async def run() -> None:
        try:
            messages = await run_agent_loop(
                prompts, context, config, lambda event: stream.push(event), signal
            )
            stream.end(messages)
        except Exception as e:
            stream.set_error(e)

    asyncio.create_task(run())
    return stream


def agent_loop_continue(
    context: AgentContext,
    config: AgentLoopConfig,
    signal: Any | None = None,
) -> AgentEventStream:
    """Continue an agent loop from the current context."""
    if not context.messages:
        raise ValueError("Cannot continue: no messages in context")

    if context.messages[-1].role == "assistant":
        raise ValueError("Cannot continue from message role: assistant")

    stream = AgentEventStream()

    async def run() -> None:
        try:
            messages = await run_agent_loop_continue(
                context, config, lambda event: stream.push(event), signal
            )
            stream.end(messages)
        except Exception as e:
            stream.set_error(e)

    asyncio.create_task(run())
    return stream


def convert_to_llm_messages(messages: list[AgentMessage]) -> list[Message]:
    """Convert AgentMessage list to LLM-compatible Message list.

    This is a default implementation that filters to user and assistant messages.
    Custom implementations can handle additional message types like bashExecution,
    custom messages, branchSummary, compactionSummary, etc.
    """
    result: list[Message] = []
    for msg in messages:
        # Only include user and assistant messages in LLM context by default
        if msg.role in ("user", "assistant"):
            result.append(msg)
    return result
