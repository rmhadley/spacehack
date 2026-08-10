"""Groombridge 34 — the end of the North Arm, three jumps from Sol.

Groombridge 34 is an M-type red dwarf binary ~11.6 ly from Sol.
The arm runs out here: beyond the gate is nothing but dark. The
mining colony on Groombridge 34 b is rough, independent territory —
prospectors work the ore fields and the local bar doubles as a
bounty office. Pirates run loose this far out; militia patrols
don't come here.

A single Jump Point leads back to Epsilon Indi. Dead end by
design, mirroring Luyten's Star at the end of the deep corridor.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Groombridge 34 — M-type red dwarf, 7x7 footprint. Deep cool
    # red matches the other red dwarfs (Wolf 359, Luyten's Star).
    solar_module.Planet(
        id="sun", name="Groombridge 34",
        char="O", fg=(255, 90, 60),                  # cool red
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A dim red dwarf - the last star on the North Arm.",
    ),
    # Groombridge 34 b — the mining colony, landable.
    solar_module.Planet(
        id="groom_b", name="Groombridge 34 b",
        char="p", fg=(110, 100, 90),                 # dim rocky brown
        pos=world.Position(55, 55), width=2, height=2,
        description="A rough mining world at the end of the arm - no laws, no militia.",
    ),
)


# Single Jump Point — back to Epsilon Indi. Dead end.
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_epsilon_indii",
        name="Epsilon Indi Gate",
        char=">",
        fg=(255, 100, 70),                           # cool red (red dwarf palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(("epsilon_indii", "jump_groombridge"),),
        description="A humming FTL gate facing Epsilon Indi - the road back to charted space.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="groombridge")


SYSTEM: SolarSystem = SolarSystem(
    id="groombridge",
    name="Groombridge 34",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),
    stars=_stars,
    npc_spawn_chance=0.75,
    npc_spawn_table=(("pirate_scout", 0.9), ("pirate_raider", 0.6), ("merchant_hauler", 0.2)),
    npc_density=5,
    patrol_density=(0, 0),
    derelict_spawn_chance=0.07,
)
