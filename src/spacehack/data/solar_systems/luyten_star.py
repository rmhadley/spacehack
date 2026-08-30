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

A Restricted Sector sits on the far right of the map — a
placeholder for whatever lurks beyond the blockade.  Four static
Militia Blockade ships patrol a vertical column through the
centre-right of the system, forming an impassable picket line
that enforces the blockade.

There is only one Jump Point — the gate back to Wolf 359.
Luyten's Star is a dead end by design: the edge of the map.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import EnemySpawn, JumpPoint, SolarSystem, StationSpec


_planets: tuple[solar_module.Planet, ...] = (
    # Luyten's Star — dim red dwarf, 7x7 footprint (matches
    # Wolf 359 in size, slightly different hue).
    solar_module.Planet(
        id="sun", name="Luyten's Star",
        char="O", fg=(255, 90, 60),                  # warm red dwarf
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A dim red dwarf - the last star on the chart.",
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
        description="A dark, airless world - utterly lifeless.",
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
            "federation space - no ships past this point without authorisation."
        ),
    ),
    StationSpec(
        id="luyt_blockade_south",
        name="Blockade Station South",
        char="#",
        fg=(130, 230, 220),
        pos=world.Position(130, 115),
        width=3, height=3,
        city_planet_id="blockade_south",
        description=(
            "A secondary quarantine checkpoint - sealed inspection decks "
            "watch the deep-space corridor beyond the federation boundary."
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
        description="A humming FTL gate facing Wolf 359 - the road back to charted space.",
    ),
)


# Restricted Sector — a placeholder marker at the far right of the
# system map.  Painted as a non-sun planet so it appears as a
# distinct body on the map that the player can bump (future: see
# what's behind the blockade).
_restricted_sector = solar_module.Planet(
    id="restricted_sector",
    name="RESTRICTED SECTOR",
    char="#",
    fg=(255, 60, 60),                                 # bright red — warning
    pos=world.Position(183, 62),
    width=6, height=6,
    description=(
        "A heavily restricted sector beyond federation space - "
        "no ships authorised past this point."
    ),
)


# Static militia picket line — a vertical column of militia ships
# that enforces the blockade.  Squad shares a single squad_id so
# they all join combat together when the player engages any one of
# them.  Positioned between the star (100, 70 7x7) and the
# Restricted Sector (183, 62 6x6), forming a wall from y=25 to
# y=115.
_static_enemies: tuple[EnemySpawn, ...] = (
    EnemySpawn(
        enemy_id="militia_blockade",
        pos=world.Position(150, 25),
        squad_id="luyt_blockade_picket",
    ),
    EnemySpawn(
        enemy_id="militia_blockade",
        pos=world.Position(150, 55),
        squad_id="luyt_blockade_picket",
    ),
    EnemySpawn(
        enemy_id="militia_blockade",
        pos=world.Position(150, 85),
        squad_id="luyt_blockade_picket",
    ),
    EnemySpawn(
        enemy_id="militia_blockade",
        pos=world.Position(150, 115),
        squad_id="luyt_blockade_picket",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="luyten_star")


SYSTEM: SolarSystem = SolarSystem(
    id="luyten_star",
    name="Luyten's Star",
    width=200,
    height=140,
    planets=_planets + (_restricted_sector,),
    jump_points=_jump_points,
    stations=_stations,
    stars=_stars,
    enemies=_static_enemies,
    # Pirates are scarce here — the militia blockade keeps them out.
    # A few merchants may pass through with military escort cargo.
    npc_spawn_chance=0.2,
    npc_spawn_table=(("merchant_hauler", 0.3),),
    npc_density=1,
    patrol_density=(4, 5),
    derelict_spawn_chance=0.04,
)
