"""Project-owned cell framebuffer for renderer-neutral game presentation.

The framebuffer deliberately exposes the small ``clear``/``print`` surface
used by the existing renderers while keeping storage and output independent
of any third-party console library.  Renderers write cells; presentation
adapters consume :class:`spacehack.world.WorldDrawCommand` values.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .world import WorldDrawCommand


Color = tuple[int, int, int]
DEFAULT_FOREGROUND: Color = (255, 255, 255)
DEFAULT_BACKGROUND: Color | None = None

_SHADE_COVERAGE: dict[str, float] = {
    "█": 1.0,
    "▓": 0.75,
    "▒": 0.5,
    "░": 0.25,
}


def _underlay_background(cell: "FrameCell") -> Color | None:
    """Return the color visibly occupying a cell beneath a later glyph."""
    if cell.bg is None:
        return None
    coverage = _SHADE_COVERAGE.get(cell.char, 0.0)
    if coverage <= 0:
        return cell.bg
    return tuple(
        round(cell.bg[index] * (1 - coverage) + cell.fg[index] * coverage)
        for index in range(3)
    )


@dataclass(frozen=True)
class FrameCell:
    """One framebuffer cell, including its optional background color."""

    char: str = " "
    fg: Color = DEFAULT_FOREGROUND
    bg: Color | None = DEFAULT_BACKGROUND


class FrameBuffer:
    """A mutable, clipped, row-major logical cell frame.

    Contract:

    * ``clear`` replaces every cell with a blank, white-foreground cell and
      the supplied background (``None`` by default).
    * ``print`` writes characters left-to-right from ``(x, y)``. Newlines
      return to the original x column and advance one row. Writes outside the
      frame are clipped without raising.
    * Later writes overwrite earlier writes one cell at a time. A blank
      character is still a real write. A write with no explicit background
      inherits the visible underlay of the existing cell, allowing entity
      glyphs to sit on the terrain beneath them instead of its raw dark
      texture background.
    * ``commands`` returns one command per non-default cell, plus explicit
      writes that happen to equal the default, in row-major order.
      Completely untouched cells are omitted because the Pygame presentation
      surface is cleared before commands are drawn.
    """

    def __init__(
        self,
        width: int,
        height: int,
        *,
        background: Color | None = DEFAULT_BACKGROUND,
    ) -> None:
        if width < 0 or height < 0:
            raise ValueError("framebuffer dimensions must be non-negative")
        self.width = width
        self.height = height
        self._default = FrameCell(bg=background)
        self._cells: list[list[FrameCell]] = [
            [self._default for _ in range(width)] for _ in range(height)
        ]
        self._written: set[tuple[int, int]] = set()

    @property
    def default_cell(self) -> FrameCell:
        """Return the cell used by ``clear`` and untouched positions."""
        return self._default

    def clear(self, *, bg: Color | None = DEFAULT_BACKGROUND) -> None:
        """Reset the entire frame to blank cells with ``bg``."""
        self._default = FrameCell(bg=bg)
        self._cells = [
            [self._default for _ in range(self.width)]
            for _ in range(self.height)
        ]
        self._written.clear()

    def cell(self, x: int, y: int) -> FrameCell:
        """Return one cell, raising ``IndexError`` when outside the frame."""
        return self._cells[y][x]

    def _write_background(
        self, x: int, y: int, bg: Color | None, char: str,
    ) -> Color | None:
        """Resolve an omitted background against the visible cell underlay."""
        if bg is not None or not (0 <= x < self.width and 0 <= y < self.height):
            return bg
        underlay = self._cells[y][x]
        if char == "@":
            return underlay.bg
        return _underlay_background(underlay)

    def _write_cell(self, x: int, y: int, cell: FrameCell) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._cells[y][x] = cell
            self._written.add((x, y))

    def print(
        self,
        *,
        x: int = 0,
        y: int = 0,
        string: str = "",
        fg: Color = DEFAULT_FOREGROUND,
        bg: Color | None = DEFAULT_BACKGROUND,
        **_kwargs: object,
    ) -> None:
        """Write clipped text using the legacy renderer call shape."""
        cell_x, cell_y = x, y
        for character in str(string):
            if character == "\n":
                cell_x = x
                cell_y += 1
                continue
            self._write_cell(
                cell_x,
                cell_y,
                FrameCell(
                    char=character,
                    fg=tuple(fg),
                    bg=self._write_background(cell_x, cell_y, bg, character),
                ),
            )
            cell_x += 1

    def iter_cells(self) -> Iterable[tuple[int, int, FrameCell]]:
        """Yield all cells in row-major order, including untouched cells."""
        for y, row in enumerate(self._cells):
            for x, cell in enumerate(row):
                yield x, y, cell

    def write_cell(
        self,
        x: int,
        y: int,
        char: str,
        *,
        fg: Color = DEFAULT_FOREGROUND,
        bg: Color | None = DEFAULT_BACKGROUND,
    ) -> None:
        """Write one already-positioned cell with normal clipping."""
        self._write_cell(
            x,
            y,
            FrameCell(
                char=char,
                fg=tuple(fg),
                bg=self._write_background(x, y, bg, char),
            ),
        )

    @property
    def commands(self) -> list["WorldDrawCommand"]:
        """Return non-default cells as renderer-neutral draw commands."""
        from .world import WorldDrawCommand

        return [
            WorldDrawCommand(x, y, cell.char, cell.fg, cell.bg)
            for x, y, cell in self.iter_cells()
            if cell != self._default or (x, y) in self._written
        ]

    def to_commands(self) -> tuple["WorldDrawCommand", ...]:
        """Return the current frame as renderer-neutral draw commands."""
        return tuple(self.commands)

    def default_background(self) -> Color | None:
        """Return the surface color needed before drawing this frame."""
        return self.default_cell.bg
