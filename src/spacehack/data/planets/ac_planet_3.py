"""AC-III — a ringed gas giant in the Alpha Centauri binary.

A floating refinery deck suspended in the ring plane — the binary's
fuel and machine stop. Ships working the Proxima and AC lanes put
in here to top off tanks and trade maintenance parts.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE corner — "The Ring Band" lounge.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import CLOUD_CITY


SPEC = PlanetSpec(
    theme=CLOUD_CITY,
    id="ac_planet_3",
    name="AC-III",
    char="P",
    fg=(210, 145, 100),
    description=(
        "A ringed gas giant in the binary's middle orbit — "
        "a floating refinery deck."
    ),
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
        ("hauler",   7, 2),
        ("cruiser", 11, 4),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Ring Hand",
                guild="bar",
                char="b",
                fg=(200, 190, 160),
                flavor_text=(
                    "The rings glitter out the window and the fuel "
                    "pumps hum all night. Long-haulers are the only "
                    "ones who appreciate either."
                ),
            ),
        ),
    ),
    produces=(
        ("fuel_cells", 25),
    ),
    demands=(
        ("food_rations", 12),
        ("machine_parts", 10),
    ),
    tech_level=2,
    mission_tier=2,
)
