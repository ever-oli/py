"""Tests for message conversion for all types."""
from __future__ import annotations

import pytest
from pi_ai.types import (
    AssistantMessage,
    Cost,
    ImageContent,
    TextContent,
    Tool,
    ToolCall,
    ToolResultMessage,
    Usage,
    UserMessage,
)


class TestMessageConversion:
    """Test message type conversions."""

    def test_user_message_creation(self):
        """Test UserMessage creation."""
        msg = UserMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_user_message_with_image(self):
        """Test UserMessage with image content."""
        msg = UserMessage(
            role="user",
            content=[
                TextContent(type="text", text="Look at this image:"),
                ImageContent(type="image", data="base64encoded", mime_type="image/jpeg"),
            ]
        )
        assert len(msg.content) == 2
        assert msg.content[0].text == "Look at this image:"
        assert msg.content[1].data == "base64encoded"

    def test_assistant_message_creation(self):
        """Test AssistantMessage creation."""
        from pi_ai.types import StopReason
        
        msg = AssistantMessage(
            role="assistant",
            content=[TextContent(type="text", text="Hello there")],
            stop_reason=StopReason.STOP,
        )
        assert msg.role == "assistant"
        assert msg.content[0].text == "Hello there"
        assert msg.stop_reason == StopReason.STOP

    def test_assistant_message_with_tool_calls(self):
        """Test AssistantMessage with tool calls."""
        from pi_ai.types import StopReason
        
        msg = AssistantMessage(
            role="assistant",
            content=[
                ToolCall(
                    id="call_123",
                    name="get_weather",
                    arguments='{"location": "NYC"}',
                )
            ],
            stop_reason=StopReason.TOOL_USE,
        )
        assert len(msg.content) == 1
        assert msg.content[0].name == "get_weather"
        assert msg.stop_reason == StopReason.TOOL_USE

    def test_tool_result_message(self):
        """Test ToolResultMessage creation."""
        msg = ToolResultMessage(
            role="toolResult",
            tool_call_id="call_123",
            tool_name="get_weather",
            content=[TextContent(type="text", text="72°F in NYC")],
            is_error=False,
        )
        assert msg.tool_call_id == "call_123"
        assert msg.tool_name == "get_weather"
        assert not msg.is_error

    def test_tool_result_message_with_error(self):
        """Test ToolResultMessage with error."""
        msg = ToolResultMessage(
            role="toolResult",
            tool_call_id="call_123",
            tool_name="get_weather",
            content=[TextContent(type="text", text="Error: API failed")],
            is_error=True,
        )
        assert msg.is_error


class TestToolConversion:
    """Test tool conversion utilities."""

    def test_tool_creation(self):
        """Test Tool creation."""
        tool = Tool(
            name="get_weather",
            description="Get weather for a location",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name"},
                },
                "required": ["location"],
            },
        )
        assert tool.name == "get_weather"
        assert tool.parameters["type"] == "object"

    def test_tool_call_creation(self):
        """Test ToolCall creation."""
        call = ToolCall(
            id="call_123",
            name="get_weather",
            arguments='{"location": "NYC"}',
        )
        assert call.id == "call_123"
        assert call.name == "get_weather"
        assert call.arguments == '{"location": "NYC"}'


class TestUsageConversion:
    """Test usage and cost calculations."""

    def test_usage_creation(self):
        """Test Usage creation."""
        usage = Usage(
            input=100,
            output=50,
            total_tokens=155,
        )
        assert usage.input == 100
        assert usage.output == 50
        assert usage.total_tokens == 155

    def test_usage_with_cost(self):
        """Test Usage with cost."""
        cost = Cost(
            input=0.01,
            output=0.02,
            cache_read=0.001,
            cache_write=0.002,
            total=0.033,
        )
        usage = Usage(
            input=100,
            output=50,
            cost=cost,
        )
        
        assert usage.cost.total == 0.033
        assert usage.cost.input == 0.01
        assert usage.cost.output == 0.02

    def test_cost_calculation(self):
        """Test cost calculation."""
        cost = Cost(
            input=0.001,
            output=0.002,
            total=0.003,
        )
        assert cost.input + cost.output == cost.total


class TestContextCreation:
    """Test context creation."""

    def test_context_with_messages(self):
        """Test Context with messages."""
        from pi_ai.types import Context
        
        context = Context(
            messages=[
                UserMessage(role="user", content="Hello"),
                UserMessage(role="assistant", content="Hi there"),
            ]
        )
        assert len(context.messages) == 2

    def test_context_with_tools(self):
        """Test Context with tools."""
        from pi_ai.types import Context
        
        tool = Tool(
            name="get_weather",
            description="Get weather",
            parameters={"type": "object"},
        )
        context = Context(
            messages=[UserMessage(role="user", content="What's the weather?")],
            tools=[tool],
        )
        assert len(context.tools) == 1
        assert context.tools[0].name == "get_weather"

    def test_context_with_system(self):
        """Test Context with system prompt."""
        from pi_ai.types import Context
        
        context = Context(
            messages=[UserMessage(role="user", content="Hello")],
            system="You are a helpful assistant.",
        )
        assert context.system == "You are a helpful assistant."


class TestModelCreation:
    """Test model creation."""

    def test_model_creation(self):
        """Test Model creation."""
        from pi_ai.types import Model
        
        model = Model(
            id="gpt-4",
            provider="openai",
            api="openai",
        )
        assert model.id == "gpt-4"
        assert model.provider == "openai"
        assert model.api == "openai"


class TestStopReason:
    """Test StopReason enum."""

    def test_stop_reason_values(self):
        """Test StopReason values."""
        from pi_ai.types import StopReason
        
        assert StopReason.STOP == "stop"
        assert StopReason.LENGTH == "length"
        assert StopReason.TOOL_USE == "toolUse"
        assert StopReason.ERROR == "error"
        assert StopReason.ABORTED == "aborted"


class TestContentTypes:
    """Test content type conversions."""

    def test_text_content(self):
        """Test TextContent."""
        content = TextContent(type="text", text="Hello world")
        assert content.type == "text"
        assert content.text == "Hello world"

    def test_image_content_with_source(self):
        """Test ImageContent with base64 data."""
        content = ImageContent(
            type="image",
            data="base64image==",
            mime_type="image/png",
        )
        assert content.type == "image"
        assert content.data == "base64image=="
        assert content.mime_type == "image/png"

    def test_image_content_with_base64(self):
        """Test ImageContent with base64."""
        content = ImageContent(
            type="image",
            data="iVBORw0KGgo=",
            mime_type="image/png",
        )
        assert content.data == "iVBORw0KGgo="
        assert content.mime_type == "image/png"
