# Quickstart

This is a minimal bot that connects to a server, prints all chat, and responds to the first dialog it receives.

```python
import asyncio
import pyraksamp
from pyraksamp import InputDialog

async def main():
    bot = pyraksamp.SAMPBot(
        host="play.example.com",
        port=7777,
        nickname="MyBot",
    )

    @bot.on_connect
    async def connected():
        print(f"Connected as player {bot.player_id}")

    @bot.on_chat()
    async def on_chat(msg):
        print(f"[chat] {msg.text.stripped}")

    @bot.on_dialog(dialog_type=InputDialog)
    async def on_input_dialog(dlg):
        print(f"Input dialog: {dlg.title.stripped}")
        dlg.submit("hello")

    await bot.start()

    await bot.run_until_disconnected()  # keep running until disconnected

asyncio.run(main())
```

### What this does

1. `SAMPBot(...)` creates the client. Nothing connects yet.
2. The `@on_*` decorators register callbacks. They can be registered at any time — before or after `start()`.
3. `await bot.start()` performs the SA:MP handshake and raises a specific exception
   (e.g. `SAMPBanned`, `SAMPServerFull`) if the connection is refused.
4. `await bot.run_until_disconnected()` keeps the script alive until the bot disconnects.

### Handling connection errors

```python
try:
    await bot.start()
except pyraksamp.SAMPBanned:
    print("banned from server")
except pyraksamp.SAMPServerFull:
    print("server is full")
except pyraksamp.SAMPConnectionError as e:
    print(f"could not connect: {e}")
```

See [Connecting](../guides/connecting.md) for the full list of exceptions and connection options.
