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
placeholder for whatever lurks beyond the blockade.  The Militia
Blockade mans a vertical column of picket stations through the
centre-right of the system — a full watch of ten ships, thinning
to four on the maintenance week (doc 41 phase 2's watchbill on
the SensorColumn).

There is only one Jump Point — the gate back to Wolf 359.
Luyten's Star is a dead end by design: the edge of the map.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import EnemySpawn, JumpPoint, SensorColumn, SolarSystem, StationSpec, WatchStation


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


# Static militia picket line — the watchbill's stations (doc 41
# phase 2).  Every row shares one squad_id so they all join combat
# together when the player engages any one of them.  The FULL watch
# is ten stations at spacing 14 (detect 7 x 2 — edge-to-edge
# physical coverage with zero slack); the THIN watch (the
# maintenance week) is the shipped four, whose wide gaps are the
# ghost window by design.  The SensorColumn's watchbill below says
# which roster stands when; rows here are just the posts.
_NORTH = "luyt_blockade_north"
_SOUTH = "luyt_blockade_south"
_static_enemies: tuple[EnemySpawn, ...] = (
    # Full watch — y = 7, 21, ..., 133 (Luyten c at (150, 95-96)
    # checked clear of every station).
    *(EnemySpawn(
        enemy_id="militia_blockade",
        pos=world.Position(150, _y),
        squad_id="luyt_blockade_picket",
    ) for _y in (7, 21, 35, 49, 63, 77, 91, 105, 119, 133)),
    # Thin watch — the shipped four.
    *(EnemySpawn(
        enemy_id="militia_blockade",
        pos=world.Position(150, _y),
        squad_id="luyt_blockade_picket",
    ) for _y in (25, 55, 85, 115)),
)


_stars = solar_module.make_stars(200, 140, seed="luyten_star")


# The Line (doc 41): the blockade is a SYSTEM, not a wall — an
# edge-to-edge broadcast sweep on the pickets' column. Any hull
# crossing x=150 with a live or spoofed transponder is swept; dark
# hulls only a picket physically spots. rank_rep 80: blockade rank
# on a worn face's sheet (data — user-dictatable). Message wording
# user-dictated 2026-09-09 (playtest round 1); {id} = the broadcast
# registration, or "Unidentified hull" when nothing resolves.
_sensor_column = SensorColumn(
    x=150,
    label="Militia Blockade",
    squad_id="luyt_blockade_picket",
    picket_enemy_id="militia_blockade",
    rank_rep=80,
    hail_lines=(
        "{id}, this is forbidden space. You're not on our list, "
        "turn back now or else.",
    ),
    manifest_lines=(
        "{id}, this is forbidden space. Your ID checks out, "
        "continue through.",
    ),
    rank_lines=(
        "{id}, this is forbidden space. Oh, sorry. Didn't recognize "
        "your ID, sir. Continue through.",
    ),
    service_lines=(
        "{id}, this is forbidden space. Your ID checks out, "
        "this time. Continue through.",
    ),
    # The watchbill (phase 2): 7-day shifts, full x3 then a thin
    # maintenance week. Leads are days-before-boundary the relief
    # launches from its base = the CEILING of its measured transit
    # (real find_path base-dock -> station) at the picket's own
    # hull speed 9 (doc 44 phase 4 re-measure; the phase-1 leads
    # assumed effective speed 8). Self-verifying:
    # test_launch_leads_match_the_measured_transits recomputes the
    # table, so these numbers cannot drift from the map. North
    # serves y <= 35 (measured crossover y ~= 36), South the rest.
    shift_days=7,
    watch_cycle=("full", "full", "full", "thin"),
    full_watch=(
        WatchStation(y=7, lead_days=9, base_id=_NORTH),
        WatchStation(y=21, lead_days=9, base_id=_NORTH),
        WatchStation(y=35, lead_days=9, base_id=_NORTH),
        WatchStation(y=49, lead_days=8, base_id=_SOUTH),
        WatchStation(y=63, lead_days=6, base_id=_SOUTH),
        WatchStation(y=77, lead_days=5, base_id=_SOUTH),
        WatchStation(y=91, lead_days=3, base_id=_SOUTH),
        WatchStation(y=105, lead_days=2, base_id=_SOUTH),
        WatchStation(y=119, lead_days=2, base_id=_SOUTH),
        WatchStation(y=133, lead_days=2, base_id=_SOUTH),
    ),
    thin_watch=(
        WatchStation(y=25, lead_days=9, base_id=_NORTH),
        WatchStation(y=55, lead_days=7, base_id=_SOUTH),
        WatchStation(y=85, lead_days=4, base_id=_SOUTH),
        WatchStation(y=115, lead_days=2, base_id=_SOUTH),
    ),
)


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
    sensor_column=_sensor_column,
    # Pirates are scarce here — the militia blockade keeps them out.
    # A few merchants may pass through with military escort cargo.
    npc_spawn_chance=0.2,
    npc_spawn_table=(("merchant_hauler", 0.3),),
    npc_density=1,
    patrol_density=(4, 5),
    derelict_spawn_chance=0.04,
)
