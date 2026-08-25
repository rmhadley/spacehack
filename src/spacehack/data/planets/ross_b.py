"""Ross 154 b -- Ember, the pirate town at the end of the Sirius arm.

Layout (120x80, volcanic):
  * Two lava channels cutting diagonally across obsidian flats.
  * Cooled-crust bridges crossing the channels.
  * Spaceport on the NW basalt shelf.
  * The Flare Line bar on the NE shelf.
  * Bounty office on the SW shelf.
  * Depot on the SE shelf.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import VOLCANIC
from ..city_npcs import ROSS_B_POPULATION


# Building positions must match ross_city.py exactly.
_SPACEPORT_ORIGIN = (4, 1)
_BAR_ORIGIN = (90, 1)
_BOUNTIES_ORIGIN = (8, 56)
_DEPOT_ORIGIN = (94, 56)

# Door offsets within each layout (from the .layout file).
_SPACEPORT_DOOR = (_SPACEPORT_ORIGIN[0] + 11, _SPACEPORT_ORIGIN[1] + 8)
_BAR_DOOR = (_BAR_ORIGIN[0] + 10, _BAR_ORIGIN[1] + 8)
_BOUNTIES_DOOR = (_BOUNTIES_ORIGIN[0] + 9, _BOUNTIES_ORIGIN[1] + 7)
_DEPOT_DOOR = (_DEPOT_ORIGIN[0] + 10, _DEPOT_ORIGIN[1])


SPEC = PlanetSpec(
    theme=VOLCANIC,
    id="ross_b",
    name="Ember",
    char="p",
    fg=(200, 90, 50),
    description="Ashfall - a pirate town on a flare-scorched volcanic world at the end of the arm.",
    width=120,
    height=80,
    hangar_anchor=world.Position(15, 18),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=_SPACEPORT_ORIGIN[0], x_hi=_SPACEPORT_ORIGIN[0] + 23,
            y_lo=_SPACEPORT_ORIGIN[1], y_hi=_SPACEPORT_ORIGIN[1] + 8,
            door_x=_SPACEPORT_DOOR[0], npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=_BAR_ORIGIN[0], x_hi=_BAR_ORIGIN[0] + 20,
            y_lo=_BAR_ORIGIN[1], y_hi=_BAR_ORIGIN[1] + 8,
            door_x=_BAR_DOOR[0], npc_id="barkeep",
        ),
        world.CityBuilding(
            label="bounties",
            x_lo=_BOUNTIES_ORIGIN[0], x_hi=_BOUNTIES_ORIGIN[0] + 18,
            y_lo=_BOUNTIES_ORIGIN[1], y_hi=_BOUNTIES_ORIGIN[1] + 7,
            door_x=_BOUNTIES_DOOR[0], npc_id="bounty_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="depot",
            x_lo=_DEPOT_ORIGIN[0], x_hi=_DEPOT_ORIGIN[0] + 23,
            y_lo=_DEPOT_ORIGIN[1], y_hi=_DEPOT_ORIGIN[1] + 8,
            door_x=_DEPOT_DOOR[0], npc_id="depot_attendant",
            door_north=True,
        ),
    ),
    city_layout_id="ross_volcanic_settlement",
    city_npc_population=ROSS_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="NW shelf",
            # Below the south-facing door.
            pos=world.Position(_SPACEPORT_DOOR[0], _SPACEPORT_ORIGIN[1] + 10),
            destinations=("bar", "bounties", "depot"),
        ),
        world.TransitStation(
            id="bar", name="The Flare Line", district="NE vent",
            # Below the south-facing door.
            pos=world.Position(_BAR_DOOR[0], _BAR_ORIGIN[1] + 10),
            destinations=("spaceport", "bounties", "depot"),
        ),
        world.TransitStation(
            id="bounties", name="Bounty Office", district="SW shelf",
            # Below the north-facing door (south of building).
            pos=world.Position(_BOUNTIES_DOOR[0], _BOUNTIES_ORIGIN[1] + 10),
            destinations=("spaceport", "bar", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Depot", district="SE shelf",
            # Below the north-facing door (south of building).
            pos=world.Position(_DEPOT_DOOR[0], _DEPOT_ORIGIN[1] - 1),
            destinations=("spaceport", "bar", "bounties"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "ross_spaceport_interior"),
        ("bar", "ross_bar_interior"),
        ("bounties", "ross_bounties_interior"),
        ("depot", "ross_depot_interior"),
    ),
    showroom_ships=(
        ("hauler", 5, -2),
        ("cruiser", -3, -2),
        ("frigate", 0, -4),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Emberglass",
                guild="bar",
                char="b",
                fg=(240, 130, 60),
                flavor_text=(
                    "Flares cook half the sensors past Sirius, and we're "
                    "the first warm plate they land on. Drink up while "
                    "the star behaves - it ain't known for manners."
                ),
            ),
        ),
        (
            "bounty_master",
            npc_module.NPC(
                id="bounty_master",
                name="Warrant Clerk",
                guild="bhguild",
                char="B",
                fg=(255, 190, 110),
                flavor_text=(
                    "Papers from back home don't mean much past Sirius. "
                    "But credits? Credits always cash out."
                ),
            ),
        ),
    ),
    produces=(
        ("weapons_blackmarket", 12),
        ("rare_earth_metals", 18),
    ),
    demands=(
        ("food_rations", 18),
        ("fuel_cells", 16),
        ("medical_supplies", 12),
    ),
    tech_level=4,
    mission_tier=4,
    quest_npc_spots=(
        ("old_smuggler", "bar"),
    ),
    explorable_site_name="caves",
)
