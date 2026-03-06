"""_EventStreams — async generators and wait_for_* helpers."""

import asyncio
from collections.abc import Callable

from pyraksamp._bus import _EventBus
from pyraksamp._utils import _make_obj_filter
from pyraksamp.dialogs import (
    AnyDialog,
    MsgboxDialog,
    InputDialog,
    PasswordDialog,
    ListDialog,
    TablistDialog,
    TablistHeadersDialog,
)
from pyraksamp.events import ChatMessage, PlayerJoin, ServerMessage


class _EventStreams:
    """Provides async generators and wait_for_* methods backed by _EventBus."""

    def __init__(self, bus: _EventBus) -> None:
        self._bus = bus

    # ── Generic event streams ──────────────────────────────────────────────────

    async def rpcs(self, rpc_id: int | None = None):
        """Async generator yielding ``(rpc_id, data)`` for raw RPCs.

        Each call creates an independent subscriber; concurrent consumers all
        receive every event (fan-out, no stealing).

        Parameters
        ----------
        rpc_id
            If given, yield only RPCs matching this ID.

        See Also
        --------
        events : Low-level generator that yields all event tuples.
        wait_for_rpc : Await a single matching RPC.
        """
        q: asyncio.Queue = asyncio.Queue()
        self._bus._subscribers.append(q)
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
            self._bus._subscribers.remove(q)

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

        See Also
        --------
        rpcs : Specialized generator for raw RPCs.
        chat : Typed generator for chat messages.
        dialogs : Typed generator for dialogs.
        """
        q: asyncio.Queue = asyncio.Queue()
        self._bus._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                yield event
                if event[0] == "disconnect":
                    return
        finally:
            self._bus._subscribers.remove(q)

    # ── Typed async generators ─────────────────────────────────────────────────

    async def _typed_gen(self, tag: str):
        q: asyncio.Queue = asyncio.Queue()
        self._bus._subscribers.append(q)
        try:
            while True:
                event = await q.get()
                if event[0] == "disconnect":
                    return
                if event[0] == tag:
                    yield event[1]
        finally:
            self._bus._subscribers.remove(q)

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

    # ── Wait-for helpers ───────────────────────────────────────────────────────

    async def wait_for_rpc(
        self, rpc_id: int, *, predicate: Callable[[int, bytes], bool] | None = None
    ) -> bytes:
        """Await the next RPC with the given ID.

        Parameters
        ----------
        rpc_id
            The RPC ID to wait for.
        predicate
            Optional additional filter; called with ``(rpc_id, data)``.

        Returns
        -------
            Raw payload bytes of the matching RPC.
        """
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

        Parameters
        ----------
        predicate
            Optional filter; called with the dialog object.
        dialog_type
            Only match dialogs of this type (e.g. ``InputDialog``).
        dialog_id
            Only match dialogs with this ID.

        Returns
        -------
            The matched dialog.
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
        """Await the next public chat message matching all given filters.

        Parameters
        ----------
        predicate
            Optional filter; called with the message.
        player_id
            Only match messages from this player.

        Returns
        -------
            The matched chat message.
        """
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
        """Await the next server message matching all given filters.

        Parameters
        ----------
        predicate
            Optional filter; called with the message.
        color
            Only match messages with this color value.

        Returns
        -------
            The matched server message.
        """
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
        """Await the next player join matching all given filters.

        Parameters
        ----------
        predicate
            Optional filter; called with the event.
        player_id
            Only match this player's ID.
        name
            Only match this player's name.

        Returns
        -------
            The matched player join event.
        """
        filt = _make_obj_filter(predicate, {"player_id": player_id, "name": name})
        async for evt in self.player_joins():
            if filt is None or filt(evt):
                return evt
