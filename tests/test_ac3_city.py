"""Regression coverage for AC-III's authored Ring Refinery floating platform."""
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


def test_ac3_is_the_authored_ring_refinery():
    game_map = load_planet("ac_planet_3")
    assert game_map.city_layout_id == "ac3_ring_refinery"
    assert (game_map.width, game_map.height) == (100, 70)
    assert len(game_map.landmark_stamps) == 2
    # Ring particle bands fill the map outside the platform.
    assert any(tile.kind == "ring_dust" for row in game_map.tiles for tile in row)
    # The platform has an edge silhouette, not a wall.
    assert any(tile.kind == "platform_edge" for row in game_map.tiles for tile in row)
    # A collector tower at the industrial core.
    assert any(tile.kind == "collector_tower" for row in game_map.tiles for tile in row)
    # Fuel tank farm on the south deck.
    assert any(
        tile.char == "o" and tile.kind == "city_building_wall"
        for row in game_map.tiles for tile in row
    )
    # Fuel pipe runs.
    assert any(tile.kind == "pipe" for row in game_map.tiles for tile in row)
    # Cooling fins on the east edge.
    assert any(tile.kind == "cooling_fin" for row in game_map.tiles for tile in row)
    # The concourse plaza carries the refinery beacon.
    assert game_map.tiles[34][50].kind == "beacon"
    # The Concourse spans the platform.
    strip = sum(
        tile.kind == "road" for row in game_map.tiles for tile in row
    )
    assert strip > 80
    # Flickering neon warning signs.
    assert any(tile.kind == "neon" for row in game_map.tiles for tile in row)


def test_ac3_buildings_transit_and_npcs_are_reachable():
    game_map = load_planet("ac_planet_3")
    spec = find_planet_spec("ac_planet_3")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {"spaceport", "concourse", "bar"}
    assert len(spec.city_npc_population) == 8
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


def test_ac3_landing_apron_is_smooth_and_showroom_is_clear():
    game_map = load_planet("ac_planet_3")
    spec = find_planet_spec("ac_planet_3")
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


def test_ac3_interiors_follow_authored_conventions():
    game_map = load_planet("ac_planet_3")
    assert set(game_map.city_buildings) == {"spaceport", "bar"}
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


def test_ac3_seeds_amber_red_lighting():
    game_map = load_planet("ac_planet_3")
    assert game_map.light_sources
    assert game_map.light_grid is not None
    kinds = {game_map.tiles[source.y][source.x].kind for source in game_map.light_sources}
    assert "neon" in kinds
    assert "beacon" in kinds
    lit = [cell for row in game_map.light_grid for cell in row if cell != (0, 0, 0)]
    assert lit


def test_ac3_has_no_voids_or_unreachable_walkable_cells():
    game_map = load_planet("ac_planet_3")
    spec = find_planet_spec("ac_planet_3")
    assert not any(tile.kind == "void" for row in game_map.tiles for tile in row)
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert all(
        not tile.walkable or (x, y) in reachable
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
    )
