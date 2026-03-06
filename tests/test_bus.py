"""Isolated unit tests for _EventBus."""

import asyncio
from unittest.mock import MagicMock

from pyraksamp._bus import _EventBus
from pyraksamp.dialogs import _make_dialog, InputDialog
from pyraksamp.events import (
    ChatMessage,
    PlayerJoin,
    ServerMessage,
    GameText,
)


# ── subscribe / unsubscribe ───────────────────────────────────────────────────


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


# ── broadcast ─────────────────────────────────────────────────────────────────


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


# ── fire ──────────────────────────────────────────────────────────────────────


def test_fire_none_is_noop():
    bus = _EventBus()
    bus.fire(None)  # must not raise


def test_fire_sync_callback():
    bus = _EventBus()
    received = []
    bus.fire(lambda x: received.append(x), 42)
    assert received == [42]


def test_fire_async_callback():
    bus = _EventBus()
    received = []

    async def cb(x):
        received.append(x)

    async def _run():
        bus.fire(cb, 99)
        await asyncio.sleep(0)  # allow task to execute

    asyncio.run(_run())
    assert received == [99]


# ── on_connect / on_disconnect ────────────────────────────────────────────────


def test_on_connect_stores_and_returns_fn():
    bus = _EventBus()

    def fn():
        pass

    result = bus.on_connect(fn)
    assert bus._cb_connect is fn
    assert result is fn


def test_on_disconnect_stores_and_returns_fn():
    bus = _EventBus()

    def fn():
        pass

    result = bus.on_disconnect(fn)
    assert bus._cb_disconnect is fn
    assert result is fn


# ── on_rpc ────────────────────────────────────────────────────────────────────


def test_on_rpc_no_filter_stores_fn_directly():
    bus = _EventBus()

    def fn(rid, data):
        pass

    bus.on_rpc(fn)
    assert bus._cb_rpc is fn


def test_on_rpc_rpc_id_filter_skips_non_matching():
    bus = _EventBus()
    received = []
    bus.on_rpc(rpc_id=10)(lambda rid, data: received.append(rid))
    asyncio.run(bus._cb_rpc(5, b""))
    assert received == []


def test_on_rpc_rpc_id_filter_calls_matching():
    bus = _EventBus()
    received = []
    bus.on_rpc(rpc_id=10)(lambda rid, data: received.append(rid))
    asyncio.run(bus._cb_rpc(10, b"hi"))
    assert received == [10]


def test_on_rpc_predicate_filter():
    bus = _EventBus()
    received = []
    bus.on_rpc(predicate=lambda rid, data: len(data) > 2)(
        lambda rid, data: received.append(data)
    )
    asyncio.run(bus._cb_rpc(1, b"ab"))  # 2 bytes — blocked
    asyncio.run(bus._cb_rpc(1, b"abc"))  # 3 bytes — passes
    assert received == [b"abc"]


# ── on_player_join ────────────────────────────────────────────────────────────


def test_on_player_join_no_filter():
    bus = _EventBus()
    received = []
    bus.on_player_join(lambda evt: received.append(evt))
    evt = PlayerJoin(player_id=1, name="Alice")
    bus._cb_player_join(evt)
    assert received == [evt]


def test_on_player_join_player_id_filter_passes():
    bus = _EventBus()
    received = []
    bus.on_player_join(player_id=1)(lambda evt: received.append(evt))
    asyncio.run(bus._cb_player_join(PlayerJoin(player_id=1, name="Alice")))
    assert len(received) == 1


def test_on_player_join_player_id_filter_blocks():
    bus = _EventBus()
    received = []
    bus.on_player_join(player_id=1)(lambda evt: received.append(evt))
    asyncio.run(bus._cb_player_join(PlayerJoin(player_id=2, name="Bob")))
    assert received == []


def test_on_player_join_name_filter():
    bus = _EventBus()
    received = []
    bus.on_player_join(name="Alice")(lambda evt: received.append(evt))
    asyncio.run(bus._cb_player_join(PlayerJoin(player_id=1, name="Alice")))
    asyncio.run(bus._cb_player_join(PlayerJoin(player_id=2, name="Bob")))
    assert len(received) == 1 and received[0].name == "Alice"


# ── on_chat ───────────────────────────────────────────────────────────────────


def test_on_chat_player_id_filter():
    bus = _EventBus()
    received = []
    bus.on_chat(player_id=3)(lambda evt: received.append(evt))
    asyncio.run(bus._cb_chat(ChatMessage(player_id=3, text="hi")))
    asyncio.run(bus._cb_chat(ChatMessage(player_id=4, text="bye")))
    assert len(received) == 1 and received[0].player_id == 3


# ── on_client_message ─────────────────────────────────────────────────────────


def test_on_client_message_color_filter():
    bus = _EventBus()
    received = []
    bus.on_client_message(color=0xFF0000FF)(lambda evt: received.append(evt))
    asyncio.run(bus._cb_client_message(ServerMessage(color=0xFF0000FF, text="red")))
    asyncio.run(bus._cb_client_message(ServerMessage(color=0x00FF00FF, text="green")))
    assert len(received) == 1 and received[0].color == 0xFF0000FF


# ── on_dialog ─────────────────────────────────────────────────────────────────


def test_on_dialog_no_filter_stores_fn_directly():
    bus = _EventBus()

    def fn(dlg):
        pass

    bus.on_dialog(fn)
    assert bus._cb_dialog is fn


def test_on_dialog_type_filter_passes_matching():
    bus = _EventBus()
    received = []
    bot = MagicMock()
    bus.on_dialog(dialog_type=InputDialog)(lambda dlg: received.append(dlg))
    dlg = _make_dialog(1, 1, "Login", "OK", "Cancel", "name", bot)
    asyncio.run(bus._cb_dialog(dlg))
    assert len(received) == 1 and isinstance(received[0], InputDialog)


def test_on_dialog_type_filter_blocks_wrong_type():
    bus = _EventBus()
    received = []
    bot = MagicMock()
    bus.on_dialog(dialog_type=InputDialog)(lambda dlg: received.append(dlg))
    dlg = _make_dialog(2, 0, "Info", "OK", "", "body", bot)  # MsgboxDialog
    asyncio.run(bus._cb_dialog(dlg))
    assert received == []


def test_on_dialog_dialog_id_filter():
    bus = _EventBus()
    received = []
    bot = MagicMock()
    bus.on_dialog(dialog_id=5)(lambda dlg: received.append(dlg))
    asyncio.run(bus._cb_dialog(_make_dialog(5, 0, "T", "OK", "", "b", bot)))
    asyncio.run(bus._cb_dialog(_make_dialog(6, 0, "T", "OK", "", "b", bot)))
    assert len(received) == 1 and received[0].dialog_id == 5


def test_on_dialog_type_and_predicate():
    bus = _EventBus()
    received = []
    bot = MagicMock()
    bus.on_dialog(
        dialog_type=InputDialog,
        predicate=lambda d: "Login" in d.title,
    )(lambda dlg: received.append(dlg))
    asyncio.run(
        bus._cb_dialog(_make_dialog(1, 1, "Login", "OK", "", "", bot))
    )  # passes
    asyncio.run(
        bus._cb_dialog(_make_dialog(2, 1, "Register", "OK", "", "", bot))
    )  # blocked
    assert len(received) == 1


# ── on_game_text ──────────────────────────────────────────────────────────────


def test_on_game_text_style_filter():
    bus = _EventBus()
    received = []
    bus.on_game_text(style=3)(lambda evt: received.append(evt))
    asyncio.run(bus._cb_game_text(GameText(style=3, duration_ms=1000, text="go")))
    asyncio.run(bus._cb_game_text(GameText(style=1, duration_ms=500, text="no")))
    assert len(received) == 1 and received[0].style == 3


# ── Simple on_* decorators ────────────────────────────────────────────────────


def test_simple_decorators_store_fn():
    bus = _EventBus()

    def fn(evt):
        pass

    bus.on_set_health(fn)
    assert bus._cb_set_health is fn
    bus.on_set_armour(fn)
    assert bus._cb_set_armour is fn
    bus.on_set_position(fn)
    assert bus._cb_set_position is fn
    bus.on_checkpoint(fn)
    assert bus._cb_checkpoint is fn
    bus.on_checkpoint_disabled(fn)
    assert bus._cb_checkpoint_disabled is fn


def test_simple_decorators_return_fn():
    bus = _EventBus()

    def fn():
        pass

    assert bus.on_connect(fn) is fn
    assert bus.on_disconnect(fn) is fn
    assert bus.on_set_health(fn) is fn
    assert bus.on_player_death(fn) is fn
