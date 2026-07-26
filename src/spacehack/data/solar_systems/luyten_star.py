"""Luyten's Star — the edge of charted federation space. The last
system before the deep, dangerous, uncharted beyond.

A dim red dwarf similar to Wolf 359 but quieter — no pirate
patrols here, because the Militia Blockade keeps this line.
Two blockade stations serve as the federation's border checkpoint.
Any ship heading past Luyten's Star leaves federation protection
behind.

The system has one dim red dwarf and two barren rocky planets.
The Blockade Stations use a dedicated PlanetSpec with a Militia
Blockade Officer NPC (see data/planets/blockade.py).

There is only one Jump Point — the gate back to Wolf 359.
Luyten's Star is a dead end by design: the edge of the map.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import JumpPoint, SolarSystem, StationSpec


_planets: tuple[solar_module.Planet, ...] = (
    # Luyten's Star — dim red dwarf, 7x7 footprint (matches
    # Wolf 359 in size, slightly different hue).
    solar_module.Planet(
        id="sun", name="Luyten's Star",
        char="O", fg=(255, 90, 60),                  # warm red dwarf
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A dim red dwarf — the last star on the chart.",
    ),
    # Luyten b — a small, cold rocky world.
    solar_module.Planet(
        id="luyt_b", name="Luyten b",
        char="p", fg=(130, 90, 70),
        pos=world.Position(45, 50), width=2, height=2,
        description="A cold, barren rock on the edge of known space.",
    ),
    # Luyten c — another barren world, outer orbit.
    solar_module.Planet(
        id="luyt_c", name="Luyten c",
        char="p", fg=(100, 80, 60),
        pos=world.Position(150, 95), width=2, height=2,
        description="A dark, airless world — utterly lifeless.",
    ),
)


# Militia Blockade Stations — use the dedicated "blockade"
# PlanetSpec (see data/planets/blockade.py) which has the
# blockade_officer NPC built in.
_stations: tuple[StationSpec, ...] = (
    StationSpec(
        id="luyt_blockade_north",
        name="Blockade Station North",
        char="#",
        fg=(130, 230, 220),                          # teal — matches militia colour.
        pos=world.Position(70, 22),
        width=3, height=3,
        city_planet_id="blockade",
        description=(
            "A militia blockade station guarding the edge of "
            "federation space — no ships past this point without authorisation."
        ),
    ),
    StationSpec(
        id="luyt_blockade_south",
        name="Blockade Station South",
        char="#",
        fg=(130, 230, 220),
        pos=world.Position(130, 115),
        width=3, height=3,
        city_planet_id="blockade",
        description=(
            "A secondary militia checkpoint — eyes on the deep-space "
            "corridor beyond the federation boundary."
        ),
    ),
)


# Single Jump Point — back to Wolf 359. Dead end.
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_wolf_359",
        name="Wolf 359 Gate",
        char=">",
        fg=(255, 80, 50),                            # cool red (Wolf 359 palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(( "wolf_359", "jump_luyten_star"),),
        description="A humming FTL gate facing Wolf 359 — the road back to charted space.",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="luyten_star")


SYSTEM: SolarSystem = SolarSystem(
    id="luyten_star",
    name="Luyten's Star",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=_stations,
    stars=_stars,
    pirate_chance=0.1,
    pirate_density=2,
)
