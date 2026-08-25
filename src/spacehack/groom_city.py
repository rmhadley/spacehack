"""Groombridge 34 b -- hardpan boomtown at the end of the North Arm.

A strung-out mining camp on flat, wind-scoured hardpan under permanent
red-dwarf dusk: no walls, no gates, no plan -- the town exists because
the ore does. One long ore-haul road carries the whole circulation
plan, with a southern service road closing the ring.

Layout (120x80):

  * Ore-haul road -- full-width east-west band through the mid-map.
  * Service road -- southern east-west band, joined by two connectors,
    so every door reaches charted space without a dead end.
  * Spaceport + landing apron -- west end.
  * The Last Gate bar -- centre-north, facing the haul road.
  * Bounty office -- centre-south, across the road from the bar (the
    bar doubles as the bounty office out here).
  * Depot -- east end, the last fuel before the gate.
  * Tailings mounds and claim stakes texture the dig fields; a few
    shanty shacks line the road edges. No militia anywhere.
"""

from __future__ import annotations

from . import world
from .city_layout import (
    building_records,
    paint_roof_labels,
    stamp_city_assets,
    stamp_metadata,
)
from .data.planets import _readable_city_theme
from .data.planets.themes import derive_theme


CITY_WIDTH = 120
CITY_HEIGHT = 80

# Cold red-dwarf dusk variant of the mining-outpost palette: dim slate
# hardpan ground, wind-scoured grey scrub, pale ember accents.
GROOM_DUSK = derive_theme(
    floor=(135, 120, 112),
    grass=(96, 88, 84),
    accent=(255, 170, 120),
)

# ---------------------------------------------------------------------------
# Building positions (footprints match the groom_*.layout assets)
# ---------------------------------------------------------------------------

_SPACEPORT_ORIGIN = (5, 13)    # 24x9 -> x 5..28,   y 13..21
_BAR_ORIGIN = (47, 15)         # 21x8 -> x 47..67,  y 15..22
_BOUNTIES_ORIGIN = (40, 51)    # 20x8 -> x 40..59,  y 51..58
_DEPOT_ORIGIN = (86, 50)       # 24x9 -> x 86..109, y 50..58

_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 12, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 7)
_BOUNTIES_DOOR = (_BOUNTIES_ORIGIN[0] + 10, _BOUNTIES_ORIGIN[1] + 7)
_DEPOT_DOOR = (_DEPOT_ORIGIN[0] + 12, _DEPOT_ORIGIN[1] + 8)

_PAD_X_LO, _PAD_X_HI = 8, 26
_PAD_Y_LO, _PAD_Y_HI = 26, 36

# Road bands: main haul road, southern service road, ring connectors.
_ROAD_Y_BANDS = ((39, 41), (62, 64))
_CONNECTOR_X_BANDS = ((6, 8), (110, 112))

LANDMARK_ORIGINS: dict[str, world.Position] = {
    "groom_spaceport": world.Position(*_SPACEPORT_ORIGIN),
    "groom_bar": world.Position(*_BAR_ORIGIN),
    "groom_bounties": world.Position(*_BOUNTIES_ORIGIN),
    "groom_depot": world.Position(*_DEPOT_ORIGIN),
}

# ---------------------------------------------------------------------------
# Custom tiles
# ---------------------------------------------------------------------------

_TAILINGS = world.Tile(
    kind="city_building_wall", char="▲", walkable=False,
    fg=(168, 148, 128), bg=(58, 48, 42),
    blocked_message="A tailings mound blocks your path.",
)
_CLAIM_STAKE = world.Tile(
    kind="floor", char="|", walkable=True,
    fg=(214, 196, 150), bg=(62, 52, 44),
)
_SHACK_WALL = world.Tile(
    kind="city_building_wall", char="#", walkable=False,
    fg=(120, 100, 84), bg=(44, 36, 30),
    blocked_message="The shack wall blocks your path.",
)
_SHACK_ROOF = world.Tile(
    kind="city_building_wall", char='"', walkable=False,
    fg=(96, 80, 66), bg=(36, 30, 24),
    blocked_message="The corrugated roof blocks your path.",
)

# Shanty shacks: (x, y, w, h) in open hardpan clear of roads, pads,
# buildings, transit bays, and door approaches.
_SHACKS: tuple[tuple[int, int, int, int], ...] = (
    (30, 28, 5, 4), (72, 29, 4, 3), (100, 29, 4, 3),
    (27, 68, 5, 4), (66, 69, 4, 3), (104, 68, 5, 4),
)

# Tailings mounds dumped between claims -- hand-placed so they never sit
# on a route cell, bay, or approach.
_TAILING_SPOTS: tuple[tuple[int, int], ...] = (
    (14, 45), (20, 48), (33, 44), (38, 55), (35, 70), (52, 70),
    (75, 48), (80, 55), (90, 44), (114, 46), (115, 55), (15, 68),
    (44, 32), (76, 33), (95, 36), (60, 45), (78, 68), (96, 70),
)

# Claim stakes marking the outer dig fields.
_CLAIM_SPOTS: tuple[tuple[int, int], ...] = (
    (12, 25), (24, 24), (33, 20), (36, 26), (70, 24), (84, 28),
    (113, 24), (114, 36), (12, 50), (30, 48), (66, 46), (80, 66),
    (20, 74), (56, 72), (88, 72), (116, 70), (46, 68),
)


# ---------------------------------------------------------------------------
# Painters
# ---------------------------------------------------------------------------

def _base_tiles(theme):
    tiles = [[theme.floor for _ in range(CITY_WIDTH)] for _ in range(CITY_HEIGHT)]
    for x in range(CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles


def _paint_scrub(tiles, theme) -> None:
    """Add sparse dry-scrub texture without filling the town with noise."""
    from .engine import seeded_rng

    rng = seeded_rng(7, "groom_scrub")
    for y in range(2, CITY_HEIGHT - 2):
        for x in range(2, CITY_WIDTH - 2):
            if tiles[y][x].kind == "floor" and rng.random() < 0.05:
                tiles[y][x] = theme.grass_accent


def _paint_pad(tiles, theme) -> None:
    """Smooth landing apron under ships and terminals -- no dot noise."""
    pad_tile = world.Tile(
        kind="landing_pad", char=" ", walkable=True,
        fg=(150, 175, 205), bg=(52, 66, 86),
    )
    for y in range(_PAD_Y_LO, _PAD_Y_HI + 1):
        for x in range(_PAD_X_LO, _PAD_X_HI + 1):
            tiles[y][x] = pad_tile


def _paint_roads(tiles, theme) -> None:
    """Two full-width east-west bands joined into one connected ring."""
    surface, lane = theme.road_surface, theme.road_ew
    for y_lo, y_hi in _ROAD_Y_BANDS:
        for y in range(y_lo, y_hi + 1):
            for x in range(1, CITY_WIDTH - 1):
                tiles[y][x] = lane if y == (y_lo + y_hi) // 2 else surface
    for x_lo, x_hi in _CONNECTOR_X_BANDS:
        for x in range(x_lo, x_hi + 1):
            for y in range(_ROAD_Y_BANDS[0][0], _ROAD_Y_BANDS[1][1] + 1):
                if tiles[y][x].kind != "road":
                    tiles[y][x] = surface


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
            tiles[by][bx] = _SHACK_WALL if edge else _SHACK_ROOF


def _paint_shacks(tiles) -> None:
    for x, y, w, h in _SHACKS:
        _paint_one_shack(tiles, x, y, w, h)


def _paint_tailings(tiles) -> None:
    for x, y in _TAILING_SPOTS:
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            if tiles[y][x].kind == "floor":
                tiles[y][x] = _TAILINGS


def _paint_claim_stakes(tiles) -> None:
    for x, y in _CLAIM_SPOTS:
        if 0 <= y < CITY_HEIGHT and 0 <= x < CITY_WIDTH:
            if tiles[y][x].kind == "floor":
                tiles[y][x] = _CLAIM_STAKE


def _paint_forecourts(tiles, theme, spec) -> None:
    """Give each south-facing door a three-cell sidewalk forecourt."""
    for building in spec.buildings:
        y = building.y_hi + 1
        for x in range(building.door_x - 1, building.door_x + 2):
            if 0 <= x < CITY_WIDTH and 0 <= y < CITY_HEIGHT:
                t = tiles[y][x]
                if t.kind == "floor":
                    tiles[y][x] = theme.sidewalk


def _paint_transit_bays(tiles, spec) -> None:
    """Paint a smooth floor bay under and around each transit stop."""
    bay = world.Tile(
        kind="floor", char=" ", walkable=True,
        fg=(150, 138, 126), bg=(70, 60, 52),
    )
    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= ny < CITY_HEIGHT and 0 <= nx < CITY_WIDTH:
                    if tiles[ny][nx].kind in {"floor", "grass"}:
                        tiles[ny][nx] = bay


# ---------------------------------------------------------------------------
# Metadata + service entities
# ---------------------------------------------------------------------------

def _set_metadata(game_map, spec, stamps) -> None:
    game_map.city_layout_id = spec.city_layout_id or "groom_hardpan_boomtown"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "groom_")


def _add_service_entities(game_map, spec, resolve_ship) -> None:
    berth = spec.hangar_anchor
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(berth.x + off_x, berth.y + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
    terminal_data = (
        ("=", "Trade Terminal", -6, "trade_terminal", (140, 230, 255)),
        ("%", "Mechanic Terminal", -2, "mech_terminal", (210, 220, 130)),
        ("A", "Armory Terminal", 2, "armory_terminal", (255, 175, 105)),
    )
    for char, name, dx, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg,
            pos=world.Position(berth.x + dx, berth.y + 3),
            name=name, **{flag: True},
        ))


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------

def build_groom_layout(spec, resolve_ship) -> world.GameMap:
    theme = _readable_city_theme(GROOM_DUSK)
    tiles = _base_tiles(theme)
    _paint_shacks(tiles)
    _paint_scrub(tiles, theme)
    _paint_pad(tiles, theme)
    _paint_roads(tiles, theme)
    _paint_tailings(tiles)
    _paint_claim_stakes(tiles)
    game_map = world.GameMap(
        width=CITY_WIDTH, height=CITY_HEIGHT,
        tiles=tiles, entities=[],
    )
    stamps = stamp_city_assets(game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk)
    _paint_forecourts(game_map.tiles, theme, spec)
    _paint_transit_bays(game_map.tiles, spec)
    paint_roof_labels(game_map, stamps, "groom_")
    _set_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map


__all__ = ["build_groom_layout", "LANDMARK_ORIGINS"]
