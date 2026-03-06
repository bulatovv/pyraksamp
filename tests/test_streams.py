"""Isolated unit tests for _EventStreams."""

import asyncio

from pyraksamp._bus import _EventBus
from pyraksamp._streams import _EventStreams
from pyraksamp.dialogs import _make_dialog, InputDialog, MsgboxDialog
from pyraksamp.events import ChatMessage, PlayerJoin, ServerMessage
from unittest.mock import MagicMock


def make_bus_streams():
    bus = _EventBus()
    streams = _EventStreams(bus)
    return bus, streams


# ── rpcs() ────────────────────────────────────────────────────────────────────


def test_rpcs_yields_rpc_events():
    async def _inner():
        bus, streams = make_bus_streams()
        results = []

        async def consume():
            async for rid, data in streams.rpcs():
                results.append((rid, data))

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("rpc", 5, b"hi"))
        bus.broadcast(("disconnect",))
        await task
        assert results == [(5, b"hi")]

    asyncio.run(_inner())


def test_rpcs_filtered_by_id():
    async def _inner():
        bus, streams = make_bus_streams()
        results = []

        async def consume():
            async for rid, data in streams.rpcs(rpc_id=10):
                results.append(rid)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("rpc", 5, b""))
        bus.broadcast(("rpc", 10, b"yes"))
        bus.broadcast(("disconnect",))
        await task
        assert results == [10]

    asyncio.run(_inner())


def test_rpcs_skips_non_rpc_events():
    async def _inner():
        bus, streams = make_bus_streams()
        results = []

        async def consume():
            async for rid, data in streams.rpcs():
                results.append(rid)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("chat", ChatMessage(player_id=1, text="hi")))
        bus.broadcast(("rpc", 7, b"data"))
        bus.broadcast(("disconnect",))
        await task
        assert results == [7]

    asyncio.run(_inner())


def test_rpcs_stops_on_disconnect():
    async def _inner():
        bus, streams = make_bus_streams()
        count = 0

        async def consume():
            nonlocal count
            async for _ in streams.rpcs():
                count += 1

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("disconnect",))
        await task
        assert count == 0

    asyncio.run(_inner())


# ── events() ──────────────────────────────────────────────────────────────────


def test_events_yields_all_event_tuples():
    async def _inner():
        bus, streams = make_bus_streams()
        results = []

        async def consume():
            async for evt in streams.events():
                results.append(evt[0])

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("connect",))
        bus.broadcast(("rpc", 1, b""))
        bus.broadcast(("disconnect",))
        await task
        assert results == ["connect", "rpc", "disconnect"]

    asyncio.run(_inner())


def test_events_stops_after_disconnect():
    async def _inner():
        bus, streams = make_bus_streams()
        results = []

        async def consume():
            async for evt in streams.events():
                results.append(evt[0])

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("disconnect",))
        bus.broadcast(("connect",))  # should NOT be received
        await task
        assert results == ["disconnect"]
        assert "connect" not in results

    asyncio.run(_inner())


# ── _typed_gen / chat() ───────────────────────────────────────────────────────


def test_chat_yields_chat_messages():
    async def _inner():
        bus, streams = make_bus_streams()
        results = []

        async def consume():
            async for msg in streams.chat():
                results.append(msg)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        msg = ChatMessage(player_id=3, text="hello")
        bus.broadcast(("chat", msg))
        bus.broadcast(("disconnect",))
        await task
        assert results == [msg]


    asyncio.run(_inner())


def test_typed_gen_skips_other_tags():
    async def _inner():
        bus, streams = make_bus_streams()
        results = []

        async def consume():
            async for msg in streams.chat():
                results.append(msg)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("rpc", 1, b""))
        bus.broadcast(("chat", ChatMessage(player_id=1, text="hi")))
        bus.broadcast(("disconnect",))
        await task
        assert len(results) == 1

    asyncio.run(_inner())


def test_typed_gen_stops_on_disconnect():
    async def _inner():
        bus, streams = make_bus_streams()
        count = 0

        async def consume():
            nonlocal count
            async for _ in streams.chat():
                count += 1

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("disconnect",))
        await task
        assert count == 0

    asyncio.run(_inner())


# ── fan-out ───────────────────────────────────────────────────────────────────


def test_fan_out_two_consumers_both_receive():
    async def _inner():
        bus, streams = make_bus_streams()
        results_a, results_b = [], []

        async def consume_a():
            async for rid, _ in streams.rpcs():
                results_a.append(rid)

        async def consume_b():
            async for rid, _ in streams.rpcs():
                results_b.append(rid)

        task_a = asyncio.create_task(consume_a())
        task_b = asyncio.create_task(consume_b())
        await asyncio.sleep(0)
        bus.broadcast(("rpc", 42, b""))
        bus.broadcast(("disconnect",))
        await task_a
        await task_b
        assert results_a == [42]
        assert results_b == [42]

    asyncio.run(_inner())


# ── unsubscribe on generator close ────────────────────────────────────────────


def test_unsubscribe_on_generator_close():
    async def _inner():
        bus, streams = make_bus_streams()

        async def consume():
            async for _ in streams.rpcs():
                pass  # will be cancelled while suspended here

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        # generator is subscribed while waiting for next event
        assert len(bus._subscribers) == 1
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0)
        # finally block in rpcs() should have unsubscribed
        assert len(bus._subscribers) == 0

    asyncio.run(_inner())


# ── wait_for_rpc ──────────────────────────────────────────────────────────────


def test_wait_for_rpc_returns_data():
    async def _inner():
        bus, streams = make_bus_streams()

        async def producer():
            await asyncio.sleep(0)
            bus.broadcast(("rpc", 20, b"\xde\xad"))

        asyncio.create_task(producer())
        data = await streams.wait_for_rpc(20)
        assert data == b"\xde\xad"

    asyncio.run(_inner())


def test_wait_for_rpc_predicate_skips_non_matching():
    async def _inner():
        bus, streams = make_bus_streams()

        async def producer():
            await asyncio.sleep(0)
            bus.broadcast(("rpc", 20, b"\x00"))      # predicate fails
            bus.broadcast(("rpc", 20, b"\xff\xff"))   # predicate passes

        asyncio.create_task(producer())
        data = await streams.wait_for_rpc(20, predicate=lambda rid, d: len(d) == 2)
        assert data == b"\xff\xff"

    asyncio.run(_inner())


# ── wait_for_dialog ───────────────────────────────────────────────────────────


def test_wait_for_dialog_type_filter():
    async def _inner():
        bus, streams = make_bus_streams()
        bot = MagicMock()
        input_dlg = _make_dialog(1, 1, "Login", "OK", "", "", bot)
        msgbox_dlg = _make_dialog(2, 0, "Info", "OK", "", "body", bot)

        async def producer():
            await asyncio.sleep(0)
            bus.broadcast(("dialog", msgbox_dlg))   # skipped
            bus.broadcast(("dialog", input_dlg))    # matched

        asyncio.create_task(producer())
        result = await streams.wait_for_dialog(dialog_type=InputDialog)
        assert isinstance(result, InputDialog)

    asyncio.run(_inner())


# ── wait_for_chat ─────────────────────────────────────────────────────────────


def test_wait_for_chat_player_id_filter():
    async def _inner():
        bus, streams = make_bus_streams()

        async def producer():
            await asyncio.sleep(0)
            bus.broadcast(("chat", ChatMessage(player_id=9, text="no")))
            bus.broadcast(("chat", ChatMessage(player_id=3, text="yes")))

        asyncio.create_task(producer())
        msg = await streams.wait_for_chat(player_id=3)
        assert msg.player_id == 3 and msg.text == "yes"

    asyncio.run(_inner())


# ── wait_for_client_message ───────────────────────────────────────────────────


def test_wait_for_client_message_color_filter():
    async def _inner():
        bus, streams = make_bus_streams()

        async def producer():
            await asyncio.sleep(0)
            bus.broadcast(("client_message", ServerMessage(color=0x00FF00FF, text="green")))
            bus.broadcast(("client_message", ServerMessage(color=0xFF0000FF, text="red")))

        asyncio.create_task(producer())
        msg = await streams.wait_for_client_message(color=0xFF0000FF)
        assert msg.color == 0xFF0000FF

    asyncio.run(_inner())


# ── wait_for_player_join ──────────────────────────────────────────────────────


def test_wait_for_player_join_name_filter():
    async def _inner():
        bus, streams = make_bus_streams()

        async def producer():
            await asyncio.sleep(0)
            bus.broadcast(("player_join", PlayerJoin(player_id=1, name="Bob")))
            bus.broadcast(("player_join", PlayerJoin(player_id=2, name="Alice")))

        asyncio.create_task(producer())
        evt = await streams.wait_for_player_join(name="Alice")
        assert evt.name == "Alice"

    asyncio.run(_inner())
