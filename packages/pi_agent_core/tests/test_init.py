"""Basic tests for pi_agent_core package."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pi_agent_core import QueueMode, ToolExecutionMode


def test_package_imports():
    """Test that all main exports can be imported."""
    from pi_agent_core import (
        Agent,
        AgentOptions,
    )

    # Just verify they exist and are importable
    assert Agent is not None
    assert AgentOptions is not None


def test_version():
    """Test package version."""
    from pi_agent_core import __version__

    assert __version__ == "0.1.0"


def test_agent_creation():
    """Test basic agent creation."""
    from pi_agent_core import Agent, AgentOptions

    agent = Agent()
    assert agent is not None
    assert agent.state is not None

    agent_with_options = Agent(AgentOptions())
    assert agent_with_options is not None


def test_agent_state_properties():
    """Test agent state properties."""
    from pi_agent_core import Agent

    agent = Agent()
    state = agent.state

    assert isinstance(state.system_prompt, str)
    assert hasattr(state, "model")
    assert hasattr(state, "thinking_level")
    assert hasattr(state, "tools")
    assert hasattr(state, "messages")
    assert hasattr(state, "is_streaming")
    assert hasattr(state, "streaming_message")
    assert hasattr(state, "pending_tool_calls")
    assert hasattr(state, "error_message")


def test_tool_creation():
    """Test tool creation."""
    from pi_agent_core import AgentTool

    tool = AgentTool(
        name="test_tool",
        label="Test Tool",
        description="A test tool",
        parameters={"type": "object", "properties": {}},
    )

    assert tool.name == "test_tool"
    assert tool.label == "Test Tool"


def test_event_types():
    """Test event type creation."""
    from pi_agent_core.types import (
        AgentEndEvent,
        AgentStartEvent,
        MessageEndEvent,
        MessageStartEvent,
        TurnEndEvent,
        TurnStartEvent,
    )
    from pi_ai.types import AssistantMessage

    start = AgentStartEvent()
    assert start.type == "agent_start"

    end = AgentEndEvent(messages=[])
    assert end.type == "agent_end"

    turn_start = TurnStartEvent()
    assert turn_start.type == "turn_start"

    turn_end = TurnEndEvent(message=AssistantMessage())
    assert turn_end.type == "turn_end"

    msg_start = MessageStartEvent(message=AssistantMessage())
    assert msg_start.type == "message_start"

    msg_end = MessageEndEvent(message=AssistantMessage())
    assert msg_end.type == "message_end"


def test_queue_modes():
    """Test queue mode values."""

    # These should be valid literal values
    all_mode: QueueMode = "all"
    one_at_a_time_mode: QueueMode = "one-at-a-time"

    assert all_mode == "all"
    assert one_at_a_time_mode == "one-at-a-time"


def test_tool_execution_modes():
    """Test tool execution mode values."""

    sequential: ToolExecutionMode = "sequential"
    parallel: ToolExecutionMode = "parallel"

    assert sequential == "sequential"
    assert parallel == "parallel"
