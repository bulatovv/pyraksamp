# Chat Logger

Log all public chat and server messages to a file.

```python
import asyncio
import pyraksamp

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, "Logger")

    with open("chat.log", "a") as log:

        @bot.on_chat()
        async def on_chat(msg):
            log.write(f"[chat] {msg.text.stripped}\n")
            log.flush()

        @bot.on_client_message()
        async def on_server_msg(msg):
            log.write(f"[server] {msg.text.stripped}\n")
            log.flush()

        await bot.start()
        await bot.run_until_disconnected()

asyncio.run(main())
```

### Stream version

Using async generators to collect into a list instead of writing to a file:

```python
messages = []
async for msg in bot.chat():
    messages.append(msg.text.stripped)
    if len(messages) >= 100:
        break   # stop after 100 messages
```
