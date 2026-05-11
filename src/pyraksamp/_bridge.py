"""_setup_bridge — wires _SAMPClient Rust callbacks to _EventBus."""

import asyncio
from collections.abc import Callable

from pyraksamp._world import Player, Vehicle
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
    SetVirtualWorld,
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


def _setup_bridge(
    client,
    bus,
    make_dialog: Callable,
    loop: asyncio.AbstractEventLoop,
    encoding: str = 'utf-8',
    *,
    players: dict | None = None,
    vehicles: dict | None = None,
    player_names: dict | None = None,
) -> None:
    """Wire all _SAMPClient Rust callbacks to the asyncio event loop via _EventBus.

    The Rust run() thread invokes these callbacks with the GIL held; we must
    not block.  All work is scheduled onto the loop via call_soon_threadsafe so
    that broadcasts execute in the event loop thread.
    """

    def on_connect():
        loop.call_soon_threadsafe(lambda: bus.broadcast(('connect',)))

    def on_disconnect():
        if players is not None:
            players.clear()
        if vehicles is not None:
            vehicles.clear()
        if player_names is not None:
            player_names.clear()
        loop.call_soon_threadsafe(lambda: bus.broadcast(('disconnect',)))

    def on_rpc(rpc_id: int, data: bytes):
        loop.call_soon_threadsafe(lambda: bus.broadcast(('rpc', rpc_id, data)))

    def on_player_join(pid: int, name: str):
        if player_names is not None:
            player_names[pid] = name
        if players is not None and pid in players:
            players[pid].name = name
        evt = PlayerJoin(player_id=pid, name=name)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_join', evt)))

    def on_player_quit(pid: int, reason: int):
        if players is not None:
            players.pop(pid, None)
        if player_names is not None:
            player_names.pop(pid, None)
        evt = PlayerQuit(player_id=pid, reason=reason)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_quit', evt)))

    def on_chat(pid: int, raw: bytes):
        from pyraksamp.colors import ColoredString

        evt = ChatMessage(
            player_id=pid,
            raw=raw,
            text=ColoredString(raw.decode(encoding, errors='replace')),
        )
        loop.call_soon_threadsafe(lambda: bus.broadcast(('chat', evt)))

    def on_client_message(color: int, raw: bytes):
        from pyraksamp.colors import ColoredString

        evt = ServerMessage(
            color=color,
            raw=raw,
            text=ColoredString(raw.decode(encoding, errors='replace')),
        )
        loop.call_soon_threadsafe(lambda: bus.broadcast(('client_message', evt)))

    def on_dialog(
        did: int,
        style: int,
        raw_title: bytes,
        raw_btn1: bytes,
        raw_btn2: bytes,
        raw_body: bytes,
    ):
        def dec(b):
            return b.decode(encoding, errors='replace')

        evt = make_dialog(
            did, style, dec(raw_title), dec(raw_btn1), dec(raw_btn2), dec(raw_body)
        )
        loop.call_soon_threadsafe(lambda: bus.broadcast(('dialog', evt)))

    def on_game_text(style: int, ms: int, text: str):
        evt = GameText(style=style, duration_ms=ms, text=text)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('game_text', evt)))

    def on_set_health(hp: float):
        evt = SetHealth(health=hp)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('set_health', evt)))

    def on_set_armour(arm: float):
        evt = SetArmour(armour=arm)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('set_armour', evt)))

    def on_set_position(x: float, y: float, z: float):
        evt = SetPosition(x=x, y=y, z=z)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('set_position', evt)))

    def on_checkpoint(x: float, y: float, z: float, size: float):
        evt = Checkpoint(x=x, y=y, z=z, size=size)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('checkpoint', evt)))

    def on_checkpoint_disabled():
        loop.call_soon_threadsafe(lambda: bus.broadcast(('checkpoint_disabled',)))

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
        if players is not None:
            players[pid] = Player(
                player_id=pid,
                name=player_names.get(pid) if player_names is not None else None,
                team=team,
                skin=skin,
                x=x,
                y=y,
                z=z,
                rotation=rot,
                color=color,
                fight_style=fs,
            )
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
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_streamed_in', evt)))

    def on_player_streamed_out(pid: int):
        if players is not None:
            players.pop(pid, None)
        evt = PlayerStreamOut(player_id=pid)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_streamed_out', evt)))

    def on_player_name(pid: int, name: str, success: int):
        if success and player_names is not None:
            player_names[pid] = name
        if success and players is not None and pid in players:
            players[pid].name = name
        evt = PlayerNameChange(player_id=pid, name=name, success=success)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_name', evt)))

    def on_toggle_controllable(moveable: int):
        evt = ToggleControllable(moveable=moveable)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('toggle_controllable', evt)))

    def on_player_time(hour: int, minute: int):
        evt = PlayerTime(hour=hour, minute=minute)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_time', evt)))

    def on_death_message(killer_id: int, player_id: int, weapon: int):
        evt = DeathMessage(killer_id=killer_id, player_id=player_id, weapon=weapon)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('death_message', evt)))

    def on_set_armed_weapon(weapon_id: int):
        evt = SetArmedWeapon(weapon_id=weapon_id)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('set_armed_weapon', evt)))

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
        loop.call_soon_threadsafe(lambda: bus.broadcast(('spawn_info', evt)))

    def on_player_team(pid: int, team: int):
        if players is not None and pid in players:
            players[pid].team = team
        evt = PlayerTeam(player_id=pid, team=team)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_team', evt)))

    def on_put_in_vehicle(vehicle_id: int, seat_id: int):
        evt = PutInVehicle(vehicle_id=vehicle_id, seat_id=seat_id)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('put_in_vehicle', evt)))

    def on_remove_from_vehicle():
        loop.call_soon_threadsafe(lambda: bus.broadcast(('remove_from_vehicle',)))

    def on_player_color(pid: int, color: int):
        if players is not None and pid in players:
            players[pid].color = color
        evt = PlayerColor(player_id=pid, color=color)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_color', evt)))

    def on_world_time(hour: int):
        evt = WorldTime(hour=hour)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('world_time', evt)))

    def on_toggle_spectating(spectating: bool):
        evt = ToggleSpectating(spectating=spectating)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('toggle_spectating', evt)))

    def on_wanted_level(level: int):
        evt = WantedLevel(level=level)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('wanted_level', evt)))

    def on_weapon_ammo(weapon_id: int, ammo: int):
        evt = WeaponAmmo(weapon_id=weapon_id, ammo=ammo)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('weapon_ammo', evt)))

    def on_gravity(gravity: float):
        evt = Gravity(gravity=gravity)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('gravity', evt)))

    def on_weather(weather_id: int):
        evt = Weather(weather_id=weather_id)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('weather', evt)))

    def on_player_skin(pid: int, skin_id: int):
        if players is not None and pid in players:
            players[pid].skin = skin_id
        evt = PlayerSkin(player_id=pid, skin_id=skin_id)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_skin', evt)))

    def on_set_interior(interior_id: int):
        evt = SetInterior(interior_id=interior_id)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('set_interior', evt)))

    def on_set_virtual_world(world_id: int):
        evt = SetVirtualWorld(world_id=world_id)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('set_virtual_world', evt)))

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
        if vehicles is not None:
            vehicles[vid] = Vehicle(
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
        loop.call_soon_threadsafe(lambda: bus.broadcast(('vehicle_streamed_in', evt)))

    def on_vehicle_streamed_out(vid: int):
        if vehicles is not None:
            vehicles.pop(vid, None)
        evt = VehicleStreamOut(vehicle_id=vid)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('vehicle_streamed_out', evt)))

    def on_player_death(pid: int):
        evt = PlayerDeath(player_id=pid)
        loop.call_soon_threadsafe(lambda: bus.broadcast(('player_death', evt)))

    def on_textdraw_show(
        td_id: int,
        flags: int,
        lw: float,
        lh: float,
        lcol: int,
        linew: float,
        lineh: float,
        bcol: int,
        shadow: int,
        outline: int,
        bgcol: int,
        style: int,
        sel: int,
        x: float,
        y: float,
        model: int,
        rx: float,
        ry: float,
        rz: float,
        zoom: float,
        col1: int,
        col2: int,
        text: str,
    ):
        args = (
            td_id,
            flags,
            lw,
            lh,
            lcol,
            linew,
            lineh,
            bcol,
            shadow,
            outline,
            bgcol,
            style,
            sel,
            x,
            y,
            model,
            rx,
            ry,
            rz,
            zoom,
            col1,
            col2,
            text,
        )
        loop.call_soon_threadsafe(lambda: bus.broadcast(('textdraw_show', *args)))

    def on_textdraw_hide(td_id: int):
        loop.call_soon_threadsafe(lambda: bus.broadcast(('textdraw_hide', td_id)))

    def on_textdraw_edit(td_id: int, text: str):
        loop.call_soon_threadsafe(lambda: bus.broadcast(('textdraw_edit', td_id, text)))

    def on_textdraw_toggle_select(enable: bool, color: int):
        loop.call_soon_threadsafe(
            lambda: bus.broadcast(('textdraw_toggle_select', enable, color))
        )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_rpc = on_rpc
    client.on_player_join = on_player_join
    client.on_player_quit = on_player_quit
    client.on_chat = on_chat
    client.on_client_message = on_client_message
    client.on_dialog = on_dialog
    client.on_game_text = on_game_text
    client.on_set_health = on_set_health
    client.on_set_armour = on_set_armour
    client.on_set_position = on_set_position
    client.on_checkpoint = on_checkpoint
    client.on_checkpoint_disabled = on_checkpoint_disabled
    client.on_player_streamed_in = on_player_streamed_in
    client.on_player_streamed_out = on_player_streamed_out
    client.on_player_name = on_player_name
    client.on_toggle_controllable = on_toggle_controllable
    client.on_player_time = on_player_time
    client.on_death_message = on_death_message
    client.on_set_armed_weapon = on_set_armed_weapon
    client.on_spawn_info = on_spawn_info
    client.on_player_team = on_player_team
    client.on_put_in_vehicle = on_put_in_vehicle
    client.on_remove_from_vehicle = on_remove_from_vehicle
    client.on_player_color = on_player_color
    client.on_world_time = on_world_time
    client.on_toggle_spectating = on_toggle_spectating
    client.on_wanted_level = on_wanted_level
    client.on_weapon_ammo = on_weapon_ammo
    client.on_gravity = on_gravity
    client.on_weather = on_weather
    client.on_player_skin = on_player_skin
    client.on_set_interior = on_set_interior
    client.on_set_virtual_world = on_set_virtual_world
    client.on_vehicle_streamed_in = on_vehicle_streamed_in
    client.on_vehicle_streamed_out = on_vehicle_streamed_out
    client.on_player_death = on_player_death
    client.on_textdraw_show = on_textdraw_show
    client.on_textdraw_hide = on_textdraw_hide
    client.on_textdraw_edit = on_textdraw_edit
    client.on_textdraw_toggle_select = on_textdraw_toggle_select
