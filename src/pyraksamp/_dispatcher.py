"""_Dispatcher — single-subscription event router for _EventBus."""

import asyncio

_STOP = object()  # sentinel: tells listeners to terminate


class _Dispatcher:
    def __init__(self, bus) -> None:
        self._bus = bus
        self._q: asyncio.Queue = asyncio.Queue()
        self._bus.subscribe(self._q)
        self._routes: list[tuple[str, object, object, asyncio.Queue]] = []
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.ensure_future(self._run())

    def register(self, tag: str, predicate=None, extract=None) -> asyncio.Queue:
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

    async def _run(self) -> None:
        try:
            while True:
                event = await self._q.get()
                if event[0] == "disconnect":
                    for _t, _p, _ex, rq in self._routes:
                        rq.put_nowait(_STOP)
                    return
                for rtag, pred, extract, rq in self._routes:
                    if rtag != event[0]:
                        continue
                    args = extract(event)
                    if pred is None or pred(*args):
                        rq.put_nowait(args)
        finally:
            self._bus.unsubscribe(self._q)
