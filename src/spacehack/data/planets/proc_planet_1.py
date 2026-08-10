"""Procyon b — a scorched rocky world orbiting Procyon A.

A dry prospecting stop on the inner edge of the crossroads system.
Not much here beyond a landing pad and a cantina — but every route
in the sector passes close enough to make it a useful waypoint.

Layout (40x24, compact):

  * spaceport, NW corner.
  * bar, NE corner — "The Crossroads" cantina.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="proc_planet_1",
    name="Procyon b",
    char="p",
    fg=(180, 160, 130),
    description=(
        "A scorched rocky world orbiting Procyon A - a waypoint "
        "on the deep-space lanes."
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
                name="Waypoint Host",
                guild="bar",
                char="b",
                fg=(200, 150, 90),
                flavor_text=(
                    "Three gates in reach of this rock, and every "
                    "pilot between them stops here for a drink. "
                    "If it happened in the lanes, I heard it."
                ),
            ),
        ),
    ),
    produces=(
        ("ore_processed", 12),
    ),
    demands=(
        ("food_rations", 8),
        ("fuel_cells", 12),
    ),
    tech_level=2,
    mission_tier=2,
)
