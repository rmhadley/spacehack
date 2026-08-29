"""Regression coverage for Vega b's authored Beacon floating station."""

from __future__ import annotations

from collections import deque

from src.spacehack import city_landmarks
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


def test_vega_b_is_the_authored_beacon_station():
    game_map = load_planet("vega_b")
    assert game_map.city_layout_id == "vega_beacon_station"
    assert (game_map.width, game_map.height) == (140, 90)
    assert len(game_map.landmark_stamps) == 4
    # The station floats in the cloud deck: most of the map is open
    # atmosphere, and the platform is the walkable cross.
    cloud = sum(
        tile.kind == "cloud_deck" for row in game_map.tiles for tile in row
    )
    assert cloud > 4000
    assert all(
        not tile.walkable
        for row in game_map.tiles for tile in row
        if tile.kind == "cloud_deck"
    )
    # The reflector fan is the signature: seven mirror rays converge on
    # the collector tower.
    mirrors = sum(
        tile.kind == "solar_mirror" for row in game_map.tiles for tile in row
    )
    assert mirrors > 150
    assert sum(
        tile.kind == "collector_tower" for row in game_map.tiles for tile in row
    ) == 25
    # The Focus hub carries the navigation beacon.
    assert game_map.tiles[45][70].kind == "beacon"
    assert game_map.tiles[45][70].char == "!"


def test_vega_b_buildings_transit_and_npcs_are_reachable():
    game_map = load_planet("vega_b")
    spec = find_planet_spec("vega_b")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {
        "spaceport", "focus", "veil", "exchange", "reflectors",
    }
    assert len(spec.city_npc_population) == 10
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


def test_vega_b_landing_apron_is_smooth_and_showroom_is_clear():
    game_map = load_planet("vega_b")
    spec = find_planet_spec("vega_b")
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


def test_vega_b_reflector_field_keeps_walkable_maintenance_lanes():
    """The lanes between the mirror rays are the field's maintenance
    access: every lane cell is walkable and reaches the hub."""
    game_map = load_planet("vega_b")
    spec = find_planet_spec("vega_b")
    reachable = _reachable(game_map, spec.hangar_anchor)
    mirrors = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "solar_mirror"
    }
    # The reflector stop sits inside a lane between rays.
    stop = game_map.city_transit["reflectors"]["pos"]
    assert stop in reachable
    # A sample of the deck between the rays stays walkable and connected.
    for point in ((95, 39), (108, 50), (100, 46), (115, 48), (100, 43), (95, 43)):
        assert game_map.tiles[point[1]][point[0]].walkable, point
        assert point in reachable, point
    assert all(
        game_map.tiles[y][x].walkable for x, y in mirrors
    )


def test_vega_b_authored_interiors_have_spawn_and_exit():
    game_map = load_planet("vega_b")
    assert set(game_map.city_buildings) == {
        "spaceport", "bar", "merchants", "depot",
    }
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, label
        assert any(tile.kind == "exit" for row in asset.game_map.tiles for tile in row), label