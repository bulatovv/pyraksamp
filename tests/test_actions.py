"""Isolated unit tests for _Actions."""

import struct
from unittest.mock import MagicMock, call

from pyraksamp._actions import _Actions
from pyraksamp import _core


def make_client():
    client = MagicMock()
    client.send_rpc.return_value = True
    return client


# ── send_rpc ──────────────────────────────────────────────────────────────────


def test_send_rpc_delegates():
    client = make_client()
    actions = _Actions(client)
    result = actions.send_rpc(42, b"\x01\x02", _core.RELIABLE)
    client.send_rpc.assert_called_once_with(42, b"\x01\x02", _core.RELIABLE)
    assert result is True


def test_send_rpc_default_reliability():
    client = make_client()
    actions = _Actions(client)
    actions.send_rpc(7)
    _, _, reliability = client.send_rpc.call_args.args
    assert reliability == _core.RELIABLE


def test_send_rpc_default_data():
    client = make_client()
    actions = _Actions(client)
    actions.send_rpc(7)
    _, data, _ = client.send_rpc.call_args.args
    assert data == b""


# ── send_chat ─────────────────────────────────────────────────────────────────


def test_send_chat_encodes():
    client = make_client()
    actions = _Actions(client)
    actions.send_chat("hello")
    msg = b"hello"
    expected = struct.pack("B", 5) + msg
    client.send_rpc.assert_called_once_with(_core.RPC_CHAT, expected, _core.RELIABLE)


def test_send_chat_truncates_to_144():
    client = make_client()
    actions = _Actions(client)
    long_msg = "x" * 200
    actions.send_chat(long_msg)
    _, payload, _ = client.send_rpc.call_args.args
    length = payload[0]
    body = payload[1:]
    assert length == 144
    assert len(body) == 144


def test_send_chat_replaces_non_ascii():
    client = make_client()
    actions = _Actions(client)
    actions.send_chat("caf\u00e9")  # é → ?
    _, payload, _ = client.send_rpc.call_args.args
    body = payload[1:]
    assert body == b"caf?"


# ── send_dialog_response ──────────────────────────────────────────────────────


def test_send_dialog_response():
    client = make_client()
    actions = _Actions(client)
    actions.send_dialog_response(5, 1, 2, "text")
    client.send_dialog_response.assert_called_once_with(5, 1, 2, "text")


def test_send_dialog_response_defaults():
    client = make_client()
    actions = _Actions(client)
    actions.send_dialog_response(5, 0)
    client.send_dialog_response.assert_called_once_with(5, 0, 0, "")


# ── send_death ────────────────────────────────────────────────────────────────


def test_send_death_defaults():
    client = make_client()
    actions = _Actions(client)
    actions.send_death()
    client.send_death.assert_called_once_with(0, 0xFFFF)


def test_send_death_custom():
    client = make_client()
    actions = _Actions(client)
    actions.send_death(weapon_id=34, killer_id=7)
    client.send_death.assert_called_once_with(34, 7)


# ── send_enter_vehicle / send_exit_vehicle / send_command ─────────────────────


def test_send_enter_vehicle():
    client = make_client()
    actions = _Actions(client)
    actions.send_enter_vehicle(99, True)
    client.send_enter_vehicle.assert_called_once_with(99, True)


def test_send_enter_vehicle_default_passenger():
    client = make_client()
    actions = _Actions(client)
    actions.send_enter_vehicle(99)
    client.send_enter_vehicle.assert_called_once_with(99, False)


def test_send_exit_vehicle():
    client = make_client()
    actions = _Actions(client)
    actions.send_exit_vehicle(42)
    client.send_exit_vehicle.assert_called_once_with(42)


def test_send_command():
    client = make_client()
    actions = _Actions(client)
    actions.send_command("/stats")
    client.send_command.assert_called_once_with("/stats")
