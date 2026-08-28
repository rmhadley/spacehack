"""Vega b — a massive gas giant with a floating observation station.

Not a planetary surface — the player "lands" on an orbital platform
suspended in the upper atmosphere. Cool blues, silver trims, and
wide observation windows looking down into the swirling cloud bands.

Layout (140x90):

  * spaceport (arrival deck), NW corner.
  * bar (observation lounge), NE corner — "The Veil" — floor-to-ceiling
    windows overlooking the gas giant's cloudscape.
  * merchants, SW corner — the hub's trade hall.

NPC overrides: the barkeep becomes the "Cloud Host" — a sleek,
welcoming figure who knows the gossip of the deep-space routes —
and the guild master becomes the "Freight Broker".
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import CLOUD_CITY
from ..city_npcs import VEGA_B_POPULATION


SPEC = PlanetSpec(
    theme=CLOUD_CITY,
    id="vega_b",
    name="Vega b",
    char="P",
    fg=(200, 200, 220),
    description="A massive gas giant - its upper atmosphere hosts a floating observation deck.",
    width=140,
    height=90,
    hangar_anchor=world.Position(20, 31),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=10, x_hi=29, y_lo=18, y_hi=27,
            door_x=20, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=94, x_hi=101, y_lo=18, y_hi=23,
            door_x=97, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants", x_lo=94, x_hi=114, y_lo=62, y_hi=71,
            door_x=104, npc_id="guild_master",
            door_north=True,
        ),
    ),
    city_layout_id="vega_mirror_fields",
    city_npc_population=VEGA_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="arrival deck",
            pos=world.Position(31, 31),
            destinations=("parallax", "exchange", "cooling_works"),
        ),
        world.TransitStation(
            id="parallax", name="The Parallax", district="observation lounge",
            pos=world.Position(94, 29),
            destinations=("spaceport", "exchange", "cooling_works"),
        ),
        world.TransitStation(
            id="exchange", name="Merchant Exchange", district="freight field",
            pos=world.Position(104, 59),
            destinations=("spaceport", "parallax", "cooling_works"),
        ),
        world.TransitStation(
            id="cooling_works", name="Cooling Works", district="central spine",
            pos=world.Position(67, 48),
            destinations=("spaceport", "parallax", "exchange"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "vega_b_spaceport_interior"),
        ("bar", "vega_b_bar_interior"),
        ("merchants", "vega_b_merchants_interior"),
    ),
    showroom_ships=(
        ("cruiser", -5, -2),
        ("freighter", 2, -2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Cloud Host",
                guild="bar",
                char="b",
                fg=(180, 220, 240),
                flavor_text=(
                    "Welcome to the Veil. Drink in the view - "
                    "the clouds below shift faster than the politics above."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="Freight Broker",
                guild="merchants",
                char="G",
                fg=(200, 210, 220),
                flavor_text=(
                    "Every route in the sector threads through Vega. "
                    "You haul cargo between the lanes, I find you "
                    "a buyer at the other end."
                ),
            ),
        ),
    ),
    produces=(
        ("luxury_goods", 12),
        ("food_rations", 10),
    ),
    demands=(
        ("electronics", 8),
        ("machine_parts", 6),
    ),
    tech_level=3,
    mission_tier=3,
)
