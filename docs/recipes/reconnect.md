# Reconnect

Automatically reconnect after disconnect with a retry delay.

```python
import asyncio
import pyraksamp
from pyraksamp import Router

RETRY_DELAY = 5

router = Router()

@router.on_chat()
async def on_chat(bot, msg):
    print(f"[chat] {msg.text.stripped}")

@router.on_connect
async def connected(bot):
    print(f"Connected as player {bot.player_id}")

async def main():
    while True:
        bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")
        bot.include_router(router)
        try:
            await bot.start()
            await bot.run_until_disconnected()
        except pyraksamp.SAMPConnectionError as e:
            print(f"Connection failed: {e}")
        print(f"Reconnecting in {RETRY_DELAY}s...")
        await asyncio.sleep(RETRY_DELAY)

asyncio.run(main())
```

## Exponential backoff

For servers that might rate-limit repeated connections:

```python
async def main():
    delay = RETRY_DELAY
    while True:
        bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")
        bot.include_router(router)
        try:
            await bot.start()
            delay = RETRY_DELAY  # reset on successful connect
            await bot.run_until_disconnected()
        except pyraksamp.SAMPConnectionError as e:
            print(f"Connection failed: {e}")
        print(f"Reconnecting in {delay}s...")
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)  # cap at 60s
```

### Notes

- Each iteration creates a new `SAMPBot` — internal state (event bus, dispatcher, listeners) is not reusable after disconnect.
- Router solves the re-registration problem: define handlers once, include on every new bot instance.
- Handlers registered directly on the bot (without Router) would need to be re-registered each iteration.
