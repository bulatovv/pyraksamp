"""_Actions — outbound game actions (send_* methods)."""

import struct

from pyraksamp._core import SAMPClient as _SAMPClient
from pyraksamp import _core

RELIABLE = _core.RELIABLE


class _Actions:
    """Outbound game actions backed by _SAMPClient."""

    def __init__(self, client: _SAMPClient) -> None:
        self._client = client

    def send_rpc(
        self, rpc_id: int, data: bytes = b"", reliability: int = RELIABLE
    ) -> bool:
        """Send a raw RPC packet to the server.

        Parameters
        ----------
        rpc_id
            SA:MP RPC ID.
        data
            Raw payload bytes.
        reliability
            One of the module-level ``RELIABLE*`` / ``UNRELIABLE*`` constants.
        """
        return self._client.send_rpc(rpc_id, data, reliability)

    def send_chat(self, message: str) -> None:
        """Send a public chat message (RPC 101)."""
        msg = message.encode("ascii", errors="replace")[:144]
        self.send_rpc(_core.RPC_CHAT, struct.pack("B", len(msg)) + msg)

    def send_dialog_response(
        self, dialog_id: int, button: int, list_item: int = 0, text: str = ""
    ) -> None:
        """Respond to a dialog (SendDialogResponse)."""
        self._client.send_dialog_response(dialog_id, button, list_item, text)

    def send_death(self, weapon_id: int = 0, killer_id: int = 0xFFFF) -> None:
        """Send a death notification (SendDeathMessage)."""
        self._client.send_death(weapon_id, killer_id)

    def send_enter_vehicle(self, vehicle_id: int, is_passenger: bool = False) -> None:
        """Notify the server we are entering a vehicle."""
        self._client.send_enter_vehicle(vehicle_id, is_passenger)

    def send_exit_vehicle(self, vehicle_id: int) -> None:
        """Notify the server we are exiting a vehicle."""
        self._client.send_exit_vehicle(vehicle_id)

    def send_command(self, text: str) -> None:
        """Send a slash command (e.g. '/stats') to the server (RPC 50)."""
        self._client.send_command(text)
