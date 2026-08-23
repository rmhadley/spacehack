"""Phase 1 regression tests for the expanded Earth city."""

from __future__ import annotations

from collections import deque

from src.spacehack import city_landmarks, earth_city, world
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


def test_earth_city_uses_expanded_dimensions_and_river_coast_layout():
    game_map = load_planet("earth")

    assert (game_map.width, game_map.height) == (160, 100)
    assert len(getattr(game_map, "water_cells", ())) > 2_000
    assert len(getattr(game_map, "bridge_crossings", ())) == 3
    assert any(tile.kind == "city_water" for row in game_map.tiles for tile in row)
    assert any(tile.kind == "city_bridge" for row in game_map.tiles for tile in row)
    assert all(
        not game_map.tiles[y][x].walkable
        for x, y in game_map.water_cells
    )


def test_earth_city_preserves_core_service_entities():
    game_map = load_planet("earth")

    # Service NPCs live inside their buildings now — none stand on the
    # street; entering a room is required to talk (see city interiors tests).
    assert not any(entity.npc_id for entity in game_map.entities)
    assert sum(entity.trade_terminal for entity in game_map.entities) == 1
    assert sum(entity.mech_terminal for entity in game_map.entities) == 1
    assert sum(entity.armory_terminal for entity in game_map.entities) == 1
    assert {entity.ship_id for entity in game_map.entities if entity.ship_id} == {
        "scout", "hauler",
    }


def test_earth_city_landmark_assets_have_persistable_origins_and_entrances():
    game_map = load_planet("earth")

    stamps = game_map.landmark_stamps
    assert set(stamps) == {
        "earth_city_spaceport", "earth_city_bar", "earth_city_bounties",
        "earth_city_merchants", "earth_city_militia", "earth_city_plaza",
    }
    for layout_id, stamp in stamps.items():
        assert stamp["origin"] in {
            (12, 12), (112, 10), (120, 58), (12, 62), (54, 70), (70, 52),
        }
        assert stamp["footprint"]
        if layout_id != "earth_city_plaza":
            assert stamp["entrance"] is not None


def test_earth_city_core_buildings_are_reachable_from_landing_pad():
    game_map = load_planet("earth")
    reachable = _reachable(game_map, find_planet_spec("earth").hangar_anchor)

    for entity in game_map.entities:
        if entity.trade_terminal or entity.mech_terminal or entity.armory_terminal:
            assert (entity.pos.x, entity.pos.y) in reachable
    # Every functional building's door is a walkable street entry point.
    for record in game_map.city_buildings.values():
        assert record["entrance"] is not None
        assert (record["entrance"][0], record["entrance"][1]) in reachable


def test_earth_city_bridges_span_the_river_and_connect_to_roads():
    game_map = load_planet("earth")

    for center_x, _center_y, _half_height in game_map.bridge_crossings:
        bridge_rows = [
            y for y in range(1, game_map.height - 1)
            if game_map.tiles[y][center_x].kind == "city_bridge"
        ]
        assert bridge_rows
        assert all(
            game_map.tiles[y][center_x - 1].kind == "city_bridge"
            and game_map.tiles[y][center_x + 1].kind == "city_bridge"
            for y in bridge_rows
        )
        assert game_map.tiles[min(bridge_rows) - 1][center_x].kind == "road"
        assert game_map.tiles[max(bridge_rows) + 1][center_x].kind == "road"


def test_earth_city_roads_do_not_replace_river_cells():
    game_map = load_planet("earth")

    assert not any(
        tile.kind == "road" and (x, y) in earth_city.RIVER_CELLS
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
    )


def test_earth_city_roads_stop_at_shore_before_the_river():
    game_map = load_planet("earth")

    assert not any(
        tile.kind == "road"
        and any(
            (x + dx, y + dy) in earth_city.RIVER_CELLS
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        )
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
    )


def test_earth_city_roads_are_not_sliced_diagonally_by_the_river():
    """Roads may only meet the river diagonally beside a bridge crossing.

    A road running into the river's diagonal bank leaves a staircase of
    shore tiles that reads as the water eating the pavement, so road ends
    must be axis-aligned against the bank rather than cut on the diagonal.
    """
    game_map = load_planet("earth")

    for y, row in enumerate(game_map.tiles):
        for x, tile in enumerate(row):
            if tile.kind not in {"road", "road_ns", "road_ew"}:
                continue
            touches_river_diagonally = any(
                (x + dx, y + dy) in earth_city.RIVER_CELLS
                for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1))
            )
            if not touches_river_diagonally:
                continue
            beside_bridge = any(
                game_map.tiles[y + dy][x + dx].kind == "city_bridge"
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
            )
            assert beside_bridge, (
                f"road cut diagonally into the river at ({x}, {y})"
            )


def test_earth_city_building_exteriors_do_not_show_their_interiors():
    """Solid building roofs: no interior floor is visible from the street."""
    game_map = load_planet("earth")

    assert not any(
        tile.kind == "city_building_floor"
        for row in game_map.tiles
        for tile in row
    )


def test_earth_city_buildings_never_overlap_roads():
    """Neither authored nor procedural buildings cover the road grid."""
    game_map = load_planet("earth")
    # The landing pad intentionally overpaves part of the west feeder road
    # and roads end at the coastal shore bank; only building tiles are
    # forbidden on the circulation grid.
    allowed = {"road", "city_bridge", "landing_pad", "city_shore"}
    road_cells: set[tuple[int, int]] = set()
    for y in range(3, 97):
        for x in (48, 49, 50, 108, 109, 110):
            road_cells.add((x, y))
    for x in range(3, 143):
        for y in (49, 50, 51, 78, 79, 80):
            road_cells.add((x, y))
    for x in range(24, 49):
        for y in (26, 27, 28):
            road_cells.add((x, y))
    for x in range(50, 93):
        for y in (64, 65, 66):
            road_cells.add((x, y))

    assert all(
        game_map.tiles[y][x].kind in allowed
        for x, y in road_cells
    )


def test_enterable_buildings_show_readable_roof_labels():
    """Every enterable building has its name carved into the roof."""
    game_map = load_planet("earth")

    for layout_id, stamp in game_map.landmark_stamps.items():
        label = layout_id.removeprefix("earth_city_").upper()
        if label == "PLAZA":
            continue
        xs = [x for x, _ in stamp["footprint"]]
        ys = [y for _, y in stamp["footprint"]]
        x_lo, x_hi = min(xs), max(xs)
        y_lo, y_hi = min(ys), max(ys)
        row = (y_lo + y_hi) // 2
        start = (x_lo + x_hi) // 2 - len(label) // 2
        for index, ch in enumerate(label):
            x = start + index
            assert x_lo < x < x_hi, f"{label} label does not fit the roof"
            tile = game_map.tiles[row][x]
            assert tile.kind == "city_building_wall"
            assert tile.walkable is False
            assert tile.char == ch, (
                f"{label} roof missing readable {ch!r} at ({x}, {row})"
            )


def test_earth_city_has_a_dense_varied_skyline():
    """The city is filled with many buildings of different footprints."""
    game_map = load_planet("earth")

    placements = getattr(game_map, "skyline_placements", ())
    assert len(placements) >= 30
    widths = {w for _x, _y, w, _h in placements}
    heights = {h for _x, _y, _w, h in placements}
    assert len(widths) >= 4
    assert len(heights) >= 3
    building_kinds = {
        "city_building_wall", "city_building_floor", "city_building_door",
    }
    assert sum(
        tile.kind in building_kinds
        for row in game_map.tiles
        for tile in row
    ) > 2_000


def test_earth_city_interiors_exit_at_the_entry_point():
    """Every interior's exit sits directly beside its spawn point."""
    game_map = load_planet("earth")

    for record in game_map.city_buildings.values():
        asset = city_landmarks.load_city_interior(record["interior_layout_id"])
        spawn = asset.spawn
        assert any(
            asset.game_map.tiles[spawn.y + dy][spawn.x + dx].kind == "exit"
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        ), f"exit not beside entry spawn for {record['label']}"


def test_earth_city_building_approaches_reach_public_routes():
    game_map = load_planet("earth")
    public_kinds = {"road", "city_bridge", "landing_pad"}

    for record in game_map.city_buildings.values():
        entrance = record["entrance"]
        assert entrance is not None
        start = (entrance[0], entrance[1] + 1)
        seen = {start}
        queue = deque([start])
        reached_public = game_map.tiles[start[1]][start[0]].kind in public_kinds
        while queue and not reached_public:
            x, y = queue.popleft()
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                point = (x + dx, y + dy)
                if point in seen or not game_map.in_bounds(*point):
                    continue
                point_kind = game_map.tiles[point[1]][point[0]].kind
                if point_kind in public_kinds:
                    reached_public = True
                    break
                if point_kind != "sidewalk":
                    continue
                seen.add(point)
                queue.append(point)
        assert reached_public, f"no public route from {record['label']}"


def test_earth_city_bridge_cells_are_reachable_from_the_landing_pad():
    game_map = load_planet("earth")
    reachable = _reachable(game_map, find_planet_spec("earth").hangar_anchor)

    for center_x, _center_y, _half_height in game_map.bridge_crossings:
        assert any(
            (center_x, y) in reachable
            for y in range(game_map.height)
            if game_map.tiles[y][center_x].kind == "city_bridge"
        )


def test_earth_city_camera_follows_player_on_large_map():
    game_map = load_planet("earth")
    camera = world.camera_for_view(
        game_map,
        world.Position(120, 75),
        region_w=80,
        region_h=54,
    )

    assert camera[0] > 0
    assert camera[1] > 0
    assert camera[2:] == (0, 0)
