"""Vega b — The Beacon, a floating power-and-observation station.

Not a planetary surface — the player "lands" on a platform suspended
in the upper atmosphere of a massive gas giant. A fan of reflector
panels concentrates Vega's light onto a collector tower; the inhabited
deck grew around that industrial core. Cool blues, silver trims, and
wide observation windows looking down into the swirling cloud bands.

Layout (140x90), authored as `vega_beacon_station`:

  * The Focus — the central hub where the four arms overlap, carrying
    the station's navigation beacon.
  * spaceport (arrival deck), north arm — door south onto the apron.
  * The Veil (bar, observation lounge), west arm — door south onto
    the arm, beyond it the railed observation deck over the clouds.
  * merchants + depot (Freight Exchange), south arm — flanking a
    central corridor, doors south onto the exchange plaza.
  * The reflector fan fills the widening east arm; the lanes between
    the mirror rays are the field's maintenance access.

NPC overrides: the barkeep becomes the "Cloud Host" — a sleek,
welcoming figure who knows the gossip of the deep-space routes — the
guild master becomes the "Freight Broker", and the depot attendant
becomes the "Loadmaster".
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
    description=(
        "A massive gas giant - its upper atmosphere hosts a floating "
        "power-and-observation station."
    ),
    width=140,
    height=90,
    hangar_anchor=world.Position(70, 13),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=58, x_hi=82, y_lo=4, y_hi=8,
            door_x=70, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=26, x_hi=44, y_lo=38, y_hi=46,
            door_x=35, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants", x_lo=56, x_hi=68, y_lo=62, y_hi=69,
            door_x=62, npc_id="guild_master",
        ),
        world.CityBuilding(
            label="depot", x_lo=72, x_hi=84, y_lo=62, y_hi=69,
            door_x=78, npc_id="depot_attendant",
        ),
    ),
    city_layout_id="vega_beacon_station",
    city_npc_population=VEGA_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing deck",
            pos=world.Position(70, 19), serves="vega_b_spaceport",
            destinations=("focus", "veil", "exchange"),
        ),
        world.TransitStation(
            id="focus", name="The Focus", district="central hub",
            pos=world.Position(75, 71), serves="vega_b_depot",
            destinations=("spaceport", "veil", "exchange"),
        ),
        world.TransitStation(
            id="veil", name="The Veil", district="observation deck",
            pos=world.Position(35, 49), serves="bar",
            destinations=("spaceport", "focus", "exchange"),
        ),
        world.TransitStation(
            id="exchange", name="Freight Exchange", district="exchange plaza",
            pos=world.Position(70, 73), serves="vega_b_merchants",
            destinations=("spaceport", "focus", "veil"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "vega_b_spaceport_interior"),
        ("bar", "vega_b_bar_interior"),
        ("merchants", "vega_b_merchants_interior"),
        ("depot", "vega_b_depot_interior"),
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
        (
            "depot_attendant",
            npc_module.NPC(
                id="depot_attendant",
                name="Loadmaster",
                guild="depot",
                char="d",
                fg=(230, 200, 140),
                flavor_text=(
                    "Every crate that crosses the sector stops here once. "
                    "If it's freight, I know where it's going - "
                    "and what it's worth."
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