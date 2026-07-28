"""τ Cet b — a temperate habitable-zone world, Sol's nearest cousin.

A fledgling colony with optimistic frontier-town energy. Lush green
parks, wide plazas, and a bustling merchant hall. The first "New Earth"
the player encounters outside Sol — a reminder that humanity is
spreading.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE — "The Waypoint" pub.
  * merchants guild, S — active trade hub for this sector.

NPC overrides: barkeep + guild master get frontier-colony flavour.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import LUSH


SPEC = PlanetSpec(
    theme=LUSH,
    id="tc_b",
    name="τ Cet b",
    char="p",
    fg=(140, 200, 180),
    description="A temperate rocky world in the habitable zone — a new frontier.",
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
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("hauler", 7, 2),
        ("cruiser", 11, 4),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Colony Host",
                guild="bar",
                char="b",
                fg=(180, 220, 130),
                flavor_text=(
                    "Welcome to τ Cet b — the beer is local, the "
                    "stories are tall, and the landing pads are always open."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="Trade Commissioner",
                guild="merchants",
                char="G",
                fg=(220, 210, 130),
                flavor_text=(
                    "This colony runs on trade. If you've got cargo "
                    "and a working drive, I've got credits."
                ),
            ),
        ),
    ),
    produces=(
        ("food_rations", 25),
        ("ore_processed", 20),
    ),
    demands=(
        ("electronics", 12),
        ("machine_parts", 10),
        ("luxury_goods", 8),
    ),
    tech_level=2,
)
