# Multi-File Organization

Small bots can define everything in one file. As a project grows, you'll want to split handlers into separate modules — a chat module, a dialog module, etc. The `Router` class makes this possible without requiring a bot instance at import time.

## Basic pattern

```python
# handlers/chat.py
from pyraksamp import Router

router = Router()

@router.on_chat()
async def on_chat(bot, msg):
    bot.send_chat(f"echo: {msg.text.stripped}")

@router.on_player_join()
async def on_join(bot, evt):
    print(f"{evt.name} joined")
```

```python
# main.py
import asyncio
import pyraksamp
from handlers import chat

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")

    bot.include_router(chat.router)

    await bot.start()
    await bot.run_until_disconnected()

asyncio.run(main())
```

`include_router` replays every handler from the router onto the bot, injecting the bot as the first argument. After that, handlers work identically to ones registered directly on the bot.

## Multiple routers

You can attach as many routers as you want:

```python
from handlers import chat, dialogs, movement

bot.include_router(chat.router)
bot.include_router(dialogs.router)
bot.include_router(movement.router)
```

Handlers fire in the order they were registered — across all routers and any `@bot.on_*()` decorators on the bot itself.

## Mix bot and router handlers

Both approaches can coexist. Use `@bot.on_*` for simple bots, routers for anything that needs to live in its own module:

```python
bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")

@bot.on_connect
async def connected():
    print(f"Connected as {bot.player_id}")

bot.include_router(chat.router)

await bot.start()
```

## Timing

Routers can be included before or after `start()`:

```python
# before start — handlers activate when the bot connects
bot.include_router(chat.router)
await bot.start()

# after start — handlers activate immediately
await bot.start()
# ... sequential login flow ...
bot.include_router(chat.router)
```

## Available methods

`Router` supports all the same `on_*` decorators as `SAMPBot`:

- `on_connect`, `on_disconnect`
- `on_chat`, `on_client_message`, `on_game_text`
- `on_dialog`, `on_rpc`
- `on_player_join`, `on_player_quit`
- `on_set_health`, `on_set_armour`, `on_set_position`
- `on_checkpoint`, `on_checkpoint_disabled`
- `on_player_streamed_in`, `on_player_streamed_out`
- `on_textdraw`
- ...and all other event decorators

Filter parameters work identically:

```python
@router.on_chat(player_id=5)
async def on_chat(bot, msg):
    ...

@router.on_dialog(dialog_type=pyraksamp.InputDialog)
async def on_input(bot, dlg):
    ...
```
