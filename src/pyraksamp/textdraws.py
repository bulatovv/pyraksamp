"""Live textdraw registry — mirrors what the player currently sees."""

from __future__ import annotations
import asyncio
from collections.abc import Callable
from typing import Literal, overload


class TextDraw:
    """Mutable mirror of a single server textdraw. Updated in-place by show/edit."""

    __slots__ = (
        "id",
        "text",
        "x",
        "y",
        "style",
        "flags",
        "letter_width",
        "letter_height",
        "letter_color",
        "line_width",
        "line_height",
        "box_color",
        "shadow",
        "outline",
        "background_color",
        "model_id",
        "rot_x",
        "rot_y",
        "rot_z",
        "zoom",
        "color1",
        "color2",
    )

    def __init__(
        self,
        td_id: int,
        flags: int,
        lw: float,
        lh: float,
        lcol: int,
        linew: float,
        lineh: float,
        bcol: int,
        shadow: int,
        outline: int,
        bgcol: int,
        style: int,
        x: float,
        y: float,
        model: int,
        rx: float,
        ry: float,
        rz: float,
        zoom: float,
        col1: int,
        col2: int,
        text: str,
    ) -> None:
        self.id = td_id
        self._update(
            flags,
            lw,
            lh,
            lcol,
            linew,
            lineh,
            bcol,
            shadow,
            outline,
            bgcol,
            style,
            x,
            y,
            model,
            rx,
            ry,
            rz,
            zoom,
            col1,
            col2,
            text,
        )

    def _update(
        self,
        flags: int,
        lw: float,
        lh: float,
        lcol: int,
        linew: float,
        lineh: float,
        bcol: int,
        shadow: int,
        outline: int,
        bgcol: int,
        style: int,
        x: float,
        y: float,
        model: int,
        rx: float,
        ry: float,
        rz: float,
        zoom: float,
        col1: int,
        col2: int,
        text: str,
    ) -> None:
        self.flags = flags
        self.letter_width = lw
        self.letter_height = lh
        self.letter_color = lcol
        self.line_width = linew
        self.line_height = lineh
        self.box_color = bcol
        self.shadow = shadow
        self.outline = outline
        self.background_color = bgcol
        self.style = style
        self.x = x
        self.y = y
        self.model_id = model
        self.rot_x = rx
        self.rot_y = ry
        self.rot_z = rz
        self.zoom = zoom
        self.color1 = col1
        self.color2 = col2
        self.text = text

    def _update_text(self, text: str) -> None:
        self.text = text

    def __repr__(self) -> str:
        return f"TextDraw(id={self.id}, text={self.text!r})"


class SelectableTextDraw(TextDraw):
    """A textdraw with selectable=1 — can be clicked."""

    __slots__ = ("_click_fn",)

    _click_fn: Callable[[int], None]

    def click(self) -> None:
        """Send SelectTextDraw RPC (83) for this textdraw."""
        self._click_fn(self.id)

    def __repr__(self) -> str:
        return f"SelectableTextDraw(id={self.id}, text={self.text!r})"


def _make_textdraw(
    td_id: int,
    flags: int,
    lw: float,
    lh: float,
    lcol: int,
    linew: float,
    lineh: float,
    bcol: int,
    shadow: int,
    outline: int,
    bgcol: int,
    style: int,
    x: float,
    y: float,
    model: int,
    rx: float,
    ry: float,
    rz: float,
    zoom: float,
    col1: int,
    col2: int,
    text: str,
    selectable: int,
    click_fn,
) -> TextDraw:
    """Factory: returns SelectableTextDraw if selectable==1, else TextDraw."""
    if selectable:
        td = SelectableTextDraw.__new__(SelectableTextDraw)
        td.id = td_id
        td._click_fn = click_fn
    else:
        td = TextDraw.__new__(TextDraw)
        td.id = td_id
    td._update(
        flags,
        lw,
        lh,
        lcol,
        linew,
        lineh,
        bcol,
        shadow,
        outline,
        bgcol,
        style,
        x,
        y,
        model,
        rx,
        ry,
        rz,
        zoom,
        col1,
        col2,
        text,
    )
    return td


class TextDraws:
    """Live registry of currently visible textdraws."""

    def __init__(self, click_fn=None) -> None:
        self._registry: dict[int, TextDraw] = {}
        self._condition: asyncio.Condition = asyncio.Condition()
        self._click_fn = click_fn

    async def _on_show(
        self,
        td_id: int,
        flags: int,
        lw: float,
        lh: float,
        lcol: int,
        linew: float,
        lineh: float,
        bcol: int,
        shadow: int,
        outline: int,
        bgcol: int,
        style: int,
        sel: int,
        x: float,
        y: float,
        model: int,
        rx: float,
        ry: float,
        rz: float,
        zoom: float,
        col1: int,
        col2: int,
        text: str,
    ) -> None:
        async with self._condition:
            existing = self._registry.get(td_id)
            if existing is not None and isinstance(
                existing, SelectableTextDraw
            ) == bool(sel):
                existing._update(
                    flags,
                    lw,
                    lh,
                    lcol,
                    linew,
                    lineh,
                    bcol,
                    shadow,
                    outline,
                    bgcol,
                    style,
                    x,
                    y,
                    model,
                    rx,
                    ry,
                    rz,
                    zoom,
                    col1,
                    col2,
                    text,
                )
            else:
                self._registry[td_id] = _make_textdraw(
                    td_id,
                    flags,
                    lw,
                    lh,
                    lcol,
                    linew,
                    lineh,
                    bcol,
                    shadow,
                    outline,
                    bgcol,
                    style,
                    x,
                    y,
                    model,
                    rx,
                    ry,
                    rz,
                    zoom,
                    col1,
                    col2,
                    text,
                    sel,
                    self._click_fn,
                )
            self._condition.notify_all()

    async def _on_hide(self, td_id: int) -> None:
        async with self._condition:
            self._registry.pop(td_id, None)
            self._condition.notify_all()

    async def _on_edit(self, td_id: int, text: str) -> None:
        async with self._condition:
            td = self._registry.get(td_id)
            if td is not None:
                td._update_text(text)
                self._condition.notify_all()

    async def _on_toggle_select(self, enable: bool, color: int) -> None:
        pass  # informational only; no registry mutation needed

    async def _on_disconnect(self) -> None:
        async with self._condition:
            self._registry.clear()
            self._condition.notify_all()

    def all(self) -> list[TextDraw]:
        """Return all currently visible textdraws."""
        return list(self._registry.values())

    @overload
    def find(
        self, predicate=None, *, selectable: Literal[True]
    ) -> SelectableTextDraw | None: ...
    @overload
    def find(
        self, predicate=None, *, selectable: Literal[False] | None = None
    ) -> TextDraw | None: ...

    def find(self, predicate=None, *, selectable=None) -> TextDraw | None:
        """Return the first textdraw matching the predicate, or None."""
        return self._find_impl(predicate, selectable)

    @overload
    def find_all(
        self, predicate=None, *, selectable: Literal[True]
    ) -> list[SelectableTextDraw]: ...
    @overload
    def find_all(
        self, predicate=None, *, selectable: Literal[False] | None = None
    ) -> list[TextDraw]: ...

    def find_all(self, predicate=None, *, selectable=None) -> list[TextDraw]:
        """Return all textdraws matching the predicate."""
        results = []
        for td in self._registry.values():
            if selectable is True and not isinstance(td, SelectableTextDraw):
                continue
            if selectable is False and isinstance(td, SelectableTextDraw):
                continue
            if predicate is not None and not predicate(td):
                continue
            results.append(td)
        return results

    @overload
    async def wait_for(
        self, predicate=None, *, selectable: Literal[True]
    ) -> SelectableTextDraw: ...
    @overload
    async def wait_for(
        self, predicate=None, *, selectable: Literal[False] | None = None
    ) -> TextDraw: ...

    async def wait_for(self, predicate=None, *, selectable=None) -> TextDraw:
        """Return immediately if a match exists; wait until one appears otherwise."""
        async with self._condition:
            while True:
                match = self._find_impl(predicate, selectable)
                if match is not None:
                    return match
                await self._condition.wait()

    async def wait_until_gone(self, td: TextDraw) -> None:
        """Wait until the given textdraw is removed from the registry."""
        async with self._condition:
            while td.id in self._registry:
                await self._condition.wait()

    def _find_impl(self, predicate, selectable) -> TextDraw | None:
        for td in self._registry.values():
            if selectable is True and not isinstance(td, SelectableTextDraw):
                continue
            if selectable is False and isinstance(td, SelectableTextDraw):
                continue
            if predicate is not None and not predicate(td):
                continue
            return td
        return None
