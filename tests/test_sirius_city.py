"""Regression coverage for Sirius Station's authored Binary Eye observatory."""
from __future__ import annotations

from collections import deque

from src.spacehack import city_interiors, city_landmarks
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


def test_sirius_is_the_authored_binary_eye():
    game_map = load_planet("sirius_station")
    assert game_map.city_layout_id == "sirius_binary_eye"
    assert (game_map.width, game_map.height) == (100, 70)
    assert len(game_map.landmark_stamps) == 2
    # The Solar Promenade spans the deck.
    strip = sum(
        tile.kind == "road" for row in game_map.tiles for tile in row
    )
    assert strip > 100
    # Solar collector arrays on the south hull.
    assert any(tile.kind == "solar_collector" for row in game_map.tiles for tile in row)
    # Observation dome on the north hull.
    assert any(tile.kind == "observation_dome" for row in game_map.tiles for tile in row)
    # The observation terrace carries the station beacon.
    assert game_map.tiles[25][54].kind == "beacon"
    # Golden solar lamps.
    assert any(tile.kind == "neon" for row in game_map.tiles for tile in row)


def test_sirius_buildings_transit_and_npcs_are_reachable():
    game_map = load_planet("sirius_station")
    spec = find_planet_spec("sirius_station")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {"spaceport", "terrace", "lab"}
    assert len(spec.city_npc_population) == 7
    for label, record in game_map.city_buildings.items():
        assert record["entrance"] in reachable, label
        x, y = record["entrance"]
        assert game_map.tiles[y][x].walkable, label
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    for entity in game_map.entities:
        if getattr(entity, "city_npc_id", ""):
            assert game_map.tiles[entity.pos.y][entity.pos.x].walkable
            assert (entity.pos.x, entity.pos.y) in reachable


def test_sirius_landing_apron_is_smooth_and_showroom_is_clear():
    game_map = load_planet("sirius_station")
    spec = find_planet_spec("sirius_station")
    showroom = [entity for entity in game_map.entities if entity.ship_id]
    assert len(showroom) == 2
    assert all(entity.pos.y < spec.hangar_anchor.y for entity in showroom)
    assert all(
        game_map.tiles[entity.pos.y][entity.pos.x].kind == "landing_pad"
        for entity in showroom
    )
    assert {
        tile.char for row in game_map.tiles for tile in row
        if tile.kind == "landing_pad"
    } == {" "}


def test_sirius_interiors_follow_authored_conventions():
    game_map = load_planet("sirius_station")
    assert set(game_map.city_buildings) == {"spaceport", "lab"}
    furniture_kinds = {"table", "bar_body", "drink", "city_ornament"}
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        interior = asset.game_map
        spawn = asset.spawn
        assert spawn is not None, label
        exits = [
            (x, y)
            for y, row in enumerate(interior.tiles)
            for x, tile in enumerate(row)
            if tile.kind == "exit"
        ]
        assert len(exits) == 1, label
        assert exits[0] == (spawn.x, spawn.y + 1), label
        assert any(
            tile.kind in furniture_kinds
            for row in interior.tiles for tile in row
        ), label
        if not record.get("npc_id"):
            continue
        seat = city_interiors._first_interior_npc(interior, spawn)
        assert seat is not None, label
        assert interior.tiles[seat.y][seat.x].walkable, label
        reachable = _reachable(interior, spawn)
        assert (seat.x, seat.y) in reachable, label


def test_sirius_seeds_golden_lighting():
    game_map = load_planet("sirius_station")
    assert game_map.light_sources
    assert game_map.light_grid is not None
    kinds = {game_map.tiles[source.y][source.x].kind for source in game_map.light_sources}
    assert "neon" in kinds
    assert "beacon" in kinds
    lit = [cell for row in game_map.light_grid for cell in row if cell != (0, 0, 0)]
    assert lit


def test_sirius_has_no_voids_or_unreachable_walkable_cells():
    game_map = load_planet("sirius_station")
    spec = find_planet_spec("sirius_station")
    assert not any(tile.kind == "void" for row in game_map.tiles for tile in row)
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert all(
        not tile.walkable or (x, y) in reachable
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
    )
