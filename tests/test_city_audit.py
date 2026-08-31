"""Tests for tools/city_audit.py — map dump + R1 station pad integrity rule."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_SPEC = importlib.util.spec_from_file_location("city_audit", TOOLS_DIR / "city_audit.py")
city_audit = importlib.util.module_from_spec(_SPEC)
sys.modules["city_audit"] = city_audit  # dataclasses needs the module registered
_SPEC.loader.exec_module(city_audit)

from spacehack import world  # noqa: E402


def _make_entity(
    name: str,
    x: int,
    y: int,
    *,
    width: int = 1,
    height: int = 1,
    transit_station_id: str = "",
) -> world.Entity:
    return world.Entity(
        char="T" if transit_station_id else "o",
        fg=(255, 255, 255),
        pos=world.Position(x, y),
        name=name,
        width=width,
        height=height,
        transit_station_id=transit_station_id,
    )


def _make_bay_tile() -> world.Tile:
    """A proper transit_bay tile (walkable, correct kind)."""
    return world.Tile(
        kind="transit_bay", char="=", walkable=True,
        fg=(100, 220, 255), bg=(25, 55, 80),
    )


def _make_map(
    entities: list[world.Entity],
    *,
    bay_cells: set[tuple[int, int]] | None = None,
) -> world.GameMap:
    """Build a 20x20 test map. Cells listed in ``bay_cells`` become
    transit_bay tiles; everything else stays FLOOR."""
    tiles = [[world.FLOOR for _ in range(20)] for _ in range(20)]
    bay = _make_bay_tile()
    for x, y in (bay_cells or set()):
        tiles[y][x] = bay
    return world.GameMap(width=20, height=20, tiles=tiles, entities=entities)


# ----- R1: station pad integrity --------------------------------------


def test_r1_passes_when_pad_fully_painted_and_no_clipping():
    """Station on a fully painted 3x3 transit_bay pad, entities far away."""
    bay_cells = {(x, y) for x in range(4, 7) for y in range(4, 7)}
    game_map = _make_map([
        _make_entity("Transit: Spaceport", 5, 5, transit_station_id="spaceport"),
        _make_entity("Trade Terminal", 10, 10),
        _make_entity("NPC: Bartender", 15, 3),
    ], bay_cells=bay_cells)
    assert city_audit.check_station_clipping(game_map) == []


def test_r1_catches_missing_pad_station_cell_not_bay():
    """Station cell is 'floor' — bay painter skipped it, no pad exists."""
    game_map = _make_map([
        _make_entity("Transit: Central Hub", 5, 5, transit_station_id="hub"),
    ], bay_cells=set())  # no bay painted at all
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) >= 1
    # The station cell itself must be flagged
    assert any(v.other == "floor" and v.location == (5, 5) for v in violations)


def test_r1_catches_partial_pad_road_intrusion():
    """One cell of the pad zone is a road — painter skipped or road won."""
    bay_cells = {(x, y) for x in range(4, 7) for y in range(4, 7)}
    bay_cells.discard((4, 4))  # remove one corner
    game_map = _make_map([
        _make_entity("Transit: Spaceport", 5, 5, transit_station_id="spaceport"),
    ], bay_cells=bay_cells)
    # Put a road tile at the missing corner
    game_map.tiles[4][4] = world.ROAD_SURFACE
    violations = city_audit.check_station_clipping(game_map)
    assert any(v.other == "road" and v.location == (4, 4) for v in violations)


def test_r1_catches_station_on_terminal():
    game_map = _make_map([
        _make_entity("Transit: Spaceport", 5, 5, transit_station_id="spaceport"),
        _make_entity("Trade Terminal", 5, 5),
    ], bay_cells={(x, y) for x in range(4, 7) for y in range(4, 7)})
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "R1"
    assert v.station == "Transit: Spaceport"
    assert v.other == "Trade Terminal"
    assert v.location == (5, 5)


def test_r1_catches_station_clipped_by_multicell_ship_pad():
    """A 3x2 showroom ship overlapping the station's pad zone must be caught."""
    bay_cells = {(x, y) for x in range(7, 10) for y in range(3, 6)}
    game_map = _make_map([
        _make_entity("Transit: Dock", 8, 4, transit_station_id="dock"),
        _make_entity("Ship: Sparrow", 9, 3, width=3, height=2),
    ], bay_cells=bay_cells)
    violations = city_audit.check_station_clipping(game_map)
    assert any(v.other == "Ship: Sparrow" for v in violations)


def test_r1_catches_station_pad_clipping_adjacent_entity():
    """Multi-cell station footprint clips an entity beside its anchor."""
    bay_cells = {(x, y) for x in range(4, 8) for y in range(4, 8)}
    game_map = _make_map([
        _make_entity("Transit: Hub", 5, 5, width=2, height=2, transit_station_id="hub"),
        _make_entity("Mechanic Terminal", 6, 6),
    ], bay_cells=bay_cells)
    violations = city_audit.check_station_clipping(game_map)
    assert any(
        v.station == "Transit: Hub" and v.other == "Mechanic Terminal"
        for v in violations
    )


def test_r1_multiple_stations_multiple_violations():
    bay_a = {(x, y) for x in range(0, 3) for y in range(0, 3)}
    bay_b = {(x, y) for x in range(2, 5) for y in range(2, 5)}
    game_map = _make_map([
        _make_entity("Transit: A", 1, 1, transit_station_id="a"),
        _make_entity("Transit: B", 3, 3, transit_station_id="b"),
        _make_entity("Terminal", 1, 1),
        _make_entity("NPC", 3, 3),
    ], bay_cells=bay_a | bay_b)
    violations = city_audit.check_station_clipping(game_map)
    station_violations = {v.station for v in violations if v.other.startswith(("Terminal", "NPC"))}
    assert {"Transit: A", "Transit: B"} <= station_violations


def test_r1_stations_do_not_flag_each_other():
    """Two stations side by side (not overlapping, separate pads) pass."""
    bay_a = {(x, y) for x in range(1, 4) for y in range(1, 4)}
    bay_b = {(x, y) for x in range(1, 4) for y in range(5, 8)}
    game_map = _make_map([
        _make_entity("Transit: A", 2, 2, transit_station_id="a"),
        _make_entity("Transit: B", 2, 6, transit_station_id="b"),
    ], bay_cells=bay_a | bay_b)
    assert city_audit.check_station_clipping(game_map) == []


def test_r1_pad_zone_catches_entity_beside_station():
    """Entity standing inside the station's 3x3 pad zone (but not on the
    station cell itself) is a violation — the pad would paint over it."""
    bay_cells = {(x, y) for x in range(4, 7) for y in range(4, 7)}
    game_map = _make_map([
        _make_entity("Transit: Bar", 5, 5, transit_station_id="bar"),
        _make_entity("Civilian Bystander", 4, 4),
    ], bay_cells=bay_cells)
    violations = city_audit.check_station_clipping(game_map)
    assert any(
        v.station == "Transit: Bar" and v.other == "Civilian Bystander"
        and v.location == (4, 4)
        for v in violations
    )


def test_r1_entity_just_outside_pad_zone_is_ok():
    """Entity two cells away is outside the default 3x3 pad zone."""
    bay_cells = {(x, y) for x in range(4, 7) for y in range(4, 7)}
    game_map = _make_map([
        _make_entity("Transit: Bar", 5, 5, transit_station_id="bar"),
        _make_entity("Civilian Bystander", 8, 5),
    ], bay_cells=bay_cells)
    assert city_audit.check_station_clipping(game_map) == []


def test_r1_pad_zone_respects_map_bounds():
    """Station near the map edge: pad zone is clipped to the map, no crash."""
    bay_cells = {(x, y) for x in range(0, 2) for y in range(0, 2)}
    game_map = _make_map([
        _make_entity("Transit: Edge", 0, 0, transit_station_id="edge"),
        _make_entity("Terminal", 0, 0),
    ], bay_cells=bay_cells)
    violations = city_audit.check_station_clipping(game_map)
    assert any(v.location == (0, 0) and v.other == "Terminal" for v in violations)


# ----- Step 1: map dump ------------------------------------------------


def test_dump_map_shape():
    bay_cells = {(x, y) for x in range(3, 6) for y in range(5, 8)}
    game_map = _make_map([
        _make_entity("Transit: Spaceport", 4, 6, transit_station_id="spaceport"),
        _make_entity("Trade Terminal", 9, 9),
    ], bay_cells=bay_cells)
    payload = city_audit.dump_map(game_map, "testplanet")
    assert payload["city_id"] == "testplanet"
    assert payload["width"] == 20
    assert payload["height"] == 20
    assert len(payload["tiles"]) == 20
    assert payload["tiles"][6][4] == "transit_bay"  # bay painted
    assert len(payload["entities"]) == 2
    station = next(e for e in payload["entities"] if e.get("transit_station_id"))
    assert station["pos"] == [4, 6]
    assert station["width"] == 1
    assert station["height"] == 1


# ----- Earth end-to-end ------------------------------------------------


def test_earth_builds_and_dumps():
    """Earth must build through the real pipeline and dump without errors."""
    game_map = city_audit.build_final_map("earth")
    assert game_map.width > 0 and game_map.height > 0
    assert game_map.entities, "earth city must have entities"
    payload = city_audit.dump_map(game_map, "earth")
    assert payload["city_id"] == "earth"
    assert len(payload["tiles"]) == game_map.height
    names = [e["name"] for e in payload["entities"]]
    assert any("Transit:" in n for n in names), "earth must have transit stations"


def test_earth_r1_report_runs():
    """The full report path runs on the real Earth map."""
    game_map = city_audit.build_final_map("earth")
    violations = city_audit.check_station_clipping(game_map)
    text = city_audit.report_text("earth", game_map, violations)
    assert "earth" in text
    assert "PASS" in text or "FAIL" in text
    json_text = city_audit.report_json("earth", game_map, violations)
    assert '"passed"' in json_text


def test_earth_r1_finds_violations():
    """On the real Earth map, no transit_bay tiles exist at all (the bay
    painter was never called in earth_city.py), so every station must
    produce a 'pad is not transit_bay' violation."""
    game_map = city_audit.build_final_map("earth")
    violations = city_audit.check_station_clipping(game_map)
    assert violations, "earth must report missing transit_bay pads"
    stations_flagged = {v.station for v in violations}
    assert "Transit: Central Hub" in stations_flagged
    # Every station must be flagged for missing bay
    all_stations = {
        e.name for e in game_map.entities if e.transit_station_id
    }
    assert all_stations <= stations_flagged, (
        f"all stations should be flagged; missing: {all_stations - stations_flagged}"
    )
