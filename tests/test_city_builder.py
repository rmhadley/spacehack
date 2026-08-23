"""Phase 5 tests: the generic data-driven city builder.

Every landable planet now builds through ``city_builder.build_city`` —
terrain keyed by ``city_layout_id``, everything else driven by the spec.
Mercury (a compact desert research station) proves the pipeline runs
identically for a non-Earth city: buildings, transit, authored
interiors, and ambient NPCs all work from data alone.
"""

from __future__ import annotations

from collections import deque

from src.spacehack import city_landmarks, city_npcs, world
from src.spacehack.data.planets import find_planet_spec, load_planet


def _reachable(game_map: world.GameMap, start: world.Position) -> set[tuple[int, int]]:
    """Return four-way walkable cells reachable from ``start``."""
    origin = (start.x, start.y)
    seen = {origin}
    queue = deque([origin])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if point in seen or not game_map.in_bounds(*point):
                continue
            if not game_map.is_walkable(*point):
                continue
            seen.add(point)
            queue.append(point)
    return seen


def test_earth_and_mercury_share_one_builder_path():
    """Both cities carry the full spec-driven systems from the same build."""
    for planet_id in ("earth", "mercury"):
        game_map = load_planet(planet_id)
        assert game_map.city_layout_id, planet_id
        assert len(game_map.city_buildings) == len(find_planet_spec(planet_id).buildings)
        assert game_map.city_transit
        assert any(
            getattr(entity, "city_npc_id", "") for entity in game_map.entities
        )


def test_earth_keeps_river_coast_mercury_uses_station_layout():
    """Layouts dispatch on city_layout_id, not on a per-planet fork."""
    assert load_planet("earth").city_layout_id == "earth_river_coast"
    mercury = load_planet("mercury")
    assert mercury.city_layout_id == "mercury_station"
    assert mercury.width == 40 and mercury.height == 30


def test_mercury_uses_authored_exteriors_like_earth():
    """Mercury's buildings are stamped authored roofs, not legacy boxes:
    every enterable building has a landmark stamp, a roof label, and no
    make_building-style wall/label tiles."""
    mercury = load_planet("mercury")
    assert set(mercury.landmark_stamps) == {
        "mercury_spaceport", "mercury_lab", "mercury_bar", "mercury_supply",
    }
    label_chars = {
        tile.char
        for row in mercury.tiles for tile in row
        if tile.kind == "city_building_wall" and tile.char.isalpha()
    }
    assert set("SPACEPORTBARSUPPLYLAB") <= label_chars
    assert not any(
        tile.kind == "label" for row in mercury.tiles for tile in row
    )


def test_mercury_deck_has_roads_plaza_and_skyline():
    """The authored deck reads as a base: service roads, a commons plaza,
    the landing apron, and a few decorative domes."""
    mercury = load_planet("mercury")
    kinds = {
        tile.kind for row in mercury.tiles for tile in row
    }
    assert "road" in kinds
    assert "plaza" in kinds
    assert "landing_pad" in kinds
    assert mercury.skyline_placements


def test_mercury_transit_stations_walkable_and_off_doors():
    """Stations sit on walkable floor, never on a building door or a wall."""
    game_map = load_planet("mercury")
    door_cells = {
        record["entrance"] for record in game_map.city_buildings.values()
    }
    for station_id, meta in game_map.city_transit.items():
        x, y = meta["pos"]
        tile = game_map.tiles[y][x]
        assert tile.walkable, f"station {station_id} on a non-walkable tile"
        assert game_map.blocking_entity_at(x, y).transit_station_id == station_id
        assert (x, y) not in door_cells, f"station {station_id} blocks a door"


def test_mercury_building_doors_walkable_and_reachable():
    """Every building record's entrance is a walkable door tile."""
    game_map = load_planet("mercury")
    reachable = _reachable(
        game_map, find_planet_spec("mercury").hangar_anchor,
    )
    for label, record in game_map.city_buildings.items():
        x, y = record["entrance"]
        assert game_map.tiles[y][x].walkable, f"{label} door not walkable"
        assert (x, y) in reachable, f"{label} door unreachable from the pad"


def test_mercury_interiors_load_with_spawn_and_exit():
    """Every Mercury building has an authored interior with P + exit."""
    game_map = load_planet("mercury")
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, f"{label} interior has no spawn"
        assert any(
            tile.kind == "exit" for row in asset.game_map.tiles for tile in row
        ), f"{label} interior has no exit"


def test_mercury_npc_spawns_walkable():
    """Every ambient citizen anchors on a walkable, unblocked cell."""
    game_map = load_planet("mercury")
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        tile = game_map.tiles[entity.pos.y][entity.pos.x]
        assert tile.walkable, f"{entity.city_npc_id} on a blocked tile"
        assert game_map.blocking_entity_at(
            entity.pos.x, entity.pos.y, exclude=entity,
        ) is None


def test_station_layout_uses_whole_floor_as_traffic_lanes():
    """A compact base with no roads gets the whole floor as landmarks, so
    citizens cross the map instead of pacing the pad (regression: the pad
    cluster alone is a parking lot, not a lane network)."""
    mercury = load_planet("mercury")
    cells = city_npcs._city_landmarks(mercury)
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    assert len(cells) > 100
    assert max(xs) - min(xs) > mercury.width // 2
    assert max(ys) - min(ys) > mercury.height // 2


def test_earth_lanes_still_span_natively():
    """Earth's real road network keeps the kind-based landmark set (no
    whole-floor fallback triggered)."""
    earth = load_planet("earth")
    cells = city_npcs._city_landmarks(earth)
    xs = [x for x, _ in cells]
    ys = [y for _, y in cells]
    assert max(xs) - min(xs) > earth.width // 2
    assert max(ys) - min(ys) > earth.height // 2
