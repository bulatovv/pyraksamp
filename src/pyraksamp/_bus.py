"""_EventBus — fan-out broadcast to subscriber queues."""

import asyncio


class _EventBus:
    """Minimal pub/sub: broadcast events to all subscribed queues."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.append(q)

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.remove(q)

    def broadcast(self, event: tuple) -> None:
        for q in self._subscribers:
            q.put_nowait(event)
