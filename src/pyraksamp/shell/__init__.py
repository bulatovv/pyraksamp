"""Shell — in-process TUI shell for SAMPBot."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pyraksamp.shell._app import SampShellApp
from pyraksamp.shell._commands import CommandRegistry, _register_builtins

if TYPE_CHECKING:
    from pyraksamp import SAMPBot

__all__ = ["Shell"]


class Shell:
    """In-process TUI shell wrapper around SAMPBot.

    Usage::

        bot = SAMPBot(...)
        shell = Shell(bot)

        @shell.command("greet")
        async def greet(args, app):
            await bot.send_chat("Hello!")

        async def main():
            await bot.start()
            await shell.run()   # blocks until TUI exits

    For remote attach, use :meth:`SAMPBot.expose_shell` instead.
    """

    def __init__(self, bot: SAMPBot, *, post_middleware_delay: float = 0.2) -> None:
        self._bot = bot
        self._commands = CommandRegistry()
        self._delay = post_middleware_delay
        _register_builtins(self._commands)

    def register_command(self, name: str, fn: Callable, help: str = "", metavar: str = "") -> None:
        """Register a custom command (e.g. ``:greet``)."""
        self._commands.register(name, fn, help, metavar)

    def command(self, name: str, help: str = "", metavar: str = ""):
        """Decorator: register a custom shell command.

        ::

            @shell.command("greet", help="Say hello")
            async def greet(args, app):
                await bot.send_chat("Hello!")
        """

        def decorator(fn: Callable) -> Callable:
            self._commands.register(name, fn, help, metavar)
            return fn

        return decorator

    async def run(self) -> None:
        """Start the TUI in the current terminal (blocks until exit).

        If the bot has not been started yet, the TUI will connect it
        automatically after subscribing to the event bus, ensuring no
        events are missed.  If the bot is already connected, the TUI
        attaches to ongoing events.
        """
        app = SampShellApp(self._bot, self._commands)
        await app.run_async()
