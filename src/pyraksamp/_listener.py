"""_StreamListener and _CallbackListener — fan-out queue subscribers."""

import asyncio
import inspect


class _StreamListener:
    """Temporary fan-out subscriber providing an async iterable interface.

    Subscribes to the bus when iteration begins, unsubscribes on completion
    or cancellation.
    """

    def __init__(self, bus, tag: str, predicate=None) -> None:
        self._bus = bus
        self._tag = tag
        self._predicate = predicate

    def __aiter__(self):
        return self._run()

    async def _run(self):
        q: asyncio.Queue = asyncio.Queue()
        self._bus.subscribe(q)
        try:
            while True:
                event = await q.get()
                if event[0] == "disconnect":
                    return
                if event[0] == self._tag:
                    obj = event[1]
                    if self._predicate is None or self._predicate(obj):
                        yield obj
        finally:
            self._bus.unsubscribe(q)


class _CallbackListener:
    """Persistent fan-out subscriber that invokes a callback for each matching event.

    Subscribes immediately on construction so that events queued before
    ``start()`` are not lost.  The background task begins when ``start()``
    is called (requires a running event loop).
    """

    def __init__(self, bus, tag: str, fn, predicate=None, extract=None) -> None:
        self._bus = bus
        self._tag = tag
        self._fn = fn
        self._predicate = predicate
        # extract(event_tuple) -> args tuple forwarded to predicate and fn
        self._extract = extract or (lambda e: (e[1],))
        self._q: asyncio.Queue = asyncio.Queue()
        bus.subscribe(self._q)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.ensure_future(self._run())

    async def _run(self) -> None:
        try:
            while True:
                event = await self._q.get()
                if event[0] == "disconnect":
                    return
                if event[0] != self._tag:
                    continue
                args = self._extract(event)
                if self._predicate is not None and not self._predicate(*args):
                    continue
                if inspect.iscoroutinefunction(self._fn):
                    await self._fn(*args)
                else:
                    self._fn(*args)
        finally:
            self._bus.unsubscribe(self._q)

    def cancel(self) -> None:
        if self._task is not None:
            self._task.cancel()
