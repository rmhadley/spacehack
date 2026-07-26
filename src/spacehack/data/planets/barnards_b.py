"""Barnard b — a scorched rocky mining outpost on the edge of charted space.

Hot, dusty, and rough-and-tumble. The bar doubles as a cantina for
off-duty miners; the salvage depot buys scrap from pilots who push
too deep and come back with more holes than they left with.

Layout (60x40, same as Earth/Mars):

  * spaceport building, NW corner (same footprint as Earth).
  * bar (cantina) building, NE corner — "The Ember" cantina.
  * salvage depot building, southern row — buys salvaged ship parts.

Three NPC overrides: bar and salvage keep their own flavour. The
salvage depot reuses the "depot" guild tag so a future mission tagged
for that id can offer salvage runs here.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="barnards_b",
    name="Barnard b",
    char="p",
    fg=(150, 100, 100),
    description="A scorched rocky super-Earth — hard ground, hard people.",
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
            label="depot",     x_lo=40, x_hi=55, y_lo=26, y_hi=35,
            door_x=47, npc_id="depot_attendant",
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("scout",  3, 2),
        ("hauler", 7, 2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Miner",
                guild="bar",
                char="b",
                fg=(220, 140, 70),
                flavor_text=(
                    "The rock here is mean and the pay is lean. "
                    "But a pilot with a fast ship can always find work."
                ),
            ),
        ),
    ),
    produces=(
        ("ore_processed", 35),
    ),
    demands=(
        ("food_rations", 15),
        ("machine_parts", 10),
        ("fuel_cells", 12),
        ("weapons_blackmarket", 8),
    ),
)
