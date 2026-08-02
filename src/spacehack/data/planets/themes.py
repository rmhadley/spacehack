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

def derive_theme(
    *,
    floor: tuple[int, int, int] = (200, 180, 140),
    grass: tuple[int, int, int] = (140, 100, 70),
    accent: tuple[int, int, int] = (255, 180, 80),
    **overrides,
) -> PlanetTheme:
    """Build a complete :class:`PlanetTheme` from 3 key colour anchors.

    The ``floor``, ``grass``, and ``accent`` colours control the visual
    direction (warm browns, cool blues, dusty reds, etc.). All other tiles
    are derived from these anchors with sensible brightness / blend curves
    so the result looks coherent without hand-tuning every tile.

    Pass ``**overrides`` to replace any specific tile after derivation::

        theme = derive_theme(
            floor=(180, 210, 240), grass=(200, 220, 245), accent=(150, 230, 255),
            # Override the road tiles with a darker custom palette
            road_surface=T("road", ".", (90, 120, 155), (35, 50, 70)),
            road_ns=T("road", ":", (75, 100, 135), (28, 42, 60)),
        )
    """
    _gbg = _darken(grass, 0.38)
    _road_fg = _darken(grass, 0.52)
    _road_bg = _darken(grass, 0.25)
    _plaza_bg = _darken(_blend(grass, (255, 245, 230), 0.5), 0.6)

    base = PlanetTheme(
        floor=T("floor", "░", floor, _darken(floor, 0.42)),
        grass=T("grass", "█", grass, _gbg),
        # Accent bg matches the grass field's visible fg (full-bleed █) and
        # the comma glyph itself is darkened (half the field colour) so it
        # reads as a clear texture mark on the same field.
        grass_accent=T("grass", ",", _darken(grass, 0.5), grass),
        plaza=T("plaza", "░", _blend(grass, (255, 245, 220), 0.55), _plaza_bg),
        sidewalk=T("sidewalk", "▒", _darken(_blend(grass, (190, 195, 210), 0.5), 0.55), _darken(_blend(grass, (190, 195, 210), 0.5), 0.32)),
        road_surface=T("road", ".", _road_fg, _road_bg),
        road_ns=T("road", ":", _darken(_road_fg, 0.82), _darken(_road_bg, 0.85)),
        road_ew=T("road", "-", _darken(_road_fg, 0.82), _darken(_road_bg, 0.85)),
        landing_pad=T("landing_pad", "▓", _blend(grass, (150, 220, 255), 0.6), _darken(grass, 0.22)),
        neon=T("neon", "*", accent, _darken(accent, 0.15)),
        tree=T("tree", "♣", _darken(grass, 0.78), _darken(grass, 0.32)),
        decor=T("plaza", "♦", accent, _plaza_bg),
    )
    if overrides:
        return _replace(base, **overrides)
    return base


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
    grass_accent=T("grass", ",", (90, 40, 25), (180, 80, 50)),
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

# Mining outpost — deep reds, dusty oranges, scorched browns.
DESERT = PlanetTheme(
    floor=T("floor", "░", (150, 80, 50), (55, 35, 20)),
    grass=T("grass", "█", (140, 60, 40), (50, 25, 15)),
    grass_accent=T("grass", ",", (70, 30, 20), (140, 60, 40)),
    plaza=T("plaza", "░", (170, 110, 70), (120, 75, 50)),
    sidewalk=T("sidewalk", "▒", (100, 55, 35), (45, 25, 15)),
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
    grass_accent=T("grass", ",", (45, 90, 35), (90, 180, 70)),
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
    grass_accent=T("grass", ",", (70, 95, 110), (140, 190, 220)),
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
    grass_accent=T("grass", ",", (100, 110, 122), (200, 220, 245)),
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

# Rugged settlement — warm earth tones, dry browns, pioneer amber.
WARM_EARTH = PlanetTheme(
    floor=T("floor", "░", (170, 140, 100), (65, 50, 35)),
    grass=T("grass", "█", (150, 110, 60), (55, 38, 22)),
    grass_accent=T("grass", ",", (75, 55, 30), (150, 110, 60)),
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
