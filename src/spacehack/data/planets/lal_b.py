"""Lalande 21185 b — Deadfall, the blacked-out colony.

The gate past Groombridge appears on no chart, and nothing on the
other side ever came back to correct the record. A colony transport
called "Requiem" answered the deep-field survey signal and went
dark mid-flight. The squatters who finally reached the system found
the habitat deck frozen solid and the reactor long cold.

They built Deadfall anyway: one weather-sealed settlement on the
ice, lit by reclamation fires. No militia, no charter, no law but
the cold. The bar doubles as the town hall, the depot as the store,
and the bounty desk as the only address for disputes.

Layout (60x40):

  * spaceport, NW corner.
  * bar, NE corner — "The Deep Freeze" hall.
  * bounty office, SW — notes from every arm, posted by anyone.
  * depot, SE — the Reclaim Store, straight trade, no questions.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="lal_b",
    name="Deadfall",
    char="p",
    fg=(140, 150, 160),
    description="A squatters' colony on a frozen world - the Requiem's last stop.",
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
                name="Caretaker",
                guild="bar",
                char="b",
                fg=(170, 200, 230),
                flavor_text=(
                    "The Requiem's crew never woke up. We buried them "
                    "under the docking ring and raised this bar on the "
                    "spot. They'd have wanted it that way - it's warm."
                ),
            ),
        ),
    ),
    produces=(
        ("ship_components", 20),
        ("electronics", 14),
        ("scrap_metal", 45),
    ),
    demands=(
        ("food_rations", 16),
        ("fuel_cells", 14),
        ("medical_supplies", 12),
    ),
    tech_level=4,
    mission_tier=4,
)