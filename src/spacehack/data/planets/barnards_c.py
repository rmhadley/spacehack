"""Barnard c — a cold gas giant orbiting Barnard's Star.

A deep-freeze mining deck skimming the gas giant's upper bands —
siphons helium-3 and rare volatiles for the frontier routes.
Quiet, cold, and a long way from anywhere.

Layout (40x24, compact):

  * spaceport, NW corner.
  * bar, NE corner — "The Deep Freeze" cantina.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="barnards_c",
    name="Barnard c",
    char="P",
    fg=(120, 150, 200),
    description=(
        "A cold gas giant on the frontier - a helium-3 mining "
        "deck in its upper bands."
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
        ("hauler", 7, 4),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Ice Skimmer",
                guild="bar",
                char="b",
                fg=(170, 200, 230),
                flavor_text=(
                    "The pumps never stop and the cold gets in "
                    "your bones. A hot drink and a contract are "
                    "the only two things that help out here."
                ),
            ),
        ),
    ),
    produces=(
        ("fuel_cells", 15),
    ),
    demands=(
        ("food_rations", 8),
        ("medical_supplies", 6),
    ),
    tech_level=2,
    mission_tier=2,
)
