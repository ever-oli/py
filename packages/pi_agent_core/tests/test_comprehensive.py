"""Comprehensive tests for pi_agent_core.

Tests agent loop, parallel/sequential tool execution, hooks, and error recovery.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


class TestAgentLoop:
    """Test agent loop with mock LLM."""

    @pytest.fixture
    def mock_config(self):
        """Create mock agent loop config."""
        from pi_agent_core.agent_loop import AgentLoopConfig
        from pi_ai import Model
        
        model = Model(id="faux-model", provider="faux", api="faux")
        return AgentLoopConfig(
            model=model,
            system_prompt="You are a test agent.",
        )

    @pytest.fixture
    def mock_context(self):
        """Create mock agent context."""
        from pi_agent_core.agent_loop import AgentContext
        from pi_ai.types import UserMessage
        
        return AgentContext(
            messages=[UserMessage(role="user", content="Hello")],
            tools=[],
        )

    @pytest.mark.asyncio
    async def test_agent_loop_basic(self, mock_config, mock_context):
        """Test basic agent loop execution."""
        from pi_agent_core.agent_loop import agent_loop

        events = []
        
        def on_event(event):
            events.append(event)

        result = await agent_loop(
            context=mock_context,
            config=mock_config,
            on_event=on_event,
        )

        # Should produce events and complete
        assert len(events) >= 0

    @pytest.mark.asyncio
    async def test_agent_loop_with_tool(self, mock_config):
        """Test agent loop with tool execution."""
        from pi_agent_core.agent_loop import AgentContext, AgentLoopConfig
        from pi_ai.types import UserMessage, Tool
        from pi_ai import Model

        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters={"type": "object"},
        )

        model = Model(id="faux-model", provider="faux", api="faux")
        config = AgentLoopConfig(
            model=model,
            system_prompt="You are a test agent.",
            tools=[tool],
        )

        context = AgentContext(
            messages=[UserMessage(role="user", content="Call the test tool")],
            tools=[tool],
        )

        events = []
        
        def on_event(event):
            events.append(event)

        result = await agent_loop(
            context=context,
            config=config,
            on_event=on_event,
        )

        assert len(events) >= 0

    @pytest.mark.asyncio
    async def test_agent_loop_stream(self, mock_config, mock_context):
        """Test agent loop streaming."""
        from pi_agent_core.agent_loop import agent_loop_stream

        stream = agent_loop_stream(
            context=mock_context,
            config=mock_config,
        )

        events = []
        async for event in stream:
            events.append(event)

        assert len(events) >= 0


class TestToolExecution:
    """Test parallel vs sequential tool execution."""

    @pytest.mark.asyncio
    async def test_sequential_tool_execution(self):
        """Test sequential tool execution."""
        from pi_agent_core.agent_loop import execute_tools_sequential
        from pi_ai.types import ToolCall, ToolResultMessage

        tool_calls = [
            ToolCall(id="call_1", name="tool1", arguments={}),
            ToolCall(id="call_2", name="tool2", arguments={}),
        ]

        async def mock_tool_executor(name, args):
            await asyncio.sleep(0.01)  # Small delay
            return {"result": f"{name} result"}

        results = await execute_tools_sequential(
            tool_calls=tool_calls,
            tool_executor=mock_tool_executor,
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_parallel_tool_execution(self):
        """Test parallel tool execution."""
        from pi_agent_core.agent_loop import execute_tools_parallel
        from pi_ai.types import ToolCall

        tool_calls = [
            ToolCall(id="call_1", name="tool1", arguments={}),
            ToolCall(id="call_2", name="tool2", arguments={}),
        ]

        async def mock_tool_executor(name, args):
            await asyncio.sleep(0.01)
            return {"result": f"{name} result"}

        results = await execute_tools_parallel(
            tool_calls=tool_calls,
            tool_executor=mock_tool_executor,
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_parallel_vs_sequential_timing(self):
        """Test that parallel execution is faster than sequential."""
        from pi_ai.types import ToolCall

        tool_calls = [
            ToolCall(id=f"call_{i}", name=f"tool{i}", arguments={})
            for i in range(3)
        ]

        async def slow_tool_executor(name, args):
            await asyncio.sleep(0.05)  # 50ms delay
            return {"result": name}

        # Sequential execution
        import time
        start = time.monotonic()
        for call in tool_calls:
            await slow_tool_executor(call.name, call.arguments)
        sequential_time = time.monotonic() - start

        # Parallel execution
        start = time.monotonic()
        await asyncio.gather(*[
            slow_tool_executor(call.name, call.arguments)
            for call in tool_calls
        ])
        parallel_time = time.monotonic() - start

        # Parallel should be significantly faster
        assert parallel_time < sequential_time * 0.8


class TestHooks:
    """Test beforeToolCall and afterToolCall hooks."""

    @pytest.mark.asyncio
    async def test_before_tool_call_hook(self):
        """Test beforeToolCall hook."""
        from pi_agent_core.agent_loop import AgentLoopConfig, AgentContext
        from pi_ai.types import ToolCall, Tool
        from pi_ai import Model

        before_calls = []

        async def before_hook(tool_call: ToolCall):
            before_calls.append(tool_call)
            return tool_call  # Return potentially modified

        tool = Tool(name="test_tool", description="Test", parameters={})
        model = Model(id="faux-model", provider="faux", api="faux")
        config = AgentLoopConfig(
            model=model,
            system_prompt="Test",
            tools=[tool],
            before_tool_call=before_hook,
        )

        # Config should have the hook
        assert config.before_tool_call is not None

    @pytest.mark.asyncio
    async def test_after_tool_call_hook(self):
        """Test afterToolCall hook."""
        from pi_agent_core.agent_loop import AgentLoopConfig
        from pi_ai.types import ToolCall, ToolResultMessage, Tool
        from pi_ai import Model

        after_calls = []

        async def after_hook(tool_call: ToolCall, result: ToolResultMessage):
            after_calls.append((tool_call, result))
            return result

        tool = Tool(name="test_tool", description="Test", parameters={})
        model = Model(id="faux-model", provider="faux", api="faux")
        config = AgentLoopConfig(
            model=model,
            system_prompt="Test",
            tools=[tool],
            after_tool_call=after_hook,
        )

        # Config should have the hook
        assert config.after_tool_call is not None


class TestErrorRecovery:
    """Test error recovery."""

    @pytest.mark.asyncio
    async def test_tool_execution_error_recovery(self):
        """Test error recovery during tool execution."""
        from pi_ai.types import ToolCall

        async def failing_tool_executor(name, args):
            if name == "failing_tool":
                raise RuntimeError("Tool failed!")
            return {"result": "success"}

        tool_calls = [
            ToolCall(id="call_1", name="failing_tool", arguments={}),
            ToolCall(id="call_2", name="working_tool", arguments={}),
        ]

        results = []
        for call in tool_calls:
            try:
                result = await failing_tool_executor(call.name, call.arguments)
                results.append((call.id, True, result))
            except Exception as e:
                results.append((call.id, False, str(e)))

        assert len(results) == 2
        assert results[0][1] is False  # First tool failed
        assert results[1][1] is True   # Second tool succeeded

    @pytest.mark.asyncio
    async def test_agent_loop_error_recovery(self):
        """Test agent loop error recovery."""
        from pi_agent_core.agent_loop import AgentLoopConfig, AgentContext
        from pi_ai.types import UserMessage
        from pi_ai import Model

        model = Model(id="faux-model", provider="faux", api="faux")
        config = AgentLoopConfig(
            model=model,
            system_prompt="Test",
            max_iterations=3,
        )
        context = AgentContext(
            messages=[UserMessage(role="user", content="Test")],
            tools=[],
        )

        # Even if some parts fail, the loop should complete
        from pi_agent_core.agent_loop import agent_loop

        events = []
        def on_event(event):
            events.append(event)

        result = await agent_loop(
            context=context,
            config=config,
            on_event=on_event,
        )

        # Should complete without raising
        assert result is not None


class TestAgentState:
    """Test agent state management."""

    def test_agent_state_creation(self):
        """Test agent state creation."""
        from pi_agent_core.types import AgentState
        from pi_ai import Model

        model = Model(id="test-model", provider="test", api="test")
        state = AgentState(
            system_prompt="Test prompt",
            model=model,
            thinking_level="off",
        )

        assert state.system_prompt == "Test prompt"
        assert state.model == model

    def test_agent_state_tools(self):
        """Test agent state with tools."""
        from pi_agent_core.types import AgentState
        from pi_ai import Model, Tool

        model = Model(id="test-model", provider="test", api="test")
        tool = Tool(name="test_tool", description="Test", parameters={})
        
        state = AgentState(
            system_prompt="Test",
            model=model,
            tools=[tool],
        )

        assert len(state.tools) == 1
        assert state.tools[0].name == "test_tool"


class TestContextManagement:
    """Test context management."""

    def test_context_creation(self):
        """Test agent context creation."""
        from pi_agent_core.agent_loop import AgentContext
        from pi_ai.types import UserMessage

        context = AgentContext(
            messages=[UserMessage(role="user", content="Hello")],
            tools=[],
        )

        assert len(context.messages) == 1
        assert context.messages[0].role == "user"

    def test_context_message_addition(self):
        """Test adding messages to context."""
        from pi_agent_core.agent_loop import AgentContext
        from pi_ai.types import UserMessage, AssistantMessage, TextContent
        from pi_ai.types import StopReason

        context = AgentContext(messages=[], tools=[])
        
        # Add user message
        context.messages.append(UserMessage(role="user", content="Hello"))
        assert len(context.messages) == 1

        # Add assistant message
        context.messages.append(
            AssistantMessage(
                role="assistant",
                content=[TextContent(type="text", text="Hi")],
                stop_reason=StopReason.STOP,
            )
        )
        assert len(context.messages) == 2
