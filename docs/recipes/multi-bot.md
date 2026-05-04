# Multi-Bot

Run multiple bot instances concurrently — useful for load testing, server population, or coordinating multiple connections.

## Basic swarm

```python
import asyncio
import pyraksamp
from pyraksamp import Router

router = Router()

@router.on_chat()
async def on_chat(bot, msg):
    print(f"[{bot.nickname}] {msg.text.stripped}")

async def run_bot(nickname):
    bot = pyraksamp.SAMPBot("play.example.com", 7777, nickname)
    bot.include_router(router)
    await bot.start()
    await bot.run_until_disconnected()

async def main():
    bots = [run_bot(f"Bot_{i}") for i in range(5)]
    await asyncio.gather(*bots)

asyncio.run(main())
```

Each bot gets its own Rust receive thread, dispatcher, and event bus. The asyncio event loop is shared — callbacks interleave cooperatively.

## With reconnect

Combine with the [reconnect](reconnect.md) pattern so bots stay alive:

```python
async def run_bot(nickname):
    while True:
        bot = pyraksamp.SAMPBot("play.example.com", 7777, nickname)
        bot.include_router(router)
        try:
            await bot.start()
            await bot.run_until_disconnected()
        except pyraksamp.SAMPConnectionError:
            pass
        await asyncio.sleep(5)
```

## Proxy rotation

Route each bot through a different SOCKS5 proxy — common for swarms connecting to the same server:

```python
PROXIES = [
    "socks5://user:pass@proxy1.example.com:1080",
    "socks5://user:pass@proxy2.example.com:1080",
    "socks5://user:pass@proxy3.example.com:1080",
]

async def run_bot(nickname, proxy):
    bot = pyraksamp.SAMPBot(
        "play.example.com", 7777, nickname, proxy=proxy,
    )
    bot.include_router(router)
    await bot.start()
    await bot.run_until_disconnected()

async def main():
    bots = [
        run_bot(f"Bot_{i}", PROXIES[i % len(PROXIES)])
        for i in range(9)
    ]
    await asyncio.gather(*bots)
```

Bots cycle through the proxy list — 3 proxies, 9 bots = 3 bots per proxy. Combine with the reconnect pattern for persistent swarms.

### Notes

- Each bot is independent — no shared state between instances.
- Router handlers receive `bot` as the first argument, so the same handler works across all bots without confusion.
- For large swarms (50+), watch for memory and file descriptor limits.
