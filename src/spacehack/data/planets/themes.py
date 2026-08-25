"""PlanetTheme presets and a :func:`derive_theme` helper.

Usage from a planet module::

    from .themes import DESERT

    SPEC = PlanetSpec(
        theme=DESERT,
        ...
    )

Or with per-planet overrides::

    from .themes import derive_theme

    theme = derive_theme(
        floor=(180, 210, 240), grass=(200, 220, 245), accent=(150, 230, 255),
        neon=Tile(kind="neon", char="*", walkable=True, fg=(255, 200, 100), bg=(30, 45, 60)),
    )
"""
from __future__ import annotations

from dataclasses import replace as _replace

from ...world import PlanetTheme, Tile

# ---------------------------------------------------------------------------
# T() helper — concise Tile constructor
# ---------------------------------------------------------------------------

def T(kind: str, char: str, fg: tuple[int, int, int], bg: tuple[int, int, int]) -> Tile:
    """One-line :class:`Tile` with ``walkable=True`` pre-filled."""
    return Tile(kind=kind, char=char, walkable=True, fg=fg, bg=bg)


def _darken(rgb: tuple[int, int, int], scale: float) -> tuple[int, int, int]:
    return tuple(min(255, max(0, int(c * scale))) for c in rgb)


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(ac * (1 - t) + bc * t) for ac, bc in zip(a, b))


def override_theme(base: PlanetTheme, **overrides) -> PlanetTheme:
    """Return a copy of ``base`` with specific field overrides.

    Example::

        from .themes import ICE, override_theme

        theme = override_theme(ICE, neon=T("neon", "*", (255, 200, 100), (30, 45, 60)))
    """
    return _replace(base, **overrides)


# ---------------------------------------------------------------------------
# derive_theme — build a complete theme from 3 colour anchors
# ---------------------------------------------------------------------------

def _derived_theme(
    floor: tuple[int, int, int],
    grass: tuple[int, int, int],
    accent: tuple[int, int, int],
) -> PlanetTheme:
    """Build the derived tile set from three color anchors."""
    grass_bg = _darken(grass, 0.38)
    road_fg = _darken(grass, 0.52)
    road_bg = _darken(grass, 0.25)
    plaza_bg = _darken(_blend(grass, (255, 245, 230), 0.5), 0.6)
    road_ns = T("road", ":", _darken(road_fg, 0.82), _darken(road_bg, 0.85))
    road_ew = T("road", "-", _darken(road_fg, 0.82), _darken(road_bg, 0.85))
    return PlanetTheme(
        floor=T("floor", "░", floor, _darken(floor, 0.42)),
        grass=T("grass", "█", grass, grass_bg),
        grass_accent=T("grass", ",", _darken(grass, 0.5), grass_bg),
        plaza=T("plaza", "░", _blend(grass, (255, 245, 220), 0.55), plaza_bg),
        sidewalk=T("sidewalk", "▒", _darken(_blend(grass, (190, 195, 210), 0.5), 0.55), _darken(_blend(grass, (190, 195, 210), 0.5), 0.32)),
        road_surface=T("road", ".", road_fg, road_bg),
        road_ns=road_ns,
        road_ew=road_ew,
        landing_pad=T("landing_pad", "▓", _blend(grass, (150, 220, 255), 0.6), _darken(grass, 0.22)),
        neon=T("neon", "*", accent, _darken(accent, 0.15)),
        tree=T("tree", "♣", _darken(grass, 0.78), _darken(grass, 0.32)),
        decor=T("plaza", "♦", accent, plaza_bg),
    )


def derive_theme(
    *,
    floor: tuple[int, int, int] = (200, 180, 140),
    grass: tuple[int, int, int] = (140, 100, 70),
    accent: tuple[int, int, int] = (255, 180, 80),
    **overrides,
) -> PlanetTheme:
    """Build a complete theme from color anchors and optional tile overrides."""
    base = _derived_theme(floor, grass, accent)
    return _replace(base, **overrides) if overrides else base


# ---------------------------------------------------------------------------
# Named presets — fully hand-tuned values
# ---------------------------------------------------------------------------

# Import Earth's default theme from world.py so earth.py can reference it.
from ...world import EARTH_THEME as EARTH_THEME_DEFAULT

# Earth — warm greens, cream plaza, slate-grey roads (the game's default palette).
EARTH = EARTH_THEME_DEFAULT

# Mars — red dust, rusty dirt, warm orange accents.
MARS = PlanetTheme(
    grass=T("grass", "█", (180, 80, 50), (60, 30, 20)),
    grass_accent=T("grass", ",", (90, 40, 25), (60, 30, 20)),
    plaza=T("plaza", "░", (200, 150, 100), (140, 100, 65)),
    sidewalk=T("sidewalk", "▒", (120, 70, 50), (55, 35, 22)),
    road_surface=T("road", ".", (110, 70, 50), (42, 28, 20)),
    road_ns=T("road", ":", (90, 55, 40), (35, 22, 18)),
    road_ew=T("road", "-", (90, 55, 40), (35, 22, 18)),
    landing_pad=T("landing_pad", "▓", (200, 130, 50), (50, 30, 15)),
    neon=T("neon", "*", (255, 180, 60), (50, 25, 10)),
    tree=T("tree", "♣", (160, 100, 50), (50, 30, 15)),
    decor=T("plaza", "♦", (255, 120, 60), (140, 100, 65)),
)

# Mars colony — red dust outside, graphite infrastructure, ceramic sidewalks,
# cyan glass and restrained orange guidance lights inside the public realm.
MARS_CITY = PlanetTheme(
    floor=T("floor", ".", (150, 70, 48), (58, 32, 25)),
    grass=T("grass", "█", (174, 72, 48), (62, 30, 22)),
    grass_accent=T("grass", ",", (98, 40, 30), (62, 30, 22)),
    plaza=T("plaza", "░", (185, 220, 224), (66, 104, 110)),
    sidewalk=T("sidewalk", "▒", (190, 205, 208), (72, 86, 92)),
    road_surface=T("road", ".", (112, 132, 145), (28, 36, 46)),
    road_ns=T("road", ":", (105, 224, 236), (26, 48, 60)),
    road_ew=T("road", "-", (105, 224, 236), (26, 48, 60)),
    landing_pad=T("landing_pad", "▓", (176, 224, 236), (34, 62, 76)),
    neon=T("neon", "*", (90, 240, 255), (24, 60, 72)),
    tree=T("tree", "♣", (218, 112, 64), (70, 34, 24)),
    decor=T("plaza", "♦", (255, 174, 78), (66, 104, 110)),
)

# Mining outpost — deep reds, dusty oranges, scorched browns.
DESERT = PlanetTheme(
    floor=T("floor", "░", (150, 80, 50), (55, 35, 20)),
    grass=T("grass", "█", (140, 60, 40), (50, 25, 15)),
    grass_accent=T("grass", ",", (70, 30, 20), (50, 25, 15)),
    plaza=T("plaza", "░", (170, 110, 70), (120, 75, 50)),
    sidewalk=T("sidewalk", "▒", (110, 60, 40), (30, 18, 10)),
    road_surface=T("road", ".", (90, 55, 40), (35, 22, 15)),
    road_ns=T("road", ":", (75, 45, 30), (30, 18, 12)),
    road_ew=T("road", "-", (75, 45, 30), (30, 18, 12)),
    landing_pad=T("landing_pad", "▓", (200, 120, 50), (40, 22, 10)),
    neon=T("neon", "*", (255, 150, 60), (40, 20, 8)),
    tree=T("tree", "♣", (130, 80, 40), (40, 22, 10)),
    decor=T("plaza", "♦", (255, 100, 40), (120, 75, 50)),
)

# Temperate colony — lush greens, warm golds, optimistic brights.
LUSH = PlanetTheme(
    floor=T("floor", "░", (200, 180, 140), (80, 70, 50)),
    grass=T("grass", "█", (90, 180, 70), (35, 75, 30)),
    grass_accent=T("grass", ",", (45, 90, 35), (35, 75, 30)),
    plaza=T("plaza", "░", (220, 200, 170), (160, 140, 110)),
    sidewalk=T("sidewalk", "▒", (140, 120, 90), (65, 55, 40)),
    road_surface=T("road", ".", (120, 110, 90), (50, 45, 35)),
    road_ns=T("road", ":", (100, 90, 70), (40, 35, 25)),
    road_ew=T("road", "-", (100, 90, 70), (40, 35, 25)),
    landing_pad=T("landing_pad", "▓", (220, 200, 120), (55, 50, 30)),
    neon=T("neon", "*", (180, 240, 120), (30, 60, 25)),
    tree=T("tree", "♣", (60, 200, 50), (35, 75, 30)),
    decor=T("plaza", "♦", (255, 200, 80), (160, 140, 110)),
)

# Cloud city — cool blues, silver, pale whites.
CLOUD_CITY = PlanetTheme(
    floor=T("floor", "░", (180, 200, 230), (60, 75, 95)),
    grass=T("grass", "█", (140, 190, 220), (50, 65, 85)),
    grass_accent=T("grass", ",", (70, 95, 110), (50, 65, 85)),
    plaza=T("plaza", "░", (210, 225, 245), (155, 175, 200)),
    sidewalk=T("sidewalk", "▒", (130, 155, 180), (55, 70, 85)),
    road_surface=T("road", ".", (110, 130, 155), (42, 55, 70)),
    road_ns=T("road", ":", (90, 110, 135), (35, 45, 60)),
    road_ew=T("road", "-", (90, 110, 135), (35, 45, 60)),
    landing_pad=T("landing_pad", "▓", (200, 230, 255), (45, 60, 75)),
    neon=T("neon", "*", (160, 220, 255), (30, 45, 60)),
    tree=T("tree", "♣", (120, 200, 230), (50, 65, 85)),
    decor=T("plaza", "♦", (200, 240, 255), (155, 175, 200)),
)

# Ice station — cold blues, icy whites, frost.
ICE = PlanetTheme(
    floor=T("floor", "░", (180, 210, 240), (60, 80, 110)),
    grass=T("grass", "█", (200, 220, 245), (70, 90, 120)),
    grass_accent=T("grass", ",", (100, 110, 122), (70, 90, 120)),
    plaza=T("plaza", "░", (210, 230, 250), (150, 175, 205)),
    sidewalk=T("sidewalk", "▒", (130, 160, 195), (55, 75, 100)),
    road_surface=T("road", ".", (110, 140, 175), (40, 60, 85)),
    road_ns=T("road", ":", (90, 120, 155), (35, 50, 70)),
    road_ew=T("road", "-", (90, 120, 155), (35, 50, 70)),
    landing_pad=T("landing_pad", "▓", (220, 240, 255), (50, 70, 95)),
    neon=T("neon", "*", (150, 230, 255), (35, 55, 80)),
    tree=T("tree", "♣", (140, 210, 240), (70, 90, 120)),
    decor=T("plaza", "♦", (200, 240, 255), (150, 175, 205)),
)

# Pirate outpost — cold dark rock, salvaged steel, dim red warning lights.
PIRATE_OUTPOST = PlanetTheme(
    floor=T("floor", ".", (115, 128, 148), (42, 48, 58)),
    grass=T("grass", "█", (72, 82, 96), (28, 34, 42)),
    grass_accent=T("grass", ",", (54, 62, 74), (28, 34, 42)),
    plaza=T("plaza", "░", (160, 175, 195), (78, 88, 102)),
    sidewalk=T("sidewalk", "▒", (95, 108, 126), (52, 58, 70)),
    road_surface=T("road", ".", (78, 90, 108), (34, 40, 50)),
    road_ns=T("road", ":", (64, 76, 92), (28, 34, 44)),
    road_ew=T("road", "-", (64, 76, 92), (28, 34, 44)),
    landing_pad=T("landing_pad", "▓", (185, 195, 210), (55, 62, 74)),
    neon=T("neon", "*", (230, 100, 60), (28, 12, 8)),
    tree=T("tree", "♣", (100, 112, 128), (38, 44, 52)),
    decor=T("plaza", "♦", (235, 155, 75), (52, 32, 18)),
)

# Rugged settlement — warm earth tones, dry browns, pioneer amber.
WARM_EARTH = PlanetTheme(
    floor=T("floor", "░", (170, 140, 100), (65, 50, 35)),
    grass=T("grass", "█", (150, 110, 60), (55, 38, 22)),
    grass_accent=T("grass", ",", (75, 55, 30), (55, 38, 22)),
    plaza=T("plaza", "░", (200, 170, 130), (145, 115, 80)),
    sidewalk=T("sidewalk", "▒", (120, 90, 60), (50, 38, 25)),
    road_surface=T("road", ".", (105, 80, 55), (40, 30, 20)),
    road_ns=T("road", ":", (85, 65, 45), (32, 24, 16)),
    road_ew=T("road", "-", (85, 65, 45), (32, 24, 16)),
    landing_pad=T("landing_pad", "▓", (210, 160, 80), (45, 32, 18)),
    neon=T("neon", "*", (255, 180, 80), (35, 22, 12)),
    tree=T("tree", "♣", (160, 110, 50), (55, 38, 22)),
    decor=T("plaza", "♦", (255, 150, 60), (145, 115, 80)),
)

# Station — sterile cool steel, polished metal deck.
STATION = PlanetTheme(
    floor=T("floor", "░", (180, 210, 240), (65, 85, 105)),
)

# Rotating research ring — dark open space, pale pressure-hull decking,
# cyan guidance systems, and restrained gold public fixtures.
# Epsilon Eridani b — dry super-Earth canyon settlement: ochre stone,
# pale terraced infrastructure, amber beacons, and sparse cyan utilities.
CANYON_SETTLEMENT = PlanetTheme(
    floor=T("floor", ".", (178, 136, 92), (68, 48, 34)),
    grass=T("grass", "█", (156, 105, 65), (58, 36, 26)),
    grass_accent=T("grass", ",", (94, 60, 42), (58, 36, 26)),
    plaza=T("plaza", "░", (224, 198, 148), (112, 82, 54)),
    sidewalk=T("sidewalk", "▒", (194, 170, 128), (82, 62, 44)),
    road_surface=T("road", ".", (130, 138, 150), (48, 52, 60)),
    road_ns=T("road", ":", (112, 210, 220), (34, 58, 62)),
    road_ew=T("road", "-", (112, 210, 220), (34, 58, 62)),
    landing_pad=T("landing_pad", "▓", (205, 177, 104), (54, 42, 28)),
    neon=T("neon", "*", (255, 190, 72), (62, 38, 18)),
    tree=T("tree", "♣", (126, 104, 54), (50, 36, 24)),
    decor=T("plaza", "♦", (255, 174, 70), (112, 82, 54)),
)

# Volcanic world — deep black-purple obsidian, molten orange/red lava,
# scorched basalt, and heat-glow accents.
VOLCANIC = PlanetTheme(
    floor=T("floor", ".", (48, 38, 52), (70, 58, 64)),
    grass=T("grass", "#", (55, 42, 60), (70, 58, 64)),
    grass_accent=T("grass", ",", (38, 28, 42), (70, 58, 64)),
    plaza=T("plaza", "░", (80, 60, 72), (72, 60, 65)),
    sidewalk=T("sidewalk", "▒", (90, 70, 78), (55, 42, 48)),
    road_surface=T("road", ".", (160, 120, 80), (60, 42, 30)),
    road_ns=T("road", ":", (180, 140, 90), (55, 38, 26)),
    road_ew=T("road", "-", (180, 140, 90), (55, 38, 26)),
    landing_pad=T("landing_pad", ".", (60, 80, 120), (50, 62, 85)),
    neon=T("neon", "*", (255, 120, 40), (72, 48, 40)),
    tree=T("tree", "\u2666", (180, 60, 20), (72, 48, 40)),
    decor=T("plaza", "\u2666", (255, 100, 30), (72, 60, 65)),
)

RING_STATION = PlanetTheme(
    floor=T("ring_deck", ".", (172, 205, 220), (48, 68, 82)),
    grass=T("ring_deck", ".", (172, 205, 220), (48, 68, 82)),
    grass_accent=T("ring_deck", ",", (100, 145, 160), (38, 56, 70)),
    plaza=T("city_plaza", "░", (220, 235, 225), (76, 105, 112)),
    sidewalk=T("sidewalk", "▒", (155, 205, 215), (42, 70, 84)),
    road_surface=T("road", ".", (100, 220, 235), (24, 48, 62)),
    road_ns=T("road", ":", (120, 235, 245), (20, 42, 56)),
    road_ew=T("road", "-", (120, 235, 245), (20, 42, 56)),
    landing_pad=T("landing_pad", "▓", (125, 230, 245), (28, 58, 76)),
    neon=T("neon", "*", (110, 245, 255), (22, 58, 72)),
    tree=T("tree", "o", (115, 205, 190), (34, 62, 66)),
    decor=T("plaza", "♦", (255, 205, 105), (76, 105, 112)),
)
