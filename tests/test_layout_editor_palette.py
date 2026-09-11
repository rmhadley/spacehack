"""Palette authoring tests for the layout editor."""

from __future__ import annotations

from pathlib import Path

from tools.layout_editor.model import load_document
from tools.layout_editor.palette import build_palette

_DATA = Path(__file__).resolve().parent.parent / "src" / "spacehack" / "data"


def test_showroom_berth_tile_is_authorable_from_the_palette(tmp_path):
    # "S" left the reserved-marker set with the berth grammar (doc 45):
    # a city document must offer SHOWROOM_BERTH as a tile directive.
    # infer_mode keys on the parent directory name; city documents
    # must live under "landmarks" to be CITY assets.
    landmarks = tmp_path / "landmarks"
    landmarks.mkdir(exist_ok=True)
    layout = landmarks / "spaceport_interior.layout"
    layout.write_text(
        "MAP\n"
        "######\n"
        "#..S.#\n"
        "#.P>.#\n"
        "######\n"
        "ENDMAP\n"
        "\n"
        "TILE: # = CITY_BUILDING_WALL\n"
        "TILE: . = CITY_BUILDING_FLOOR\n"
        "TILE: S = SHOWROOM_BERTH\n",
        encoding="utf-8",
    )

    entries = build_palette(load_document(layout))

    assert any(
        entry.tile_name == "SHOWROOM_BERTH" and entry.glyph == "S"
        for entry in entries
    )
