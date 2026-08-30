"""Procyon c — Ice Campus: the research campus carved into the ice sheet.

A cold icy body on the outer edge of the Procyon system. The cramped
40x24 outpost grew into a proper campus: four buildings sunk into a
sheltered trench of the ice sheet around a snow-packed quad, a frozen
meltwater channel running past it, and — the signature — the mouth of
the ice caves opening at the city's east edge. The caves beneath are
the lab chain's delve site; the lab stands closest to their mouth.

Layout (140x100), authored as `proc_c_ice_campus`:

  * spaceport NW — door south onto the landing apron.
  * lab NE — door south onto the lab terrace, closest to the caves.
  * mess hall + supply depot south of the quad, doors north.
  * The Quad — central plaza with the campus beacon.
  * Frozen channel (walkable ice) + one bridge; sastrugi ridges
    texture the open ice; CAVE MOUTH at the east edge.

NPCs: the research officer stays in the lab (global catalog entry);
ambient campus staff walk the quad and terraces (PROC_C_POPULATION).
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from ...dungeon import DungeonParams
from . import PlanetSpec
from ..city_npcs import PROC_C_POPULATION
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="proc_planet_2",
    name="Procyon c",
    char="P",
    fg=(190, 200, 215),
    description="An icy body on Procyon's outer reach - a research campus carved into the ice.",
    width=140,
    height=100,
    hangar_anchor=world.Position(14, 20),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=6, x_hi=30, y_lo=6, y_hi=16,
            door_x=18, npc_id="",
        ),
        world.CityBuilding(
            label="lab", x_lo=98, x_hi=122, y_lo=10, y_hi=20,
            door_x=110, npc_id="research_officer",
        ),
        world.CityBuilding(
            label="mess", x_lo=34, x_hi=56, y_lo=70, y_hi=80,
            door_x=45, npc_id="cook", door_north=True,
        ),
        world.CityBuilding(
            label="depot", x_lo=92, x_hi=114, y_lo=74, y_hi=84,
            door_x=103, npc_id="depot_attendant", door_north=True,
        ),
    ),
    city_layout_id="proc_c_ice_campus",
    city_npc_population=PROC_C_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing apron",
            pos=world.Position(20, 22),
            destinations=("quad", "lab", "mess", "depot"),
        ),
        world.TransitStation(
            id="quad", name="The Quad", district="campus center",
            pos=world.Position(75, 52),
            destinations=("spaceport", "lab", "mess", "depot"),
        ),
        world.TransitStation(
            id="lab", name="Research Lab", district="lab terrace",
            pos=world.Position(108, 26),
            destinations=("spaceport", "quad", "mess", "depot"),
        ),
        world.TransitStation(
            id="mess", name="Mess Hall", district="south campus",
            pos=world.Position(45, 64),
            destinations=("spaceport", "quad", "lab", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Supply Depot", district="far bank",
            pos=world.Position(103, 70),
            destinations=("spaceport", "quad", "lab", "mess"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "proc_c_spaceport_interior"),
        ("lab", "proc_c_lab_interior"),
        ("mess", "proc_c_mess_interior"),
        ("depot", "proc_c_depot_interior"),
    ),
    showroom_ships=(
        ("scout", -6, -2),
        ("cruiser", 0, -2),
        ("freighter", 6, -2),
    ),
    npc_overrides=(
        (
            "cook",
            npc_module.NPC(
                id="cook",
                name="Campus Cook",
                guild="mess",
                char="c",
                fg=(240, 200, 150),
                flavor_text=(
                    "Hot chowder at every shift change. On this rock "
                    "the kitchen is the warmest place for fifty "
                    "kilometres - eat while it's hot."
                ),
            ),
        ),
        (
            "depot_attendant",
            npc_module.NPC(
                id="depot_attendant",
                name="Stores Keeper",
                guild="depot",
                char="d",
                fg=(200, 220, 240),
                flavor_text=(
                    "Thermal blankets, core drill bits, de-icer - "
                    "whatever the campus needs, it comes through "
                    "this cage first. Sign for it."
                ),
            ),
        ),
    ),
    produces=(
        ("research_data", 10),
    ),
    demands=(
        ("food_rations", 8),
        ("fuel_cells", 10),
    ),
    tech_level=2,
    mission_tier=2,
    # Lab chain delve site (lab_q3_reference): the sealed research
    # cache holds the reference resonance dataset in the ice caves
    # beneath the campus. Planet-themed tiles (deep ice blue).
    # PRESERVED byte-identical from the 40x24 outpost era.
    explorable_site_name="caves",
    dungeon_params=DungeonParams(
        width=80,
        height=60,
        min_room_size=4,
        max_room_size=14,
        room_fill_pct=0.6,
        tile_wall=world.Tile(
            kind="dungeon_wall", char="#", walkable=False,
            fg=(120, 150, 195), bg=(25, 35, 55),
        ),
        tile_floor=world.Tile(
            kind="dungeon_floor", char=".", walkable=True,
            fg=(200, 220, 245), bg=(55, 70, 95),
        ),
        # Deep ice caves (lab chain delve): tier 2 — worms + spitters.
        monster_pool=("ice_worm", "frost_spitter"),
        monster_density=1.6,
        cache_guardian_pool=("ice_worm",),
        cache_guardian_count=2,
    ),
)
