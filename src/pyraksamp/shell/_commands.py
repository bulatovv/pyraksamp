"""CommandRegistry and built-in shell commands."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyraksamp.shell._app import SampShellApp


@dataclass
class Command:
    name: str
    fn: Callable
    help: str = ""
    metavar: str = ""


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(
        self, name: str, fn: Callable, help: str = "", metavar: str = ""
    ) -> None:
        self._commands[name] = Command(name=name, fn=fn, help=help, metavar=metavar)

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def names(self) -> list[str]:
        return sorted(self._commands)


async def _cmd_help(args: list[str], app: SampShellApp) -> None:
    lines = [("bold", "Available commands:")]
    for name in app._commands.names():
        cmd = app._commands.get(name)
        desc = f"  :{name}"
        if cmd and cmd.help:
            desc += f"  — {cmd.help}"
        lines.append(("dim", desc))
    for style, text in lines:
        app.log_line(text, style=style)


async def _cmd_loglevel(args: list[str], app: SampShellApp) -> None:
    if not args:
        app.log_line("Usage: :loglevel [logger_name] LEVEL", style="dim")
        return
    if len(args) == 1:
        logger_name = None
        level_str = args[0]
    else:
        logger_name = args[0]
        level_str = args[1]
    level = getattr(logging, level_str.upper(), None)
    if not isinstance(level, int):
        app.log_line(f"Unknown log level: {level_str!r}", style="error")
        return
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.setLevel(level)
    name_disp = logger_name or "root"
    app.log_line(f"Set {name_disp} logger to {level_str.upper()}", style="dim")


async def _cmd_textdraws(args: list[str], app: SampShellApp) -> None:
    app.toggle_textdraws()


async def _cmd_dialogs(args: list[str], app: SampShellApp) -> None:
    if not app._dialog_history:
        app.log_line("No dialogs in history.", style="dim")
        return
    for i, dlg in enumerate(app._dialog_history):
        title = getattr(dlg, "title", "?")
        style = type(dlg).__name__
        app.log_line(
            f"  [{i}] {style} id={dlg.dialog_id!r} title={title!r}", style="dim"
        )


async def _cmd_tablist(args: list[str], app: SampShellApp) -> None:
    if not app._players:
        app.log_line("No players tracked.", style="dim")
        return
    col_id = max(len("ID"), max(len(str(pid)) for pid in app._players))
    col_name = max(len("Name"), max(len(name) for name in app._players.values()))
    header = f"{'ID':<{col_id}}  {'Name':<{col_name}}"
    sep = "─" * len(header)
    app.log_line(header, style="dim")
    app.log_line(sep, style="dim")
    for pid, name in sorted(app._players.items()):
        app.log_line(f"{pid:<{col_id}}  {name:<{col_name}}", style="dim")


async def _cmd_quit(args: list[str], app: SampShellApp) -> None:
    app.exit()


def _register_builtins(registry: CommandRegistry) -> None:
    registry.register("help", _cmd_help, "List all commands")
    registry.register(
        "loglevel", _cmd_loglevel, "Set log level", metavar="[logger] <level>"
    )
    registry.register("textdraws", _cmd_textdraws, "Toggle textdraw panel")
    registry.register("dialogs", _cmd_dialogs, "Print dialog history")
    registry.register("tablist", _cmd_tablist, "Show player table")
    registry.register("quit", _cmd_quit, "Exit the shell")
