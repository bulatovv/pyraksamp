"""Isolated unit tests for SAMPBot facade and gen_gpci."""

import asyncio
from unittest.mock import patch

from pyraksamp import SAMPBot, SAMPClient, gen_gpci
from pyraksamp import _core
from pyraksamp.dialogs import InputDialog, _make_dialog, _Responder
from unittest.mock import MagicMock


# ── gen_gpci ──────────────────────────────────────────────────────────────────


def test_gen_gpci_valid_hex_string():
    s = gen_gpci()
    assert isinstance(s, str)
    assert all(c in "0123456789ABCDEFabcdef" for c in s)


def test_gen_gpci_correct_length():
    s = gen_gpci()
    assert 35 <= len(s) <= 49


def test_gen_gpci_divisible_by_1001():
    s = gen_gpci()
    assert int(s, 16) % 1001 == 0


def test_gen_gpci_varies():
    results = {gen_gpci() for _ in range(10)}
    assert len(results) > 1  # very unlikely to always be the same


# ── SAMPBot.__init__ ──────────────────────────────────────────────────────────


def test_init_uses_provided_gpci():
    gpci = "AABBCCDDEE1122334455667788990011223344"
    with patch("pyraksamp._SAMPClient") as MockClient:
        SAMPBot("host", 7777, "Bot", "", gpci)
        args = MockClient.call_args.args
        assert args[4] == gpci


def test_init_generates_gpci_when_empty():
    with patch("pyraksamp._SAMPClient") as MockClient:
        SAMPBot("host", 7777, "Bot")
        args = MockClient.call_args.args
        gpci = args[4]
        assert 35 <= len(gpci) <= 49
        assert int(gpci, 16) % 1001 == 0


def test_init_creates_all_components():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        assert bot._bus is not None
        assert bot._actions is not None
        assert bot._make_dialog is not None


# ── Properties ────────────────────────────────────────────────────────────────


def test_is_connected_delegates():
    with patch("pyraksamp._SAMPClient") as MockClient:
        MockClient.return_value.is_connected = True
        bot = SAMPBot("host")
        assert bot.is_connected is True


def test_player_id_delegates():
    with patch("pyraksamp._SAMPClient") as MockClient:
        MockClient.return_value.player_id = 42
        bot = SAMPBot("host")
        assert bot.player_id == 42


# ── Lifecycle ─────────────────────────────────────────────────────────────────


def test_disconnect_calls_client():
    with patch("pyraksamp._SAMPClient") as MockClient:
        bot = SAMPBot("host")
        bot.disconnect()
        MockClient.return_value.disconnect.assert_called_once()


def test_stop_calls_client():
    with patch("pyraksamp._SAMPClient") as MockClient:
        bot = SAMPBot("host")
        bot.stop()
        MockClient.return_value.stop.assert_called_once()


# ── on_connect fires callback on connect event ────────────────────────────────


def test_on_connect_fires_on_connect_event():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            called = []
            bot.on_connect(lambda: called.append(True))
            await bot.start()
            bot._bus.broadcast(("connect",))
            await asyncio.sleep(0)  # dispatcher routes
            await asyncio.sleep(0)  # listener processes
            assert called == [True]

    asyncio.run(_inner())


def test_on_connect_returns_fn():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")

        def fn():
            pass

        assert bot.on_connect(fn) is fn


def test_on_connect_does_not_fire_on_other_events():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            called = []
            bot.on_connect(lambda: called.append(True))
            await bot.start()
            bot._bus.broadcast(("disconnect",))
            await asyncio.sleep(0)
            assert called == []

    asyncio.run(_inner())


def test_multiple_on_connect_handlers_all_fire():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            calls = []
            bot.on_connect(lambda: calls.append(1))
            bot.on_connect(lambda: calls.append(2))
            await bot.start()
            bot._bus.broadcast(("connect",))
            await asyncio.sleep(0)  # dispatcher routes
            await asyncio.sleep(0)  # listener processes
            assert sorted(calls) == [1, 2]

    asyncio.run(_inner())


def test_on_rpc_fires_on_rpc_event():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            received = []
            bot.on_rpc(rpc_id=42)(lambda rid, data: received.append((rid, data)))
            await bot.start()
            bot._bus.broadcast(("rpc", 42, b"\xff"))
            await asyncio.sleep(0)  # dispatcher routes
            await asyncio.sleep(0)  # listener processes
            assert received == [(42, b"\xff")]

    asyncio.run(_inner())


def test_on_dialog_fires_on_dialog_event():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            received = []
            bot.on_dialog(dialog_type=InputDialog)(lambda dlg: received.append(dlg))
            await bot.start()
            dlg = _make_dialog(
                1,
                1,
                "Login",
                "Submit",
                "Cancel",
                "Enter:",
                _Responder(MagicMock().send_dialog_response),
            )
            bot._bus.broadcast(("dialog", dlg))
            await asyncio.sleep(0)  # dispatcher routes
            await asyncio.sleep(0)  # listener processes
            assert len(received) == 1
            assert isinstance(received[0], InputDialog)

    asyncio.run(_inner())


# ── start() wires bridge and starts listeners ─────────────────────────────────


def test_start_wires_bridge_and_calls_executor():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            result = await bot.start()
            # All client callbacks should be assigned by _setup_bridge
            assert callable(MockClient.return_value.on_connect)
            assert result is True

    asyncio.run(_inner())


def test_start_enables_callbacks():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            called = []
            bot.on_connect(lambda: called.append(True))
            bot.on_disconnect(lambda: called.append(False))
            await bot.start()
            bot._bus.broadcast(("connect",))
            await asyncio.sleep(0)  # dispatcher routes
            await asyncio.sleep(0)  # listener processes
            assert True in called

    asyncio.run(_inner())


def test_register_listener_after_start_fires_immediately():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            await bot.start()
            called = []
            bot.on_connect(lambda: called.append(True))
            bot._bus.broadcast(("connect",))
            await asyncio.sleep(0)  # dispatcher routes
            await asyncio.sleep(0)  # listener processes
            assert called == [True]

    asyncio.run(_inner())


# ── Stream methods yield events ───────────────────────────────────────────────


def test_chat_stream_yields_chat_events():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            await bot.start()
            from pyraksamp.events import ChatMessage

            msg = ChatMessage(player_id=1, raw=b"hello", text="hello")
            results = []

            async def consume():
                async for m in bot.chat():
                    results.append(m)

            task = asyncio.create_task(consume())
            await asyncio.sleep(0)
            bot._bus.broadcast(("chat", msg))
            bot._bus.broadcast(("disconnect",))
            await task
            assert results == [msg]

    asyncio.run(_inner())


def test_dialogs_stream_yields_dialog_events():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            await bot.start()
            dlg = _make_dialog(
                1,
                0,
                "T",
                "OK",
                "",
                "body",
                _Responder(MagicMock().send_dialog_response),
            )
            results = []

            async def consume():
                async for d in bot.dialogs():
                    results.append(d)

            task = asyncio.create_task(consume())
            await asyncio.sleep(0)
            bot._bus.broadcast(("dialog", dlg))
            bot._bus.broadcast(("disconnect",))
            await task
            assert results == [dlg]

    asyncio.run(_inner())


def test_events_stream_is_async_iterable():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        gen = bot.events()
        assert hasattr(gen, "__aiter__")


# ── Action delegation ─────────────────────────────────────────────────────────


def test_send_chat_delegates_to_actions():
    with patch("pyraksamp._SAMPClient") as MockClient:
        bot = SAMPBot("host")
        bot.send_chat("hello")
        MockClient.return_value.send_rpc.assert_called_once()
        args = MockClient.return_value.send_rpc.call_args.args
        assert args[0] == _core.RPC_CHAT


def test_send_dialog_response_delegates():
    with patch("pyraksamp._SAMPClient") as MockClient:
        bot = SAMPBot("host")
        bot.send_dialog_response(5, 1, 2, "text")
        MockClient.return_value.send_dialog_response.assert_called_once_with(
            5, 1, 2, b"text"
        )


# ── atexit registration ───────────────────────────────────────────────────────


def test_start_registers_atexit_handler():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient, patch(
            "atexit.register"
        ) as mock_register:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            await bot.start()
            mock_register.assert_called_once_with(MockClient.return_value.stop)

    asyncio.run(_inner())


def test_start_registers_atexit_only_once():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient, patch(
            "atexit.register"
        ) as mock_register:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            await bot.start()
            await bot.start()
            mock_register.assert_called_once()

    asyncio.run(_inner())


# ── SAMPClient alias ──────────────────────────────────────────────────────────


def test_samp_client_is_alias_for_samp_bot():
    assert SAMPClient is SAMPBot
