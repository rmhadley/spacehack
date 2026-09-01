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

Layout (100x70), authored as `ross_c_scrap_ring`:

  * the walkable floor is the blast-crater bowl; an irregular rubble
    rim (the dome's foundation) rings it, badlands beyond.
  * landing apron at the west rim breach — the airlock gate where
    the old fortification wall failed.
  * spaceport hull north of the apron, door south.
  * The Long Burn dockhall bar north-east, door south to the ring.
  * salvage brokers hall south-west, door north to the dock street.
  * depot south-east, door north to the ring.
  * the bazaar rings the sealed impact-slag mound at the crater's
    heart; the ship-breaker yard fills the east floor with
    half-stripped navy hulls.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import SCRAP_RING
from ..city_npcs import ROSS_C_POPULATION


SPEC = PlanetSpec(
    theme=SCRAP_RING,
    id="ross_c",
    name="Cinder",
    char="p",
    fg=(150, 120, 160),
    description="The Scrap Ring - a salvage bazaar domed over a shattered moon.",
    width=100,
    height=70,
    hangar_anchor=world.Position(24, 38),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=24, x_hi=44, y_lo=24, y_hi=31,
            door_x=33, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=56, x_hi=74, y_lo=18, y_hi=25,
            door_x=65, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants", x_lo=26, x_hi=44, y_lo=42, y_hi=50,
            door_x=35, npc_id="guild_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="depot", x_lo=64, x_hi=80, y_lo=44, y_hi=51,
            door_x=72, npc_id="depot_attendant",
            door_north=True,
        ),
    ),
    city_layout_id="ross_c_scrap_ring",
    city_npc_population=ROSS_C_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing field",
            pos=world.Position(38, 39), serves="ross_c_merchants",
            destinations=("long_burn", "depot"),
        ),
        world.TransitStation(
            id="long_burn", name="The Long Burn", district="dockhall",
            pos=world.Position(62, 28), serves="ross_c_bar",
            destinations=("spaceport", "depot"),
        ),
        world.TransitStation(
            id="depot", name="South Depot", district="depot quarter",
            pos=world.Position(70, 42), serves="ross_c_depot",
            destinations=("spaceport", "long_burn"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "ross_c_spaceport_interior"),
        ("bar", "ross_c_bar_interior"),
        ("merchants", "ross_c_merchants_interior"),
        ("depot", "ross_c_depot_interior"),
    ),
    # Showroom craft sit on the landing pad just north of the owned ship.
    showroom_ships=(
        ("hauler",  -6, -2),
        ("cruiser", -2, -2),
        ("frigate",  2, -2),
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
        (
            "depot_attendant",
            npc_module.NPC(
                id="depot_attendant",
                name="Yard Factor",
                guild="depot",
                char="d",
                fg=(230, 190, 120),
                flavor_text=(
                    "Fuel, patch plate, air bottles. Whatever gets your "
                    "hull back through the flares - the Yard stocks it."
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
