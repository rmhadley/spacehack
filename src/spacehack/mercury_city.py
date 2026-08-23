"""Mercury's authored station-deck city layout generator.

Phase 5: Mercury is a second *layout* in the generic city pipeline
(:mod:`spacehack.city_builder` dispatches on ``city_layout_id ==
"mercury_station"``). It reads as a scorched research base — the same
machinery Earth uses (authored exterior stamps, roof labels, skyline,
sidewalks) but themed for a desert station: a bare heat-shield deck,
two service-road strips, a commons plaza, and scorched scrub instead
of parks and a river.

The shared authored-layout machinery lives in
:mod:`spacehack.city_layout`; the shared city tail (transit stations +
ambient NPCs) runs in ``city_builder.build_city`` for every planet,
Mercury included.
"""

from __future__ import annotations

from . import world
from .city_layout import (
    building_records,
    paint_roof_labels,
    paint_skyline,
    stamp_city_assets,
    stamp_metadata,
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

# The deck's service-road strip: two east-west service roads. The north
# road sits below the pad and lab; the south road connects the bar and
# supply depot doors. Every building door opens onto a road or the pad,
# so doors never need sidewalk bridges. The open deck between the roads
# stays bare plating for the skyline domes to fill.
_ROAD_A_Y = 19
_ROAD_B_Y = 58

# Small commons plaza under the transit hub (a 7x5 patch of deck).
_PLAZA_X_LO, _PLAZA_X_HI = 47, 53
_PLAZA_Y_LO, _PLAZA_Y_HI = 33, 37

# Deck lamps near the service roads (fixed, walkable floor spots).
_LAMPS: tuple[tuple[int, int], ...] = (
    (30, 18), (70, 18), (30, 57), (70, 57),
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


def _base_tiles() -> tuple[list[list[world.Tile]], object]:
    """Create the deck base: heat-shield floor with perimeter walls."""
    theme = _deck_theme()
    tiles = [
        [theme.floor for _ in range(MERCURY_CITY_WIDTH)]
        for _ in range(MERCURY_CITY_HEIGHT)
    ]
    for x in range(MERCURY_CITY_WIDTH):
        tiles[0][x] = world.WALL
        tiles[-1][x] = world.WALL
    for y in range(MERCURY_CITY_HEIGHT):
        tiles[y][0] = world.WALL
        tiles[y][-1] = world.WALL
    return tiles, theme


def _paint_deck_roads(tiles, theme) -> None:
    """Paint the two east-west service roads across the deck."""
    for x in range(3, MERCURY_CITY_WIDTH - 2):
        tiles[_ROAD_A_Y][x] = theme.road_ew
        tiles[_ROAD_B_Y][x] = theme.road_ew


def _paint_deck_plaza(tiles, theme) -> None:
    """Paint the small commons plaza under the transit hub."""
    for y in range(_PLAZA_Y_LO, _PLAZA_Y_HI + 1):
        for x in range(_PLAZA_X_LO, _PLAZA_X_HI + 1):
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


def _new_mercury_map(spec) -> world.GameMap:
    """Create and decorate the station-deck terrain."""
    tiles, theme = _base_tiles()
    _paint_deck_roads(tiles, theme)
    _paint_deck_plaza(tiles, theme)
    _paint_deck_pad(tiles, theme, spec)
    _paint_deck_scrub(tiles, theme)
    return world.GameMap(
        width=MERCURY_CITY_WIDTH, height=MERCURY_CITY_HEIGHT,
        tiles=tiles, entities=[],
    )


def _set_mercury_metadata(game_map, spec, stamps) -> None:
    """Attach the metadata city systems need for Mercury."""
    game_map.city_layout_id = spec.city_layout_id or "mercury_station"
    game_map.landmark_stamps = stamp_metadata(stamps)
    game_map.city_buildings = building_records(spec, stamps, "mercury_")


def _add_service_entities(game_map, spec, resolve_ship) -> None:
    """Add showroom ships on the apron + terminals below the port door."""
    anchor = spec.hangar_anchor
    pad_x_lo = max(1, anchor.x - 3)
    pad_y_lo = spec.buildings[0].y_hi + 1
    for ship_id, off_x, off_y in spec.showroom_ships:
        ship_obj = resolve_ship(ship_id)
        game_map.entities.append(world.Entity(
            char=ship_obj.char, fg=ship_obj.fg,
            pos=world.Position(pad_x_lo + off_x, pad_y_lo + off_y),
            name=f"Ship: {ship_obj.name}", ship_id=ship_obj.id,
            width=ship_obj.width, height=ship_obj.height,
        ))
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
    game_map = _new_mercury_map(spec)
    stamps = stamp_city_assets(game_map, LANDMARK_ORIGINS)
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
    _set_mercury_metadata(game_map, spec, stamps)
    _add_service_entities(game_map, spec, resolve_ship)
    return game_map
