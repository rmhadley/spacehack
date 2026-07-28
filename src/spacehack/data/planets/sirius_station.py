"""Sirius Binary Research Station — a solar observatory between two stars.

Perched in the gravity well between Sirius A and Sirius B, this station
studies the binary interaction — solar flares, gravitational tides, and
the exotic physics of a white dwarf orbiting a blue-white giant. The
view from the lab window is unlike anything else in charted space.

Layout (40x24, compact):

  * spaceport, NW corner.
  * lab, NE corner — stellar research wing.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import STATION


SPEC = PlanetSpec(
    theme=STATION,
    id="sirius_station",
    name="Binary Station",
    char="#",
    fg=(180, 210, 240),
    description="A solar research station between Sirius A and B — the only port in the system.",
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
        ("hauler",  7, 4),
        ("cruiser", 11, 4),
    ),
    npc_overrides=(
        (
            "research_officer",
            npc_module.NPC(
                id="research_officer",
                name="Binary Observer",
                guild="lab",
                char="S",
                fg=(150, 220, 240),
                flavor_text=(
                    "Two stars, one orbit, a thousand questions. "
                    "Every day the data tells us something new about "
                    "how binaries live — and how they die."
                ),
            ),
        ),
    ),
    produces=(
        ("research_data", 15),
    ),
    demands=(
        ("food_rations", 10),
        ("medical_supplies", 8),
        ("electronics", 10),
    ),
    tech_level=4,
)
