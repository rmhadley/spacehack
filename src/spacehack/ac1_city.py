"""AC-I — The Claim: a sun-cracked salt-flat boomtown under two suns.

Alpha Centauri A and B pour white light onto a hot, dust-scoured rock.
The ground baked into a cracked salt pan — a bleached white plain
crossed by dark fracture lines where the crust split under the heat.
The town grew from a strike-camp into a permanent claim: a ramshackle
grid of diggings and processing shacks around the assayer's office
("The Claim"), with claim stakes dotting the landscape and ore piles
marking each prospector's patch. The sodium-vapor lamp posts lining
the grid streets cast amber pools of light across the salt at night.

Layout (100x70), authored as `ac1_the_claim`:

  * The walkable ground is a cracked salt flat — bleached white
    terrain crossed by dark fracture lines (a deterministic crack
    pattern radiating from the town center). Sun-cracked salt ridges
    (non-walkable) rim the map edges instead of a wall.
  * The town is a grid: two east-west streets (North Grid Street and
    South Grid Street) crossed by one north-south avenue (Claim
    Avenue), meeting at the crossroads plaza with the town beacon.
  * Landing apron NW — smooth pad, showroom ships, terminals.
  * Spaceport NW of the apron, door south.
  * "The Claim" bar/assayer east on South Grid Street, door north.
  * Claim stakes and ore piles dot the south salt flat between the
    diggings; sun-blasted boulders and shanty shacks texture the
    north flat.
  * Sodium-vapor amber neon lamps line the grid intersections.
"""
from __future__ import annotations

import math
from collections import deque

from . import world
from .city_kit import (
    TERMINAL_PALETTE_CLASSIC,
    add_service_terminals,
    add_showroom_ships,
    in_bounds,
    paint_door_forecourts,
    paint_transit_bays,
    set_city_metadata,
)
from .city_layout import paint_roof_labels, stamp_city_assets
from .data.planets import _readable_city_theme
from .data.planets.themes import T, derive_theme, override_theme


CITY_WIDTH = 100
CITY_HEIGHT = 70

# Bleached, doubly-scorched salt-flat palette: white-cracked salt,
# amber sodium-vapor lamps, dusty brown diggings.
AC1_SALT = override_theme(
    derive_theme(
        floor=(215, 205, 185),
        grass=(185, 175, 155),
        accent=(255, 200, 100),
        road_surface=T("road", ".", (180, 170, 145), (120, 110, 88)),
        road_ns=T("road", ":", (255, 200, 100), (100, 85, 50)),
        road_ew=T("road", "-", (255, 200, 100), (100, 85, 50)),
        sidewalk=T("sidewalk", "▒", (195, 185, 165), (130, 120, 95)),
        plaza=T("plaza", "░", (225, 215, 190), (150, 140, 110)),
        landing_pad=T("landing_pad", "▓", (210, 195, 160), (120, 105, 75)),
        neon=T("neon", "*", (255, 200, 100), (70, 45, 15)),
    ),
    floor=T("floor", "░", (215, 205, 185), (120, 110, 88)),
)

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "ac1_spaceport": world.Position(6, 4),
    "ac1_bar":       world.Position(66, 52),
}

# ---------------------------------------------------------------------
# Salt-flat crack geometry
# ---------------------------------------------------------------------

# Cracks radiate from the town center, with deterministic branches.
# Each crack is (angle_deg, start_r, end_r, branch_at, branch_angle).
_CRACK_CENTER = (50, 35)
_CRACKS = (
    (15,  3, 28, 12, 45),
    (55,  4, 25, 10, -40),
    (95,  3, 30, 15, 35),
    (135, 4, 22, 10, -50),
    (175, 3, 27, 14, 40),
    (215, 4, 24, 11, -35),
    (255, 3, 29, 13, 45),
    (295, 4, 26, 10, -40),
    (335, 3, 25, 12, 50),
)

# Sun-cracked salt ridges rim the map edges (irregular, non-wall).
_RIDGE_SEED = 31

# ---------------------------------------------------------------------
# Planned circulation — a grid, not one strip
# ---------------------------------------------------------------------

# Two east-west streets + one north-south avenue, crossing at the plaza.
_NORTH_STREET_Y = (24, 25, 26)
_SOUTH_STREET_Y = (44, 45, 46)
_STREET_X_LO, _STREET_X_HI = 4, 96
_AVENUE_X = (48, 49, 50)
_AVENUE_Y_LO, _AVENUE_Y_HI = 8, 66

# Landing apron NW.
_APRON = (4, 22, 18, 28)

# Crossroads plaza at the avenue + south-street intersection.
_PLAZA = (44, 56, 44, 46)
_BEACON = (50, 45)

# ---------------------------------------------------------------------
# Decoration
# ---------------------------------------------------------------------

# Claim stakes dotting the south salt flat.
_CLAIM_STAKES = (
    (15, 55), (22, 58), (30, 56), (38, 60),
    (50, 62), (62, 58), (70, 60), (80, 56),
    (88, 58), (92, 54),
)

# Ore piles marking prospector patches.
_ORE_PILES = (
    (12, 60), (18, 64), (28, 62), (35, 65),
    (45, 63), (55, 66), (65, 64), (75, 62),
    (85, 66), (90, 60),
)

# Sun-blasted boulders on the north flat.
_BOULDERS = (
    (30, 12), (40, 10), (52, 14), (64, 10),
    (76, 12), (88, 8),
)

# Shanty shacks on the north flat, clear of roads.
_SHACKS: tuple[tuple[int, int, int, int], ...] = (
    (30, 14, 5, 4), (42, 14, 4, 3), (54, 14, 5, 4),
    (66, 14, 4, 3), (78, 14, 5, 4),
)

# Sodium-vapor lamp posts at grid intersections and along streets.
_LAMP_POSTS = (
    (20, 25), (35, 25), (65, 25), (80, 25),
    (20, 45), (35, 45), (65, 45), (80, 45),
    (49, 15), (49, 30), (49, 55), (49, 62),
)


# ---------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------


def _tile(kind, char, fg, bg, walkable=True, message=None) -> world.Tile:
    return world.Tile(
        kind=kind, char=char, walkable=walkable, fg=fg, bg=bg,
        blocked_message=message,
    )


SALT_CRACK = _tile(
    "salt_crack", "~", (95, 82, 60), (78, 65, 45),
    message="A crack in the salt crust - the ground split under the double sun.",
)
SALT_RIDGE = _tile(
    "salt_ridge", "▓", (200, 195, 180), (130, 120, 100), walkable=False,
    message="A sun-cracked salt ridge - too rough to cross.",
)
CLAIM_STAKE = _tile(
    "claim_stake", "^", (255, 215, 80), (75, 60, 25), walkable=False,
    message="A rusted claim stake marks a prospector's patch.",
)
ORE_PILE = _tile(
    "ore_pile", "▲", (180, 130, 70), (55, 38, 20), walkable=False,
    message="A pile of raw ore - not yours to take.",
)
BOULDER = _tile(
    "boulder", "o", (160, 130, 95), (58, 45, 30), walkable=False,
    message="A sun-blasted boulder blocks your path.",
)
SHACK_WALL = _tile(
    "city_building_wall", "#", (135, 108, 75), (50, 40, 28), walkable=False,
    message="The shack wall blocks your path.",
)
SHACK_ROOF = _tile(
    "city_building_wall", '"', (110, 88, 60), (42, 34, 24), walkable=False,
    message="The corrugated roof blocks your path.",
)
BEACON = _tile(
    "beacon", "!", (255, 220, 100), (50, 42, 22), walkable=False,
    message="The town beacon marks the assayer's office for inbound pilots.",
)
LAMP = _tile(
    "neon", "i", (255, 200, 100), (70, 45, 15), walkable=False,
    message="A sodium-vapor lamp post casts an amber pool of light.",
)
BAY = _tile(
    "transit_bay", "=", (255, 220, 120), (92, 72, 44),
    message="A transit boarding bay.",
)


# ---------------------------------------------------------------------
# Terrain painters
# ---------------------------------------------------------------------


def _paint_salt_ridges(tiles) -> None:
    """Ring the map with irregular sun-cracked salt ridges (no wall)."""
    from .engine import seeded_rng

    rng = seeded_rng(_RIDGE_SEED, "ac1_ridges")
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            edge_dist = min(x, y, CITY_WIDTH - 1 - x, CITY_HEIGHT - 1 - y)
            if edge_dist == 0:
                tiles[y][x] = SALT_RIDGE
            elif edge_dist <= 2 and rng.random() < 0.6:
                tiles[y][x] = SALT_RIDGE


def _paint_cracks(tiles) -> None:
    """Paint the salt-flat fracture lines radiating from the town center.

    Cracks are walkable — they read as visible fracture lines in the
    crust, not obstacles. The dark crack lines on the white salt give
    the terrain its identity.
    """
    cx, cy = _CRACK_CENTER
    for angle_deg, r_start, r_end, branch_r, branch_angle in _CRACKS:
        angle = math.radians(angle_deg)
        for step in range(r_start, r_end + 1):
            x = int(round(cx + math.cos(angle) * step))
            y = int(round(cy + math.sin(angle) * step))
            if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                tiles[y][x].kind == "floor"
            ):
                tiles[y][x] = SALT_CRACK
        # Branch
        if branch_r > 0:
            bx = int(round(cx + math.cos(angle) * branch_r))
            by = int(round(cy + math.sin(angle) * branch_r))
            b_angle = math.radians(angle_deg + branch_angle)
            for step in range(1, 8):
                x = int(round(bx + math.cos(b_angle) * step))
                y = int(round(by + math.sin(b_angle) * step))
                if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
                    tiles[y][x].kind == "floor"
                ):
                    tiles[y][x] = SALT_CRACK


def _paint_grid_streets(tiles, theme) -> None:
    """Paint the grid: two EW streets + one NS avenue with lane markers."""
    # East-west streets
    for x in range(_STREET_X_LO, _STREET_X_HI + 1):
        for y in _NORTH_STREET_Y:
            tiles[y][x] = theme.road_ew if y == _NORTH_STREET_Y[1] else theme.road_surface
        for y in _SOUTH_STREET_Y:
            tiles[y][x] = theme.road_ew if y == _SOUTH_STREET_Y[1] else theme.road_surface
    # North-south avenue
    for y in range(_AVENUE_Y_LO, _AVENUE_Y_HI + 1):
        for x in _AVENUE_X:
            tiles[y][x] = theme.road_ns if x == _AVENUE_X[1] else theme.road_surface


def _paint_apron(tiles, theme) -> None:
    """Reserve the quiet blank landing apron at the NW end."""
    pad = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(200, 190, 165), bg=(120, 105, 75),
    )
    x_lo, x_hi, y_lo, y_hi = _APRON
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = pad


def _paint_plaza(tiles, theme) -> None:
    """Paint the crossroads plaza with the town beacon."""
    x_lo, x_hi, y_lo, y_hi = _PLAZA
    for y in range(y_lo, y_hi + 1):
        for x in range(x_lo, x_hi + 1):
            tiles[y][x] = theme.plaza
    bx, by = _BEACON
    tiles[by][bx] = BEACON


def _paint_boulders(tiles) -> None:
    """Scatter sun-blasted boulders on the north flat."""
    for x, y in _BOULDERS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = BOULDER


def _paint_one_shack(tiles, x, y, w, h) -> None:
    if not all(
        0 <= by < CITY_HEIGHT and 0 <= bx < CITY_WIDTH
        and tiles[by][bx].kind == "floor"
        for by in range(y, y + h) for bx in range(x, x + w)
    ):
        return
    for by in range(y, y + h):
        for bx in range(x, x + w):
            edge = by in (y, y + h - 1) or bx in (x, x + w - 1)
            tiles[by][bx] = SHACK_WALL if edge else SHACK_ROOF


def _paint_shacks(tiles) -> None:
    for x, y, w, h in _SHACKS:
        _paint_one_shack(tiles, x, y, w, h)


def _paint_claim_stakes(tiles) -> None:
    """Plant rusted claim stakes across the south salt flat."""
    for x, y in _CLAIM_STAKES:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = CLAIM_STAKE


def _paint_ore_piles(tiles) -> None:
    """Scatter ore piles on the south flat."""
    for x, y in _ORE_PILES:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind == "floor"
        ):
            tiles[y][x] = ORE_PILE


def _paint_lamps(tiles) -> None:
    """Line grid intersections with sodium-vapor lamp posts."""
    for x, y in _LAMP_POSTS:
        if in_bounds(x, y, CITY_WIDTH, CITY_HEIGHT) and (
            tiles[y][x].kind in ("floor", "salt_crack", "road", "plaza")
        ):
            tiles[y][x] = LAMP


def _seal_dead_salt(tiles, anchor) -> None:
    """Turn walkable cells cut off from the hangar into salt ridges."""
    start = (anchor.x, anchor.y)
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            point = (x + dx, y + dy)
            if point in seen or not in_bounds(point[0], point[1], CITY_WIDTH, CITY_HEIGHT):
                continue
            if tiles[point[1]][point[0]].walkable:
                seen.add(point)
                queue.append(point)
    for y in range(CITY_HEIGHT):
        for x in range(CITY_WIDTH):
            if tiles[y][x].walkable and (x, y) not in seen:
                tiles[y][x] = SALT_RIDGE


# ---------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------


def _finish_ac1(spec, resolve_ship, tiles, theme):
    """Stamp assets, paint transit/lamps, seed lighting for AC-I."""
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    paint_door_forecourts(
        game_map.tiles, theme, spec, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "salt_crack"}),
    )
    paint_transit_bays(
        game_map.tiles, spec, BAY, width=CITY_WIDTH, height=CITY_HEIGHT,
        overwrite_kinds=frozenset({"floor", "sidewalk", "plaza", "salt_crack"}),
    )
    _paint_lamps(game_map.tiles)
    _seal_dead_salt(game_map.tiles, spec.hangar_anchor)
    paint_roof_labels(game_map, stamps, "ac1_")
    set_city_metadata(
        game_map, spec, stamps,
        prefix="ac1_", default_layout_id="ac1_the_claim",
    )
    add_showroom_ships(game_map, spec, resolve_ship, origin=spec.hangar_anchor)
    add_service_terminals(
        game_map, spec, dy=3, dxs=(-5, -2, 1),
        palette=TERMINAL_PALETTE_CLASSIC,
    )
    return game_map


def build_ac1_layout(spec, resolve_ship) -> world.GameMap:
    """Build The Claim's 100x70 salt-flat boomtown from data + assets."""
    theme = _readable_city_theme(AC1_SALT)
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    _paint_salt_ridges(tiles)
    _paint_cracks(tiles)
    _paint_grid_streets(tiles, theme)
    _paint_apron(tiles, theme)
    _paint_plaza(tiles, theme)
    _paint_boulders(tiles)
    _paint_shacks(tiles)
    _paint_claim_stakes(tiles)
    _paint_ore_piles(tiles)
    return _finish_ac1(spec, resolve_ship, tiles, theme)


__all__ = ["build_ac1_layout", "LANDMARK_ORIGINS", "AC1_SALT"]
