"""_Dispatcher — single-subscription event router for _EventBus."""

import asyncio
import inspect
from collections.abc import Callable

_STOP = object()  # sentinel: tells listeners to terminate


async def _run_post_middlewares(event_obj, middlewares):
    for fn in middlewares:
        result = fn(event_obj)
        if inspect.isawaitable(result):
            await result


async def _wait_then_run(futures, event_obj, middlewares):
    await asyncio.gather(*futures)
    await _run_post_middlewares(event_obj, middlewares)


_ExtractFn = Callable[[tuple], tuple]
_PredicateFn = Callable[..., bool]

class _Dispatcher:
    def __init__(self, bus) -> None:
        self._bus = bus
        self._q: asyncio.Queue = asyncio.Queue()
        self._bus.subscribe(self._q)
        self._routes: list[tuple[str, _PredicateFn | None, _ExtractFn, asyncio.Queue]] = []
        self._post_middlewares: list[tuple[str, Callable]] = []
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.ensure_future(self._run())

    def register(
        self, tag: str, predicate: _PredicateFn | None = None, extract: _ExtractFn | None = None,
    ) -> asyncio.Queue:
        if self._task is None:
            try:
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self._run())
            except RuntimeError:
                pass  # no running event loop; start() will be called later
        q: asyncio.Queue = asyncio.Queue()
        self._routes.append((tag, predicate, extract or (lambda e: (e[1],)), q))
        return q

    def unregister(self, q: asyncio.Queue) -> None:
        self._routes = [(t, p, ex, rq) for t, p, ex, rq in self._routes if rq is not q]

    def add_post_middleware(self, tag: str, fn: Callable) -> None:
        """Register a post-middleware called after all handlers for *tag* finish."""
        self._post_middlewares.append((tag, fn))

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            while True:
                event = await self._q.get()
                if event[0] == "disconnect":
                    for _t, _p, _ex, rq in self._routes:
                        rq.put_nowait(_STOP)
                    return
                mws = [fn for mtag, fn in self._post_middlewares if mtag == event[0]]
                futures = []
                for rtag, pred, extract, rq in self._routes:
                    if rtag != event[0]:
                        continue
                    args = extract(event)
                    if pred is None or pred(*args):
                        if mws:
                            fut = loop.create_future()
                            futures.append(fut)
                        else:
                            fut = None
                        rq.put_nowait((args, fut))
                if mws and futures:
                    asyncio.ensure_future(_wait_then_run(futures, event[1], mws))
        finally:
            self._bus.unsubscribe(self._q)
