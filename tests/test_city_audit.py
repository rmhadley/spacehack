"""Tests for tools/city_audit.py — map dump + R1 station clipping rule."""

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


def _make_map(entities: list[world.Entity]) -> world.GameMap:
    return world.GameMap(
        width=20, height=20,
        tiles=[[world.FLOOR for _ in range(20)] for _ in range(20)],
        entities=entities,
    )


# ----- R1: station clipping -------------------------------------------


def test_r1_passes_when_no_clipping():
    game_map = _make_map([
        _make_entity("Transit: Spaceport", 5, 5, transit_station_id="spaceport"),
        _make_entity("Trade Terminal", 10, 10),
        _make_entity("NPC: Bartender", 15, 3),
    ])
    assert city_audit.check_station_clipping(game_map) == []


def test_r1_catches_station_on_terminal():
    game_map = _make_map([
        _make_entity("Transit: Spaceport", 5, 5, transit_station_id="spaceport"),
        _make_entity("Trade Terminal", 5, 5),
    ])
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "R1"
    assert v.station == "Transit: Spaceport"
    assert v.other == "Trade Terminal"
    assert v.location == (5, 5)


def test_r1_catches_station_clipped_by_multicell_ship_pad():
    """A 3x2 showroom ship overlapping the station's cell must be caught."""
    game_map = _make_map([
        _make_entity("Transit: Dock", 8, 4, transit_station_id="dock"),
        _make_entity("Ship: Sparrow", 6, 4, width=3, height=2),
    ])
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 1
    assert violations[0].other == "Ship: Sparrow"


def test_r1_catches_station_pad_clipping_adjacent_entity():
    """Multi-cell station footprint clips an entity beside its anchor."""
    game_map = _make_map([
        _make_entity("Transit: Hub", 5, 5, width=2, height=2, transit_station_id="hub"),
        _make_entity("Mechanic Terminal", 6, 6),
    ])
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 1
    assert violations[0].station == "Transit: Hub"
    assert violations[0].other == "Mechanic Terminal"


def test_r1_multiple_stations_multiple_violations():
    game_map = _make_map([
        _make_entity("Transit: A", 1, 1, transit_station_id="a"),
        _make_entity("Transit: B", 3, 3, transit_station_id="b"),
        _make_entity("Terminal", 1, 1),
        _make_entity("NPC", 3, 3),
    ])
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 2
    assert {v.station for v in violations} == {"Transit: A", "Transit: B"}


def test_r1_stations_do_not_flag_each_other():
    """Two stations side by side (not overlapping) produce no violations."""
    game_map = _make_map([
        _make_entity("Transit: A", 2, 2, transit_station_id="a"),
        _make_entity("Transit: B", 2, 4, transit_station_id="b"),
    ])
    assert city_audit.check_station_clipping(game_map) == []


def test_r1_pad_zone_catches_entity_beside_station():
    """Entity standing inside the station's 3x3 pad zone (but not on the
    station cell itself) is a violation — the pad would paint over it."""
    game_map = _make_map([
        _make_entity("Transit: Bar", 5, 5, transit_station_id="bar"),
        _make_entity("Civilian Bystander", 4, 4),
    ])
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 1
    assert violations[0].station == "Transit: Bar"
    assert violations[0].other == "Civilian Bystander"
    assert violations[0].location == (4, 4)


def test_r1_entity_just_outside_pad_zone_is_ok():
    """Entity two cells away is outside the default 3x3 pad zone."""
    game_map = _make_map([
        _make_entity("Transit: Bar", 5, 5, transit_station_id="bar"),
        _make_entity("Civilian Bystander", 7, 5),
    ])
    assert city_audit.check_station_clipping(game_map) == []


def test_r1_pad_zone_clipped_by_multicell_ship():
    """Multi-cell ship whose footprint overlaps the pad zone is caught."""
    game_map = _make_map([
        _make_entity("Transit: Dock", 8, 4, transit_station_id="dock"),
        _make_entity("Ship: Hauler", 9, 3, width=3, height=2),
    ])
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 1
    assert violations[0].other == "Ship: Hauler"


def test_r1_pad_zone_respects_map_bounds():
    """Station near the map edge: pad zone is clipped to the map, no crash."""
    game_map = _make_map([
        _make_entity("Transit: Edge", 0, 0, transit_station_id="edge"),
        _make_entity("Terminal", 0, 0),
    ])
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 1
    assert violations[0].location == (0, 0)


# ----- Step 1: map dump ------------------------------------------------


def test_dump_map_shape():
    game_map = _make_map([
        _make_entity("Transit: Spaceport", 4, 6, transit_station_id="spaceport"),
        _make_entity("Trade Terminal", 9, 9),
    ])
    payload = city_audit.dump_map(game_map, "testplanet")
    assert payload["city_id"] == "testplanet"
    assert payload["width"] == 20
    assert payload["height"] == 20
    assert len(payload["tiles"]) == 20
    assert all(row[0] == "floor" for row in payload["tiles"])
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


def test_earth_r1_finds_pad_zone_clipping():
    """On the real Earth map, station pad zones clip bystander/trooper NPCs
    standing inside the 3x3 bay area (known baseline violations)."""
    game_map = city_audit.build_final_map("earth")
    violations = city_audit.check_station_clipping(game_map)
    assert violations, "earth baseline must report pad-zone clipping"
    pairs = {(v.station, v.other) for v in violations}
    assert ("Transit: Bar District", "Civilian Bystander") in pairs
    assert ("Transit: Militia Center", "Militia Trooper") in pairs
