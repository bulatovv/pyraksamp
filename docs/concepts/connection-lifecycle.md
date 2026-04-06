# Connection Lifecycle

## Phases

```
SAMPBot(...)          ← object created, nothing happens yet
     │
await bot.start()     ← handshake begins
     │
     ├── open-connection (UDP)
     ├── connection-request
     ├── connection-accepted  ── or ─► raises SAMPConnectionError subclass
     ├── auth RPC (join with nickname, password, GPCI)
     └── init-game RPC        ── server sends player ID, world state
     │
"connect" event fires  ← @bot.on_connect callbacks run
     │
In-game               ← dialogs, chat, textdraws, RPCs flowing
     │
bot.disconnect()      ← send disconnect RPC, stop receive loop
  or bot.stop()       ← stop receive loop without notifying server
  or server drops     ← receive loop times out
     │
"disconnect" event fires  ← @bot.on_disconnect callbacks run
     │
bot.events() exits    ← async for loop terminates
```

## connect event

The `on_connect` event fires after `init-game` is received — the server has assigned a player ID and sent the initial world state. `bot.player_id` is valid from this point.

```python
@bot.on_connect
async def connected():
    print(f"Connected as player {bot.player_id}")
```

## disconnect event

Fires when the receive loop stops, for any reason: clean disconnect, server kick, or timeout.

```python
@bot.on_disconnect
async def disconnected():
    print("Disconnected")
```

The `bot.events()` generator also stops after yielding the disconnect event, so `async for _ in bot.events(): pass` is the natural way to keep the script alive until disconnected.

## Timeout behavior

The Rust receive loop sends keepalive packets every ~500 ms. If the server stops responding, the loop times out after approximately 5–10 seconds and fires the disconnect event.

## Reconnection

pyraksamp does not reconnect automatically. To reconnect, create a new `SAMPBot` instance and call `start()` again.

```python
while True:
    bot = pyraksamp.SAMPBot(host, port, nick)
    try:
        await bot.start()
        async for _ in bot.events():
            pass
    except pyraksamp.SAMPConnectionError as e:
        print(f"Connection failed: {e}, retrying...")
        await asyncio.sleep(5)
```
