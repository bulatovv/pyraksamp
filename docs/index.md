# pyraksamp

**pyraksamp** is an async Python library for controlling SA:MP 0.3.7 headless bot clients.
It wraps a Rust UDP core via PyO3, exposing a clean Python API with typed events, dialogs,
textdraws, and an interactive TUI shell.

```python
import asyncio
import pyraksamp

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")

    @bot.on_chat()
    async def on_chat(msg):
        if "hello" in msg.text.stripped.lower():
            bot.send_chat("hi!")

    await bot.start()
    async for _ in bot.events():
        pass

asyncio.run(main())
```

## Install

```
pip install pyraksamp
```

For build-from-source instructions (requires Rust + maturin), see
[Installation](getting-started/installation.md).

## Navigation

- **[Getting Started](getting-started/installation.md)** — install and run your first bot
- **[Guides](guides/connecting.md)** — in-depth topics: flows, dialogs, textdraws, actions
- **[Recipes](recipes/index.md)** — short self-contained scripts for common tasks
- **[Concepts](concepts/architecture.md)** — how the library works internally
- **[API Reference](api/index.md)** — auto-generated from docstrings
