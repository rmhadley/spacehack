"""Cygni b — a dry temperate shipyard colony on the North Arm.

The first stop out of Sol: hulls for the North Arm trade are forged
here, and the port never sleeps. Rough-hewn and busy — a frontier
that's still close enough to home that the militia keeps an eye on
it.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE corner — "The Anvil" cantina.
  * merchant guild, SW — ship-chandler contracts.
  * militia, SE — a small station house.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="cygni_b",
    name="Cygni b",
    char="p",
    fg=(160, 170, 120),
    description="A dry temperate world - hulls are forged in its orbital yards.",
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
