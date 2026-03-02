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

        @bot.on_dialog
        async def handle_dialog(dlg: pyraksamp.Dialog):
            # Sequential: await anything while events still fire
            await bot.send_dialog_response(dlg.dialog_id, button=1)

        if not await bot.start():
            return

        async for event in bot.events():
            pass  # keep running until disconnected

    asyncio.run(main())
"""

import asyncio
import random
import struct
import threading

from pyraksamp._core import SAMPClient as _SAMPClient
from pyraksamp import _core
from pyraksamp.events import (
    ChatMessage, ServerMessage, Dialog, GameText,
    PlayerJoin, PlayerQuit, PlayerStreamIn, PlayerStreamOut,
    SetHealth, SetArmour, SetPosition, Checkpoint,
)

__all__ = ["SAMPBot", "gen_gpci",
           "ChatMessage", "ServerMessage", "Dialog", "GameText",
           "PlayerJoin", "PlayerQuit", "PlayerStreamIn", "PlayerStreamOut",
           "SetHealth", "SetArmour", "SetPosition", "Checkpoint"]

# ── Re-export reliability constants ───────────────────────────────────────────
UNRELIABLE           = _core.UNRELIABLE
UNRELIABLE_SEQUENCED = _core.UNRELIABLE_SEQUENCED
RELIABLE             = _core.RELIABLE
RELIABLE_ORDERED     = _core.RELIABLE_ORDERED
RELIABLE_SEQUENCED   = _core.RELIABLE_SEQUENCED

# ── Re-export RPC ID constants ─────────────────────────────────────────────────
# server→client
RPC_SERVER_JOIN         = _core.RPC_SERVER_JOIN
RPC_SERVER_QUIT         = _core.RPC_SERVER_QUIT
RPC_INIT_GAME           = _core.RPC_INIT_GAME
RPC_CHAT                = _core.RPC_CHAT
RPC_CLIENT_MESSAGE      = _core.RPC_CLIENT_MESSAGE
RPC_DIALOG_BOX          = _core.RPC_DIALOG_BOX
RPC_GAME_TEXT           = _core.RPC_GAME_TEXT
RPC_SET_HEALTH          = _core.RPC_SET_HEALTH
RPC_SET_ARMOUR          = _core.RPC_SET_ARMOUR
RPC_SET_POSITION        = _core.RPC_SET_POSITION
RPC_SET_CHECKPOINT      = _core.RPC_SET_CHECKPOINT
RPC_DISABLE_CHECKPOINT  = _core.RPC_DISABLE_CHECKPOINT
RPC_WORLD_PLAYER_ADD    = _core.RPC_WORLD_PLAYER_ADD
RPC_WORLD_PLAYER_REMOVE = _core.RPC_WORLD_PLAYER_REMOVE
RPC_CONNECTION_REJ      = _core.RPC_CONNECTION_REJ
# client→server
RPC_CLIENT_JOIN         = _core.RPC_CLIENT_JOIN
RPC_REQUEST_CLASS       = _core.RPC_REQUEST_CLASS
RPC_REQUEST_SPAWN       = _core.RPC_REQUEST_SPAWN
RPC_SPAWN               = _core.RPC_SPAWN
RPC_DIALOG_RESPONSE     = _core.RPC_DIALOG_RESPONSE
RPC_DEATH               = _core.RPC_DEATH
RPC_ENTER_VEHICLE       = _core.RPC_ENTER_VEHICLE
RPC_EXIT_VEHICLE        = _core.RPC_EXIT_VEHICLE


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

    Sending (send_rpc, send_chat, send_dialog_response, …) is synchronous and
    safe to call from async code — no await needed, no executor overhead.
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
        # Connection
        self._cb_connect:    object = None
        self._cb_disconnect: object = None
        # Raw
        self._cb_rpc:        object = None
        # Player roster
        self._cb_player_join:         object = None
        self._cb_player_quit:         object = None
        # Chat
        self._cb_chat:                object = None
        self._cb_client_message:      object = None
        # Dialogs
        self._cb_dialog:              object = None
        # HUD
        self._cb_game_text:           object = None
        # Player state
        self._cb_set_health:          object = None
        self._cb_set_armour:          object = None
        self._cb_set_position:        object = None
        # World
        self._cb_checkpoint:          object = None
        self._cb_checkpoint_disabled: object = None
        # Proximity
        self._cb_player_streamed_in:  object = None
        self._cb_player_streamed_out: object = None

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
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('rpc', rpc_id, data)),
                self._fire(self._cb_rpc, rpc_id, data),
            ))

        def on_player_join(pid: int, name: str):
            evt = PlayerJoin(player_id=pid, name=name)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('player_join', evt)),
                self._fire(self._cb_player_join, evt),
            ))

        def on_player_quit(pid: int, reason: int):
            evt = PlayerQuit(player_id=pid, reason=reason)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('player_quit', evt)),
                self._fire(self._cb_player_quit, evt),
            ))

        def on_chat(pid: int, text: str):
            evt = ChatMessage(player_id=pid, text=text)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('chat', evt)),
                self._fire(self._cb_chat, evt),
            ))

        def on_client_message(color: int, text: str):
            evt = ServerMessage(color=color, text=text)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('client_message', evt)),
                self._fire(self._cb_client_message, evt),
            ))

        def on_dialog(did: int, style: int, title: str, btn1: str, btn2: str, body: str):
            evt = Dialog(dialog_id=did, style=style, title=title,
                         button1=btn1, button2=btn2, body=body)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('dialog', evt)),
                self._fire(self._cb_dialog, evt),
            ))

        def on_game_text(style: int, ms: int, text: str):
            evt = GameText(style=style, duration_ms=ms, text=text)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('game_text', evt)),
                self._fire(self._cb_game_text, evt),
            ))

        def on_set_health(hp: float):
            evt = SetHealth(health=hp)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('set_health', evt)),
                self._fire(self._cb_set_health, evt),
            ))

        def on_set_armour(arm: float):
            evt = SetArmour(armour=arm)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('set_armour', evt)),
                self._fire(self._cb_set_armour, evt),
            ))

        def on_set_position(x: float, y: float, z: float):
            evt = SetPosition(x=x, y=y, z=z)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('set_position', evt)),
                self._fire(self._cb_set_position, evt),
            ))

        def on_checkpoint(x: float, y: float, z: float, size: float):
            evt = Checkpoint(x=x, y=y, z=z, size=size)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('checkpoint', evt)),
                self._fire(self._cb_checkpoint, evt),
            ))

        def on_checkpoint_disabled():
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('checkpoint_disabled',)),
                self._fire(self._cb_checkpoint_disabled),
            ))

        def on_player_streamed_in(pid: int, team: int, skin: int,
                                   x: float, y: float, z: float, rot: float,
                                   color: int, fs: int):
            evt = PlayerStreamIn(player_id=pid, team=team, skin=skin,
                                 x=x, y=y, z=z, rotation=rot,
                                 color=color, fight_style=fs)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('player_streamed_in', evt)),
                self._fire(self._cb_player_streamed_in, evt),
            ))

        def on_player_streamed_out(pid: int):
            evt = PlayerStreamOut(player_id=pid)
            loop.call_soon_threadsafe(lambda: (
                self._broadcast(('player_streamed_out', evt)),
                self._fire(self._cb_player_streamed_out, evt),
            ))

        self._client.on_connect              = on_connect
        self._client.on_disconnect           = on_disconnect
        self._client.on_rpc                  = on_rpc
        self._client.on_player_join          = on_player_join
        self._client.on_player_quit          = on_player_quit
        self._client.on_chat                 = on_chat
        self._client.on_client_message       = on_client_message
        self._client.on_dialog               = on_dialog
        self._client.on_game_text            = on_game_text
        self._client.on_set_health           = on_set_health
        self._client.on_set_armour           = on_set_armour
        self._client.on_set_position         = on_set_position
        self._client.on_checkpoint           = on_checkpoint
        self._client.on_checkpoint_disabled  = on_checkpoint_disabled
        self._client.on_player_streamed_in   = on_player_streamed_in
        self._client.on_player_streamed_out  = on_player_streamed_out

    # ── Decorator-style callbacks ──────────────────────────────────────────────
    # Each decorator accepts both plain functions and async def coroutines.
    # Typed callbacks receive the corresponding dataclass instance as first arg.

    def on_connect(self, fn):
        """Decorator: called (no args) when fully connected."""
        self._cb_connect = fn; return fn

    def on_disconnect(self, fn):
        """Decorator: called (no args) on disconnection."""
        self._cb_disconnect = fn; return fn

    def on_rpc(self, fn):
        """Decorator: fn(rpc_id: int, data: bytes) for every incoming RPC (raw)."""
        self._cb_rpc = fn; return fn

    def on_player_join(self, fn):
        """Decorator: fn(event: PlayerJoin) when a player connects."""
        self._cb_player_join = fn; return fn

    def on_player_quit(self, fn):
        """Decorator: fn(event: PlayerQuit) when a player disconnects."""
        self._cb_player_quit = fn; return fn

    def on_chat(self, fn):
        """Decorator: fn(event: ChatMessage) for public chat."""
        self._cb_chat = fn; return fn

    def on_client_message(self, fn):
        """Decorator: fn(event: ServerMessage) for server messages."""
        self._cb_client_message = fn; return fn

    def on_dialog(self, fn):
        """Decorator: fn(event: Dialog) when a dialog is shown."""
        self._cb_dialog = fn; return fn

    def on_game_text(self, fn):
        """Decorator: fn(event: GameText) for ShowGameText."""
        self._cb_game_text = fn; return fn

    def on_set_health(self, fn):
        """Decorator: fn(event: SetHealth)."""
        self._cb_set_health = fn; return fn

    def on_set_armour(self, fn):
        """Decorator: fn(event: SetArmour)."""
        self._cb_set_armour = fn; return fn

    def on_set_position(self, fn):
        """Decorator: fn(event: SetPosition)."""
        self._cb_set_position = fn; return fn

    def on_checkpoint(self, fn):
        """Decorator: fn(event: Checkpoint)."""
        self._cb_checkpoint = fn; return fn

    def on_checkpoint_disabled(self, fn):
        """Decorator: fn() when the checkpoint is disabled."""
        self._cb_checkpoint_disabled = fn; return fn

    def on_player_streamed_in(self, fn):
        """Decorator: fn(event: PlayerStreamIn)."""
        self._cb_player_streamed_in = fn; return fn

    def on_player_streamed_out(self, fn):
        """Decorator: fn(event: PlayerStreamOut)."""
        self._cb_player_streamed_out = fn; return fn

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
            target=self._client.run, daemon=True,
            name=f"samp-recv-{self._client.player_id}")
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

    # ── Generic event streams ──────────────────────────────────────────────────

    async def rpcs(self, rpc_id: int | None = None):
        """Async generator yielding (rpc_id, data: bytes) for raw RPCs.

        Each call creates an independent subscriber — multiple concurrent
        consumers each see every event independently (fan-out, no stealing).

        Args:
            rpc_id: If given, yield only RPCs matching this ID.
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
        """Async generator that yields every event as a tuple.

        Event tags and payloads:

        - ``('connect',)``
        - ``('disconnect',)``
        - ``('rpc', rpc_id, data)``                  raw bytes escape hatch
        - ``('player_join', PlayerJoin)``
        - ``('player_quit', PlayerQuit)``
        - ``('chat', ChatMessage)``
        - ``('client_message', ServerMessage)``
        - ``('dialog', Dialog)``
        - ``('game_text', GameText)``
        - ``('set_health', SetHealth)``
        - ``('set_armour', SetArmour)``
        - ``('set_position', SetPosition)``
        - ``('checkpoint', Checkpoint)``
        - ``('checkpoint_disabled',)``
        - ``('player_streamed_in', PlayerStreamIn)``
        - ``('player_streamed_out', PlayerStreamOut)``

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

    # ── Typed async generators ─────────────────────────────────────────────────

    async def _typed_gen(self, tag: str):
        """Yield the payload object for events matching *tag*."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                if event[0] == 'disconnect':
                    return
                if event[0] == tag:
                    yield event[1]
        finally:
            self._subscribers.remove(q)

    def chat(self):
        """Async generator yielding ChatMessage for each public chat message."""
        return self._typed_gen('chat')

    def server_messages(self):
        """Async generator yielding ServerMessage for each client message."""
        return self._typed_gen('client_message')

    def dialogs(self):
        """Async generator yielding Dialog each time a dialog is shown."""
        return self._typed_gen('dialog')

    def game_texts(self):
        """Async generator yielding GameText for each ShowGameText."""
        return self._typed_gen('game_text')

    def player_joins(self):
        """Async generator yielding PlayerJoin for each connecting player."""
        return self._typed_gen('player_join')

    def player_quits(self):
        """Async generator yielding PlayerQuit for each disconnecting player."""
        return self._typed_gen('player_quit')

    def player_stream_ins(self):
        """Async generator yielding PlayerStreamIn."""
        return self._typed_gen('player_streamed_in')

    def player_stream_outs(self):
        """Async generator yielding PlayerStreamOut."""
        return self._typed_gen('player_streamed_out')

    async def wait_for_rpc(self, rpc_id: int) -> bytes:
        """Await the next raw RPC with the given ID and return its payload bytes."""
        async for _, data in self.rpcs(rpc_id=rpc_id):
            return data

    async def wait_for_dialog(self) -> Dialog:
        """Await the next dialog and return it."""
        async for dlg in self.dialogs():
            return dlg

    # ── Game actions ───────────────────────────────────────────────────────────
    # Sending a UDP packet is fast — no executor or await needed.

    def send_rpc(self, rpc_id: int, data: bytes = b"",
                 reliability: int = RELIABLE) -> bool:
        return self._client.send_rpc(rpc_id, data, reliability)

    def send_chat(self, message: str) -> None:
        """Send a public chat message (RPC 101)."""
        msg = message.encode("ascii", errors="replace")[:144]
        self.send_rpc(RPC_CHAT, struct.pack("B", len(msg)) + msg)

    def send_dialog_response(self, dialog_id: int, button: int,
                              list_item: int = 0, text: str = "") -> None:
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

    # ── State ──────────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    @property
    def player_id(self) -> int:
        return self._client.player_id


# Backwards-compatibility alias
SAMPClient = SAMPBot
