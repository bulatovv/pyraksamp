"""
pyraksamp — SA:MP 0.3.7 async headless client library.

Quick start::

    import asyncio
    import pyraksamp

    async def main():
        bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")

        @bot.on_connect
        async def connected():
            print(f"Connected as player {bot.player_id}")

        if not await bot.start():
            return

        # Sequential dialog flow while chat is handled concurrently
        lock = asyncio.Lock()
        asyncio.create_task(chat_handler(bot))
        asyncio.create_task(dialog_handler(bot, lock))

        # Keep running until disconnected
        async for event in bot.events():
            if event[0] == 'disconnect':
                break

    asyncio.run(main())
"""

import asyncio
import random
import struct
import threading
from pyraksamp._core import SAMPClient as _SAMPClient
from pyraksamp import _core

__all__ = ["SAMPBot", "gen_gpci"]

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


class SAMPBot:
    """Async SA:MP 0.3.7 headless client.

    Internally runs one daemon thread per bot (the C++ receive/keepalive loop).
    All user-facing callbacks and event streams run in the asyncio event loop —
    no thread management required from user code.

    Sending (send_rpc, send_chat) is synchronous and safe to call from
    async code — no await needed, no executor overhead.
    """

    def __init__(self, host: str, port: int = 7777, nickname: str = "PyBot",
                 password: str = "", gpci: str = ""):
        if not gpci:
            gpci = gen_gpci()
        self._client = _SAMPClient(host, port, nickname, password, gpci)
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        # Fan-out subscriber queues.  Each active rpcs()/events() call appends
        # its own queue here; _broadcast() copies every event to all of them so
        # concurrent consumers are fully independent (no event stealing).
        # Accessed only from the event-loop thread (via call_soon_threadsafe),
        # so no additional locking is required.
        self._subscribers: list[asyncio.Queue] = []

        # User-registered callbacks (set via decorators or direct assignment).
        self._cb_connect: object = None
        self._cb_disconnect: object = None
        self._cb_rpc: object = None
        self._cb_player_join: object = None

    # ── Internal: async bridge ─────────────────────────────────────────────────

    def _broadcast(self, event: tuple) -> None:
        """Fan an event out to every active subscriber queue.
        Always called inside the event loop (via call_soon_threadsafe).
        """
        for q in self._subscribers:
            q.put_nowait(event)

    def _fire(self, cb, *args) -> None:
        """Call a user callback (sync or async def) from the event loop thread."""
        if cb is None:
            return
        if asyncio.iscoroutinefunction(cb):
            asyncio.create_task(cb(*args))
        else:
            cb(*args)

    def _setup_callbacks(self, loop: asyncio.AbstractEventLoop) -> None:
        """Wire C++ callbacks → asyncio event loop.

        The C++ run() thread invokes these functions with the GIL held (pybind11
        acquires it before each callback).  We must not block here; instead we
        schedule all work onto the event loop with call_soon_threadsafe so that
        both the broadcast and user callback always execute in the loop thread.
        """
        def on_connect():
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('connect',)),
                self._fire(self._cb_connect),
            ))

        def on_disconnect():
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('disconnect',)),
                self._fire(self._cb_disconnect),
            ))

        def on_rpc(rpc_id: int, data: bytes):
            # data arrives as bytes from the pybind11 binding — immutable and
            # safe to capture in the closure across threads.
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('rpc', rpc_id, data)),
                self._fire(self._cb_rpc, rpc_id, data),
            ))

        def on_player_join(pid: int, name: str):
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('player_join', pid, name)),
                self._fire(self._cb_player_join, pid, name),
            ))

        self._client.on_connect     = on_connect
        self._client.on_disconnect  = on_disconnect
        self._client.on_rpc         = on_rpc
        self._client.on_player_join = on_player_join

    # ── Decorator-style callbacks ──────────────────────────────────────────────
    # Accept both plain functions and async def coroutines.

    def on_connect(self, fn):
        """Decorator: called (no args) when fully connected."""
        self._cb_connect = fn
        return fn

    def on_disconnect(self, fn):
        """Decorator: called (no args) on disconnection."""
        self._cb_disconnect = fn
        return fn

    def on_rpc(self, fn):
        """Decorator: fn(rpc_id: int, data: bytes) for every incoming RPC."""
        self._cb_rpc = fn
        return fn

    def on_player_join(self, fn):
        """Decorator: fn(player_id: int, name: str) when a player joins."""
        self._cb_player_join = fn
        return fn

    # ── Connection lifecycle ───────────────────────────────────────────────────

    async def connect(self, timeout: float = 15.0) -> bool:
        """Perform the full handshake/auth/join sequence.
        Runs the blocking C++ connect() in a thread-pool executor.
        Returns True on success.
        """
        loop = asyncio.get_running_loop()
        self._loop = loop
        self._setup_callbacks(loop)
        return await loop.run_in_executor(None, lambda: self._client.connect(timeout))

    async def start(self, timeout: float = 15.0) -> bool:
        """Connect, then spawn the background C++ receive/keepalive thread.
        Returns True on success.  After this returns, events begin flowing.
        """
        if not await self.connect(timeout):
            return False
        self._thread = threading.Thread(
            target=self._client.run, daemon=True, name=f"samp-recv-{self._client.player_id}")
        self._thread.start()
        return True

    async def disconnect(self) -> None:
        """Send disconnect notification and wait for the receive thread to exit."""
        loop = asyncio.get_running_loop()
        self._client.disconnect()
        if self._thread:
            await loop.run_in_executor(None, lambda: self._thread.join(timeout=2.0))
            self._thread = None

    def stop(self) -> None:
        """Signal the receive loop to stop without sending a disconnect packet."""
        self._client.stop()

    # ── Event streams ──────────────────────────────────────────────────────────

    async def rpcs(self, rpc_id: int | None = None):
        """Async generator that yields (rpc_id, data) for every incoming RPC.

        Each call creates an independent subscriber — multiple concurrent
        consumers each see every event independently (fan-out, no stealing).

        Args:
            rpc_id: If given, yield only RPCs matching this ID.

        Example::

            # Two concurrent consumers, both see all events:
            asyncio.create_task(chat_handler(bot))   # uses rpcs(CHAT_RPC)
            asyncio.create_task(dialog_handler(bot)) # uses rpcs(SHOW_DIALOG_RPC)
        """
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                if event[0] == 'disconnect':
                    return
                if event[0] == 'rpc':
                    rid, data = event[1], event[2]
                    if rpc_id is None or rid == rpc_id:
                        yield rid, data
        finally:
            self._subscribers.remove(q)

    async def events(self):
        """Async generator that yields every event as a tuple:

        - ``('connect',)``
        - ``('disconnect',)``
        - ``('rpc', rpc_id, data)``
        - ``('player_join', player_id, name)``

        Stops after yielding ``('disconnect',)``.
        """
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield event
                if event[0] == 'disconnect':
                    return
        finally:
            self._subscribers.remove(q)

    async def wait_for_rpc(self, rpc_id: int) -> bytes:
        """Await the next RPC with the given ID and return its payload bytes."""
        async for _, data in self.rpcs(rpc_id=rpc_id):
            return data

    # ── Game actions ───────────────────────────────────────────────────────────
    # These are synchronous — sending a UDP packet is fast, no executor needed.

    def send_rpc(self, rpc_id: int, data: bytes = b"",
                 reliability: int = RELIABLE) -> bool:
        return self._client.send_rpc(rpc_id, data, reliability)

    def send_chat(self, message: str) -> None:
        """Send a public chat message (RPC 101)."""
        msg = message.encode("ascii", errors="replace")[:144]
        self.send_rpc(RPC_CHAT, struct.pack("B", len(msg)) + msg)

    # ── State ──────────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    @property
    def player_id(self) -> int:
        return self._client.player_id


# Backwards-compatibility alias
SAMPClient = SAMPBot
