"""Regression coverage for Procyon b's authored Crossroads waypoint."""

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


def test_proc_b_is_the_authored_crossroads_waypoint():
    game_map = load_planet("proc_planet_1")
    assert game_map.city_layout_id == "proc_b_crossroads"
    assert (game_map.width, game_map.height) == (120, 80)
    assert len(game_map.landmark_stamps) == 3
    # The main strip spans the town (its west end becomes the apron).
    strip = sum(
        tile.kind == "road" for row in game_map.tiles for tile in row
    )
    assert strip > 200
    # The dry arroyo cuts the south-west corner.
    assert any(tile.kind == "arroyo" for row in game_map.tiles for tile in row)
    # The crossroads plaza carries the nav beacon.
    assert game_map.tiles[43][85].kind == "beacon"
    # Shanty shacks line the strip's north side.
    shacks = sum(
        tile.char == '"' for row in game_map.tiles for tile in row
    )
    assert shacks >= 4


def test_proc_b_buildings_transit_and_npcs_are_reachable():
    game_map = load_planet("proc_planet_1")
    spec = find_planet_spec("proc_planet_1")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {"spaceport", "crossroads", "depot"}
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


def test_proc_b_landing_apron_is_smooth_and_showroom_is_clear():
    game_map = load_planet("proc_planet_1")
    spec = find_planet_spec("proc_planet_1")
    showroom = [entity for entity in game_map.entities if entity.ship_id]
    assert len(showroom) == 3
    assert all(entity.pos.y < spec.hangar_anchor.y for entity in showroom)
    assert all(
        game_map.tiles[entity.pos.y][entity.pos.x].kind == "landing_pad"
        for entity in showroom
    )
    assert {
        tile.char for row in game_map.tiles for tile in row
        if tile.kind == "landing_pad"
    } == {" "}


def test_proc_b_interiors_follow_authored_conventions():
    """Every Procyon b interior uses the shared authored-room conventions:
    spawn and exit adjacent at the door side, furnished rooms, and each
    service NPC seats on a walkable, spawn-reachable cell."""
    game_map = load_planet("proc_planet_1")
    assert set(game_map.city_buildings) == {"spaceport", "bar", "depot"}
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


def test_proc_b_crossroads_beacon_and_shady_element():
    """The waypoint keeps its flavor: a nav beacon at the crossroads and
    one hostile pirate element near the cantina."""
    game_map = load_planet("proc_planet_1")
    assert sum(
        tile.kind == "beacon" for row in game_map.tiles for tile in row
    ) == 1
    from src.spacehack.data.city_npcs import PROC_B_POPULATION
    ids = {npc.id for npc in PROC_B_POPULATION}
    assert "procb_shady" in ids
    shady = next(npc for npc in PROC_B_POPULATION if npc.id == "procb_shady")
    assert shady.npc_char_id == "pirate_raider"