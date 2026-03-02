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
]


@dataclass
class ChatMessage:
    """Public chat message sent by another player."""
    player_id: int
    text: str


@dataclass
class ServerMessage:
    """Coloured server message (SendClientMessage)."""
    color: int    # 0xRRGGBBAA
    text: str


@dataclass
class Dialog:
    """ShowPlayerDialog — style constants match SA:MP DIALOG_STYLE_*."""
    dialog_id: int
    style: int      # 0=MSGBOX 1=INPUT 2=LIST 3=PASSWORD
    title: str
    button1: str
    button2: str    # empty string means no second button
    body: str       # Huffman-decoded body / list contents


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
    is_npc: bool = False    # NOTE: is_npc not preserved by current server join handler


@dataclass
class PlayerQuit:
    """Player disconnected from the server (RPC_SERVER_QUIT)."""
    player_id: int
    reason: int     # 0=timeout 1=quit 2=kick


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
    color: int      # 0xRRGGBBAA
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
