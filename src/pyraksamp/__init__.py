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
from pyraksamp._bridge import _CallbackBridge
from pyraksamp._streams import _EventStreams
from pyraksamp._actions import _Actions
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
        self._bridge = _CallbackBridge(self._client, self._bus)
        self._streams = _EventStreams(self._bus)
        self._actions = _Actions(self._client)

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
        self._bridge.setup(loop)
        return await loop.run_in_executor(None, lambda: self._client.start(timeout))

    async def disconnect(self) -> None:
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
        """The bot's player ID assigned by the server, or -1 before the connection is accepted."""
        return self._client.player_id

    # ── Delegation: on_* decorators → _bus ────────────────────────────────────

    def on_connect[F: Callable](self, fn: F) -> F:
        return self._bus.on_connect(fn)

    def on_disconnect[F: Callable](self, fn: F) -> F:
        return self._bus.on_disconnect(fn)

    def on_rpc[F: Callable](
        self,
        fn: F | None = None,
        *,
        rpc_id: int | None = None,
        predicate: Callable[[int, bytes], bool] | None = None,
    ) -> F | Callable[[F], F]:
        return self._bus.on_rpc(fn, rpc_id=rpc_id, predicate=predicate)

    def on_player_join[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        name: str | None = None,
        predicate: Callable[[PlayerJoin], bool] | None = None,
    ) -> F | Callable[[F], F]:
        return self._bus.on_player_join(fn, player_id=player_id, name=name, predicate=predicate)

    def on_player_quit[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        predicate: Callable[[PlayerQuit], bool] | None = None,
    ) -> F | Callable[[F], F]:
        return self._bus.on_player_quit(fn, player_id=player_id, predicate=predicate)

    def on_chat[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        predicate: Callable[[ChatMessage], bool] | None = None,
    ) -> F | Callable[[F], F]:
        return self._bus.on_chat(fn, player_id=player_id, predicate=predicate)

    def on_client_message[F: Callable](
        self,
        fn: F | None = None,
        *,
        color: int | None = None,
        predicate: Callable[[ServerMessage], bool] | None = None,
    ) -> F | Callable[[F], F]:
        return self._bus.on_client_message(fn, color=color, predicate=predicate)

    @overload
    def on_dialog(
        self,
        fn: Callable[[AnyDialog], Any],
    ) -> Callable[[AnyDialog], Any]: ...

    @overload
    def on_dialog[D: (MsgboxDialog, InputDialog, PasswordDialog, ListDialog, TablistDialog, TablistHeadersDialog)](
        self,
        fn: None = ...,
        *,
        dialog_type: type[D] | None = ...,
        predicate: Callable[[D], bool] | None = ...,
        dialog_id: int | None = ...,
    ) -> Callable[[Callable[[D], Any]], Callable[[D], Any]]: ...

    def on_dialog[D: (MsgboxDialog, InputDialog, PasswordDialog, ListDialog, TablistDialog, TablistHeadersDialog)](
        self,
        fn: Callable[[Any], Any] | None = None,
        *,
        dialog_type: type[D] | None = None,
        predicate: Callable[[D], bool] | None = None,
        dialog_id: int | None = None,
    ) -> Callable[[Any], Any]:
        return self._bus.on_dialog(fn, dialog_type=dialog_type, predicate=predicate, dialog_id=dialog_id)

    def on_game_text[F: Callable](
        self,
        fn: F | None = None,
        *,
        style: int | None = None,
        predicate: Callable[[GameText], bool] | None = None,
    ) -> F | Callable[[F], F]:
        return self._bus.on_game_text(fn, style=style, predicate=predicate)

    def on_set_health[F: Callable](self, fn: F) -> F:
        return self._bus.on_set_health(fn)

    def on_set_armour[F: Callable](self, fn: F) -> F:
        return self._bus.on_set_armour(fn)

    def on_set_position[F: Callable](self, fn: F) -> F:
        return self._bus.on_set_position(fn)

    def on_checkpoint[F: Callable](self, fn: F) -> F:
        return self._bus.on_checkpoint(fn)

    def on_checkpoint_disabled[F: Callable](self, fn: F) -> F:
        return self._bus.on_checkpoint_disabled(fn)

    def on_player_streamed_in[F: Callable](self, fn: F) -> F:
        return self._bus.on_player_streamed_in(fn)

    def on_player_streamed_out[F: Callable](self, fn: F) -> F:
        return self._bus.on_player_streamed_out(fn)

    def on_player_name[F: Callable](self, fn: F) -> F:
        return self._bus.on_player_name(fn)

    def on_toggle_controllable[F: Callable](self, fn: F) -> F:
        return self._bus.on_toggle_controllable(fn)

    def on_player_time[F: Callable](self, fn: F) -> F:
        return self._bus.on_player_time(fn)

    def on_death_message[F: Callable](self, fn: F) -> F:
        return self._bus.on_death_message(fn)

    def on_set_armed_weapon[F: Callable](self, fn: F) -> F:
        return self._bus.on_set_armed_weapon(fn)

    def on_spawn_info[F: Callable](self, fn: F) -> F:
        return self._bus.on_spawn_info(fn)

    def on_player_team[F: Callable](self, fn: F) -> F:
        return self._bus.on_player_team(fn)

    def on_put_in_vehicle[F: Callable](self, fn: F) -> F:
        return self._bus.on_put_in_vehicle(fn)

    def on_remove_from_vehicle[F: Callable](self, fn: F) -> F:
        return self._bus.on_remove_from_vehicle(fn)

    def on_player_color[F: Callable](self, fn: F) -> F:
        return self._bus.on_player_color(fn)

    def on_world_time[F: Callable](self, fn: F) -> F:
        return self._bus.on_world_time(fn)

    def on_toggle_spectating[F: Callable](self, fn: F) -> F:
        return self._bus.on_toggle_spectating(fn)

    def on_wanted_level[F: Callable](self, fn: F) -> F:
        return self._bus.on_wanted_level(fn)

    def on_weapon_ammo[F: Callable](self, fn: F) -> F:
        return self._bus.on_weapon_ammo(fn)

    def on_gravity[F: Callable](self, fn: F) -> F:
        return self._bus.on_gravity(fn)

    def on_weather[F: Callable](self, fn: F) -> F:
        return self._bus.on_weather(fn)

    def on_player_skin[F: Callable](self, fn: F) -> F:
        return self._bus.on_player_skin(fn)

    def on_set_interior[F: Callable](self, fn: F) -> F:
        return self._bus.on_set_interior(fn)

    def on_vehicle_streamed_in[F: Callable](self, fn: F) -> F:
        return self._bus.on_vehicle_streamed_in(fn)

    def on_vehicle_streamed_out[F: Callable](self, fn: F) -> F:
        return self._bus.on_vehicle_streamed_out(fn)

    def on_player_death[F: Callable](self, fn: F) -> F:
        return self._bus.on_player_death(fn)

    # ── Delegation: streams → _streams ────────────────────────────────────────

    def rpcs(self, rpc_id: int | None = None):
        return self._streams.rpcs(rpc_id)

    def events(self):
        return self._streams.events()

    def chat(self):
        return self._streams.chat()

    def server_messages(self):
        return self._streams.server_messages()

    def dialogs(self):
        return self._streams.dialogs()

    def game_texts(self):
        return self._streams.game_texts()

    def player_joins(self):
        return self._streams.player_joins()

    def player_quits(self):
        return self._streams.player_quits()

    def player_stream_ins(self):
        return self._streams.player_stream_ins()

    def player_stream_outs(self):
        return self._streams.player_stream_outs()

    def player_name_changes(self):
        return self._streams.player_name_changes()

    def death_messages(self):
        return self._streams.death_messages()

    def spawn_infos(self):
        return self._streams.spawn_infos()

    def put_in_vehicles(self):
        return self._streams.put_in_vehicles()

    def player_colors(self):
        return self._streams.player_colors()

    def weather_changes(self):
        return self._streams.weather_changes()

    def gravity_changes(self):
        return self._streams.gravity_changes()

    def player_skins(self):
        return self._streams.player_skins()

    def interior_changes(self):
        return self._streams.interior_changes()

    def vehicle_stream_ins(self):
        return self._streams.vehicle_stream_ins()

    def vehicle_stream_outs(self):
        return self._streams.vehicle_stream_outs()

    def player_deaths(self):
        return self._streams.player_deaths()

    async def wait_for_rpc(
        self, rpc_id: int, *, predicate: Callable[[int, bytes], bool] | None = None
    ) -> bytes:
        return await self._streams.wait_for_rpc(rpc_id, predicate=predicate)

    async def wait_for_dialog[D: (MsgboxDialog, InputDialog, PasswordDialog, ListDialog, TablistDialog, TablistHeadersDialog)](
        self,
        predicate: Callable[[D], bool] | None = None,
        *,
        dialog_type: type[D] | None = None,
        dialog_id: int | None = None,
    ) -> D:
        return await self._streams.wait_for_dialog(predicate, dialog_type=dialog_type, dialog_id=dialog_id)

    async def wait_for_chat(
        self,
        predicate: Callable[[ChatMessage], bool] | None = None,
        *,
        player_id: int | None = None,
    ) -> ChatMessage:
        return await self._streams.wait_for_chat(predicate, player_id=player_id)

    async def wait_for_client_message(
        self,
        predicate: Callable[[ServerMessage], bool] | None = None,
        *,
        color: int | None = None,
    ) -> ServerMessage:
        return await self._streams.wait_for_client_message(predicate, color=color)

    async def wait_for_player_join(
        self,
        predicate: Callable[[PlayerJoin], bool] | None = None,
        *,
        player_id: int | None = None,
        name: str | None = None,
    ) -> PlayerJoin:
        return await self._streams.wait_for_player_join(predicate, player_id=player_id, name=name)

    # ── Delegation: actions → _actions ────────────────────────────────────────

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
