"""_StreamListener and _CallbackListener — dispatcher-backed listeners."""

import asyncio
import inspect

from pyraksamp._dispatcher import _STOP


class _StreamListener:
    """Temporary route subscriber providing an async iterable interface.

    Registers a route with the dispatcher when iteration begins, unregisters
    on completion or cancellation.
    """

    def __init__(self, dispatcher, tag: str, predicate=None) -> None:
        self._dispatcher = dispatcher
        self._tag = tag
        self._predicate = predicate

    def __aiter__(self):
        return self._run()

    async def _run(self):
        q = self._dispatcher.register(self._tag, self._predicate)
        try:
            while True:
                args = await q.get()
                if args is _STOP:
                    return
                yield args[0]
        finally:
            self._dispatcher.unregister(q)


class _CallbackListener:
    """Persistent route subscriber that invokes a callback for each matching event.

    Registers with the dispatcher immediately on construction so that events
    queued before ``start()`` are not lost. The background task begins when
    ``start()`` is called (requires a running event loop).
    """

    def __init__(self, dispatcher, tag: str, fn, predicate=None, extract=None) -> None:
        self._fn = fn
        self._dispatcher = dispatcher
        self._q = dispatcher.register(tag, predicate, extract)
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.ensure_future(self._run())

    async def _run(self) -> None:
        try:
            while True:
                args = await self._q.get()
                if args is _STOP:
                    return
                if inspect.iscoroutinefunction(self._fn):
                    await self._fn(*args)
                else:
                    self._fn(*args)
        finally:
            self._dispatcher.unregister(self._q)

    def cancel(self) -> None:
        if self._task is not None:
            self._task.cancel()
