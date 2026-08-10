"""Epsilon Indi — the middle of the North Arm, two jumps from Sol.

A K-type orange dwarf ~11.8 ly from Sol, notable for hosting a
brown dwarf companion (Indi c) in a wide orbit. Indi b is a
temperate agricultural colony that feeds the shipyards on
Cygni b — the two planets trade heavily along this arm.

Reachable from 61 Cygni in the west; the arm continues east to
Groombridge 34.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Epsilon Indi — K-type orange dwarf, 7x7 footprint. Slightly
    # warmer than 61 Cygni so the two stars read as distinct.
    solar_module.Planet(
        id="sun", name="Epsilon Indi",
        char="O", fg=(255, 205, 120),                # warm amber
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A K-type orange dwarf at the heart of the North Arm.",
    ),
    # Indi b — the agricultural colony, landable.
    solar_module.Planet(
        id="indi_b", name="Indi b",
        char="p", fg=(120, 180, 130),                # soft green — farmland
        pos=world.Position(60, 50), width=2, height=2,
        description="A temperate world of broad farmlands feeding the arm's shipyards.",
    ),
    # Indi c — the brown dwarf companion, unlandable.
    solar_module.Planet(
        id="indi_c", name="Indi c",
        char="d", fg=(90, 70, 90),                   # dim brown-grey
        pos=world.Position(150, 95), width=2, height=2,
        description="A dim brown dwarf - a failed star in a wide orbit.",
    ),
)


# Two Jump Points — west to 61 Cygni, east to Groombridge 34.
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_cygni",
        name="61 Cygni Gate",
        char=">",
        fg=(255, 180, 90),                           # amber (matches 61 Cygni)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(("cygni", "jump_epsilon_indii"),),
        description="A humming FTL gate facing 61 Cygni - back toward Sol.",
    ),
    JumpPoint(
        id="jump_groombridge",
        name="Groombridge 34 Gate",
        char="<",
        fg=(255, 100, 70),                           # cool red (M-type palette)
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(("groombridge", "jump_epsilon_indii"),),
        description="A humming FTL gate facing Groombridge 34 - the arm's end.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="epsilon_indii")


SYSTEM: SolarSystem = SolarSystem(
    id="epsilon_indii",
    name="Epsilon Indi",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),
    stars=_stars,
    npc_spawn_chance=0.55,
    npc_spawn_table=(("merchant_hauler", 0.5), ("pirate_scout", 0.4), ("pirate_raider", 0.2)),
    npc_density=3,
    patrol_density=(1, 1),
    derelict_spawn_chance=0.05,
)
