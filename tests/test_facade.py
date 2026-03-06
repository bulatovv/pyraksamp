"""Isolated unit tests for SAMPBot facade and gen_gpci."""

import asyncio
from unittest.mock import patch

from pyraksamp import SAMPBot, SAMPClient, gen_gpci
from pyraksamp import _core
from pyraksamp._listener import _CallbackListener, _StreamListener
from pyraksamp.dialogs import InputDialog


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
        assert bot._bridge is not None
        assert isinstance(bot._listeners, list)


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


# ── on_* registers _CallbackListener ──────────────────────────────────────────


def test_on_connect_registers_listener():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")

        def fn(): pass

        bot.on_connect(fn)
        assert any(l._fn is fn for l in bot._listeners)


def test_on_connect_returns_fn():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")

        def fn(): pass

        assert bot.on_connect(fn) is fn


def test_on_dialog_registers_listener():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        received = []
        bot.on_dialog(dialog_type=InputDialog)(lambda dlg: received.append(dlg))
        assert len(bot._listeners) == 1
        assert isinstance(bot._listeners[0], _CallbackListener)


def test_on_connect_tag_is_connect():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")

        def fn(): pass

        bot.on_connect(fn)
        listener = next(l for l in bot._listeners if l._fn is fn)
        assert listener._tag == "connect"


def test_multiple_on_connect_handlers_allowed():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")

        def fn1(): pass
        def fn2(): pass

        bot.on_connect(fn1)
        bot.on_connect(fn2)
        connect_listeners = [l for l in bot._listeners if l._tag == "connect"]
        assert len(connect_listeners) == 2


# ── Stream methods return _StreamListener ─────────────────────────────────────


def test_chat_returns_stream_listener():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        assert isinstance(bot.chat(), _StreamListener)


def test_dialogs_returns_stream_listener():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        assert isinstance(bot.dialogs(), _StreamListener)


def test_events_stream_is_async_iterable():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        gen = bot.events()
        assert hasattr(gen, "__aiter__")


# ── start() wires bridge and starts listeners ─────────────────────────────────


def test_start_wires_bridge_and_calls_executor():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")

            setup_calls = []
            original_setup = bot._bridge.setup

            def record_setup(loop):
                setup_calls.append(loop)
                original_setup(loop)

            bot._bridge.setup = record_setup
            result = await bot.start()

        assert len(setup_calls) == 1
        assert result is True

    asyncio.run(_inner())


def test_start_starts_all_registered_listeners():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")

            def fn(): pass

            bot.on_connect(fn)
            bot.on_disconnect(fn)
            assert all(l._task is None for l in bot._listeners)

            await bot.start()
            assert all(l._task is not None for l in bot._listeners)

    asyncio.run(_inner())


def test_register_listener_after_start_starts_immediately():
    async def _inner():
        with patch("pyraksamp._SAMPClient") as MockClient:
            MockClient.return_value.start.return_value = True
            bot = SAMPBot("host")
            await bot.start()

            def fn(): pass

            bot.on_connect(fn)
            listener = next(l for l in bot._listeners if l._fn is fn)
            assert listener._task is not None

    asyncio.run(_inner())


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
            5, 1, 2, "text"
        )


# ── SAMPClient alias ──────────────────────────────────────────────────────────


def test_samp_client_is_alias_for_samp_bot():
    assert SAMPClient is SAMPBot
