"""
pyraksamp — SA:MP 0.3.7 headless client library.

Quick start::

    import pyraksamp
    import threading

    client = pyraksamp.SAMPClient("play.example.com", 7777, "MyBot")

    @client.on_connect
    def connected():
        print(f"Connected as player {client.player_id}")
        client.send_chat("Hello!")

    @client.on_rpc
    def rpc(rpc_id, data):
        print(f"RPC {rpc_id}: {data.hex()}")

    if client.connect():
        threading.Thread(target=client.run, daemon=True).start()
"""

import random
import struct
import threading
from pyraksamp._core import SAMPClient as _SAMPClient
from pyraksamp import _core

__all__ = ["SAMPClient", "gen_gpci"]

# Re-export constants
UNRELIABLE           = _core.UNRELIABLE
UNRELIABLE_SEQUENCED = _core.UNRELIABLE_SEQUENCED
RELIABLE             = _core.RELIABLE
RELIABLE_ORDERED     = _core.RELIABLE_ORDERED
RELIABLE_SEQUENCED   = _core.RELIABLE_SEQUENCED

RPC_CLIENT_JOIN   = _core.RPC_CLIENT_JOIN
RPC_INIT_GAME     = _core.RPC_INIT_GAME
RPC_REQUEST_CLASS = _core.RPC_REQUEST_CLASS
RPC_REQUEST_SPAWN = _core.RPC_REQUEST_SPAWN
RPC_SPAWN         = _core.RPC_SPAWN
RPC_CHAT          = _core.RPC_CHAT


def gen_gpci() -> str:
    """Generate a random valid GPCI (hex string divisible by 1001, 35–49 chars)."""
    factor = 1001
    while True:
        n = random.randint(10**35, 10**47)
        r = n % factor
        if r:
            n += factor - r
        s = hex(n)[2:].upper()
        if 35 <= len(s) <= 49:
            return s


class SAMPClient:
    """High-level SA:MP headless client.

    Args:
        host:     Server hostname or IP.
        port:     Server port (default 7777).
        nickname: In-game nickname (max 20 chars).
        password: Server password (empty string if none).
        gpci:     GPCI string (auto-generated if not supplied).
    """

    def __init__(self, host: str, port: int = 7777, nickname: str = "PyBot",
                 password: str = "", gpci: str = ""):
        if not gpci:
            gpci = gen_gpci()
        self._client = _SAMPClient(host, port, nickname, password, gpci)
        self._thread: threading.Thread | None = None

    # ── Decorator-style callback registration ─────────────────────────────────

    def on_connect(self, fn):
        """Decorator: called with no arguments when fully connected."""
        self._client.on_connect = fn
        return fn

    def on_disconnect(self, fn):
        """Decorator: called when the server disconnects us."""
        self._client.on_disconnect = fn
        return fn

    def on_rpc(self, fn):
        """Decorator: called as fn(rpc_id: int, data: bytes) for every incoming RPC."""
        self._client.on_rpc = fn
        return fn

    def on_player_join(self, fn):
        """Decorator: called as fn(player_id: int, name: str)."""
        self._client.on_player_join = fn
        return fn

    # ── Connection control ────────────────────────────────────────────────────

    def connect(self, timeout: float = 15.0) -> bool:
        """Blocking connect. Returns True on success."""
        return self._client.connect(timeout)

    def run(self):
        """Blocking receive loop. Call after connect(), e.g. in a thread."""
        self._client.run()

    def start(self, timeout: float = 15.0) -> bool:
        """Connect and spawn background thread for run(). Returns True on success."""
        if not self.connect(timeout):
            return False
        self._thread = threading.Thread(target=self.run, daemon=True, name="samp-recv")
        self._thread.start()
        return True

    def stop(self):
        self._client.stop()

    def disconnect(self):
        self._client.disconnect()
        if self._thread:
            self._thread.join(timeout=2.0)

    # ── Game actions ──────────────────────────────────────────────────────────

    def send_rpc(self, rpc_id: int, data: bytes = b"",
                 reliability: int = RELIABLE) -> bool:
        return self._client.send_rpc(rpc_id, data, reliability)

    def send_chat(self, message: str):
        """Send a chat message (RPC 101)."""
        msg = message.encode("ascii", errors="replace")[:144]
        payload = struct.pack("B", len(msg)) + msg
        self.send_rpc(RPC_CHAT, payload)

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    @property
    def player_id(self) -> int:
        return self._client.player_id
