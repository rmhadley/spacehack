"""Wolf 359 b — a dark, airless rock on the frontier of charted space.

A small listening post — just a landing bay and a supply depot —
serves as the last rest stop before the Luyten's Star blockade.
Quiet, cold, and utterly dark outside the station walls.

Layout (40x24, compact):

  * spaceport, NW corner.
  * depot, NE corner — supplies and emergency shelter.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="wolf_b",
    name="Wolf 359 b",
    char="p",
    fg=(80, 60, 50),
    description="A dark, airless rock — a lone listening post watches the frontier.",
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
            label="depot",
            x_lo=22, x_hi=37, y_lo=8,  y_hi=18,
            door_x=29, npc_id="depot_attendant",
        ),
    ),
    showroom_ships=(
        ("scout",  3, 2),
        ("hauler", 7, 4),
        ("cruiser", 11, 4),
    ),
    npc_overrides=(
        (
            "depot_attendant",
            npc_module.NPC(
                id="depot_attendant",
                name="Frontier Operator",
                guild="depot",
                char="A",
                fg=(180, 180, 160),
                flavor_text=(
                    "Not many ships come this far out. Fuel's short, "
                    "supplies are shorter. Make it count."
                ),
            ),
        ),
    ),
    produces=(),
    demands=(
        ("food_rations", 12),
        ("fuel_cells", 10),
        ("medical_supplies", 8),
    ),
    tech_level=2,
)
