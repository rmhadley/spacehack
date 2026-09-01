"""Venus — Cloudbreak City: a packed neon downtown floating in the clouds.

A dense, cloud-shrouded planet. Venus's floating port grew into a
megacity: a deck hung in the upper atmosphere, tower blocks packed into
a neon canyon around a cross of avenues, and every edge dissolving into
sulphuric cloud bands. The view from The Cloudbreak lounge is still the
best on the deck — endless cloud bands strobed by neon.

Layout (140x100), authored as `venus_cloudbreak`:

  * spaceport NW — door south onto the landing apron.
  * The Cloudbreak (bar) west — hot-pink observation lounge on the
    cloud rim, on its own spur off the Cross Street.
  * merchants hall east — door south onto its canyon lane.
  * deck stores depot south — door north onto its lane.
  * The Promenade + Cross Street avenues and the north-south spine
    cross at The Cross plaza (city beacon).

Transit network (4 stops, one per destination): spaceport, the bar
lounge, the merchants hall, and the deck stores depot.
  * Packed skyline blocks with neon signage line every avenue.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import VENUS_POPULATION
from .themes import CLOUD_CITY


SPEC = PlanetSpec(
    theme=CLOUD_CITY,
    id="venus",
    name="Venus",
    char="v",
    fg=(235, 215, 165),
    description=(
        "A dense, cloud-shrouded planet - Cloudbreak City hangs in the "
        "upper atmosphere, a neon canyon packed with towers."
    ),
    width=140,
    height=100,
    hangar_anchor=world.Position(14, 20),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=6, x_hi=30, y_lo=6, y_hi=14,
            door_x=18, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=16, x_hi=40, y_lo=70, y_hi=78,
            door_x=27, npc_id="barkeep", door_north=True,
        ),
        world.CityBuilding(
            label="merchants", x_lo=96, x_hi=120, y_lo=70, y_hi=78,
            door_x=108, npc_id="guild_master", door_north=True,
        ),
        world.CityBuilding(
            label="depot", x_lo=92, x_hi=116, y_lo=84, y_hi=92,
            door_x=103, npc_id="depot_attendant", door_north=True,
        ),
    ),
    city_layout_id="venus_cloudbreak",
    city_npc_population=VENUS_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="north rim",
            pos=world.Position(18, 22), serves="spaceport",
            destinations=("cloudbreak", "merchants", "depot"),
        ),
        world.TransitStation(
            id="cloudbreak", name="The Cloudbreak", district="west rim",
            pos=world.Position(31, 68), serves="venus_bar",
            destinations=("spaceport", "merchants", "depot"),
        ),
        world.TransitStation(
            id="merchants", name="Exchange Hall", district="east district",
            pos=world.Position(111, 68), serves="venus_merchants",
            destinations=("spaceport", "cloudbreak", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Deck Stores", district="south deck",
            pos=world.Position(93, 81), serves="venus_depot",
            destinations=("spaceport", "cloudbreak", "merchants"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "venus_spaceport_interior"),
        ("bar", "venus_bar_interior"),
        ("merchants", "venus_merchants_interior"),
        ("depot", "venus_depot_interior"),
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
                name="Cloud Guide",
                guild="bar",
                char="b",
                fg=(180, 180, 200),
                flavor_text=(
                    "Forty levels of city hang over the cloud bands, and "
                    "every window in it is somebody's sky. Stay for one "
                    "more, pilot - the view doesn't repeat."
                ),
            ),
        ),
        (
            "depot_attendant",
            npc_module.NPC(
                id="depot_attendant",
                name="Deck Keeper",
                guild="depot",
                char="d",
                fg=(210, 190, 150),
                flavor_text=(
                    "Rations, reactor cells, de-icer for the deck vents - "
                    "if it lands on Venus it comes through this cage. "
                    "Sign for it before it drifts off the edge."
                ),
            ),
        ),
    ),
    produces=(
        ("luxury_goods", 15),
        ("food_rations", 10),
    ),
    demands=(
        ("electronics", 10),
        ("machine_parts", 8),
    ),
    tech_level=2,
)