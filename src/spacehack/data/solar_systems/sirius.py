"""Sirius — the brightest star in the night sky, reachable only
through Vega in this iteration (single-hop system).

The Sirius A + B binary is the visual signature of this system.
A is the dominant body (15x15 - bigger than Sol) so the player
feels 'I went somewhere far' when they arrive. A faint white
dwarf companion (Sirius B) sits close to A so the binary
relationship reads at a glance.

The only Jump Point is on the WEST, leading back to Vega. A
future iteration may add a gate to a deep-space exploration
sector (or sneak-peak a hub system), but for v1 Sirius is a
dead-end reachable only through Vega.

A :class:`spacehack.data.planets.PlanetSpec` is NOT registered
for either Sirius body, so neither is landable. Map dims
deliberately MATCH the other 200x140 systems so the navigation
UX stays consistent across the universe.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Sirius A — dominant blue-white A1V star, 15x15 footprint.
    # Larger than any Sol-system body so the player feels 'I am
    # somewhere exotic' on arrival.
    solar_module.Planet(
        id="sun", name="Sirius A",
        char="O", fg=(180, 200, 255),
        pos=world.Position(100, 70), width=15, height=15,
        sun=True,
        description="A brilliant blue-white main-sequence star.",
    ),
    # Sirius B — small white dwarf companion, 3x3 (tiny vs. A).
    solar_module.Planet(
        id="sirius_b", name="Sirius B",
        char="o", fg=(220, 240, 255),
        pos=world.Position(35, 35), width=3, height=3,
        sun=True,
        description="A faint white dwarf companion.",
    ),
)


# Single Jump Point on the west edge leading back to Vega.
# '>' chevron reads as "out toward Vega" (the only outgoing path).
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_vega",
        name="Vega Gate",
        char=">",
        fg=(220, 240, 255),                        # pale blue-white (Vega adjacency)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(("vega", "jump_sirius"),),
        description="A humming FTL gate facing Vega.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="sirius")


SYSTEM: SolarSystem = SolarSystem(
    id="sirius",
    name="Sirius",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),              # no stations in Sirius this iteration.
    stars=_stars,
    pirate_chance=0.15,
    pirate_density=2,
)
