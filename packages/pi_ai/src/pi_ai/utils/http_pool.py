"""HTTP client connection pool management.

Provides shared, reusable HTTP clients for optimal performance.
"""

from __future__ import annotations

import asyncio
import atexit
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

# Global connection pool instance
_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()

# Default connection limits
DEFAULT_LIMITS = {
    "max_connections": 100,
    "max_keepalive_connections": 20,
    "keepalive_expiry": 30.0,
}


def _create_client() -> httpx.AsyncClient:
    """Create a new HTTP client with connection pooling."""
    import httpx

    limits = httpx.Limits(
        max_connections=DEFAULT_LIMITS["max_connections"],
        max_keepalive_connections=DEFAULT_LIMITS["max_keepalive_connections"],
        keepalive_expiry=DEFAULT_LIMITS["keepalive_expiry"],
    )

    # Configure timeouts for streaming responses
    timeout = httpx.Timeout(
        connect=10.0,
        read=300.0,  # 5 minutes for streaming
        write=10.0,
        pool=10.0,
    )

    return httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
        http2=False,  # HTTP/1.1 is more compatible with most APIs
    )


async def get_http_client() -> httpx.AsyncClient:
    """Get the shared HTTP client instance.

    Creates the client on first call with lazy initialization.

    Returns:
        Shared AsyncClient instance with connection pooling
    """
    global _client

    if _client is None:
        async with _client_lock:
            if _client is None:
                _client = _create_client()

    return _client


def get_http_client_sync() -> httpx.AsyncClient:
    """Get the shared HTTP client (synchronous version).

    For use in contexts where async is not available.
    Creates the client if it doesn't exist.

    Returns:
        Shared AsyncClient instance
    """
    global _client

    if _client is None:
        _client = _create_client()

    return _client


async def close_http_client() -> None:
    """Close the shared HTTP client.

    Should be called on application shutdown for clean resource cleanup.
    """
    global _client

    async with _client_lock:
        if _client is not None:
            await _client.aclose()
            _client = None


def reset_http_client() -> None:
    """Reset the HTTP client (for testing purposes)."""
    global _client
    _client = None


# Register cleanup on exit
def _cleanup():
    """Cleanup function registered with atexit."""
    global _client
    if _client is not None:
        try:
            # Try to close synchronously if possible
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule close in running loop
                    asyncio.create_task(close_http_client())
                else:
                    loop.run_until_complete(close_http_client())
            except RuntimeError:
                # No event loop
                pass
        except Exception:
            pass


atexit.register(_cleanup)


__all__ = [
    "get_http_client",
    "get_http_client_sync",
    "close_http_client",
    "reset_http_client",
    "DEFAULT_LIMITS",
]
