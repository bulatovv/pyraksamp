"""Typed dialog objects with rich interaction APIs."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Generic, Literal, TypeVar

if TYPE_CHECKING:
    from pyraksamp import SAMPBot

_R = TypeVar("_R")

__all__ = [
    "AnyDialog",
    "MsgboxDialog",
    "InputDialog",
    "PasswordDialog",
    "ListDialog",
    "TablistDialog",
    "TablistHeadersDialog",
    "Button",
    "ButtonSelector",
    "ListRow",
    "TablistRow",
    "RowSelector",
]


# ── Buttons ────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class Button:
    """A dialog button. SA:MP IDs: 1 = first/OK, 0 = second/Cancel."""

    label: str
    id: int  # SA:MP button ID: 1=first, 0=second
    _dialog_id: int = field(repr=False, compare=False)
    _bot: SAMPBot = field(repr=False, compare=False)

    def click(self) -> None:
        self._bot.send_dialog_response(self._dialog_id, button=self.id)


class ButtonSelector:
    """Selector for dialog buttons. Positional: [0]=left/OK, [1]=right/Cancel.

    Stored as a 2-element list:
        _buttons[0] = left/first (always present)
        _buttons[1] = right/second (None if no second button)
    """

    __slots__ = ("_buttons",)

    def __init__(self, buttons: list[Button | None]) -> None:
        self._buttons = buttons  # [0]=left, [1]=right

    def __getitem__(self, idx: int) -> Button:
        btn = self._buttons[idx]
        if btn is None:
            raise KeyError(idx)
        return btn

    def __call__(self, pred: Callable[[Button], bool]) -> Button:
        for b in self._buttons:
            if b is not None and pred(b):
                return b
        raise ValueError("no button matches predicate")

    def __iter__(self) -> Iterator[Button]:
        return (b for b in self._buttons if b is not None)

    def __len__(self) -> int:
        return sum(1 for b in self._buttons if b is not None)


def _make_buttons(
    dialog_id: int, button1: str, button2: str, bot: SAMPBot
) -> ButtonSelector:
    # [0]=left/OK (wire id=1), [1]=right/Cancel (wire id=0)
    left = Button(label=button1, id=1, _dialog_id=dialog_id, _bot=bot)
    right = (
        Button(label=button2, id=0, _dialog_id=dialog_id, _bot=bot) if button2 else None
    )
    return ButtonSelector([left, right])


# ── Rows ───────────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class ListRow:
    text: str
    index: int
    _dialog_id: int = field(repr=False, compare=False)
    _bot: SAMPBot = field(repr=False, compare=False)

    def select(self) -> None:
        self._bot.send_dialog_response(self._dialog_id, button=1, list_item=self.index)


@dataclass(slots=True)
class TablistRow:
    columns: list[str]
    index: int
    _dialog_id: int = field(repr=False, compare=False)
    _bot: SAMPBot = field(repr=False, compare=False)

    def select(self) -> None:
        self._bot.send_dialog_response(self._dialog_id, button=1, list_item=self.index)

    def __getitem__(self, col: int) -> str:
        return self.columns[col]

    def __iter__(self) -> Iterator[str]:
        return iter(self.columns)


class RowSelector(Generic[_R]):
    __slots__ = ("_rows",)

    def __init__(self, rows: list[_R]) -> None:
        self._rows = rows

    def __getitem__(self, idx: int) -> _R:
        return self._rows[idx]

    def __call__(self, pred: Callable[[_R], bool]) -> _R:
        for r in self._rows:
            if pred(r):
                return r
        raise ValueError("no row matches predicate")

    def __iter__(self) -> Iterator[_R]:
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)


# ── Dialog types ───────────────────────────────────────────────────────────────


@dataclass(slots=True)
class MsgboxDialog:
    style: ClassVar[Literal[0]] = 0
    dialog_id: int
    title: str
    body: str
    button1: str
    button2: str
    buttons: ButtonSelector
    _bot: SAMPBot = field(repr=False, compare=False)

    def ok(self) -> None:
        self._bot.send_dialog_response(self.dialog_id, button=1)

    def cancel(self) -> None:
        self._bot.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True)
class InputDialog:
    style: ClassVar[Literal[1]] = 1
    dialog_id: int
    title: str
    body: str
    button1: str
    button2: str
    buttons: ButtonSelector
    _bot: SAMPBot = field(repr=False, compare=False)

    def submit(self, text: str = "") -> None:
        self._bot.send_dialog_response(self.dialog_id, button=1, text=text)

    def cancel(self) -> None:
        self._bot.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True)
class PasswordDialog:
    style: ClassVar[Literal[3]] = 3
    dialog_id: int
    title: str
    body: str
    button1: str
    button2: str
    buttons: ButtonSelector
    _bot: SAMPBot = field(repr=False, compare=False)

    def submit(self, text: str = "") -> None:
        self._bot.send_dialog_response(self.dialog_id, button=1, text=text)

    def cancel(self) -> None:
        self._bot.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True)
class ListDialog:
    style: ClassVar[Literal[2]] = 2
    dialog_id: int
    title: str
    button1: str
    button2: str
    rows: RowSelector[ListRow]
    _bot: SAMPBot = field(repr=False, compare=False)

    def cancel(self) -> None:
        self._bot.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True)
class TablistDialog:
    style: ClassVar[Literal[4]] = 4
    dialog_id: int
    title: str
    button1: str
    button2: str
    rows: RowSelector[TablistRow]
    _bot: SAMPBot = field(repr=False, compare=False)

    def cancel(self) -> None:
        self._bot.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True)
class TablistHeadersDialog:
    style: ClassVar[Literal[5]] = 5
    dialog_id: int
    title: str
    button1: str
    button2: str
    headers: list[str]
    rows: RowSelector[TablistRow]
    _bot: SAMPBot = field(repr=False, compare=False)

    def cancel(self) -> None:
        self._bot.send_dialog_response(self.dialog_id, button=0)


AnyDialog = (
    MsgboxDialog
    | InputDialog
    | PasswordDialog
    | ListDialog
    | TablistDialog
    | TablistHeadersDialog
)


# ── Factory ────────────────────────────────────────────────────────────────────


def _make_dialog(
    did: int, style: int, title: str, btn1: str, btn2: str, body: str, bot: SAMPBot
) -> AnyDialog:
    buttons = _make_buttons(did, btn1, btn2, bot)

    if style == 0:
        return MsgboxDialog(
            dialog_id=did,
            title=title,
            body=body,
            button1=btn1,
            button2=btn2,
            buttons=buttons,
            _bot=bot,
        )
    if style == 1:
        return InputDialog(
            dialog_id=did,
            title=title,
            body=body,
            button1=btn1,
            button2=btn2,
            buttons=buttons,
            _bot=bot,
        )
    if style == 3:
        return PasswordDialog(
            dialog_id=did,
            title=title,
            body=body,
            button1=btn1,
            button2=btn2,
            buttons=buttons,
            _bot=bot,
        )
    if style == 2:
        rows: RowSelector[ListRow] = RowSelector(
            [
                ListRow(text=line, index=i, _dialog_id=did, _bot=bot)
                for i, line in enumerate(ln for ln in body.split("\n") if ln)
            ]
        )
        return ListDialog(
            dialog_id=did,
            title=title,
            button1=btn1,
            button2=btn2,
            rows=rows,
            _bot=bot,
        )
    if style == 4:
        rows_t: RowSelector[TablistRow] = RowSelector(
            [
                TablistRow(columns=line.split("\t"), index=i, _dialog_id=did, _bot=bot)
                for i, line in enumerate(ln for ln in body.split("\n") if ln)
            ]
        )
        return TablistDialog(
            dialog_id=did,
            title=title,
            button1=btn1,
            button2=btn2,
            rows=rows_t,
            _bot=bot,
        )
    if style == 5:
        lines = [ln for ln in body.split("\n") if ln]
        headers = lines[0].split("\t") if lines else []
        rows_th: RowSelector[TablistRow] = RowSelector(
            [
                TablistRow(columns=line.split("\t"), index=i, _dialog_id=did, _bot=bot)
                for i, line in enumerate(lines[1:])
            ]
        )
        return TablistHeadersDialog(
            dialog_id=did,
            title=title,
            button1=btn1,
            button2=btn2,
            headers=headers,
            rows=rows_th,
            _bot=bot,
        )
    # Unknown style — treat as msgbox
    return MsgboxDialog(
        dialog_id=did,
        title=title,
        body=body,
        button1=btn1,
        button2=btn2,
        buttons=buttons,
        _bot=bot,
    )
