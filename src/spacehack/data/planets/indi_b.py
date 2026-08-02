"""Indi b — a temperate agricultural colony at the middle of the
North Arm.

The breadbasket of the arm: broad farmlands under a warm K-type
sun, feeding the shipyards on Cygni b. Calmer than the other two
arm worlds, with a steady merchant trade and a quiet militia post.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE corner — "The Harvest" tavern.
  * merchant guild, SW — grain futures and freight contracts.
  * militia, SE — a modest station house.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import LUSH


SPEC = PlanetSpec(
    theme=LUSH,
    id="indi_b",
    name="Indi b",
    char="p",
    fg=(120, 180, 130),
    description="A temperate world of broad farmlands feeding the arm's shipyards.",
    width=60,
    height=40,
    hangar_anchor=world.Position(13, 17),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=4,  x_hi=23, y_lo=3,  y_hi=12,
            door_x=13, npc_id="",
        ),
        world.CityBuilding(
            label="bar",       x_lo=34, x_hi=41, y_lo=8,  y_hi=13,
            door_x=37, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants", x_lo=4,  x_hi=24, y_lo=25, y_hi=36,
            door_x=14, npc_id="guild_master",
        ),
        world.CityBuilding(
            label="militia",   x_lo=40, x_hi=55, y_lo=26, y_hi=35,
            door_x=47, npc_id="militia_captain",
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("scout",   3, 2),
        ("hauler",  7, 2),
        ("freighter", 15, 2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Farmer",
                guild="bar",
                char="b",
                fg=(180, 210, 120),
                flavor_text=(
                    "The grain goes out to Cygni b; the credits come "
                    "back. The rest is weather and patience."
                ),
            ),
        ),
    ),
    produces=(
        ("food_rations", 30),
        ("luxury_goods", 8),
    ),
    demands=(
        ("machine_parts", 12),
        ("electronics", 10),
        ("medical_supplies", 8),
    ),
    tech_level=2,
    mission_tier=2,
)
