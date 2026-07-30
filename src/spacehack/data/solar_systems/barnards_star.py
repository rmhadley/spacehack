"""Barnard's Star — a cool red dwarf system reachable from
Alpha Centauri and the gateway to Vega.

The fourth-nearest star system to Sol at ~6 ly. v1 ships the
star + two planets + a western gate to Alpha Centauri
(reciprocal of alpha_centauri/jump_barnards_star) + an eastern
gate to Vega (reciprocal of vega/jump_barnards_star). No
landable bodies yet — Barnard's is a transit system only.

The star is a small red dwarf (9x9 footprint) so the visual
contrast vs. Sol's 13x13 G-type main-sequence star is obvious
when the player lands here for the first time. The cool red
fg (255, 100, 70) reads as 'cold ember' against the navy void
vs. Sol's warm yellow.

Bodies intentionally NOT landable in v1 (no
:class:`spacehack.data.planets.PlanetSpec` entries) — they're
for visual flavour + the connectivity hubs the navigation
graph needs.

Map dims intentionally MATCH Sol's 200x140 footprint so the
systems feel like the same size class. Jump-point positions
mirror the player's mental map: AC gate on the WEST (point of
origin from AC), Vega gate on the EAST (next hop).
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Barnard's Star: small red dwarf, 9x9 footprint. Sized down
    # from Sol's 13x13 so the size differential reads at a glance
    # against Sol and against Sirius's brighter 15x15 disk.
    solar_module.Planet(
        id="sun", name="Barnard's Star",
        char="O", fg=(255, 100, 70),                # cool red dwarf glow
        pos=world.Position(100, 70), width=9, height=9,
        sun=True,
        description="A small, cool red dwarf star.",
    ),
    # Barnard b — small rocky super-Earth (2x2). Smaller than
    # any Sol-system rocky so the player sees 'tiny inner
    # world' flavour.
    solar_module.Planet(
        id="barnards_b", name="Barnard b",
        char="p", fg=(150, 100, 100),
        pos=world.Position(70, 50), width=2, height=2,
        description="A scorched rocky super-Earth.",
    ),
    # Barnard c — cold gas giant (3x3). Outer-orbit cold tones
    # so it reads as the system's slow, far companion.
    solar_module.Planet(
        id="barnards_c", name="Barnard c",
        char="P", fg=(120, 150, 200),
        pos=world.Position(155, 95), width=3, height=3,
        description="A cold gas giant orbiting the dim star.",
    ),
)


# Jump-point FGs match the destination-system star palette so the
# player can read "this gate leads to a [colour] system" at a
# glance before reading the label. AC gate = gold (warm); Vega
# gate = pale-blue-white (cool).
_jump_points: tuple[JumpPoint, ...] = (
    # Western gate -> Alpha Centauri. 2x2 footprint centered
    # on row 70 so it's directly east of nothing important. '>'
    # chevron reads as "out toward AC" (mirror of Sol's west
    # gate -> east, but here we're heading to AC).
    JumpPoint(
        id="jump_alpha_centauri",
        name="Alpha Centauri Gate",
        char=">",
        fg=(245, 215, 110),                        # warm gold (matches AC star)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(("alpha_centauri", "jump_barnards_star"),),
        description="A humming FTL gate facing Alpha Centauri.",
    ),
    # Eastern gate -> Vega. '<' chevron reads as "out toward Vega".
    JumpPoint(
        id="jump_vega",
        name="Vega Gate",
        char="<",
        fg=(220, 240, 255),                        # pale blue-white (Vega palette)
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(("vega", "jump_barnards_star"),),
        description="A humming FTL gate facing Vega.",
    ),
)


# Sparse star sprinkle around the perimeter + a few across the
# map. Same density as the historical one-system set so the
# void read isn't different per-system.
_stars = solar_module.make_stars(200, 140, seed="barnards_star")


SYSTEM: SolarSystem = SolarSystem(
    id="barnards_star",
    name="Barnard's Star",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),              # no stations in Barnard's Star this iteration.
    stars=_stars,
    npc_spawn_chance=0.6,
    npc_spawn_table=(("pirate_scout", 0.5), ("merchant_hauler", 0.5), ("pirate_raider", 0.3)),
    npc_density=3,
    derelict_spawn_chance=0.06,
)
