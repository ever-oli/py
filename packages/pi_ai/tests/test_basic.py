"""Basic tests for pi_ai package."""

import pytest


def test_import():
    """Test that pi_ai can be imported."""
    import pi_ai

    assert pi_ai.__version__ == "0.1.0"


def test_types_import():
    """Test that core types are available."""
    # Just verify they exist and are importable


def test_faux_provider_registered():
    """Test that faux provider is auto-registered."""
    from pi_ai import get_api_provider, list_api_providers

    providers = list_api_providers()
    assert "faux" in providers

    faux = get_api_provider("faux")
    assert faux is not None


def test_openai_provider_registered():
    """Test that OpenAI provider is auto-registered."""
    from pi_ai import get_api_provider, list_api_providers

    providers = list_api_providers()
    assert "openai-completions" in providers

    openai = get_api_provider("openai-completions")
    assert openai is not None


def test_anthropic_provider_registered():
    """Test that Anthropic provider is auto-registered."""
    from pi_ai import get_api_provider, list_api_providers

    providers = list_api_providers()
    assert "anthropic-messages" in providers

    anthropic = get_api_provider("anthropic-messages")
    assert anthropic is not None


@pytest.mark.asyncio
async def test_faux_stream():
    """Test faux provider streaming."""
    from pi_ai import (
        Context,
        EndEvent,
        Model,
        ModelCapabilities,
        TextEvent,
        UserMessage,
        get_api_provider,
    )

    faux = get_api_provider("faux")
    assert faux is not None

    model = Model(
        id="faux-model",
        api="faux",
        provider="faux",
        capabilities=ModelCapabilities(),
    )

    context = Context(
        messages=[UserMessage(role="user", content="Hello")],
    )

    stream = faux.stream(model, context)

    events = []
    async for event in stream:
        events.append(event)

    # Should have text events and an end event
    assert len(events) > 0
    assert any(isinstance(e, TextEvent) for e in events)
    assert any(isinstance(e, EndEvent) for e in events)


@pytest.mark.asyncio
async def test_faux_complete():
    """Test faux provider complete function."""
    from pi_ai import (
        Context,
        Model,
        ModelCapabilities,
        UserMessage,
        get_api_provider,
    )

    faux = get_api_provider("faux")
    assert faux is not None

    model = Model(
        id="faux-model",
        api="faux",
        provider="faux",
        capabilities=ModelCapabilities(),
    )

    context = Context(
        messages=[UserMessage(role="user", content="Hello")],
    )

    stream = faux.stream(model, context)
    message = await stream.result()

    assert message.role == "assistant"
    assert len(message.content) > 0
    assert "[FAUX]" in message.content[0].text
