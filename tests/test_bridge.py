"""Isolated unit tests for _setup_bridge."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from pyraksamp._bus import _EventBus
from pyraksamp._bridge import _setup_bridge
from pyraksamp.dialogs import _make_dialog, InputDialog
from pyraksamp.events import PlayerJoin


# All 37 callback attribute names that _setup_bridge must assign.
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


def setup():
    """Return (client_ns, bus, mock_actions, loop_calls)."""
    client = SimpleNamespace()
    bus = _EventBus()
    mock_actions = MagicMock()

    def make_dialog(did, style, title, btn1, btn2, body):
        return _make_dialog(did, style, title, btn1, btn2, body, mock_actions)

    loop_calls = []
    mock_loop = SimpleNamespace(call_soon_threadsafe=lambda fn: loop_calls.append(fn))

    _setup_bridge(client, bus, make_dialog, mock_loop)
    return client, bus, mock_actions, loop_calls


# ── assigns all callbacks ─────────────────────────────────────────────────────


def test_assigns_all_callbacks():
    client, bus, mock_actions, loop_calls = setup()
    for attr in _ALL_CALLBACK_ATTRS:
        assert callable(getattr(client, attr, None)), f"missing callback: {attr}"


# ── on_connect ────────────────────────────────────────────────────────────────


def test_on_connect_schedules_lambda():
    client, bus, mock_actions, loop_calls = setup()
    client.on_connect()
    assert len(loop_calls) == 1


def test_on_connect_lambda_broadcasts():
    async def _inner():
        client, bus, mock_actions, loop_calls = setup()
        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_connect()
        loop_calls[0]()

        assert q.get_nowait() == ("connect",)

    asyncio.run(_inner())


# ── on_player_join ────────────────────────────────────────────────────────────


def test_on_player_join_constructs_event():
    async def _inner():
        client, bus, mock_actions, loop_calls = setup()
        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_player_join(42, "Alice")
        loop_calls[0]()

        tag, evt = q.get_nowait()
        assert tag == "player_join"
        assert evt == PlayerJoin(player_id=42, name="Alice")

    asyncio.run(_inner())


# ── on_dialog uses make_dialog factory ───────────────────────────────────────


def test_on_dialog_uses_make_dialog_factory():
    async def _inner():
        client, bus, mock_actions, loop_calls = setup()
        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_dialog(1, 1, "Login", "OK", "Cancel", "Enter name:")
        loop_calls[0]()

        tag, dlg = q.get_nowait()
        assert tag == "dialog"
        assert isinstance(dlg, InputDialog)
        assert dlg._bot is mock_actions

    asyncio.run(_inner())


# ── on_rpc ────────────────────────────────────────────────────────────────────


def test_on_rpc_broadcasts_correct_tuple():
    async def _inner():
        client, bus, mock_actions, loop_calls = setup()
        q = asyncio.Queue()
        bus.subscribe(q)

        client.on_rpc(55, b"\x01")
        loop_calls[0]()

        assert q.get_nowait() == ("rpc", 55, b"\x01")

    asyncio.run(_inner())


# ── on_vehicle_streamed_in add_siren cast to bool ─────────────────────────────


def test_on_vehicle_streamed_in_siren_cast_to_bool():
    async def _inner():
        client, bus, mock_actions, loop_calls = setup()
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
    client, bus, mock_actions, loop_calls = setup()
    q = asyncio.Queue()
    bus.subscribe(q)

    client.on_connect()
    assert q.qsize() == 0
    loop_calls[0]()
    assert q.qsize() == 1
