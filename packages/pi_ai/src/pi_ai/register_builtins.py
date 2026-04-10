"""
Register built-in API providers with lazy loading.
Python port of TypeScript providers/register-builtins.ts
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import (
        AssistantMessageEventStream,
        Context,
        Model,
        SimpleStreamOptions,
        StreamOptions,
    )

from .api_registry import clear_api_providers, register_api_provider
from .event_stream import AssistantMessageEventStream

# Module promises for lazy loading
_module_promises: dict[str, Any] = {}
_bedrock_module_override: Any = None


def _forward_stream(
    target: AssistantMessageEventStream,
    source: Any,  # AsyncIterable[AssistantMessageEvent]
) -> None:
    """Forward events from source stream to target stream."""

    async def process():
        try:
            async for event in source:
                target.push(event)
            target.end()
        except Exception as e:
            from .types import AssistantMessage, ErrorEvent, StopReason, Usage

            error_msg = AssistantMessage(
                role="assistant",
                content=[],
                api="",
                provider="",
                model="",
                usage=Usage(),
                stop_reason=StopReason.ERROR,
                error_message=str(e),
            )
            target.push(ErrorEvent(reason="error", error=error_msg))
            target.end(error_msg)

    asyncio.create_task(process())


def _create_lazy_load_error_message(model: Model, error: Exception) -> AssistantMessage:
    """Create an error message for lazy load failures."""
    from .types import AssistantMessage, StopReason, Usage

    return AssistantMessage(
        role="assistant",
        content=[],
        api=model.api,
        provider=model.provider,
        model=model.id,
        usage=Usage(),
        stop_reason=StopReason.ERROR,
        error_message=str(error),
    )


def _create_lazy_stream(load_module: callable) -> callable:
    """Create a lazy-loading stream function."""

    def stream(
        model: Model,
        context: Context,
        options: StreamOptions | None = None,
    ) -> AssistantMessageEventStream:
        outer = AssistantMessageEventStream()

        async def load_and_stream():
            try:
                module = await load_module()
                inner = module["stream"](model, context, options)
                _forward_stream(outer, inner)
            except Exception as error:
                message = _create_lazy_load_error_message(model, error)
                from .types import ErrorEvent

                outer.push(ErrorEvent(reason="error", error=message))
                outer.end(message)

        asyncio.create_task(load_and_stream())
        return outer

    return stream


def _create_lazy_simple_stream(load_module: callable) -> callable:
    """Create a lazy-loading simple stream function."""

    def stream_simple(
        model: Model,
        context: Context,
        options: SimpleStreamOptions | None = None,
    ) -> AssistantMessageEventStream:
        outer = AssistantMessageEventStream()

        async def load_and_stream():
            try:
                module = await load_module()
                inner = module["stream_simple"](model, context, options)
                _forward_stream(outer, inner)
            except Exception as error:
                message = _create_lazy_load_error_message(model, error)
                from .types import ErrorEvent

                outer.push(ErrorEvent(reason="error", error=message))
                outer.end(message)

        asyncio.create_task(load_and_stream())
        return outer

    return stream_simple


async def _load_anthropic_module() -> dict[str, Any]:
    """Lazy load Anthropic provider module."""
    if "anthropic" not in _module_promises:
        from .providers.anthropic_provider import stream_anthropic, stream_simple_anthropic

        _module_promises["anthropic"] = {
            "stream": stream_anthropic,
            "stream_simple": stream_simple_anthropic,
        }
    return _module_promises["anthropic"]


async def _load_openai_completions_module() -> dict[str, Any]:
    """Lazy load OpenAI completions provider module."""
    if "openai_completions" not in _module_promises:
        from .providers.openai_completions import (
            stream_openai_completions,
            stream_simple_openai_completions,
        )

        _module_promises["openai_completions"] = {
            "stream": stream_openai_completions,
            "stream_simple": stream_simple_openai_completions,
        }
    return _module_promises["openai_completions"]


async def _load_mistral_module() -> dict[str, Any]:
    """Lazy load Mistral provider module."""
    if "mistral" not in _module_promises:
        from .providers.mistral import (
            stream_mistral_conversations,
            stream_simple_mistral_conversations,
        )

        _module_promises["mistral"] = {
            "stream": stream_mistral_conversations,
            "stream_simple": stream_simple_mistral_conversations,
        }
    return _module_promises["mistral"]


async def _load_openai_responses_module() -> dict[str, Any]:
    """Lazy load OpenAI responses provider module."""
    if "openai_responses" not in _module_promises:
        from .providers.openai_responses import (
            stream_openai_responses,
            stream_simple_openai_responses,
        )

        _module_promises["openai_responses"] = {
            "stream": stream_openai_responses,
            "stream_simple": stream_simple_openai_responses,
        }
    return _module_promises["openai_responses"]


async def _load_azure_openai_responses_module() -> dict[str, Any]:
    """Lazy load Azure OpenAI responses provider module."""
    if "azure_openai_responses" not in _module_promises:
        from .providers.azure_openai_responses import (
            stream_azure_openai_responses,
            stream_simple_azure_openai_responses,
        )

        _module_promises["azure_openai_responses"] = {
            "stream": stream_azure_openai_responses,
            "stream_simple": stream_simple_azure_openai_responses,
        }
    return _module_promises["azure_openai_responses"]


async def _load_openai_codex_responses_module() -> dict[str, Any]:
    """Lazy load OpenAI Codex responses provider module."""
    if "openai_codex_responses" not in _module_promises:
        from .providers.openai_codex_responses import (
            stream_openai_codex_responses,
            stream_simple_openai_codex_responses,
        )

        _module_promises["openai_codex_responses"] = {
            "stream": stream_openai_codex_responses,
            "stream_simple": stream_simple_openai_codex_responses,
        }
    return _module_promises["openai_codex_responses"]


async def _load_faux_module() -> dict[str, Any]:
    """Lazy load Faux/mock provider module."""
    if "faux" not in _module_promises:
        from .providers.faux import stream_faux, stream_simple_faux

        _module_promises["faux"] = {
            "stream": stream_faux,
            "stream_simple": stream_simple_faux,
        }
    return _module_promises["faux"]


async def _load_google_module() -> dict[str, Any]:
    """Lazy load Google Generative AI provider module."""
    if "google" not in _module_promises:
        from .providers.google import stream_google, stream_simple_google

        _module_promises["google"] = {
            "stream": stream_google,
            "stream_simple": stream_simple_google,
        }
    return _module_promises["google"]


async def _load_google_gemini_cli_module() -> dict[str, Any]:
    """Lazy load Google Gemini CLI provider module."""
    if "google_gemini_cli" not in _module_promises:
        from .providers.google_gemini_cli import (
            stream_google_gemini_cli,
            stream_simple_google_gemini_cli,
        )

        _module_promises["google_gemini_cli"] = {
            "stream": stream_google_gemini_cli,
            "stream_simple": stream_simple_google_gemini_cli,
        }
    return _module_promises["google_gemini_cli"]


async def _load_google_vertex_module() -> dict[str, Any]:
    """Lazy load Google Vertex AI provider module."""
    if "google_vertex" not in _module_promises:
        from .providers.google_vertex import (
            stream_google_vertex,
            stream_simple_google_vertex,
        )

        _module_promises["google_vertex"] = {
            "stream": stream_google_vertex,
            "stream_simple": stream_simple_google_vertex,
        }
    return _module_promises["google_vertex"]


async def _load_bedrock_module() -> dict[str, Any]:
    """Lazy load Amazon Bedrock provider module."""
    if _bedrock_module_override:
        return _bedrock_module_override

    if "bedrock" not in _module_promises:
        from .providers.amazon_bedrock import (
            stream_bedrock_converse,
            stream_simple_bedrock_converse,
        )

        _module_promises["bedrock"] = {
            "stream": stream_bedrock_converse,
            "stream_simple": stream_simple_bedrock_converse,
        }
    return _module_promises["bedrock"]


def set_bedrock_provider_module(module: Any) -> None:
    """Override the Bedrock provider module (for testing)."""
    global _bedrock_module_override
    _bedrock_module_override = {
        "stream": module.stream_bedrock_converse,
        "stream_simple": module.stream_simple_bedrock_converse,
    }


# Create lazy stream functions
stream_anthropic = _create_lazy_stream(_load_anthropic_module)
stream_simple_anthropic = _create_lazy_simple_stream(_load_anthropic_module)

stream_openai_completions = _create_lazy_stream(_load_openai_completions_module)
stream_simple_openai_completions = _create_lazy_simple_stream(_load_openai_completions_module)

stream_mistral = _create_lazy_stream(_load_mistral_module)
stream_simple_mistral = _create_lazy_simple_stream(_load_mistral_module)

stream_openai_responses = _create_lazy_stream(_load_openai_responses_module)
stream_simple_openai_responses = _create_lazy_simple_stream(_load_openai_responses_module)

stream_azure_openai_responses = _create_lazy_stream(_load_azure_openai_responses_module)
stream_simple_azure_openai_responses = _create_lazy_simple_stream(
    _load_azure_openai_responses_module
)

stream_openai_codex_responses = _create_lazy_stream(_load_openai_codex_responses_module)
stream_simple_openai_codex_responses = _create_lazy_simple_stream(
    _load_openai_codex_responses_module
)

stream_faux = _create_lazy_stream(_load_faux_module)
stream_simple_faux = _create_lazy_simple_stream(_load_faux_module)

stream_google = _create_lazy_stream(_load_google_module)
stream_simple_google = _create_lazy_simple_stream(_load_google_module)

stream_google_gemini_cli = _create_lazy_stream(_load_google_gemini_cli_module)
stream_simple_google_gemini_cli = _create_lazy_simple_stream(_load_google_gemini_cli_module)

stream_google_vertex = _create_lazy_stream(_load_google_vertex_module)
stream_simple_google_vertex = _create_lazy_simple_stream(_load_google_vertex_module)

stream_bedrock_lazy = _create_lazy_stream(_load_bedrock_module)
stream_simple_bedrock_lazy = _create_lazy_simple_stream(_load_bedrock_module)


def register_built_in_api_providers() -> None:
    """Register all built-in API providers."""
    # Anthropic Messages API
    register_api_provider(
        api="anthropic-messages",
        stream=stream_anthropic,
        stream_simple=stream_simple_anthropic,
    )

    # OpenAI Completions API (supports OpenRouter)
    register_api_provider(
        api="openai-completions",
        stream=stream_openai_completions,
        stream_simple=stream_simple_openai_completions,
    )

    # Faux/Mock provider for testing
    register_api_provider(
        api="faux",
        stream=stream_faux,
        stream_simple=stream_simple_faux,
    )

    # Mistral Conversations API
    register_api_provider(
        api="mistral-conversations",
        stream=stream_mistral,
        stream_simple=stream_simple_mistral,
    )

    # OpenAI Responses API
    register_api_provider(
        api="openai-responses",
        stream=stream_openai_responses,
        stream_simple=stream_simple_openai_responses,
    )

    # Azure OpenAI Responses API
    register_api_provider(
        api="azure-openai-responses",
        stream=stream_azure_openai_responses,
        stream_simple=stream_simple_azure_openai_responses,
    )

    # OpenAI Codex Responses API
    register_api_provider(
        api="openai-codex-responses",
        stream=stream_openai_codex_responses,
        stream_simple=stream_simple_openai_codex_responses,
    )

    # Google Generative AI API
    register_api_provider(
        api="google-generative-ai",
        stream=stream_google,
        stream_simple=stream_simple_google,
    )

    # Google Gemini CLI API
    register_api_provider(
        api="google-gemini-cli",
        stream=stream_google_gemini_cli,
        stream_simple=stream_simple_google_gemini_cli,
    )

    # Google Vertex AI API
    register_api_provider(
        api="google-vertex",
        stream=stream_google_vertex,
        stream_simple=stream_simple_google_vertex,
    )

    # Amazon Bedrock Converse Stream API
    register_api_provider(
        api="bedrock-converse-stream",
        stream=stream_bedrock_lazy,
        stream_simple=stream_simple_bedrock_lazy,
    )


def reset_api_providers() -> None:
    """Clear and re-register all API providers."""
    clear_api_providers()
    register_built_in_api_providers()


__all__ = [
    "register_built_in_api_providers",
    "reset_api_providers",
    "set_bedrock_provider_module",
    # Exposed stream functions
    "stream_anthropic",
    "stream_simple_anthropic",
    "stream_openai_completions",
    "stream_simple_openai_completions",
    "stream_faux",
    "stream_simple_faux",
    "stream_mistral",
    "stream_simple_mistral",
    "stream_openai_responses",
    "stream_simple_openai_responses",
    "stream_azure_openai_responses",
    "stream_simple_azure_openai_responses",
    "stream_openai_codex_responses",
    "stream_simple_openai_codex_responses",
    "stream_google",
    "stream_simple_google",
    "stream_google_gemini_cli",
    "stream_simple_google_gemini_cli",
    "stream_google_vertex",
    "stream_simple_google_vertex",
]
