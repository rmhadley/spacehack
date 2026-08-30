"""Regression coverage for Procyon c's authored Ice Campus."""

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


def test_proc_c_is_the_authored_ice_campus():
    game_map = load_planet("proc_planet_2")
    assert game_map.city_layout_id == "proc_c_ice_campus"
    assert (game_map.width, game_map.height) == (140, 100)
    assert len(game_map.landmark_stamps) == 4
    # Frozen channel cuts the campus.
    assert any(tile.kind == "ice_channel" for row in game_map.tiles for tile in row)
    # The bridge carries the main route across the channel.
    assert any(tile.kind == "city_bridge" for row in game_map.tiles for tile in row)
    # Campus quad carries the beacon.
    assert game_map.tiles[50][75].kind == "beacon"
    # Sastrugi texture the open ice.
    assert any(tile.kind == "sastrugi" for row in game_map.tiles for tile in row)


def test_proc_c_cave_mouth_is_the_east_landmark():
    game_map = load_planet("proc_planet_2")
    # Marker stands in the mouth center.
    mark = game_map.tiles[27][128]
    assert mark.kind == "cave_marker"
    # Dark ring walls surround it; the mouth floor is walkable.
    assert any(tile.kind == "cave_ice_wall" for row in game_map.tiles for tile in row)
    mouth = sum(
        tile.kind == "cave_mouth" for row in game_map.tiles for tile in row
    )
    assert mouth >= 20
    # The approach corridor from the west is open (marker reachable below).


def test_proc_c_buildings_transit_and_npcs_are_reachable():
    game_map = load_planet("proc_planet_2")
    spec = find_planet_spec("proc_planet_2")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {
        "spaceport", "quad", "lab", "mess", "depot",
    }
    # All-to-all network: every stop lists every other stop.
    assert all(
        set(metadata["destinations"]) == set(game_map.city_transit) - {station_id}
        for station_id, metadata in game_map.city_transit.items()
    )
    assert len(spec.city_npc_population) == 9
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
    # The cave mouth is reachable from the hangar (marker itself is a
    # non-walkable signpost; the walkable mouth floor beside it must be).
    assert any((x, 27) in reachable for x in range(125, 132)), "cave mouth"


def test_proc_c_map_has_no_wall_holes_or_dead_ice_pockets():
    """The authored exteriors must close every wall row (no void gaps)
    and every walkable cell must be reachable from the hangar (no
    sealed pockets between the cave ring, crevasses, or building
    walls)."""
    game_map = load_planet("proc_planet_2")
    spec = find_planet_spec("proc_planet_2")
    assert not any(
        tile.kind == "void"
        for row in game_map.tiles for tile in row
    ), "ragged layout row left a void wall gap"
    reachable = _reachable(game_map, spec.hangar_anchor)
    pockets = [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.walkable and (x, y) not in reachable
    ]
    assert not pockets, f"walkable cells sealed from the hangar: {pockets}"


def test_proc_c_circulation_is_planned():
    """Civil-engineering regression: one connected road network, the
    bridge sealing the channel where the spine crosses it, and every
    transit stop standing on charted surface."""
    game_map = load_planet("proc_planet_2")
    road_kinds = {"road", "road_ns", "road_ew", "road_surface", "city_bridge"}
    planned = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind in road_kinds
    }
    assert len(planned) > 500, "the campus road network is too small"
    # One connected component: no planned band stranded off the network.
    start = next(iter(planned))
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if point in seen or point not in planned:
                continue
            seen.add(point)
            queue.append(point)
    assert seen == planned, f"road bands stranded: {planned - seen}"
    # The bridge seals the crossing: no channel may cut the spine corridor.
    assert not any(
        game_map.tiles[y][x].kind == "ice_channel"
        for y in range(70, 77)
        for x in range(79, 84)
    ), "the bridge crossing leaves channel on the road corridor"
    # Every transit stop stands on charted surface (road, plaza, pad, bay).
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        kind = game_map.tiles[y][x].kind
        assert kind in {
            "road", "road_ns", "road_ew", "road_surface", "plaza",
            "landing_pad", "transit_bay", "city_bridge",
        }, f"{station_id} stop floats on {kind}"


def test_proc_c_dungeon_params_preserved():
    """The lab-chain delve site must survive the city rebuild byte-identical."""
    spec = find_planet_spec("proc_planet_2")
    dp = spec.dungeon_params
    assert spec.explorable_site_name == "caves"
    assert (dp.width, dp.height) == (80, 60)
    assert dp.monster_pool == ("ice_worm", "frost_spitter")
    assert dp.monster_density == 1.6
    assert dp.cache_guardian_pool == ("ice_worm",)
    assert dp.cache_guardian_count == 2
    assert dp.tile_wall.kind == "dungeon_wall"
    assert dp.tile_floor.fg == (200, 220, 245)


def test_proc_c_interiors_follow_authored_conventions():
    """Every Procyon c interior uses the shared authored-room conventions:
    spawn and exit adjacent at the door side, furnished rooms, and each
    service NPC seats on a walkable, spawn-reachable cell."""
    game_map = load_planet("proc_planet_2")
    assert set(game_map.city_buildings) == {"spaceport", "lab", "mess", "depot"}
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
