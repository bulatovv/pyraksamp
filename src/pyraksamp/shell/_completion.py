"""Reusable completion primitives for the pyraksamp shell TUI."""

from __future__ import annotations

from dataclasses import dataclass, field
from textual.markup import escape
from textual.widgets import Static


@dataclass
class CompletionItem:
    insert: str       # text inserted into input on confirm
    label: str        # first column: name + metavar
    description: str = field(default="")


# ── CommandHistory ─────────────────────────────────────────────────────────────


class CommandHistory:
    """Ordered unique command history with Up/Down navigation support."""

    _MAX = 500

    def __init__(self) -> None:
        self._entries: list[str] = []
        self._nav_pos: int | None = None   # None = at end (not navigating)
        self._nav_saved: str = ""          # input captured when navigation started

    def add(self, command: str) -> None:
        command = command.strip()
        if not command:
            return
        try:
            self._entries.remove(command)
        except ValueError:
            pass
        self._entries.append(command)
        if len(self._entries) > self._MAX:
            self._entries.pop(0)
        self._nav_pos = None
        self._nav_saved = ""

    def navigate_up(self, current: str) -> str | None:
        """Go to older entry.  Saves *current* on first call.
        Returns entry text, or None if already at oldest."""
        if not self._entries:
            return None
        if self._nav_pos is None:
            self._nav_saved = current
            self._nav_pos = len(self._entries) - 1
        elif self._nav_pos > 0:
            self._nav_pos -= 1
        else:
            return None
        return self._entries[self._nav_pos]

    def navigate_down(self) -> str:
        """Go to newer entry.  Returns saved input when stepping past the end."""
        if self._nav_pos is None:
            return ""
        if self._nav_pos < len(self._entries) - 1:
            self._nav_pos += 1
            return self._entries[self._nav_pos]
        saved = self._nav_saved
        self._nav_pos = None
        self._nav_saved = ""
        return saved

    def navigate_reset(self) -> None:
        self._nav_pos = None
        self._nav_saved = ""

    def completions(self, prefix: str) -> list[str]:
        """Return entries that start with *prefix*, most recent first."""
        return [e for e in reversed(self._entries) if e.startswith(prefix)]


# ── CompletionMenu ─────────────────────────────────────────────────────────────


class CompletionMenu(Static):
    """Non-focusable completion popup rendered above the input bar.

    Items are ``(text, description)`` pairs.  *text* is what gets inserted
    into the input on confirmation; *description* is shown dimmed after it.
    """

    can_focus = False

    DEFAULT_CSS = """
    CompletionMenu {
        height: auto;
        max-height: 8;
        background: transparent;
        color: ansi_white;
        padding: 0 1;
        display: none;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._items: list[CompletionItem] = []
        self._index: int = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self.display and bool(self._items)

    @property
    def selected(self) -> str | None:
        if self._items:
            return self._items[self._index].insert
        return None

    def open(self, items: list[CompletionItem]) -> None:
        """Show the menu with *items*.  No-op if list is empty."""
        if not items:
            return
        self._items = items
        self._index = 0
        self._refresh()
        self.display = True

    def close(self) -> None:
        self.display = False
        self._items = []

    def move(self, delta: int) -> str | None:
        """Advance selection by *delta* (wraps around).  Returns insert text."""
        if not self._items:
            return None
        self._index = (self._index + delta) % len(self._items)
        self._refresh()
        return self.selected

    # ── Internal ───────────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        col_w = max(len(item.label) for item in self._items)
        lines = []
        for i, item in enumerate(self._items):
            label = f"{escape(item.label):<{col_w}}"
            if i == self._index:
                line = f"[reverse] {label} [/reverse]"
            else:
                line = f" {label} "
            if item.description:
                line += f"  [dim]{escape(item.description)}[/dim]"
            lines.append(line)
        self.update("\n".join(lines))
