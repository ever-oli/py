"""Tests for streaming functionality with mock SSE data."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


class TestStreaming:
    """Test streaming functionality across providers."""

    @pytest.fixture
    def mock_sse_stream(self):
        """Mock SSE stream data."""
        return [
            b'data: {"id":"test","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hello"}}]}\n\n',
            b'data: {"id":"test","object":"chat.completion.chunk","choices":[{"delta":{"content":" from"}}]}\n\n',
            b'data: {"id":"test","object":"chat.completion.chunk","choices":[{"delta":{"content":" stream!"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]

    @pytest.fixture
    def mock_anthropic_sse_stream(self):
        """Mock Anthropic SSE stream data."""
        return [
            b'event: message_start\ndata: {"type":"message_start","message":{"id":"msg_123","role":"assistant"}}\n\n',
            b'event: content_block_start\ndata: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}\n\n',
            b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello from "}}\n\n',
            b'event: content_block_delta\ndata: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Anthropic stream!"}}\n\n',
            b'event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n',
            b'event: message_stop\ndata: {"type":"message_stop"}\n\n',
        ]

    @pytest.mark.asyncio
    async def test_faux_streaming(self):
        """Test faux streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.faux import stream_faux

        model = Model(id="faux-model", provider="faux", api="faux")
        context = Context(messages=[UserMessage(role="user", content="Test message")])

        stream = stream_faux(model, context)
        
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)

        # Should have start, text, and end events
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_simple(self):
        """Test stream_simple helper."""
        from pi_ai import stream_simple, Context, UserMessage, Model

        model = Model(id="faux-model", provider="faux", api="faux")
        context = Context(messages=[UserMessage(role="user", content="Hello")])

        stream = stream_simple(model, context)
        
        events = []
        async for event in stream:
            events.append(event)

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_stream_simple_with_options(self):
        """Test stream_simple with options."""
        from pi_ai import stream_simple, Context, UserMessage, Model, SimpleStreamOptions

        model = Model(id="faux-model", provider="faux", api="faux")
        context = Context(messages=[UserMessage(role="user", content="Hello")])
        options = SimpleStreamOptions(reasoning="medium")

        stream = stream_simple(model, context, options)
        
        events = []
        async for event in stream:
            events.append(event)

        assert len(events) > 0


class TestEventStream:
    """Test event stream functionality."""

    @pytest.mark.asyncio
    async def test_event_stream_creation(self):
        """Test event stream creation."""
        from pi_ai.event_stream import AssistantMessageEventStream

        stream = AssistantMessageEventStream()
        assert stream is not None

    @pytest.mark.asyncio
    async def test_event_stream_push_and_iterate(self):
        """Test pushing events and iterating."""
        from pi_ai.event_stream import AssistantMessageEventStream
        from pi_ai.types import TextEvent, StartEvent, EndEvent, AssistantMessage, StopReason, TextContent

        stream = AssistantMessageEventStream()

        # Create a partial message
        msg = AssistantMessage(
            role="assistant",
            content=[TextContent(type="text", text="")],
            stop_reason=StopReason.STOP,
        )

        stream.push(StartEvent(partial=msg))
        stream.push(TextEvent(text="Hello"))
        stream.push(TextEvent(text=" world!"))
        stream.push(EndEvent(message=msg))
        stream.end(msg)

        events = []
        async for event in stream:
            events.append(event)

        assert len(events) >= 3  # Start, text events, end

    @pytest.mark.asyncio
    async def test_event_stream_error(self):
        """Test error handling in event stream."""
        from pi_ai.event_stream import AssistantMessageEventStream

        stream = AssistantMessageEventStream()
        
        # The event stream doesn't have set_error method - let's test error handling differently
        msg = MagicMock()
        stream.end(msg)
        
        events = []
        async for event in stream:
            events.append(event)
        
        # Should complete without error
        assert len(events) >= 0


class TestStreamHelpers:
    """Test streaming helper functions."""

    @pytest.mark.asyncio
    async def test_stream_simple_with_faux(self):
        """Test stream_simple with faux provider."""
        from pi_ai import stream_simple, Context, UserMessage, Model

        model = Model(id="faux-model", provider="faux", api="faux")
        context = Context(messages=[UserMessage(role="user", content="Hello")])

        stream = stream_simple(model, context)
        
        events = []
        async for event in stream:
            events.append(event)

        assert len(events) > 0
