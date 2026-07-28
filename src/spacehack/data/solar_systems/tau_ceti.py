"""Tau Ceti — a G-type system three hops from Sol, reachable through
Procyon. A refueling depot at the outer ice giant gives the player
a chance to refuel before pushing into the dangerous Wolf 359
sector.

Tau Ceti is ~12 ly from Earth and considered one of the most
Earth-like star systems in the real neighbourhood. The system has
four bodies: the star, a habitable-zone rocky planet (Tau Cet b),
an inner rocky world (Tau Cet c), and an outer ice giant (Tau Cet d)
with an orbital refueling depot.

The depot at Tau Cet d is the last refueling opportunity before
Wolf 359 — any ship pushing further out should top off here.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem, station_near


_planets: tuple[solar_module.Planet, ...] = (
    # Tau Ceti — G-type main-sequence, 11x11 (same size class as
    # Epsilon Eridani, slightly warmer palette).
    solar_module.Planet(
        id="sun", name="Tau Ceti",
        char="O", fg=(255, 235, 140),                # warm golden-yellow
        pos=world.Position(100, 70), width=11, height=11,
        sun=True,
        description="A G-type main-sequence star — one of Sol's nearest cousins.",
    ),
    # Tau Cet b — habitable-zone rocky planet, 2x2.
    solar_module.Planet(
        id="tc_b", name="Tau Cet b",
        char="p", fg=(140, 200, 180),
        pos=world.Position(55, 45), width=2, height=2,
        description="A temperate rocky world in the habitable zone.",
    ),
    # Tau Cet c — inner rocky world, 2x2.
    solar_module.Planet(
        id="tc_c", name="Tau Cet c",
        char="p", fg=(180, 140, 100),
        pos=world.Position(130, 55), width=2, height=2,
        description="A hot rocky world close to Tau Ceti.",
    ),
    # Tau Cet d — outer ice giant, 4x4, with the refueling depot.
    solar_module.Planet(
        id="tc_d", name="Tau Cet d",
        char="P", fg=(170, 210, 240),
        pos=world.Position(150, 100), width=4, height=4,
        description="A cold ice giant — the system's outermost planet.",
    ),
)


# Refueling Depot at Tau Cet d — built with station_near() so the
# position is computed from the planet's footprint.
_tc_d = [p for p in _planets if p.id == "tc_d"][0]
_stations = (station_near(
    _tc_d, east=9, north=3, station_id="tc_depot",
    name="Tau Cet Refueling Depot",
    description=(
        "A refueling depot in orbit around Tau Cet d — the "
        "last stop before the Wolf 359 frontier."
    ),
),)


_jump_points: tuple[JumpPoint, ...] = (
    # Western gate -> Procyon.
    JumpPoint(
        id="jump_procyon",
        name="Procyon Gate",
        char=">",
        fg=(200, 220, 255),                        # cool blue-white (Procyon palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(( "procyon", "jump_tau_ceti"),),
        description="A humming FTL gate facing Procyon.",
    ),
    # Eastern gate -> Wolf 359.
    JumpPoint(
        id="jump_wolf_359",
        name="Wolf 359 Gate",
        char="<",
        fg=(255, 100, 70),                         # cool red (red dwarf palette)
        pos=world.Position(193, 70),
        width=2, height=2,
        connects_to=(( "wolf_359", "jump_tau_ceti"),),
        description="A humming FTL gate facing Wolf 359.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="tau_ceti")


SYSTEM: SolarSystem = SolarSystem(
    id="tau_ceti",
    name="Tau Ceti",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=_stations,
    stars=_stars,
    npc_spawn_chance=0.7,
    npc_spawn_table=(("pirate_scout", 0.7), ("pirate_raider", 0.5), ("merchant_hauler", 0.3)),
    npc_density=4,
)
