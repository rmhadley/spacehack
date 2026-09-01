"""Mercury's authored station-deck city layout generator.

Phase 5: Mercury is a second *layout* in the generic city pipeline
(:mod:`spacehack.city_builder` dispatches on ``city_layout_id ==
"mercury_station"``). It reads as a scorched research base — the same
machinery Earth uses (authored exterior stamps, roof labels, skyline,
sidewalks) but themed for a desert station: a bare heat-shield deck,
a 3-wide road grid, a commons plaza, and scorched scrub instead of
parks and a river.

The shared authored-layout machinery lives in
:mod:`spacehack.city_layout`; the shared city tail (transit stations +
ambient NPCs) runs in ``city_builder.build_city`` for every planet,
Mercury included.
"""

from __future__ import annotations

from . import world
from .city_kit import (
    add_showroom_ships,
    base_tiles,
    paint_transit_bays,
    set_city_metadata,
)
from .city_layout import (
    paint_roof_labels,
    paint_skyline,
    stamp_city_assets,
)
from .data.planets import _readable_city_theme
from .data.planets.themes import DESERT


MERCURY_CITY_WIDTH = 100
MERCURY_CITY_HEIGHT = 70

# Fixed authored origins — one per spec building, matching the building
# rectangles so records/doors line up. The assets stay swappable without
# touching the road grid or the deck data.
LANDMARK_ORIGINS: dict[str, world.Position] = {
    "mercury_spaceport": world.Position(2, 2),
    "mercury_lab": world.Position(62, 4),
    "mercury_bar": world.Position(5, 50),
    "mercury_supply": world.Position(65, 50),
}

# Three east-west boulevards, each 3 tiles wide with a centre lane
# marker (road_ew).  Buildings sit above or below the boulevards and
# doors open onto a short sidewalk or feeder that reaches the nearest
# boulevard — exactly like Earth's road/district layout.
_NORTH_BOULEVARD_Y = (16, 17, 18)
_CENTRAL_BOULEVARD_Y = (34, 35, 36)
_SOUTH_BOULEVARD_Y = (58, 59, 60)

# Three north-south avenues, each 3 tiles wide with a centre lane
# marker (road_ns).
_WEST_AVENUE_X = (25, 26, 27)
_CENTRAL_AVENUE_X = (48, 49, 50)
_EAST_AVENUE_X = (84, 85, 86)

# Short east-west feeder roads (1-wide, road_surface) that connect each
# building's door level to the nearest avenue so the player never has
# to detour to a boulevard to cross the map.
_FEEDERS: tuple[tuple[int, int, int], ...] = (
    # (x_lo, x_hi, y) — horizontal segments
    (13, 24, 15),   # pad area east → west avenue  (1 cell below pad)
    (78, 83, 15),   # lab area east → east avenue
    (16, 24, 57),   # bar area east → west avenue   (1 cell below bar)
    (77, 83, 57),   # supply area east → east avenue
)

# Small commons plaza below the central boulevard, centred between the
# central avenues.
_PLAZA_X_LO, _PLAZA_X_HI = 42, 56
_PLAZA_Y_LO, _PLAZA_Y_HI = 39, 43

# Deck lamps near the service roads (fixed, walkable floor spots).
_LAMPS: tuple[tuple[int, int], ...] = (
    (20, 15), (30, 15), (70, 15), (90, 15),
    (20, 57), (30, 57), (70, 57), (90, 57),
)

# Procedural skyline: small utility domes and sheds fill the open deck.
# A fixed seed keeps the same base every run; a sparse palette of
# scorched rust/sand/ash reads as station hardware, not city towers.
# Each scheme is ``(wall_fg, wall_bg, roof_fg, roof_bg)``.
_SKYLINE_SCHEMES: tuple[tuple[tuple[int, int, int], ...], ...] = (
    ((150, 100, 65), (48, 30, 16), (175, 130, 85), (56, 38, 22)),   # rust
    ((170, 145, 110), (56, 44, 30), (195, 170, 130), (64, 52, 36)), # sand
    ((135, 135, 145), (42, 42, 48), (160, 160, 170), (50, 50, 58)), # ash
    ((165, 120, 80), (52, 36, 22), (190, 145, 100), (60, 44, 28)),  # ochre
)


def _deck_theme():
    """Mercury's scorched theme, readability-adjusted like every city."""
    return _readable_city_theme(DESERT)




def _paint_road_cell(tiles, x, y, tile) -> None:
    """Paint one road cell — only on floor or grass (never overwrite walls)."""
    kind = tiles[y][x].kind
    if kind in {"floor", "grass"}:
        tiles[y][x] = tile


def _paint_road_corridor(tiles, theme, *, horizontal=False,
                         span_start=3, span_end=None) -> None:
    """Paint the full 3-wide road grid: three boulevards + three avenues.

    Each corridor is 3 tiles wide.  The centre tile carries the lane
    marker (road_ew for horizontal, road_ns for vertical) while the
    outer tiles are plain road_surface — matching Earth's road style.
    """
    road = theme.road_surface
    lane_h = theme.road_ew
    lane_v = theme.road_ns
    w = MERCURY_CITY_WIDTH
    h = MERCURY_CITY_HEIGHT
    end_h = span_end if span_end is not None else w - 2
    end_v = span_end if span_end is not None else h - 2

    # East-west boulevards (horizontal)
    for y_lo, y_mid, y_hi in (
        _NORTH_BOULEVARD_Y, _CENTRAL_BOULEVARD_Y, _SOUTH_BOULEVARD_Y,
    ):
        for x in range(span_start, end_h):
            _paint_road_cell(tiles, x, y_lo, road)
            _paint_road_cell(tiles, x, y_mid, lane_h)
            _paint_road_cell(tiles, x, y_hi, road)

    # North-south avenues (vertical)
    for x_lo, x_mid, x_hi in (
        _WEST_AVENUE_X, _CENTRAL_AVENUE_X, _EAST_AVENUE_X,
    ):
        for y in range(span_start, end_v):
            _paint_road_cell(tiles, x_lo, y, road)
            _paint_road_cell(tiles, x_mid, y, lane_v)
            _paint_road_cell(tiles, x_hi, y, road)

    # Short east-west feeder roads connecting buildings to avenues.
    road_sf = theme.road_surface
    for x_lo, x_hi, y in _FEEDERS:
        for x in range(x_lo, x_hi + 1):
            _paint_road_cell(tiles, x, y, road_sf)


def _paint_deck_plaza(tiles, theme) -> None:
    """Paint the commons plaza below the central boulevard."""
    for y in range(_PLAZA_Y_LO, _PLAZA_Y_HI + 1):
        for x in range(_PLAZA_X_LO, _PLAZA_X_HI + 1):
            if tiles[y][x].kind == "floor":
                tiles[y][x] = theme.plaza


def _paint_deck_pad(tiles, theme, spec) -> None:
    """Paint the landing apron below the spaceport."""
    anchor = spec.hangar_anchor
    port = spec.buildings[0]
    x_lo = max(1, anchor.x - 3)
    x_hi = min(MERCURY_CITY_WIDTH - 2, anchor.x + 3)
    y_lo = port.y_hi + 1
    y_hi = min(MERCURY_CITY_HEIGHT - 2, anchor.y + 1)
    for py in range(y_lo, y_hi + 1):
        for px in range(x_lo, x_hi + 1):
            tiles[py][px] = theme.landing_pad


# Transit boarding bay: cyan tile with kind "transit_bay" (same visual
# language as the other authored cities). Painted by _paint_transit_bays
# after all terrain painters so nothing repaints over the bays.
_TRANSIT_BAY_TILE = world.Tile(
    kind="transit_bay", char="=", walkable=True,
    fg=(140, 240, 255), bg=(42, 74, 88),
)


def _paint_transit_bays(tiles) -> None:
    """Carve a 3x3 bay under and around every transit station.

    ``force_center`` guarantees the station cell itself becomes a bay
    even when it sits on a protected kind (road/plaza); ``overwrite_kinds``
    covers every ground kind the deck uses so the rest of the 3x3 zone is
    carved too. Roads, pads, sidewalks and building tiles stay untouched
    outside the zone.
    """
    paint_transit_bays(
        tiles, _mercury_spec_stub(), _TRANSIT_BAY_TILE,
        width=MERCURY_CITY_WIDTH, height=MERCURY_CITY_HEIGHT,
        overwrite_kinds=frozenset({
            "floor", "grass", "grass_accent", "plaza", "city_plaza",
            "sidewalk", "landing_pad",
        }),
        force_center=True,
    )


def _mercury_spec_stub():
    """Return the minimal station data paint_transit_bays needs.

    The builder receives the resolved PlanetSpec only later in the
    pipeline, so expose the station positions from the data module.
    """
    from .data.planets.mercury import SPEC
    return SPEC


def _paint_deck_scrub(tiles, theme) -> None:
    """Add sparse scorched scrub and deck beacons to the bare deck.

    The deck stays mostly bare heat-shield plating so the base reads as
    a clean station, not a field of scrub; the accents are sparse and
    the skyline domes fill the open plating afterwards.
    """
    for y in range(2, MERCURY_CITY_HEIGHT - 2):
        for x in range(2, MERCURY_CITY_WIDTH - 2):
            if tiles[y][x].kind != "floor" or (x * 7 + y * 11) % 23:
                continue
            tiles[y][x] = theme.grass_accent
    for x, y in _LAMPS:
        if tiles[y][x].walkable:
            tiles[y][x] = theme.neon


def _new_mercury_map(spec) -> tuple[world.GameMap, object]:
    """Create and decorate the station-deck terrain."""
    theme = _deck_theme()
    tiles = base_tiles(
        MERCURY_CITY_WIDTH, MERCURY_CITY_HEIGHT, theme.floor,
    )
    _paint_road_corridor(tiles, theme)
    _paint_deck_plaza(tiles, theme)
    _paint_deck_pad(tiles, theme, spec)
    _paint_deck_scrub(tiles, theme)
    return (
        world.GameMap(
            width=MERCURY_CITY_WIDTH, height=MERCURY_CITY_HEIGHT,
            tiles=tiles, entities=[],
        ),
        theme,
    )


def _add_service_entities(game_map, spec, resolve_ship) -> None:
    """Add showroom ships on the apron + terminals below the port door."""
    anchor = spec.hangar_anchor
    pad_x_lo = max(1, anchor.x - 3)
    pad_y_lo = spec.buildings[0].y_hi + 1
    add_showroom_ships(
        game_map, spec, resolve_ship,
        origin=world.Position(pad_x_lo, pad_y_lo),
    )
    terminal_data = (
        ("=", "Trade Terminal", (10, 11), "trade_terminal", (100, 220, 255)),
        ("%", "Mechanic Terminal", (6, 11), "mech_terminal", (200, 220, 100)),
        ("A", "Armory Terminal", (3, 11), "armory_terminal", (255, 160, 80)),
    )
    for char, name, position, flag, fg in terminal_data:
        game_map.entities.append(world.Entity(
            char=char, fg=fg, pos=world.Position(*position),
            name=name, **{flag: True},
        ))


def build_mercury_layout(spec, resolve_ship) -> world.GameMap:
    """Build Mercury's 100x70 station deck from data + authored assets.

    Transit stations and ambient NPCs are NOT placed here — the generic
    :func:`spacehack.city_builder.build_city` shared tail adds them for
    every planet, so Earth and Mercury run the identical city pipeline.
    """
    game_map, theme = _new_mercury_map(spec)
    stamps = stamp_city_assets(
        game_map, LANDMARK_ORIGINS, sidewalk=theme.sidewalk,
    )
    # Bays run AFTER stamping/roof labels so sidewalk routing and any
    # other terrain pass cannot repaint over the pads (R1).
    _paint_transit_bays(game_map.tiles)
    paint_roof_labels(game_map, stamps, "mercury_")
    paint_skyline(
        game_map,
        seed_key=("mercury", "skyline"),
        schemes=_SKYLINE_SCHEMES,
        # Domes sit on the bare deck plating (and the sparse scrub
        # accents over it) and read as solid hardware against it. They
        # keep the strict circulation buffer like Earth's skyline, so
        # the roads, pad, plaza, and passages stay open.
        site_kinds=frozenset({"floor", "grass"}),
        roof_char="#",
        width_range=(5, 7),
        height_range=(4, 5),
        min_size=(5, 4),
        row_stride=3,
    )
    set_city_metadata(
        game_map, spec, stamps,
        prefix="mercury_", default_layout_id="mercury_station",
    )
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map
