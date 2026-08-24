"""Cygni b — a dry temperate shipyard colony on the North Arm.

The first stop out of Sol: hulls for the North Arm trade are forged here,
and the port never sleeps. A wide haul road splits the the colony down
the middle — portside to the west, the forge complex to the east.

Layout (160×100, authored port-and-forge colony):

  * spaceport, landing pad, and merchants on the port side (west).
  * dock market stalls along the haul road.
  * two massive hull-forge factories and a plate works (east side).
  * The Anvil bar tucked between the forges.
  * militia outpost facing the haul road.
  * worker-row shacks south of the factories.
  * yard workers moving between forge entrances and the haul road.

NPC overrides: the barkeep (Rigger, guild bar) and the guild-master
retain their existing flavour.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import DESERT
from ..city_npcs import CYGNI_B_POPULATION


SPEC = PlanetSpec(
    theme=DESERT,
    id="cygni_b",
    name="Cygni b",
    char="p",
    fg=(160, 170, 120),
    description="A dry temperate world - hulls are forged in its orbital yards.",
    width=160,
    height=100,
    hangar_anchor=world.Position(40, 16),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=6, x_hi=29, y_lo=10, y_hi=20,
            door_x=13, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=112, x_hi=132, y_lo=48, y_hi=57,
            door_x=122, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants",
            x_lo=6, x_hi=25, y_lo=48, y_hi=58,
            door_x=14, npc_id="guild_master",
        ),
        world.CityBuilding(
            label="militia",
            x_lo=122, x_hi=144, y_lo=74, y_hi=84,
            door_x=132, npc_id="militia_captain",
        ),
    ),
    city_layout_id="cygni_shipyard_colony",
    city_npc_population=CYGNI_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="west pad",
            pos=world.Position(42, 20),
            destinations=("bar", "merchants", "militia"),
        ),
        world.TransitStation(
            id="bar", name="The Anvil", district="forge row",
            pos=world.Position(126, 59),
            destinations=("spaceport", "merchants", "militia"),
        ),
        world.TransitStation(
            id="merchants", name="Chandler", district="port south",
            pos=world.Position(16, 60),
            destinations=("spaceport", "bar", "militia"),
        ),
        world.TransitStation(
            id="militia", name="Station House", district="forge south",
            pos=world.Position(134, 86),
            destinations=("spaceport", "bar", "merchants"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "cygni_spaceport_interior"),
        ("bar", "cygni_bar_interior"),
        ("merchants", "cygni_merchants_interior"),
        ("militia", "cygni_militia_interior"),
    ),
    showroom_ships=(
        ("scout", 3, -5),
        ("hauler", 6, -3),
        ("freighter", 10, -3),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Rigger",
                guild="bar",
                char="b",
                fg=(220, 140, 70),
                flavor_text=(
                    "Every hull off the line here takes its first jump "
                    "loaded with somebody's gamble. What's yours?"
                ),
            ),
        ),
    ),
    produces=(
        ("machine_parts", 25),
        ("ore_processed", 15),
    ),
    demands=(
        ("food_rations", 15),
        ("fuel_cells", 12),
        ("electronics", 8),
    ),
    tech_level=2,
    mission_tier=2,
)