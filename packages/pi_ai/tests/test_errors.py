"""Tests for error handling, retries, and timeouts."""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


class TestErrorHandling:
    """Test error handling in pi_ai."""

    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Test handling of network timeouts."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.openai_completions import stream_openai_completions

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=asyncio.TimeoutError("Connection timed out"))
            mock_client_class.return_value = mock_client

            model = Model(id="gpt-4", provider="openai", api="openai")
            context = Context(messages=[UserMessage(role="user", content="Hello")])

            stream = stream_openai_completions(model, context)
            
            # Errors are captured as ErrorEvent, not raised
            events = []
            async for event in stream:
                events.append(event)
            
            # Should have an error event
            assert len(events) > 0
            assert events[-1].type == "error"
            assert "timed out" in events[-1].error.error_message.lower() or "timeout" in events[-1].error.error_message.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test handling of connection errors."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.openai_completions import stream_openai_completions

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=ConnectionError("Failed to connect"))
            mock_client_class.return_value = mock_client

            model = Model(id="gpt-4", provider="openai", api="openai")
            context = Context(messages=[UserMessage(role="user", content="Hello")])

            stream = stream_openai_completions(model, context)
            
            # Errors are captured as ErrorEvent, not raised
            events = []
            async for event in stream:
                events.append(event)
            
            # Should have an error event
            assert len(events) > 0
            assert events[-1].type == "error"
            assert "connect" in events[-1].error.error_message.lower() or "failed" in events[-1].error.error_message.lower()

    @pytest.mark.asyncio
    async def test_http_500_error(self):
        """Test handling of HTTP 500 errors."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.anthropic_provider import stream_anthropic

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json = Mock(return_value={"error": {"message": "Internal server error"}})
        mock_response.text = '{"error": {"message": "Internal server error"}}'

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="claude-3-opus", provider="anthropic", api="anthropic")
            context = Context(messages=[UserMessage(role="user", content="Hello")])

            stream = stream_anthropic(model, context)
            
            # Errors are captured as ErrorEvent, not raised
            events = []
            async for event in stream:
                events.append(event)
            
            # Should have an error event
            assert len(events) > 0
            assert events[-1].type == "error"
            assert "500" in events[-1].error.error_message.lower() or "internal" in events[-1].error.error_message.lower()

    @pytest.mark.asyncio
    async def test_http_401_unauthorized(self):
        """Test handling of HTTP 401 unauthorized errors."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.openai_completions import stream_openai_completions

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json = Mock(return_value={"error": {"message": "Invalid API key"}})
        mock_response.text = '{"error": {"message": "Invalid API key"}}'

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="gpt-4", provider="openai", api="openai")
            context = Context(messages=[UserMessage(role="user", content="Hello")])

            stream = stream_openai_completions(model, context)
            
            # Errors are captured as ErrorEvent, not raised
            events = []
            async for event in stream:
                events.append(event)
            
            # Should have an error event
            assert len(events) > 0
            assert events[-1].type == "error"
            assert "401" in events[-1].error.error_message.lower() or "unauthorized" in events[-1].error.error_message.lower()

    @pytest.mark.asyncio
    async def test_http_403_forbidden(self):
        """Test handling of HTTP 403 forbidden errors."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.openai_completions import stream_openai_completions

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json = Mock(return_value={"error": {"message": "Access forbidden"}})
        mock_response.text = '{"error": {"message": "Access forbidden"}}'

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="gpt-4", provider="openai", api="openai")
            context = Context(messages=[UserMessage(role="user", content="Hello")])

            stream = stream_openai_completions(model, context)
            
            # Errors are captured as ErrorEvent, not raised
            events = []
            async for event in stream:
                events.append(event)
            
            # Should have an error event
            assert len(events) > 0
            assert events[-1].type == "error"
            assert "403" in events[-1].error.error_message.lower() or "forbidden" in events[-1].error.error_message.lower()


class TestValidationErrors:
    """Test input validation errors."""

    def test_valid_thinking_levels(self):
        """Test valid thinking levels."""
        from pi_ai.types import ThinkingLevel
        
        assert ThinkingLevel.OFF == "off"
        assert ThinkingLevel.LOW == "low"
        assert ThinkingLevel.MEDIUM == "medium"
        assert ThinkingLevel.HIGH == "high"
        assert ThinkingLevel.XHIGH == "xhigh"

    def test_invalid_thinking_level(self):
        """Test validation of invalid thinking level."""
        from pi_ai.types import ThinkingLevel
        
        # Should raise ValueError for invalid level
        with pytest.raises(ValueError):
            ThinkingLevel("invalid_level")
