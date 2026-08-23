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
    assert mercury.width == 100 and mercury.height == 70


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


# --- Mars colony layout ---


def test_mars_builds_with_all_systems():
    """Mars produces a 160x100 city with buildings, transit, and NPCs."""
    game_map = load_planet("mars")
    assert game_map.width == 160
    assert game_map.height == 100
    assert len(game_map.city_buildings) == 5
    assert len(game_map.city_transit) == 6
    assert any(
        getattr(e, "city_npc_id", "")
        for e in game_map.entities
    )


def test_mars_building_doors_walkable_and_reachable():
    """Every Mars building entrance is walkable and reachable from the pad."""
    game_map = load_planet("mars")
    reachable = _reachable(
        game_map, find_planet_spec("mars").hangar_anchor,
    )
    for label, record in game_map.city_buildings.items():
        entrance = record.get("entrance")
        if entrance is None:
            continue  # stamped asset did not record an entrance
        x, y = entrance
        assert game_map.tiles[y][x].walkable, f"{label} door not walkable"
        assert (x, y) in reachable, f"{label} door unreachable from pad"


def test_mars_transit_stations_walkable_and_reachable():
    """Mars transit stops are on walkable, reachable cells."""
    game_map = load_planet("mars")
    reachable = _reachable(
        game_map, find_planet_spec("mars").hangar_anchor,
    )
    for station_id, meta in game_map.city_transit.items():
        x, y = meta["pos"]
        tile = game_map.tiles[y][x]
        assert tile.walkable, f"station {station_id} on non-walkable tile"
        assert (x, y) in reachable, f"station {station_id} unreachable"


def test_mars_npc_spawns_walkable_and_unblocked():
    """Every Mars ambient citizen anchors on a walkable, unblocked cell."""
    game_map = load_planet("mars")
    positions = set()
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        tile = game_map.tiles[entity.pos.y][entity.pos.x]
        assert tile.walkable, f"{entity.city_npc_id} on a blocked tile"
        pos = (entity.pos.x, entity.pos.y)
        assert pos not in positions, f"{entity.city_npc_id} overlaps another NPC"
        positions.add(pos)
        assert game_map.blocking_entity_at(
            entity.pos.x, entity.pos.y, exclude=entity,
        ) is None


def test_mars_interiors_load_with_spawn_and_exit():
    """Every Mars building has an authored interior with P + exit."""
    game_map = load_planet("mars")
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, f"{label} interior has no spawn"
        assert any(
            tile.kind == "exit" for row in asset.game_map.tiles for tile in row
        ), f"{label} interior has no exit"


def test_mars_uses_authored_layout_not_generic_grid():
    """Mars routes through the authored mars_colony layout, not the grid."""
    game_map = load_planet("mars")
    assert getattr(game_map, "city_layout_id", None) == "mars_colony"
    assert len(getattr(game_map, "landmark_stamps", {})) == 5
    assert len(getattr(game_map, "skyline_placements", ())) > 100


# --- Regression: unreachable destinations, asset failures, resize ---


def test_earth_building_doors_walkable_and_reachable():
    """Every Earth building entrance is walkable and reachable from the pad."""
    game_map = load_planet("earth")
    reachable = _reachable(
        game_map, find_planet_spec("earth").hangar_anchor,
    )
    for label, record in game_map.city_buildings.items():
        x, y = record["entrance"]
        assert game_map.tiles[y][x].walkable, f"{label} door not walkable"
        assert (x, y) in reachable, f"{label} door unreachable from pad"


def test_earth_transit_stations_walkable_and_off_doors():
    """Transit stops are on walkable tiles and never block a building door."""
    game_map = load_planet("earth")
    door_cells = {
        record["entrance"] for record in game_map.city_buildings.values()
    }
    for station_id, meta in game_map.city_transit.items():
        x, y = meta["pos"]
        tile = game_map.tiles[y][x]
        assert tile.walkable, f"station {station_id} on non-walkable tile"
        assert (x, y) not in door_cells, f"station {station_id} blocks a door"


def test_earth_npc_spawns_walkable_and_unblocked():
    """Every Earth ambient citizen anchors on a walkable, unblocked cell."""
    game_map = load_planet("earth")
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        tile = game_map.tiles[entity.pos.y][entity.pos.x]
        assert tile.walkable, f"{entity.city_npc_id} on a blocked tile"
        assert game_map.blocking_entity_at(
            entity.pos.x, entity.pos.y, exclude=entity,
        ) is None, f"{entity.city_npc_id} overlaps another entity"


def test_missing_interior_layout_does_not_crash():
    """A building with a nonexistent interior_layout_id still builds."""
    from src.spacehack.data.planets import PlanetSpec
    from src.spacehack.city_builder import build_city
    from unittest.mock import MagicMock

    spec = PlanetSpec(
        id="test_missing", name="Test",
        char=".", fg=(200, 200, 200),
        description="test planet",
        width=40, height=30,
        hangar_anchor=(20, 15),
        buildings=(),
        showroom_ships=(),
        interior_layouts=(("bogus", "nonexistent_asset_id"),),
    )
    resolve_npc = MagicMock(return_value=None)
    resolve_ship = MagicMock(return_value=MagicMock(
        char='S', fg=(200, 200, 200), name='Test Ship', id='test_ship',
        width=2, height=1,
    ))
    # Must not raise
    game_map = build_city(spec, resolve_npc, resolve_ship)
    assert game_map.width == 40
    assert game_map.height == 30


def test_very_small_map_builds_without_error():
    """A planet with tiny dimensions still produces a valid city."""
    from src.spacehack.data.planets import PlanetSpec
    from src.spacehack.city_builder import build_city
    from unittest.mock import MagicMock

    spec = PlanetSpec(
        id="test_tiny", name="Tiny",
        char=".", fg=(200, 200, 200),
        description="tiny test",
        width=30, height=20,
        hangar_anchor=(15, 10),
        buildings=(),
        showroom_ships=(),
    )
    resolve_npc = MagicMock(return_value=None)
    resolve_ship = MagicMock(return_value=MagicMock(
        char='S', fg=(200, 200, 200), name='Ship', id='ship',
        width=2, height=1,
    ))
    game_map = build_city(spec, resolve_npc, resolve_ship)
    assert game_map.width == 30
    assert game_map.height == 20
    assert game_map.tiles[0][0].kind == "wall"
