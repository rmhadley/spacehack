"""Tau Ceti — a G-type system three hops from Sol, reachable through
Procyon. A refueling depot at the outer ice giant gives the player
a chance to refuel before pushing into the dangerous Wolf 359
sector.

Tau Ceti is ~12 ly from Earth and considered one of the most
Earth-like star systems in the real neighbourhood. The system has
four bodies: the star, a habitable-zone rocky planet (τ Cet b),
an inner rocky world (τ Cet c), and an outer ice giant (τ Cet d)
with an orbital refueling depot.

The depot at τ Cet d is the last refueling opportunity before
Wolf 359 — any ship pushing further out should top off here.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem, StationSpec


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
    # τ Cet b — habitable-zone rocky planet, 2x2.
    solar_module.Planet(
        id="tc_b", name="τ Cet b",
        char="p", fg=(140, 200, 180),
        pos=world.Position(55, 45), width=2, height=2,
        description="A temperate rocky world in the habitable zone.",
    ),
    # τ Cet c — inner rocky world, 2x2.
    solar_module.Planet(
        id="tc_c", name="τ Cet c",
        char="p", fg=(180, 140, 100),
        pos=world.Position(130, 55), width=2, height=2,
        description="A hot rocky world close to Tau Ceti.",
    ),
    # τ Cet d — outer ice giant, 4x4, with the refueling depot.
    solar_module.Planet(
        id="tc_d", name="τ Cet d",
        char="P", fg=(170, 210, 240),
        pos=world.Position(150, 100), width=4, height=4,
        description="A cold ice giant — the system's outermost planet.",
    ),
)


# Refueling Depot at τ Cet d. Reuses the generic "depot" PlanetSpec
# (see data/planets/depot.py). NPC override gives the attendant
# Tau Ceti-specific flavour text.
_stations: tuple[StationSpec, ...] = (
    StationSpec(
        id="tc_depot",
        name="τ Cet Refueling Depot",
        char="#",
        fg=(200, 200, 180),
        pos=world.Position(163, 97),    # just east of τ Cet d (150, 100), 4x4.
        width=3, height=3,
        city_planet_id="depot",
        description=(
            "A refueling depot in orbit around τ Cet d — the "
            "last stop before the Wolf 359 frontier."
        ),
    ),
)


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
    (45, 100), (105, 100), (160, 100),
    (95, 50), (105, 60), (75, 80), (135, 95),
    # Stars near gates
    (8, 65), (8, 78), (4, 73), (15, 60), (15, 80),
    (188, 65), (188, 78), (195, 73), (193, 60), (193, 80),
    # Depot vicinity
    (167, 93), (167, 103), (160, 91), (160, 105),
)


SYSTEM: SolarSystem = SolarSystem(
    id="tau_ceti",
    name="Tau Ceti",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=_stations,
    stars=_stars,
)
