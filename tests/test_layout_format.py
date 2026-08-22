"""Tests for the shared authored-layout source parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.spacehack import layout_format, world


_DATA = Path(__file__).resolve().parent.parent / "src" / "spacehack" / "data"


def test_parse_ship_layout_preserves_map_and_directive_semantics():
    parsed = layout_format.parse_layout_file(_DATA / "layouts" / "scout_a.layout")

    assert parsed.width == 73
    assert parsed.height == 26
    assert parsed.map_lines[0].startswith("           ")
    assert parsed.tile_map["#"] is world.DUNGEON_WALL
    assert parsed.tile_map["d"] is world.DUNGEON_DOOR
    assert parsed.loot_zones == {
        "1": "engine_room",
        "2": "mess_hall",
        "3": "personal_storage",
        "4": "cargo_bay",
    }
    assert parsed.enemy_spawn_specs["R"] == ("pirate_rifleman", 1.0, 2, 4)
    assert parsed.enemy_spawn_specs["m"] == ("hull_parasite", 0.15, 2, 4)
    assert parsed.colour_overrides["#"].fg == (120, 130, 150)


def test_parse_landmark_layout_supports_equals_glyph_and_backgrounds():
    parsed = layout_format.parse_layout_file(
        _DATA / "landmarks" / "mars_signal_door.layout",
    )

    assert parsed.tile_map["="] is world.UNDULATING_DOOR_A
    assert parsed.tile_map["~"] is world.UNDULATING_DOOR_B
    assert parsed.colour_overrides["="] == layout_format.ColourOverride(
        fg=(46, 219, 211),
        bg=(24, 72, 96),
    )
    assert parsed.colour_overrides["C"].bg == (48, 52, 92)


def test_parse_layout_pads_rows_without_changing_authored_cells():
    parsed = layout_format.parse_layout(
        ["MAP", "  ##", "#.#", "ENDMAP", "TILE: # = DUNGEON_WALL", "TILE: . = DUNGEON_FLOOR"],
        "padded",
    )

    assert parsed.width == 4
    assert parsed.map_lines == ("  ##", "#.# ")
    assert parsed.height == 2


def test_parse_layout_rejects_unknown_tile_name():
    with pytest.raises(ValueError, match="Unknown tile name 'NOT_A_TILE'"):
        layout_format.parse_layout(
            ["MAP", "P", "ENDMAP", "TILE: P = NOT_A_TILE"],
            "broken",
        )


def test_parse_layout_rejects_missing_map():
    with pytest.raises(ValueError, match="has no MAP section"):
        layout_format.parse_layout(["# comment", "TILE: . = DUNGEON_FLOOR"], "empty")
