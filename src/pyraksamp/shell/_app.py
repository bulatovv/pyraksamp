"""SampShellApp — main Textual application for the pyraksamp shell."""

from __future__ import annotations

import asyncio
import logging
import shlex
import traceback
from typing import TYPE_CHECKING, ClassVar

from textual.app import App, ComposeResult
from textual import on
from textual.binding import Binding
from textual.widgets import Static, Rule, Label
from textual.containers import Horizontal

from pyraksamp.dialogs import AnyDialog
from pyraksamp.events import (
    ChatMessage,
    PlayerJoin,
    PlayerQuit,
    ServerMessage,
)
from pyraksamp.shell._commands import CommandRegistry
from pyraksamp.shell._completion import CommandHistory, CompletionItem, CompletionMenu
from pyraksamp.shell._widgets import (
    ChatInput,
    EventLog,
    TextdrawMenu,
    _strip_colors,
)

if TYPE_CHECKING:
    from pyraksamp import SAMPBot


class _ShellLogHandler(logging.Handler):
    """Logging handler that writes records to EventLog."""

    def __init__(self, app: SampShellApp) -> None:
        super().__init__()
        self._app = app

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        level = record.levelname.lower()
        style_map = {
            "debug": "dim",
            "info": "",
            "warning": "warning",
            "error": "error",
            "critical": "error",
        }
        style = style_map.get(level, "")
        try:
            asyncio.ensure_future(self._app._event_log.append_line(msg, style=style))
        except Exception:
            pass


class SampShellApp(App):
    """In-process TUI shell for SAMPBot."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("alt+left", "prev_dialog", "Prev dialog", show=False),
        Binding("alt+right", "next_dialog", "Next dialog", show=False),
        Binding("ctrl+q", "none", "Quit", show=False),  # Unbind ctrl+q
    ]

    CSS = """
    Screen {
        layout: vertical;
        background: transparent;
        scrollbar-size: 0 0;
    }
    #input-hint {
        height: 1;
        color: ansi_white;
        padding: 0 1;
        background: transparent;
    }
    #input-sep, #input-sep-bottom {
        height: 1;
        color: ansi_white;
        text-style: dim;
        margin: 0;
        padding: 0;
    }
    #input-bar {
        height: 1;
    }
    #input-prefix {
        width: 2;
        height: 1;
        padding: 0;
        color: ansi_white;
    }
    #input-prefix.mode-chat { color: ansi_white; }
    #input-prefix.mode-command { color: ansi_magenta; }
    #input-prefix.mode-sampcmd { color: ansi_cyan; }
    #input-bar ChatInput {
        width: 1fr;
    }
    """

    def __init__(self, bot: SAMPBot, commands: CommandRegistry, **kwargs) -> None:
        kwargs.setdefault("ansi_color", True)
        super().__init__(**kwargs)
        self._bot = bot
        self._commands = commands
        self._bus_q: asyncio.Queue = asyncio.Queue()
        self._event_task: asyncio.Task | None = None
        self._log_handler: _ShellLogHandler | None = None
        self._textdraw_panel: TextdrawMenu | None = None
        self._exit_timer: asyncio.TimerHandle | None = None

        # Bot state mirror
        self._players: dict[int, str] = {}
        self._connected_at: float = 0.0
        self._dialog_history: list[AnyDialog] = []

        self._samp_history = CommandHistory()
        self._cmd_history = CommandHistory()
        self._chat_history = CommandHistory()

    def compose(self) -> ComposeResult:
        self._event_log = EventLog()
        self._chat_input = ChatInput()
        self._completion_menu = CompletionMenu()
        self._input_prefix = Static(">", id="input-prefix")
        self._input_hint = Label("", id="input-hint")
        yield self._event_log
        yield self._input_hint
        yield self._completion_menu
        yield Rule(id="input-sep")
        with Horizontal(id="input-bar"):
            yield self._input_prefix
            yield self._chat_input
        yield Rule(id="input-sep-bottom")

    async def on_mount(self) -> None:
        # Subscribe BEFORE starting (or attaching to) the bot so no events are missed.
        self._bot.subscribe(self._bus_q)
        self._event_task = asyncio.create_task(self._consume_events())

        self._log_handler = _ShellLogHandler(self)
        logging.getLogger().addHandler(self._log_handler)
        self._chat_input.focus()

        if not self._bot._started:
            self.set_hint("Connecting...", dim_yellow=True)
            asyncio.create_task(self._do_connect())
        elif self._bot.is_connected:
            await self._event_log.append_line(
                "Attached to already-connected bot (events before this point not shown).",
                style="dim",
            )

    async def _do_connect(self) -> None:
        try:
            await self._bot.start()
        except Exception as exc:
            await self._event_log.append_line(
                f"Connection failed: {exc}", style="error"
            )
            self.exit(1)

    async def on_unmount(self) -> None:
        if self._exit_timer:
            self._exit_timer.cancel()
        if self._event_task:
            self._event_task.cancel()
        self._bot.unsubscribe(self._bus_q)
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)

        # Ensure bot disconnects and stops on TUI exit.
        if self._bot.is_connected:
            self._bot.disconnect()
        self._bot.stop()

    # ── Public helpers for commands ────────────────────────────────────────────

    def set_hint(
        self, text: str, *, dim: bool = False, dim_yellow: bool = False
    ) -> None:
        """Update the input hint label."""
        if text and dim_yellow:
            self._input_hint.update(f"[ansi_yellow]{text}[/]")
        elif text and dim:
            self._input_hint.update(f"[dim]{text}[/dim]")
        else:
            self._input_hint.update(text)

    def log_line(self, text: str, *, style: str = "") -> None:
        """Schedule a log line append (safe to call from commands)."""
        asyncio.ensure_future(self._event_log.append_line(text, style=style))

    def toggle_textdraws(self) -> None:
        """Mount or unmount the TextdrawMenu."""
        if self._textdraw_panel is not None:
            self._textdraw_panel.remove()
            self._textdraw_panel = None
            self._chat_input.focus()
        else:
            panel = TextdrawMenu(self._bot)
            self._textdraw_panel = panel
            self.mount(panel, before=self._input_hint)
            panel.focus()

    @on(TextdrawMenu.Dismissed)
    def _on_textdraw_dismissed(self, _event: TextdrawMenu.Dismissed) -> None:
        self.toggle_textdraws()

    async def _watch_dialog_response(self, dlg, group) -> None:
        """Reset cascade timer when a dialog is auto-responded by the bot."""
        while not dlg.is_responded:
            await asyncio.sleep(0.05)
        if not group.is_sealed:
            group._reset_cascade_timer()

    def action_prev_dialog(self) -> None:
        g = self._event_log._active_group
        if g is not None:
            g.action_prev_pane()
            g._update_nav()

    def action_next_dialog(self) -> None:
        g = self._event_log._active_group
        if g is not None:
            g.action_next_pane()
            g._update_nav()

    async def on_key(self, event) -> None:
        if event.key == "ctrl+c":
            event.prevent_default()
            if self._exit_timer:
                self.exit()
            else:
                self.set_hint("[ansi_yellow]Press Ctrl+C again to exit[/]")
                self._exit_timer = asyncio.get_event_loop().call_later(
                    4.0, self._clear_exit_hint
                )
        elif event.key == "ctrl+q":
            # Unbind ctrl+q
            event.prevent_default()

    def on_mouse_move(self, event) -> None:
        event.prevent_default()
        event.stop()

    def on_mouse_down(self, event) -> None:
        event.prevent_default()
        event.stop()

    def on_mouse_up(self, event) -> None:
        event.prevent_default()
        event.stop()

    def _clear_exit_hint(self) -> None:
        self._exit_timer = None
        # Only clear if we are not currently showing a dialog nav hint
        g = self._event_log._active_group
        if g is None or len(g._panes) <= 1:
            self.set_hint("")

    # ── Event consumption ──────────────────────────────────────────────────────

    async def _consume_events(self) -> None:
        try:
            while True:
                event = await self._bus_q.get()
                tag = event[0]
                if tag == "disconnect":
                    await self._event_log.append_line(
                        "Disconnected from server.", style="error"
                    )
                    self._input_hint.update("[ansi_red]Disconnected[/]")
                    break
                try:
                    await self._route(tag, event)
                except Exception as exc:
                    tb = traceback.format_exc()
                    await self._event_log.append_line(
                        f"[TUI error routing {tag!r}: {exc}]\n{tb}", style="error"
                    )
        except asyncio.CancelledError:
            pass

    @staticmethod
    def _is_junk_dialog(dlg: AnyDialog) -> bool:
        if dlg.dialog_id == 65535:
            return True
        if not (dlg.button1 or "").strip() and not (dlg.button2 or "").strip():
            return True

        title = _strip_colors(getattr(dlg, "title", "") or "").strip()

        # List-style dialogs (2, 4, 5) are defined by their rows, not a 'body' text.
        if dlg.style in (2, 4, 5):
            return not title and len(getattr(dlg, "rows", [])) == 0

        body = _strip_colors(getattr(dlg, "body", "") or "").strip()
        return not title and not body

    async def _route(self, tag: str, event: tuple) -> None:
        if tag == "connect":
            import time

            self._connected_at = time.monotonic()
            self.set_hint("")

        elif tag == "chat":
            msg: ChatMessage = event[1]
            name = self._players.get(msg.player_id, f"[{msg.player_id}]")
            await self._event_log.append_line(
                f"[CHAT] {name}: [ansi_white]{msg.text}[/ansi_white]", style="chat"
            )

        elif tag == "client_message":
            msg: ServerMessage = event[1]
            await self._event_log.append_line(msg.text, style="server")

        elif tag == "player_join":
            import time

            evt: PlayerJoin = event[1]
            self._players[evt.player_id] = evt.name
            if time.monotonic() - self._connected_at > 10.0:
                await self._event_log.append_line(
                    f"→ {evt.name} ({evt.player_id})", style="join"
                )

        elif tag == "player_quit":
            import time

            evt: PlayerQuit = event[1]
            name = self._players.pop(evt.player_id, f"[{evt.player_id}]")
            if time.monotonic() - self._connected_at > 10.0:
                await self._event_log.append_line(
                    f"← {name} ({evt.player_id})", style="quit"
                )

        elif tag == "dialog":
            dlg: AnyDialog = event[1]
            if self._is_junk_dialog(dlg):
                return
            self._dialog_history.append(dlg)
            self._event_log._capture_scroll_intent()
            group = await self._event_log.get_or_create_dialog_group()
            pane = await group.add_dialog(dlg)
            self._event_log.call_after_refresh(self._event_log._auto_scroll)
            if self.focused is self._chat_input and not self._chat_input.value:
                pane._focus_interactive()
            elif self.focused is self._chat_input:
                self.set_hint("Press Tab to navigate to dialog")
            asyncio.ensure_future(self._watch_dialog_response(dlg, group))

    # ── Chat input handler ─────────────────────────────────────────────────────

    @on(ChatInput.ModeChanged)
    def _on_mode_changed(self, event: ChatInput.ModeChanged) -> None:
        self._input_prefix.remove_class("mode-chat", "mode-command", "mode-sampcmd")
        if event.mode == "command":
            self._input_prefix.update(":")
            self._input_prefix.add_class("mode-command")
        elif event.mode == "sampcmd":
            self._input_prefix.update("/")
            self._input_prefix.add_class("mode-sampcmd")
        else:
            self._input_prefix.update(">")
            self._input_prefix.add_class("mode-chat")

    # ── Completion ─────────────────────────────────────────────────────────────

    def _close_completion(self) -> None:
        self._completion_menu.close()
        self._chat_input.completion_active = False

    def _apply_completion(self, text: str) -> None:
        self._close_completion()
        self._chat_input.value = text
        self._chat_input.cursor_position = len(text)

    @on(ChatInput.TabPressed)
    def _on_tab_pressed(self, event: ChatInput.TabPressed) -> None:
        if self._completion_menu.is_open and not event.shift:
            selected = self._completion_menu.move(1)
            if selected is not None:
                self._chat_input.value = selected
                self._chat_input.cursor_position = len(selected)
            return

        # Shift+Tab — open (or reopen) menu with fresh completions
        prefix = self._chat_input.value.strip()
        if self._chat_input.command_mode:
            items = []
            for name in self._commands.names():
                if not name.startswith(prefix):
                    continue
                cmd = self._commands.get(name)
                label = f"{name} {cmd.metavar}".rstrip() if cmd.metavar else name
                items.append(
                    CompletionItem(insert=name, label=label, description=cmd.help)
                )
        else:  # samp_mode
            full_prefix = f"/{prefix}" if not prefix.startswith("/") else prefix
            items = [
                CompletionItem(insert=c[1:] if c.startswith("/") else c, label=c)
                for c in self._samp_history.completions(full_prefix)
            ]

        if not items:
            return

        self._completion_menu.open(items)
        self._chat_input.completion_active = True
        # Preview first item
        self._chat_input.value = items[0].insert
        self._chat_input.cursor_position = len(items[0].insert)

    @on(ChatInput.CompletionConfirmed)
    def _on_completion_confirmed(self, _event: ChatInput.CompletionConfirmed) -> None:
        selected = self._completion_menu.selected
        if selected:
            self._apply_completion(selected)

    @on(ChatInput.CompletionDismissed)
    def _on_completion_dismissed(self, _event: ChatInput.CompletionDismissed) -> None:
        self._close_completion()

    @on(ChatInput.ModeChanged)
    def _on_mode_changed_completion(self, _event: ChatInput.ModeChanged) -> None:
        if self._completion_menu.is_open:
            self._close_completion()
        for hist in (self._samp_history, self._cmd_history, self._chat_history):
            hist.navigate_reset()

    # ── History navigation ─────────────────────────────────────────────────────

    def _current_history(self) -> "CommandHistory":
        if self._chat_input.command_mode:
            return self._cmd_history
        if self._chat_input.samp_mode:
            return self._samp_history
        return self._chat_history

    def _set_input(self, text: str) -> None:
        self._chat_input.value = text
        self._chat_input.cursor_position = len(text)

    @on(ChatInput.HistoryUp)
    def _on_history_up(self, _event: ChatInput.HistoryUp) -> None:
        hist = self._current_history()
        # In samp mode the input has no leading "/", but history stores "/cmd"
        current = self._chat_input.value
        stored_current = f"/{current}" if self._chat_input.samp_mode else current
        result = hist.navigate_up(stored_current)
        if result is not None:
            if self._chat_input.samp_mode and result.startswith("/"):
                result = result[1:]
            self._set_input(result)

    @on(ChatInput.HistoryDown)
    def _on_history_down(self, _event: ChatInput.HistoryDown) -> None:
        hist = self._current_history()
        result = hist.navigate_down()
        if self._chat_input.samp_mode and result.startswith("/"):
            result = result[1:]
        self._set_input(result)

    # ── Chat input handler ─────────────────────────────────────────────────────

    @on(ChatInput.Submitted)
    async def _on_chat_submitted(self, event: ChatInput.Submitted) -> None:
        self._close_completion()
        for hist in (self._samp_history, self._cmd_history, self._chat_history):
            hist.navigate_reset()
        text = event.value.strip()
        is_samp_command = self._chat_input.samp_mode or text.startswith("/")
        is_tui_command = self._chat_input.command_mode or text.startswith(":")

        self._chat_input.clear()
        if not text:
            return

        if is_tui_command:
            cmd_text = text.lstrip(":")
            self._cmd_history.add(cmd_text)
            parts = shlex.split(cmd_text)
            if not parts:
                return
            cmd_name = parts[0]
            args = parts[1:]
            cmd = self._commands.get(cmd_name)
            if cmd is None:
                await self._event_log.append_line(
                    f"Unknown command: :{cmd_name}  (type :help for list)",
                    style="error",
                )
            else:
                try:
                    await cmd.fn(args, self)
                except Exception as exc:
                    await self._event_log.append_line(
                        f"Command error: {exc}", style="error"
                    )
        elif is_samp_command:
            try:
                cmd_text = text if text.startswith("/") else f"/{text}"
                self._samp_history.add(cmd_text)
                self._bot.send_command(cmd_text)
            except Exception as exc:
                await self._event_log.append_line(f"Send error: {exc}", style="error")
        else:
            self._chat_history.add(text)
            try:
                self._bot.send_chat(text)
            except Exception as exc:
                await self._event_log.append_line(f"Send error: {exc}", style="error")
