"""
pi_ai - Python port of pi-mono TypeScript AI package

A clean room rewrite of the LLM provider abstraction layer.
Supports: OpenAI, Anthropic, OpenRouter, Mistral, Google, Amazon Bedrock, and more.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Core types
# API registry
from .api_registry import (
    ApiProvider,
    clear_api_providers,
    get_api_provider,
    list_api_providers,
    register_api_provider,
)

# Event stream
from .event_stream import (
    AssistantMessageEventStream,
    create_assistant_message_event_stream,
)

# Models
from .models import (
    calculate_cost,
    get_model,
    get_models,
    get_providers,
    models_are_equal,
    register_model,
    supports_xhigh,
)

# Import and register built-in providers
from .register_builtins import register_built_in_api_providers, reset_api_providers
from .types import (
    Api,
    AssistantMessage,
    CacheRetention,
    Context,
    Cost,
    DoneEvent,
    EndEvent,
    ErrorEvent,
    EventType,
    ImageContent,
    KnownApi,
    KnownProvider,
    Message,
    Model,
    ModelCapabilities,
    ModelPricing,
    Provider,
    SimpleStreamOptions,
    StartEvent,
    StopReason,
    StreamOptions,
    TextContent,
    TextDeltaEvent,
    TextEndEvent,
    TextEvent,
    TextStartEvent,
    ThinkingBudgets,
    ThinkingContent,
    ThinkingDeltaEvent,
    ThinkingEndEvent,
    ThinkingEvent,
    ThinkingLevel,
    ThinkingStartEvent,
    Tool,
    ToolCall,
    ToolCallDeltaEvent,
    ToolCallEndEvent,
    ToolCallEvent,
    ToolCallStartEvent,
    ToolResultMessage,
    Transport,
    Usage,
    UsageEvent,
    UserMessage,
)

# Utilities
from .utils.env_api_keys import get_env_api_key
from .utils.json_parse import parse_streaming_json
from .utils.validation import validate_tool_arguments, validate_tool_call

# Register providers on module load
register_built_in_api_providers()

# Register models on module load
from .models_generated import register_all_models
register_all_models()


def stream(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AssistantMessageEventStream:
    """
    Stream a completion from the model.

    Args:
        model: The model to use
        context: The conversation context
        options: Optional streaming options

    Returns:
        An event stream that yields completion events
    """
    from .api_registry import get_api_provider

    provider = get_api_provider(model.api)
    if not provider:
        raise ValueError(f"No API provider registered for api: {model.api}")
    return provider.stream(model, context, options)


async def complete(
    model: Model,
    context: Context,
    options: StreamOptions | None = None,
) -> AssistantMessage:
    """
    Complete a request and return the full message.

    Args:
        model: The model to use
        context: The conversation context
        options: Optional streaming options

    Returns:
        The complete assistant message
    """
    s = stream(model, context, options)
    return await s.result()


def stream_simple(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessageEventStream:
    """
    Stream a completion with simplified options.

    Args:
        model: The model to use
        context: The conversation context
        options: Optional simple streaming options

    Returns:
        An event stream that yields completion events
    """
    from .api_registry import get_api_provider

    provider = get_api_provider(model.api)
    if not provider:
        raise ValueError(f"No API provider registered for api: {model.api}")
    return provider.stream_simple(model, context, options)


async def complete_simple(
    model: Model,
    context: Context,
    options: SimpleStreamOptions | None = None,
) -> AssistantMessage:
    """
    Complete a request with simplified options and return the full message.

    Args:
        model: The model to use
        context: The conversation context
        options: Optional simple streaming options

    Returns:
        The complete assistant message
    """
    s = stream_simple(model, context, options)
    return await s.result()


__all__ = [
    # Version
    "__version__",
    # Core streaming functions
    "stream",
    "complete",
    "stream_simple",
    "complete_simple",
    # Types
    "Api",
    "AssistantMessage",
    "CacheRetention",
    "Context",
    "Cost",
    "DoneEvent",
    "EndEvent",
    "ErrorEvent",
    "EventType",
    "ImageContent",
    "KnownApi",
    "KnownProvider",
    "Message",
    "Model",
    "ModelCapabilities",
    "ModelPricing",
    "Provider",
    "SimpleStreamOptions",
    "StartEvent",
    "StopReason",
    "StreamOptions",
    "TextContent",
    "TextDeltaEvent",
    "TextEndEvent",
    "TextEvent",
    "TextStartEvent",
    "ThinkingBudgets",
    "ThinkingContent",
    "ThinkingDeltaEvent",
    "ThinkingEndEvent",
    "ThinkingEvent",
    "ThinkingLevel",
    "ThinkingStartEvent",
    "Tool",
    "ToolCall",
    "ToolCallDeltaEvent",
    "ToolCallEndEvent",
    "ToolCallEvent",
    "ToolCallStartEvent",
    "ToolResultMessage",
    "Transport",
    "Usage",
    "UsageEvent",
    "UserMessage",
    # Event stream
    "AssistantMessageEventStream",
    "create_assistant_message_event_stream",
    # API registry
    "ApiProvider",
    "clear_api_providers",
    "get_api_provider",
    "list_api_providers",
    "register_api_provider",
    # Models
    "calculate_cost",
    "get_model",
    "get_models",
    "get_providers",
    "models_are_equal",
    "register_model",
    "supports_xhigh",
    # Utilities
    "get_env_api_key",
    "parse_streaming_json",
    "validate_tool_call",
    "validate_tool_arguments",
    # Registration
    "register_built_in_api_providers",
    "reset_api_providers",
]
