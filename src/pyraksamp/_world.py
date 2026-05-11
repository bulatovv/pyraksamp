"""World-state objects: Player and Vehicle."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ['Player', 'Vehicle']


@dataclass(slots=True)
class Player:
    """Last-known state for a streamed-in player.

    Populated on :class:`PlayerStreamIn` and kept current by subsequent
    state-change events (team, color, skin, name).  Removed from
    :attr:`SAMPBot.players` on :class:`PlayerStreamOut`.
    """

    player_id: int
    name: str | None  # None until a PlayerJoin or PlayerNameChange is seen
    team: int
    skin: int
    x: float
    y: float
    z: float
    rotation: float
    color: int  # 0xRRGGBBAA
    fight_style: int


@dataclass(slots=True)
class Vehicle:
    """Last-known state for a streamed-in vehicle.

    Populated on :class:`VehicleStreamIn`.  Removed from
    :attr:`SAMPBot.vehicles` on :class:`VehicleStreamOut`.
    Vehicle health is a float (wire format for vehicles in SA:MP).
    """

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
