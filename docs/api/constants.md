# Constants

::: pyraksamp.Keys

## Reliability flags

| Constant | Description |
|---|---|
| `pyraksamp.UNRELIABLE` | No delivery guarantee, no ordering |
| `pyraksamp.UNRELIABLE_SEQUENCED` | No delivery guarantee, newer packets discard older ones |
| `pyraksamp.RELIABLE` | Guaranteed delivery, unordered |
| `pyraksamp.RELIABLE_ORDERED` | Guaranteed delivery, ordered per channel |
| `pyraksamp.RELIABLE_SEQUENCED` | Guaranteed delivery of latest packet only |

## RPC IDs — server → client

| Constant | Value | Description |
|---|---|---|
| `RPC_SERVER_JOIN` | — | Player joined the server |
| `RPC_SERVER_QUIT` | — | Player left the server |
| `RPC_INIT_GAME` | — | Initial world state on connect |
| `RPC_CHAT` | — | Public chat message |
| `RPC_CLIENT_MESSAGE` | — | Coloured server message |
| `RPC_DIALOG_BOX` | — | Show dialog |
| `RPC_GAME_TEXT` | — | Show game text |
| `RPC_SET_HEALTH` | — | Set player health |
| `RPC_SET_ARMOUR` | — | Set player armour |
| `RPC_SET_POSITION` | — | Teleport player |
| `RPC_SET_CHECKPOINT` | — | Set checkpoint |
| `RPC_DISABLE_CHECKPOINT` | — | Disable checkpoint |
| `RPC_WORLD_PLAYER_ADD` | — | Player streamed in |
| `RPC_WORLD_PLAYER_REMOVE` | — | Player streamed out |
| `RPC_CONNECTION_REJ` | — | Connection rejected |
| `RPC_SET_PLAYER_NAME` | — | Player name changed |
| `RPC_TOGGLE_CONTROLLABLE` | — | Toggle player controllable |
| `RPC_SET_PLAYER_TIME` | — | Set player time |
| `RPC_SEND_DEATH_MESSAGE` | — | Death message broadcast |
| `RPC_SET_ARMED_WEAPON` | — | Set armed weapon |
| `RPC_SET_SPAWN_INFO` | — | Spawn info |
| `RPC_SET_PLAYER_TEAM` | — | Set player team |
| `RPC_PUT_IN_VEHICLE` | — | Put player in vehicle |
| `RPC_REMOVE_FROM_VEHICLE` | — | Remove from vehicle |
| `RPC_SET_PLAYER_COLOR` | — | Set player colour |
| `RPC_SET_WORLD_TIME` | — | Set world time |
| `RPC_TOGGLE_SPECTATING` | — | Toggle spectating |
| `RPC_SET_WANTED_LEVEL` | — | Set wanted level |
| `RPC_SET_WEAPON_AMMO` | — | Set weapon ammo |
| `RPC_SET_GRAVITY` | — | Set gravity |
| `RPC_SET_WEATHER` | — | Set weather |
| `RPC_SET_PLAYER_SKIN` | — | Set player skin |
| `RPC_SET_INTERIOR` | — | Set interior |
| `RPC_WORLD_VEHICLE_ADD` | — | Vehicle streamed in |
| `RPC_WORLD_VEHICLE_REMOVE` | — | Vehicle streamed out |
| `RPC_DEATH_BROADCAST` | — | Player death broadcast |

## RPC IDs — client → server

| Constant | Description |
|---|---|
| `RPC_CLIENT_JOIN` | Join with nickname/password/GPCI |
| `RPC_REQUEST_CLASS` | Request a player class |
| `RPC_REQUEST_SPAWN` | Request spawn |
| `RPC_SPAWN` | Spawn |
| `RPC_DIALOG_RESPONSE` | Respond to a dialog |
| `RPC_DEATH` | Send death notification |
| `RPC_ENTER_VEHICLE` | Enter vehicle |
| `RPC_EXIT_VEHICLE` | Exit vehicle |
| `RPC_SERVER_COMMAND` | Send slash command |
