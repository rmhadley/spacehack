"""Tests for the project-owned Phase 2 cell framebuffer."""

from __future__ import annotations

import pytest

from src.spacehack.framebuffer import FrameBuffer, FrameCell
from src.spacehack.world import WorldDrawCommand


def test_empty_frame_omits_default_cells():
    frame = FrameBuffer(3, 2)

    assert frame.commands == []
    assert frame.cell(1, 1) == FrameCell()


def test_print_writes_cells_with_colors_and_backgrounds():
    frame = FrameBuffer(4, 1)

    frame.print(x=1, y=0, string="AB", fg=(1, 2, 3), bg=(4, 5, 6))

    assert frame.commands == [
        WorldDrawCommand(1, 0, "A", (1, 2, 3), (4, 5, 6)),
        WorldDrawCommand(2, 0, "B", (1, 2, 3), (4, 5, 6)),
    ]


def test_print_handles_newlines_and_clips_all_edges():
    frame = FrameBuffer(3, 2)

    frame.print(x=-1, y=-1, string="ab\ncd\nef")

    assert frame.commands == [
        WorldDrawCommand(0, 0, "d", (255, 255, 255), None),
        WorldDrawCommand(0, 1, "f", (255, 255, 255), None),
    ]


def test_explicit_default_cell_write_is_preserved_as_a_command():
    frame = FrameBuffer(1, 1)

    frame.print(string=" ")

    assert frame.commands == [WorldDrawCommand(0, 0, " ", (255, 255, 255), None)]


def test_later_writes_overwrite_earlier_cells_in_place():
    frame = FrameBuffer(2, 1)
    frame.print(string="AB", fg=(1, 1, 1))
    frame.print(x=1, string=" ", fg=(2, 2, 2), bg=(3, 3, 3))

    assert frame.cell(1, 0) == FrameCell(" ", (2, 2, 2), (3, 3, 3))
    assert frame.commands[-1] == WorldDrawCommand(
        1, 0, " ", (2, 2, 2), (3, 3, 3),
    )


def test_later_glyph_without_background_inherits_the_existing_tile_background():
    frame = FrameBuffer(1, 1)
    frame.write_cell(0, 0, ".", fg=(200, 210, 220), bg=(10, 20, 30))
    frame.write_cell(0, 0, "@", fg=(255, 255, 255))

    assert frame.cell(0, 0) == FrameCell("@", (255, 255, 255), (10, 20, 30))


def test_later_glyph_inherits_the_visible_underlay_of_dense_tile_glyphs():
    frame = FrameBuffer(1, 1)
    frame.write_cell(0, 0, "▓", fg=(220, 240, 255), bg=(50, 70, 95))
    frame.write_cell(0, 0, "t", fg=(180, 200, 220))

    assert frame.cell(0, 0).bg == (178, 198, 215)


def test_clear_resets_cells_and_changes_default_background():
    frame = FrameBuffer(2, 1, background=(9, 9, 9))
    frame.print(string="A")

    frame.clear(bg=(7, 8, 9))

    assert frame.commands == []
    assert frame.default_cell == FrameCell(bg=(7, 8, 9))
    assert frame.default_background() == (7, 8, 9)
    assert frame.cell(0, 0) == FrameCell(bg=(7, 8, 9))


def test_to_commands_preserves_overwrite_order_as_a_tuple():
    frame = FrameBuffer(2, 1)
    frame.print(string="AB", fg=(1, 2, 3))

    assert frame.to_commands() == tuple(frame.commands)


@pytest.mark.parametrize("width,height", [(0, 0), (0, 2), (2, 0)])
def test_zero_sized_frames_are_valid(width: int, height: int):
    frame = FrameBuffer(width, height)

    frame.print(string="ignored")

    assert frame.commands == []


def test_negative_dimensions_are_rejected():
    with pytest.raises(ValueError):
        FrameBuffer(-1, 2)
    with pytest.raises(ValueError):
        FrameBuffer(2, -1)
