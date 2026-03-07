"""Unit tests for _EventBus, _StreamListener, and _CallbackListener."""

import asyncio

from pyraksamp._bus import _EventBus
from pyraksamp._dispatcher import _Dispatcher
from pyraksamp._listener import _CallbackListener, _StreamListener
from pyraksamp.events import ChatMessage, PlayerJoin


def _make_dispatcher(bus):
    d = _Dispatcher(bus)
    d.start()
    return d


# ── _EventBus ─────────────────────────────────────────────────────────────────


def test_subscribe_adds_queue():
    bus = _EventBus()
    q = asyncio.Queue()
    bus.subscribe(q)
    assert q in bus._subscribers


def test_unsubscribe_removes_queue():
    bus = _EventBus()
    q = asyncio.Queue()
    bus.subscribe(q)
    bus.unsubscribe(q)
    assert q not in bus._subscribers


def test_broadcast_delivers_to_all_queues():
    bus = _EventBus()
    q1, q2 = asyncio.Queue(), asyncio.Queue()
    bus.subscribe(q1)
    bus.subscribe(q2)
    bus.broadcast(("connect",))
    assert q1.get_nowait() == ("connect",)
    assert q2.get_nowait() == ("connect",)


def test_broadcast_no_subscribers_is_noop():
    bus = _EventBus()
    bus.broadcast(("connect",))  # must not raise


# ── _StreamListener ───────────────────────────────────────────────────────────


def test_stream_listener_yields_matching_tag():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        results = []

        async def consume():
            async for msg in _StreamListener(d, "chat"):
                results.append(msg)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        msg = ChatMessage(player_id=1, text="hi")
        bus.broadcast(("chat", msg))
        bus.broadcast(("disconnect",))
        await task
        assert results == [msg]

    asyncio.run(_inner())


def test_stream_listener_skips_other_tags():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        results = []

        async def consume():
            async for msg in _StreamListener(d, "chat"):
                results.append(msg)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("rpc", 1, b""))
        bus.broadcast(("chat", ChatMessage(player_id=1, text="yes")))
        bus.broadcast(("disconnect",))
        await task
        assert len(results) == 1

    asyncio.run(_inner())


def test_stream_listener_predicate_filter():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        results = []

        async def consume():
            async for msg in _StreamListener(d, "chat", lambda m: m.player_id == 3):
                results.append(msg)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("chat", ChatMessage(player_id=1, text="no")))
        bus.broadcast(("chat", ChatMessage(player_id=3, text="yes")))
        bus.broadcast(("disconnect",))
        await task
        assert len(results) == 1 and results[0].player_id == 3

    asyncio.run(_inner())


def test_stream_listener_stops_on_disconnect():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        count = 0

        async def consume():
            nonlocal count
            async for _ in _StreamListener(d, "chat"):
                count += 1

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("disconnect",))
        await task
        assert count == 0

    asyncio.run(_inner())


def test_stream_listener_unsubscribes_on_close():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)

        async def consume():
            async for _ in _StreamListener(d, "chat"):
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        assert len(d._routes) == 1
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0)
        assert len(d._routes) == 0

    asyncio.run(_inner())


def test_stream_listener_fan_out():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        a, b = [], []

        async def consume(out):
            async for msg in _StreamListener(d, "chat"):
                out.append(msg)

        ta = asyncio.create_task(consume(a))
        tb = asyncio.create_task(consume(b))
        await asyncio.sleep(0)
        msg = ChatMessage(player_id=1, text="x")
        bus.broadcast(("chat", msg))
        bus.broadcast(("disconnect",))
        await ta
        await tb
        assert a == [msg] and b == [msg]

    asyncio.run(_inner())


# ── _CallbackListener ─────────────────────────────────────────────────────────


def test_callback_listener_subscribes_on_construction():
    bus = _EventBus()
    d = _Dispatcher(bus)

    def fn(evt):
        pass

    _CallbackListener(d, "chat", fn)
    assert len(d._routes) == 1


def test_callback_listener_invokes_sync_fn():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        received = []
        listener = _CallbackListener(d, "chat", lambda msg: received.append(msg))
        listener.start()
        await asyncio.sleep(0)
        msg = ChatMessage(player_id=1, text="hello")
        bus.broadcast(("chat", msg))
        await asyncio.sleep(0)  # dispatcher routes to listener queue
        await asyncio.sleep(0)  # listener processes
        assert received == [msg]

    asyncio.run(_inner())


def test_callback_listener_invokes_async_fn():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        received = []

        async def cb(msg):
            received.append(msg)

        listener = _CallbackListener(d, "chat", cb)
        listener.start()
        await asyncio.sleep(0)
        msg = ChatMessage(player_id=2, text="async")
        bus.broadcast(("chat", msg))
        await asyncio.sleep(0)  # dispatcher routes
        await asyncio.sleep(0)  # listener processes
        assert received == [msg]

    asyncio.run(_inner())


def test_callback_listener_predicate_filter():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        received = []
        listener = _CallbackListener(
            d,
            "player_join",
            lambda evt: received.append(evt),
            predicate=lambda evt: evt.player_id == 5,
        )
        listener.start()
        await asyncio.sleep(0)
        bus.broadcast(("player_join", PlayerJoin(player_id=1, name="Bob")))
        bus.broadcast(("player_join", PlayerJoin(player_id=5, name="Alice")))
        await asyncio.sleep(0)  # dispatcher routes
        await asyncio.sleep(0)  # listener processes
        assert len(received) == 1 and received[0].player_id == 5

    asyncio.run(_inner())


def test_callback_listener_no_arg_extract():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        called = []
        listener = _CallbackListener(
            d, "connect", lambda: called.append(True), extract=lambda e: ()
        )
        listener.start()
        await asyncio.sleep(0)
        bus.broadcast(("connect",))
        await asyncio.sleep(0)  # dispatcher routes
        await asyncio.sleep(0)  # listener processes
        assert called == [True]

    asyncio.run(_inner())


def test_callback_listener_two_arg_extract():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        received = []
        listener = _CallbackListener(
            d,
            "rpc",
            lambda rid, data: received.append((rid, data)),
            extract=lambda e: (e[1], e[2]),
        )
        listener.start()
        await asyncio.sleep(0)
        bus.broadcast(("rpc", 42, b"\xff"))
        await asyncio.sleep(0)  # dispatcher routes
        await asyncio.sleep(0)  # listener processes
        assert received == [(42, b"\xff")]

    asyncio.run(_inner())


def test_callback_listener_stops_on_disconnect():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        received = []
        listener = _CallbackListener(d, "chat", lambda m: received.append(m))
        listener.start()
        await asyncio.sleep(0)
        bus.broadcast(("disconnect",))
        await asyncio.sleep(0)
        bus.broadcast(("chat", ChatMessage(player_id=1, text="late")))
        await asyncio.sleep(0)
        assert received == []

    asyncio.run(_inner())


def test_callback_listener_queues_events_before_start():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        received = []
        listener = _CallbackListener(d, "chat", lambda m: received.append(m))
        msg = ChatMessage(player_id=1, text="early")
        bus.broadcast(("chat", msg))
        listener.start()
        await asyncio.sleep(0)
        assert received == [msg]

    asyncio.run(_inner())


def test_callback_listener_skips_other_tags():
    async def _inner():
        bus = _EventBus()
        d = _make_dispatcher(bus)
        received = []
        listener = _CallbackListener(d, "chat", lambda m: received.append(m))
        listener.start()
        await asyncio.sleep(0)
        bus.broadcast(("rpc", 1, b""))
        bus.broadcast(("chat", ChatMessage(player_id=1, text="yes")))
        await asyncio.sleep(0)  # dispatcher routes
        await asyncio.sleep(0)  # listener processes
        assert len(received) == 1

    asyncio.run(_inner())
