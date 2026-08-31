"""Regression coverage for Blockade South's Quarantine Cordon station."""
from __future__ import annotations

from collections import deque

from src.spacehack.data.planets import find_planet_spec, load_planet


def _reachable(game_map, start):
    origin = (start.x, start.y)
    seen = {origin}
    queue = deque([origin])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if point in seen or not game_map.in_bounds(*point):
                continue
            if game_map.is_walkable(*point):
                seen.add(point)
                queue.append(point)
    return seen


def test_blockade_south_is_distinct_authored_station():
    game_map = load_planet("blockade_south")
    assert game_map.city_layout_id == "blockade_south_quarantine"
    assert (game_map.width, game_map.height) == (140, 90)
    assert game_map.city_transit["spaceport"]["name"] == "Spaceport"
    assert "inspection" not in game_map.city_transit
    assert game_map.city_transit["quarantine"]["pos"] == (70, 37)
    assert all(
        game_map.tiles[y][x].kind == "transit_bay"
        for y in range(36, 39)
        for x in range(69, 72)
    )
    assert len(game_map.landmark_stamps) == 3
    assert any(tile.kind == "station_bulkhead" for row in game_map.tiles for tile in row)
    assert any(tile.kind == "quarantine" for row in game_map.tiles for tile in row)
    assert any(tile.kind == "beacon" for row in game_map.tiles for tile in row)


def test_blockade_south_has_three_wide_connected_road_network():
    game_map = load_planet("blockade_south")
    roads = {(x, y) for y, row in enumerate(game_map.tiles) for x, tile in enumerate(row) if tile.kind == "road"}
    assert len(roads) >= 300
    assert all(game_map.tiles[y][x].walkable for x, y in roads)
    assert sum(game_map.tiles[42][x].char == "▓" for x in range(2, 138)) >= 120
    for x in range(2, 138):
        assert all(game_map.tiles[y][x].kind == "road" for y in (42, 43, 44))
    for y in range(2, 24):
        assert all(game_map.tiles[y][x].kind == "road" for x in (68, 69, 70))
    for y in (44, 45, 58, 59, 60):
        assert all(game_map.tiles[y][x].kind == "road" for x in (68, 69, 70))
    for x in range(2, 79):
        assert game_map.tiles[59][x].kind == "road"
    for x in range(130, 138):
        assert game_map.tiles[59][x].kind == "road"
    for x in range(137, 129, -1):
        assert game_map.tiles[59][x].kind == "road"
    for x in range(78, 75, -1):
        assert game_map.tiles[59][x].kind == "road"
    for x in range(36, 82):
        assert all(game_map.tiles[y][x].kind == "road" for y in (66, 67, 68))
    for x in range(133, 138):
        assert all(game_map.tiles[y][x].kind == "road" for y in (66, 67, 68))
    for x in (36, 37, 38, 76, 77, 78):
        assert sum(game_map.tiles[y][x].kind == "road" for y in range(45, 65)) >= 15
    for x in (68, 69, 70):
        assert sum(game_map.tiles[y][x].kind == "road" for y in range(2, 88)) >= 15
    assert not any(tile.kind == "sidewalk" for row in game_map.tiles for tile in row)
    protected = {"city_building_wall", "city_building_roof", "city_building_door", "landing_pad", "plaza", "transit_bay", "quarantine", "station_bulkhead"}
    for y, row in enumerate(game_map.tiles):
        for x, tile in enumerate(row):
            if tile.kind == "road":
                assert not any(
                    game_map.tiles[yy][xx].kind in protected - {"station_bulkhead"}
                    for yy in range(max(0, y - 1), min(game_map.height, y + 2))
                    for xx in range(max(0, x - 1), min(game_map.width, x + 2))
                )
    assert sum(tile.kind == "plaza" for row in game_map.tiles for tile in row) > 0
    assert sum(tile.kind == "landing_pad" for row in game_map.tiles for tile in row) > 0


def test_blockade_south_routes_and_stops_are_reachable():
    game_map = load_planet("blockade_south")
    spec = find_planet_spec("blockade_south")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {
        "spaceport", "quarantine", "militia", "bounties",
    }
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    assert game_map.city_transit["militia"]["pos"] == (116, 79)
    assert game_map.city_transit["bounties"]["pos"] == (21, 79)
    for label, record in game_map.city_buildings.items():
        x, y = record["entrance"]
        assert game_map.tiles[y][x].walkable, label
        assert (x, y) in reachable, label
    assert len(spec.city_npc_population) == 8
    showroom = [entity for entity in game_map.entities if entity.ship_id]
    assert showroom
    assert all(15 <= entity.pos.y <= 25 for entity in showroom)
    terminals = [entity for entity in game_map.entities if entity.trade_terminal or entity.mech_terminal or entity.armory_terminal]
    assert all((entity.pos.x, entity.pos.y) not in {(station.pos.x, station.pos.y) for station in spec.transit_stations} for entity in terminals)
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
            assert (entity.pos.x, entity.pos.y) in reachable


def test_blockade_south_seeds_atmospheric_lighting():
    game_map = load_planet("blockade_south")
    assert game_map.light_sources
    assert game_map.light_grid is not None
    kinds = {game_map.tiles[source.y][source.x].kind for source in game_map.light_sources}
    assert "neon" in kinds
    assert "beacon" in kinds
    lit = [cell for row in game_map.light_grid for cell in row if cell != (0, 0, 0)]
    assert lit


def test_blockade_south_has_no_voids_or_unreachable_walkable_cells():
    game_map = load_planet("blockade_south")
    spec = find_planet_spec("blockade_south")
    assert not any(tile.kind == "void" for row in game_map.tiles for tile in row)
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert all(
        not tile.walkable or (x, y) in reachable
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
    )
