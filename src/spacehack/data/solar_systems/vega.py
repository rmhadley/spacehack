"""Vega — the navigation HUB system, reachable from Sol, Barnard's
Star, and Sirius.

Vega serves as the second-out hub from Sol: three Jump Points
(Barnard's, Sirius, and a hidden Sol shortcut) point to three
different neighbour systems. Players visiting Vega see immediately
that 'this system connects to multiple others' — the on-screen
palette of three differently-coloured gates reinforces the
multi-hop navigation pattern.

Vega's star is a hot bluish-white A0V type, brighter than Sol's
G2V. The 13x13 footprint matches Sol in size but uses a paler,
cooler fg so the player reads "I'm in a hub system" the moment
they arrive.

The 'Hidden Sol Gate' at row 100 is a story-side shortcut: it
mirrors Sol's primary eastward JP back to Vega, so from Vega the
player can jump straight home as well as branching north to
Barnard's or south to Sirius. The N/S separation makes the map
read 'strategic crossroads' rather than a single-direction
corridor.

No landable bodies in v1 — Vega is a transit hub only. Map
dims MATCH the other 200x140 systems so all system map renders
share one viewport sizing contract.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Vega — bright bluish-white A0V star, 13x13 (matches Sol in
    # size, contrasts in palette).
    solar_module.Planet(
        id="sun", name="Vega",
        char="O", fg=(200, 220, 255),                # cool bluish-white
        pos=world.Position(100, 70), width=13, height=13,
        sun=True,
        description="A bright bluish-white main-sequence star.",
    ),
    # Vega b — large gas giant (5x5) on the southern rim.
    solar_module.Planet(
        id="vega_b", name="Vega b",
        char="P", fg=(200, 200, 220),
        pos=world.Position(80, 105), width=5, height=5,
        description="A massive gas giant orbiting Vega.",
    ),
)


# Three Jump Points - the hub signature of this system. Each
# gate's fg matches the destination system so the player can
# read "a warm-coloured gate -> warm system" without reading
# the label.
_jump_points: tuple[JumpPoint, ...] = (
    # NORTH gate -> Barnard's Star. Red-tinted so it pops
    # against the cool Vega palette. 2x2 centered on row 40
    # (above the gas giant at row 105).
    JumpPoint(
        id="jump_barnards_star",
        name="Barnard's Star Gate",
        char=">",
        fg=(245, 100, 70),                          # warm red (Barnard's palette)
        pos=world.Position(5, 40),
        width=2, height=2,
        connects_to=(("barnards_star", "jump_vega"),),
        description="A humming FTL gate facing Barnard's Star.",
    ),
    # SOUTH gate -> Sol. Warm-gold like Sol's own gates so the
    # player feels 'this is a primary highway' rather than an
    # obscure branch.
    JumpPoint(
        id="jump_sol",
        name="Sol Gate",
        char=">",
        fg=(245, 215, 110),                        # warm gold (Sol palette)
        pos=world.Position(5, 100),
        width=2, height=2,
        connects_to=(("sol", "jump_vega"),),
        description="A humming FTL gate facing Sol.",
    ),
    # EAST gate -> Sirius. Pale-blue-white matches Sirius.
    JumpPoint(
        id="jump_sirius",
        name="Sirius Gate",
        char="<",
        fg=(180, 200, 255),                        # Sirius's palette
        pos=world.Position(193, 40),
        width=2, height=2,
        connects_to=(("sirius", "jump_vega"),),
        description="A humming FTL gate facing Sirius.",
    ),
    # SOUTH-EAST gate -> Procyon. Warm white (Procyon A's
    # F-type palette hint). Positioned at (193, 100) so it
    # sits below the Sirius gate on the east edge, matching
    # the vertical-stack pattern on Sol's east edge.
    JumpPoint(
        id="jump_procyon",
        name="Procyon Gate",
        char="<",
        fg=(200, 220, 255),                        # cool white (Procyon palette)
        pos=world.Position(193, 100),
        width=2, height=2,
        connects_to=(("procyon", "jump_vega"),),
        description="A humming FTL gate facing Procyon — the deep-space shortcut.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="vega")


SYSTEM: SolarSystem = SolarSystem(
    id="vega",
    name="Vega",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),              # no stations in Vega this iteration.
    stars=_stars,
    pirate_chance=0.35,
    pirate_density=3,
)
