"""Isolated unit tests for SAMPBot facade and gen_gpci."""

import asyncio
from unittest.mock import patch

from pyraksamp import SAMPBot, SAMPClient, gen_gpci
from pyraksamp import _core
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


def make_bot(gpci="AABBCCDDEE1122334455667788990011223344"):
    """Create a SAMPBot with a mocked _SAMPClient (no network)."""
    with patch("pyraksamp._SAMPClient") as MockClient:
        bot = SAMPBot("127.0.0.1", 7777, "TestBot", "", gpci)
        mock_instance = MockClient.return_value
        bot._mock_client = mock_instance
    return bot


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
        assert bot._streams is not None


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


# ── Callback delegation → _bus ────────────────────────────────────────────────


def test_on_connect_delegates_to_bus():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")

        def fn():
            pass

        bot.on_connect(fn)
        assert bot._bus._cb_connect is fn


def test_on_dialog_delegates_to_bus():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        received = []
        bot.on_dialog(dialog_type=InputDialog)(lambda dlg: received.append(dlg))
        assert bot._bus._cb_dialog is not None  # wrapper was installed


# ── Action delegation → _actions ──────────────────────────────────────────────


def test_send_chat_delegates_to_actions():
    with patch("pyraksamp._SAMPClient") as MockClient:
        bot = SAMPBot("host")
        bot.send_chat("hello")
        # _actions.send_chat ultimately calls client.send_rpc with RPC_CHAT
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


# ── Stream delegation → _streams ──────────────────────────────────────────────


def test_chat_stream_delegates():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        # Both calls should return an async generator backed by the same bus
        gen_a = bot.chat()
        gen_b = bot._streams.chat()
        # They are independent generator instances but backed by the same bus
        assert type(gen_a) is type(gen_b)


def test_events_stream_delegates():
    with patch("pyraksamp._SAMPClient"):
        bot = SAMPBot("host")
        gen = bot.events()
        assert hasattr(gen, "__aiter__")


# ── start() wires bridge ──────────────────────────────────────────────────────


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


# ── SAMPClient alias ──────────────────────────────────────────────────────────


def test_samp_client_is_alias_for_samp_bot():
    assert SAMPClient is SAMPBot
