"""Procyon b — The Crossroads: a scorched rocky waypoint on the deep lanes.

A dry prospecting stop on the inner edge of the crossroads system.
Every route in the sector threads through Procyon, and every pilot
between the gates sets down here for fuel and a drink — a sun-blasted
truck stop with the nav beacon that marks the waypoint.

Layout (120x80), authored as `proc_b_crossroads`:

  * One main strip runs east-west; the west end opens onto the wide
    landing apron with the spaceport north of it.
  * The Crossroads cantina (bar) and the fuel depot face the plaza
    south of the strip, with the nav beacon between them.
  * A dry arroyo cuts the south-west corner; shanty shacks and
    boulders texture the scorched hardpan.

NPC overrides: the barkeep becomes the "Waypoint Host" and the depot
attendant becomes the "Fuel Factor".
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import PROC_B_POPULATION


SPEC = PlanetSpec(
    id="proc_planet_1",
    name="Procyon b",
    char="p",
    fg=(180, 160, 130),
    description=(
        "A scorched rocky world orbiting Procyon A - a waypoint "
        "on the deep-space lanes."
    ),
    width=120,
    height=80,
    hangar_anchor=world.Position(15, 33),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=8, x_hi=28, y_lo=18, y_hi=25,
            door_x=18, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=60, x_hi=78, y_lo=46, y_hi=53,
            door_x=69, npc_id="barkeep", door_north=True,
        ),
        world.CityBuilding(
            label="depot", x_lo=92, x_hi=110, y_lo=46, y_hi=53,
            door_x=101, npc_id="depot_attendant", door_north=True,
        ),
    ),
    city_layout_id="proc_b_crossroads",
    city_npc_population=PROC_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing apron",
            pos=world.Position(22, 27),
            destinations=("crossroads", "depot"),
        ),
        world.TransitStation(
            id="crossroads", name="Crossroads Plaza", district="plaza",
            pos=world.Position(82, 43),
            destinations=("spaceport", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Fuel Depot", district="fuel yard",
            pos=world.Position(105, 44),
            destinations=("spaceport", "crossroads"),
        ),
    ),

    interior_layouts=(
        ("spaceport", "proc_b_spaceport_interior"),
        ("bar", "proc_b_bar_interior"),
        ("depot", "proc_b_depot_interior"),
    ),
    showroom_ships=(
        ("scout", -6, -2),
        ("cruiser", 0, -2),
        ("freighter", 6, -2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Waypoint Host",
                guild="bar",
                char="b",
                fg=(200, 150, 90),
                flavor_text=(
                    "Three gates in reach of this rock, and every "
                    "pilot between them stops here for a drink. "
                    "If it happened in the lanes, I heard it."
                ),
            ),
        ),
        (
            "depot_attendant",
            npc_module.NPC(
                id="depot_attendant",
                name="Fuel Factor",
                guild="depot",
                char="d",
                fg=(230, 190, 120),
                flavor_text=(
                    "Tanks topped, filters clean, and the ledger's "
                    "straight. The lanes run on fuel - and fuel runs "
                    "through this yard."
                ),
            ),
        ),
    ),
    produces=(
        ("ore_processed", 12),
    ),
    demands=(
        ("food_rations", 8),
        ("fuel_cells", 12),
    ),
    tech_level=2,
    mission_tier=2,
)