# Connecting

## Basic connection

```python
bot = pyraksamp.SAMPBot(
    host="play.example.com",
    port=7777,
    nickname="MyBot",
)
await bot.start()
```

`start()` blocks until the connection is accepted or an exception is raised. It also starts the background Rust receive/keepalive thread.

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | `str` | — | Server hostname or IP address |
| `port` | `int` | `7777` | UDP port |
| `nickname` | `str` | `"PyBot"` | In-game name (max 20 characters) |
| `password` | `str` | `""` | Server password (leave empty for public servers) |
| `gpci` | `str` | auto-generated | Hardware key (GTA serial). Supply a fixed value to keep a persistent identity across reconnects. |
| `server_encoding` | `str` | `"utf-8"` | Text encoding used by the server |
| `proxy` | `str \| None` | `None` | SOCKS5 proxy URL |

## GPCI

SA:MP servers use the GPCI string as a hardware fingerprint. pyraksamp generates a random valid GPCI by default. If you want to maintain a stable identity (e.g. to avoid repeated bans or to keep the same in-game ID), pass a fixed value:

```python
bot = pyraksamp.SAMPBot("...", gpci="A1B2C3...")
```

You can generate a valid random GPCI with:

```python
gpci = pyraksamp.gen_gpci()
```

## SOCKS5 proxy

Pass a SOCKS5 proxy URL via the `proxy` parameter:

```python
bot = pyraksamp.SAMPBot(
    "play.example.com", 7777, "MyBot",
    proxy="socks5://user:pass@proxy.host:1080",
)
```

Authentication is optional: `socks5://proxy.host:1080` works too.

## Connection exceptions

`start()` raises one of these on failure:

| Exception | Meaning |
|---|---|
| `SAMPBanned` | Client IP is banned from the server |
| `SAMPInvalidPassword` | Wrong server password |
| `SAMPServerFull` | No free player slots |
| `SAMPRejected` | Server actively refused the connection |
| `SAMPHandshakeTimeout` | Server did not complete the open-connection handshake in time |
| `SAMPConnectionTimeout` | Server did not accept the connection request in time |
| `SAMPHostResolutionError` | Hostname could not be resolved |
| `SAMPProxyError` | SOCKS5 proxy handshake failed |
| `SAMPSocketError` | Could not bind the local UDP socket |

All are subclasses of `SAMPConnectionError`.

```python
try:
    await bot.start()
except pyraksamp.SAMPBanned:
    ...
except pyraksamp.SAMPConnectionError as e:
    ...  # catch-all for any connection failure
```

## Disconnecting

```python
bot.disconnect()   # send disconnect packet, then stop
bot.stop()         # stop immediately without notifying the server
```

## Connection state

```python
bot.is_connected   # True while the bot is connected
bot.player_id      # server-assigned player ID, or -1 before connect
```
