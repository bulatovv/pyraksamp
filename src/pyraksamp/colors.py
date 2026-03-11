"""SA:MP color representation and parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


_COLOR_RE = re.compile(r"\{([0-9A-Fa-f]{6})\}")


@dataclass(slots=True, frozen=True)
class Color:
    """A 24-bit RGB color (RRGGBB)."""

    value: int  # 0xRRGGBB

    @classmethod
    def from_hex(cls, hex_str: str) -> Color:
        """Create a Color from a hex string (e.g. "FF0000")."""
        return cls(int(hex_str, 16))

    def __repr__(self) -> str:
        return f"Color(#{self.value:06X})"

    def to_hex(self) -> str:
        """Return the hex representation without '#'."""
        return f"{self.value:06X}"

    def to_rgb(self) -> tuple[int, int, int]:
        """Return (R, G, B) tuple."""
        return (
            (self.value >> 16) & 0xFF,
            (self.value >> 8) & 0xFF,
            self.value & 0xFF,
        )

    def to_int(self) -> int:
        """Return the raw integer value."""
        return self.value


class ColoredString(str):
    """A string that may contain embedded SA:MP color codes {RRGGBB}."""

    @cached_property
    def _components(self) -> tuple[str | Color, ...]:
        """Split text by {RRGGBB} color codes into a tuple of parts."""
        return parse_embedded_colors(self)

    @cached_property
    def stripped(self) -> str:
        """Return the string with all {RRGGBB} color codes removed."""
        return _COLOR_RE.sub("", self)


def parse_embedded_colors(text: str) -> tuple[str | Color, ...]:
    """Split a string by {RRGGBB} color codes into a tuple of parts."""
    if not text:
        return ()

    components: list[str | Color] = []
    last_end = 0

    for match in _COLOR_RE.finditer(text):
        start, end = match.span()
        if start > last_end:
            components.append(text[last_end:start])
        components.append(Color.from_hex(match.group(1)))
        last_end = end

    if last_end < len(text):
        components.append(text[last_end:])

    return tuple(components)
