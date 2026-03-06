"""Isolated unit tests for _CallbackBridge."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from pyraksamp._bus import _EventBus
from pyraksamp._actions import _Actions
from pyraksamp._bridge import _CallbackBridge
from pyraksamp.events import PlayerJoin
from pyraksamp.dialogs import InputDialog


# All 37 callback attribute names that _CallbackBridge.setup() must assign.
_ALL_CALLBACK_ATTRS = [
    "on_connect",
    "on_disconnect",
    "on_rpc",
    "on_player_join",
    "on_player_quit",
    "on_chat",
    "on_client_message",
    "on_dialog",
    "on_game_text",
    "on_set_health",
    "on_set_armour",
    "on_set_position",
    "on_checkpoint",
    "on_checkpoint_disabled",
    "on_player_streamed_in",
    "on_player_streamed_out",
    "on_player_name",
    "on_toggle_controllable",
    "on_player_time",
    "on_death_message",
    "on_set_armed_weapon",
    "on_spawn_info",
    "on_player_team",
    "on_put_in_vehicle",
    "on_remove_from_vehicle",
    "on_player_color",
    "on_world_time",
    "on_toggle_spectating",
    "on_wanted_level",
    "on_weapon_ammo",
    "on_gravity",
    "on_weather",
    "on_player_skin",
    "on_set_interior",
    "on_vehicle_streamed_in",
    "on_vehicle_streamed_out",
    "on_player_death",
]


def make_bridge():
    """Return (client_ns, bus, actions, bridge, loop_calls)."""
    client = SimpleNamespace()
    bus = _EventBus()
    mock_client = MagicMock()
    actions = _Actions(mock_client)

    loop_calls = []
    mock_loop = SimpleNamespace(call_soon_threadsafe=lambda fn: loop_calls.append(fn))

    bridge = _CallbackBridge(client, bus, actions)
    bridge.setup(mock_loop)
    return client, bus, actions, loop_calls


# ── setup assigns all callbacks ───────────────────────────────────────────────


def test_setup_assigns_all_callbacks():
    client, bus, actions, loop_calls = make_bridge()
    for attr in _ALL_CALLBACK_ATTRS:
        assert callable(getattr(client, attr, None)), f"missing callback: {attr}"


# ── on_connect ────────────────────────────────────────────────────────────────


def test_on_connect_schedules_lambda():
    client, bus, actions, loop_calls = make_bridge()
    client.on_connect()
    assert len(loop_calls) == 1


def test_on_connect_lambda_broadcasts_and_fires():
    async def _inner():
        client, bus, actions, loop_calls = make_bridge()
        received = []
        bus.on_connect(lambda: received.append("connected"))

        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_connect()
        loop_calls[0]()  # execute the scheduled lambda

        assert q.get_nowait() == ("connect",)
        assert received == ["connected"]

    asyncio.run(_inner())


# ── on_player_join ────────────────────────────────────────────────────────────


def test_on_player_join_constructs_event():
    async def _inner():
        client, bus, actions, loop_calls = make_bridge()
        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_player_join(42, "Alice")
        loop_calls[0]()

        tag, evt = q.get_nowait()
        assert tag == "player_join"
        assert evt == PlayerJoin(player_id=42, name="Alice")

    asyncio.run(_inner())


def test_on_player_join_fires_callback():
    async def _inner():
        client, bus, actions, loop_calls = make_bridge()
        received = []
        bus.on_player_join(lambda evt: received.append(evt))

        client.on_player_join(7, "Bob")
        loop_calls[0]()

        assert len(received) == 1
        assert received[0].name == "Bob"

    asyncio.run(_inner())


# ── on_dialog uses _actions ───────────────────────────────────────────────────


def test_on_dialog_uses_actions_not_client():
    async def _inner():
        client, bus, actions, loop_calls = make_bridge()
        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_dialog(1, 1, "Login", "OK", "Cancel", "Enter name:")
        loop_calls[0]()

        tag, dlg = q.get_nowait()
        assert tag == "dialog"
        assert isinstance(dlg, InputDialog)
        # _bot must be the _Actions instance, not the Rust client
        assert dlg._bot is actions

    asyncio.run(_inner())


# ── on_rpc ────────────────────────────────────────────────────────────────────


def test_on_rpc_broadcasts_correct_tuple():
    async def _inner():
        client, bus, actions, loop_calls = make_bridge()
        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_rpc(55, b"\x01")
        loop_calls[0]()

        evt = q.get_nowait()
        assert evt == ("rpc", 55, b"\x01")

    asyncio.run(_inner())


# ── on_vehicle_streamed_in add_siren cast to bool ─────────────────────────────


def test_on_vehicle_streamed_in_siren_cast_to_bool():
    async def _inner():
        client, bus, actions, loop_calls = make_bridge()
        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_vehicle_streamed_in(
            10,
            411,
            0.0,
            0.0,
            0.0,
            0.0,
            1,
            2,
            1000.0,
            0,
            0,
            0,
            0,
            0,
            1,  # add_siren as int
            0,
            0,
            0,
        )
        loop_calls[0]()

        tag, evt = q.get_nowait()
        assert tag == "vehicle_streamed_in"
        assert evt.add_siren is True

    asyncio.run(_inner())


# ── no sync execution ─────────────────────────────────────────────────────────


def test_no_sync_execution_before_lambda_called():
    client, bus, actions, loop_calls = make_bridge()
    q = asyncio.Queue()
    bus.subscribe(q)

    client.on_connect()
    # loop lambda captured but not executed yet
    assert q.qsize() == 0
    loop_calls[0]()
    assert q.qsize() == 1
