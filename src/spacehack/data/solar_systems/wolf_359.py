"""Wolf 359 — a dim red dwarf system on the frontier of charted
space. Quiet, empty, the last gate before the edge.

Wolf 359 is one of the faintest stars in Earth's night sky at
~7.8 ly distance. The star is a small dim red dwarf (7x7
footprint). Only a single barren rocky world orbits here.

Despite its grim reputation, no pirates patrol these empty
reaches — the real danger lies beyond Luyten's Star, in the
uncharted void past the militia blockade.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Wolf 359 — dim red dwarf, 7x7 footprint. Small, faint,
    # menacing palette.
    solar_module.Planet(
        id="sun", name="Wolf 359",
        char="O", fg=(255, 80, 50),                  # deep cool red
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A dim red dwarf — one of the faintest stars in the sky.",
    ),
    # A single barren rocky world — dark, airless.
    solar_module.Planet(
        id="wolf_b", name="Wolf 359 b",
        char="p", fg=(80, 60, 50),                   # very dim brown
        pos=world.Position(55, 55), width=2, height=2,
        description="A dark, airless rock barely reflecting the star's dim glow.",
    ),
)


# Two Jump Points — west to Tau Ceti, east to Luyten's Star.
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_tau_ceti",
        name="Tau Ceti Gate",
        char=">",
        fg=(255, 235, 140),                          # golden-yellow (Tau Ceti palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(( "tau_ceti", "jump_wolf_359"),),
        description="A humming FTL gate facing Tau Ceti.",
    ),
    JumpPoint(
        id="jump_luyten_star",
        name="Luyten's Star Gate",
        char="<",
        fg=(220, 180, 130),                          # warm brownish (dim star palette)
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(( "luyten_star", "jump_wolf_359"),),
        description="A humming FTL gate facing Luyten's Star.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="wolf_359")


SYSTEM: SolarSystem = SolarSystem(
    id="wolf_359",
    name="Wolf 359",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),
    stars=_stars,
    pirate_chance=0.5,
    pirate_density=4,
)
