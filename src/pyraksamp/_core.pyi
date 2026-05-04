from collections.abc import Callable

RELIABLE: int
RELIABLE_ORDERED: int
RELIABLE_SEQUENCED: int
UNRELIABLE: int
UNRELIABLE_SEQUENCED: int

RPC_CHAT: int
RPC_CLIENT_JOIN: int
RPC_CLIENT_MESSAGE: int
RPC_CLICK_TEXTDRAW: int
RPC_CONNECTION_REJ: int
RPC_DEATH: int
RPC_DEATH_BROADCAST: int
RPC_DIALOG_BOX: int
RPC_DIALOG_RESPONSE: int
RPC_DISABLE_CHECKPOINT: int
RPC_ENTER_VEHICLE: int
RPC_EXIT_VEHICLE: int
RPC_GAME_TEXT: int
RPC_INIT_GAME: int
RPC_PUT_IN_VEHICLE: int
RPC_REMOVE_FROM_VEHICLE: int
RPC_REQUEST_CLASS: int
RPC_REQUEST_SPAWN: int
RPC_SEND_DEATH_MESSAGE: int
RPC_SERVER_COMMAND: int
RPC_SERVER_JOIN: int
RPC_SERVER_QUIT: int
RPC_SET_ARMED_WEAPON: int
RPC_SET_ARMOUR: int
RPC_SET_CHECKPOINT: int
RPC_SET_GRAVITY: int
RPC_SET_HEALTH: int
RPC_SET_INTERIOR: int
RPC_SET_PLAYER_COLOR: int
RPC_SET_PLAYER_NAME: int
RPC_SET_PLAYER_SKIN: int
RPC_SET_PLAYER_TEAM: int
RPC_SET_PLAYER_TIME: int
RPC_SET_POSITION: int
RPC_SET_SPAWN_INFO: int
RPC_SET_WANTED_LEVEL: int
RPC_SET_WEAPON_AMMO: int
RPC_SET_WEATHER: int
RPC_SET_WORLD_TIME: int
RPC_SPAWN: int
RPC_TEXTDRAW_EDIT: int
RPC_TEXTDRAW_HIDE: int
RPC_TEXTDRAW_SHOW: int
RPC_TOGGLE_CONTROLLABLE: int
RPC_TOGGLE_SPECTATING: int
RPC_WORLD_PLAYER_ADD: int
RPC_WORLD_PLAYER_REMOVE: int
RPC_WORLD_VEHICLE_ADD: int
RPC_WORLD_VEHICLE_REMOVE: int

ID_AUTH_KEY: int
ID_CONNECTED_PONG: int
ID_CONNECTION_ATTEMPT_FAILED: int
ID_CONNECTION_BANNED: int
ID_CONNECTION_LOST: int
ID_CONNECTION_REQUEST: int
ID_CONNECTION_REQUEST_ACCEPTED: int
ID_DISCONNECTION_NOTIFICATION: int
ID_INTERNAL_PING: int
ID_INVALID_PASSWORD: int
ID_NEW_INCOMING_CONNECTION: int
ID_NO_FREE_INCOMING_CONNECTIONS: int
ID_OPEN_CONNECTION_COOKIE: int
ID_OPEN_CONNECTION_REPLY: int
ID_OPEN_CONNECTION_REQUEST: int
ID_RPC: int

class SAMPClient:
    player_id: int
    is_connected: bool

    def __init__(
        self,
        host: str,
        port: int,
        nickname: str,
        password: str = "",
        gpci: str = "",
        proxy_host: str | None = None,
        proxy_port: int | None = None,
        proxy_username: str | None = None,
        proxy_password: str | None = None,
    ) -> None: ...

    def start(self, timeout: float = 15.0) -> bool: ...
    def stop(self) -> None: ...
    def disconnect(self) -> None: ...
    def send_rpc(self, rpc_id: int, data: bytes | None = None, reliability: int = 8) -> bool: ...
    def send_command(self, text: bytes) -> None: ...
    def send_dialog_response(self, dialog_id: int, button: int, list_item: int = 0, text: bytes | None = None) -> None: ...
    def send_death(self, weapon_id: int = 0, killer_id: int = 65535) -> None: ...
    def send_enter_vehicle(self, vehicle_id: int, is_passenger: bool = False) -> None: ...
    def send_exit_vehicle(self, vehicle_id: int) -> None: ...
    def set_keys(self, keys: int, lr_analog: int = 0, ud_analog: int = 0) -> None: ...
    def click_textdraw(self, textdraw_id: int) -> None: ...

    on_connect: Callable[..., None]
    on_disconnect: Callable[..., None]
    on_rpc: Callable[..., None]
    on_player_join: Callable[..., None]
    on_player_quit: Callable[..., None]
    on_chat: Callable[..., None]
    on_client_message: Callable[..., None]
    on_dialog: Callable[..., None]
    on_game_text: Callable[..., None]
    on_set_health: Callable[..., None]
    on_set_armour: Callable[..., None]
    on_set_position: Callable[..., None]
    on_checkpoint: Callable[..., None]
    on_checkpoint_disabled: Callable[..., None]
    on_player_streamed_in: Callable[..., None]
    on_player_streamed_out: Callable[..., None]
    on_player_name: Callable[..., None]
    on_toggle_controllable: Callable[..., None]
    on_player_time: Callable[..., None]
    on_death_message: Callable[..., None]
    on_set_armed_weapon: Callable[..., None]
    on_spawn_info: Callable[..., None]
    on_player_team: Callable[..., None]
    on_put_in_vehicle: Callable[..., None]
    on_remove_from_vehicle: Callable[..., None]
    on_player_color: Callable[..., None]
    on_world_time: Callable[..., None]
    on_toggle_spectating: Callable[..., None]
    on_wanted_level: Callable[..., None]
    on_weapon_ammo: Callable[..., None]
    on_gravity: Callable[..., None]
    on_weather: Callable[..., None]
    on_player_skin: Callable[..., None]
    on_set_interior: Callable[..., None]
    on_set_virtual_world: Callable[..., None]
    on_vehicle_streamed_in: Callable[..., None]
    on_vehicle_streamed_out: Callable[..., None]
    on_player_death: Callable[..., None]
    on_textdraw_show: Callable[..., None]
    on_textdraw_hide: Callable[..., None]
    on_textdraw_edit: Callable[..., None]
    on_textdraw_toggle_select: Callable[..., None]
