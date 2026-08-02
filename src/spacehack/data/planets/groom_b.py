"""Groombridge 34 b — a rough mining colony at the end of the North
Arm.

The arm runs out here: beyond the gate is nothing but dark. The
ore fields draw hard-bitten prospectors, the bar doubles as a
bounty office, and the militia doesn't come this far. Law and order
are whatever you bring with you.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE corner — "The Last Gate" saloon.
  * bounty office, SW — wanted posters from all along the arm.
  * depot, SE — refueling for the run back to charted space.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="groom_b",
    name="Groombridge 34 b",
    char="p",
    fg=(110, 100, 90),
    description="A rough mining world at the end of the arm — no laws, no militia.",
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
            label="bounties",  x_lo=4,  x_hi=19, y_lo=26, y_hi=35,
            door_x=11, npc_id="bounty_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="depot",     x_lo=40, x_hi=55, y_lo=26, y_hi=35,
            door_x=47, npc_id="depot_attendant",
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("hauler",   7, 2),
        ("cruiser",  11, 4),
        ("frigate",  15, 2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Prospector",
                guild="bar",
                char="b",
                fg=(210, 130, 80),
                flavor_text=(
                    "Out past the gate there's nothing — that's the "
                    "point. In here, a pilot can get rich or get dead. "
                    "Sometimes both."
                ),
            ),
        ),
    ),
    produces=(
        ("ore_processed", 35),
        ("weapons_blackmarket", 6),
    ),
    demands=(
        ("food_rations", 15),
        ("fuel_cells", 12),
        ("medical_supplies", 10),
    ),
    tech_level=3,
    mission_tier=3,
)
