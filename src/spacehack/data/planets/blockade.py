"""Blockade Station North — The Picket: the primary militia garrison on the frontier.

The primary militia checkpoint on the Luyten frontier — the last
outpost of charted space. The station is a sealed military deck organized
around a command centre, an armory, and a bounty office for frontier
claims. Pressure bulkheads and artificial lighting give it its identity:
teal operational strips lead through public corridors, amber lights mark
the armory approach, and red warning lights identify restricted doors.

Layout (100x70), authored as `blockade_north_picket`:

  * spaceport NW — door south onto the landing apron.
  * militia command SE — door north onto the corridor.
  * bounty office SW — door north onto the corridor.
  * The Corridor runs east-west; the command plaza carries the station
    beacon mid-deck.
  * Pressure bulkheads texture the deck between districts.
  * Teal operational lamps, amber armory lights, red warning lights,
    and a central beacon provide atmospheric lighting.
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec
from ..city_npcs import BLOCKADE_NORTH_POPULATION
from .themes import STATION


SPEC = PlanetSpec(
    theme=STATION,
    id="blockade",
    name="Blockade Station North",
    char="#",
    fg=(130, 230, 220),
    description=(
        "A militia blockade station guarding the edge of federation "
        "space - The Picket, a sealed military garrison."
    ),
    width=100,
    height=70,
    hangar_anchor=world.Position(13, 23),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=6, x_hi=30, y_lo=4, y_hi=12,
            door_x=18, npc_id="",
        ),
        world.CityBuilding(
            label="militia", x_lo=62, x_hi=80, y_lo=52, y_hi=60,
            door_x=71, npc_id="blockade_officer", door_north=True,
        ),
        world.CityBuilding(
            label="bounties", x_lo=6, x_hi=24, y_lo=52, y_hi=60,
            door_x=15, npc_id="bounty_master", door_north=True,
        ),
    ),
    city_layout_id="blockade_north_picket",
    city_npc_population=BLOCKADE_NORTH_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing bay",
            pos=world.Position(16, 14), serves="blockade_north_spaceport",
            destinations=("militia", "bounties"),
        ),
        world.TransitStation(
            id="militia", name="Militia Command", district="SE deck",
            pos=world.Position(72, 50), serves="blockade_north_militia",
            destinations=("spaceport", "bounties"),
        ),
        world.TransitStation(
            id="bounties", name="Bounty Office", district="SW deck",
            pos=world.Position(15, 49), serves="blockade_north_bounties",
            destinations=("spaceport", "militia"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "blockade_north_spaceport_interior"),
        ("militia", "blockade_north_militia_interior"),
        ("bounties", "blockade_north_bounties_interior"),
    ),
    showroom_ships=(
        ("cruiser", -6, -2),
        ("frigate", 0, -2),
    ),
    npc_overrides=(),
    produces=(
        ("weapons_blackmarket", 5),
    ),
    demands=(
        ("food_rations", 10),
        ("electronics", 8),
        ("fuel_cells", 12),
    ),
    tech_level=4,
    mission_tier=4,
)
