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


def test_blockade_south_has_connected_civil_engineering_network():
    game_map = load_planet("blockade_south")
    roads = {(x, y) for y, row in enumerate(game_map.tiles) for x, tile in enumerate(row) if tile.kind == "road"}
    sidewalks = {(x, y) for y, row in enumerate(game_map.tiles) for x, tile in enumerate(row) if tile.kind == "sidewalk"}
    assert len(roads) >= 250
    assert len(sidewalks) >= 100
    assert game_map.tiles[48][40].char == "═"
    assert any(tile.kind == "road" and tile.char == "║" for row in game_map.tiles for tile in row)
    assert game_map.tiles[48][40].bg != game_map.tiles[46][40].bg
    for y in (47, 48, 49):
        assert game_map.tiles[y][50].kind == "road"
    assert sum(game_map.tiles[67][x].kind == "road" for x in range(24, 116)) >= 60
    for y in range(1, game_map.height - 1):
        for x in range(1, game_map.width - 1):
            if game_map.tiles[y][x].kind == "road":
                assert sum(game_map.tiles[y + dy][x + dx].kind == "road" for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))) >= 1
    seen = _reachable(game_map, find_planet_spec("blockade_south").hangar_anchor)
    assert roads <= seen
    assert any(abs(x - 20) <= 2 and 25 <= y <= 27 for x, y in sidewalks)
    assert any(abs(x - 21) <= 2 and 65 <= y <= 69 for x, y in sidewalks)
    assert any(abs(x - 116) <= 2 and 65 <= y <= 69 for x, y in sidewalks)
    assert any(abs(x - 70) <= 3 and 34 <= y <= 40 for x, y in sidewalks)


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
