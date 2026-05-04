[![CI](https://github.com/bulatovv/pyraksamp/actions/workflows/ci.yml/badge.svg)](https://github.com/bulatovv/pyraksamp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyraksamp)](https://pypi.org/project/pyraksamp/)

# pyraksamp

SA:MP 0.3.7 headless client library for Python.

## Install

```
pip install pyraksamp
```

## Example

```python
import asyncio
from pyraksamp import SAMPBot

bot = SAMPBot("play.example.com", 7777, nickname="MyBot")

@bot.on_chat
async def on_chat(msg):
    if str(msg.text) == "!hello":
        await bot.send_chat("Hello!")

asyncio.run(bot.run_until_disconnected())
```

## Docs

https://bulatovv.github.io/pyraksamp/
