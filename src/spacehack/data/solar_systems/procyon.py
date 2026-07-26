"""Procyon — a binary star system serving as the crossroads of the
deep-space chain and the shortcut back to Sol-space.

Procyon A (F-type white star) and Procyon B (white dwarf companion)
are the visual signature. Three gates connect it to Epsilon Eridani
(west), Tau Ceti (east), and Vega (north shortcut) — making it an
ideal refueling / navigation pivot for deep-space traders.

The Vega shortcut creates a loop: players can go
Sol -> Epsilon Eridani -> Procyon -> Vega instead of backtracking
through Barnard's Star, giving multi-hop trade routes a meaningful
choice between the short safe route vs. the deeper route.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Procyon A — white F-type star, 11x11 (similar to Epsilon
    # Eridani's star, different palette: cool white vs warm yellow).
    solar_module.Planet(
        id="procyon_a", name="Procyon A",
        char="O", fg=(200, 220, 255),                # cool bluish-white
        pos=world.Position(85, 60), width=11, height=11,
        sun=True,
        description="A bright white F-type main-sequence star.",
    ),
    # Procyon B — white dwarf companion, tiny 2x2 footprint
    # relative to Procyon A, positioned to the south-east.
    solar_module.Planet(
        id="procyon_b", name="Procyon B",
        char="o", fg=(220, 240, 255),
        pos=world.Position(130, 95), width=2, height=2,
        sun=True,
        description="A faint white dwarf companion.",
    ),
    # A few flavour planets for visual depth.
    solar_module.Planet(
        id="proc_planet_1", name="Procyon b",
        char="p", fg=(180, 160, 130),
        pos=world.Position(45, 115), width=2, height=2,
        description="A scorched rocky world orbiting Procyon A.",
    ),
    solar_module.Planet(
        id="proc_planet_2", name="Procyon c",
        char="P", fg=(190, 200, 215),
        pos=world.Position(150, 40), width=3, height=3,
        description="An icy body in the system's outer reach.",
    ),
)


# Three gates — the triple-crossroads design. Each gate's fg
# matches the destination palette so the player can read colours
# at a glance.
_jump_points: tuple[JumpPoint, ...] = (
    # Western gate -> Epsilon Eridani.
    JumpPoint(
        id="jump_epsilon_eridani",
        name="Epsilon Eridani Gate",
        char=">",
        fg=(255, 230, 150),                        # warm yellow (EE palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(( "epsilon_eridani", "jump_procyon"),),
        description="A humming FTL gate facing Epsilon Eridani.",
    ),
    # Eastern gate -> Tau Ceti.
    JumpPoint(
        id="jump_tau_ceti",
        name="Tau Ceti Gate",
        char="<",
        fg=(240, 220, 130),                        # golden-yellow (Tau Ceti palette)
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(( "tau_ceti", "jump_procyon"),),
        description="A humming FTL gate facing Tau Ceti.",
    ),
    # Northern gate (shortcut) -> Vega. Pale blue-white matches
    # Vega's cool star palette.
    JumpPoint(
        id="jump_vega",
        name="Vega Gate",
        char="^",
        fg=(200, 220, 255),                        # cool blue-white (Vega palette)
        pos=world.Position(100, 2),
        width=2, height=2,
        connects_to=(( "vega", "jump_procyon"),),
        description="A humming FTL gate facing Vega.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="procyon")


SYSTEM: SolarSystem = SolarSystem(
    id="procyon",
    name="Procyon",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),
    stars=_stars,
    npc_spawn_chance=0.5,
    npc_spawn_table=(("pirate_scout", 0.7), ("pirate_raider", 0.5), ("merchant_hauler", 0.2)),
    npc_density=4,
)
