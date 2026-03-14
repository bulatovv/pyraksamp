"""Textual widgets for the pyraksamp shell TUI."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)
from textual.containers import Horizontal, ScrollableContainer, Vertical

import re

from pyraksamp.dialogs import (
    AnyDialog,
    InputDialog,
    ListDialog,
    MsgboxDialog,
    PasswordDialog,
    TablistDialog,
    TablistHeadersDialog,
)

from pyraksamp.colors import Color, ColoredString

_SAMP_COLOR_RE = re.compile(r"\{[0-9A-Fa-f]{6}\}")


def _to_markup(text: str) -> str:
    """Convert ColoredString to markup if applicable, otherwise escape."""
    from textual.markup import escape

    if isinstance(text, ColoredString):
        parts = []
        for comp in text._components:
            if isinstance(comp, Color):
                parts.append(f"[#{comp.value:06X}]")
            else:
                parts.append(escape(comp))
        return "".join(parts)
    return escape(str(text))


def _strip_colors(text: str) -> str:
    """Remove SA:MP inline color codes like {FFFFFF}."""
    return _SAMP_COLOR_RE.sub("", text)


if TYPE_CHECKING:
    pass

# ── LogLine ────────────────────────────────────────────────────────────────────


class LogLine(Static):
    """A single log entry in EventLog."""

    DEFAULT_CSS = """
    LogLine {
        height: auto;
        padding: 0 1;
        background: transparent;
    }
    LogLine.chat { color: ansi_white; }
    LogLine.server { color: ansi_bright_black; }
    LogLine.join { color: ansi_green; }
    LogLine.quit { color: ansi_bright_black; }
    LogLine.dim { color: ansi_bright_black; }
    LogLine.bold { color: ansi_white; text-style: bold; }
    LogLine.error { color: ansi_red; text-style: bold; }
    LogLine.warning { color: ansi_yellow; }
    """

    def __init__(self, text: str, *, style: str = "") -> None:
        super().__init__(_to_markup(text))
        if style:
            self.add_class(style)


# ── StatusBar ─────────────────────────────────────────────────────────────────


class StatusBar(Static):
    """Bottom status bar showing bot state."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: transparent;
        color: ansi_bright_black;
        padding: 0 1;
    }
    """

    hp: reactive[float] = reactive(100.0)
    armour: reactive[float] = reactive(0.0)
    pos: reactive[tuple] = reactive((0.0, 0.0, 0.0))
    players: reactive[int] = reactive(0)
    connected: reactive[bool] = reactive(False)

    def render(self) -> str:
        x, y, z = self.pos
        if self.connected:
            status = "[ansi_green]CONNECTED[/]"
        else:
            status = "[ansi_red]DISCONNECTED[/]"
        
        return (
            f" {status}  |  "
            f"POS: {x:.1f}, {y:.1f}, {z:.1f}  |  "
            f"Players: {self.players}"
        )


# ── ChatInput ─────────────────────────────────────────────────────────────────


class ChatInput(Input):
    """Chat and command input widget."""

    DEFAULT_CSS = """
    ChatInput {
        border: none;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("enter", "submit", "Send", show=False),
    ]

    class ModeChanged(Message):
        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode  # "chat", "command", or "sampcmd"

    def __init__(self) -> None:
        super().__init__(
            placeholder="type a message or :command or /samp_command", compact=True
        )
        self.command_mode = False
        self.samp_mode = False

    def on_key(self, event) -> None:
        if not self.value and not (self.command_mode or self.samp_mode):
            if event.character == ":":
                event.prevent_default()
                self.command_mode = True
                self.post_message(self.ModeChanged("command"))
            elif event.character == "/":
                event.prevent_default()
                self.samp_mode = True
                self.post_message(self.ModeChanged("sampcmd"))
        elif event.key == "backspace" and not self.value:
            if self.command_mode:
                self.command_mode = False
                self.post_message(self.ModeChanged("chat"))
            elif self.samp_mode:
                self.samp_mode = False
                self.post_message(self.ModeChanged("chat"))

    def clear(self) -> None:
        super().clear()
        if self.command_mode or self.samp_mode:
            self.command_mode = False
            self.samp_mode = False
            self.post_message(self.ModeChanged("chat"))


# ── DialogWidget ──────────────────────────────────────────────────────────────


class DialogWidget(Vertical):
    """Renders a single dialog pane."""

    DEFAULT_CSS = """
    DialogWidget {
        height: auto;
        border: round ansi_white;
        padding: 0 1;
        margin: 0;
        background: transparent;
    }
    DialogWidget.responded {
        border: round ansi_bright_black;
    }
    DialogWidget.responded Label {
        color: ansi_white;
        text-style: dim;
    }
    DialogWidget Label.dialog-body {
        height: auto;
        width: 1fr;
    }
    DialogWidget Input {
        width: 1fr;
        height: 3;
        margin-top: 1;
        border: round ansi_white;
        padding: 0 1;
        color: ansi_white;
    }
    DialogWidget Input:focus {
        border: round ansi_yellow;
        outline: none;
    }
    DialogWidget.responded Input {
        background: transparent;
        color: ansi_white;
        text-style: dim;
        border: round ansi_bright_black;
    }
    DialogWidget.responded ListItem {
        color: ansi_white;
        text-style: dim;
    }
    DialogWidget DataTable {
        height: auto;
        background: transparent;
        border: none;
        margin: 1 0;
    }
    DialogWidget .datatable-header {
        height: 1;
        color: ansi_white;
        text-style: bold;
        padding: 0 0;
        background: transparent;
    }
    DialogWidget DataTable > .datatable--cursor {
        background: ansi_bright_black 30%;
    }
    DialogWidget DataTable:focus > .datatable--cursor {
        background: ansi_yellow 20%;
        color: ansi_black;
        text-style: bold;
    }
    DialogWidget DataTable > .datatable--hover {
        background: ansi_white 10%;
    }
    DialogWidget DataTable > .datatable--odd-row {
        background: transparent;
    }
    DialogWidget DataTable > .datatable--even-row {
        background: transparent;
    }
    DialogWidget.responded DataTable {
        background: transparent;
        color: ansi_white;
        text-style: dim;
    }
    DialogWidget.responded DataTable > .datatable--cursor {
        background: transparent;
    }
    DialogWidget.responded DataTable > .datatable--odd-row {
        background: transparent;
    }
    DialogWidget.responded DataTable > .datatable--even-row {
        background: transparent;
    }
    DialogWidget ListView {
        height: auto;
        max-height: 10;
        background: transparent;
        border: none;
        margin: 1 0;
    }
    DialogWidget ListItem {
        background: transparent;
        padding: 0 1;
    }
    DialogWidget ListItem:hover {
        background: ansi_white 10%;
    }
    DialogWidget ListItem:focus {
        background: ansi_yellow 20%;
        color: ansi_black;
        text-style: bold;
    }
    DialogWidget ListItem.--highlight {
        background: ansi_yellow 20%;
        color: ansi_black;
        text-style: bold;
    }
    DialogWidget .dialog-buttons {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    DialogWidget Button {
        min-width: 4;
        background: transparent;
        color: ansi_cyan;
        border: round ansi_cyan;
    }
    DialogWidget Button:hover {
        border: round ansi_bright_cyan;
        color: ansi_bright_cyan;
    }
    DialogWidget Button:disabled {
        color: ansi_white;
        text-style: dim;
        border: round ansi_bright_black;
    }
    DialogWidget.responded Button {
        border: round ansi_bright_black;
    }
    """

    def __init__(self, dialog: AnyDialog) -> None:
        super().__init__()
        self._dialog = dialog
        self._input_widget: Input | None = None
        self._list_widget: ListView | DataTable | None = None
        self._btn1: Button | None = None
        self._btn2: Button | None = None

    def compose(self) -> ComposeResult:
        dlg = self._dialog
        body = getattr(dlg, "body", "")
        btn1_label = _strip_colors(getattr(dlg, "button1", "") or "").strip()
        btn2_label = _strip_colors(getattr(dlg, "button2", "") or "").strip()

        if isinstance(dlg, MsgboxDialog):
            if body:
                yield Label(_to_markup(body), classes="dialog-body")

        elif isinstance(dlg, PasswordDialog):
            if body:
                yield Label(_to_markup(body), classes="dialog-body")
            self._input_widget = Input(password=True)
            yield self._input_widget

        elif isinstance(dlg, InputDialog):
            if body:
                yield Label(_to_markup(body), classes="dialog-body")
            self._input_widget = Input()
            yield self._input_widget

        elif isinstance(dlg, (ListDialog, TablistDialog, TablistHeadersDialog)):
            if isinstance(dlg, TablistHeadersDialog):
                yield Static("", classes="datatable-header")
            dt = DataTable(cursor_type="row", show_header=False)
            self._list_widget = dt
            yield dt

        with Horizontal(classes="dialog-buttons"):
            if btn1_label:
                self._btn1 = Button(btn1_label, variant="primary", compact=True)
                yield self._btn1
            if btn2_label:
                self._btn2 = Button(btn2_label, variant="default", compact=True)
                yield self._btn2

    async def on_mount(self) -> None:
        dlg = self._dialog

        title = _strip_colors(getattr(dlg, "title", "") or "").strip()
        if title:
            self.border_title = title

        if isinstance(self._list_widget, DataTable):
            dt = self._list_widget
            if isinstance(dlg, ListDialog):
                dt.add_column("", key="col0")
                for row in dlg.rows:
                    dt.add_row(_to_markup(row.text))
            elif isinstance(dlg, TablistDialog):
                if dlg.rows:
                    for i in range(len(dlg.rows[0].columns)):
                        dt.add_column("", key=f"col{i}")
                    for row in dlg.rows:
                        dt.add_row(*(_to_markup(c) for c in row.columns))
            elif isinstance(dlg, TablistHeadersDialog):
                hdr = self.query_one(".datatable-header", Static)
                headers_plain = [_strip_colors(h) for h in dlg.headers]
                col_widths = [len(h) for h in headers_plain]
                for row in dlg.rows:
                    for i, col in enumerate(row.columns):
                        col_widths[i] = max(col_widths[i], len(_strip_colors(col)))
                hdr.update("".join(
                    f" {h:<{w}} " for h, w in zip(headers_plain, col_widths)
                ))
                for i in range(len(dlg.headers)):
                    dt.add_column("", key=f"col{i}")
                for row in dlg.rows:
                    dt.add_row(*(_to_markup(c) for c in row.columns))

    def on_key(self, event) -> None:
        if event.key == "escape" and not self._dialog.is_responded:
            event.prevent_default()
            event.stop()
            self._dialog.cancel()
            self._mark_responded(return_focus=True)

    @on(Input.Submitted)
    async def _on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        if self._dialog.is_responded:
            return
        dlg = self._dialog
        if isinstance(dlg, (InputDialog, PasswordDialog)):
            text = self._input_widget.value if self._input_widget else ""
            dlg.submit(text)
            self._mark_responded(return_focus=True)

    @on(DataTable.RowSelected)
    async def _on_table_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        if self._btn1 and not self._dialog.is_responded:
            await self._on_button_pressed(Button.Pressed(self._btn1))

    @on(Button.Pressed)
    async def _on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._dialog.is_responded:
            return
        focused = self.has_pseudo_class("focus-within")
        if event.button is self._btn1:
            dlg = self._dialog
            if isinstance(dlg, (InputDialog, PasswordDialog)):
                text = self._input_widget.value if self._input_widget else ""
                dlg.submit(text)
            elif isinstance(dlg, (ListDialog, TablistDialog, TablistHeadersDialog)):
                selected_idx = 0
                if isinstance(self._list_widget, DataTable):
                    crow = self._list_widget.cursor_row
                    selected_idx = crow if crow is not None else 0
                dlg.rows[selected_idx].select()
            else:
                dlg.ok()
            self._mark_responded(return_focus=focused)
        elif event.button is self._btn2:
            self._dialog.cancel()
            self._mark_responded(return_focus=focused)

    def _focus_interactive(self) -> None:
        if self._input_widget is not None:
            self._input_widget.focus()
        elif self._list_widget is not None:
            self._list_widget.focus()
        elif self._btn1 is not None:
            self._btn1.focus()

    def _mark_responded(self, *, return_focus: bool = False) -> None:
        self.add_class("responded")
        if self._btn1:
            self._btn1.disabled = True
        if self._btn2:
            self._btn2.disabled = True
        if self._input_widget:
            self._input_widget.read_only = True
            self._input_widget.can_focus = False
        if self._list_widget is not None:
            self._list_widget.can_focus = False
        if return_focus:
            self.set_timer(0.3, self._maybe_return_focus)

    def _maybe_return_focus(self) -> None:
        from pyraksamp.shell._app import SampShellApp

        group = self.parent
        if not isinstance(group, DialogGroupWidget):
            return
        # If a cascade happened, a new pane is now last — don't steal focus
        if group._panes[-1] is not self:
            return
        if isinstance(self.app, SampShellApp):
            self.app.set_hint("")
            self.app._chat_input.focus()

    def mark_responded_externally(self) -> None:
        """Called when dialog was responded outside the TUI (e.g. via bot.on_dialog)."""
        self._mark_responded()


# ── DialogGroupWidget ─────────────────────────────────────────────────────────


class DialogGroupWidget(Vertical):
    """Horizontal-navigable group of one or more dialog panes with cascade logic."""

    _CASCADE_DELAY = 5.0  # seconds

    DEFAULT_CSS = """
    DialogGroupWidget {
        height: auto;
        margin: 0;
        padding: 0;
        background: transparent;
    }
    DialogGroupWidget > .pane-nav {
        height: 1;
        color: ansi_bright_black;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._panes: list[DialogWidget] = []
        self._current: int = 0
        self._sealed: bool = False
        self._cascade_timer = None
        self._nav_label: Label | None = None

    def compose(self) -> ComposeResult:
        self._nav_label = Label("", classes="pane-nav")
        yield self._nav_label

    async def add_dialog(self, dialog: AnyDialog) -> DialogWidget:
        """Add a dialog pane to this group and reset cascade timer."""
        prev_focused = (
            self._panes[-1].has_pseudo_class("focus-within") if self._panes else False
        )
        pane = DialogWidget(dialog)
        self._panes.append(pane)
        # Hide all previous panes; only the newest is shown.
        for p in self._panes[:-1]:
            p.display = False
        await self.mount(pane)
        self._current = len(self._panes) - 1
        self._update_nav()
        self._reset_cascade_timer()
        if prev_focused:
            pane._focus_interactive()
        return pane

    def _update_nav(self) -> None:
        from pyraksamp.shell._app import SampShellApp

        if not isinstance(self.app, SampShellApp):
            return

        if self._nav_label is None:
            return

        if len(self._panes) <= 1:
            self._nav_label.update("")
            self.app.set_hint("")
        else:
            # Count stays local and bright
            self._nav_label.update(f"Dialog {self._current + 1}/{len(self._panes)}")
            # Only show hint if the group or its children are focused
            if self.has_focus or self.has_pseudo_class("focus-within"):
                self.app.set_hint("[Alt+←/→ to navigate]", dim=True)
            else:
                self.app.set_hint("")

    def on_descendant_focus(self) -> None:
        self._update_nav()

    def on_descendant_blur(self) -> None:
        # Give a small delay to check if focus moved to another child
        self.set_timer(0.05, self._update_nav)

    def _reset_cascade_timer(self) -> None:
        if self._cascade_timer is not None:
            self._cascade_timer.stop()
        self._cascade_timer = self.set_timer(self._CASCADE_DELAY, self._seal)

    def _seal(self) -> None:
        self._sealed = True

    @property
    def is_sealed(self) -> bool:
        return self._sealed

    def _show_current(self) -> None:
        for i, pane in enumerate(self._panes):
            pane.display = i == self._current

    def action_prev_pane(self) -> None:
        if self._current > 0:
            self._current -= 1
            self._show_current()
            self._update_nav()

    def action_next_pane(self) -> None:
        if self._current < len(self._panes) - 1:
            self._current += 1
            self._show_current()
            self._update_nav()

    @property
    def is_responded(self) -> bool:
        """True once every dialog pane in this group has been responded to."""
        if not self._panes:
            return False
        return all(pane._dialog.is_responded for pane in self._panes)

    def get_pane_for_dialog(self, dialog: AnyDialog) -> DialogWidget | None:
        for pane in self._panes:
            if pane._dialog is dialog:
                return pane
        return None


# ── EventLog ──────────────────────────────────────────────────────────────────


class EventLog(ScrollableContainer):
    """Scrollable log container.

    Each entry is either a LogLine (simple text) or a DialogGroupWidget.
    Old LogLine entries beyond *max_lines* are pruned automatically.
    """

    MAX_LINES = 2000

    DEFAULT_CSS = """
    EventLog {
        height: 1fr;
        overflow-y: auto;
        scrollbar-size: 0 0;
        border: none;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._line_count = 0
        self._active_group: DialogGroupWidget | None = None
        self._want_scroll = False

    def _capture_scroll_intent(self) -> None:
        """Call BEFORE mounting new content.

        Records whether the user is at the bottom right now, so that
        _auto_scroll() can scroll after the layout has been updated —
        without comparing the old scroll_y against the new (larger) max_scroll_y.
        """
        at_bottom = self.max_scroll_y == 0 or self.scroll_y >= self.max_scroll_y - 2
        if at_bottom:
            self._want_scroll = True

    async def append_line(self, text: str, *, style: str = "") -> None:
        """Append a plain text log entry.

        If there are any unresponded dialog groups, keep them pinned at the bottom
        by inserting the new line before the first such group found.
        """
        self._capture_scroll_intent()
        line = LogLine(text, style=style)

        # Find the first unresponded group to pin before
        first_unresponded = None
        for child in self.children:
            if isinstance(child, DialogGroupWidget) and not child.is_responded:
                first_unresponded = child
                break

        if first_unresponded is not None:
            await self.mount(line, before=first_unresponded)
        else:
            await self.mount(line)

        self._line_count += 1
        self._prune()
        self.call_after_refresh(self._auto_scroll)

    async def get_or_create_dialog_group(self) -> DialogGroupWidget:
        """Return the active unsealed group, or create a new one."""
        # Reuse group only if it is not sealed AND not yet responded to.
        if (
            self._active_group is not None
            and not self._active_group.is_sealed
            and not self._active_group.is_responded
        ):
            return self._active_group
        self._capture_scroll_intent()
        group = DialogGroupWidget()
        await self.mount(group)
        self._active_group = group
        self.call_after_refresh(self._auto_scroll)
        return group

    def _prune(self) -> None:
        if self._line_count <= self.MAX_LINES:
            return
        excess = self._line_count - self.MAX_LINES
        children = list(self.query(LogLine))
        for child in children[:excess]:
            child.remove()
            self._line_count -= 1

    def _auto_scroll(self) -> None:
        """Scroll to bottom if _capture_scroll_intent() decided we should."""
        if self._want_scroll:
            self._want_scroll = False
            self.scroll_end(animate=False)


# ── TextdrawPanel ─────────────────────────────────────────────────────────────


class TextdrawPanel(ListView):
    """Inline textdraw list, togglable via :textdraws command."""

    DEFAULT_CSS = """
    TextdrawPanel {
        height: auto;
        max-height: 8;
        border: round $accent;
        margin: 0;
        scrollbar-size: 0 0;
    }
    """

    def __init__(self, bot) -> None:
        super().__init__()
        self._bot = bot
        self._watch_task: asyncio.Task | None = None

    async def on_mount(self) -> None:
        self._refresh_list()
        self._watch_task = asyncio.create_task(self._watch_changes())

    def on_unmount(self) -> None:
        if self._watch_task:
            self._watch_task.cancel()

    def _refresh_list(self) -> None:
        self.clear()
        for td in self._bot.textdraws.all():
            from pyraksamp.textdraws import SelectableTextDraw

            sel_marker = "[SEL]" if isinstance(td, SelectableTextDraw) else "[ ]  "
            text_preview = (td.text or "")[:40]
            self.append(ListItem(Label(f"{sel_marker} {td.id}  {text_preview!r}")))

    async def _watch_changes(self) -> None:
        cond = self._bot.textdraws._condition
        while True:
            try:
                async with cond:
                    await cond.wait()
                self.call_from_thread(self._refresh_list)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.5)

    @on(ListView.Selected)
    async def _on_selected(self, event: ListView.Selected) -> None:
        """Click the textdraw if it's selectable."""
        tds = self._bot.textdraws.all()
        idx = self.index
        if idx is None or idx >= len(tds):
            return
        td = tds[idx]
        from pyraksamp.textdraws import SelectableTextDraw

        if isinstance(td, SelectableTextDraw):
            td.click()
