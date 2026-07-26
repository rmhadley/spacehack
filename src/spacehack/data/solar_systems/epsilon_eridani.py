"""Epsilon Eridani — the first deep-space hub beyond Sol, reachable
from Sol via a dedicated gate (south-east edge of Sol's map).

Epsilon Eridani is a G-type star similar to Sol (~10.5 ly from
Earth). The system has three bodies: the star, a warm rocky world
(ε Eri b), and a cold gas giant (ε Eri c) with an orbital
refueling depot.

The Refueling Depot at ε Eri c is the player's first opportunity
to top up tanks before pushing deeper into the Procyon / Tau Ceti
chain. A single Jump Point at the eastern edge leads to Procyon.

Map dims match the other 200x140 systems so renderer layout stays
consistent across the universe.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem, StationSpec


_planets: tuple[solar_module.Planet, ...] = (
    # Epsilon Eridani — G-type main-sequence, 11x11 (slightly
    # smaller than Sol's 13x13, matching real-world size ratio).
    solar_module.Planet(
        id="sun", name="Epsilon Eridani",
        char="O", fg=(255, 230, 150),                 # warm yellow (slightly paler than Sol)
        pos=world.Position(100, 70), width=11, height=11,
        sun=True,
        description="A G-type main-sequence star similar to Sol.",
    ),
    # ε Eri b — warm rocky super-Earth in the habitable zone.
    # Small 2x2 footprint so it reads as a single-char body
    # compared to the star.
    solar_module.Planet(
        id="eri_b", name="ε Eri b",
        char="p", fg=(190, 130, 90),
        pos=world.Position(60, 50), width=2, height=2,
        description="A warm, rocky super-Earth in the habitable zone.",
    ),
    # ε Eri c — cold gas giant with the refueling depot.
    # 4x4 footprint, outer orbit.
    solar_module.Planet(
        id="eri_c", name="ε Eri c",
        char="P", fg=(160, 190, 220),
        pos=world.Position(155, 95), width=4, height=4,
        description="A cold gas giant — the system's outer sentinel.",
    ),
)


# Refueling Depot — station at ε Eri c. The player lands here
# for fuel + basic supplies before heading deeper. Uses the
# generic "depot" PlanetSpec (see data/planets/depot.py).
_stations: tuple[StationSpec, ...] = (
    StationSpec(
        id="eri_depot",
        name="ε Eri Refueling Depot",
        char="#",
        fg=(200, 200, 180),        # warm grey — reads as industrial/utility.
        pos=world.Position(168, 92),  # just east of ε Eri c (155, 95), 4x4 footprint.
        width=3, height=3,
        city_planet_id="depot",
        description=(
            "A refueling outpost in high orbit around ε Eri c — "
            "the last gas stop before the deep chain."
        ),
    ),
)


_jump_points: tuple[JumpPoint, ...] = (
    # Western gate -> Sol. Warm-gold palette matches Sol's own
    # gate colour so the player reads 'this leads to Sol'.
    JumpPoint(
        id="jump_sol",
        name="Sol Gate",
        char=">",
        fg=(245, 215, 110),                        # warm gold (Sol palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(( "sol", "jump_epsilon_eridani"),),
        description="A humming FTL gate facing Sol.",
    ),
    # Eastern gate -> Procyon. Pale white-blue (Procyon's
    # F-type palette hint).
    JumpPoint(
        id="jump_procyon",
        name="Procyon Gate",
        char="<",
        fg=(200, 220, 255),                        # pale blue-white (Procyon palette)
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(( "procyon", "jump_epsilon_eridani"),),
        description="A humming FTL gate facing Procyon.",
    ),
)


_stars: tuple[tuple[int, int], ...] = (
    # North edge
    (10, 5), (25, 12), (40, 6), (55, 11), (70, 4), (90, 9),
    (110, 5), (130, 7), (155, 10), (175, 7), (190, 12),
    # South edge
    (15, 130), (35, 125), (55, 135), (80, 132), (100, 138),
    (125, 130), (150, 134), (175, 128),
    # Side gutters
    (5, 30), (5, 50), (5, 90), (5, 110),
    (190, 30), (190, 50), (190, 90), (190, 110),
    # Mid-system
    (45, 25), (85, 25), (160, 25),
    (45, 100), (105, 100), (160, 100), (185, 115),
    (95, 50), (105, 60), (75, 75), (135, 95),
    # Stars near gates
    (8, 65), (8, 78), (4, 73), (15, 60), (15, 80),
    (188, 65), (188, 78), (195, 73), (193, 60), (193, 80),
    # Station vicinity
    (172, 88), (172, 98), (165, 86), (165, 100),
)


SYSTEM: SolarSystem = SolarSystem(
    id="epsilon_eridani",
    name="Epsilon Eridani",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=_stations,
    stars=_stars,
)
