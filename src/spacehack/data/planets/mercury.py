"""Mercury — a scorched rocky world, closest to Sol.

A small solar research station studies the sun from the best vantage
point in the system. The station is heavily shielded and cooled —
without protection, the surface heat would melt a ship in minutes.

Layout (40x24, compact):

  * spaceport, NW corner.
  * lab, NE corner — solar observatory.
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="mercury",
    name="Mercury",
    char="m",
    fg=(180, 175, 165),
    description="A scorched rocky world — closest to Sol, home to a solar research station.",
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
            label="lab",
            x_lo=22, x_hi=37, y_lo=8,  y_hi=18,
            door_x=29, npc_id="research_officer",
        ),
    ),
    showroom_ships=(
        ("scout",  3, 2),
        ("hauler", 7, 4),
    ),
    npc_overrides=(),
)
