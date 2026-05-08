[![CI](https://github.com/bulatovv/pyraksamp/actions/workflows/ci.yml/badge.svg)](https://github.com/bulatovv/pyraksamp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyraksamp)](https://pypi.org/project/pyraksamp/)
[![Python](https://img.shields.io/pypi/pyversions/pyraksamp)](https://pypi.org/project/pyraksamp/)

# pyraksamp

SA:MP 0.3.7 headless client library for Python.

## Install

```
pip install pyraksamp
```

## Example

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
    await bot.run_until_disconnected()

asyncio.run(main())
```

## Docs

https://bulatovv.github.io/pyraksamp/
