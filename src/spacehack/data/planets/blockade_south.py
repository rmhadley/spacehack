"""Blockade South — The Quarantine Cordon space station."""
from __future__ import annotations

from ... import world
from ..city_npcs import BLOCKADE_SOUTH_POPULATION
from . import PlanetSpec


SPEC = PlanetSpec(
    id="blockade_south",
    name="Blockade Station South",
    char="#",
    fg=(130, 230, 220),
    description=(
        "A sealed militia quarantine station: inspection halls, held cargo, "
        "and a restricted airlock facing uncharted space."
    ),
    width=140,
    height=90,
    hangar_anchor=world.Position(18, 20),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=7, x_hi=31, y_lo=5, y_hi=14,
            door_x=19, npc_id="",
        ),
        world.CityBuilding(
            label="bounties", x_lo=12, x_hi=31, y_lo=67, y_hi=77,
            door_x=21, npc_id="bounty_master", door_north=True,
        ),
        world.CityBuilding(
            label="militia", x_lo=104, x_hi=129, y_lo=67, y_hi=77,
            door_x=116, npc_id="blockade_officer", door_north=True,
        ),
    ),
    showroom_ships=(
        ("cruiser", -6, -3),
        ("frigate", 6, -3),
    ),
    city_layout_id="blockade_south_quarantine",
    city_npc_population=BLOCKADE_SOUTH_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="arrival deck",
            pos=world.Position(19, 25),
            destinations=("quarantine", "militia", "bounties"),
        ),
        world.TransitStation(
            id="quarantine", name="Quarantine Plaza", district="cordon",
            pos=world.Position(70, 37),
            destinations=("spaceport", "militia", "bounties"),
        ),
        world.TransitStation(
            id="militia", name="South Watch", district="command deck",
            pos=world.Position(116, 79),
            destinations=("spaceport", "quarantine", "bounties"),
        ),
        world.TransitStation(
            id="bounties", name="Frontier Claims", district="claims deck",
            pos=world.Position(21, 79),
            destinations=("spaceport", "quarantine", "militia"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "blockade_south_spaceport_interior"),
        ("militia", "blockade_south_militia_interior"),
        ("bounties", "blockade_south_bounties_interior"),
    ),
    npc_overrides=(),
    produces=(("weapons_blackmarket", 5),),
    demands=(("food_rations", 10), ("electronics", 8), ("fuel_cells", 12)),
    tech_level=4,
    mission_tier=4,
)
