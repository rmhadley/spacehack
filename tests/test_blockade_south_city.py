"""Regression coverage for Blockade South's Quarantine Cordon station."""
from __future__ import annotations

from collections import deque

from src.spacehack.data.planets import find_planet_spec, load_planet


ROAD_KINDS = {"road", "road_ns", "road_ew", "road_surface"}


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
    assert "quarantine" not in game_map.city_transit
    assert len(game_map.landmark_stamps) == 3
    assert any(tile.kind == "station_bulkhead" for row in game_map.tiles for tile in row)
    assert any(tile.kind == "quarantine" for row in game_map.tiles for tile in row)
    assert any(tile.kind == "beacon" for row in game_map.tiles for tile in row)


def test_blockade_south_circulation_is_planned():
    """Civil-engineering regression: one connected road network painted on
    open deck, matching the established band-painter conventions."""
    game_map = load_planet("blockade_south")
    roads = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind in ROAD_KINDS
    }
    assert len(roads) >= 300, "the station road network is too small"
    assert all(game_map.tiles[y][x].walkable for x, y in roads)
    # One connected component: no band stranded off the network.
    start = next(iter(roads))
    seen = {start}
    queue = deque(seen)
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if point in seen or point not in roads:
                continue
            seen.add(point)
            queue.append(point)
    assert seen == roads, f"road bands stranded: {len(roads - seen)} cells"
    # Roads never bury protected fixtures: pads, plaza, yards, bays, doors.
    for x, y in roads:
        assert game_map.tiles[y][x].kind in ROAD_KINDS
        for yy in range(max(0, y - 1), min(game_map.height, y + 2)):
            for xx in range(max(0, x - 1), min(game_map.width, x + 2)):
                kind = game_map.tiles[yy][xx].kind
                assert kind != "city_building_door", f"road {(x, y)} abuts a door"
    # Lane markers exist: the arterial reads east-west, spines north-south.
    # (Lane-marker tiles keep kind "road"; only the char differs.)
    chars = {tile.char for row in game_map.tiles for tile in row if tile.kind == "road"}
    assert "-" in chars, "no east-west lane marker painted"
    assert ":" in chars, "no north-south lane marker painted"


def test_blockade_south_routes_and_stops_are_reachable():
    game_map = load_planet("blockade_south")
    spec = find_planet_spec("blockade_south")
    reachable = _reachable(game_map, spec.hangar_anchor)
    assert set(game_map.city_transit) == {
        "spaceport", "militia", "bounties",
    }
    for station_id, metadata in game_map.city_transit.items():
        x, y = metadata["pos"]
        assert game_map.tiles[y][x].walkable, station_id
        assert (x, y) in reachable, station_id
    assert game_map.city_transit["militia"]["pos"] == (113, 77)
    assert game_map.city_transit["bounties"]["pos"] == (18, 77)
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


def test_blockade_south_transit_bays_do_not_clip_or_block():
    """Transit bays stay off roads and doors, keep sidewalk approaches
    intact, and each stop stands beside its own destination."""
    import math
    game_map = load_planet("blockade_south")
    spec = find_planet_spec("blockade_south")

    # 1. No bay cell (center + 8 neighbors) touches a road or a door.
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                kind = game_map.tiles[y + dy][x + dx].kind
                assert kind not in ROAD_KINDS, f"{station.id} bay clips road at ({x + dx},{y + dy})"
                assert kind != "city_building_door", f"{station.id} bay clips a door"

    # 2. Sidewalk door approaches stay sidewalk (not bay, not road).
    for building in spec.buildings:
        if building.label == "spaceport":
            continue  # the spaceport's approach is the landing apron by design
        fy = building.y_lo - 1 if getattr(building, "door_north", False) else building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            kind = game_map.tiles[fy][x].kind
            assert kind == "sidewalk", f"{building.label} approach ({x},{fy}) is {kind}"

    # 3. Each stop stands beside its own destination (<= 6 cells).
    entrances = {
        label: tuple(record["entrance"])
        for label, record in game_map.city_buildings.items()
    }
    for station in spec.transit_stations:
        entrance = entrances.get(station.id) or entrances.get(station.id.replace("_", ""))
        if entrance is None:
            continue  # plaza stop serves the hall area, not one building
        sx, sy = station.pos.x, station.pos.y
        distance = math.hypot(entrance[0] - sx, entrance[1] - sy)
        assert distance <= 6.0, f"{station.id} stop is {distance:.1f} from {entrance}"


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


def test_blockade_south_sidewalks_connect_doors_to_stops_and_roads():
    """Every building door reaches a road via a contiguous walkable chain of
    sidewalk / bay / pad / plaza cells, and the door approaches carry a
    visible sidewalk strip (no bare-deck gaps between bay and forecourt)."""
    game_map = load_planet("blockade_south")

    def path_to_road(sx, sy):
        seen = {(sx, sy)}
        queue = deque([(sx, sy)])
        while queue:
            x, y = queue.popleft()
            for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in seen or not game_map.in_bounds(nx, ny):
                    continue
                kind = game_map.tiles[ny][nx].kind
                if kind in ROAD_KINDS:
                    return True
                if kind in {"sidewalk", "transit_bay", "plaza", "landing_pad"}:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        return False

    for label, record in game_map.city_buildings.items():
        ex, ey = record["entrance"]
        assert path_to_road(ex, ey + 1), f"{label} door has no walkable path to a road"

    # The connector strips painted by the builder bridge bay edge -> door
    # forecourt -> south street: no bare deck left in the door approach rows.
    approaches = {
        "bounties": (20, 21, range(76, 79)),
        "militia": (115, 117, range(76, 79)),
        "quarantine": (70, 70, range(39, 42)),
    }
    for label, (x_lo, x_hi, ys) in approaches.items():
        for y in ys:
            for x in range(x_lo, x_hi + 1):
                kind = game_map.tiles[y][x].kind
                assert kind == "sidewalk", f"{label} connector ({x},{y}) is {kind}"
