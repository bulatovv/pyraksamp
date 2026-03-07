"""Typed dialog objects with rich interaction APIs."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import ClassVar, Literal


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
    "DialogAlreadyRespondedError",
]


class DialogAlreadyRespondedError(Exception):
    """Raised when a dialog is responded to more than once."""

    def __init__(self, dialog_id: int) -> None:
        super().__init__(f"dialog {dialog_id} has already been responded to")
        self.dialog_id = dialog_id


class _Responder:
    """Tracks response state for a single dialog event."""

    __slots__ = ("_fn", "_responded")

    def __init__(self, fn) -> None:
        self._fn = fn
        self._responded = False

    @property
    def is_responded(self) -> bool:
        return self._responded

    def send_dialog_response(self, dialog_id: int, /, **kwargs) -> None:
        if self._responded:
            raise DialogAlreadyRespondedError(dialog_id)
        self._responded = True
        self._fn(dialog_id, **kwargs)


# ── Buttons ────────────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class Button:
    """A dialog button. SA:MP IDs: 1 = first/OK, 0 = second/Cancel."""

    label: str
    id: int
    _dialog_id: int = field(repr=False, compare=False)
    _responder: _Responder = field(repr=False, compare=False)

    def click(self) -> None:
        """Send this button's response to the server."""
        self._responder.send_dialog_response(self._dialog_id, button=self.id)


class ButtonSelector:
    """Selector for dialog buttons. Positional: [0]=left/OK, [1]=right/Cancel."""

    __slots__ = ("_buttons",)

    def __init__(self, buttons: tuple[Button, ...]) -> None:
        self._buttons = buttons

    def __getitem__(self, idx: int) -> Button:
        return self._buttons[idx]

    def __call__(self, pred: Callable[[Button], bool]) -> Button:
        """Return the first button matching ``pred``.

        Raises
        ------
        ValueError
            If no button matches.
        """
        for b in self._buttons:
            if pred(b):
                return b
        raise ValueError("no button matches predicate")

    def __iter__(self) -> Iterator[Button]:
        return iter(self._buttons)

    def __len__(self) -> int:
        return len(self._buttons)


def _make_buttons(
    dialog_id: int, button1: str, button2: str, responder: _Responder
) -> ButtonSelector:
    # [0]=left/OK (wire id=1), [1]=right/Cancel (wire id=0)
    left = Button(label=button1, id=1, _dialog_id=dialog_id, _responder=responder)
    if button2:
        right = Button(label=button2, id=0, _dialog_id=dialog_id, _responder=responder)
        return ButtonSelector((left, right))
    return ButtonSelector((left,))


# ── Rows ───────────────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class ListRow:
    """A single row in a list dialog."""

    text: str
    index: int
    _dialog_id: int = field(repr=False, compare=False)
    _responder: _Responder = field(repr=False, compare=False)

    def select(self) -> None:
        """Send a selection response for this row."""
        self._responder.send_dialog_response(
            self._dialog_id, button=1, list_item=self.index
        )


@dataclass(slots=True, frozen=True)
class TablistRow:
    """A single row in a tablist dialog, with tab-separated column values."""

    columns: tuple[str, ...]
    index: int
    _dialog_id: int = field(repr=False, compare=False)
    _responder: _Responder = field(repr=False, compare=False)

    def select(self) -> None:
        """Send a selection response for this row."""
        self._responder.send_dialog_response(
            self._dialog_id, button=1, list_item=self.index
        )

    def __getitem__(self, col: int) -> str:
        return self.columns[col]

    def __iter__(self) -> Iterator[str]:
        return iter(self.columns)


class RowSelector[_R]:
    """Indexed and predicate-searchable collection of dialog rows."""

    __slots__ = ("_rows",)

    def __init__(self, rows: list[_R]) -> None:
        self._rows = rows

    def __getitem__(self, idx: int) -> _R:
        return self._rows[idx]

    def __call__(self, pred: Callable[[_R], bool]) -> _R:
        """Return the first row matching ``pred``.

        Raises
        ------
        ValueError
            If no row matches.
        """
        for r in self._rows:
            if pred(r):
                return r
        raise ValueError("no row matches predicate")

    def __iter__(self) -> Iterator[_R]:
        return iter(self._rows)

    def __len__(self) -> int:
        return len(self._rows)


# ── Dialog types ───────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class MsgboxDialog:
    """A message box dialog with OK/Cancel buttons (style 0)."""

    style: ClassVar[Literal[0]] = 0
    dialog_id: int
    title: str
    body: str
    button1: str
    button2: str
    buttons: ButtonSelector
    _responder: _Responder = field(repr=False, compare=False)

    @property
    def is_responded(self) -> bool:
        return self._responder.is_responded

    def ok(self) -> None:
        """Send the OK (first button) response."""
        self._responder.send_dialog_response(self.dialog_id, button=1)

    def cancel(self) -> None:
        """Send the Cancel (second button) response."""
        self._responder.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True, frozen=True)
class InputDialog:
    """A text input dialog (style 1)."""

    style: ClassVar[Literal[1]] = 1
    dialog_id: int
    title: str
    body: str
    button1: str
    button2: str
    buttons: ButtonSelector
    _responder: _Responder = field(repr=False, compare=False)

    @property
    def is_responded(self) -> bool:
        return self._responder.is_responded

    def submit(self, text: str = "") -> None:
        """Send the OK response with the given text input."""
        self._responder.send_dialog_response(self.dialog_id, button=1, text=text)

    def cancel(self) -> None:
        """Send the Cancel response."""
        self._responder.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True, frozen=True)
class PasswordDialog:
    """A masked-input (password) dialog (style 3)."""

    style: ClassVar[Literal[3]] = 3
    dialog_id: int
    title: str
    body: str
    button1: str
    button2: str
    buttons: ButtonSelector
    _responder: _Responder = field(repr=False, compare=False)

    @property
    def is_responded(self) -> bool:
        return self._responder.is_responded

    def submit(self, text: str = "") -> None:
        """Send the OK response with the given password."""
        self._responder.send_dialog_response(self.dialog_id, button=1, text=text)

    def cancel(self) -> None:
        """Send the Cancel response."""
        self._responder.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True, frozen=True)
class ListDialog:
    """A scrollable list dialog (style 2)."""

    style: ClassVar[Literal[2]] = 2
    dialog_id: int
    title: str
    button1: str
    button2: str
    rows: RowSelector[ListRow]
    _responder: _Responder = field(repr=False, compare=False)

    @property
    def is_responded(self) -> bool:
        return self._responder.is_responded

    def cancel(self) -> None:
        """Send the Cancel response."""
        self._responder.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True, frozen=True)
class TablistDialog:
    """A tabular list dialog without column headers (style 4)."""

    style: ClassVar[Literal[4]] = 4
    dialog_id: int
    title: str
    button1: str
    button2: str
    rows: RowSelector[TablistRow]
    _responder: _Responder = field(repr=False, compare=False)

    @property
    def is_responded(self) -> bool:
        return self._responder.is_responded

    def cancel(self) -> None:
        """Send the Cancel response."""
        self._responder.send_dialog_response(self.dialog_id, button=0)


@dataclass(slots=True, frozen=True)
class TablistHeadersDialog:
    """A tabular list dialog with column headers (style 5)."""

    style: ClassVar[Literal[5]] = 5
    dialog_id: int
    title: str
    button1: str
    button2: str
    headers: tuple[str, ...]
    rows: RowSelector[TablistRow]
    _responder: _Responder = field(repr=False, compare=False)

    @property
    def is_responded(self) -> bool:
        return self._responder.is_responded

    def cancel(self) -> None:
        """Send the Cancel response."""
        self._responder.send_dialog_response(self.dialog_id, button=0)


type AnyDialog = (
    MsgboxDialog
    | InputDialog
    | PasswordDialog
    | ListDialog
    | TablistDialog
    | TablistHeadersDialog
)


# ── Factory ────────────────────────────────────────────────────────────────────


def _make_dialog(
    did: int,
    style: int,
    title: str,
    btn1: str,
    btn2: str,
    body: str,
    responder: _Responder,
) -> AnyDialog:
    buttons = _make_buttons(did, btn1, btn2, responder)

    if style == 0:
        return MsgboxDialog(
            dialog_id=did,
            title=title,
            body=body,
            button1=btn1,
            button2=btn2,
            buttons=buttons,
            _responder=responder,
        )
    if style == 1:
        return InputDialog(
            dialog_id=did,
            title=title,
            body=body,
            button1=btn1,
            button2=btn2,
            buttons=buttons,
            _responder=responder,
        )
    if style == 3:
        return PasswordDialog(
            dialog_id=did,
            title=title,
            body=body,
            button1=btn1,
            button2=btn2,
            buttons=buttons,
            _responder=responder,
        )
    if style == 2:
        rows: RowSelector[ListRow] = RowSelector(
            [
                ListRow(text=line, index=i, _dialog_id=did, _responder=responder)
                for i, line in enumerate(ln for ln in body.split("\n") if ln)
            ]
        )
        return ListDialog(
            dialog_id=did,
            title=title,
            button1=btn1,
            button2=btn2,
            rows=rows,
            _responder=responder,
        )
    if style == 4:
        rows_t: RowSelector[TablistRow] = RowSelector(
            [
                TablistRow(
                    columns=tuple(line.split("\t")),
                    index=i,
                    _dialog_id=did,
                    _responder=responder,
                )
                for i, line in enumerate(ln for ln in body.split("\n") if ln)
            ]
        )
        return TablistDialog(
            dialog_id=did,
            title=title,
            button1=btn1,
            button2=btn2,
            rows=rows_t,
            _responder=responder,
        )
    if style == 5:
        lines = [ln for ln in body.split("\n") if ln]
        headers = tuple(lines[0].split("\t")) if lines else ()
        rows_th: RowSelector[TablistRow] = RowSelector(
            [
                TablistRow(
                    columns=tuple(line.split("\t")),
                    index=i,
                    _dialog_id=did,
                    _responder=responder,
                )
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
            _responder=responder,
        )
    # Unknown style — treat as msgbox
    return MsgboxDialog(
        dialog_id=did,
        title=title,
        body=body,
        button1=btn1,
        button2=btn2,
        buttons=buttons,
        _responder=responder,
    )
