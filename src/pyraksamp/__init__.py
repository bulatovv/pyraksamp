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

        @bot.on_dialog()
        async def handle_dialog(dlg: pyraksamp.AnyDialog):
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
from collections.abc import Callable
from typing import Any, overload

from pyraksamp._core import SAMPClient as _SAMPClient
from pyraksamp import _core
from pyraksamp._bus import _EventBus
from pyraksamp._bridge import _setup_bridge
from pyraksamp._dispatcher import _Dispatcher
from pyraksamp._listener import _StreamListener, _CallbackListener
from pyraksamp._actions import _Actions
from pyraksamp._utils import _make_obj_filter
from pyraksamp.dialogs import (
    AnyDialog,
    MsgboxDialog,
    InputDialog,
    PasswordDialog,
    ListDialog,
    TablistDialog,
    TablistHeadersDialog,
    Button,
    ButtonSelector,
    ListRow,
    TablistRow,
    RowSelector,
    DialogAlreadyRespondedError,
    _Responder as _DialogResponder,
    _make_dialog,
)
from pyraksamp.events import (
    ChatMessage,
    ServerMessage,
    GameText,
    PlayerJoin,
    PlayerQuit,
    PlayerStreamIn,
    PlayerStreamOut,
    SetHealth,
    SetArmour,
    SetPosition,
    Checkpoint,
    PlayerNameChange,
    ToggleControllable,
    PlayerTime,
    DeathMessage,
    SetArmedWeapon,
    SpawnInfo,
    PlayerTeam,
    PutInVehicle,
    PlayerColor,
    WorldTime,
    ToggleSpectating,
    WantedLevel,
    WeaponAmmo,
    Gravity,
    Weather,
    PlayerSkin,
    SetInterior,
    VehicleStreamIn,
    VehicleStreamOut,
    PlayerDeath,
)

__all__ = [
    # Client
    "SAMPBot",
    "SAMPClient",  # backwards-compatibility alias
    "gen_gpci",
    # Reliability constants (used with send_rpc)
    "UNRELIABLE",
    "UNRELIABLE_SEQUENCED",
    "RELIABLE",
    "RELIABLE_ORDERED",
    "RELIABLE_SEQUENCED",
    # RPC ID constants – server→client
    "RPC_SERVER_JOIN",
    "RPC_SERVER_QUIT",
    "RPC_INIT_GAME",
    "RPC_CHAT",
    "RPC_CLIENT_MESSAGE",
    "RPC_DIALOG_BOX",
    "RPC_GAME_TEXT",
    "RPC_SET_HEALTH",
    "RPC_SET_ARMOUR",
    "RPC_SET_POSITION",
    "RPC_SET_CHECKPOINT",
    "RPC_DISABLE_CHECKPOINT",
    "RPC_WORLD_PLAYER_ADD",
    "RPC_WORLD_PLAYER_REMOVE",
    "RPC_CONNECTION_REJ",
    "RPC_SET_PLAYER_NAME",
    "RPC_TOGGLE_CONTROLLABLE",
    "RPC_SET_PLAYER_TIME",
    "RPC_SEND_DEATH_MESSAGE",
    "RPC_SET_ARMED_WEAPON",
    "RPC_SET_SPAWN_INFO",
    "RPC_SET_PLAYER_TEAM",
    "RPC_PUT_IN_VEHICLE",
    "RPC_REMOVE_FROM_VEHICLE",
    "RPC_SET_PLAYER_COLOR",
    "RPC_SET_WORLD_TIME",
    "RPC_TOGGLE_SPECTATING",
    "RPC_SET_WANTED_LEVEL",
    "RPC_SET_WEAPON_AMMO",
    "RPC_SET_GRAVITY",
    "RPC_SET_WEATHER",
    "RPC_SET_PLAYER_SKIN",
    "RPC_SET_INTERIOR",
    "RPC_WORLD_VEHICLE_ADD",
    "RPC_WORLD_VEHICLE_REMOVE",
    "RPC_DEATH_BROADCAST",
    # RPC ID constants – client→server
    "RPC_CLIENT_JOIN",
    "RPC_REQUEST_CLASS",
    "RPC_REQUEST_SPAWN",
    "RPC_SPAWN",
    "RPC_DIALOG_RESPONSE",
    "RPC_DEATH",
    "RPC_ENTER_VEHICLE",
    "RPC_EXIT_VEHICLE",
    "RPC_SERVER_COMMAND",
    # Dialog types
    "AnyDialog",
    "MsgboxDialog",
    "InputDialog",
    "PasswordDialog",
    "ListDialog",
    "TablistDialog",
    "TablistHeadersDialog",
    # Dialog errors
    "DialogAlreadyRespondedError",
    # Dialog helpers
    "Button",
    "ButtonSelector",
    "ListRow",
    "TablistRow",
    "RowSelector",
    # Event types
    "ChatMessage",
    "ServerMessage",
    "GameText",
    "PlayerJoin",
    "PlayerQuit",
    "PlayerStreamIn",
    "PlayerStreamOut",
    "SetHealth",
    "SetArmour",
    "SetPosition",
    "Checkpoint",
    "PlayerNameChange",
    "ToggleControllable",
    "PlayerTime",
    "DeathMessage",
    "SetArmedWeapon",
    "SpawnInfo",
    "PlayerTeam",
    "PutInVehicle",
    "PlayerColor",
    "WorldTime",
    "ToggleSpectating",
    "WantedLevel",
    "WeaponAmmo",
    "Gravity",
    "Weather",
    "PlayerSkin",
    "SetInterior",
    "VehicleStreamIn",
    "VehicleStreamOut",
    "PlayerDeath",
]

# ── Re-export reliability constants ───────────────────────────────────────────
UNRELIABLE = _core.UNRELIABLE
UNRELIABLE_SEQUENCED = _core.UNRELIABLE_SEQUENCED
RELIABLE = _core.RELIABLE
RELIABLE_ORDERED = _core.RELIABLE_ORDERED
RELIABLE_SEQUENCED = _core.RELIABLE_SEQUENCED

# ── Re-export RPC ID constants ─────────────────────────────────────────────────
# server→client
RPC_SERVER_JOIN = _core.RPC_SERVER_JOIN
RPC_SERVER_QUIT = _core.RPC_SERVER_QUIT
RPC_INIT_GAME = _core.RPC_INIT_GAME
RPC_CHAT = _core.RPC_CHAT
RPC_CLIENT_MESSAGE = _core.RPC_CLIENT_MESSAGE
RPC_DIALOG_BOX = _core.RPC_DIALOG_BOX
RPC_GAME_TEXT = _core.RPC_GAME_TEXT
RPC_SET_HEALTH = _core.RPC_SET_HEALTH
RPC_SET_ARMOUR = _core.RPC_SET_ARMOUR
RPC_SET_POSITION = _core.RPC_SET_POSITION
RPC_SET_CHECKPOINT = _core.RPC_SET_CHECKPOINT
RPC_DISABLE_CHECKPOINT = _core.RPC_DISABLE_CHECKPOINT
RPC_WORLD_PLAYER_ADD = _core.RPC_WORLD_PLAYER_ADD
RPC_WORLD_PLAYER_REMOVE = _core.RPC_WORLD_PLAYER_REMOVE
RPC_CONNECTION_REJ = _core.RPC_CONNECTION_REJ
# client→server
RPC_CLIENT_JOIN = _core.RPC_CLIENT_JOIN
RPC_REQUEST_CLASS = _core.RPC_REQUEST_CLASS
RPC_REQUEST_SPAWN = _core.RPC_REQUEST_SPAWN
RPC_SPAWN = _core.RPC_SPAWN
RPC_DIALOG_RESPONSE = _core.RPC_DIALOG_RESPONSE
RPC_DEATH = _core.RPC_DEATH
RPC_ENTER_VEHICLE = _core.RPC_ENTER_VEHICLE
RPC_EXIT_VEHICLE = _core.RPC_EXIT_VEHICLE
RPC_SERVER_COMMAND = _core.RPC_SERVER_COMMAND
# new server→client
RPC_SET_PLAYER_NAME = _core.RPC_SET_PLAYER_NAME
RPC_TOGGLE_CONTROLLABLE = _core.RPC_TOGGLE_CONTROLLABLE
RPC_SET_PLAYER_TIME = _core.RPC_SET_PLAYER_TIME
RPC_SEND_DEATH_MESSAGE = _core.RPC_SEND_DEATH_MESSAGE
RPC_SET_ARMED_WEAPON = _core.RPC_SET_ARMED_WEAPON
RPC_SET_SPAWN_INFO = _core.RPC_SET_SPAWN_INFO
RPC_SET_PLAYER_TEAM = _core.RPC_SET_PLAYER_TEAM
RPC_PUT_IN_VEHICLE = _core.RPC_PUT_IN_VEHICLE
RPC_REMOVE_FROM_VEHICLE = _core.RPC_REMOVE_FROM_VEHICLE
RPC_SET_PLAYER_COLOR = _core.RPC_SET_PLAYER_COLOR
RPC_SET_WORLD_TIME = _core.RPC_SET_WORLD_TIME
RPC_TOGGLE_SPECTATING = _core.RPC_TOGGLE_SPECTATING
RPC_SET_WANTED_LEVEL = _core.RPC_SET_WANTED_LEVEL
RPC_SET_WEAPON_AMMO = _core.RPC_SET_WEAPON_AMMO
RPC_SET_GRAVITY = _core.RPC_SET_GRAVITY
RPC_SET_WEATHER = _core.RPC_SET_WEATHER
RPC_SET_PLAYER_SKIN = _core.RPC_SET_PLAYER_SKIN
RPC_SET_INTERIOR = _core.RPC_SET_INTERIOR
RPC_WORLD_VEHICLE_ADD = _core.RPC_WORLD_VEHICLE_ADD
RPC_WORLD_VEHICLE_REMOVE = _core.RPC_WORLD_VEHICLE_REMOVE
RPC_DEATH_BROADCAST = _core.RPC_DEATH_BROADCAST


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


# ── No-arg extract for events that carry no payload ───────────────────────────
_NO_ARG = lambda e: ()  # noqa: E731


class SAMPBot:
    """Async SA:MP 0.3.7 headless client.

    Internally runs one daemon thread per bot (the Rust receive/keepalive loop).
    All user-facing callbacks and event streams run in the asyncio event loop —
    no thread management required from user code.

    Sending (send_rpc, send_chat, send_dialog_response, …) is synchronous and
    safe to call from async code — no await needed, no executor overhead.

    Parameters
    ----------
    host
        Server hostname or IP address.
    port
        UDP port the server listens on.
    nickname
        In-game name shown to other players (max 20 characters).
    password
        Server password; leave empty for password-free servers.
    gpci
        Hardware key string (GTA serial). A valid random key is generated if
        omitted; supply a fixed value to maintain a persistent identity.

    See Also
    --------
    gen_gpci : Generate a random valid GPCI string.
    """

    def __init__(
        self,
        host: str,
        port: int = 7777,
        nickname: str = "PyBot",
        password: str = "",
        gpci: str = "",
    ):
        if not gpci:
            gpci = gen_gpci()
        self._client = _SAMPClient(host, port, nickname, password, gpci)
        self._bus = _EventBus()
        self._dispatcher = _Dispatcher(self._bus)
        self._actions = _Actions(self._client)
        self._make_dialog = lambda did, style, title, btn1, btn2, body: _make_dialog(
            did,
            style,
            title,
            btn1,
            btn2,
            body,
            _DialogResponder(self._actions.send_dialog_response),
        )
        self._listeners: list[_CallbackListener] = []
        self._started: bool = False

    def _register_listener(self, listener: _CallbackListener) -> None:
        self._listeners.append(listener)
        if self._started:
            listener.start()

    # ── Connection lifecycle ───────────────────────────────────────────────────

    async def start(self, timeout: float = 15.0) -> bool:
        """Connect and start the background receive/keepalive thread.

        Parameters
        ----------
        timeout
            Maximum seconds to wait for the connection to be accepted.

        Returns
        -------
            ``True`` if connected, ``False`` on timeout or rejection.
        """
        loop = asyncio.get_running_loop()
        _setup_bridge(self._client, self._bus, self._make_dialog, loop)
        self._dispatcher.start()
        self._started = True
        for listener in self._listeners:
            listener.start()
        return await loop.run_in_executor(None, lambda: self._client.start(timeout))

    def disconnect(self) -> None:
        """Send disconnect notification and stop the receive loop."""
        self._client.disconnect()

    def stop(self) -> None:
        """Signal the receive loop to stop without sending a disconnect packet."""
        self._client.stop()

    # ── State ──────────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        """True if the client is currently connected to the server."""
        return self._client.is_connected

    @property
    def player_id(self) -> int:
        """The bot's player ID assigned by the server, or -1 before connect."""
        return self._client.player_id

    # ── Decorator listeners ────────────────────────────────────────────────────

    def on_connect[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the client connects."""
        self._register_listener(
            _CallbackListener(self._dispatcher, "connect", fn, extract=_NO_ARG)
        )
        return fn

    def on_disconnect[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the client disconnects."""
        self._register_listener(
            _CallbackListener(self._dispatcher, "disconnect", fn, extract=_NO_ARG)
        )
        return fn

    def on_rpc[F: Callable](
        self,
        fn: F | None = None,
        *,
        rpc_id: int | None = None,
        predicate: Callable[[int, bytes], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Register a callback invoked for every incoming RPC.

        Parameters
        ----------
        rpc_id
            If given, only invoke for RPCs with this ID.
        predicate
            Additional filter; called with ``(rpc_id, data)``.
        """

        def decorator(f: F) -> F:
            def filt(rid: int, data: bytes) -> bool:
                if rpc_id is not None and rid != rpc_id:
                    return False
                if predicate is not None and not predicate(rid, data):
                    return False
                return True

            self._register_listener(
                _CallbackListener(
                    self._dispatcher,
                    "rpc",
                    f,
                    predicate=filt
                    if (rpc_id is not None or predicate is not None)
                    else None,
                    extract=lambda e: (e[1], e[2]),
                )
            )
            return f

        return decorator(fn) if fn is not None else decorator

    def on_player_join[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        name: str | None = None,
        predicate: Callable[[PlayerJoin], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Register a callback invoked when a player joins."""

        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {"player_id": player_id, "name": name})
            self._register_listener(
                _CallbackListener(self._dispatcher, "player_join", f, filt)
            )
            return f

        return decorator(fn) if fn is not None else decorator

    def on_player_quit[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        predicate: Callable[[PlayerQuit], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Register a callback invoked when a player disconnects."""

        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {"player_id": player_id})
            self._register_listener(
                _CallbackListener(self._dispatcher, "player_quit", f, filt)
            )
            return f

        return decorator(fn) if fn is not None else decorator

    def on_chat[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        predicate: Callable[[ChatMessage], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Register a callback invoked for each public chat message."""

        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {"player_id": player_id})
            self._register_listener(
                _CallbackListener(self._dispatcher, "chat", f, filt)
            )
            return f

        return decorator(fn) if fn is not None else decorator

    def on_client_message[F: Callable](
        self,
        fn: F | None = None,
        *,
        color: int | None = None,
        predicate: Callable[[ServerMessage], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Register a callback invoked for each server message."""

        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {"color": color})
            self._register_listener(
                _CallbackListener(self._dispatcher, "client_message", f, filt)
            )
            return f

        return decorator(fn) if fn is not None else decorator

    @overload
    def on_dialog(
        self,
        fn: Callable[[AnyDialog], Any],
    ) -> Callable[[AnyDialog], Any]: ...

    @overload
    def on_dialog[
        D: (
            MsgboxDialog,
            InputDialog,
            PasswordDialog,
            ListDialog,
            TablistDialog,
            TablistHeadersDialog,
        )
    ](
        self,
        fn: None = ...,
        *,
        dialog_type: type[D] | None = ...,
        predicate: Callable[[D], bool] | None = ...,
        dialog_id: int | None = ...,
    ) -> Callable[[Callable[[D], Any]], Callable[[D], Any]]: ...

    def on_dialog[
        D: (
            MsgboxDialog,
            InputDialog,
            PasswordDialog,
            ListDialog,
            TablistDialog,
            TablistHeadersDialog,
        )
    ](
        self,
        fn: Callable[[Any], Any] | None = None,
        *,
        dialog_type: type[D] | None = None,
        predicate: Callable[[D], bool] | None = None,
        dialog_id: int | None = None,
    ) -> Callable[[Any], Any]:
        """Register a callback invoked when a dialog is shown."""

        def decorator(f: Callable[[Any], Any]) -> Callable[[Any], Any]:
            filt = _make_obj_filter(
                predicate, {"dialog_id": dialog_id}, instance_of=dialog_type
            )
            self._register_listener(
                _CallbackListener(self._dispatcher, "dialog", f, filt)
            )
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    def on_game_text[F: Callable](
        self,
        fn: F | None = None,
        *,
        style: int | None = None,
        predicate: Callable[[GameText], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Register a callback invoked for ShowGameText."""

        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {"style": style})
            self._register_listener(
                _CallbackListener(self._dispatcher, "game_text", f, filt)
            )
            return f

        return decorator(fn) if fn is not None else decorator

    def on_set_health[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "set_health", fn))
        return fn

    def on_set_armour[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "set_armour", fn))
        return fn

    def on_set_position[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "set_position", fn))
        return fn

    def on_checkpoint[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "checkpoint", fn))
        return fn

    def on_checkpoint_disabled[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(
                self._dispatcher, "checkpoint_disabled", fn, extract=_NO_ARG
            )
        )
        return fn

    def on_player_streamed_in[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "player_streamed_in", fn)
        )
        return fn

    def on_player_streamed_out[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "player_streamed_out", fn)
        )
        return fn

    def on_player_name[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "player_name", fn))
        return fn

    def on_toggle_controllable[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "toggle_controllable", fn)
        )
        return fn

    def on_player_time[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "player_time", fn))
        return fn

    def on_death_message[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "death_message", fn)
        )
        return fn

    def on_set_armed_weapon[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "set_armed_weapon", fn)
        )
        return fn

    def on_spawn_info[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "spawn_info", fn))
        return fn

    def on_player_team[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "player_team", fn))
        return fn

    def on_put_in_vehicle[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "put_in_vehicle", fn)
        )
        return fn

    def on_remove_from_vehicle[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(
                self._dispatcher, "remove_from_vehicle", fn, extract=_NO_ARG
            )
        )
        return fn

    def on_player_color[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "player_color", fn))
        return fn

    def on_world_time[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "world_time", fn))
        return fn

    def on_toggle_spectating[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "toggle_spectating", fn)
        )
        return fn

    def on_wanted_level[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "wanted_level", fn))
        return fn

    def on_weapon_ammo[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "weapon_ammo", fn))
        return fn

    def on_gravity[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "gravity", fn))
        return fn

    def on_weather[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "weather", fn))
        return fn

    def on_player_skin[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "player_skin", fn))
        return fn

    def on_set_interior[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "set_interior", fn))
        return fn

    def on_vehicle_streamed_in[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "vehicle_streamed_in", fn)
        )
        return fn

    def on_vehicle_streamed_out[F: Callable](self, fn: F) -> F:
        self._register_listener(
            _CallbackListener(self._dispatcher, "vehicle_streamed_out", fn)
        )
        return fn

    def on_player_death[F: Callable](self, fn: F) -> F:
        self._register_listener(_CallbackListener(self._dispatcher, "player_death", fn))
        return fn

    # ── Async generators ───────────────────────────────────────────────────────

    async def rpcs(self, rpc_id: int | None = None):
        """Async generator yielding ``(rpc_id, data)`` for raw RPCs."""
        q: asyncio.Queue = asyncio.Queue()
        self._bus.subscribe(q)
        try:
            while True:
                event = await q.get()
                if event[0] == "disconnect":
                    return
                if event[0] == "rpc":
                    rid, data = event[1], event[2]
                    if rpc_id is None or rid == rpc_id:
                        yield rid, data
        finally:
            self._bus.unsubscribe(q)

    async def events(self):
        """Async generator yielding every event tuple; stops after disconnect."""
        q: asyncio.Queue = asyncio.Queue()
        self._bus.subscribe(q)
        try:
            while True:
                event = await q.get()
                yield event
                if event[0] == "disconnect":
                    return
        finally:
            self._bus.unsubscribe(q)

    def chat(self) -> _StreamListener:
        """Async generator yielding ChatMessage for each public chat message."""
        return _StreamListener(self._dispatcher, "chat")

    def server_messages(self) -> _StreamListener:
        """Async generator yielding ServerMessage for each client message."""
        return _StreamListener(self._dispatcher, "client_message")

    def dialogs(self) -> _StreamListener:
        """Async generator yielding AnyDialog each time a dialog is shown."""
        return _StreamListener(self._dispatcher, "dialog")

    def game_texts(self) -> _StreamListener:
        """Async generator yielding GameText for each ShowGameText."""
        return _StreamListener(self._dispatcher, "game_text")

    def player_joins(self) -> _StreamListener:
        """Async generator yielding PlayerJoin for each connecting player."""
        return _StreamListener(self._dispatcher, "player_join")

    def player_quits(self) -> _StreamListener:
        """Async generator yielding PlayerQuit for each disconnecting player."""
        return _StreamListener(self._dispatcher, "player_quit")

    def player_stream_ins(self) -> _StreamListener:
        """Async generator yielding PlayerStreamIn."""
        return _StreamListener(self._dispatcher, "player_streamed_in")

    def player_stream_outs(self) -> _StreamListener:
        """Async generator yielding PlayerStreamOut."""
        return _StreamListener(self._dispatcher, "player_streamed_out")

    def player_name_changes(self) -> _StreamListener:
        """Async generator yielding PlayerNameChange."""
        return _StreamListener(self._dispatcher, "player_name")

    def death_messages(self) -> _StreamListener:
        """Async generator yielding DeathMessage."""
        return _StreamListener(self._dispatcher, "death_message")

    def spawn_infos(self) -> _StreamListener:
        """Async generator yielding SpawnInfo."""
        return _StreamListener(self._dispatcher, "spawn_info")

    def put_in_vehicles(self) -> _StreamListener:
        """Async generator yielding PutInVehicle."""
        return _StreamListener(self._dispatcher, "put_in_vehicle")

    def player_colors(self) -> _StreamListener:
        """Async generator yielding PlayerColor."""
        return _StreamListener(self._dispatcher, "player_color")

    def weather_changes(self) -> _StreamListener:
        """Async generator yielding Weather."""
        return _StreamListener(self._dispatcher, "weather")

    def gravity_changes(self) -> _StreamListener:
        """Async generator yielding Gravity."""
        return _StreamListener(self._dispatcher, "gravity")

    def player_skins(self) -> _StreamListener:
        """Async generator yielding PlayerSkin."""
        return _StreamListener(self._dispatcher, "player_skin")

    def interior_changes(self) -> _StreamListener:
        """Async generator yielding SetInterior."""
        return _StreamListener(self._dispatcher, "set_interior")

    def vehicle_stream_ins(self) -> _StreamListener:
        """Async generator yielding VehicleStreamIn."""
        return _StreamListener(self._dispatcher, "vehicle_streamed_in")

    def vehicle_stream_outs(self) -> _StreamListener:
        """Async generator yielding VehicleStreamOut."""
        return _StreamListener(self._dispatcher, "vehicle_streamed_out")

    def player_deaths(self) -> _StreamListener:
        """Async generator yielding PlayerDeath."""
        return _StreamListener(self._dispatcher, "player_death")

    # ── Wait-for helpers ───────────────────────────────────────────────────────

    async def wait_for_rpc(
        self, rpc_id: int, *, predicate: Callable[[int, bytes], bool] | None = None
    ) -> bytes:
        """Await the next RPC with the given ID."""
        async for _, data in self.rpcs(rpc_id):
            if predicate is None or predicate(rpc_id, data):
                return data

    async def wait_for_dialog[
        D: (
            MsgboxDialog,
            InputDialog,
            PasswordDialog,
            ListDialog,
            TablistDialog,
            TablistHeadersDialog,
        )
    ](
        self,
        predicate: Callable[[D], bool] | None = None,
        *,
        dialog_type: type[D] | None = None,
        dialog_id: int | None = None,
    ) -> D:
        """Await the next dialog matching all given filters."""
        filt = _make_obj_filter(
            predicate, {"dialog_id": dialog_id}, instance_of=dialog_type
        )
        async for dlg in _StreamListener(self._dispatcher, "dialog", filt):
            return dlg  # type: ignore[return-value]

    async def wait_for_chat(
        self,
        predicate: Callable[[ChatMessage], bool] | None = None,
        *,
        player_id: int | None = None,
    ) -> ChatMessage:
        """Await the next public chat message matching all given filters."""
        filt = _make_obj_filter(predicate, {"player_id": player_id})
        async for msg in _StreamListener(self._dispatcher, "chat", filt):
            return msg

    async def wait_for_client_message(
        self,
        predicate: Callable[[ServerMessage], bool] | None = None,
        *,
        color: int | None = None,
    ) -> ServerMessage:
        """Await the next server message matching all given filters."""
        filt = _make_obj_filter(predicate, {"color": color})
        async for msg in _StreamListener(self._dispatcher, "client_message", filt):
            return msg

    async def wait_for_player_join(
        self,
        predicate: Callable[[PlayerJoin], bool] | None = None,
        *,
        player_id: int | None = None,
        name: str | None = None,
    ) -> PlayerJoin:
        """Await the next player join matching all given filters."""
        filt = _make_obj_filter(predicate, {"player_id": player_id, "name": name})
        async for evt in _StreamListener(self._dispatcher, "player_join", filt):
            return evt

    # ── Actions ────────────────────────────────────────────────────────────────

    def send_rpc(
        self, rpc_id: int, data: bytes = b"", reliability: int = RELIABLE
    ) -> bool:
        return self._actions.send_rpc(rpc_id, data, reliability)

    def send_chat(self, message: str) -> None:
        return self._actions.send_chat(message)

    def send_dialog_response(
        self, dialog_id: int, button: int, list_item: int = 0, text: str = ""
    ) -> None:
        return self._actions.send_dialog_response(dialog_id, button, list_item, text)

    def send_death(self, weapon_id: int = 0, killer_id: int = 0xFFFF) -> None:
        return self._actions.send_death(weapon_id, killer_id)

    def send_enter_vehicle(self, vehicle_id: int, is_passenger: bool = False) -> None:
        return self._actions.send_enter_vehicle(vehicle_id, is_passenger)

    def send_exit_vehicle(self, vehicle_id: int) -> None:
        return self._actions.send_exit_vehicle(vehicle_id)

    def send_command(self, text: str) -> None:
        return self._actions.send_command(text)


# Backwards-compatibility alias
SAMPClient = SAMPBot
