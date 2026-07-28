"""Vega b — a massive gas giant with a floating observation station.

Not a planetary surface — the player "lands" on an orbital platform
suspended in the upper atmosphere. Cool blues, silver trims, and
wide observation windows looking down into the swirling cloud bands.

Layout (60x40):

  * spaceport (arrival deck), NW corner.
  * bar (observation lounge), NE corner — "The Veil" — floor-to-ceiling
    windows overlooking the gas giant's cloudscape.

NPC overrides: the barkeep becomes the "Cloud Host" — a sleek,
welcoming figure who knows the gossip of the deep-space routes.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import CLOUD_CITY


SPEC = PlanetSpec(
    theme=CLOUD_CITY,
    id="vega_b",
    name="Vega b",
    char="P",
    fg=(200, 200, 220),
    description="A massive gas giant — its upper atmosphere hosts a floating observation deck.",
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
    ),
    showroom_ships=(
        ("cruiser",   11, 4),
        ("freighter", 15, 2),
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
                    "Welcome to the Veil. Drink in the view — "
                    "the clouds below shift faster than the politics above."
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
