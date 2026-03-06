"""Tests for SAMPBot stream generators and wait_for_* helpers."""

import asyncio
from unittest.mock import patch

from pyraksamp import SAMPBot
from pyraksamp._bus import _EventBus
from pyraksamp._listener import _StreamListener
from pyraksamp.dialogs import _make_dialog, InputDialog
from pyraksamp.events import ChatMessage, PlayerJoin, ServerMessage
from unittest.mock import MagicMock


def make_bus():
    return _EventBus()


# ── rpcs() ────────────────────────────────────────────────────────────────────


def test_rpcs_yields_rpc_events():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")
        results = []

        async def consume():
            async for rid, data in bot.rpcs():
                results.append((rid, data))

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bot._bus.broadcast(("rpc", 5, b"hi"))
        bot._bus.broadcast(("disconnect",))
        await task
        assert results == [(5, b"hi")]

    asyncio.run(_inner())


def test_rpcs_filtered_by_id():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")
        results = []

        async def consume():
            async for rid, _ in bot.rpcs(rpc_id=10):
                results.append(rid)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bot._bus.broadcast(("rpc", 5, b""))
        bot._bus.broadcast(("rpc", 10, b"yes"))
        bot._bus.broadcast(("disconnect",))
        await task
        assert results == [10]

    asyncio.run(_inner())


def test_rpcs_stops_on_disconnect():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")
        count = 0

        async def consume():
            nonlocal count
            async for _ in bot.rpcs():
                count += 1

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bot._bus.broadcast(("disconnect",))
        await task
        assert count == 0

    asyncio.run(_inner())


# ── events() ──────────────────────────────────────────────────────────────────


def test_events_yields_all_event_tuples():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")
        results = []

        async def consume():
            async for evt in bot.events():
                results.append(evt[0])

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bot._bus.broadcast(("connect",))
        bot._bus.broadcast(("rpc", 1, b""))
        bot._bus.broadcast(("disconnect",))
        await task
        assert results == ["connect", "rpc", "disconnect"]

    asyncio.run(_inner())


def test_events_stops_after_disconnect():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")
        results = []

        async def consume():
            async for evt in bot.events():
                results.append(evt[0])

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bot._bus.broadcast(("disconnect",))
        bot._bus.broadcast(("connect",))  # must NOT be received
        await task
        assert results == ["disconnect"]

    asyncio.run(_inner())


# ── chat() / _StreamListener ──────────────────────────────────────────────────


def test_chat_yields_chat_messages():
    async def _inner():
        bus = make_bus()
        results = []

        async def consume():
            async for msg in _StreamListener(bus, "chat"):
                results.append(msg)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        msg = ChatMessage(player_id=3, text="hello")
        bus.broadcast(("chat", msg))
        bus.broadcast(("disconnect",))
        await task
        assert results == [msg]

    asyncio.run(_inner())


def test_typed_stream_skips_other_tags():
    async def _inner():
        bus = make_bus()
        results = []

        async def consume():
            async for msg in _StreamListener(bus, "chat"):
                results.append(msg)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        bus.broadcast(("rpc", 1, b""))
        bus.broadcast(("chat", ChatMessage(player_id=1, text="hi")))
        bus.broadcast(("disconnect",))
        await task
        assert len(results) == 1

    asyncio.run(_inner())


def test_fan_out_two_consumers_both_receive():
    async def _inner():
        bus = make_bus()
        a, b = [], []

        async def consume(out):
            async for msg in _StreamListener(bus, "chat"):
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


# ── wait_for_rpc ──────────────────────────────────────────────────────────────


def test_wait_for_rpc_returns_data():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")

        async def producer():
            await asyncio.sleep(0)
            bot._bus.broadcast(("rpc", 20, b"\xde\xad"))

        asyncio.create_task(producer())
        data = await bot.wait_for_rpc(20)
        assert data == b"\xde\xad"

    asyncio.run(_inner())


def test_wait_for_rpc_predicate_skips_non_matching():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")

        async def producer():
            await asyncio.sleep(0)
            bot._bus.broadcast(("rpc", 20, b"\x00"))
            bot._bus.broadcast(("rpc", 20, b"\xff\xff"))

        asyncio.create_task(producer())
        data = await bot.wait_for_rpc(20, predicate=lambda rid, d: len(d) == 2)
        assert data == b"\xff\xff"

    asyncio.run(_inner())


# ── wait_for_dialog ───────────────────────────────────────────────────────────


def test_wait_for_dialog_type_filter():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")
        bot_mock = MagicMock()
        input_dlg = _make_dialog(1, 1, "Login", "OK", "", "", bot_mock)
        msgbox_dlg = _make_dialog(2, 0, "Info", "OK", "", "body", bot_mock)

        async def producer():
            await asyncio.sleep(0)
            bot._bus.broadcast(("dialog", msgbox_dlg))
            bot._bus.broadcast(("dialog", input_dlg))

        asyncio.create_task(producer())
        result = await bot.wait_for_dialog(dialog_type=InputDialog)
        assert isinstance(result, InputDialog)

    asyncio.run(_inner())


# ── wait_for_chat ─────────────────────────────────────────────────────────────


def test_wait_for_chat_player_id_filter():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")

        async def producer():
            await asyncio.sleep(0)
            bot._bus.broadcast(("chat", ChatMessage(player_id=9, text="no")))
            bot._bus.broadcast(("chat", ChatMessage(player_id=3, text="yes")))

        asyncio.create_task(producer())
        msg = await bot.wait_for_chat(player_id=3)
        assert msg.player_id == 3 and msg.text == "yes"

    asyncio.run(_inner())


# ── wait_for_client_message ───────────────────────────────────────────────────


def test_wait_for_client_message_color_filter():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")

        async def producer():
            await asyncio.sleep(0)
            bot._bus.broadcast(
                ("client_message", ServerMessage(color=0x00FF00FF, text="green"))
            )
            bot._bus.broadcast(
                ("client_message", ServerMessage(color=0xFF0000FF, text="red"))
            )

        asyncio.create_task(producer())
        msg = await bot.wait_for_client_message(color=0xFF0000FF)
        assert msg.color == 0xFF0000FF

    asyncio.run(_inner())


# ── wait_for_player_join ──────────────────────────────────────────────────────


def test_wait_for_player_join_name_filter():
    async def _inner():
        with patch("pyraksamp._SAMPClient"):
            bot = SAMPBot("host")

        async def producer():
            await asyncio.sleep(0)
            bot._bus.broadcast(("player_join", PlayerJoin(player_id=1, name="Bob")))
            bot._bus.broadcast(("player_join", PlayerJoin(player_id=2, name="Alice")))

        asyncio.create_task(producer())
        evt = await bot.wait_for_player_join(name="Alice")
        assert evt.name == "Alice"

    asyncio.run(_inner())
