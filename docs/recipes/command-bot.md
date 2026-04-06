# Command Bot

React to chat messages that look like commands (e.g. `!help`, `!pos`).

```python
import asyncio
import pyraksamp
from pyraksamp import ChatMessage

COMMAND_PREFIX = "!"

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, "CmdBot")

    @bot.on_chat()
    async def on_chat(msg: ChatMessage):
        text = msg.text.stripped
        if not text.startswith(COMMAND_PREFIX):
            return

        parts = text[len(COMMAND_PREFIX):].split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "help":
            bot.send_chat("Commands: !help, !pos, !hello")
        elif cmd == "pos":
            bot.send_chat(f"Player {msg.player_id} said: {args!r}")
        elif cmd == "hello":
            bot.send_chat(f"Hi, player {msg.player_id}!")

    await bot.start()
    async for _ in bot.events():
        pass

asyncio.run(main())
```

### Using send_command for slash commands

To send SA:MP server-side slash commands (processed by server scripts):

```python
bot.send_command("/stats")
bot.send_command("/pm 5 hello there")
```

This is different from chat — it goes through the server-side `OnPlayerCommandText` handler.
