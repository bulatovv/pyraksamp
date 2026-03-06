"""_EventBus — owns callback slots, subscriber queues, and on_* decorators."""

import asyncio
from collections.abc import Callable
from typing import Any, overload

from pyraksamp._utils import _make_obj_filter, _wrap_obj
from pyraksamp.dialogs import (
    AnyDialog,
    MsgboxDialog,
    InputDialog,
    PasswordDialog,
    ListDialog,
    TablistDialog,
    TablistHeadersDialog,
)
from pyraksamp.events import (
    ChatMessage,
    ServerMessage,
    GameText,
    PlayerJoin,
    PlayerQuit,
)


class _EventBus:
    """Owns all callback slots and subscriber queues for SAMPBot."""

    def __init__(self) -> None:
        # Fan-out subscriber queues.  Each active rpcs()/events() call appends
        # its own queue here; broadcast() copies every event to all of them so
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

    # ── Internal dispatch ──────────────────────────────────────────────────────

    def subscribe(self, q: asyncio.Queue) -> None:
        """Register a queue to receive all broadcast events."""
        self._subscribers.append(q)

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Deregister a previously subscribed queue."""
        self._subscribers.remove(q)

    def broadcast(self, event: tuple) -> None:
        """Fan an event out to every active subscriber queue."""
        for q in self._subscribers:
            q.put_nowait(event)

    def fire(self, cb, *args) -> None:
        """Call a user callback (sync or async def) from the event loop thread."""
        if cb is None:
            return
        if asyncio.iscoroutinefunction(cb):
            asyncio.create_task(cb(*args))
        else:
            cb(*args)

    # ── Decorator-style callbacks ──────────────────────────────────────────────

    def on_connect[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the client connects."""
        self._cb_connect = fn
        return fn

    def on_disconnect[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the client disconnects."""
        self._cb_disconnect = fn
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
            If given, only invoke the callback for RPCs with this ID.
        predicate
            Additional filter; called with ``(rpc_id, data)``.
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
        """Register a callback invoked when a player joins.

        Parameters
        ----------
        player_id
            Only invoke when this player's ID matches.
        name
            Only invoke when the player's name matches.
        predicate
            Additional filter; called with the event.
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
        """Register a callback invoked when a player disconnects.

        Parameters
        ----------
        player_id
            Only invoke when this player's ID matches.
        predicate
            Additional filter; called with the event.
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
        """Register a callback invoked for public chat messages.

        Parameters
        ----------
        player_id
            Only invoke when the sender's player ID matches.
        predicate
            Additional filter; e.g. ``lambda e: e.text.startswith("!")``.
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
        """Register a callback invoked for server messages (SendClientMessage).

        Parameters
        ----------
        color
            Only invoke when the message color matches (e.g. ``0xFF0000FF``).
        predicate
            Additional filter; called with the event.
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
        """Register a callback invoked when a dialog is shown.

        Parameters
        ----------
        dialog_type
            Only invoke for dialogs of this type (e.g. ``InputDialog``).
        dialog_id
            Only invoke for dialogs with this ID.
        predicate
            Additional filter; called with the dialog object.
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
        """Register a callback invoked for ShowGameText.

        Parameters
        ----------
        style
            Only invoke when the text style matches.
        predicate
            Additional filter; called with the event.
        """

        def decorator(f):
            filt = _make_obj_filter(predicate, {"style": style})
            self._cb_game_text = _wrap_obj(f, filt) if filt else f
            return f

        if fn is not None:
            return decorator(fn)
        return decorator

    def on_set_health[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets our health."""
        self._cb_set_health = fn
        return fn

    def on_set_armour[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets our armour."""
        self._cb_set_armour = fn
        return fn

    def on_set_position[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server teleports us."""
        self._cb_set_position = fn
        return fn

    def on_checkpoint[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets a checkpoint."""
        self._cb_checkpoint = fn
        return fn

    def on_checkpoint_disabled[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the checkpoint is disabled."""
        self._cb_checkpoint_disabled = fn
        return fn

    def on_player_streamed_in[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a player streams into proximity."""
        self._cb_player_streamed_in = fn
        return fn

    def on_player_streamed_out[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a player streams out of proximity."""
        self._cb_player_streamed_out = fn
        return fn

    def on_player_name[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a player's name changes."""
        self._cb_player_name = fn
        return fn

    def on_toggle_controllable[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server toggles our controllable state."""
        self._cb_toggle_controllable = fn
        return fn

    def on_player_time[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets the player time."""
        self._cb_player_time = fn
        return fn

    def on_death_message[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a death message is broadcast."""
        self._cb_death_message = fn
        return fn

    def on_set_armed_weapon[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets our armed weapon."""
        self._cb_set_armed_weapon = fn
        return fn

    def on_spawn_info[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sends spawn info."""
        self._cb_spawn_info = fn
        return fn

    def on_player_team[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a player's team is set."""
        self._cb_player_team = fn
        return fn

    def on_put_in_vehicle[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when we are put in a vehicle."""
        self._cb_put_in_vehicle = fn
        return fn

    def on_remove_from_vehicle[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when we are removed from a vehicle."""
        self._cb_remove_from_vehicle = fn
        return fn

    def on_player_color[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a player's color is set."""
        self._cb_player_color = fn
        return fn

    def on_world_time[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets the world time."""
        self._cb_world_time = fn
        return fn

    def on_toggle_spectating[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server toggles spectating mode."""
        self._cb_toggle_spectating = fn
        return fn

    def on_wanted_level[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets our wanted level."""
        self._cb_wanted_level = fn
        return fn

    def on_weapon_ammo[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets weapon ammo."""
        self._cb_weapon_ammo = fn
        return fn

    def on_gravity[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets world gravity."""
        self._cb_gravity = fn
        return fn

    def on_weather[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets the weather."""
        self._cb_weather = fn
        return fn

    def on_player_skin[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a player's skin is set."""
        self._cb_player_skin = fn
        return fn

    def on_set_interior[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when the server sets our interior."""
        self._cb_set_interior = fn
        return fn

    def on_vehicle_streamed_in[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a vehicle streams into proximity."""
        self._cb_vehicle_streamed_in = fn
        return fn

    def on_vehicle_streamed_out[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a vehicle streams out of proximity."""
        self._cb_vehicle_streamed_out = fn
        return fn

    def on_player_death[F: Callable](self, fn: F) -> F:
        """Register a callback invoked when a player death is broadcast."""
        self._cb_player_death = fn
        return fn
