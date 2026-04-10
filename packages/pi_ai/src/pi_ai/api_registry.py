"""API Provider Registry

Python port of TypeScript api-registry.ts
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .types import (
        AssistantMessageEventStream,
    )


# Type aliases for stream functions (use string annotations for forward refs)
ApiStreamFunction = Callable[..., "AssistantMessageEventStream"]
ApiStreamSimpleFunction = Callable[..., "AssistantMessageEventStream"]


@dataclass
class ApiProvider:
    """Registered API provider with stream functions."""

    api: str
    stream: ApiStreamFunction
    stream_simple: ApiStreamSimpleFunction


# Global registry: api -> ApiProvider
_api_providers: dict[str, ApiProvider] = {}


def register_api_provider(
    api: str,
    stream: ApiStreamFunction,
    stream_simple: ApiStreamSimpleFunction,
) -> None:
    """Register an API provider.

    Args:
        api: The API identifier (e.g., "openai-completions")
        stream: The stream function
        stream_simple: The simple stream function
    """
    _api_providers[api] = ApiProvider(
        api=api,
        stream=stream,
        stream_simple=stream_simple,
    )


def get_api_provider(api: str) -> ApiProvider | None:
    """Get an API provider by API identifier."""
    return _api_providers.get(api)


def list_api_providers() -> list[str]:
    """List all registered API identifiers."""
    return list(_api_providers.keys())


def clear_api_providers() -> None:
    """Clear all registered providers."""
    _api_providers.clear()


__all__ = [
    "ApiProvider",
    "register_api_provider",
    "get_api_provider",
    "list_api_providers",
    "clear_api_providers",
]
