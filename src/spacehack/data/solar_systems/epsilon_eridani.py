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

from . import JumpPoint, SolarSystem, station_near


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


# Refueling Depot at ε Eri c — built with the station_near()
# helper so the position is computed from the planet's footprint.
_eri_c = [p for p in _planets if p.id == "eri_c"][0]
_stations = (station_near(
    _eri_c, east=9, north=3, station_id="eri_depot",
    name="ε Eri Refueling Depot",
    description=(
        "A refueling outpost in high orbit around ε Eri c — "
        "the last gas stop before the deep chain."
    ),
),)


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


_stars = solar_module.make_stars(200, 140, seed="epsilon_eridani")


SYSTEM: SolarSystem = SolarSystem(
    id="epsilon_eridani",
    name="Epsilon Eridani",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=_stations,
    stars=_stars,
    npc_spawn_chance=0.35,
    npc_spawn_table=(("pirate_scout", 0.5), ("pirate_raider", 0.3), ("merchant_hauler", 0.3)),
    npc_density=3,
)
