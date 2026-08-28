"""Regression coverage for Vega b's authored Mirror Fields city."""

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


def test_vega_b_is_the_authored_mirror_fields_station():
    game_map = load_planet("vega_b")
    assert game_map.city_layout_id == "vega_mirror_fields"
    assert (game_map.width, game_map.height) == (140, 90)
    assert len(game_map.landmark_stamps) == 3
    assert sum(tile.kind == "solar_mirror" for row in game_map.tiles for tile in row) > 500
    assert sum(tile.kind == "cooling_works" for row in game_map.tiles for tile in row) == 3


def test_vega_b_buildings_transit_and_npcs_are_reachable():
    game_map = load_planet("vega_b")
    spec = find_planet_spec("vega_b")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {"spaceport", "parallax", "exchange", "cooling_works"}
    assert len(spec.city_npc_population) == 6
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


def test_vega_b_authored_interiors_have_spawn_and_exit():
    game_map = load_planet("vega_b")
    for label, record in game_map.city_buildings.items():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        assert asset.spawn is not None, label
        assert any(tile.kind == "exit" for row in asset.game_map.tiles for tile in row), label
