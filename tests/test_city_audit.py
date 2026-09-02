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


# ----- R0: serves declared (fail-fast gate) ---------------------------


def test_r0_flags_station_without_serves():
    game_map = _make_map([
        _make_entity("Transit: Hub", 5, 5, transit_station_id="hub"),
    ], bay_cells=set())
    violations = city_audit.check_serves_declared(game_map)
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "R0"
    assert v.station == "Transit: Hub"
    assert "does not declare 'serves'" in v.message


def test_r0_passes_when_serves_declared_on_entity():
    station = _make_entity("Transit: Bar", 5, 5, transit_station_id="bar")
    station.serves = "bar"
    game_map = _make_map([station], bay_cells=set())
    assert city_audit.check_serves_declared(game_map) == []


def test_r0_passes_when_serves_in_city_transit_lookup():
    game_map = _make_map([
        _make_entity("Transit: Bar", 5, 5, transit_station_id="bar"),
    ], bay_cells=set())
    game_map.city_transit = {"bar": {"serves": "bar"}}
    assert city_audit.check_serves_declared(game_map) == []


def test_r0_flags_each_station_without_serves():
    game_map = _make_map([
        _make_entity("Transit: A", 2, 2, transit_station_id="a"),
        _make_entity("Transit: B", 8, 8, transit_station_id="b"),
    ], bay_cells=set())
    violations = city_audit.check_serves_declared(game_map)
    assert {v.station for v in violations} == {"Transit: A", "Transit: B"}


def test_r0_ignores_non_station_entities():
    game_map = _make_map([
        _make_entity("Trade Terminal", 5, 5),
    ], bay_cells=set())
    assert city_audit.check_serves_declared(game_map) == []


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


def test_dump_map_includes_building_entrances():
    """Building records (label + entrance/door cell) are part of the dump
    substrate so rules can check a station sits near the building it serves."""
    game_map = _make_map([
        _make_entity("Transit: Bar", 4, 6, transit_station_id="bar"),
    ], bay_cells={(x, y) for x in range(3, 6) for y in range(5, 8)})
    game_map.city_buildings = {
        "bar": {
            "label": "bar",
            "display_name": "bar",
            "npc_id": "bartender",
            "npc_override": None,
            "interior_layout_id": "bar_interior",
            "entrance": (12, 8),
        },
    }
    payload = city_audit.dump_map(game_map, "testplanet")
    assert payload["buildings"]["bar"] == {
        "display_name": "bar",
        "entrance": [12, 8],
    }


def test_dump_map_without_buildings_metadata_yields_empty():
    """A map with no city_buildings metadata dumps an empty buildings map
    (getattr default) — the field is always present, never missing."""
    game_map = _make_map([], bay_cells=set())
    payload = city_audit.dump_map(game_map, "testplanet")
    assert payload["buildings"] == {}


# ----- R0 fix-plan refusal payload --------------------------------------


def _r0_map_with_target():
    """A station missing serves + one nearby building to suggest."""
    game_map = _make_map([
        _make_entity("Transit: Hub", 5, 5, transit_station_id="hub"),
    ], bay_cells=set())
    game_map.city_buildings = {
        "bar": {"label": "bar", "display_name": "bar", "entrance": (6, 6)},
    }
    return game_map


def test_r0_refusal_includes_per_station_serves_edit():
    r0 = city_audit.check_serves_declared(_r0_map_with_target())
    payload = city_audit.r0_refusal_payload("testplanet", r0)
    stations = payload["how_to_fix"]["stations_missing_serves"]
    assert stations == [{
        "station": "Transit: Hub",
        "station_pos": [5, 5],
        "serves": "bar",
        "edit": 'serves="bar"',
    }]


def test_r0_refusal_flags_duplicate_suggestions():
    game_map = _make_map([
        _make_entity("Transit: A", 5, 5, transit_station_id="a"),
        _make_entity("Transit: B", 7, 7, transit_station_id="b"),
    ], bay_cells=set())
    game_map.city_buildings = {
        "bar": {"label": "bar", "display_name": "bar", "entrance": (6, 6)},
    }
    r0 = city_audit.check_serves_declared(game_map)
    payload = city_audit.r0_refusal_payload("testplanet", r0)
    assert payload["duplicate_serves_suggestions"] == ["bar"]
    assert "redundant stop" in payload["decision_required"]
    assert "Delete one TransitStation" in payload["decision_required"]


def test_r0_refusal_names_exact_spec_file_and_pinned_tests():
    payload = city_audit.r0_refusal_payload(
        "earth", [city_audit.Violation(
            "R0", "Transit: Hub", "(no serves field)", (0, 0), "x",
        )],
    )
    assert payload["how_to_fix"]["file"] == "src/spacehack/data/planets/earth.py"
    files = {hit["file"] for hit in payload["tests_referencing_city"]}
    assert "tests/test_city_builder.py" in files


# ----- R1 check 4: stations never share a pad --------------------------


def test_r1_flags_two_stations_sharing_a_pad():
    """Two stations stacked on one painted pad pass checks 1-3 — check 4
    must catch the stack (regression: a verified Mars fix-plan once moved
    two stations onto the same cell)."""
    bay = {(x, y) for x in range(4, 7) for y in range(4, 7)}
    game_map = _make_map([
        _make_entity("Transit: Civic Square", 5, 5, transit_station_id="hub"),
        _make_entity("Transit: Civic Services", 5, 5, transit_station_id="bounties"),
    ], bay_cells=bay)
    violations = city_audit.check_station_clipping(game_map)
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "R1"
    assert v.station == "Transit: Civic Square"
    assert v.other == "Transit: Civic Services"
    assert "share a pad" in v.message


def test_r1_recommendation_moves_stacked_station_clear():
    """The stacked pair's violation carries a move recommendation whose
    pad does not touch the other station's pad."""
    bay = {(x, y) for x in range(4, 7) for y in range(4, 7)}
    game_map = _make_map([
        _make_entity("Transit: Civic Square", 5, 5, transit_station_id="hub"),
        _make_entity("Transit: Civic Services", 5, 5, transit_station_id="bounties"),
    ], bay_cells=bay)
    violations = city_audit.check_station_clipping(game_map)
    rec = violations[0].recommendation
    assert rec is not None
    rx, ry = rec["pos"]
    new_zone = {
        (rx + dx, ry + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
    }
    assert new_zone.isdisjoint(bay)


# ----- R2: duplicate serves targets -------------------------------------


def test_r2_flags_duplicate_serves_targets():
    """Two stations declaring the same serves target are a redundant
    stop — an explicit delete-or-re-target decision, not a move."""
    a = _make_entity("Transit: Hub", 5, 5, transit_station_id="hub")
    a.serves = "bar"
    b = _make_entity("Transit: Services", 8, 8, transit_station_id="svc")
    b.serves = "bar"
    game_map = _make_map([a, b], bay_cells=set())
    game_map.city_buildings = {
        "bar": {"label": "bar", "display_name": "bar", "entrance": (5, 6)},
    }
    violations = city_audit.check_serves(game_map)
    assert len(violations) == 1
    v = violations[0]
    assert v.rule_id == "R2"
    assert "all serve 'bar'" in v.message
    assert "delete" in v.remediation.lower()


def test_r2_allows_distinct_targets():
    a = _make_entity("Transit: Hub", 5, 5, transit_station_id="hub")
    a.serves = "bar"
    b = _make_entity("Transit: Services", 8, 8, transit_station_id="svc")
    b.serves = "guild"
    game_map = _make_map([a, b], bay_cells=set())
    game_map.city_buildings = {
        "bar": {"label": "bar", "display_name": "bar", "entrance": (5, 6)},
        "guild": {"label": "guild", "display_name": "guild", "entrance": (8, 9)},
    }
    assert city_audit.check_serves(game_map) == []


# ----- Fix plan: pad reservation ----------------------------------------


def test_fix_plan_moves_station_off_clean_station_pad():
    """Phase A must never land a moved station on a staying station's
    pad, and the patched map must verify."""
    bay = {(x, y) for x in range(1, 4) for y in range(1, 4)}
    game_map = _make_map([
        _make_entity("Transit: A", 2, 2, transit_station_id="a"),
        _make_entity("Transit: B", 10, 10, transit_station_id="b"),
    ], bay_cells=bay)
    game_map.city_transit = {"a": {"serves": "bar"}, "b": {"serves": "guild"}}
    game_map.city_buildings = {
        "bar": {"label": "bar", "display_name": "bar", "entrance": (2, 4)},
        "guild": {"label": "guild", "display_name": "guild", "entrance": (4, 2)},
    }
    plan = city_audit.build_fix_plan(game_map)
    assert plan is not None and plan["verified"], plan
    move = next(
        op for op in plan["ops"]
        if op["op"] == "move_station" and op["station_id"] == "b"
    )
    mx, my = move["to"]
    new_zone = {
        (mx + dx, my + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
    }
    assert new_zone.isdisjoint(bay)


# ----- Fix plan: exact file targets + summary format --------------------


def test_fix_plan_ops_name_exact_files():
    """Ops carry the exact spec/builder files to edit — no placeholders
    that force the caller to map city id -> file."""
    game_map = _make_map([
        _make_entity("Transit: B", 10, 10, transit_station_id="b"),
    ], bay_cells=set())
    game_map.city_transit = {"b": {"serves": "guild"}}
    game_map.city_buildings = {
        "guild": {"label": "guild", "display_name": "guild", "entrance": (10, 12)},
    }
    game_map.city_layout_id = "earth_river_coast"
    plan = city_audit.build_fix_plan(game_map, city_id="earth")
    assert plan is not None and plan["verified"], plan
    move = next(op for op in plan["ops"] if op["op"] == "move_station")
    assert move["file"] == "src/spacehack/data/planets/earth.py"
    assert "earth.py transit_stations pos" in move["stage"]
    paint = next(op for op in plan["ops"] if op["op"] == "paint_transit_bays")
    assert paint["target"]["file"] == "src/spacehack/earth_city.py"
    assert paint["target"]["function"] == "build_earth_layout"


def test_report_summary_is_compact():
    """Summary = verdict + violations; no tile/entity dump."""
    import json as json_mod

    game_map = _make_map([
        _make_entity("Transit: Hub", 5, 5, transit_station_id="hub"),
    ], bay_cells=set())
    violations = city_audit.check_station_clipping(game_map)
    payload = json_mod.loads(city_audit.report_summary("t", game_map, violations))
    assert payload["passed"] is False
    assert payload["violation_count"] == len(violations) > 0
    assert "tiles" not in payload
    assert "entities" not in payload
    clean = json_mod.loads(city_audit.report_summary("t", game_map, []))
    assert clean["passed"] is True and clean["violation_count"] == 0


# ----- Recommendations only propose carvable pads ----------------------


def test_cell_pad_ok_rejects_walkable_unpaintable_kinds():
    """A 'tree' cell is walkable but no overwrite set carves it — a pad
    zone containing one must be invalid (tau_ceti_b regression: a
    recommended pad contained a tree and the plan could not verify)."""
    game_map = _make_map([])
    tree = world.Tile(
        kind="tree", char="♣", walkable=True,
        fg=(80, 200, 90), bg=(20, 40, 20),
    )
    game_map.tiles[7][7] = tree
    assert city_audit._cell_pad_ok(game_map, 7, 7, 1, set()) is False
    assert city_audit._cell_pad_ok(game_map, 3, 3, 1, set()) is True


def test_recommendation_avoids_tree_cells():
    """The recommended pad's whole zone must be paintable ground."""
    game_map = _make_map([
        _make_entity("Transit: Waypoint", 5, 5, transit_station_id="way"),
    ], bay_cells=set())
    for y in range(2, 12):
        game_map.tiles[y][9] = world.Tile(
            kind="tree", char="♣", walkable=True,
            fg=(80, 200, 90), bg=(20, 40, 20),
        )
    violations = city_audit.check_station_clipping(game_map)
    rec = violations[0].recommendation
    assert rec is not None
    rx, ry = rec["pos"]
    assert all(
        game_map.tiles[ry + dy][rx + dx].kind in city_audit._PAINTABLE_PAD_KINDS
        for dx in (-1, 0, 1) for dy in (-1, 0, 1)
    )


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
    assert payload["buildings"], "earth must expose building records"
    entrances = [b["entrance"] for b in payload["buildings"].values()]
    assert all(e is not None for e in entrances), (
        f"every earth building must have an entrance; got {payload['buildings']}"
    )


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
    """On the real Earth map, every transit station sits on a painted
    transit_bay pad (earth_city.py now calls paint_transit_bays with
    force_center), so the audit must pass with zero R1 violations."""
    game_map = city_audit.build_final_map("earth")
    violations = city_audit.check_station_clipping(game_map)
    assert violations == [], (
        "earth transit stations must all sit on painted transit_bay pads; "
        "got: " + [(v.station, v.message) for v in violations]
    )


# ----- Recommendations + remediation ----------------------------------


def test_failing_station_gets_recommendation():
    """Every failing station carries a recommendation to a valid 3x3 spot."""
    game_map = _make_map([
        _make_entity("Transit: Hub", 5, 5, transit_station_id="hub"),
    ], bay_cells=set())  # no pad painted -> violation
    violations = city_audit.check_station_clipping(game_map)
    assert violations
    first = violations[0]
    assert first.recommendation is not None
    rec = first.recommendation
    assert set(rec) == {"pos", "distance", "note"}
    x, y = rec["pos"]
    assert 1 <= x < 19 and 1 <= y < 19  # pad must fit in the map
    # The recommended location must itself pass R1 if the station moved there
    moved = _make_map([
        _make_entity("Transit: Hub", x, y, transit_station_id="hub"),
    ], bay_cells={
        (x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
    })
    moved_violations = city_audit.check_station_clipping(moved)
    assert moved_violations == [], (
        f"recommended spot {rec['pos']} must be valid; got {moved_violations}"
    )


def test_clean_station_gets_no_recommendation():
    """A station with a proper pad produces no violations (and no rec)."""
    bay_cells = {(x, y) for x in range(4, 7) for y in range(4, 7)}
    game_map = _make_map([
        _make_entity("Transit: Ok", 5, 5, transit_station_id="ok"),
    ], bay_cells=bay_cells)
    assert city_audit.check_station_clipping(game_map) == []


def test_recommendation_avoids_entities():
    """The recommended location must not overlap other entity footprints."""
    # Surround the station with terminals on all sides of a 5x5 area;
    # the recommendation must land outside them.
    entities = [_make_entity("Transit: Hub", 10, 10, transit_station_id="hub")]
    for dx in (-2, 0, 2):
        for dy in (-2, 0, 2):
            if (dx, dy) != (0, 0):
                entities.append(_make_entity("Terminal", 10 + dx, 10 + dy))
    game_map = _make_map(entities, bay_cells=set())
    violations = city_audit.check_station_clipping(game_map)
    assert violations
    rec = violations[0].recommendation
    assert rec is not None
    rx, ry = rec["pos"]
    # Recommended pad (3x3 around rx,ry) must not touch any terminal cell
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            assert (rx + dx, ry + dy) not in {
                (10 + dx2, 10 + dy2)
                for dx2 in (-2, 0, 2) for dy2 in (-2, 0, 2) if (dx2, dy2) != (0, 0)
            }


def test_old_method_diagnosis_attaches_remediation():
    """When the map has zero transit_bay tiles, violations carry the
    old-authoring-method remediation text."""
    game_map = _make_map([
        _make_entity("Transit: Hub", 5, 5, transit_station_id="hub"),
    ], bay_cells=set())
    violations = city_audit.check_station_clipping(game_map)
    assert violations
    assert violations[0].remediation is not None
    assert "paint_transit_bays" in violations[0].remediation
    assert "city_kit" in violations[0].remediation


def test_no_remediation_when_bays_exist():
    """A partial-pad failure on a map WITH bay tiles gets no remediation
    (the module clearly paints bays; the problem is placement)."""
    bay_cells = {(x, y) for x in range(4, 7) for y in range(4, 7)}
    bay_cells.discard((4, 4))  # one corner missing
    game_map = _make_map([
        _make_entity("Transit: Hub", 5, 5, transit_station_id="hub"),
    ], bay_cells=bay_cells)
    game_map.tiles[4][4] = world.ROAD_SURFACE
    violations = city_audit.check_station_clipping(game_map)
    assert violations
    assert all(v.remediation is None for v in violations)


def test_recommendation_deterministic():
    """Same map -> same recommendation (distance, then y, then x)."""
    def build():
        return _make_map([
            _make_entity("Transit: Hub", 5, 5, transit_station_id="hub"),
        ], bay_cells=set())
    v1 = city_audit.check_station_clipping(build())
    v2 = city_audit.check_station_clipping(build())
    assert v1[0].recommendation == v2[0].recommendation


def test_earth_recommendations_and_remediation():
    """Earth is now authored the correct way (paint_transit_bays called in
    earth_city.py), so the real map produces no violations at all —
    recommendation/remediation behaviour is covered by the synthetic
    tests above."""
    game_map = city_audit.build_final_map("earth")
    violations = city_audit.check_station_clipping(game_map)
    assert violations == [], (
        "earth must pass R1; got: " + [(v.station, v.message) for v in violations]
    )


# ----- R1 check 5: pads never cover a door approach ---------------------


def _map_with_door(bay_cells, station_pos, entrance):
    game_map = _make_map([
        _make_entity("Transit: Bar", *station_pos, transit_station_id="bar"),
    ], bay_cells=bay_cells)
    game_map.city_buildings = {
        "bar": {"label": "bar", "display_name": "bar", "entrance": entrance},
    }
    return game_map


def test_r1_flags_pad_covering_door_approach():
    """A pad cell orthogonally adjacent to an entrance blocks the front
    walk (groom_b/ross_b regression)."""
    x, y = 5, 5
    bay = {(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    game_map = _map_with_door(bay, (x, y), entrance=(5, 3))  # (5,4) fronts door
    violations = city_audit.check_station_clipping(game_map)
    assert any(
        v.other == "door approach" and v.location == (5, 4)
        for v in violations
    )


def test_r1_allows_pad_beside_the_front_walk():
    """Same geometry shifted one cell east: the pad flanks the approach
    and no door-approach violation fires."""
    x, y = 7, 5
    bay = {(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    game_map = _map_with_door(bay, (x, y), entrance=(5, 3))
    violations = [
        v for v in city_audit.check_station_clipping(game_map)
        if v.other == "door approach"
    ]
    assert violations == []


def test_recommendation_avoids_door_approach_cells():
    """When a station must move, the recommended pad may not cover any
    door-approach cell."""
    game_map = _make_map([
        _make_entity("Transit: Bar", 5, 5, transit_station_id="bar"),
    ], bay_cells=set())
    game_map.city_buildings = {
        "bar": {"label": "bar", "display_name": "bar", "entrance": (5, 6)},
    }
    violations = city_audit.check_station_clipping(game_map)
    rec = violations[0].recommendation
    assert rec is not None
    rx, ry = rec["pos"]
    zone = {(rx + dx, ry + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    assert zone.isdisjoint({(5, 5), (6, 6), (4, 6), (5, 7)})


# ----- Fix plan rescues R2-unreachable stations -------------------------


def test_fix_plan_moves_station_far_from_its_target():
    """A station with a perfectly painted pad but far from its served
    entrance must still get a move op (vega_b regression: clean pads,
    unreachable target, and no op meant a refused plan with no path
    forward)."""
    x, y = 1, 1
    bay = {(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    game_map = _make_map([
        _make_entity("Transit: Far", x, y, transit_station_id="far"),
    ], bay_cells=bay)
    game_map.city_transit = {"far": {"serves": "bar"}}
    game_map.city_buildings = {
        # Opposite corner: 8-dir walkable steps = 18 > R2's 15 limit
        "bar": {"label": "bar", "display_name": "bar", "entrance": (19, 19)},
    }
    plan = city_audit.build_fix_plan(game_map)
    assert plan is not None and plan["verified"], plan
    move = next(op for op in plan["ops"] if op["op"] == "move_station")
    assert move["station_id"] == "far"
    mx, my = move["to"]
    assert max(abs(mx - 19), abs(my - 19)) <= 12, move["to"]
