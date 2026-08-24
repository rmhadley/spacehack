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


def test_ac_station_is_a_hollow_ring_with_connected_spokes():
    """Alpha Centauri reads as a pressurized rotating ring, not a rectangle."""
    game_map = load_planet("ac_station")
    assert game_map.city_layout_id == "ac_ring_station"
    assert (game_map.width, game_map.height) == (120, 80)
    geometry = game_map.ring_geometry
    center_x, center_y = geometry["center"]
    assert game_map.tiles[center_y][center_x].kind == "city_plaza"
    assert game_map.tiles[center_y - 12][center_x - 12].kind == "ring_void"
    assert game_map.tiles[center_y + 12][center_x + 12].kind == "ring_void"
    for point in ((60, 9), (60, 71), (10, 40), (110, 40)):
        x, y = point
        assert game_map.in_bounds(x, y)
        assert game_map.tiles[y][x].kind in {"ring_hull", "road", "sidewalk"}
    assert len(game_map.ring_void_cells) > 1_000


def test_ac_station_landing_apron_is_smooth_under_dock_fixtures():
    """The ring dock uses a blank landing surface instead of dot texture."""
    game_map = load_planet("ac_station")
    apron_tiles = [
        game_map.tiles[y][x]
        for y in range(19, 26)
        for x in range(53, 68)
        if game_map.tiles[y][x].kind == "landing_pad"
    ]
    assert apron_tiles
    assert {tile.char for tile in apron_tiles} == {" "}


def test_ac_station_roof_labels_are_complete_and_facades_use_no_letter_noise():
    """Ring roofs show complete readable labels without decorative letters."""
    game_map = load_planet("ac_station")
    expected = {
        "ac_ring_spaceport": "SPACEPORT",
        "ac_ring_archive": "ARCHIVE",
        "ac_ring_lab": "LAB",
        "ac_ring_commons": "COMMONS",
        "ac_ring_observation": "OBSERVATION",
    }
    for layout_id, label in expected.items():
        stamp = game_map.landmark_stamps[layout_id]
        x_lo = min(x for x, _ in stamp["footprint"])
        x_hi = max(x for x, _ in stamp["footprint"])
        y_lo = min(y for _, y in stamp["footprint"])
        y_hi = max(y for _, y in stamp["footprint"])
        roof_rows = [
            "".join(game_map.tiles[y][x].char for x in range(x_lo, x_hi + 1))
            for y in range(y_lo, y_hi + 1)
        ]
        assert any(label in row for row in roof_rows), layout_id
        letters = {
            char for row in roof_rows for char in row if char.isalpha()
        }
        assert set(label) == letters, layout_id


def test_ac_station_transit_stops_match_building_entrance_side():
    """Every sector stop stays on the same south side as its door."""
    game_map = load_planet("ac_station")
    assert game_map.city_transit["spaceport"]["name"] == "Spaceport"
    for label in game_map.city_buildings:
        station = game_map.city_transit[label]
        stop_x, stop_y = station["pos"]
        building = find_planet_spec("ac_station").buildings
        spec_building = next(item for item in building if item.label == label)
        assert stop_y > spec_building.y_hi, label
        assert stop_x >= spec_building.x_lo - 2
        assert stop_x <= spec_building.x_hi + 2


def test_ac_station_buildings_and_transit_are_reachable():
    """Every ring sector has a walkable door and a connected transit stop."""
    game_map = load_planet("ac_station")
    spec = find_planet_spec("ac_station")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert len(game_map.city_buildings) == 5
    assert len(game_map.city_transit) == 6
    for label, record in game_map.city_buildings.items():
        entrance = record["entrance"]
        assert entrance is not None, label
        x, y = entrance
        assert game_map.tiles[y][x].walkable, label
        assert (x, y) in reachable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
        assert (x, y) not in game_map.ring_void_cells, station_id


def test_ac_station_interiors_and_population_are_complete():
    """The ring's five sectors load authored rooms and living station crew."""
    game_map = load_planet("ac_station")
    assert len([
        entity for entity in game_map.entities
        if getattr(entity, "city_npc_id", "")
    ]) == 6
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, label
        assert any(
            tile.kind == "exit" for row in asset.game_map.tiles for tile in row
        ), label
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
        assert game_map.blocking_entity_at(
            entity.pos.x, entity.pos.y, exclude=entity,
        ) is None


def test_eri_b_is_a_large_canyon_settlement():
    """Epsilon Eridani b uses the super-Earth-scale canyon layout."""
    game_map = load_planet("eri_b")
    assert game_map.city_layout_id == "eri_canyon_settlement"
    assert (game_map.width, game_map.height) == (200, 140)
    assert len(game_map.canyon_cells) > 1_500
    assert len(game_map.bridge_crossings) == 4
    assert any(tile.kind == "canyon_floor" for row in game_map.tiles for tile in row)
    assert any(tile.kind == "bridge" for row in game_map.tiles for tile in row)
    assert game_map.tiles[47][78].kind == "monument"


def test_eri_b_buildings_transit_and_population_are_reachable():
    """The large settlement keeps every service connected across the canyon."""
    game_map = load_planet("eri_b")
    spec = find_planet_spec("eri_b")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert len(game_map.city_buildings) == 4
    assert len(game_map.city_transit) == 5
    assert sum(bool(getattr(entity, "city_npc_id", "")) for entity in game_map.entities) == 8
    for label, record in game_map.city_buildings.items():
        entrance = record["entrance"]
        assert entrance is not None, label
        x, y = entrance
        assert game_map.tiles[y][x].walkable, label
        assert (x, y) in reachable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
            assert game_map.blocking_entity_at(
                entity.pos.x, entity.pos.y, exclude=entity,
            ) is None


def test_eri_b_transit_stops_are_on_their_buildings_entrance_side():
    """Every Epsilon service stop is south of its building's south door."""
    game_map = load_planet("eri_b")
    spec = find_planet_spec("eri_b")
    for building in spec.buildings:
        stop = game_map.city_transit[building.label]["pos"]
        assert stop[1] > building.y_hi, building.label
        assert building.x_lo - 2 <= stop[0] <= building.x_hi + 2


def test_eri_b_uses_authored_exteriors_and_interiors():
    """All four Epsilon facilities use complete authored rooms and facades."""
    game_map = load_planet("eri_b")
    for label, record in game_map.city_buildings.items():
        exterior = city_landmarks.load_city_landmark(f"eri_{label}")
        assert {len(row) for row in exterior.tiles} == {exterior.width}, label
        assert sum(
            tile.kind == "city_building_door"
            for row in exterior.tiles for tile in row
        ) == 1
        interior = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert interior.spawn is not None, label
        assert any(
            tile.kind == "exit" for row in interior.game_map.tiles for tile in row
        ), label


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


def test_mars_has_planned_boulevard_grid_and_distinct_high_tech_palette():
    """Mars uses rectilinear avenues and a high-tech public realm."""
    game_map = load_planet("mars")
    road_cells = {
        (x, y): tile
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "road"
    }
    horizontal = sum(
        all((x, y) in road_cells for x in range(2, game_map.width - 2))
        for y in range(game_map.height)
    )
    vertical = sum(
        all((x, y) in road_cells for y in range(2, game_map.height - 2))
        for x in range(game_map.width)
    )
    assert horizontal >= 4
    assert vertical >= 3
    assert any(tile.kind == "sidewalk" for row in game_map.tiles for tile in row)
    assert any(tile.kind == "monument" for row in game_map.tiles for tile in row)
    assert any(
        tile.kind == "city_building_wall" and tile.bg[2] > tile.bg[0]
        for row in game_map.tiles for tile in row
    )


def test_authored_city_sidewalks_use_one_consistent_palette():
    """Door approaches and main sidewalks share each city's theme colors."""
    for planet_id in ("earth", "mercury", "mars"):
        game_map = load_planet(planet_id)
        palettes = {
            (tile.fg, tile.bg)
            for row in game_map.tiles
            for tile in row
            if tile.kind == "sidewalk"
        }
        assert len(palettes) == 1, f"{planet_id} has mixed sidewalk colors"


def test_mars_transit_and_npcs_are_separate_from_building_doors():
    """Public stops and ambient citizens do not occupy entrances or roofs."""
    game_map = load_planet("mars")
    doors = {
        record["entrance"] for record in game_map.city_buildings.values()
    }
    stations = {
        metadata["pos"] for metadata in game_map.city_transit.values()
    }
    assert doors.isdisjoint(stations)
    for position in stations:
        x, y = position
        assert game_map.tiles[y][x].kind != "sidewalk"
        assert any(
            game_map.tiles[y + dy][x + dx].kind == "sidewalk"
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
            if game_map.in_bounds(x + dx, y + dy)
        )
    door_approaches = {
        (x, y + 1)
        for x, y in doors
        if game_map.in_bounds(x, y + 1)
    }
    assert stations.isdisjoint(door_approaches)
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert (entity.pos.x, entity.pos.y) not in doors
            assert (entity.pos.x, entity.pos.y) not in stations


def test_mars_facades_are_rectangular_and_doors_are_on_outer_edges():
    """Each authored facade is complete and exposes a real outside door."""
    game_map = load_planet("mars")
    for label, record in game_map.city_buildings.items():
        layout_id = f"mars_{label}"
        asset = city_landmarks.load_city_landmark(layout_id)
        assert {len(row) for row in asset.tiles} == {asset.width}
        doors = [
            (x, y)
            for y, row in enumerate(asset.tiles)
            for x, tile in enumerate(row)
            if tile.kind == "city_building_door"
        ]
        assert len(doors) == 1
        door_x, door_y = doors[0]
        assert door_y == asset.height - 1
        assert record["entrance"] == (
            game_map.landmark_stamps[layout_id]["origin"][0] + door_x,
            game_map.landmark_stamps[layout_id]["origin"][1] + door_y,
        )


def test_mars_buildings_do_not_overwrite_public_corridors():
    """The planned city keeps building footprints off roads and sidewalks."""
    game_map = load_planet("mars")
    public_cells = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind in {"road", "sidewalk"}
    }
    for stamp in game_map.landmark_stamps.values():
        assert not public_cells.intersection(stamp["footprint"])


def test_mars_spaceport_apron_replaces_west_port_road():
    """The port's west side is landing space; the city road starts east."""
    game_map = load_planet("mars")
    berth = find_planet_spec("mars").hangar_anchor
    marked_berth = {
        (berth.x, berth.y),
        (berth.x - 1, berth.y - 1),
        (berth.x + 1, berth.y - 1),
        (berth.x - 1, berth.y + 1),
        (berth.x + 1, berth.y + 1),
    }
    for y in range(87, 94):
        for x in range(3, 35):
            if (x, y) not in marked_berth:
                assert game_map.tiles[y][x].kind == "landing_pad"
    for y in (89, 90, 91):
        assert game_map.tiles[y][34].kind == "landing_pad"
        assert game_map.tiles[y][35].kind == "road"
    port_entities = [
        entity for entity in game_map.entities
        if entity.pos.x < 35 and 87 <= entity.pos.y < 94
    ]
    assert any(entity.ship_id for entity in port_entities)
    assert sum(entity.trade_terminal for entity in port_entities) == 1
    assert sum(entity.mech_terminal for entity in port_entities) == 1
    assert sum(entity.armory_terminal for entity in port_entities) == 1
    fixtures = [
        entity for entity in port_entities
        if entity.ship_id or entity.trade_terminal
        or entity.mech_terminal or entity.armory_terminal
    ]
    fixture_cells = {
        (x, y)
        for entity in fixtures
        for y in range(entity.pos.y, entity.pos.y + entity.height)
        for x in range(entity.pos.x, entity.pos.x + entity.width)
    }
    assert len(fixture_cells) == sum(entity.width * entity.height for entity in fixtures)
    assert max(x for x, _ in fixture_cells) - min(x for x, _ in fixture_cells) >= 15
    assert max(y for _, y in fixture_cells) - min(y for _, y in fixture_cells) >= 3


def test_mars_owned_ship_berth_is_marked_and_service_terminals_clustered():
    """The owned ship has a visible apron berth clear of the spaceport door."""
    game_map = load_planet("mars")
    spec = find_planet_spec("mars")
    berth = (spec.hangar_anchor.x, spec.hangar_anchor.y)
    port_door = game_map.city_buildings["spaceport"]["entrance"]
    stations = {
        metadata["pos"] for metadata in game_map.city_transit.values()
    }
    assert game_map.tiles[berth[1]][berth[0]].kind == "plaza"
    assert berth != port_door
    assert berth not in stations
    assert abs(berth[0] - port_door[0]) + abs(berth[1] - port_door[1]) >= 3

    terminals = [
        entity for entity in game_map.entities
        if entity.trade_terminal or entity.mech_terminal or entity.armory_terminal
    ]
    assert len(terminals) == 3
    terminal_cells = {(entity.pos.x, entity.pos.y) for entity in terminals}
    assert terminal_cells == {
        (berth[0] - 3, berth[1] + 2),
        (berth[0], berth[1] + 2),
        (berth[0] + 3, berth[1] + 2),
    }
    assert berth not in terminal_cells
    assert max(x for x, _ in terminal_cells) - min(x for x, _ in terminal_cells) == 6
    assert all(
        game_map.tiles[y][x].kind == "landing_pad"
        for x, y in terminal_cells
    )


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
