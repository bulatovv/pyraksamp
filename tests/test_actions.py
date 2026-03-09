"""Isolated unit tests for _Actions."""

import asyncio
import contextlib
import struct
from unittest.mock import MagicMock

import pytest

from pyraksamp._actions import _Actions
from pyraksamp import _core
from pyraksamp import Keys


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


def test_send_chat_encodes_utf8_by_default():
    client = make_client()
    actions = _Actions(client)
    actions.send_chat("caf\u00e9")  # é → UTF-8 \xc3\xa9
    _, payload, _ = client.send_rpc.call_args.args
    body = payload[1:]
    assert body == "caf\u00e9".encode("utf-8")


def test_send_chat_uses_server_encoding():
    client = make_client()
    actions = _Actions(client, encoding="ascii")
    actions.send_chat("caf\u00e9")  # é → ? with ascii+replace
    _, payload, _ = client.send_rpc.call_args.args
    body = payload[1:]
    assert body == b"caf?"


# ── send_dialog_response ──────────────────────────────────────────────────────


def test_send_dialog_response():
    client = make_client()
    actions = _Actions(client)
    actions.send_dialog_response(5, 1, 2, "text")
    client.send_dialog_response.assert_called_once_with(5, 1, 2, b"text")


def test_send_dialog_response_defaults():
    client = make_client()
    actions = _Actions(client)
    actions.send_dialog_response(5, 0)
    client.send_dialog_response.assert_called_once_with(5, 0, 0, b"")


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
    client.send_command.assert_called_once_with(b"/stats")


# ── send_keys (low-level) ──────────────────────────────────────────────────────


def test_send_keys_delegates():
    client = make_client()
    actions = _Actions(client)
    actions.send_keys(4, 100, 200)
    client.set_keys.assert_called_once_with(4, 100, 200)


def test_send_keys_defaults():
    client = make_client()
    actions = _Actions(client)
    actions.send_keys(0)
    client.set_keys.assert_called_once_with(0, 0, 0)


def test_send_keys_masks_negative_analog():
    client = make_client()
    actions = _Actions(client)
    actions.send_keys(0, -128, -256)
    _, lr, ud = client.set_keys.call_args.args
    assert lr == (-128 & 0xFFFF)
    assert ud == (-256 & 0xFFFF)


def test_send_keys_accepts_keys_enum():
    client = make_client()
    actions = _Actions(client)
    actions.send_keys(Keys.FIRE | Keys.SPRINT)
    client.set_keys.assert_called_once_with(int(Keys.FIRE | Keys.SPRINT), 0, 0)


# ── press_keys (high-level) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_press_keys_sets_then_clears():
    client = make_client()
    actions = _Actions(client)
    await actions.press_keys(int(Keys.FIRE), duration=0)
    calls = [c.args[0] for c in client.set_keys.call_args_list]
    assert calls[0] == int(Keys.FIRE)   # pressed
    assert calls[-1] == 0               # released


@pytest.mark.asyncio
async def test_press_keys_concurrent_different_bits():
    """SPRINT and FIRE pressed concurrently; FIRE releases first without killing SPRINT."""
    client = make_client()
    actions = _Actions(client)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(actions.press_keys(int(Keys.SPRINT), duration=0.05))
        tg.create_task(actions.press_keys(int(Keys.FIRE),   duration=0.02))
    assert client.set_keys.call_args.args[0] == 0


@pytest.mark.asyncio
async def test_press_keys_refcount_same_bit():
    """Same key pressed twice; only clears when both calls finish."""
    client = make_client()
    actions = _Actions(client)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(actions.press_keys(int(Keys.FIRE), duration=0.05))
        tg.create_task(actions.press_keys(int(Keys.FIRE), duration=0.02))
    assert client.set_keys.call_args.args[0] == 0


@pytest.mark.asyncio
async def test_press_keys_combined_key():
    """FIRE|SPRINT pressed as one call; both bits set then both cleared."""
    client = make_client()
    actions = _Actions(client)
    await actions.press_keys(int(Keys.FIRE | Keys.SPRINT), duration=0)
    key_states = [c.args[0] for c in client.set_keys.call_args_list]
    assert key_states[0] == int(Keys.FIRE | Keys.SPRINT)
    assert key_states[-1] == 0


@pytest.mark.asyncio
async def test_press_keys_intermediate_state():
    """SPRINT still set at the exact moment FIRE releases (not yet zero)."""
    client = make_client()
    actions = _Actions(client)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(actions.press_keys(int(Keys.SPRINT), duration=0.05))
        tg.create_task(actions.press_keys(int(Keys.FIRE),   duration=0.02))
    # Expected call sequence: set(SPRINT), set(SPRINT|FIRE), set(SPRINT), set(0)
    # The second-to-last call must still have SPRINT but not FIRE.
    key_states = [c.args[0] for c in client.set_keys.call_args_list]
    assert key_states[-2] == int(Keys.SPRINT)
    assert key_states[-1] == 0


@pytest.mark.asyncio
async def test_press_keys_releases_on_cancel():
    """Keys are released even when the task is cancelled."""
    client = make_client()
    actions = _Actions(client)
    task = asyncio.create_task(actions.press_keys(int(Keys.SPRINT), duration=10))
    await asyncio.sleep(0)  # let task start
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert client.set_keys.call_args.args[0] == 0
