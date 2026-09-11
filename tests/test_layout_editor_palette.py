"""Palette authoring tests for the layout editor."""

from __future__ import annotations

from pathlib import Path

from tools.layout_editor.model import load_document
from tools.layout_editor.palette import build_palette
from tools.layout_editor.validation import validate_document

_DATA = Path(__file__).resolve().parent.parent / "src" / "spacehack" / "data"


def _write_layout(landmarks, name, author_berth: bool):
    layout = landmarks / name
    lines = [
        "MAP",
        "######",
        "#..S.#" if author_berth else "#....#",
        "#.P>.#",
        "######",
        "ENDMAP",
        "",
        "TILE: # = CITY_BUILDING_WALL",
        "TILE: . = INTERIOR",
        "TILE: > = EXIT",
    ]
    if author_berth:
        lines.append("TILE: S = SHOWROOM_BERTH")
    layout.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return layout


def test_blank_render_tiles_author_via_directive_but_arent_palette_offered(tmp_path):
    # SHOWROOM_BERTH renders blank (entity underlays stay clean), and
    # the palette keys fresh tile offers by render glyph — so a blank
    # render tile cannot be offered, but the TILE-directive grammar
    # keeps authoring it (existing spaceport interiors do), and an
    # authored directive still lists in the palette.
    from src.spacehack import layout_format

    assert layout_format.tile_for_name("SHOWROOM_BERTH").char == " "

    landmarks = tmp_path / "landmarks"
    landmarks.mkdir(exist_ok=True)

    authored = load_document(_write_layout(landmarks, "with_berth.layout", True))
    assert not [i for i in validate_document(authored) if i.severity == "error"]
    assert any(
        entry.tile_name == "SHOWROOM_BERTH" for entry in build_palette(authored)
    )

    bare = load_document(_write_layout(landmarks, "without_berth.layout", False))
    assert not [i for i in validate_document(bare) if i.severity == "error"]
    assert not any(
        entry.tile_name == "SHOWROOM_BERTH" for entry in build_palette(bare)
    )
