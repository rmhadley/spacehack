"""Authored outdoor Earth city foundation."""

from __future__ import annotations

from collections import deque

from . import city_landmarks, city_tiles, city_transit, world
from .engine import seeded_rng


EARTH_CITY_WIDTH = 160
EARTH_CITY_HEIGHT = 100

# Water runs diagonally from the west map edge to the eastern coast.
# Bridges are deliberately wide enough to remain readable and easy to find.
RIVER_CELLS: frozenset[tuple[int, int]] = frozenset(
    (x, y)
    for x in range(1, 143)
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
# the surrounding city data or interaction logic. Origins are chosen so no
# building footprint overlaps the road grid or the river bank.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "earth_city_spaceport": world.Position(12, 12),
    "earth_city_bar": world.Position(112, 10),
    "earth_city_bounties": world.Position(120, 58),
    "earth_city_merchants": world.Position(12, 62),
    "earth_city_militia": world.Position(54, 70),
    "earth_city_plaza": world.Position(70, 52),
}

# Procedural skyline: decorative (non-enterable) buildings fill the city
# blocks between the road grid and the river. A fixed seed keeps the same
# city every run, matching the deterministic terrain generation.
_SKYLINE_SEED: int = 1
# Each scheme is ``(wall_fg, wall_bg, roof_fg, roof_bg)`` for one building.
# Muted hues with low wall/roof contrast keep the skyline colorful but calm.
_SKYLINE_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((168, 196, 222), (58, 70, 86), (186, 208, 228), (66, 80, 96)),   # steel blue
    ((152, 200, 192), (54, 70, 68), (172, 212, 206), (62, 80, 78)),   # teal
    ((188, 176, 214), (66, 60, 80), (204, 194, 224), (74, 68, 88)),   # violet
    ((218, 190, 152), (74, 62, 46), (232, 208, 176), (82, 70, 54)),   # amber
    ((164, 200, 164), (56, 70, 56), (184, 214, 184), (64, 78, 64)),   # green
    ((196, 196, 208), (64, 64, 72), (212, 212, 220), (72, 72, 80)),   # slate
)

# Kinds the procedural skyline must never paint over or touch.
_SKYLINE_AVOID_KINDS: frozenset[str] = frozenset({
    "road", "city_water", "city_shore", "city_bridge", "landing_pad",
    "sidewalk", "city_plaza", "city_fountain", "city_ornament",
})


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
    water_cells = RIVER_CELLS | COAST_CELLS
    for x, y in water_cells:
        tiles[y][x] = city_tiles.CITY_WATER
    for x, y in water_cells:
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            shore_x, shore_y = x + dx, y + dy
            if not (0 <= shore_x < EARTH_CITY_WIDTH and 0 <= shore_y < EARTH_CITY_HEIGHT):
                continue
            if tiles[shore_y][shore_x].kind == "floor":
                tiles[shore_y][shore_x] = city_tiles.CITY_SHORE
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


def _paint_road_cell(
    tiles: list[list[world.Tile]], x: int, y: int, tile: world.Tile,
) -> None:
    """Paint a road only on dry land; bridges own river crossings."""
    if tiles[y][x].kind not in {"city_water", "city_shore"}:
        tiles[y][x] = tile


def _paint_roads_and_districts(tiles: list[list[world.Tile]]) -> None:
    """Paint a readable road network around the water and districts."""
    road = world.ROAD_SURFACE
    lane_ns = world.ROAD_NS
    lane_ew = world.ROAD_EW
    for y in range(3, 97):
        for x in (48, 49, 50, 108, 109, 110):
            _paint_road_cell(tiles, x, y, lane_ns if x in {49, 109} else road)
    for x in range(3, 143):
        for y in (49, 50, 51, 78, 79, 80):
            _paint_road_cell(tiles, x, y, lane_ew if y in {50, 79} else road)
    # Short feeder roads toward the five core districts. Roads never run
    # east of the x=108 bridge road at these latitudes: the river's diagonal
    # bank would slice through the pavement, so the bridge road owns access
    # to the waterfront district.
    for x in range(24, 49):
        for y in (26, 27, 28):
            _paint_road_cell(tiles, x, y, lane_ew if y == 27 else road)
    for x in range(50, 93):
        for y in (64, 65, 66):
            _paint_road_cell(tiles, x, y, lane_ew if y == 65 else road)


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


def _sidewalk_route(
    game_map: world.GameMap,
    start: tuple[int, int],
) -> list[tuple[int, int]]:
    """Find a walkable route from a door to the nearest public route."""
    route_kinds = {"road", "city_bridge", "landing_pad"}
    blocked_kinds = {
        "city_building_floor", "city_building_door", "city_building_wall",
    }
    queue = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        point = queue.popleft()
        if game_map.tiles[point[1]][point[0]].kind in route_kinds:
            path: list[tuple[int, int]] = []
            while point is not None:
                path.append(point)
                point = previous[point]
            return list(reversed(path))
        for dx, dy in ((0, 1), (-1, 0), (1, 0), (0, -1)):
            next_point = (point[0] + dx, point[1] + dy)
            if next_point in previous or not game_map.in_bounds(*next_point):
                continue
            tile = game_map.tiles[next_point[1]][next_point[0]]
            if not tile.walkable or tile.kind in blocked_kinds:
                continue
            previous[next_point] = point
            queue.append(next_point)
    return []


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
        route = _sidewalk_route(
            game_map, (stamp.entrance.x, stamp.entrance.y + 1),
        )
        for x, y in route:
            if game_map.tiles[y][x].kind in {"road", "city_bridge", "landing_pad"}:
                continue
            game_map.tiles[y][x] = world.SIDEWALK
    return stamps


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


def _building_site_free(
    tiles: list[list[world.Tile]],
    x: int, y: int, w: int, h: int,
) -> bool:
    """Whether a ``w x h`` footprint at ``(x, y)`` is a clear grass site.

    The whole footprint must be bare grass and must not sit orthogonally
    against a road, water, bridge, pad, sidewalk, or plaza tile. This
    keeps alleys between buildings and leaves the circulation network
    untouched.
    """
    for by in range(y, y + h):
        for bx in range(x, x + w):
            if tiles[by][bx].kind != "grass":
                return False
    for by in range(y, y + h):
        for bx in range(x, x + w):
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                if tiles[by + dy][bx + dx].kind in _SKYLINE_AVOID_KINDS:
                    return False
    return True


def _skyline_tile(
    char: str,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
) -> world.Tile:
    """Build one non-walkable skyline roof/wall tile."""
    return world.Tile(
        kind="city_building_wall", char=char, walkable=False,
        fg=fg, bg=bg,
        blocked_message="The building wall blocks your path.",
    )


def _paint_one_skyline_building(
    tiles: list[list[world.Tile]],
    x: int, y: int, w: int, h: int,
    rng,
) -> None:
    """Paint one solid decorative building: a calm roof block."""
    wall_fg, wall_bg, roof_fg, roof_bg = rng.choice(_SKYLINE_SCHEMES)
    wall = _skyline_tile("#", wall_fg, wall_bg)
    roof = _skyline_tile(".", roof_fg, roof_bg)
    for by in range(y, y + h):
        for bx in range(x, x + w):
            if by in (y, y + h - 1) or bx in (x, x + w - 1):
                tiles[by][bx] = wall
            else:
                tiles[by][bx] = roof


def _fit_skyline_building(
    tiles: list[list[world.Tile]],
    x: int, y: int, bw: int, bh: int,
) -> tuple[int, int] | None:
    """Return a slightly smaller size that fits, or ``None``."""
    for nbw, nbh in (
        (bw - 1, bh), (bw, bh - 1),
        (bw - 1, bh - 1), (bw - 2, bh - 1),
    ):
        if nbw >= 5 and nbh >= 4 and _building_site_free(
            tiles, x, y, nbw, nbh,
        ):
            return nbw, nbh
    return None


def _paint_skyline(game_map: world.GameMap) -> None:
    """Fill every free city block with varied decorative buildings.

    Buildings are solid, non-walkable roof blocks in a range of sizes
    and muted colour schemes. They never touch roads, water, the landing
    pad, sidewalks, or plazas, so the road network and every service
    interaction stay reachable. The fixed seed keeps the skyline
    identical across runs and save/load rebuilds.
    """
    rng = seeded_rng(_SKYLINE_SEED, "earth", "skyline")
    tiles = game_map.tiles
    placements: list[tuple[int, int, int, int]] = []
    y = 2
    while y < game_map.height - 2:
        x = 2
        while x < game_map.width - 2:
            if tiles[y][x].kind != "grass":
                x += 1
                continue
            bw = min(rng.randint(6, 12), game_map.width - 2 - x)
            bh = min(rng.randint(5, 9), game_map.height - 2 - y)
            if bw < 5 or bh < 4:
                x += 1
                continue
            if not _building_site_free(tiles, x, y, bw, bh):
                fitted = _fit_skyline_building(tiles, x, y, bw, bh)
                if fitted is None:
                    x += 1
                    continue
                bw, bh = fitted
            _paint_one_skyline_building(tiles, x, y, bw, bh, rng)
            placements.append((x, y, bw, bh))
            x += bw + 2
        y += 1
    game_map.skyline_placements = placements


def _paint_roof_labels(game_map: world.GameMap, stamps) -> None:
    """Carve each enterable building's name into its roof as readable text.

    Bright letters replace the roof cells on a single centered band, so
    the building reads as a rooftop sign while staying fully non-walkable.
    """
    label_fg = (244, 246, 240)
    for layout_id, stamp in stamps.items():
        label = layout_id.removeprefix("earth_city_").upper()
        if label == "PLAZA":
            continue
        xs = [x for x, _ in stamp.footprint]
        ys = [y for _, y in stamp.footprint]
        x_lo, x_hi = min(xs), max(xs)
        y_lo, y_hi = min(ys), max(ys)
        row = (y_lo + y_hi) // 2
        start = (x_lo + x_hi) // 2 - len(label) // 2
        for index, ch in enumerate(label):
            x = start + index
            if not (x_lo < x < x_hi):
                continue
            bg = game_map.tiles[row][x].bg
            game_map.tiles[row][x] = world.Tile(
                kind="city_building_wall", char=ch, walkable=False,
                fg=label_fg, bg=bg,
                blocked_message="The building wall blocks your path.",
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
    """Add showroom ships and spaceport terminals to the street.

    Service NPCs live inside their authored interiors (seated when the
    room is first loaded), so nothing stands on the pavement outside.
    """
    # Showroom ships sit on the landing pad south of the solid hangar roof
    # (offsets are relative to the pad's top-left corner, x=18 / y=20).
    _pad_x, _pad_y = 18, 20
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(_pad_x + off_x, _pad_y + off_y),
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
    _paint_roof_labels(game_map, stamps)
    _paint_skyline(game_map)
    _set_city_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_npc, resolve_ship)
    city_transit.place_transit_stations(game_map, spec)
    from . import city_npcs
    city_npcs.place_city_npcs(game_map, spec.city_npc_population)
    return game_map
