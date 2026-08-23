"""Authored outdoor Earth city foundation."""

from __future__ import annotations

from . import city_landmarks, city_tiles, world


EARTH_CITY_WIDTH = 160
EARTH_CITY_HEIGHT = 100

# Water runs diagonally from the northwest floodplain to the eastern coast.
# Bridges are deliberately wide enough to remain readable and easy to find.
RIVER_CELLS: frozenset[tuple[int, int]] = frozenset(
    (x, y)
    for x in range(18, 143)
    for y in range(max(1, 42 - x // 8), min(98, 47 - x // 8) + 1)
)
COAST_CELLS: frozenset[tuple[int, int]] = frozenset(
    (x, y) for x in range(143, 159) for y in range(1, 99)
)
# Each crossing is ``(center_x, center_y, half_height)``. The river runs
# generally east-west, so bridges run north-south through the full water band.
BRIDGE_CROSSINGS: tuple[tuple[int, int, int], ...] = (
    (49, 39, 6),
    (86, 35, 6),
    (109, 31, 6),
)

# Fixed authored origins. The assets remain easy to replace without moving
# the surrounding city data or interaction logic.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "earth_city_spaceport": world.Position(12, 12),
    "earth_city_bar": world.Position(112, 10),
    "earth_city_bounties": world.Position(120, 58),
    "earth_city_merchants": world.Position(12, 62),
    "earth_city_militia": world.Position(92, 72),
    "earth_city_plaza": world.Position(70, 42),
}

# Each service NPC remains anchored to an interior-center-like outdoor cell
# for Phase 1. Phase 2 will make these entrances and interiors explicit.
NPC_POSITIONS: dict[str, world.Position] = {
    "barkeep": world.Position(119, 12),
    "bounty_master": world.Position(128, 60),
    "guild_master": world.Position(22, 64),
    "militia_captain": world.Position(101, 74),
}


def _base_tiles() -> list[list[world.Tile]]:
    """Create the Earth terrain base with perimeter walls."""
    tiles = [
        [world.EARTH_THEME.floor for _ in range(EARTH_CITY_WIDTH)]
        for _ in range(EARTH_CITY_HEIGHT)
    ]
    for x in range(EARTH_CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(EARTH_CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles


def _paint_water_and_shore(tiles: list[list[world.Tile]]) -> None:
    """Paint the river, shoreline, and a small northwest wetland."""
    for x, y in RIVER_CELLS | COAST_CELLS:
        if (x, y) in COAST_CELLS:
            tiles[y][x] = city_tiles.CITY_WATER
        elif x in {18, 19, 20}:
            tiles[y][x] = city_tiles.CITY_SHORE
        else:
            tiles[y][x] = city_tiles.CITY_WATER
    for x in range(8, 25):
        for y in range(30, 39):
            if (x + y) % 3:
                tiles[y][x] = city_tiles.CITY_SHORE


def _paint_bridges(tiles: list[list[world.Tile]]) -> None:
    """Paint north-south bridges with roads approaching both banks."""
    for center_x, _center_y, _half_height in BRIDGE_CROSSINGS:
        bridge_xs = range(center_x - 1, center_x + 2)
        river_rows = [
            y for y in range(1, EARTH_CITY_HEIGHT - 1)
            if any((x, y) in RIVER_CELLS for x in bridge_xs)
        ]
        if not river_rows:
            continue
        bridge_rows = range(min(river_rows) - 1, max(river_rows) + 2)
        for y in bridge_rows:
            for x in bridge_xs:
                tiles[y][x] = city_tiles.CITY_BRIDGE
        for y in range(4, EARTH_CITY_HEIGHT - 1):
            for x in bridge_xs:
                if tiles[y][x].kind in {
                    "city_water", "city_bridge", "city_building_wall",
                    "city_building_floor", "city_building_door",
                }:
                    continue
                tiles[y][x] = world.ROAD_SURFACE


def _paint_roads_and_districts(tiles: list[list[world.Tile]]) -> None:
    """Paint a readable road network around the water and districts."""
    road = world.ROAD_SURFACE
    lane_ns = world.ROAD_NS
    lane_ew = world.ROAD_EW
    for y in range(3, 97):
        for x in (48, 49, 50, 108, 109, 110):
            tiles[y][x] = lane_ns if x in {49, 109} else road
    for x in range(3, 143):
        for y in (49, 50, 51, 78, 79, 80):
            tiles[y][x] = lane_ew if y in {50, 79} else road
    # Short feeder roads toward the five core districts.
    for x in range(24, 49):
        for y in (26, 27, 28):
            tiles[y][x] = lane_ew if y == 27 else road
    for x in range(110, 143):
        for y in (25, 26, 27):
            tiles[y][x] = lane_ew if y == 26 else road
    for x in range(50, 93):
        for y in (64, 65, 66):
            tiles[y][x] = lane_ew if y == 65 else road
    for x in range(18, 120):
        for y in (38, 39, 40):
            if tiles[y][x].kind != "city_water":
                tiles[y][x] = lane_ew if y == 39 else road
    # Door approaches are short, direct sidewalks that remain readable
    # against the larger road grid.
    for x, y in ((119, 12), (128, 60), (23, 60), (101, 70)):
        for py in range(y, min(99, y + 12)):
            if tiles[py][x].kind != "city_water":
                tiles[py][x] = world.SIDEWALK


def _paint_parks_and_details(tiles: list[list[world.Tile]]) -> None:
    """Add deterministic parks, trees, lamps, and district texture."""
    for x in range(4, 157):
        for y in range(3, 97):
            if tiles[y][x] is world.EARTH_THEME.floor:
                tiles[y][x] = world.GRASS_ACCENT if (x * 7 + y * 11) % 13 == 0 else world.GRASS
    for x, y in (
        (8, 8), (32, 16), (66, 20), (104, 18), (145, 12),
        (8, 55), (34, 88), (66, 87), (118, 88), (136, 70),
    ):
        if tiles[y][x].walkable:
            tiles[y][x] = world.TREE
    for x, y in ((56, 43), (64, 57), (116, 43), (134, 55), (74, 84)):
        if tiles[y][x].walkable:
            tiles[y][x] = world.NEON


def _paint_landing_pad(tiles: list[list[world.Tile]]) -> None:
    """Place the port landing apron below the spaceport."""
    _pad = world.Tile(
        kind="landing_pad", char=".", walkable=True,
        fg=(100, 210, 255), bg=(40, 64, 98),
    )
    for y in range(20, 30):
        for x in range(18, 38):
            if (x, y) not in RIVER_CELLS:
                tiles[y][x] = _pad


def _stamp_assets(game_map: world.GameMap) -> dict[str, city_landmarks.CityLandmarkStamp]:
    """Stamp all authored Earth exteriors and return their placement data."""
    stamps = {
        layout_id: city_landmarks.stamp_city_landmark(
            game_map, layout_id, origin,
        )
        for layout_id, origin in LANDMARK_ORIGINS.items()
    }
    for stamp in stamps.values():
        if stamp.entrance is None:
            continue
        x, y = stamp.entrance.x, stamp.entrance.y
        for approach_y in range(y + 1, min(EARTH_CITY_HEIGHT - 1, y + 25)):
            if game_map.tiles[approach_y][x].kind in {"city_water", "landing_pad"}:
                continue
            game_map.tiles[approach_y][x] = world.SIDEWALK
    return stamps


def _place_service_entities(game_map: world.GameMap) -> None:
    """Add named NPCs and spaceport fixtures while preserving interactions."""
    for npc_id, position in NPC_POSITIONS.items():
        # NPC identity is resolved by the planet loader before this helper;
        # this placeholder is replaced by the loader's catalog entity.
        del npc_id, position
        break


def _new_earth_map() -> world.GameMap:
    """Create and decorate the expanded outdoor terrain."""
    tiles = _base_tiles()
    _paint_water_and_shore(tiles)
    _paint_roads_and_districts(tiles)
    _paint_bridges(tiles)
    _paint_parks_and_details(tiles)
    _paint_landing_pad(tiles)
    return world.GameMap(
        width=EARTH_CITY_WIDTH, height=EARTH_CITY_HEIGHT,
        tiles=tiles, entities=[],
    )


def _city_building_records(spec, stamps) -> dict:
    """Build data-driven exterior/interior records for Earth buildings."""
    layout_by_label = {
        layout_id.removeprefix("earth_city_"): stamp
        for layout_id, stamp in stamps.items()
        if layout_id != "earth_city_plaza"
    }
    return {
        building.label: {
            "label": building.label,
            "display_name": building.label.replace("_", " "),
            "npc_id": building.npc_id,
            "interior_layout_id": dict(spec.interior_layouts).get(building.label, ""),
            "entrance": (
                (stamp.entrance.x, stamp.entrance.y)
                if (stamp := layout_by_label[building.label]).entrance is not None
                else None
            ),
            "npc_position": (
                (NPC_POSITIONS[building.npc_id].x, NPC_POSITIONS[building.npc_id].y)
                if building.npc_id in NPC_POSITIONS else None
            ),
            "cache_key": f"city:{spec.id}:{building.label}",
        }
        for building in spec.buildings
        if building.label in layout_by_label
    }


def _set_city_metadata(game_map, spec, stamps) -> None:
    """Attach persistent city layout metadata to the map."""
    game_map.city_layout_id = spec.city_layout_id or "earth_river_coast"
    game_map.landmark_stamps = {
        layout_id: {
            "origin": (stamp.origin.x, stamp.origin.y),
            "footprint": set(stamp.footprint),
            "entrance": (
                (stamp.entrance.x, stamp.entrance.y)
                if stamp.entrance is not None else None
            ),
        }
        for layout_id, stamp in stamps.items()
    }
    game_map.water_cells = {
        (x, y) for x, y in RIVER_CELLS | COAST_CELLS
        if game_map.tiles[y][x].kind == "city_water"
    }
    game_map.bridge_crossings = BRIDGE_CROSSINGS
    game_map.city_districts = {
        "spaceport": (4, 8, 52, 39), "plaza": (54, 35, 106, 61),
        "waterfront": (112, 1, 158, 98), "market": (4, 53, 56, 96),
        "civic": (58, 62, 110, 96),
    }
    game_map.city_buildings = _city_building_records(spec, stamps)


def _add_service_entities(game_map, spec, resolve_npc, resolve_ship) -> None:
    """Add service NPCs, showroom ships, and spaceport terminals."""
    for building in spec.buildings:
        npc = resolve_npc(building.npc_id)
        if npc is not None:
            npc.pos = NPC_POSITIONS.get(
                building.npc_id,
                world.Position(building.x_lo + 2, building.y_lo + 2),
            )
            game_map.entities.append(npc)
    port = next(building for building in spec.buildings if building.label == "spaceport")
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(port.x_lo + off_x, port.y_lo + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
    terminal_data = (
        ("=", "Trade Terminal", world.Position(34, 29), "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", world.Position(30, 29), "mech_terminal", (200, 220, 100)),
        ("A", "Armory Terminal", world.Position(25, 29), "armory_terminal", (255, 160, 80)),
    )
    for char, name, position, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg, pos=position, name=name, **{flag: True},
        ))


def build_earth_city(spec, resolve_npc, resolve_ship) -> world.GameMap:
    """Build Earth's 160x100 outdoor city from data and authored assets."""
    game_map = _new_earth_map()
    stamps = _stamp_assets(game_map)
    _set_city_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_npc, resolve_ship)
    return game_map
