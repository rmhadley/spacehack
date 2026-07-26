"""AC-II — an icy body on the outer rim of the Alpha Centauri binary.

A cold research outpost studies the binary star system from the
quiet dark of the outer rim. The lab focuses on long-baseline
stellar interferometry, taking advantage of AC-II's stable orbit
far from the two suns.

Layout (40x24, compact):

  * spaceport, NW corner.
  * lab, NE corner — stellar research.
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="ac_planet_2",
    name="AC-II",
    char="p",
    fg=(190, 200, 220),
    description="An icy body on the outer rim of the binary — a quiet research outpost.",
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
    produces=(
        ("research_data", 10),
    ),
    demands=(
        ("food_rations", 10),
        ("fuel_cells", 12),
    ),
)
