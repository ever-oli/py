"""Event stream abstractions for async iteration.
Python port of TypeScript event-stream.ts

Optimized version using deque for O(1) operations.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import Generic, TypeVar

from .types import AssistantMessage, AssistantMessageEvent

T = TypeVar("T")
R = TypeVar("R")


class EventStream(Generic[T, R]):
    """
    Generic event stream class for async iteration.

    Similar to the TypeScript EventStream class, this provides:
    - A queue for events
    - Async iteration support
    - Result extraction
    
    Optimized with deque for O(1) push/pop operations.
    """

    def __init__(
        self,
        is_complete: Callable[[T], bool],
        extract_result: Callable[[T], R],
    ):
        self._is_complete = is_complete
        self._extract_result = extract_result
        self._queue: deque[T] = deque()
        # Use deque for O(1) popleft() instead of list pop(0) which is O(n)
        self._waiting: deque[asyncio.Future[tuple[T | None, bool]]] = deque()
        self._done = False
        self._result: R | None = None
        self._result_event = asyncio.Event()

    def push(self, event: T) -> None:
        """Push an event to the stream."""
        if self._done:
            return

        if self._is_complete(event):
            self._done = True
            self._result = self._extract_result(event)
            self._result_event.set()

        # Deliver to waiting consumer or queue it
        if self._waiting:
            waiter = self._waiting.popleft()
            waiter.set_result((event, False))
        else:
            self._queue.append(event)

    def end(self, result: R | None = None) -> None:
        """End the stream with an optional result."""
        self._done = True
        if result is not None:
            self._result = result
            self._result_event.set()

        # Notify all waiting consumers that we're done
        for waiter in self._waiting:
            waiter.set_result((None, True))
        self._waiting.clear()

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        while True:
            if self._queue:
                return self._queue.popleft()
            elif self._done:
                raise StopAsyncIteration
            else:
                # Create a future for waiting
                waiter: asyncio.Future[tuple[T | None, bool]] = (
                    asyncio.get_event_loop().create_future()
                )
                self._waiting.append(waiter)
                value, done = await waiter
                if done:
                    raise StopAsyncIteration
                if value is not None:
                    return value

    async def result(self) -> R:
        """Get the final result of the stream."""
        await self._result_event.wait()
        if self._result is None:
            raise RuntimeError("Stream ended without a result")
        return self._result


class AssistantMessageEventStream(EventStream[AssistantMessageEvent, AssistantMessage]):
    """
    Specialized event stream for assistant messages.
    """

    def __init__(self) -> None:
        super().__init__(
            is_complete=lambda event: isinstance(event, (EndEvent, ErrorEvent)),
            extract_result=lambda event: (
                event.message
                if isinstance(event, EndEvent)
                else event.error
                if isinstance(event, ErrorEvent)
                else AssistantMessage()
            ),
        )


# Import here to avoid circular imports
from .types import EndEvent, ErrorEvent


def create_assistant_message_event_stream() -> AssistantMessageEventStream:
    """Factory function for AssistantMessageEventStream."""
    return AssistantMessageEventStream()


__all__ = [
    "EventStream",
    "AssistantMessageEventStream",
    "create_assistant_message_event_stream",
]