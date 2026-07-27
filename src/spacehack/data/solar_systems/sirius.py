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

A Binary Research Station (:class:`spacehack.data.planets.sirius_station`)
orbits between the two stars, giving the system a single landable port.
Map dims
deliberately MATCH the other 200x140 systems so the navigation
UX stays consistent across the universe.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem, StationSpec


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
    stations=(
        # Binary Research Station — between Sirius A (100,70, 15x15)
        # and Sirius B (35,35, 3x3). Positioned at the midpoint gap
        # so it reads as 'between the two stars' on the system map.
        StationSpec(
            id="sirius_binary_station",
            name="Binary Station",
            char="#",
            fg=(180, 210, 240),              # cool steel-blue
            pos=world.Position(65, 50),
            width=3, height=3,
            city_planet_id="sirius_station",
            description=(
                "A solar research station suspended between the "
                "binary pair — studying the dance of two stars."
            ),
        ),
    ),
    stars=_stars,
    npc_spawn_chance=0.5,
    npc_spawn_table=(("merchant_hauler", 0.6), ("pirate_scout", 0.4), ("pirate_raider", 0.2)),
    npc_density=2,
)
