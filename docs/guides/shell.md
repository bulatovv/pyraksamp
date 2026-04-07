# Interactive Shell

pyraksamp includes a Textual-based TUI shell for interactive control of a running bot.

---

## Launch from the CLI

Connect directly to a server without writing any code:

```
pyraksamp shell --host play.example.com --port 7777 --nick MyBot
```

Optional flags:

| Flag | Default | Description |
|---|---|---|
| `--password PW` | `""` | Server password |
| `--proxy URL` | — | SOCKS5 proxy (e.g. `socks5://user:pass@host:1080`) |
| `--encoding ENC` | `ascii` | Server text encoding |

---

## Launch from a module

Point the CLI at a `SAMPBot` or `Shell` object in your module:

```
pyraksamp shell mymodule:bot
pyraksamp shell mymodule:shell
```

The bot is connected automatically if not already started. If already running, the TUI attaches to the live event stream.

---

## Embed in code

Use `Shell` directly in your script to add an interactive TUI while the bot is running:

```python
import asyncio
import pyraksamp
from pyraksamp.shell import Shell

async def main():
    bot = pyraksamp.SAMPBot("play.example.com", 7777, "MyBot")
    shell = Shell(bot)

    @shell.command("greet", help="Say hello in chat")
    async def greet(args, app):
        bot.send_chat("Hello everyone!")

    await bot.start()
    await shell.run()    # blocks until TUI exits

asyncio.run(main())
```

Custom commands are invoked in the TUI by typing `:commandname [args]`.

### Registering commands

```python
# decorator style
@shell.command("echo", help="Echo args to chat", metavar="<text>")
async def echo_cmd(args, app):
    bot.send_chat(args)

# imperative style
shell.register_command("echo", echo_cmd, help="Echo args to chat")
```

The callback receives `args` (everything after the command name, as a string) and `app`
(the Textual `App` instance for advanced TUI interactions).

---

## Remote attach

For headless deployments, expose the shell over a Unix socket and attach from another terminal:

```python
# In your bot script:
server = await bot.expose_shell()      # starts TUI + Unix socket relay
# bot continues running in the background
await bot.run_until_disconnected()
```

Attach from any terminal on the same machine:

```
pyraksamp shell --attach                   # auto-detects the socket
pyraksamp shell --attach /tmp/pyraksamp-1234.sock   # specific socket
```

The relay forwards ANSI bytes and keystrokes bidirectionally, so the full TUI renders in the attached terminal.

To stop accepting new connections without stopping the bot:

```python
server.close()
```
