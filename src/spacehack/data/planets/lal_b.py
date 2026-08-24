"""Lalande 21185 b — Deadfall, the blacked-out colony.

The Requiem's hull is embedded in the ice crust at an angle — the
settlement is built into the frozen wreck. Spaceport and depot sit in
the upper deck section; the bar glows amber through frosted viewports
deep in the ice. The docking ring marks the crew's grave, lit by
reclamation lanterns. Salvage gantries and scrap piles ring the hull.

Layout (140×100, authored wreck colony):

  * spaceport and depot in the upper deck section (west / east).
  * bar — The Deep Freeze — deep in the ice on the lower deck.
  * bounty office — weather-sealed shack, north edge.
  * docking ring — circle in the terrain, south of the hull.
  * salvage yard — gantries, scrap, reclamation fires.

NPC overrides: the barkeep (Caretaker) retains existing flavour.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import ICE
from ..city_npcs import LAL_B_POPULATION


SPEC = PlanetSpec(
    theme=ICE,
    id="lal_b",
    name="Deadfall",
    char="p",
    fg=(140, 150, 160),
    description="A squatters' colony on a frozen world - the Requiem's last stop.",
    width=140,
    height=100,
    hangar_anchor=world.Position(42, 14),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=8, x_hi=31, y_lo=8, y_hi=18,
            door_x=20, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=56, x_hi=76, y_lo=56, y_hi=65,
            door_x=66, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="bounties",
            x_lo=8, x_hi=23, y_lo=72, y_hi=82,
            door_x=15, npc_id="bounty_master",
        ),
        world.CityBuilding(
            label="depot",
            x_lo=90, x_hi=109, y_lo=10, y_hi=18,
            door_x=99, npc_id="depot_attendant",
        ),
    ),
    city_layout_id="lal_wreck_colony",
    city_npc_population=LAL_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="upper deck",
            pos=world.Position(50, 20),
            destinations=("bar", "bounties", "depot"),
        ),
        world.TransitStation(
            id="bar", name="Deep Freeze", district="lower deck",
            pos=world.Position(68, 67),
            destinations=("spaceport", "bounties", "depot"),
        ),
        world.TransitStation(
            id="bounties", name="Bounty Board", district="south-west",
            pos=world.Position(20, 84),
            destinations=("spaceport", "bar", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Reclaim Store", district="upper deck east",
            pos=world.Position(100, 19),
            destinations=("spaceport", "bar", "bounties"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "lal_spaceport_interior"),
        ("bar", "lal_bar_interior"),
        ("bounties", "lal_bounties_interior"),
        ("depot", "lal_depot_interior"),
    ),
    showroom_ships=(
        ("hauler", 4, -5),
        ("cruiser", 8, -3),
        ("frigate", 12, -3),
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