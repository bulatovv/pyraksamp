"""Typed event objects yielded by SAMPBot's async generators."""

from dataclasses import dataclass

__all__ = [
    "ChatMessage",
    "ServerMessage",
    "Dialog",
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


@dataclass
class ChatMessage:
    """Public chat message sent by another player."""

    player_id: int
    text: str


@dataclass
class ServerMessage:
    """Coloured server message (SendClientMessage)."""

    color: int  # 0xRRGGBBAA
    text: str


@dataclass
class Dialog:
    """ShowPlayerDialog — style constants match SA:MP DIALOG_STYLE_*."""

    dialog_id: int
    style: int  # 0=MSGBOX 1=INPUT 2=LIST 3=PASSWORD
    title: str
    button1: str
    button2: str  # empty string means no second button
    body: str  # Huffman-decoded body / list contents


@dataclass
class GameText:
    """ShowGameText — appears on-screen in a GTA text style."""

    style: int
    duration_ms: int
    text: str


@dataclass
class PlayerJoin:
    """Player connected to the server (RPC_SERVER_JOIN)."""

    player_id: int
    name: str
    is_npc: bool = False  # NOTE: is_npc not preserved by current server join handler


@dataclass
class PlayerQuit:
    """Player disconnected from the server (RPC_SERVER_QUIT)."""

    player_id: int
    reason: int  # 0=timeout 1=quit 2=kick


@dataclass
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


@dataclass
class PlayerStreamOut:
    """Player streamed out of proximity (RPC_WORLD_PLAYER_REMOVE)."""

    player_id: int


@dataclass
class SetHealth:
    """Server set our health (SetPlayerHealth)."""

    health: float


@dataclass
class SetArmour:
    """Server set our armour (SetPlayerArmour)."""

    armour: float


@dataclass
class SetPosition:
    """Server teleported us (SetPlayerPos)."""

    x: float
    y: float
    z: float


@dataclass
class Checkpoint:
    """Server created a checkpoint (SetPlayerCheckpoint)."""

    x: float
    y: float
    z: float
    size: float


@dataclass(frozen=True)
class PlayerNameChange:
    """Server changed a player's name (RPC_SET_PLAYER_NAME)."""

    player_id: int
    name: str
    success: int


@dataclass(frozen=True)
class ToggleControllable:
    """Server toggled player controllable state."""

    moveable: int


@dataclass(frozen=True)
class PlayerTime:
    """Server set player time."""

    hour: int
    minute: int


@dataclass(frozen=True)
class DeathMessage:
    """Server broadcast a death message."""

    killer_id: int
    player_id: int
    weapon: int


@dataclass(frozen=True)
class SetArmedWeapon:
    """Server set the player's armed weapon."""

    weapon_id: int


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class PlayerTeam:
    """Server set a player's team."""

    player_id: int
    team: int


@dataclass(frozen=True)
class PutInVehicle:
    """Server put us in a vehicle."""

    vehicle_id: int
    seat_id: int


@dataclass(frozen=True)
class PlayerColor:
    """Server set a player's color."""

    player_id: int
    color: int


@dataclass(frozen=True)
class WorldTime:
    """Server set the world time."""

    hour: int


@dataclass(frozen=True)
class ToggleSpectating:
    """Server toggled spectating mode."""

    spectating: bool


@dataclass(frozen=True)
class WantedLevel:
    """Server set our wanted level."""

    level: int


@dataclass(frozen=True)
class WeaponAmmo:
    """Server set ammo for a weapon slot."""

    weapon_id: int
    ammo: int


@dataclass(frozen=True)
class Gravity:
    """Server set world gravity."""

    gravity: float


@dataclass(frozen=True)
class Weather:
    """Server set world weather."""

    weather_id: int


@dataclass(frozen=True)
class PlayerSkin:
    """Server set a player's skin."""

    player_id: int
    skin_id: int


@dataclass(frozen=True)
class SetInterior:
    """Server set our interior."""

    interior_id: int


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class VehicleStreamOut:
    """Vehicle streamed out of proximity (WorldVehicleRemove)."""

    vehicle_id: int


@dataclass(frozen=True)
class PlayerDeath:
    """Server broadcast a player death (DeathBroadcast)."""

    player_id: int
