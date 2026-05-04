"""_Actions — outbound game actions (send_* methods)."""

import asyncio
import struct
from collections import Counter

from pyraksamp import _core
from pyraksamp._core import SAMPClient as _SAMPClient

RELIABLE = _core.RELIABLE


class _Actions:
    """Outbound game actions backed by _SAMPClient."""

    def __init__(self, client: _SAMPClient, encoding: str = "utf-8") -> None:
        self._client = client
        self._encoding = encoding
        self._key_refs: Counter[int] = Counter()  # bit → hold count

    def _enc(self, text: str, max_bytes: int) -> bytes:
        return text.encode(self._encoding, errors="replace")[:max_bytes]

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
        msg = self._enc(message, 144)
        self.send_rpc(_core.RPC_CHAT, struct.pack("B", len(msg)) + msg)

    def send_dialog_response(
        self, dialog_id: int, button: int, list_item: int = 0, text: str = ""
    ) -> None:
        """Respond to a dialog (SendDialogResponse)."""
        self._client.send_dialog_response(
            dialog_id, button, list_item, self._enc(text, 255)
        )

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
        self._client.send_command(self._enc(text, 100))

    def click_textdraw(self, textdraw_id: int) -> None:
        """Send SelectTextDraw RPC (83) for the given textdraw ID."""
        self._client.click_textdraw(textdraw_id)

    def send_keys(self, keys: int, lr_analog: int = 0, ud_analog: int = 0) -> None:
        """Directly set the key state reported in on-foot sync packets (sticky).

        The state persists across keepalive packets until called again.
        Bypasses the ref-counting used by :meth:`press_keys`.

        Parameters
        ----------
        keys
            Bitmask of pressed keys (use :class:`Keys` constants).
        lr_analog
            Left/right analog axis value (signed, cast to u16; 0 = neutral).
        ud_analog
            Up/down analog axis value (signed, cast to u16; 0 = neutral).
        """
        self._client.set_keys(keys & 0xFFFF, lr_analog & 0xFFFF, ud_analog & 0xFFFF)

    def _recompute_keys(self) -> None:
        bitmask = 0
        for bit, count in self._key_refs.items():
            if count > 0:
                bitmask |= bit
        self._client.set_keys(bitmask & 0xFFFF, 0, 0)

    async def press_keys(self, keys: int, duration: float = 0.5) -> None:
        """Hold *keys* for *duration* seconds, then auto-release.

        Safe to call concurrently — each call only releases its own bits.
        If the same key is held by multiple concurrent calls, it stays
        pressed until the last one finishes (ref-counted per bit).

        Parameters
        ----------
        keys
            Bitmask of keys to press (use :class:`Keys` constants).
        duration
            Seconds to hold before auto-release (default 0.5 s = one keepalive
            interval, guaranteeing at least one packet is sent).
        """
        bits = [1 << i for i in range(19) if keys & (1 << i)]
        for b in bits:
            self._key_refs[b] += 1
        self._recompute_keys()
        try:
            await asyncio.sleep(duration)
        finally:
            for b in bits:
                self._key_refs[b] -= 1
                if self._key_refs[b] == 0:
                    del self._key_refs[b]
            self._recompute_keys()
