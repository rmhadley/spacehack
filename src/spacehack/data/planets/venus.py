"""Venus — a dense, cloud-shrouded world with a floating observation port.

High in Venus's upper atmosphere, where pressure and temperature are
Earth-like, a small floating port offers shelter to passing pilots.
The view from the observation lounge is breathtaking — endless
sulphuric cloud bands stretching to the horizon.

Layout (60x40):

  * spaceport, NW corner.
  * bar (observation lounge), NE corner — "The Cloudbreak."
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import CLOUD_CITY


SPEC = PlanetSpec(
    theme=CLOUD_CITY,
    id="venus",
    name="Venus",
    char="v",
    fg=(235, 215, 165),
    description="A dense, cloud-shrouded planet — a floating port hangs in the upper atmosphere.",
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
        ("scout",    3, 2),
        ("hauler",   7, 2),
        ("freighter", 15, 2),
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
                    "The clouds below hide storms that'd tear a ship apart. "
                    "Stay in the port, and you'll live to see the view again."
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
)
