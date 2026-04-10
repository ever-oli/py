"""Comprehensive tests for pi_ai providers.

Tests all 10 providers with mock HTTP responses.
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


class TestFauxProvider:
    """Test Faux provider."""

    @pytest.mark.asyncio
    async def test_stream_faux(self):
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
    async def test_faux_echoes_message(self):
        """Test that faux echoes user message."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.faux import stream_faux
        from pi_ai.types import EndEvent

        model = Model(id="faux-model", provider="faux", api="faux")
        context = Context(messages=[UserMessage(role="user", content="Hello there")])

        stream = stream_faux(model, context)
        
        final_message = None
        async for event in stream:
            if isinstance(event, EndEvent):
                final_message = event.message

        assert final_message is not None
        # Check that the response contains the echoed message
        content_text = ""
        for content in final_message.content:
            if hasattr(content, 'text'):
                content_text += content.text
        assert "Hello there" in content_text or "[FAUX]" in content_text


class TestOpenAICompletionsProvider:
    """Test OpenAI completions provider."""

    @pytest.mark.asyncio
    async def test_stream_openai_completions(self):
        """Test OpenAI completions streaming."""
        from pi_ai.types import Context, Model, Tool, UserMessage
        from pi_ai.providers.openai_completions import stream_openai_completions

        # Mock the httpx client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'data: {"id":"test","object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hello"}}]}',
            b'',
            b'data: {"id":"test","object":"chat.completion.chunk","choices":[{"delta":{"content":" world"}}]}',
            b'',
            b'data: [DONE]',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="gpt-4", provider="openai", api="openai")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_openai_completions(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestAnthropicProvider:
    """Test Anthropic provider."""

    @pytest.mark.asyncio
    async def test_stream_anthropic(self):
        """Test Anthropic streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.anthropic_provider import stream_anthropic

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'event: message_start',
            b'data: {"type":"message_start","message":{"id":"msg_123","role":"assistant"}}',
            b'',
            b'event: content_block_delta',
            b'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello from Anthropic"}}',
            b'',
            b'event: message_stop',
            b'data: {"type":"message_stop"}',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="claude-3-opus", provider="anthropic", api="anthropic")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_anthropic(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestGoogleProvider:
    """Test Google Gemini provider."""

    @pytest.mark.asyncio
    async def test_stream_google(self):
        """Test Google streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.google import stream_google

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}',
            b'',
            b'data: {"candidates":[{"content":{"parts":[{"text":" from Gemini"}]}}]}',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="gemini-pro", provider="google", api="google")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_google(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestMistralProvider:
    """Test Mistral provider."""

    @pytest.mark.asyncio
    async def test_stream_mistral(self):
        """Test Mistral streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.mistral import stream_mistral

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'data: {"id":"test","choices":[{"delta":{"role":"assistant","content":"Hello"}}]}',
            b'',
            b'data: [DONE]',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="mistral-medium", provider="mistral", api="mistral")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_mistral(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestAzureOpenAIResponsesProvider:
    """Test Azure OpenAI responses provider."""

    @pytest.mark.asyncio
    async def test_stream_azure_openai_responses(self):
        """Test Azure OpenAI responses streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.azure_openai_responses import stream_azure_openai_responses

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'data: {"id":"test","choices":[{"delta":{"content":"Hello"}}]}',
            b'',
            b'data: [DONE]',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="gpt-4", provider="azure-openai", api="azure_openai_responses")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_azure_openai_responses(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestOpenAIResponsesProvider:
    """Test OpenAI responses provider."""

    @pytest.mark.asyncio
    async def test_stream_openai_responses(self):
        """Test OpenAI responses streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.openai_responses import stream_openai_responses

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'data: {"id":"test","choices":[{"delta":{"content":"Hello"}}]}',
            b'',
            b'data: [DONE]',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="gpt-4", provider="openai", api="openai_responses")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_openai_responses(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestAmazonBedrockProvider:
    """Test Amazon Bedrock provider."""

    @pytest.mark.asyncio
    async def test_stream_amazon_bedrock(self):
        """Test Amazon Bedrock streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.amazon_bedrock import stream_amazon_bedrock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'{"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}',
            b'{"type":"content_block_delta","delta":{"type":"text_delta","text":" from Bedrock"}}',
            b'{"type":"message_stop"}',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="claude-3-opus", provider="amazon-bedrock", api="amazon_bedrock")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_amazon_bedrock(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestGoogleGeminiCLIProvider:
    """Test Google Gemini CLI provider."""

    @pytest.mark.asyncio
    async def test_stream_google_gemini_cli(self):
        """Test Google Gemini CLI streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.google_gemini_cli import stream_google_gemini_cli

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'data: {"candidates":[{"content":{"parts":[{"text":"Hello from Gemini CLI"}]}}]}',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="gemini-pro", provider="google-gemini-cli", api="google_gemini_cli")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_google_gemini_cli(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestGoogleVertexProvider:
    """Test Google Vertex provider."""

    @pytest.mark.asyncio
    async def test_stream_google_vertex(self):
        """Test Google Vertex streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.google_vertex import stream_google_vertex

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'data: {"candidates":[{"content":{"parts":[{"text":"Hello from Vertex"}]}}]}',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="gemini-pro", provider="google-vertex", api="google_vertex")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_google_vertex(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0


class TestOpenAICodexResponsesProvider:
    """Test OpenAI Codex responses provider."""

    @pytest.mark.asyncio
    async def test_stream_openai_codex_responses(self):
        """Test OpenAI Codex responses streaming."""
        from pi_ai.types import Context, Model, UserMessage
        from pi_ai.providers.openai_codex_responses import stream_openai_codex_responses

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = AsyncMock(return_value=[
            b'data: {"id":"test","choices":[{"delta":{"content":"Hello from Codex"}}]}',
            b'',
            b'data: [DONE]',
            b'',
        ])

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            model = Model(id="codex", provider="openai-codex", api="openai_codex_responses")
            context = Context(messages=[UserMessage(role="user", content="Hello")])
            
            stream = stream_openai_codex_responses(model, context)
            
            chunks = []
            async for chunk in stream:
                chunks.append(chunk)

            assert len(chunks) > 0
