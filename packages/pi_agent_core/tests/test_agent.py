"""Tests for pi_agent_core agent module."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pi_agent_core.agent_loop import (
    AgentEventStream,
    run_agent_loop,
    run_agent_loop_continue,
)
from pi_agent_core.types import (
    AgentContext,
    AgentEndEvent,
    AgentState,
    MessageEndEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
)
from pi_ai.event_stream import EventStream
from pi_ai.types import (
    AssistantMessage,
    Model,
    StopReason,
    TextContent,
    ToolCall,
    Usage,
    UserMessage,
)

from pi_agent_core import (
    Agent,
    AgentOptions,
    AgentTool,
    AgentToolResult,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_model():
    """Create a mock model."""
    return Model(
        id="mock",
        api="openai-responses",
        provider="openai",
        name="mock",
    )


@pytest.fixture
def create_assistant_message(mock_model):
    """Factory for creating assistant messages."""

    def _create(
        content: list[Any],
        stop_reason: StopReason = StopReason.STOP,
    ) -> AssistantMessage:
        return AssistantMessage(
            role="assistant",
            content=content,
            api=mock_model.api,
            provider=mock_model.provider,
            model=mock_model.id,
            usage=Usage(),
            stop_reason=stop_reason,
            timestamp=1,
        )

    return _create


@pytest.fixture
def create_user_message():
    """Factory for creating user messages."""

    def _create(text: str) -> UserMessage:
        return UserMessage(
            role="user",
            content=[TextContent(type="text", text=text)],
            timestamp=1,
        )

    return _create


@pytest.fixture
def mock_stream_class():
    """Create a mock assistant stream class."""

    class MockAssistantStream(EventStream):
        def __init__(self):
            super().__init__(
                is_complete=lambda event: event.type in ("done", "error"),
                extract_result=lambda event: (
                    event.message
                    if event.type == "done"
                    else event.error
                    if event.type == "error"
                    else AssistantMessage()
                ),
            )

    return MockAssistantStream


@pytest.fixture
def mock_stream_fn(mock_stream_class, create_assistant_message):
    """Create a mock stream function."""

    def _create(response_text: str = "ok"):
        def stream_fn(model, context, options):
            stream = mock_stream_class()

            async def push_response():
                await asyncio.sleep(0.01)  # Small delay to simulate async
                message = create_assistant_message([TextContent(type="text", text=response_text)])
                from pi_ai.types import EndEvent

                stream.push(EndEvent(type="end", message=message))

            asyncio.create_task(push_response())
            return stream

        return stream_fn

    return _create


# ============================================================================
# Agent Tests
# ============================================================================


class TestAgent:
    """Test suite for Agent class."""

    def test_create_agent_with_default_state(self):
        """Agent should create with default state."""
        agent = Agent()

        assert agent.state is not None
        assert agent.state.system_prompt == ""
        assert agent.state.model.id == "unknown"
        assert agent.state.thinking_level.value == "off"
        assert agent.state.tools == []
        assert agent.state.messages == []
        assert agent.state.is_streaming is False
        assert agent.state.streaming_message is None
        assert agent.state.pending_tool_calls == frozenset()
        assert agent.state.error_message is None

    def test_create_agent_with_custom_initial_state(self, mock_model):
        """Agent should accept custom initial state."""
        agent = Agent(
            AgentOptions(
                initial_state={
                    "system_prompt": "You are a helpful assistant.",
                    "model": mock_model,
                    "thinking_level": "low",
                }
            )
        )

        assert agent.state.system_prompt == "You are a helpful assistant."
        assert agent.state.model == mock_model
        assert agent.state.thinking_level.value == "low"

    def test_subscribe_to_events(self):
        """Agent should allow subscribing to events."""
        agent = Agent()

        event_count = 0

        def listener(event, signal):
            nonlocal event_count
            event_count += 1

        unsubscribe = agent.subscribe(listener)

        # No initial event on subscribe
        assert event_count == 0

        # State mutators don't emit events
        agent.state._tools = []  # type: ignore
        assert event_count == 0

        # Unsubscribe should work
        unsubscribe()
        assert len(agent._listeners) == 0

    @pytest.mark.asyncio
    async def test_await_async_subscribers_before_prompt_resolves(self, mock_stream_fn):
        """Agent should await async subscribers before prompt resolves."""
        barrier = asyncio.Event()
        agent = Agent(AgentOptions(stream_fn=mock_stream_fn()))

        listener_finished = False

        async def listener(event, signal):
            nonlocal listener_finished
            if isinstance(event, AgentEndEvent) or (
                isinstance(event, dict) and event.get("type") == "agent_end"
            ):
                await barrier.wait()
                listener_finished = True

        agent.subscribe(listener)

        prompt_resolved = False

        async def run_prompt():
            nonlocal prompt_resolved
            await agent.prompt("hello")
            prompt_resolved = True

        task = asyncio.create_task(run_prompt())
        await asyncio.sleep(0.05)

        assert prompt_resolved is False
        assert listener_finished is False
        assert agent.state.is_streaming is True

        barrier.set()
        await task

        assert listener_finished is True
        assert prompt_resolved is True

    @pytest.mark.asyncio
    async def test_wait_for_idle_waits_for_async_subscribers(self, mock_stream_fn):
        """wait_for_idle should wait for async subscribers."""
        barrier = asyncio.Event()
        agent = Agent(AgentOptions(stream_fn=mock_stream_fn()))

        async def listener(event, signal):
            if isinstance(event, MessageEndEvent) or (
                isinstance(event, dict) and event.get("type") == "message_end"
            ):
                message = event.message if hasattr(event, "message") else event.get("message")
                if message and message.role == "assistant":
                    await barrier.wait()

        agent.subscribe(listener)

        prompt_task = asyncio.create_task(agent.prompt("hello"))
        idle_resolved = False

        async def wait_idle():
            nonlocal idle_resolved
            await agent.wait_for_idle()
            idle_resolved = True

        idle_task = asyncio.create_task(wait_idle())
        await asyncio.sleep(0.05)

        assert idle_resolved is False
        assert agent.state.is_streaming is True

        barrier.set()
        await asyncio.gather(prompt_task, idle_task)

        assert idle_resolved is True
        assert agent.state.is_streaming is False

    def test_steering_message_queue(self, create_user_message):
        """Agent should support steering message queue."""
        agent = Agent()

        message = create_user_message("Steering message")
        agent.steer(message)

        # The message is queued but not yet in state.messages
        assert message not in agent.state.messages
        assert agent._steering_queue.has_items() is True

    def test_follow_up_message_queue(self, create_user_message):
        """Agent should support follow-up message queue."""
        agent = Agent()

        message = create_user_message("Follow-up message")
        agent.follow_up(message)

        # The message is queued but not yet in state.messages
        assert message not in agent.state.messages
        assert agent._follow_up_queue.has_items() is True

    def test_abort_controller(self):
        """Agent should handle abort controller."""
        agent = Agent()

        # Should not throw even if nothing is running
        agent.abort()

    @pytest.mark.asyncio
    async def test_throw_when_prompt_called_while_streaming(self, mock_stream_fn):
        """prompt() should throw when already streaming."""
        agent = Agent(AgentOptions(stream_fn=mock_stream_fn()))

        # Start first prompt (don't await, it will block until abort)
        first_prompt = asyncio.create_task(agent.prompt("First message"))
        await asyncio.sleep(0.05)

        assert agent.state.is_streaming is True

        # Second prompt should raise
        with pytest.raises(RuntimeError, match="Agent is already processing"):
            await agent.prompt("Second message")

        # Cleanup
        agent.abort()
        await first_prompt

    @pytest.mark.asyncio
    async def test_throw_when_continue_called_while_streaming(self, mock_stream_fn):
        """continue_run() should throw when already streaming."""
        agent = Agent(AgentOptions(stream_fn=mock_stream_fn()))

        # Start first prompt
        first_prompt = asyncio.create_task(agent.prompt("First message"))
        await asyncio.sleep(0.05)

        assert agent.state.is_streaming is True

        # continue() should raise
        with pytest.raises(RuntimeError, match="Agent is already processing"):
            await agent.continue_run()

        # Cleanup
        agent.abort()
        await first_prompt

    def test_reset_clears_state(self, create_user_message):
        """reset() should clear transcript and runtime state."""
        agent = Agent()
        agent._state.messages = [create_user_message("test")]
        agent._state.is_streaming = False
        agent._state.error_message = "error"
        agent._steering_queue.enqueue(create_user_message("steering"))
        agent._follow_up_queue.enqueue(create_user_message("follow-up"))

        agent.reset()

        assert agent.state.messages == []
        assert agent.state.is_streaming is False
        assert agent.state.error_message is None
        assert not agent._steering_queue.has_items()
        assert not agent._follow_up_queue.has_items()

    def test_queue_modes(self):
        """Agent should support different queue modes."""
        agent = Agent(
            AgentOptions(
                steering_mode="all",
                follow_up_mode="one-at-a-time",
            )
        )

        assert agent.steering_mode == "all"
        assert agent.follow_up_mode == "one-at-a-time"

        # Change modes
        agent.steering_mode = "one-at-a-time"
        agent.follow_up_mode = "all"

        assert agent.steering_mode == "one-at-a-time"
        assert agent.follow_up_mode == "all"


# ============================================================================
# Agent Loop Tests
# ============================================================================


class TestAgentLoop:
    """Test suite for agent loop functions."""

    @pytest.mark.asyncio
    async def test_emit_events_with_agent_message_types(
        self, mock_model, create_user_message, create_assistant_message
    ):
        """Should emit events with AgentMessage types."""
        context = AgentContext(
            system_prompt="You are helpful.",
            messages=[],
            tools=[],
        )

        user_prompt = create_user_message("Hello")

        from pi_agent_core.types import AgentLoopConfig

        config = AgentLoopConfig(
            model=mock_model,
            convert_to_llm=lambda messages: [
                m for m in messages if m.role in ("user", "assistant")
            ],
        )

        async def mock_stream_fn(model, ctx, options):
            stream = AgentEventStream()
            message = create_assistant_message([TextContent(type="text", text="Hi there!")])
            stream.end([user_prompt, message])
            return stream

        events = []

        async def emit(event):
            events.append(event)

        new_messages = await run_agent_loop(
            [user_prompt], context, config, emit, None, mock_stream_fn
        )

        # Should have user message and assistant message
        assert len(new_messages) == 2
        assert new_messages[0].role == "user"
        assert new_messages[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_handle_tool_calls_and_results(
        self, mock_model, create_user_message, create_assistant_message
    ):
        """Should handle tool calls and results."""
        executed = []

        tool = AgentTool(
            name="echo",
            label="Echo",
            description="Echo tool",
            parameters={"type": "object", "properties": {"value": {"type": "string"}}},
        )

        async def execute_tool(tool_call_id, params, signal, on_update):
            executed.append(params.get("value"))
            return AgentToolResult(
                content=[TextContent(type="text", text=f"echoed: {params.get('value')}")],
                details={"value": params.get("value")},
            )

        tool.execute = execute_tool

        context = AgentContext(
            system_prompt="",
            messages=[],
            tools=[tool],
        )

        user_prompt = create_user_message("echo something")

        from pi_agent_core.types import AgentLoopConfig

        config = AgentLoopConfig(
            model=mock_model,
            convert_to_llm=lambda messages: [
                m for m in messages if m.role in ("user", "assistant")
            ],
        )

        call_index = 0

        async def mock_stream_fn(model, ctx, options):
            nonlocal call_index
            stream = AgentEventStream()

            if call_index == 0:
                # First call: return tool call
                message = create_assistant_message(
                    [
                        ToolCall(
                            type="toolCall", id="tool-1", name="echo", arguments={"value": "hello"}
                        )
                    ],
                    StopReason.TOOL_USE,
                )
            else:
                # Second call: return final response
                message = create_assistant_message([TextContent(type="text", text="done")])

            call_index += 1
            stream.end([message])
            return stream

        events = []

        async def emit(event):
            events.append(event)

        await run_agent_loop([user_prompt], context, config, emit, None, mock_stream_fn)

        # Tool should have been executed
        assert executed == ["hello"]

        # Should have tool execution events
        tool_starts = [
            e
            for e in events
            if isinstance(e, ToolExecutionStartEvent)
            or (isinstance(e, dict) and e.get("type") == "tool_execution_start")
        ]
        tool_ends = [
            e
            for e in events
            if isinstance(e, ToolExecutionEndEvent)
            or (isinstance(e, dict) and e.get("type") == "tool_execution_end")
        ]
        assert len(tool_starts) > 0
        assert len(tool_ends) > 0

    @pytest.mark.asyncio
    async def test_execute_tool_calls_in_parallel(
        self, mock_model, create_user_message, create_assistant_message
    ):
        """Should execute tool calls in parallel."""
        executed = []
        first_started = asyncio.Event()
        first_release = asyncio.Event()

        tool = AgentTool(
            name="echo",
            label="Echo",
            description="Echo tool",
            parameters={"type": "object", "properties": {"value": {"type": "string"}}},
        )

        async def execute_tool(tool_call_id, params, signal, on_update):
            value = params.get("value")
            if value == "first":
                first_started.set()
                await first_release.wait()
            elif value == "second":
                # Check if first is still waiting (parallel execution)
                if not first_release.is_set():
                    executed.append("parallel_observed")
            executed.append(value)
            return AgentToolResult(
                content=[TextContent(type="text", text=f"echoed: {value}")],
                details={"value": value},
            )

        tool.execute = execute_tool

        context = AgentContext(
            system_prompt="",
            messages=[],
            tools=[tool],
        )

        user_prompt = create_user_message("echo both")

        from pi_agent_core.types import AgentLoopConfig

        config = AgentLoopConfig(
            model=mock_model,
            convert_to_llm=lambda messages: [
                m for m in messages if m.role in ("user", "assistant")
            ],
            tool_execution="parallel",
        )

        call_index = 0

        async def mock_stream_fn(model, ctx, options):
            nonlocal call_index
            stream = AgentEventStream()

            if call_index == 0:
                message = create_assistant_message(
                    [
                        ToolCall(
                            type="toolCall", id="tool-1", name="echo", arguments={"value": "first"}
                        ),
                        ToolCall(
                            type="toolCall", id="tool-2", name="echo", arguments={"value": "second"}
                        ),
                    ],
                    StopReason.TOOL_USE,
                )
            else:
                message = create_assistant_message([TextContent(type="text", text="done")])

            call_index += 1
            stream.end([message])
            return stream

        events = []

        async def emit(event):
            events.append(event)

        async def run():
            await run_agent_loop([user_prompt], context, config, emit, None, mock_stream_fn)

        task = asyncio.create_task(run())
        await first_started.wait()
        first_release.set()
        await task

        # Both tools should have executed
        assert "first" in executed
        assert "second" in executed

    @pytest.mark.asyncio
    async def test_agent_loop_continue_without_user_message_events(
        self, mock_model, create_user_message, create_assistant_message
    ):
        """agent_loop_continue should not emit user message events."""
        user_message = create_user_message("Hello")

        context = AgentContext(
            system_prompt="You are helpful.",
            messages=[user_message],
            tools=[],
        )

        from pi_agent_core.types import AgentLoopConfig

        config = AgentLoopConfig(
            model=mock_model,
            convert_to_llm=lambda messages: [
                m for m in messages if m.role in ("user", "assistant")
            ],
        )

        async def mock_stream_fn(model, ctx, options):
            stream = AgentEventStream()
            message = create_assistant_message([TextContent(type="text", text="Response")])
            stream.end([message])
            return stream

        events = []

        async def emit(event):
            events.append(event)

        new_messages = await run_agent_loop_continue(context, config, emit, None, mock_stream_fn)

        # Should only return the new assistant message
        assert len(new_messages) == 1
        assert new_messages[0].role == "assistant"

        # Should NOT have user message events
        message_ends = [
            e
            for e in events
            if isinstance(e, MessageEndEvent)
            or (isinstance(e, dict) and e.get("type") == "message_end")
        ]
        assert len(message_ends) == 1
        message = (
            message_ends[0].message
            if hasattr(message_ends[0], "message")
            else message_ends[0].get("message")
        )
        assert message.role == "assistant"

    @pytest.mark.asyncio
    async def test_throw_when_continue_with_no_messages(self, mock_model):
        """agent_loop_continue should throw when context has no messages."""
        context = AgentContext(
            system_prompt="You are helpful.",
            messages=[],
            tools=[],
        )

        from pi_agent_core.types import AgentLoopConfig

        config = AgentLoopConfig(
            model=mock_model,
            convert_to_llm=lambda messages: messages,
        )

        async def emit(event):
            pass

        with pytest.raises(ValueError, match="Cannot continue: no messages in context"):
            await run_agent_loop_continue(context, config, emit)


# ============================================================================
# State Management Tests
# ============================================================================


class TestStateManagement:
    """Test suite for state management."""

    def test_agent_state_tools_copy(self):
        """AgentState should copy tools on get/set."""
        state = AgentState()
        tools = [AgentTool(name="test", label="Test", description="Test tool", parameters={})]

        state._tools = tools

        # Get should return copy
        got_tools = state.tools
        assert got_tools == tools
        assert got_tools is not tools

    def test_agent_state_messages_copy(self):
        """AgentState should copy messages on get/set."""
        state = AgentState()
        messages = [UserMessage(role="user", content="test", timestamp=1)]

        state._messages = messages

        # Get should return copy
        got_messages = state.messages
        assert got_messages == messages
        assert got_messages is not messages

    def test_pending_tool_calls_frozen(self):
        """pending_tool_calls should be immutable."""
        state = AgentState()
        state._pending_tool_calls = {"tool-1", "tool-2"}

        pending = state.pending_tool_calls
        assert pending == frozenset({"tool-1", "tool-2"})

        # Should not be modifiable
        with pytest.raises(AttributeError):
            pending.add("tool-3")


# ============================================================================
# Queue Tests
# ============================================================================


class TestPendingMessageQueue:
    """Test suite for PendingMessageQueue."""

    def test_enqueue_and_drain_all_mode(self, create_user_message):
        """Queue in 'all' mode should drain all messages."""
        from pi_agent_core.agent import PendingMessageQueue

        queue = PendingMessageQueue(mode="all")

        msg1 = create_user_message("1")
        msg2 = create_user_message("2")

        queue.enqueue(msg1)
        queue.enqueue(msg2)

        drained = queue.drain()
        assert len(drained) == 2
        assert msg1 in drained
        assert msg2 in drained
        assert not queue.has_items()

    def test_enqueue_and_drain_one_at_a_time_mode(self, create_user_message):
        """Queue in 'one-at-a-time' mode should drain one message."""
        from pi_agent_core.agent import PendingMessageQueue

        queue = PendingMessageQueue(mode="one-at-a-time")

        msg1 = create_user_message("1")
        msg2 = create_user_message("2")

        queue.enqueue(msg1)
        queue.enqueue(msg2)

        drained1 = queue.drain()
        assert len(drained1) == 1
        assert drained1[0] == msg1
        assert queue.has_items()

        drained2 = queue.drain()
        assert len(drained2) == 1
        assert drained2[0] == msg2
        assert not queue.has_items()

    def test_clear_queue(self, create_user_message):
        """Queue should clear all messages."""
        from pi_agent_core.agent import PendingMessageQueue

        queue = PendingMessageQueue()

        queue.enqueue(create_user_message("1"))
        queue.enqueue(create_user_message("2"))

        queue.clear()

        assert not queue.has_items()
        assert queue.drain() == []
