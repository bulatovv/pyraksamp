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

        await bot.start()
        await bot.run_until_disconnected()

    asyncio.run(main())
"""

import asyncio
import inspect
import random
from collections.abc import Callable
from enum import IntFlag
from typing import Any, overload

from pyraksamp import _core
from pyraksamp._actions import _Actions
from pyraksamp._bridge import _setup_bridge
from pyraksamp._bus import _EventBus
from pyraksamp._core import SAMPClient as _SAMPClient
from pyraksamp._dispatcher import _Dispatcher
from pyraksamp._listener import _CallbackListener, _StreamListener
from pyraksamp._utils import _make_obj_filter
from pyraksamp.dialogs import (
    AnyDialog,
    Button,
    ButtonSelector,
    DialogAlreadyRespondedError,
    InputDialog,
    ListDialog,
    ListRow,
    MsgboxDialog,
    PasswordDialog,
    RowSelector,
    TablistDialog,
    TablistHeadersDialog,
    TablistRow,
    _make_dialog,
)
from pyraksamp.dialogs import (
    _Responder as _DialogResponder,
)
from pyraksamp.events import (
    ChatMessage,
    Checkpoint,
    DeathMessage,
    GameText,
    Gravity,
    PlayerColor,
    PlayerDeath,
    PlayerJoin,
    PlayerNameChange,
    PlayerQuit,
    PlayerSkin,
    PlayerStreamIn,
    PlayerStreamOut,
    PlayerTeam,
    PlayerTime,
    PutInVehicle,
    ServerMessage,
    SetArmedWeapon,
    SetArmour,
    SetHealth,
    SetInterior,
    SetPosition,
    SpawnInfo,
    ToggleControllable,
    ToggleSpectating,
    VehicleStreamIn,
    VehicleStreamOut,
    WantedLevel,
    WeaponAmmo,
    Weather,
    WorldTime,
)
from pyraksamp.exceptions import (
    SAMPBanned,
    SAMPConnectionError,
    SAMPConnectionTimeout,
    SAMPHandshakeTimeout,
    SAMPHostResolutionError,
    SAMPInvalidPassword,
    SAMPProxyError,
    SAMPRejected,
    SAMPServerFull,
    SAMPSocketError,
)
from pyraksamp.textdraws import SelectableTextDraw, TextDraw, TextDraws

__all__ = [
    # Client
    'SAMPBot',
    'Router',
    # Key constants
    'Keys',
    # TextDraw types
    'TextDraw',
    'TextDraws',
    'SelectableTextDraw',
    'SAMPClient',  # backwards-compatibility alias
    'gen_gpci',
    # Reliability constants (used with send_rpc)
    'UNRELIABLE',
    'UNRELIABLE_SEQUENCED',
    'RELIABLE',
    'RELIABLE_ORDERED',
    'RELIABLE_SEQUENCED',
    # RPC ID constants – server→client
    'RPC_SERVER_JOIN',
    'RPC_SERVER_QUIT',
    'RPC_INIT_GAME',
    'RPC_CHAT',
    'RPC_CLIENT_MESSAGE',
    'RPC_DIALOG_BOX',
    'RPC_GAME_TEXT',
    'RPC_SET_HEALTH',
    'RPC_SET_ARMOUR',
    'RPC_SET_POSITION',
    'RPC_SET_CHECKPOINT',
    'RPC_DISABLE_CHECKPOINT',
    'RPC_WORLD_PLAYER_ADD',
    'RPC_WORLD_PLAYER_REMOVE',
    'RPC_CONNECTION_REJ',
    'RPC_SET_PLAYER_NAME',
    'RPC_TOGGLE_CONTROLLABLE',
    'RPC_SET_PLAYER_TIME',
    'RPC_SEND_DEATH_MESSAGE',
    'RPC_SET_ARMED_WEAPON',
    'RPC_SET_SPAWN_INFO',
    'RPC_SET_PLAYER_TEAM',
    'RPC_PUT_IN_VEHICLE',
    'RPC_REMOVE_FROM_VEHICLE',
    'RPC_SET_PLAYER_COLOR',
    'RPC_SET_WORLD_TIME',
    'RPC_TOGGLE_SPECTATING',
    'RPC_SET_WANTED_LEVEL',
    'RPC_SET_WEAPON_AMMO',
    'RPC_SET_GRAVITY',
    'RPC_SET_WEATHER',
    'RPC_SET_PLAYER_SKIN',
    'RPC_SET_INTERIOR',
    'RPC_WORLD_VEHICLE_ADD',
    'RPC_WORLD_VEHICLE_REMOVE',
    'RPC_DEATH_BROADCAST',
    # RPC ID constants – client→server
    'RPC_CLIENT_JOIN',
    'RPC_REQUEST_CLASS',
    'RPC_REQUEST_SPAWN',
    'RPC_SPAWN',
    'RPC_DIALOG_RESPONSE',
    'RPC_DEATH',
    'RPC_ENTER_VEHICLE',
    'RPC_EXIT_VEHICLE',
    'RPC_SERVER_COMMAND',
    # Dialog types
    'AnyDialog',
    'MsgboxDialog',
    'InputDialog',
    'PasswordDialog',
    'ListDialog',
    'TablistDialog',
    'TablistHeadersDialog',
    # Connection exceptions
    'SAMPConnectionError',
    'SAMPBanned',
    'SAMPInvalidPassword',
    'SAMPServerFull',
    'SAMPRejected',
    'SAMPHandshakeTimeout',
    'SAMPConnectionTimeout',
    'SAMPHostResolutionError',
    'SAMPProxyError',
    'SAMPSocketError',
    # Dialog errors
    'DialogAlreadyRespondedError',
    # Dialog helpers
    'Button',
    'ButtonSelector',
    'ListRow',
    'TablistRow',
    'RowSelector',
    # Event types
    'ChatMessage',
    'ServerMessage',
    'GameText',
    'PlayerJoin',
    'PlayerQuit',
    'PlayerStreamIn',
    'PlayerStreamOut',
    'SetHealth',
    'SetArmour',
    'SetPosition',
    'Checkpoint',
    'PlayerNameChange',
    'ToggleControllable',
    'PlayerTime',
    'DeathMessage',
    'SetArmedWeapon',
    'SpawnInfo',
    'PlayerTeam',
    'PutInVehicle',
    'PlayerColor',
    'WorldTime',
    'ToggleSpectating',
    'WantedLevel',
    'WeaponAmmo',
    'Gravity',
    'Weather',
    'PlayerSkin',
    'SetInterior',
    'VehicleStreamIn',
    'VehicleStreamOut',
    'PlayerDeath',
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


class Keys(IntFlag):
    """SA:MP key bitmask constants for use with :meth:`SAMPBot.send_keys`
    and :meth:`SAMPBot.press_keys`.

    These map to the ``wKeys`` field in on-foot sync packets.
    Some bits have different names depending on context (on foot vs. vehicle);
    members here use the on-foot name.  Vehicle-only aliases are listed in
    comments for when vehicle support is added.
    """

    # ── Shared (on foot & vehicle) ─────────────────────────────────────────────
    ACTION = 1  # TAB  / ALT GR
    CROUCH = 2  # C    / H
    FIRE = 4  # LCTRL / LALT
    SPRINT = 8  # SPACE / W
    SECONDARY_ATTACK = 16  # ENTER / ENTER
    JUMP = 32  # LSHIFT / S
    YES = 65536  # Y
    NO = 131072  # N
    CTRL_BACK = 262144  # H

    # ── On-foot only (same bit = different vehicle key, noted in comment) ───────
    LOOK_RIGHT = 64  # E           (veh: —)
    AIM = 128  # RMB         (veh: HANDBRAKE = 128)
    LOOK_LEFT = 256  # Q           (veh: —)
    SUBMISSION = 512  # NUM1        (veh: LOOK_BEHIND = 512)
    WALK = 1024  # LALT        (veh: —)
    ANALOG_UP = 2048  # NUM8
    ANALOG_DOWN = 4096  # NUM2
    ANALOG_LEFT = 8192  # NUM4
    ANALOG_RIGHT = 16384  # NUM6


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
        nickname: str = 'PyBot',
        password: str = '',
        gpci: str = '',
        server_encoding: str = 'utf-8',
        proxy: str | None = None,
    ):
        if not gpci:
            gpci = gen_gpci()
        proxy_host = proxy_port_int = proxy_username = proxy_password = None
        if proxy:
            from urllib.parse import urlparse

            _p = urlparse(proxy)
            proxy_host = _p.hostname
            proxy_port_int = _p.port
            proxy_username = _p.username or None
            proxy_password = _p.password or None
        self._client = _SAMPClient(
            host,
            port,
            nickname,
            password,
            gpci,
            proxy_host=proxy_host,
            proxy_port=proxy_port_int,
            proxy_username=proxy_username,
            proxy_password=proxy_password,
        )
        self._server_encoding = server_encoding
        self._bus = _EventBus()
        self._dispatcher = _Dispatcher(self._bus)
        self._actions = _Actions(self._client, server_encoding)
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
        self.textdraws = TextDraws(click_fn=self._actions.click_textdraw)

    def _register_listener(self, listener: _CallbackListener) -> None:
        self._listeners.append(listener)
        if self._started:
            listener.start()

    # ── Connection lifecycle ───────────────────────────────────────────────────

    async def start(self, timeout: float = 15.0) -> None:
        """Connect and start the background receive/keepalive thread.

        Parameters
        ----------
        timeout
            Maximum seconds to wait for the connection to be accepted.

        Raises
        ------
        SAMPBanned
            The client is banned from the server.
        SAMPInvalidPassword
            Wrong server password.
        SAMPServerFull
            Server has no free player slots.
        SAMPRejected
            Server actively refused the connection attempt.
        SAMPHandshakeTimeout
            Server did not complete the open-connection handshake in time.
        SAMPConnectionTimeout
            Server did not accept the connection request in time.
        SAMPHostResolutionError
            Server hostname could not be resolved.
        SAMPProxyError
            SOCKS5 proxy handshake failed.
        SAMPSocketError
            Could not bind the local UDP socket.
        """
        loop = asyncio.get_running_loop()
        _setup_bridge(self._client, self._bus, self._make_dialog, loop, self._server_encoding)
        self._dispatcher.start()
        # Feed textdraw events into the registry (must be registered before user listeners)
        for tag, fn in [
            ('textdraw_show', self.textdraws._on_show),
            ('textdraw_hide', self.textdraws._on_hide),
            ('textdraw_edit', self.textdraws._on_edit),
            ('textdraw_toggle_select', self.textdraws._on_toggle_select),
            ('disconnect', self.textdraws._on_disconnect),
        ]:
            self._register_listener(
                _CallbackListener(self._dispatcher, tag, fn, extract=lambda e: e[1:])
            )
        if not getattr(self, '_atexit_registered', False):
            import atexit

            atexit.register(self._client.stop)
            self._atexit_registered = True
        self._started = True
        for listener in self._listeners:
            listener.start()
        await loop.run_in_executor(None, lambda: self._client.start(timeout))

    def disconnect(self) -> None:
        """Send disconnect notification and stop the receive loop."""
        self._client.disconnect()

    def stop(self) -> None:
        """Signal the receive loop to stop without sending a disconnect packet."""
        self._client.stop()

    async def run_until_disconnected(self) -> None:
        """Block until the bot disconnects.

        Intended as the final line of a ``main`` coroutine after
        :meth:`start` and any sequential setup::

            await bot.start()
            # login flow, handler registration, …
            await bot.run_until_disconnected()
        """
        async for _ in self.events():
            pass

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
        self._register_handler('connect', fn, extract=_NO_ARG)
        return fn

    def on_disconnect[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the client disconnects."""
        self._register_handler('disconnect', fn, extract=_NO_ARG)
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
                return not (
                    (rpc_id is not None and rid != rpc_id)
                    or (predicate is not None and not predicate(rid, data))
                )

            self._register_handler(
                'rpc',
                f,
                predicate=filt if (rpc_id is not None or predicate is not None) else None,
                extract=lambda e: (e[1], e[2]),
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
            filt = _make_obj_filter(predicate, {'player_id': player_id, 'name': name})
            self._register_handler('player_join', f, filt)
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
            filt = _make_obj_filter(predicate, {'player_id': player_id})
            self._register_handler('player_quit', f, filt)
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
            filt = _make_obj_filter(predicate, {'player_id': player_id})
            self._register_handler('chat', f, filt)
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
            filt = _make_obj_filter(predicate, {'color': color})
            self._register_handler('client_message', f, filt)
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
                predicate, {'dialog_id': dialog_id}, instance_of=dialog_type
            )
            self._register_handler('dialog', f, filt)
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
            filt = _make_obj_filter(predicate, {'style': style})
            self._register_handler('game_text', f, filt)
            return f

        return decorator(fn) if fn is not None else decorator

    def on_set_health[F: Callable](self, fn: F) -> F:
        self._register_handler('set_health', fn)
        return fn

    def on_set_armour[F: Callable](self, fn: F) -> F:
        self._register_handler('set_armour', fn)
        return fn

    def on_set_position[F: Callable](self, fn: F) -> F:
        self._register_handler('set_position', fn)
        return fn

    def on_checkpoint[F: Callable](self, fn: F) -> F:
        self._register_handler('checkpoint', fn)
        return fn

    def on_checkpoint_disabled[F: Callable](self, fn: F) -> F:
        self._register_handler('checkpoint_disabled', fn, extract=_NO_ARG)
        return fn

    def on_player_streamed_in[F: Callable](self, fn: F) -> F:
        self._register_handler('player_streamed_in', fn)
        return fn

    def on_player_streamed_out[F: Callable](self, fn: F) -> F:
        self._register_handler('player_streamed_out', fn)
        return fn

    def on_player_name[F: Callable](self, fn: F) -> F:
        self._register_handler('player_name', fn)
        return fn

    def on_toggle_controllable[F: Callable](self, fn: F) -> F:
        self._register_handler('toggle_controllable', fn)
        return fn

    def on_player_time[F: Callable](self, fn: F) -> F:
        self._register_handler('player_time', fn)
        return fn

    def on_death_message[F: Callable](self, fn: F) -> F:
        self._register_handler('death_message', fn)
        return fn

    def on_set_armed_weapon[F: Callable](self, fn: F) -> F:
        self._register_handler('set_armed_weapon', fn)
        return fn

    def on_spawn_info[F: Callable](self, fn: F) -> F:
        self._register_handler('spawn_info', fn)
        return fn

    def on_player_team[F: Callable](self, fn: F) -> F:
        self._register_handler('player_team', fn)
        return fn

    def on_put_in_vehicle[F: Callable](self, fn: F) -> F:
        self._register_handler('put_in_vehicle', fn)
        return fn

    def on_remove_from_vehicle[F: Callable](self, fn: F) -> F:
        self._register_handler('remove_from_vehicle', fn, extract=_NO_ARG)
        return fn

    def on_player_color[F: Callable](self, fn: F) -> F:
        self._register_handler('player_color', fn)
        return fn

    def on_world_time[F: Callable](self, fn: F) -> F:
        self._register_handler('world_time', fn)
        return fn

    def on_toggle_spectating[F: Callable](self, fn: F) -> F:
        self._register_handler('toggle_spectating', fn)
        return fn

    def on_wanted_level[F: Callable](self, fn: F) -> F:
        self._register_handler('wanted_level', fn)
        return fn

    def on_weapon_ammo[F: Callable](self, fn: F) -> F:
        self._register_handler('weapon_ammo', fn)
        return fn

    def on_gravity[F: Callable](self, fn: F) -> F:
        self._register_handler('gravity', fn)
        return fn

    def on_weather[F: Callable](self, fn: F) -> F:
        self._register_handler('weather', fn)
        return fn

    def on_player_skin[F: Callable](self, fn: F) -> F:
        self._register_handler('player_skin', fn)
        return fn

    def on_set_interior[F: Callable](self, fn: F) -> F:
        self._register_handler('set_interior', fn)
        return fn

    def on_vehicle_streamed_in[F: Callable](self, fn: F) -> F:
        self._register_handler('vehicle_streamed_in', fn)
        return fn

    def on_vehicle_streamed_out[F: Callable](self, fn: F) -> F:
        self._register_handler('vehicle_streamed_out', fn)
        return fn

    def on_player_death[F: Callable](self, fn: F) -> F:
        self._register_handler('player_death', fn)
        return fn

    def on_textdraw(
        self,
        fn=None,
        *,
        id: int | None = None,
        text: str | None = None,
        predicate: Callable[[TextDraw], bool] | None = None,
        selectable: bool | None = None,
    ):
        """Register a callback fired each time a matching textdraw is shown.

        Parameters
        ----------
        id:
            Only fire for textdraws with this exact id.
        text:
            Only fire for textdraws whose text equals this value.
        predicate:
            Arbitrary filter called with the TextDraw object.
        selectable:
            True → only SelectableTextDraw; False → exclude them; None → all.
        """
        filt = _make_obj_filter(predicate, {'id': id, 'text': text})

        def decorator(f):
            async def wrapped(td_id, *_args):
                # Yield once so that the registry _on_show coroutine (registered
                # first in the dispatcher routes) can complete before we look up.
                await asyncio.sleep(0)
                td = self.textdraws._registry.get(td_id)
                if td is None:
                    return
                if selectable is True and not isinstance(td, SelectableTextDraw):
                    return
                if selectable is False and isinstance(td, SelectableTextDraw):
                    return
                if filt is not None and not filt(td):
                    return
                if inspect.iscoroutinefunction(f):
                    await f(td)
                else:
                    f(td)

            self._register_handler(
                'textdraw_show',
                wrapped,
                extract=lambda e: (e[1],),
            )
            return f

        return decorator(fn) if fn is not None else decorator

    # ── Async generators ───────────────────────────────────────────────────────

    async def rpcs(self, rpc_id: int | None = None):
        """Async generator yielding ``(rpc_id, data)`` for raw RPCs."""
        q: asyncio.Queue = asyncio.Queue()
        self._bus.subscribe(q)
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
            self._bus.unsubscribe(q)

    async def events(self):
        """Async generator yielding every event tuple; stops after disconnect."""
        q: asyncio.Queue = asyncio.Queue()
        self._bus.subscribe(q)
        try:
            while True:
                event = await q.get()
                yield event
                if event[0] == 'disconnect':
                    return
        finally:
            self._bus.unsubscribe(q)

    def chat(self) -> _StreamListener:
        """Async generator yielding ChatMessage for each public chat message."""
        return _StreamListener(self._dispatcher, 'chat')

    def server_messages(self) -> _StreamListener:
        """Async generator yielding ServerMessage for each client message."""
        return _StreamListener(self._dispatcher, 'client_message')

    def dialogs(self) -> _StreamListener:
        """Async generator yielding AnyDialog each time a dialog is shown."""
        return _StreamListener(self._dispatcher, 'dialog')

    def game_texts(self) -> _StreamListener:
        """Async generator yielding GameText for each ShowGameText."""
        return _StreamListener(self._dispatcher, 'game_text')

    def player_joins(self) -> _StreamListener:
        """Async generator yielding PlayerJoin for each connecting player."""
        return _StreamListener(self._dispatcher, 'player_join')

    def player_quits(self) -> _StreamListener:
        """Async generator yielding PlayerQuit for each disconnecting player."""
        return _StreamListener(self._dispatcher, 'player_quit')

    def player_stream_ins(self) -> _StreamListener:
        """Async generator yielding PlayerStreamIn."""
        return _StreamListener(self._dispatcher, 'player_streamed_in')

    def player_stream_outs(self) -> _StreamListener:
        """Async generator yielding PlayerStreamOut."""
        return _StreamListener(self._dispatcher, 'player_streamed_out')

    def player_name_changes(self) -> _StreamListener:
        """Async generator yielding PlayerNameChange."""
        return _StreamListener(self._dispatcher, 'player_name')

    def death_messages(self) -> _StreamListener:
        """Async generator yielding DeathMessage."""
        return _StreamListener(self._dispatcher, 'death_message')

    def spawn_infos(self) -> _StreamListener:
        """Async generator yielding SpawnInfo."""
        return _StreamListener(self._dispatcher, 'spawn_info')

    def put_in_vehicles(self) -> _StreamListener:
        """Async generator yielding PutInVehicle."""
        return _StreamListener(self._dispatcher, 'put_in_vehicle')

    def player_colors(self) -> _StreamListener:
        """Async generator yielding PlayerColor."""
        return _StreamListener(self._dispatcher, 'player_color')

    def weather_changes(self) -> _StreamListener:
        """Async generator yielding Weather."""
        return _StreamListener(self._dispatcher, 'weather')

    def gravity_changes(self) -> _StreamListener:
        """Async generator yielding Gravity."""
        return _StreamListener(self._dispatcher, 'gravity')

    def player_skins(self) -> _StreamListener:
        """Async generator yielding PlayerSkin."""
        return _StreamListener(self._dispatcher, 'player_skin')

    def interior_changes(self) -> _StreamListener:
        """Async generator yielding SetInterior."""
        return _StreamListener(self._dispatcher, 'set_interior')

    def vehicle_stream_ins(self) -> _StreamListener:
        """Async generator yielding VehicleStreamIn."""
        return _StreamListener(self._dispatcher, 'vehicle_streamed_in')

    def vehicle_stream_outs(self) -> _StreamListener:
        """Async generator yielding VehicleStreamOut."""
        return _StreamListener(self._dispatcher, 'vehicle_streamed_out')

    def player_deaths(self) -> _StreamListener:
        """Async generator yielding PlayerDeath."""
        return _StreamListener(self._dispatcher, 'player_death')

    # ── Wait-for helpers ───────────────────────────────────────────────────────

    async def wait_for_rpc(
        self, rpc_id: int, *, predicate: Callable[[int, bytes], bool] | None = None
    ) -> bytes:
        """Await the next RPC with the given ID."""
        async for _, data in self.rpcs(rpc_id):
            if predicate is None or predicate(rpc_id, data):
                return data
        raise AssertionError('unreachable: stream ended without match')

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
        filt = _make_obj_filter(predicate, {'dialog_id': dialog_id}, instance_of=dialog_type)
        async for dlg in _StreamListener(self._dispatcher, 'dialog', filt):
            return dlg  # type: ignore[return-value]
        raise AssertionError('unreachable: stream ended without match')

    async def wait_for_chat(
        self,
        predicate: Callable[[ChatMessage], bool] | None = None,
        *,
        player_id: int | None = None,
    ) -> ChatMessage:
        """Await the next public chat message matching all given filters."""
        filt = _make_obj_filter(predicate, {'player_id': player_id})
        async for msg in _StreamListener(self._dispatcher, 'chat', filt):
            return msg
        raise AssertionError('unreachable: stream ended without match')

    async def wait_for_client_message(
        self,
        predicate: Callable[[ServerMessage], bool] | None = None,
        *,
        color: int | None = None,
    ) -> ServerMessage:
        """Await the next server message matching all given filters."""
        filt = _make_obj_filter(predicate, {'color': color})
        async for msg in _StreamListener(self._dispatcher, 'client_message', filt):
            return msg
        raise AssertionError('unreachable: stream ended without match')

    async def wait_for_player_join(
        self,
        predicate: Callable[[PlayerJoin], bool] | None = None,
        *,
        player_id: int | None = None,
        name: str | None = None,
    ) -> PlayerJoin:
        """Await the next player join matching all given filters."""
        filt = _make_obj_filter(predicate, {'player_id': player_id, 'name': name})
        async for evt in _StreamListener(self._dispatcher, 'player_join', filt):
            return evt
        raise AssertionError('unreachable: stream ended without match')

    # ── Actions ────────────────────────────────────────────────────────────────

    def send_rpc(self, rpc_id: int, data: bytes = b'', reliability: int = RELIABLE) -> bool:
        return self._actions.send_rpc(rpc_id, data, reliability)

    def send_chat(self, message: str) -> None:
        return self._actions.send_chat(message)

    def send_dialog_response(
        self, dialog_id: int, button: int, list_item: int = 0, text: str = ''
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

    def click_textdraw(self, textdraw_id: int) -> None:
        """Send SelectTextDraw RPC (83) for the given textdraw ID."""
        self._actions.click_textdraw(textdraw_id)

    def send_keys(
        self,
        keys: Keys | int,
        lr_analog: int = 0,
        ud_analog: int = 0,
    ) -> None:
        """Directly set the key state in on-foot sync packets (sticky).

        The state persists across keepalive packets until called again.
        Bypasses the ref-counting used by :meth:`press_keys`.

        Parameters
        ----------
        keys
            Bitmask of pressed keys; combine :class:`Keys` members with ``|``.
        lr_analog
            Left/right analog axis (0 = neutral, negative = left, positive = right).
        ud_analog
            Up/down analog axis (0 = neutral, negative = up, positive = down).
        """
        self._actions.send_keys(int(keys), lr_analog, ud_analog)

    async def press_keys(
        self,
        keys: Keys | int,
        duration: float = 0.5,
    ) -> None:
        """Hold *keys* for *duration* seconds, then auto-release.

        Safe to call concurrently from multiple handlers. Each call only
        releases its own bits; keys held by other concurrent calls are
        unaffected. The same key pressed by two concurrent calls stays
        pressed until the last one finishes (ref-counted per bit).

        For fire-and-forget (non-blocking), wrap with ``asyncio.create_task``.

        Parameters
        ----------
        keys
            Bitmask of keys to press; combine :class:`Keys` members with ``|``.
        duration
            Seconds to hold (default 0.5 s = one keepalive interval).
        """
        await self._actions.press_keys(int(keys), duration)

    # ── Bus pub/sub (public) ───────────────────────────────────────────────────

    def subscribe(self, q: asyncio.Queue) -> None:
        """Subscribe *q* to the event bus; receives every raw event tuple."""
        self._bus.subscribe(q)

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Unsubscribe *q* from the event bus."""
        self._bus.unsubscribe(q)

    # ── Post-middleware ────────────────────────────────────────────────────────

    def add_post_middleware(self, fn: Callable, *, tag: str = 'dialog') -> None:
        """Register *fn* as a post-middleware for events with *tag*.

        *fn* is called with the event object after **all** registered handlers
        for that event have finished.  Can be sync or async.

        Parameters
        ----------
        fn
            Callable (sync or async) that receives the event object.
        tag
            Event tag to listen for (default ``"dialog"``).
        """
        self._dispatcher.add_post_middleware(tag, fn)

    def post_middleware(self, fn: Callable | None = None, *, tag: str = 'dialog'):
        """Decorator that registers a post-middleware for *tag* events.

        Can be used with or without arguments::

            @bot.post_middleware
            async def after_dialog(dlg):
                ...

            @bot.post_middleware(tag="chat")
            async def after_chat(msg):
                ...
        """

        def decorator(f: Callable) -> Callable:
            self._dispatcher.add_post_middleware(tag, f)
            return f

        return decorator(fn) if fn is not None else decorator

    # ── Remote shell ───────────────────────────────────────────────────────────

    async def expose_shell(self, path: str | None = None) -> asyncio.Server:
        """Start an in-process TUI and expose it via a Unix socket relay.

        The TUI runs in the same asyncio loop using a PTY.  A thin relay
        client (``pyraksamp shell --attach [SOCK]``) can connect to forward
        ANSI bytes to its terminal and send keystrokes back.

        Parameters
        ----------
        path
            Unix socket path.  Defaults to ``/tmp/pyraksamp-<pid>.sock``.

        Returns
        -------
        asyncio.Server
            The relay server (call ``.close()`` to stop accepting).
        """
        import os
        import pty

        from pyraksamp.shell._app import SampShellApp
        from pyraksamp.shell._commands import CommandRegistry, _register_builtins
        from pyraksamp.shell._pty import _relay_client, make_pty_driver_class

        master_fd, slave_fd = pty.openpty()
        path = path or f'/tmp/pyraksamp-{os.getpid()}.sock'

        commands = CommandRegistry()
        _register_builtins(commands)
        driver_cls = make_pty_driver_class(slave_fd)
        app = SampShellApp(self, commands, driver_class=driver_cls)
        asyncio.create_task(app.run_async())

        server = await asyncio.start_unix_server(
            lambda r, w: _relay_client(master_fd, r, w), path
        )
        return server

    def _register_handler(
        self,
        tag: str,
        fn: Callable,
        predicate: Callable | None = None,
        extract: Callable | None = None,
    ) -> None:
        self._register_listener(
            _CallbackListener(self._dispatcher, tag, fn, predicate, extract)
        )

    def include_router(self, router: 'Router') -> None:
        """Register all handlers from *router*, injecting this bot as first argument.

        Each handler in the router receives the bot as its first positional
        argument followed by the event object::

            router = Router()

            @router.on_chat()
            async def on_chat(bot, msg):
                bot.send_chat("hi")

            bot.include_router(router)
        """
        for spec in router._specs:
            spec(self)


# Backwards-compatibility alias
SAMPClient = SAMPBot


def _with_bot(bot: SAMPBot, fn: Callable) -> Callable:
    if inspect.iscoroutinefunction(fn):

        async def wrapped(*args, _fn=fn):
            return await _fn(bot, *args)

        return wrapped

    def wrapped(*args, _fn=fn):
        return _fn(bot, *args)

    return wrapped


class Router:
    """Collects event handler registrations independently of a bot instance.

    Handlers registered on a router receive the bot as their first argument,
    followed by the event object.  Attach a router to a bot with
    :meth:`SAMPBot.include_router`::

        # handlers/chat.py
        from pyraksamp import Router

        router = Router()

        @router.on_chat()
        async def on_chat(bot, msg):
            bot.send_chat(f"echo: {msg.text.stripped}")

        @router.on_dialog()
        async def on_dialog(bot, dlg):
            dlg.buttons[0].click()

        # main.py
        from handlers import chat

        await bot.start()
        bot.include_router(chat.router)
        await bot.run_until_disconnected()
    """

    def __init__(self) -> None:
        self._specs: list[Callable[[SAMPBot], None]] = []

    def _store(
        self,
        tag: str,
        fn: Callable,
        predicate: Callable | None = None,
        extract: Callable | None = None,
    ) -> None:
        def replay(bot: SAMPBot) -> None:
            bot._register_handler(tag, _with_bot(bot, fn), predicate, extract)

        self._specs.append(replay)

    def _store_textdraw(
        self,
        fn: Callable,
        filt: Callable | None,
        selectable: bool | None,
    ) -> None:
        def replay(bot: SAMPBot) -> None:
            injected = _with_bot(bot, fn)

            async def textdraw_wrapper(td_id, *_args):
                await asyncio.sleep(0)
                td = bot.textdraws._registry.get(td_id)
                if td is None:
                    return
                if selectable is True and not isinstance(td, SelectableTextDraw):
                    return
                if selectable is False and isinstance(td, SelectableTextDraw):
                    return
                if filt is not None and not filt(td):
                    return
                if inspect.iscoroutinefunction(injected):
                    await injected(td)
                else:
                    injected(td)

            bot._register_handler(
                'textdraw_show',
                textdraw_wrapper,
                extract=lambda e: (e[1],),
            )

        self._specs.append(replay)

    def on_connect[F: Callable](self, fn: F) -> F:
        self._store('connect', fn, extract=_NO_ARG)
        return fn

    def on_disconnect[F: Callable](self, fn: F) -> F:
        self._store('disconnect', fn, extract=_NO_ARG)
        return fn

    def on_rpc[F: Callable](
        self,
        fn: F | None = None,
        *,
        rpc_id: int | None = None,
        predicate: Callable[[int, bytes], bool] | None = None,
    ) -> F | Callable[[F], F]:
        def decorator(f: F) -> F:
            def filt(rid: int, data: bytes) -> bool:
                return not (
                    (rpc_id is not None and rid != rpc_id)
                    or (predicate is not None and not predicate(rid, data))
                )

            self._store(
                'rpc',
                f,
                predicate=filt if (rpc_id is not None or predicate is not None) else None,
                extract=lambda e: (e[1], e[2]),
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
        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {'player_id': player_id, 'name': name})
            self._store('player_join', f, filt)
            return f

        return decorator(fn) if fn is not None else decorator

    def on_player_quit[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        predicate: Callable[[PlayerQuit], bool] | None = None,
    ) -> F | Callable[[F], F]:
        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {'player_id': player_id})
            self._store('player_quit', f, filt)
            return f

        return decorator(fn) if fn is not None else decorator

    def on_chat[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        predicate: Callable[[ChatMessage], bool] | None = None,
    ) -> F | Callable[[F], F]:
        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {'player_id': player_id})
            self._store('chat', f, filt)
            return f

        return decorator(fn) if fn is not None else decorator

    def on_client_message[F: Callable](
        self,
        fn: F | None = None,
        *,
        color: int | None = None,
        predicate: Callable[[ServerMessage], bool] | None = None,
    ) -> F | Callable[[F], F]:
        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {'color': color})
            self._store('client_message', f, filt)
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
        def decorator(f: Callable[[Any], Any]) -> Callable[[Any], Any]:
            filt = _make_obj_filter(
                predicate, {'dialog_id': dialog_id}, instance_of=dialog_type
            )
            self._store('dialog', f, filt)
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
        def decorator(f: F) -> F:
            filt = _make_obj_filter(predicate, {'style': style})
            self._store('game_text', f, filt)
            return f

        return decorator(fn) if fn is not None else decorator

    def on_set_health[F: Callable](self, fn: F) -> F:
        self._store('set_health', fn)
        return fn

    def on_set_armour[F: Callable](self, fn: F) -> F:
        self._store('set_armour', fn)
        return fn

    def on_set_position[F: Callable](self, fn: F) -> F:
        self._store('set_position', fn)
        return fn

    def on_checkpoint[F: Callable](self, fn: F) -> F:
        self._store('checkpoint', fn)
        return fn

    def on_checkpoint_disabled[F: Callable](self, fn: F) -> F:
        self._store('checkpoint_disabled', fn, extract=_NO_ARG)
        return fn

    def on_player_streamed_in[F: Callable](self, fn: F) -> F:
        self._store('player_streamed_in', fn)
        return fn

    def on_player_streamed_out[F: Callable](self, fn: F) -> F:
        self._store('player_streamed_out', fn)
        return fn

    def on_player_name[F: Callable](self, fn: F) -> F:
        self._store('player_name', fn)
        return fn

    def on_toggle_controllable[F: Callable](self, fn: F) -> F:
        self._store('toggle_controllable', fn)
        return fn

    def on_player_time[F: Callable](self, fn: F) -> F:
        self._store('player_time', fn)
        return fn

    def on_death_message[F: Callable](self, fn: F) -> F:
        self._store('death_message', fn)
        return fn

    def on_set_armed_weapon[F: Callable](self, fn: F) -> F:
        self._store('set_armed_weapon', fn)
        return fn

    def on_spawn_info[F: Callable](self, fn: F) -> F:
        self._store('spawn_info', fn)
        return fn

    def on_player_team[F: Callable](self, fn: F) -> F:
        self._store('player_team', fn)
        return fn

    def on_put_in_vehicle[F: Callable](self, fn: F) -> F:
        self._store('put_in_vehicle', fn)
        return fn

    def on_remove_from_vehicle[F: Callable](self, fn: F) -> F:
        self._store('remove_from_vehicle', fn, extract=_NO_ARG)
        return fn

    def on_player_color[F: Callable](self, fn: F) -> F:
        self._store('player_color', fn)
        return fn

    def on_world_time[F: Callable](self, fn: F) -> F:
        self._store('world_time', fn)
        return fn

    def on_toggle_spectating[F: Callable](self, fn: F) -> F:
        self._store('toggle_spectating', fn)
        return fn

    def on_wanted_level[F: Callable](self, fn: F) -> F:
        self._store('wanted_level', fn)
        return fn

    def on_weapon_ammo[F: Callable](self, fn: F) -> F:
        self._store('weapon_ammo', fn)
        return fn

    def on_gravity[F: Callable](self, fn: F) -> F:
        self._store('gravity', fn)
        return fn

    def on_weather[F: Callable](self, fn: F) -> F:
        self._store('weather', fn)
        return fn

    def on_player_skin[F: Callable](self, fn: F) -> F:
        self._store('player_skin', fn)
        return fn

    def on_set_interior[F: Callable](self, fn: F) -> F:
        self._store('set_interior', fn)
        return fn

    def on_vehicle_streamed_in[F: Callable](self, fn: F) -> F:
        self._store('vehicle_streamed_in', fn)
        return fn

    def on_vehicle_streamed_out[F: Callable](self, fn: F) -> F:
        self._store('vehicle_streamed_out', fn)
        return fn

    def on_player_death[F: Callable](self, fn: F) -> F:
        self._store('player_death', fn)
        return fn

    def on_textdraw(
        self,
        fn=None,
        *,
        id: int | None = None,
        text: str | None = None,
        predicate: Callable[[TextDraw], bool] | None = None,
        selectable: bool | None = None,
    ):
        filt = _make_obj_filter(predicate, {'id': id, 'text': text})

        def decorator(f):
            self._store_textdraw(f, filt, selectable)
            return f

        return decorator(fn) if fn is not None else decorator
