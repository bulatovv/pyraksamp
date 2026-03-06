"""Typed event objects yielded by SAMPBot's async generators."""

from dataclasses import dataclass

__all__ = [
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


@dataclass(slots=True, frozen=True)
class ChatMessage:
    """Public chat message sent by another player."""

    player_id: int
    text: str


@dataclass(slots=True, frozen=True)
class ServerMessage:
    """Coloured server message (SendClientMessage)."""

    color: int  # 0xRRGGBBAA
    text: str


@dataclass(slots=True, frozen=True)
class GameText:
    """ShowGameText — appears on-screen in a GTA text style."""

    style: int
    duration_ms: int
    text: str


@dataclass(slots=True, frozen=True)
class PlayerJoin:
    """Player connected to the server (RPC_SERVER_JOIN)."""

    player_id: int
    name: str
    is_npc: bool = False  # NOTE: is_npc not preserved by current server join handler


@dataclass(slots=True, frozen=True)
class PlayerQuit:
    """Player disconnected from the server (RPC_SERVER_QUIT)."""

    player_id: int
    reason: int  # 0=timeout 1=quit 2=kick


@dataclass(slots=True, frozen=True)
class PlayerStreamIn:
    """Player streamed into proximity (RPC_WORLD_PLAYER_ADD)."""

    player_id: int
    team: int
    skin: int
    x: float
    y: float
    z: float
    rotation: float
    color: int  # 0xRRGGBBAA
    fight_style: int


@dataclass(slots=True, frozen=True)
class PlayerStreamOut:
    """Player streamed out of proximity (RPC_WORLD_PLAYER_REMOVE)."""

    player_id: int


@dataclass(slots=True, frozen=True)
class SetHealth:
    """Server set our health (SetPlayerHealth)."""

    health: float


@dataclass(slots=True, frozen=True)
class SetArmour:
    """Server set our armour (SetPlayerArmour)."""

    armour: float


@dataclass(slots=True, frozen=True)
class SetPosition:
    """Server teleported us (SetPlayerPos)."""

    x: float
    y: float
    z: float


@dataclass(slots=True, frozen=True)
class Checkpoint:
    """Server created a checkpoint (SetPlayerCheckpoint)."""

    x: float
    y: float
    z: float
    size: float


@dataclass(slots=True, frozen=True)
class PlayerNameChange:
    """Server changed a player's name (RPC_SET_PLAYER_NAME)."""

    player_id: int
    name: str
    success: int


@dataclass(slots=True, frozen=True)
class ToggleControllable:
    """Server toggled player controllable state."""

    moveable: int


@dataclass(slots=True, frozen=True)
class PlayerTime:
    """Server set player time."""

    hour: int
    minute: int


@dataclass(slots=True, frozen=True)
class DeathMessage:
    """Server broadcast a death message."""

    killer_id: int
    player_id: int
    weapon: int


@dataclass(slots=True, frozen=True)
class SetArmedWeapon:
    """Server set the player's armed weapon."""

    weapon_id: int


@dataclass(slots=True, frozen=True)
class SpawnInfo:
    """Server sent spawn info (SetSpawnInfo)."""

    team: int
    skin: int
    x: float
    y: float
    z: float
    rotation: float
    weapons: tuple
    ammo: tuple


@dataclass(slots=True, frozen=True)
class PlayerTeam:
    """Server set a player's team."""

    player_id: int
    team: int


@dataclass(slots=True, frozen=True)
class PutInVehicle:
    """Server put us in a vehicle."""

    vehicle_id: int
    seat_id: int


@dataclass(slots=True, frozen=True)
class PlayerColor:
    """Server set a player's color."""

    player_id: int
    color: int


@dataclass(slots=True, frozen=True)
class WorldTime:
    """Server set the world time."""

    hour: int


@dataclass(slots=True, frozen=True)
class ToggleSpectating:
    """Server toggled spectating mode."""

    spectating: bool


@dataclass(slots=True, frozen=True)
class WantedLevel:
    """Server set our wanted level."""

    level: int


@dataclass(slots=True, frozen=True)
class WeaponAmmo:
    """Server set ammo for a weapon slot."""

    weapon_id: int
    ammo: int


@dataclass(slots=True, frozen=True)
class Gravity:
    """Server set world gravity."""

    gravity: float


@dataclass(slots=True, frozen=True)
class Weather:
    """Server set world weather."""

    weather_id: int


@dataclass(slots=True, frozen=True)
class PlayerSkin:
    """Server set a player's skin."""

    player_id: int
    skin_id: int


@dataclass(slots=True, frozen=True)
class SetInterior:
    """Server set our interior."""

    interior_id: int


@dataclass(slots=True, frozen=True)
class VehicleStreamIn:
    """Vehicle streamed into proximity (WorldVehicleAdd)."""

    vehicle_id: int
    model: int
    x: float
    y: float
    z: float
    angle: float
    color1: int
    color2: int
    health: float
    interior: int
    door_damage: int
    panel_damage: int
    light_damage: int
    tire_damage: int
    add_siren: bool
    paintjob: int
    body_color1: int
    body_color2: int


@dataclass(slots=True, frozen=True)
class VehicleStreamOut:
    """Vehicle streamed out of proximity (WorldVehicleRemove)."""

    vehicle_id: int


@dataclass(slots=True, frozen=True)
class PlayerDeath:
    """Server broadcast a player death (DeathBroadcast)."""

    player_id: int
