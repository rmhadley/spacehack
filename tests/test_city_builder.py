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
from src.spacehack.data.planets import (
    find_planet_spec,
    list_planet_specs,
    load_planet,
)


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
    """Every Epsilon service stop stays beside its destination entrance."""
    game_map = load_planet("eri_b")
    spec = find_planet_spec("eri_b")
    for building in spec.buildings:
        entrance = game_map.city_buildings[building.label]["entrance"]
        stop = game_map.city_transit[building.label]["pos"]
        assert stop != entrance, building.label
        assert stop[1] > entrance[1], building.label
        building_bounds = next(
            item for item in spec.buildings if item.label == building.label
        )
        assert building_bounds.x_lo <= stop[0] <= building_bounds.x_hi, building.label
        neighbors = {
            (stop[0] + dx, stop[1] + dy)
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
            if game_map.in_bounds(stop[0] + dx, stop[1] + dy)
        }
        assert any(
            game_map.tiles[y][x].kind == "sidewalk"
            for x, y in neighbors
        ), building.label
        assert game_map.tiles[stop[1]][stop[0]].kind != "sidewalk", building.label
        assert game_map.tiles[stop[1]][stop[0]].kind not in {
            "road", "bridge", "landing_pad",
        }, building.label
        assert all(
            game_map.tiles[y][x].kind != "sidewalk"
            for x, y in {(stop[0], stop[1])}
        ), building.label


def test_eri_b_public_routes_form_one_connected_network():
    """Collectors, sidewalks, plazas, and bridges form one civic network."""
    from collections import deque

    game_map = load_planet("eri_b")
    route_kinds = {"road", "sidewalk", "bridge", "plaza", "landing_pad"}
    route = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind in route_kinds
    }
    start = next(iter(route))
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            point = (x + dx, y + dy)
            if point in seen or point not in route:
                continue
            seen.add(point)
            queue.append(point)
    assert seen == route
    assert sum(tile.kind == "bridge" for row in game_map.tiles for tile in row) >= 4 * 18


def test_eri_b_buildings_clear_public_circulation():
    """Epsilon facades occupy planned blocks, never public corridors."""
    game_map = load_planet("eri_b")
    public_kinds = {"road", "sidewalk", "bridge", "landing_pad", "city_plaza"}
    for label, stamp in game_map.landmark_stamps.items():
        overlap = {
            point for point in stamp["footprint"]
            if game_map.tiles[point[1]][point[0]].kind in public_kinds
        }
        assert not overlap, label
        building_label = label.removeprefix("eri_")
        entrance = game_map.city_buildings[building_label]["entrance"]
        approach = (entrance[0], entrance[1] + 1)
        assert game_map.in_bounds(*approach), label
        assert game_map.tiles[approach[1]][approach[0]].walkable, label


def test_eri_b_roofs_are_complete_and_quiet():
    """Every Epsilon roof is rectangular, filled, and free of stray letters."""
    game_map = load_planet("eri_b")
    expected = {
        "eri_spaceport": "SPACEPORT",
        "eri_bar": "BAR",
        "eri_merchants": "MERCHANTS",
        "eri_militia": "MILITIA",
    }
    for layout_id, label in expected.items():
        asset = city_landmarks.load_city_landmark(layout_id)
        assert {len(row) for row in asset.tiles} == {asset.width}, layout_id
        assert sum(
            tile.kind == "city_building_door"
            for row in asset.tiles for tile in row
        ) == 1, layout_id
        assert all(
            tile.kind in {"city_building_wall", "city_building_roof", "city_building_door"}
            for row in asset.tiles for tile in row
        ), layout_id
        stamp = game_map.landmark_stamps[layout_id]
        x_lo = min(x for x, _ in stamp["footprint"])
        x_hi = max(x for x, _ in stamp["footprint"])
        y_lo = min(y for _, y in stamp["footprint"])
        y_hi = max(y for _, y in stamp["footprint"])
        rows = [
            "".join(game_map.tiles[y][x].char for x in range(x_lo, x_hi + 1))
            for y in range(y_lo, y_hi + 1)
        ]
        assert any(label in row for row in rows), layout_id
        letters = {char for row in rows for char in row if char.isalpha()}
        assert letters == set(label), layout_id


def test_eri_b_dash_runs_are_complete_road_bands():
    """A road center marker is never left as a detached dash line."""
    game_map = load_planet("eri_b")
    for y, row in enumerate(game_map.tiles):
        for x, tile in enumerate(row):
            if tile.char != "-":
                continue
            assert tile.kind == "road"
            assert all(
                game_map.in_bounds(x + dx, y + dy)
                and game_map.tiles[y + dy][x + dx].kind == "road"
                for dx, dy in ((0, -1), (0, 1))
            ), (x, y)


def test_eri_b_beacon_spine_is_not_overwritten_by_bar():
    """The civic plaza remains separate from the bar block."""
    game_map = load_planet("eri_b")
    bar = game_map.landmark_stamps["eri_bar"]["footprint"]
    plaza = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "plaza"
    }
    assert not bar.intersection(plaza)
    assert game_map.tiles[47][78].kind == "monument"



def test_eri_b_spaceport_apron_is_smooth_and_fixtures_are_clear():
    """The landing apron is quiet beneath ships and terminals."""
    game_map = load_planet("eri_b")
    apron = [
        game_map.tiles[y][x]
        for y in range(31, 50)
        for x in range(18, 52)
    ]
    assert {tile.kind for tile in apron} <= {"landing_pad", "plaza", "neon"}
    assert {
        tile.char for tile in apron if tile.kind == "landing_pad"
    } == {" "}
    fixtures = [
        entity for entity in game_map.entities
        if entity.ship_id or entity.trade_terminal
        or entity.mech_terminal or entity.armory_terminal
    ]
    cells = {
        (x, y)
        for entity in fixtures
        for y in range(entity.pos.y, entity.pos.y + entity.height)
        for x in range(entity.pos.x, entity.pos.x + entity.width)
    }
    assert len(cells) == sum(entity.width * entity.height for entity in fixtures)
    assert all(game_map.tiles[y][x].kind == "landing_pad" for x, y in cells)


def test_eri_b_npcs_are_walkable_clear_and_reachable():
    """Ambient colonists do not spawn inside public fixtures or facades."""
    game_map = load_planet("eri_b")
    reachable = _reachable(game_map, find_planet_spec("eri_b").hangar_anchor)
    building_cells = {
        point for stamp in game_map.landmark_stamps.values()
        for point in stamp["footprint"]
    }
    station_cells = {
        metadata["pos"] for metadata in game_map.city_transit.values()
    }
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        point = (entity.pos.x, entity.pos.y)
        assert point not in building_cells, entity.city_npc_id
        assert point not in station_cells, entity.city_npc_id
        assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
        assert point in reachable
        assert game_map.blocking_entity_at(
            entity.pos.x, entity.pos.y, exclude=entity,
        ) is None


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


def test_eri_b_has_homesteads_market_square_and_mine_head():
    """The frontier settlement reads as lived-in beyond the four
    enterable buildings: non-enterable sheds, a west-bank market square,
    and a sealed mine head with ore heaps on the north-eastern terrace."""
    game_map = load_planet("eri_b")

    # Non-enterable homestead sheds — city_building_wall tiles that are not
    # part of any enterable building's landmark stamp.
    landmark_cells = {
        point
        for stamp in game_map.landmark_stamps.values()
        for point in stamp["footprint"]
    }
    shed_walls = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "city_building_wall" and (x, y) not in landmark_cells
    }
    assert len(shed_walls) > 100

    # A market square with stalls (♦) sits between the west-bank collectors.
    market = [
        game_map.tiles[y][x]
        for y in range(63, 80) for x in range(22, 51)
    ]
    assert any(tile.kind == "plaza" for tile in market)
    assert any(tile.char == "♦" for tile in market)

    # A sealed mine head carves into the north-eastern terrace.
    kinds = {tile.kind for row in game_map.tiles for tile in row}
    assert {"mine_rock", "mine_shaft", "ore_heap"} <= kinds


def test_wolf_b_is_a_crater_pirate_outpost():
    """Wolf 359 b uses the authored crater outpost layout."""
    game_map = load_planet("wolf_b")
    assert game_map.city_layout_id == "wolf_crater_settlement"
    assert (game_map.width, game_map.height) == (120, 80)
    assert len(game_map.city_buildings) == 3
    assert len(game_map.city_transit) == 3
    assert sum(
        bool(getattr(entity, "city_npc_id", "")) for entity in game_map.entities
    ) == 12
    # The crater settlement has non-enterable shacks and antenna masts.
    shed_walls = sum(
        tile.kind == "city_building_wall"
        for row in game_map.tiles for tile in row
    )
    # Three enterable buildings + many non-enterable shacks/antennas.
    assert shed_walls > 100
    # A cave entrance marks the delve site.
    assert any(tile.kind == "mine_shaft" for row in game_map.tiles for tile in row)
    # Smuggler's Row — contraband market south of the bar.
    stalls = sum(
        tile.char == "▒" and tile.kind == "plaza"
        for row in game_map.tiles for tile in row
    )
    assert stalls >= 20
    # Centre beacon.
    assert any(tile.kind == "neon" for row in game_map.tiles for tile in row)


def test_wolf_b_buildings_transit_and_population_are_reachable():
    """The pirate outpost keeps every service connected across the crater."""
    game_map = load_planet("wolf_b")
    spec = find_planet_spec("wolf_b")
    reachable = _reachable(game_map, spec.hangar_anchor)
    for label, record in game_map.city_buildings.items():
        entrance = record["entrance"]
        assert entrance is not None, label
        assert game_map.tiles[entrance[1]][entrance[0]].walkable, label
        assert entrance in reachable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
            assert (entity.pos.x, entity.pos.y) in reachable
            assert game_map.blocking_entity_at(
                entity.pos.x, entity.pos.y, exclude=entity,
            ) is None


def test_ross_c_npcs_spawn_outside_the_merchants_facade():
    """Ross c ambient anchors never land inside the brokers hall."""
    game_map = load_planet("ross_c")
    merchant_cells = game_map.landmark_stamps["ross_c_merchants"]["footprint"]
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", "").startswith("rsc_"):
            assert (entity.pos.x, entity.pos.y) not in merchant_cells
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable


def test_ross_c_uses_three_transit_stops_and_pad_showroom():
    """Cinder keeps only the useful Spaceport, bar, and depot stops."""
    game_map = load_planet("ross_c")
    assert set(game_map.city_transit) == {"spaceport", "long_burn", "depot"}
    assert game_map.city_transit["spaceport"]["name"] == "Spaceport"
    assert all(
        set(metadata["destinations"]) == set(game_map.city_transit) - {station_id}
        for station_id, metadata in game_map.city_transit.items()
    )
    owned = find_planet_spec("ross_c").hangar_anchor
    showroom = [entity for entity in game_map.entities if entity.ship_id]
    assert len(showroom) == 3
    assert all(entity.pos.y < owned.y for entity in showroom)
    assert all(
        game_map.tiles[entity.pos.y][entity.pos.x].kind == "landing_pad"
        for entity in showroom
    )


def test_ross_c_merchants_and_depot_have_complete_south_walls():
    """The two south-door buildings retain solid bottom facades."""
    for layout_id in ("ross_c_merchants", "ross_c_depot"):
        asset = city_landmarks.load_city_landmark(layout_id)
        bottom = asset.tiles[-1]
        assert all(tile.kind == "city_building_wall" for tile in bottom)


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
        if tile.kind in {"city_building_wall", "city_building_roof"} and tile.char.isalpha()
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
    assert len(game_map.city_transit) == 5
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
        assert game_map.tiles[y][x].kind == "transit_bay"
        assert all(
            game_map.tiles[y + dy][x + dx].walkable
            for dx in (-1, 0, 1)
            for dy in (-1, 0, 1)
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


# --- Groombridge 34 b: hardpan boomtown --------------------------------


def test_groom_b_is_a_hardpan_boomtown():
    """Groombridge reads as a strung-out mining camp, not a planned city."""
    game_map = load_planet("groom_b")
    assert game_map.city_layout_id == "groom_hardpan_boomtown"
    assert (game_map.width, game_map.height) == (120, 80)
    assert len(game_map.city_buildings) == 4
    assert len(game_map.city_transit) == 4
    assert sum(
        bool(getattr(entity, "city_npc_id", "")) for entity in game_map.entities
    ) == 10
    # Tailings mounds are the plain's only relief.
    tailings = sum(
        tile.char == "▲" and tile.kind == "city_building_wall"
        for row in game_map.tiles for tile in row
    )
    assert tailings >= 15
    # Shanty shacks ring the town outside the four service buildings.
    shack_roofs = sum(
        tile.char == '"' for row in game_map.tiles for tile in row
    )
    assert shack_roofs >= 8
    # Claim stakes mark the outer dig fields.
    stakes = sum(
        tile.char == "|" and tile.kind == "floor"
        for row in game_map.tiles for tile in row
    )
    assert stakes >= 15
    # No delve site here — Groombridge has no explorable caves.
    assert not any(
        tile.kind == "mine_shaft" for row in game_map.tiles for tile in row
    )
    # The landing apron stays smooth under dock fixtures.
    apron = [
        tile for row in game_map.tiles for tile in row
        if tile.kind == "landing_pad"
    ]
    assert apron
    assert {tile.char for tile in apron} == {" "}


def test_groom_b_buildings_transit_and_population_are_reachable():
    """The boomtown keeps every service connected along the haul road."""
    game_map = load_planet("groom_b")
    spec = find_planet_spec("groom_b")
    reachable = _reachable(game_map, spec.hangar_anchor)
    for label, record in game_map.city_buildings.items():
        entrance = record["entrance"]
        assert entrance is not None, label
        assert game_map.tiles[entrance[1]][entrance[0]].walkable, label
        assert entrance in reachable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
            assert (entity.pos.x, entity.pos.y) in reachable
            assert game_map.blocking_entity_at(
                entity.pos.x, entity.pos.y, exclude=entity,
            ) is None


def test_groom_b_interiors_load_with_spawn_and_exit():
    """All four service buildings have authored, enterable interiors."""
    game_map = load_planet("groom_b")
    assert set(game_map.city_buildings) == {
        "spaceport", "bar", "bounties", "depot",
    }
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, label
        assert any(
            tile.kind == "exit" for row in asset.game_map.tiles for tile in row
        ), label


def test_groom_b_population_is_deliberately_lawless():
    """No patrol presence: prospectors, crew, hunters, and one shady type."""
    from src.spacehack.data.city_npcs import GROOM_B_POPULATION
    ids = {npc.id for npc in GROOM_B_POPULATION}
    assert len(ids) == 10
    assert all(npc_id.startswith("groom_") for npc_id in ids)
    # The Last Gate loiterer includes a hostile pirate raider.
    assert "groom_gate_shade" in ids
    # Bounty office staffed by the guild override, not a patrol captain.
    spec = find_planet_spec("groom_b")
    overrides = dict(spec.npc_overrides)
    assert "bounty_master" in overrides
    assert overrides["bounty_master"].guild == "bhguild"


# --- Tau Ceti b: canopy clearing ---------------------------------------


def test_tc_b_is_a_canopy_clearing():
    """Tau Cet b reads as a town hacked out of a purple alien rainforest."""
    game_map = load_planet("tc_b")
    assert game_map.city_layout_id == "tc_canopy_clearing"
    assert (game_map.width, game_map.height) == (160, 100)
    assert len(game_map.city_buildings) == 3
    assert len(game_map.city_transit) == 3
    assert sum(
        bool(getattr(entity, "city_npc_id", "")) for entity in game_map.entities
    ) == 9
    # The canopy wall rings the clearing -- thousands of blocked trees.
    canopy = sum(
        tile.char == "♣" and not tile.walkable
        for row in game_map.tiles for tile in row
    )
    assert canopy >= 4000
    # Walkable saplings push through the meadow floor.
    saplings = sum(
        tile.char == "♣" and tile.walkable
        for row in game_map.tiles for tile in row
    )
    assert saplings >= 100
    # Bioluminescent spore patches glow in the undergrowth.
    spores = sum(
        tile.kind == "neon" for row in game_map.tiles for tile in row
    )
    assert spores >= 5
    # No delve site here.
    assert not any(
        tile.kind == "mine_shaft" for row in game_map.tiles for tile in row
    )
    # The landing apron stays smooth under dock fixtures.
    apron = [
        tile for row in game_map.tiles for tile in row
        if tile.kind == "landing_pad"
    ]
    assert apron
    assert {tile.char for tile in apron} == {" "}


def test_tc_b_buildings_transit_and_population_are_reachable():
    """The clearing keeps every service connected across the groves."""
    game_map = load_planet("tc_b")
    spec = find_planet_spec("tc_b")
    reachable = _reachable(game_map, spec.hangar_anchor)
    for label, record in game_map.city_buildings.items():
        entrance = record["entrance"]
        assert entrance is not None, label
        assert game_map.tiles[entrance[1]][entrance[0]].walkable, label
        assert entrance in reachable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
            assert (entity.pos.x, entity.pos.y) in reachable
            assert game_map.blocking_entity_at(
                entity.pos.x, entity.pos.y, exclude=entity,
            ) is None


def test_tc_b_interiors_load_with_spawn_and_exit():
    """All three service buildings have authored, enterable interiors."""
    game_map = load_planet("tc_b")
    assert set(game_map.city_buildings) == {"spaceport", "bar", "merchants"}
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, label
        assert any(
            tile.kind == "exit" for row in asset.game_map.tiles for tile in row
        ), label


def test_tc_b_keeps_the_salvage_specialist_quest_hook():
    """Act 0 still spawns the salvage_specialist in the merchants hall:
    the quest spot survives the redesign and the interior keeps the
    centre column plus centre-east cell walkable for her dynamic spawn."""
    spec = find_planet_spec("tc_b")
    assert (("salvage_specialist", "merchants")) in spec.quest_npc_spots
    asset = city_landmarks.load_city_interior(
        dict(spec.interior_layouts)["merchants"],
    )
    interior = asset.game_map
    cx, cy = interior.width // 2, interior.height // 2
    assert interior.tiles[cy][cx].walkable
    assert interior.tiles[cy][cx + 1].walkable


def test_tc_b_population_is_a_lawful_frontier():
    """Colonists and rangers only -- no pirate element on Tau Cet b."""
    from src.spacehack.data.city_npcs import TC_B_POPULATION
    ids = {npc.id for npc in TC_B_POPULATION}
    assert len(ids) == 9
    assert all(npc_id.startswith("tc_") for npc_id in ids)
    rangers = {
        npc.id for npc in TC_B_POPULATION
        if npc.npc_char_id == "militia_trooper"
    }
    assert len(rangers) == 2
    assert not any("pirate" in npc.npc_char_id for npc in TC_B_POPULATION)


# --- Epsilon Indi b: patchwork farmland ---------------------------------


def test_indi_b_is_a_patchwork_farm_town():
    """Indi b reads as farmland: crop plots, hedgerows, silos, lanes."""
    game_map = load_planet("indi_b")
    assert game_map.city_layout_id == "indi_farmland_grid"
    assert (game_map.width, game_map.height) == (160, 100)
    assert len(game_map.city_buildings) == 4
    assert len(game_map.city_transit) == 4
    assert sum(
        bool(getattr(entity, "city_npc_id", "")) for entity in game_map.entities
    ) == 10
    # Mature crop plots dominate the fields.
    mature = sum(
        tile.char == "█" and tile.kind == "grass"
        for row in game_map.tiles for tile in row
    )
    assert mature >= 2000
    # Hedgerow windbreaks divide the plots.
    hedges = sum(
        tile.kind == "tree" for row in game_map.tiles for tile in row
    )
    assert hedges >= 400
    # Grain silos stand near the harvest road and guild hall.
    silos = sum(
        tile.char == "O" for row in game_map.tiles for tile in row
    )
    assert silos >= 5
    # The crossroads market is a real plaza.
    plaza = sum(
        tile.kind == "plaza" for row in game_map.tiles for tile in row
    )
    assert plaza >= 150
    # No delve site here.
    assert not any(
        tile.kind == "mine_shaft" for row in game_map.tiles for tile in row
    )
    # The landing apron stays smooth under dock fixtures.
    apron = [
        tile for row in game_map.tiles for tile in row
        if tile.kind == "landing_pad"
    ]
    assert apron
    assert {tile.char for tile in apron} == {" "}


def test_indi_b_buildings_transit_and_population_are_reachable():
    """Every door, transit stop, and citizen connects across the fields."""
    game_map = load_planet("indi_b")
    spec = find_planet_spec("indi_b")
    reachable = _reachable(game_map, spec.hangar_anchor)
    for label, record in game_map.city_buildings.items():
        entrance = record["entrance"]
        assert entrance is not None, label
        assert game_map.tiles[entrance[1]][entrance[0]].walkable, label
        assert entrance in reachable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
            assert (entity.pos.x, entity.pos.y) in reachable
            assert game_map.blocking_entity_at(
                entity.pos.x, entity.pos.y, exclude=entity,
            ) is None


def test_indi_b_interiors_load_with_spawn_and_exit():
    """All four service buildings have authored, enterable interiors."""
    game_map = load_planet("indi_b")
    assert set(game_map.city_buildings) == {
        "spaceport", "bar", "merchants", "militia",
    }
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, label
        assert any(
            tile.kind == "exit" for row in asset.game_map.tiles for tile in row
        ), label


def test_indi_b_militia_door_faces_the_patrol_lane():
    """The militia station's north-side door opens onto its forecourt."""
    game_map = load_planet("indi_b")
    spec = find_planet_spec("indi_b")
    militia = next(b for b in spec.buildings if b.label == "militia")
    assert militia.door_north
    entrance = game_map.city_buildings["militia"]["entrance"]
    assert entrance[1] == militia.y_lo, entrance  # on the north edge


def test_indi_b_population_is_a_lawful_breadbasket():
    """Farmers and troopers -- the arm's established, orderly world."""
    from src.spacehack.data.city_npcs import INDI_B_POPULATION
    ids = {npc.id for npc in INDI_B_POPULATION}
    assert len(ids) == 10
    assert all(npc_id.startswith("indi_") for npc_id in ids)
    troopers = {
        npc.id for npc in INDI_B_POPULATION
        if npc.npc_char_id == "militia_trooper"
    }
    assert len(troopers) == 2
    overrides = dict(find_planet_spec("indi_b").npc_overrides)
    assert {"barkeep", "guild_master"} <= set(overrides)


# --- Cross-city circulation invariants ----------------------------------
#
# Roads should be purposeful, sidewalks should allow access, and transit
# stops should drop you near something worth visiting.

# Route surfaces that legitimately front a door. Bare ground (plain
# floor/grass) does not count -- that is how "the front walk goes
# nowhere" bugs slip through reachability checks.
_ROUTE_KINDS = frozenset({"road", "sidewalk", "plaza", "landing_pad"})

# Cave cities have no road vocabulary: doors open onto carved tunnel
# floor and the tunnels themselves are the routes.
_NO_ROUTE_VOCABULARY = frozenset({"barnards_mine_colony"})

# Legacy town-center stops from Phases 1-5: intentionally central
# rather than door-side. Grandfathered like the architecture ratchet --
# shrink this table as those cities get revisited.
_STOP_DISTANCE_GRANDFATHER = {
    ("earth", "hub"): 35,
    ("mercury", "hub"): 40,
    # Cloudbreak depot stop sits deliberately on the depot lane rim,
    # right beside the road and the sidewalk fronting the depot door.
    ("venus", "depot"): 13,
}

_STOP_BASE_REACH = 12


def _authored_city_ids():
    from src.spacehack.city_builder import _LAYOUTS
    return [
        spec.id for spec in list_planet_specs()
        if spec.city_layout_id in _LAYOUTS
    ]


def _near_landmark(game_map, x, y, radius=2):
    """True when plaza/neon landmark tiles sit within ``radius``."""
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = x + dx, y + dy
            if game_map.in_bounds(nx, ny) and game_map.tiles[ny][nx].kind in {
                "plaza", "neon",
            }:
                return True
    return False


def test_authored_city_doors_front_a_route():
    """Every building entrance opens onto a purposeful route surface --
    not bare ground. Regression: indi_b's guild hall door sat in a
    pocket whose 'front walk' connected only through crop tiles."""
    for planet_id in _authored_city_ids():
        game_map = load_planet(planet_id)
        if game_map.city_layout_id in _NO_ROUTE_VOCABULARY:
            continue
        for label, record in game_map.city_buildings.items():
            ex, ey = record["entrance"]
            fronted = any(
                game_map.in_bounds(ex + dx, ey + dy)
                and game_map.tiles[ey + dy][ex + dx].kind in _ROUTE_KINDS
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
            )
            assert fronted, (
                f"{planet_id} {label}: entrance {(ex, ey)} fronts bare "
                "ground -- extend a road/sidewalk/pad to the door"
            )


def test_transit_stops_drop_you_near_something_interesting():
    """Every stop sits within a short walk of a destination: a building
    door, a service terminal, the player berth, or a landmark square."""
    for planet_id in _authored_city_ids():
        game_map = load_planet(planet_id)
        spec = find_planet_spec(planet_id)
        pois = [
            tuple(record["entrance"])
            for record in game_map.city_buildings.values()
            if record.get("entrance")
        ]
        pois += [
            (entity.pos.x, entity.pos.y) for entity in game_map.entities
            if entity.trade_terminal or entity.mech_terminal
            or entity.armory_terminal
        ]
        pois.append((spec.hangar_anchor.x, spec.hangar_anchor.y))
        for sid, meta in game_map.city_transit.items():
            sx, sy = meta["pos"]
            nearest = min(abs(sx - px) + abs(sy - py) for px, py in pois)
            limit = _STOP_DISTANCE_GRANDFATHER.get(
                (planet_id, sid), _STOP_BASE_REACH,
            )
            assert nearest <= limit or _near_landmark(game_map, sx, sy), (
                f"{planet_id} stop {sid!r} at {(sx, sy)} is {nearest} from "
                "any door/terminal/berth and beside no landmark -- move it "
                "near something worth visiting"
            )


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


# --- Lalande 21185 c: shipping-container maze ---------------------------


def test_lal_c_is_a_tight_container_maze():
    """Whisper uses the authored container-maze layout and full city systems."""
    game_map = load_planet("lal_c")
    assert game_map.city_layout_id == "lalc_container_maze"
    assert (game_map.width, game_map.height) == (100, 70)
    assert set(game_map.city_buildings) == {
        "spaceport", "bar", "merchants", "bounties",
    }
    assert len(game_map.city_transit) == 4
    assert sum(
        bool(getattr(entity, "city_npc_id", "")) for entity in game_map.entities
    ) == 8
    container_walls = sum(
        tile.kind == "city_building_wall" and tile.char in {"#", "="}
        for row in game_map.tiles for tile in row
    )
    assert container_walls >= 180
    apron = [
        tile for row in game_map.tiles for tile in row
        if tile.kind == "landing_pad"
    ]
    assert apron
    assert {tile.char for tile in apron} == {" "}


def test_lal_c_public_lanes_connect_every_service():
    """The narrow container lanes connect the landing apron to every door and stop."""
    game_map = load_planet("lal_c")
    spec = find_planet_spec("lal_c")
    reachable = _reachable(game_map, spec.hangar_anchor)
    for label, record in game_map.city_buildings.items():
        entrance = record["entrance"]
        assert entrance is not None, label
        x, y = entrance
        assert game_map.tiles[y][x].walkable, label
        assert entrance in reachable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id


def test_lal_c_containers_clear_public_routes_and_doors():
    """Container stacks never bury lanes, aprons, or building entrances."""
    game_map = load_planet("lal_c")
    public_kinds = {"road", "sidewalk", "landing_pad", "plaza"}
    for label, stamp in game_map.landmark_stamps.items():
        assert not {
            point for point in stamp["footprint"]
            if game_map.tiles[point[1]][point[0]].kind in public_kinds
        }, label
    for label, record in game_map.city_buildings.items():
        x, y = record["entrance"]
        assert any(
            game_map.in_bounds(x + dx, y + dy)
            and game_map.tiles[y + dy][x + dx].kind in public_kinds
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        ), label


def test_lal_c_transit_stops_are_off_lanes_and_on_door_side():
    """Each stop uses a small bay beside the lane and south of its door."""
    game_map = load_planet("lal_c")
    spec = find_planet_spec("lal_c")
    station_for = {
        "spaceport": "spaceport", "bar": "hush",
        "merchants": "ledger", "bounties": "bounties",
    }
    for building in spec.buildings:
        entrance = game_map.city_buildings[building.label]["entrance"]
        stop = game_map.city_transit[station_for[building.label]]["pos"]
        assert stop[1] > entrance[1], building.label
        if building.label != "spaceport":
            assert game_map.tiles[stop[1]][stop[0]].kind not in {
                "road", "sidewalk", "landing_pad",
            }, building.label
        assert any(
            game_map.tiles[stop[1] + dy][stop[0] + dx].kind == "sidewalk"
            for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
            if game_map.in_bounds(stop[0] + dx, stop[1] + dy)
        ), building.label
        assert abs(stop[0] - entrance[0]) <= 12, building.label


def test_lal_c_uses_complete_authored_exteriors_and_interiors():
    """All four Whisper facilities have one real door and a valid room."""
    game_map = load_planet("lal_c")
    for label, record in game_map.city_buildings.items():
        exterior = city_landmarks.load_city_landmark(f"lalc_{label}")
        assert {len(row) for row in exterior.tiles} == {exterior.width}, label
        assert sum(
            tile.kind == "city_building_door"
            for row in exterior.tiles for tile in row
        ) == 1, label
        interior = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert interior.spawn is not None, label
        assert any(
            tile.kind == "exit" for row in interior.game_map.tiles for tile in row
        ), label
        assert record["entrance"] == (
            game_map.landmark_stamps[f"lalc_{label}"]["entrance"]
        )


def test_lal_c_population_stays_clear_of_the_maze_architecture():
    """Ambient smugglers spawn on walkable lanes, never in stacks or stops."""
    game_map = load_planet("lal_c")
    reachable = _reachable(game_map, find_planet_spec("lal_c").hangar_anchor)
    building_cells = {
        point for stamp in game_map.landmark_stamps.values()
        for point in stamp["footprint"]
    }
    station_cells = {
        metadata["pos"] for metadata in game_map.city_transit.values()
    }
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        point = (entity.pos.x, entity.pos.y)
        assert point not in building_cells, entity.city_npc_id
        assert point not in station_cells, entity.city_npc_id
        assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
        assert point in reachable
        assert game_map.blocking_entity_at(
            entity.pos.x, entity.pos.y, exclude=entity,
        ) is None


def test_lal_c_maze_has_two_crossings_and_three_lane_bands():
    """The authored circulation reads as a maze with repeated container belts."""
    game_map = load_planet("lal_c")
    road_rows = {
        y for y, row in enumerate(game_map.tiles)
        if sum(tile.kind == "road" for tile in row) >= 60
    }
    road_columns = {
        x for x in range(game_map.width)
        if sum(game_map.tiles[y][x].kind == "road" for y in range(game_map.height)) >= 35
    }
    assert {26, 47, 65} <= road_rows
    assert {33, 69} <= road_columns


def test_lal_c_has_colorful_storage_containers_in_freight_yards():
    """Open vault pockets are filled with readable, varied container stacks."""
    game_map = load_planet("lal_c")
    containers = [
        tile for row in game_map.tiles for tile in row
        if tile.kind == "storage_container"
    ]
    assert len(containers) >= 180
    assert len({tile.fg for tile in containers}) >= 5
    assert len({tile.bg for tile in containers}) >= 5
    assert all(not tile.walkable for tile in containers)


def test_lal_c_storage_containers_clear_city_anchors():
    """Freight stacks do not consume routes, facilities, stops, or citizens."""
    game_map = load_planet("lal_c")
    public_kinds = {"road", "sidewalk", "landing_pad", "plaza"}
    assert all(
        tile.kind not in public_kinds
        for row in game_map.tiles for tile in row
        if tile.kind == "storage_container"
    )
    building_cells = {
        point for stamp in game_map.landmark_stamps.values()
        for point in stamp["footprint"]
    }
    station_cells = {
        metadata["pos"] for metadata in game_map.city_transit.values()
    }
    npc_cells = {
        (entity.pos.x, entity.pos.y)
        for entity in game_map.entities
        if getattr(entity, "city_npc_id", "")
    }
    blocked = building_cells | station_cells | npc_cells
    for y, row in enumerate(game_map.tiles):
        for x, tile in enumerate(row):
            if tile.kind == "storage_container":
                assert (x, y) not in blocked


def test_lal_c_bounty_office_has_clear_container_setback():
    """The warrant office keeps a visible buffer from freight stacks."""
    game_map = load_planet("lal_c")
    footprint = game_map.landmark_stamps["lalc_bounties"]["footprint"]
    container_cells = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "storage_container"
    }
    assert not any(
        (x + dx, y + dy) in container_cells
        for x, y in footprint
        for dx, dy in (
            (0, 0), (0, -1), (1, -1), (-1, -1),
            (0, 1), (1, 1), (-1, 1),
            (1, 0), (-1, 0),
        )
    )


# ---------------------------------------------------------------------
# Barnard c -- the Skimmer Deck (atmospheric helium-3 platform)
# ---------------------------------------------------------------------


def test_barnards_c_is_a_skimmer_deck():
    """Whisper-free deck: authored layout, two facilities, two stops."""
    game_map = load_planet("barnards_c")
    assert game_map.city_layout_id == "barnards_c_atmo_deck"
    assert (game_map.width, game_map.height) == (110, 72)
    assert set(game_map.city_buildings) == {"spaceport", "bar"}
    assert set(game_map.city_transit) == {"spaceport", "deep_freeze"}
    assert sum(
        bool(getattr(entity, "city_npc_id", "")) for entity in game_map.entities
    ) == 8


def test_barnards_c_two_stops_pair_the_port_and_the_bar():
    """Each stop sits south of its door, beside a sidewalk, and the two
    stops list only each other as destinations."""
    game_map = load_planet("barnards_c")
    spec = find_planet_spec("barnards_c")
    station_for = {"spaceport": "spaceport", "deep_freeze": "bar"}
    other = {"spaceport": "deep_freeze", "deep_freeze": "spaceport"}
    for sid, label in station_for.items():
        station = next(s for s in spec.transit_stations if s.id == sid)
        x, y = station.pos.x, station.pos.y
        assert game_map.tiles[y][x].kind == "transit_bay", sid
        assert all(
            game_map.tiles[y + dy][x + dx].walkable
            for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if game_map.in_bounds(x + dx, y + dy)
        ), sid
        assert station.destinations == (other[sid],), sid
        assert station.serves == f"barnards_c_{label}", sid


def test_barnards_c_public_lanes_connect_every_service():
    """The spine and connectors reach both doors and both stops from the berth."""
    game_map = load_planet("barnards_c")
    spec = find_planet_spec("barnards_c")
    reachable = _reachable(game_map, spec.hangar_anchor)
    for label, record in game_map.city_buildings.items():
        entrance = record["entrance"]
        assert entrance is not None, label
        assert game_map.tiles[entrance[1]][entrance[0]].walkable, label
        assert entrance in reachable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id


def test_barnards_c_sheared_corner_reads_as_storm_void():
    """The southwest corner is cut away in steps: void inside the cut,
    rim plating on surviving deck, apron smooth up to its rimmed edge."""
    game_map = load_planet("barnards_c")
    for x, y in ((10, 60), (20, 66), (35, 63), (45, 68), (2, 68)):
        tile = game_map.tiles[y][x]
        assert tile.kind == "storm_void" and not tile.walkable, (x, y)
    for x, y in ((31, 57), (41, 62), (51, 66), (15, 54)):
        assert game_map.tiles[y][x].kind == "storm_rim", (x, y)
    for y in range(41, 54):
        for x in range(10, 26):
            tile = game_map.tiles[y][x]
            assert tile.kind == "landing_pad" and tile.char == " ", (x, y)


def test_barnards_c_toe_line_never_bridges_the_void():
    """The painted hazard line skips void and rim: the inlet mouth and
    the sheared corner stay impassable all the way to the map edge."""
    game_map = load_planet("barnards_c")
    for row in game_map.tiles:
        for tile in row:
            if tile.kind == "hazard_toe":
                assert tile.walkable
    for x, y in ((70, 69), (10, 69)):
        assert game_map.tiles[y][x].kind == "storm_void", (x, y)
    rim = game_map.tiles[60][69]
    assert rim.kind == "storm_rim" and not rim.walkable
    assert game_map.tiles[69][95].kind == "hazard_toe"


def test_barnards_c_industrial_dressing_is_expressive():
    """Tank farm, pipeline network, manifolds, and skimmer cradles all
    present -- the deck reads as a working gas mine, not a town grid."""
    game_map = load_planet("barnards_c")
    kinds = [
        tile.kind for row in game_map.tiles for tile in row
    ]
    assert kinds.count("he3_tank") >= 200
    assert kinds.count("he3_manifold") == 8
    assert kinds.count("skimmer_cradle") == 12
    pipes = [
        tile for row in game_map.tiles for tile in row
        if tile.kind == "he3_pipe"
    ]
    assert len(pipes) >= 60
    assert all(pipe.walkable for pipe in pipes)
    # Cradle frames stand at the inlet mouth with deck-side gates open,
    # and no frame hangs over the sheared void below.
    assert game_map.tiles[61][47].kind == "gantry_truss"
    assert game_map.tiles[61][88].kind == "gantry_truss"
    assert game_map.tiles[62][47].walkable
    assert game_map.tiles[62][88].walkable
    assert game_map.tiles[62][48].kind == "skimmer_cradle"
    assert game_map.tiles[65][48].kind == "storm_rim"


def test_barnards_c_interiors_load_with_spawn_and_exit():
    """Both skimmer-deck facilities have authored interiors with P + exit."""
    game_map = load_planet("barnards_c")
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, f"{label} interior has no spawn"
        assert any(
            tile.kind == "exit" for row in asset.game_map.tiles for tile in row
        ), f"{label} interior has no exit"


def test_barnards_c_interior_spawns_sit_inside_the_door():
    """Entering a building drops you just inside the entrance, not
    mid-floor: the P spawn sits directly above the exit marker, and the
    exit backs onto the door-side (south) wall. Regression: both
    skimmer-deck interiors spawned the player in the middle of the
    room, which no doorway works like."""
    game_map = load_planet("barnards_c")
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        interior = asset.game_map
        exits = [
            (x, y)
            for y, row in enumerate(interior.tiles)
            for x, tile in enumerate(row)
            if tile.kind == "exit"
        ]
        assert len(exits) == 1, f"{label} interior needs exactly one exit"
        ex, ey = exits[0]
        spawn = asset.spawn
        assert (spawn.x, spawn.y) == (ex, ey - 1), (
            f"{label}: spawn {(spawn.x, spawn.y)} must sit directly inside "
            f"the exit at {(ex, ey)}"
        )
        bottom_wall = interior.tiles[ey + 1][ex]
        assert bottom_wall.kind == "city_building_wall", (
            f"{label}: exit must back onto the door-side wall"
        )


def test_barnards_c_population_walks_the_deck():
    """Every ambient crew member anchors on a walkable, unblocked cell."""
    game_map = load_planet("barnards_c")
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        tile = game_map.tiles[entity.pos.y][entity.pos.x]
        assert tile.walkable, f"{entity.city_npc_id} on a blocked tile"
        assert game_map.blocking_entity_at(
            entity.pos.x, entity.pos.y, exclude=entity,
        ) is None


def test_every_transit_station_destinations_is_a_tuple_of_sibling_ids():
    """A station's destinations must be a tuple of sibling station ids.

    Regression: scripted station deletions left ``destinations=("bar")``
    — a bare string, not a 1-tuple — so the transit router iterated the
    string's characters and every bump said "no transit routes".
    """
    for spec in list_planet_specs():
        ids = {station.id for station in (spec.transit_stations or ())}
        for station in spec.transit_stations or ():
            assert isinstance(station.destinations, tuple), (
                f"{spec.id}:{station.id} destinations is "
                f"{type(station.destinations).__name__}, not tuple"
            )
            assert set(station.destinations) <= ids - {station.id}, (
                f"{spec.id}:{station.id} destinations "
                f"{station.destinations} reference non-sibling ids"
            )
