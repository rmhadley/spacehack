"""AC-I — a scorched rocky world orbiting Alpha Centauri A.

A rough prospecting outpost on the inner edge of the binary — hot,
dusty, and full of claim-stakers. The bar doubles as the assayer's
office; everyone here is either grubbing ore or grubbing credits.

Layout (40x24, compact):

  * spaceport, NW corner.
  * bar, NE corner — "The Claim" cantina.

NPC overrides: the barkeep is a grizzled prospector.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="ac_planet_1",
    name="AC-I",
    char="p",
    fg=(180, 165, 130),
    description=(
        "A scorched rocky world in the binary's inner belt - "
        "a prospecting outpost."
    ),
    width=40,
    height=24,
    hangar_anchor=world.Position(7, 14),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=2,  x_hi=15, y_lo=2,  y_hi=10,
            door_x=8, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=22, x_hi=37, y_lo=8,  y_hi=18,
            door_x=29, npc_id="barkeep",
        ),
    ),
    showroom_ships=(
        ("scout", 3, 2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Claim Staker",
                guild="bar",
                char="b",
                fg=(210, 150, 80),
                flavor_text=(
                    "Two suns, one hot rock, and a hundred ways "
                    "to go broke. Sit down, pilot - everyone here "
                    "has a story, and most of them end in ore."
                ),
            ),
        ),
    ),
    produces=(
        ("ore_processed", 15),
    ),
    demands=(
        ("food_rations", 8),
        ("fuel_cells", 10),
    ),
    tech_level=1,
    mission_tier=1,
)
