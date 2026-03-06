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
import struct
from collections.abc import Callable
from typing import Any, overload

from pyraksamp._core import SAMPClient as _SAMPClient
from pyraksamp import _core
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
    "SAMPBot",
    "gen_gpci",
    "AnyDialog",
    "MsgboxDialog",
    "InputDialog",
    "PasswordDialog",
    "ListDialog",
    "TablistDialog",
    "TablistHeadersDialog",
    "Button",
    "ButtonSelector",
    "ListRow",
    "TablistRow",
    "RowSelector",
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




def _make_obj_filter(predicate, kwargs):
    """Return a filter callable(obj)->bool, or None if no filtering requested."""
    kw = {k: v for k, v in kwargs.items() if v is not None}
    if predicate is None and not kw:
        return None

    def filt(obj):
        if predicate is not None and not predicate(obj):
            return False
        return all(getattr(obj, k) == v for k, v in kw.items())

    return filt


def _wrap_obj(fn, filt):
    """Wrap a single-arg event callback with a predicate guard."""

    async def wrapper(obj):
        if filt(obj):
            if asyncio.iscoroutinefunction(fn):
                await fn(obj)
            else:
                fn(obj)

    return wrapper


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
        self._loop: asyncio.AbstractEventLoop | None = None

        # Fan-out subscriber queues.  Each active rpcs()/events() call appends
        # its own queue here; _broadcast() copies every event to all of them so
        # concurrent consumers are fully independent (no event stealing).
        # Accessed only from the event-loop thread (via call_soon_threadsafe),
        # so no additional locking is required.
        self._subscribers: list[asyncio.Queue] = []

        # User-registered callbacks (set via decorators or direct assignment).
        # Connection
        self._cb_connect: object = None
        self._cb_disconnect: object = None
        # Raw
        self._cb_rpc: object = None
        # Player roster
        self._cb_player_join: object = None
        self._cb_player_quit: object = None
        # Chat
        self._cb_chat: object = None
        self._cb_client_message: object = None
        # Dialogs
        self._cb_dialog: object = None
        # HUD
        self._cb_game_text: object = None
        # Player state
        self._cb_set_health: object = None
        self._cb_set_armour: object = None
        self._cb_set_position: object = None
        # World
        self._cb_checkpoint: object = None
        self._cb_checkpoint_disabled: object = None
        # Proximity
        self._cb_player_streamed_in: object = None
        self._cb_player_streamed_out: object = None
        # Player info
        self._cb_player_name: object = None
        self._cb_toggle_controllable: object = None
        self._cb_player_time: object = None
        self._cb_death_message: object = None
        self._cb_set_armed_weapon: object = None
        self._cb_spawn_info: object = None
        self._cb_player_team: object = None
        self._cb_put_in_vehicle: object = None
        self._cb_remove_from_vehicle: object = None
        self._cb_player_color: object = None
        self._cb_world_time: object = None
        self._cb_toggle_spectating: object = None
        self._cb_wanted_level: object = None
        self._cb_weapon_ammo: object = None
        self._cb_gravity: object = None
        self._cb_weather: object = None
        self._cb_player_skin: object = None
        self._cb_set_interior: object = None
        self._cb_vehicle_streamed_in: object = None
        self._cb_vehicle_streamed_out: object = None
        self._cb_player_death: object = None

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
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("connect",)),
                    self._fire(self._cb_connect),
                )
            )

        def on_disconnect():
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("disconnect",)),
                    self._fire(self._cb_disconnect),
                )
            )

        def on_rpc(rpc_id: int, data: bytes):
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("rpc", rpc_id, data)),
                    self._fire(self._cb_rpc, rpc_id, data),
                )
            )

        def on_player_join(pid: int, name: str):
            evt = PlayerJoin(player_id=pid, name=name)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_join", evt)),
                    self._fire(self._cb_player_join, evt),
                )
            )

        def on_player_quit(pid: int, reason: int):
            evt = PlayerQuit(player_id=pid, reason=reason)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_quit", evt)),
                    self._fire(self._cb_player_quit, evt),
                )
            )

        def on_chat(pid: int, text: str):
            evt = ChatMessage(player_id=pid, text=text)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("chat", evt)),
                    self._fire(self._cb_chat, evt),
                )
            )

        def on_client_message(color: int, text: str):
            evt = ServerMessage(color=color, text=text)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("client_message", evt)),
                    self._fire(self._cb_client_message, evt),
                )
            )

        def on_dialog(
            did: int, style: int, title: str, btn1: str, btn2: str, body: str
        ):
            evt = _make_dialog(did, style, title, btn1, btn2, body, self)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("dialog", evt)),
                    self._fire(self._cb_dialog, evt),
                )
            )

        def on_game_text(style: int, ms: int, text: str):
            evt = GameText(style=style, duration_ms=ms, text=text)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("game_text", evt)),
                    self._fire(self._cb_game_text, evt),
                )
            )

        def on_set_health(hp: float):
            evt = SetHealth(health=hp)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("set_health", evt)),
                    self._fire(self._cb_set_health, evt),
                )
            )

        def on_set_armour(arm: float):
            evt = SetArmour(armour=arm)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("set_armour", evt)),
                    self._fire(self._cb_set_armour, evt),
                )
            )

        def on_set_position(x: float, y: float, z: float):
            evt = SetPosition(x=x, y=y, z=z)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("set_position", evt)),
                    self._fire(self._cb_set_position, evt),
                )
            )

        def on_checkpoint(x: float, y: float, z: float, size: float):
            evt = Checkpoint(x=x, y=y, z=z, size=size)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("checkpoint", evt)),
                    self._fire(self._cb_checkpoint, evt),
                )
            )

        def on_checkpoint_disabled():
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("checkpoint_disabled",)),
                    self._fire(self._cb_checkpoint_disabled),
                )
            )

        def on_player_streamed_in(
            pid: int,
            team: int,
            skin: int,
            x: float,
            y: float,
            z: float,
            rot: float,
            color: int,
            fs: int,
        ):
            evt = PlayerStreamIn(
                player_id=pid,
                team=team,
                skin=skin,
                x=x,
                y=y,
                z=z,
                rotation=rot,
                color=color,
                fight_style=fs,
            )
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_streamed_in", evt)),
                    self._fire(self._cb_player_streamed_in, evt),
                )
            )

        def on_player_streamed_out(pid: int):
            evt = PlayerStreamOut(player_id=pid)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_streamed_out", evt)),
                    self._fire(self._cb_player_streamed_out, evt),
                )
            )

        def on_player_name(pid: int, name: str, success: int):
            evt = PlayerNameChange(player_id=pid, name=name, success=success)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_name", evt)),
                    self._fire(self._cb_player_name, evt),
                )
            )

        def on_toggle_controllable(moveable: int):
            evt = ToggleControllable(moveable=moveable)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("toggle_controllable", evt)),
                    self._fire(self._cb_toggle_controllable, evt),
                )
            )

        def on_player_time(hour: int, minute: int):
            evt = PlayerTime(hour=hour, minute=minute)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_time", evt)),
                    self._fire(self._cb_player_time, evt),
                )
            )

        def on_death_message(killer_id: int, player_id: int, weapon: int):
            evt = DeathMessage(killer_id=killer_id, player_id=player_id, weapon=weapon)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("death_message", evt)),
                    self._fire(self._cb_death_message, evt),
                )
            )

        def on_set_armed_weapon(weapon_id: int):
            evt = SetArmedWeapon(weapon_id=weapon_id)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("set_armed_weapon", evt)),
                    self._fire(self._cb_set_armed_weapon, evt),
                )
            )

        def on_spawn_info(
            team: int,
            skin: int,
            x: float,
            y: float,
            z: float,
            rot: float,
            w1: int,
            w2: int,
            w3: int,
            a1: int,
            a2: int,
            a3: int,
        ):
            evt = SpawnInfo(
                team=team,
                skin=skin,
                x=x,
                y=y,
                z=z,
                rotation=rot,
                weapons=(w1, w2, w3),
                ammo=(a1, a2, a3),
            )
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("spawn_info", evt)),
                    self._fire(self._cb_spawn_info, evt),
                )
            )

        def on_player_team(pid: int, team: int):
            evt = PlayerTeam(player_id=pid, team=team)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_team", evt)),
                    self._fire(self._cb_player_team, evt),
                )
            )

        def on_put_in_vehicle(vehicle_id: int, seat_id: int):
            evt = PutInVehicle(vehicle_id=vehicle_id, seat_id=seat_id)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("put_in_vehicle", evt)),
                    self._fire(self._cb_put_in_vehicle, evt),
                )
            )

        def on_remove_from_vehicle():
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("remove_from_vehicle",)),
                    self._fire(self._cb_remove_from_vehicle),
                )
            )

        def on_player_color(pid: int, color: int):
            evt = PlayerColor(player_id=pid, color=color)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_color", evt)),
                    self._fire(self._cb_player_color, evt),
                )
            )

        def on_world_time(hour: int):
            evt = WorldTime(hour=hour)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("world_time", evt)),
                    self._fire(self._cb_world_time, evt),
                )
            )

        def on_toggle_spectating(spectating: bool):
            evt = ToggleSpectating(spectating=spectating)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("toggle_spectating", evt)),
                    self._fire(self._cb_toggle_spectating, evt),
                )
            )

        def on_wanted_level(level: int):
            evt = WantedLevel(level=level)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("wanted_level", evt)),
                    self._fire(self._cb_wanted_level, evt),
                )
            )

        def on_weapon_ammo(weapon_id: int, ammo: int):
            evt = WeaponAmmo(weapon_id=weapon_id, ammo=ammo)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("weapon_ammo", evt)),
                    self._fire(self._cb_weapon_ammo, evt),
                )
            )

        def on_gravity(gravity: float):
            evt = Gravity(gravity=gravity)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("gravity", evt)),
                    self._fire(self._cb_gravity, evt),
                )
            )

        def on_weather(weather_id: int):
            evt = Weather(weather_id=weather_id)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("weather", evt)),
                    self._fire(self._cb_weather, evt),
                )
            )

        def on_player_skin(pid: int, skin_id: int):
            evt = PlayerSkin(player_id=pid, skin_id=skin_id)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_skin", evt)),
                    self._fire(self._cb_player_skin, evt),
                )
            )

        def on_set_interior(interior_id: int):
            evt = SetInterior(interior_id=interior_id)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("set_interior", evt)),
                    self._fire(self._cb_set_interior, evt),
                )
            )

        def on_vehicle_streamed_in(
            vid: int,
            model: int,
            x: float,
            y: float,
            z: float,
            angle: float,
            color1: int,
            color2: int,
            health: float,
            interior: int,
            door_dmg: int,
            panel_dmg: int,
            light_dmg: int,
            tire_dmg: int,
            add_siren: int,
            paintjob: int,
            body_color1: int,
            body_color2: int,
        ):
            evt = VehicleStreamIn(
                vehicle_id=vid,
                model=model,
                x=x,
                y=y,
                z=z,
                angle=angle,
                color1=color1,
                color2=color2,
                health=health,
                interior=interior,
                door_damage=door_dmg,
                panel_damage=panel_dmg,
                light_damage=light_dmg,
                tire_damage=tire_dmg,
                add_siren=bool(add_siren),
                paintjob=paintjob,
                body_color1=body_color1,
                body_color2=body_color2,
            )
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("vehicle_streamed_in", evt)),
                    self._fire(self._cb_vehicle_streamed_in, evt),
                )
            )

        def on_vehicle_streamed_out(vid: int):
            evt = VehicleStreamOut(vehicle_id=vid)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("vehicle_streamed_out", evt)),
                    self._fire(self._cb_vehicle_streamed_out, evt),
                )
            )

        def on_player_death(pid: int):
            evt = PlayerDeath(player_id=pid)
            loop.call_soon_threadsafe(
                lambda: (
                    self._broadcast(("player_death", evt)),
                    self._fire(self._cb_player_death, evt),
                )
            )

        self._client.on_connect = on_connect
        self._client.on_disconnect = on_disconnect
        self._client.on_rpc = on_rpc
        self._client.on_player_join = on_player_join
        self._client.on_player_quit = on_player_quit
        self._client.on_chat = on_chat
        self._client.on_client_message = on_client_message
        self._client.on_dialog = on_dialog
        self._client.on_game_text = on_game_text
        self._client.on_set_health = on_set_health
        self._client.on_set_armour = on_set_armour
        self._client.on_set_position = on_set_position
        self._client.on_checkpoint = on_checkpoint
        self._client.on_checkpoint_disabled = on_checkpoint_disabled
        self._client.on_player_streamed_in = on_player_streamed_in
        self._client.on_player_streamed_out = on_player_streamed_out
        self._client.on_player_name = on_player_name
        self._client.on_toggle_controllable = on_toggle_controllable
        self._client.on_player_time = on_player_time
        self._client.on_death_message = on_death_message
        self._client.on_set_armed_weapon = on_set_armed_weapon
        self._client.on_spawn_info = on_spawn_info
        self._client.on_player_team = on_player_team
        self._client.on_put_in_vehicle = on_put_in_vehicle
        self._client.on_remove_from_vehicle = on_remove_from_vehicle
        self._client.on_player_color = on_player_color
        self._client.on_world_time = on_world_time
        self._client.on_toggle_spectating = on_toggle_spectating
        self._client.on_wanted_level = on_wanted_level
        self._client.on_weapon_ammo = on_weapon_ammo
        self._client.on_gravity = on_gravity
        self._client.on_weather = on_weather
        self._client.on_player_skin = on_player_skin
        self._client.on_set_interior = on_set_interior
        self._client.on_vehicle_streamed_in = on_vehicle_streamed_in
        self._client.on_vehicle_streamed_out = on_vehicle_streamed_out
        self._client.on_player_death = on_player_death

    # ── Decorator-style callbacks ──────────────────────────────────────────────
    # Each decorator accepts both plain functions and async def coroutines.
    # Typed callbacks receive the corresponding dataclass instance as first arg.

    def on_connect[F: Callable](self, fn: F) -> F:
        """Decorator: called (no args) when fully connected."""
        self._cb_connect = fn
        return fn

    def on_disconnect[F: Callable](self, fn: F) -> F:
        """Decorator: called (no args) on disconnection."""
        self._cb_disconnect = fn
        return fn

    def on_rpc[F: Callable](
        self,
        fn: F | None = None,
        *,
        rpc_id: int | None = None,
        predicate: Callable[[int, bytes], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Decorator: fn(rpc_id: int, data: bytes) for every incoming RPC (raw).

        Optional filters:
            rpc_id=61            – specific RPC only
            predicate=lambda rid, data: ...
        """

        def decorator(f):
            if rpc_id is not None or predicate is not None:

                async def wrapper(rid, data):
                    if rpc_id is not None and rid != rpc_id:
                        return
                    if predicate is not None and not predicate(rid, data):
                        return
                    if asyncio.iscoroutinefunction(f):
                        await f(rid, data)
                    else:
                        f(rid, data)

                self._cb_rpc = wrapper
            else:
                self._cb_rpc = f
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    def on_player_join[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        name: str | None = None,
        predicate: Callable[[PlayerJoin], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Decorator: fn(event: PlayerJoin) when a player connects.

        Optional filters: player_id=, name=, predicate=lambda e: ...
        """

        def decorator(f):
            filt = _make_obj_filter(predicate, {"player_id": player_id, "name": name})
            self._cb_player_join = _wrap_obj(f, filt) if filt else f
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    def on_player_quit[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        predicate: Callable[[PlayerQuit], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Decorator: fn(event: PlayerQuit) when a player disconnects.

        Optional filters: player_id=, predicate=lambda e: ...
        """

        def decorator(f):
            filt = _make_obj_filter(predicate, {"player_id": player_id})
            self._cb_player_quit = _wrap_obj(f, filt) if filt else f
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    def on_chat[F: Callable](
        self,
        fn: F | None = None,
        *,
        player_id: int | None = None,
        predicate: Callable[[ChatMessage], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Decorator: fn(event: ChatMessage) for public chat.

        Optional filters: player_id=, predicate=lambda e: e.text.startswith("!")
        """

        def decorator(f):
            filt = _make_obj_filter(predicate, {"player_id": player_id})
            self._cb_chat = _wrap_obj(f, filt) if filt else f
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    def on_client_message[F: Callable](
        self,
        fn: F | None = None,
        *,
        color: int | None = None,
        predicate: Callable[[ServerMessage], bool] | None = None,
    ) -> F | Callable[[F], F]:
        """Decorator: fn(event: ServerMessage) for server messages.

        Optional filters: color=0xFF0000FF, predicate=lambda e: ...
        """

        def decorator(f):
            filt = _make_obj_filter(predicate, {"color": color})
            self._cb_client_message = _wrap_obj(f, filt) if filt else f
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

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
        """Decorator: fn(event) when a dialog is shown.

        Optional filters (all must match):
            dialog_type=InputDialog  – INPUT dialogs only
            dialog_id=32700          – specific dialog ID
            predicate=lambda d: "register" in d.title
        """

        def decorator(f: Callable[[D], Any]) -> Callable[[D], Any]:
            type_pred = (lambda obj: isinstance(obj, dialog_type)) if dialog_type is not None else None
            if type_pred is not None and predicate is not None:
                _p = predicate
                combined: Callable[[D], bool] | None = lambda obj: type_pred(obj) and _p(obj)
            else:
                combined = type_pred or predicate
            filt = _make_obj_filter(combined, {"dialog_id": dialog_id})
            self._cb_dialog = _wrap_obj(f, filt) if filt else f
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
        """Decorator: fn(event: GameText) for ShowGameText.

        Optional filters: style=, predicate=lambda e: ...
        """

        def decorator(f):
            filt = _make_obj_filter(predicate, {"style": style})
            self._cb_game_text = _wrap_obj(f, filt) if filt else f
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    def on_set_health[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: SetHealth)."""
        self._cb_set_health = fn
        return fn

    def on_set_armour[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: SetArmour)."""
        self._cb_set_armour = fn
        return fn

    def on_set_position[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: SetPosition)."""
        self._cb_set_position = fn
        return fn

    def on_checkpoint[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: Checkpoint)."""
        self._cb_checkpoint = fn
        return fn

    def on_checkpoint_disabled[F: Callable](self, fn: F) -> F:
        """Decorator: fn() when the checkpoint is disabled."""
        self._cb_checkpoint_disabled = fn
        return fn

    def on_player_streamed_in[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PlayerStreamIn)."""
        self._cb_player_streamed_in = fn
        return fn

    def on_player_streamed_out[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PlayerStreamOut)."""
        self._cb_player_streamed_out = fn
        return fn

    def on_player_name[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PlayerNameChange)."""
        self._cb_player_name = fn
        return fn

    def on_toggle_controllable[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: ToggleControllable)."""
        self._cb_toggle_controllable = fn
        return fn

    def on_player_time[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PlayerTime)."""
        self._cb_player_time = fn
        return fn

    def on_death_message[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: DeathMessage)."""
        self._cb_death_message = fn
        return fn

    def on_set_armed_weapon[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: SetArmedWeapon)."""
        self._cb_set_armed_weapon = fn
        return fn

    def on_spawn_info[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: SpawnInfo)."""
        self._cb_spawn_info = fn
        return fn

    def on_player_team[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PlayerTeam)."""
        self._cb_player_team = fn
        return fn

    def on_put_in_vehicle[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PutInVehicle)."""
        self._cb_put_in_vehicle = fn
        return fn

    def on_remove_from_vehicle[F: Callable](self, fn: F) -> F:
        """Decorator: fn() when removed from vehicle."""
        self._cb_remove_from_vehicle = fn
        return fn

    def on_player_color[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PlayerColor)."""
        self._cb_player_color = fn
        return fn

    def on_world_time[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: WorldTime)."""
        self._cb_world_time = fn
        return fn

    def on_toggle_spectating[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: ToggleSpectating)."""
        self._cb_toggle_spectating = fn
        return fn

    def on_wanted_level[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: WantedLevel)."""
        self._cb_wanted_level = fn
        return fn

    def on_weapon_ammo[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: WeaponAmmo)."""
        self._cb_weapon_ammo = fn
        return fn

    def on_gravity[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: Gravity)."""
        self._cb_gravity = fn
        return fn

    def on_weather[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: Weather)."""
        self._cb_weather = fn
        return fn

    def on_player_skin[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PlayerSkin)."""
        self._cb_player_skin = fn
        return fn

    def on_set_interior[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: SetInterior)."""
        self._cb_set_interior = fn
        return fn

    def on_vehicle_streamed_in[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: VehicleStreamIn)."""
        self._cb_vehicle_streamed_in = fn
        return fn

    def on_vehicle_streamed_out[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: VehicleStreamOut)."""
        self._cb_vehicle_streamed_out = fn
        return fn

    def on_player_death[F: Callable](self, fn: F) -> F:
        """Decorator: fn(event: PlayerDeath)."""
        self._cb_player_death = fn
        return fn

    # ── Connection lifecycle ───────────────────────────────────────────────────

    async def start(self, timeout: float = 15.0) -> bool:
        """Connect and spawn the background receive/keepalive thread.
        Returns True on success.  After this returns, events begin flowing.
        """
        loop = asyncio.get_running_loop()
        self._loop = loop
        self._setup_callbacks(loop)
        return await loop.run_in_executor(None, lambda: self._client.start(timeout))

    async def disconnect(self) -> None:
        """Send disconnect notification and stop the receive loop."""
        self._client.disconnect()

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
                if event[0] == "disconnect":
                    return
                if event[0] == "rpc":
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
        - ``('dialog', AnyDialog)``
        - ``('game_text', GameText)``
        - ``('set_health', SetHealth)``
        - ``('set_armour', SetArmour)``
        - ``('set_position', SetPosition)``
        - ``('checkpoint', Checkpoint)``
        - ``('checkpoint_disabled',)``
        - ``('player_streamed_in', PlayerStreamIn)``
        - ``('player_streamed_out', PlayerStreamOut)``
        - ``('player_name', PlayerNameChange)``
        - ``('toggle_controllable', ToggleControllable)``
        - ``('player_time', PlayerTime)``
        - ``('death_message', DeathMessage)``
        - ``('set_armed_weapon', SetArmedWeapon)``
        - ``('spawn_info', SpawnInfo)``
        - ``('player_team', PlayerTeam)``
        - ``('put_in_vehicle', PutInVehicle)``
        - ``('remove_from_vehicle',)``
        - ``('player_color', PlayerColor)``
        - ``('world_time', WorldTime)``
        - ``('toggle_spectating', ToggleSpectating)``
        - ``('wanted_level', WantedLevel)``
        - ``('weapon_ammo', WeaponAmmo)``
        - ``('gravity', Gravity)``
        - ``('weather', Weather)``
        - ``('player_skin', PlayerSkin)``
        - ``('set_interior', SetInterior)``
        - ``('vehicle_streamed_in', VehicleStreamIn)``
        - ``('vehicle_streamed_out', VehicleStreamOut)``
        - ``('player_death', PlayerDeath)``

        Stops after yielding ``('disconnect',)``.
        """
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield event
                if event[0] == "disconnect":
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
                if event[0] == "disconnect":
                    return
                if event[0] == tag:
                    yield event[1]
        finally:
            self._subscribers.remove(q)

    def chat(self):
        """Async generator yielding ChatMessage for each public chat message."""
        return self._typed_gen("chat")

    def server_messages(self):
        """Async generator yielding ServerMessage for each client message."""
        return self._typed_gen("client_message")

    def dialogs(self):
        """Async generator yielding AnyDialog each time a dialog is shown."""
        return self._typed_gen("dialog")

    def game_texts(self):
        """Async generator yielding GameText for each ShowGameText."""
        return self._typed_gen("game_text")

    def player_joins(self):
        """Async generator yielding PlayerJoin for each connecting player."""
        return self._typed_gen("player_join")

    def player_quits(self):
        """Async generator yielding PlayerQuit for each disconnecting player."""
        return self._typed_gen("player_quit")

    def player_stream_ins(self):
        """Async generator yielding PlayerStreamIn."""
        return self._typed_gen("player_streamed_in")

    def player_stream_outs(self):
        """Async generator yielding PlayerStreamOut."""
        return self._typed_gen("player_streamed_out")

    def player_name_changes(self):
        """Async generator yielding PlayerNameChange."""
        return self._typed_gen("player_name")

    def death_messages(self):
        """Async generator yielding DeathMessage."""
        return self._typed_gen("death_message")

    def spawn_infos(self):
        """Async generator yielding SpawnInfo."""
        return self._typed_gen("spawn_info")

    def put_in_vehicles(self):
        """Async generator yielding PutInVehicle."""
        return self._typed_gen("put_in_vehicle")

    def player_colors(self):
        """Async generator yielding PlayerColor."""
        return self._typed_gen("player_color")

    def weather_changes(self):
        """Async generator yielding Weather."""
        return self._typed_gen("weather")

    def gravity_changes(self):
        """Async generator yielding Gravity."""
        return self._typed_gen("gravity")

    def player_skins(self):
        """Async generator yielding PlayerSkin."""
        return self._typed_gen("player_skin")

    def interior_changes(self):
        """Async generator yielding SetInterior."""
        return self._typed_gen("set_interior")

    def vehicle_stream_ins(self):
        """Async generator yielding VehicleStreamIn."""
        return self._typed_gen("vehicle_streamed_in")

    def vehicle_stream_outs(self):
        """Async generator yielding VehicleStreamOut."""
        return self._typed_gen("vehicle_streamed_out")

    def player_deaths(self):
        """Async generator yielding PlayerDeath."""
        return self._typed_gen("player_death")

    async def wait_for_rpc(
        self, rpc_id: int, *, predicate: Callable[[int, bytes], bool] | None = None
    ) -> bytes:
        """Await the next RPC with the given ID and return its payload bytes."""
        async for _, data in self.rpcs(rpc_id=rpc_id):
            if predicate is None or predicate(rpc_id, data):
                return data

    async def wait_for_dialog[D: (MsgboxDialog, InputDialog, PasswordDialog, ListDialog, TablistDialog, TablistHeadersDialog)](
        self,
        predicate: Callable[[D], bool] | None = None,
        *,
        dialog_type: type[D] | None = None,
        dialog_id: int | None = None,
    ) -> D:
        """Await the next dialog matching all given filters.

        Optional filters (all must match):
            dialog_type=InputDialog  – INPUT dialogs only
            dialog_id=32700          – specific dialog ID
            predicate=lambda d: "register" in d.title
        """
        type_pred = (lambda obj: isinstance(obj, dialog_type)) if dialog_type is not None else None
        if type_pred is not None and predicate is not None:
            _p = predicate
            combined: Callable[[D], bool] | None = lambda obj: type_pred(obj) and _p(obj)
        else:
            combined = type_pred or predicate
        filt = _make_obj_filter(combined, {"dialog_id": dialog_id})
        async for dlg in self.dialogs():
            if filt is None or filt(dlg):
                return dlg  # type: ignore[return-value]

    async def wait_for_chat(
        self,
        predicate: Callable[[ChatMessage], bool] | None = None,
        *,
        player_id: int | None = None,
    ) -> ChatMessage:
        """Await the next public chat message matching all given filters."""
        filt = _make_obj_filter(predicate, {"player_id": player_id})
        async for msg in self.chat():
            if filt is None or filt(msg):
                return msg

    async def wait_for_client_message(
        self,
        predicate: Callable[[ServerMessage], bool] | None = None,
        *,
        color: int | None = None,
    ) -> ServerMessage:
        """Await the next server message matching all given filters."""
        filt = _make_obj_filter(predicate, {"color": color})
        async for msg in self.server_messages():
            if filt is None or filt(msg):
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
        async for evt in self.player_joins():
            if filt is None or filt(evt):
                return evt

    # ── Game actions ───────────────────────────────────────────────────────────
    # Sending a UDP packet is fast — no executor or await needed.

    def send_rpc(
        self, rpc_id: int, data: bytes = b"", reliability: int = RELIABLE
    ) -> bool:
        return self._client.send_rpc(rpc_id, data, reliability)

    def send_chat(self, message: str) -> None:
        """Send a public chat message (RPC 101)."""
        msg = message.encode("ascii", errors="replace")[:144]
        self.send_rpc(RPC_CHAT, struct.pack("B", len(msg)) + msg)

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

    # ── State ──────────────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    @property
    def player_id(self) -> int:
        return self._client.player_id


# Backwards-compatibility alias
SAMPClient = SAMPBot
