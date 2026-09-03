"""Depot — Waypoint 7: a deep-space refueling nexus and truck stop.

Every long-hauler between Epsilon Eridani and Tau Ceti stops at
Waypoint 7 — the refueling depot at the midpoint of the deep-space run.
It's a utilitarian industrial deck: a landing bay, a fuel depot, a
mechanic's yard, and cargo stacks. The amber sodium-vapor work lights
that line the freight corridors and the fuel pipe runs that crisscross
the deck give it its industrial texture.

Layout (100x70), authored as `depot_waypoint7`:

  * spaceport NW — door south onto the landing apron.
  * depot east — fuel depot, door north onto the freight plaza.
  * The Freightway runs east-west; the freight plaza carries the
    depot beacon mid-deck.
  * Cargo container stacks and fuel pipe runs texture the south deck.
  * Amber sodium-vapor work lights line the Freightway.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import DEPOT_POPULATION
from .themes import STATION


SPEC = PlanetSpec(
    theme=STATION,
    id="depot",
    name="Refueling Depot",
    char="#",
    fg=(200, 200, 180),
    description=(
        "A deep-space refueling station - Waypoint 7, the truck stop "
        "at the midpoint of the deep-space run."
    ),
    width=100,
    height=70,
    hangar_anchor=world.Position(13, 23),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=6, x_hi=30, y_lo=4, y_hi=12,
            door_x=18, npc_id="",
        ),
        world.CityBuilding(
            label="depot", x_lo=66, x_hi=84, y_lo=52, y_hi=60,
            door_x=75, npc_id="depot_attendant", door_north=True,
        ),
    ),
    city_layout_id="depot_waypoint7",
    city_npc_population=DEPOT_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing bay",
            pos=world.Position(15, 14), serves="depot_spaceport",
            destinations=("depot",),
        ),
        world.TransitStation(
            id="depot", name="Fuel Depot", district="east end",
            pos=world.Position(75, 49), serves="depot",
            destinations=("spaceport",),
        ),
    ),
    interior_layouts=(
        ("spaceport", "depot_spaceport_interior"),
        ("depot", "depot_depot_interior"),
    ),
    showroom_ships=(
        ("hauler", -6, -2),
        ("freighter", 0, -2),
    ),
    npc_overrides=(
        (
            "depot_attendant",
            npc_module.NPC(
                id="depot_attendant",
                name="Yard Boss",
                guild="depot",
                char="A",
                fg=(210, 190, 150),
                flavor_text=(
                    "Fuel pumps are online. The deep-space run is long - "
                    "make sure your tanks are topped before you push "
                    "further out. Every hauler between Eri and Tau Ceti "
                    "stops here, and every one of them owes me a tab."
                ),
            ),
        ),
    ),
    produces=(
        ("fuel_cells", 25),
        ("machine_parts", 15),
    ),
    demands=(
        ("food_rations", 10),
        ("electronics", 8),
    ),
    tech_level=3,
    mission_tier=2,
)
