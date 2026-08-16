"""Ross 154 c — Cinder, the Scrap Ring dome city.

Ross 154 c is a shattered moon that a dead navy fleet once mined
and fortified. When the federation stopped coming, the salvage
crews moved in and never left. They domed the worst of the blast
crater, rigged the old docks to the decommissioned hulls around it,
and turned the whole graveyard into a bazaar.

Cinder's economy is the deep end of the arm's trade: repurposed
ship components, electronics pried out of wrecks the flares never
quite finished, research data off scorched couriers. Everything is
"recovered," nothing is "stolen" — at least not to your face.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE corner — "The Long Burn" dockhall.
  * merchants guild hall, SW — salvage brokers.
  * depot, SE — fuel and patch-plate supply for the run back.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import CLOUD_CITY


SPEC = PlanetSpec(
    theme=CLOUD_CITY,
    id="ross_c",
    name="Cinder",
    char="p",
    fg=(150, 120, 160),
    description="The Scrap Ring - a salvage bazaar domed over a shattered moon.",
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
                name="Salvage Host",
                guild="bar",
                char="b",
                fg=(150, 230, 220),
                flavor_text=(
                    "Every hull out there is a story someone left "
                    "half-finished. We finish them - for a finder's fee."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="Ring Broker",
                guild="merchants",
                char="g",
                fg=(200, 225, 255),
                flavor_text=(
                    "The Ring trades in whatever the flares forgot to "
                    "destroy. If it still hums, it has a price."
                ),
            ),
        ),
    ),
    produces=(
        ("ship_components", 22),
        ("electronics", 16),
        ("research_data", 10),
    ),
    demands=(
        ("food_rations", 15),
        ("fuel_cells", 14),
        ("medical_supplies", 10),
    ),
    tech_level=4,
    mission_tier=4,
)