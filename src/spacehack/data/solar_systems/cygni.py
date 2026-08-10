"""61 Cygni — the first stop on the North Arm, a new chain branching
off from Sol in the opposite direction of the deep-space corridor.

61 Cygni is a K-type binary (two orange dwarfs ~11.4 ly from Sol)
and one of the most famous nearby stars — the first star other than
the Sun to have its distance measured. The system hosts a busy
shipyard colony on Cygni b, where hulls are built for the growing
North Arm trade.

One jump from Sol via a dedicated gate (north edge of Sol's map).
From here the arm continues east to Epsilon Indi and Groombridge 34.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # 61 Cygni — K-type orange dwarf, 7x7 footprint. Warm amber
    # palette distinguishes it from Sol's yellow and the red dwarfs
    # further down the arm.
    solar_module.Planet(
        id="sun", name="61 Cygni",
        char="O", fg=(255, 190, 110),                # warm orange
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A K-type orange dwarf - the gateway to the North Arm.",
    ),
    # Cygni b — the shipyard colony, landable.
    solar_module.Planet(
        id="cygni_b", name="Cygni b",
        char="p", fg=(160, 170, 120),                # dry green-brown
        pos=world.Position(60, 50), width=2, height=2,
        description="A dry temperate world - hulls are forged in its orbital yards.",
    ),
    # Cygni c — a cold outer gas giant, unlandable.
    solar_module.Planet(
        id="cygni_c", name="Cygni c",
        char="P", fg=(170, 190, 210),
        pos=world.Position(150, 95), width=4, height=4,
        description="A cold gas giant on the system's outer edge.",
    ),
)


# Two Jump Points — west back to Sol, east to Epsilon Indi.
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_sol",
        name="Sol Gate",
        char=">",
        fg=(255, 180, 90),                           # amber (matches Sol's new gate)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(("sol", "jump_61_cygni"),),
        description="A humming FTL gate facing Sol - the road home.",
    ),
    JumpPoint(
        id="jump_epsilon_indii",
        name="Epsilon Indi Gate",
        char="<",
        fg=(255, 205, 120),                          # pale warm (K-type palette)
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(("epsilon_indii", "jump_cygni"),),
        description="A humming FTL gate facing Epsilon Indi - deeper into the arm.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="cygni")


SYSTEM: SolarSystem = SolarSystem(
    id="cygni",
    name="61 Cygni",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),
    stars=_stars,
    npc_spawn_chance=0.5,
    npc_spawn_table=(("merchant_hauler", 0.6), ("pirate_scout", 0.3)),
    npc_density=2,
    patrol_density=(1, 2),
    derelict_spawn_chance=0.04,
)
