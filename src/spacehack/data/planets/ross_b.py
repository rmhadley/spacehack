"""Ross 154 b -- Ember, the pirate town at the end of the Sirius arm.

Ross 154 is a flare star: violent eruptions that scramble scanners
and blind patrols.  Nothing official exists this far out, and the
flares are why -- the federation's eyes glaze over, so the pirates
who elbowed their way past Sirius built a town here instead of
getting caught.

Ashfall is the system's lawless heart.  It burns hot, drinks cheap,
and pays top credit for guns and anything that survived a flare:
rare earths fused and forged by stellar fire.

Layout (120x80, volcanic):
  * Two lava channels cutting diagonally across obsidian flats.
  * Cooled-crust bridges crossing the channels.
  * Spaceport on the NW basalt shelf.
  * The Flare Line bar carved into a dormant vent on the NE shelf.
  * Bounty office on the SW shelf.
  * Depot on the SE shelf.
  * Landing pad on a raised basalt platform.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import VOLCANIC
from ..city_npcs import ROSS_B_POPULATION


SPEC = PlanetSpec(
    theme=VOLCANIC,
    id="ross_b",
    name="Ember",
    char="p",
    fg=(200, 90, 50),
    description="Ashfall - a pirate town on a flare-scorched volcanic world at the end of the arm.",
    width=120,
    height=80,
    hangar_anchor=world.Position(21, 18),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=8, x_hi=32, y_lo=10, y_hi=22,
            door_x=20, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=88, x_hi=112, y_lo=8, y_hi=18,
            door_x=100, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="bounties", x_lo=8, x_hi=26, y_lo=55, y_hi=68,
            door_x=17, npc_id="bounty_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="depot", x_lo=88, x_hi=112, y_lo=55, y_hi=68,
            door_x=100, npc_id="depot_attendant",
            door_north=True,
        ),
    ),
    city_layout_id="ross_volcanic_settlement",
    city_npc_population=ROSS_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="NW shelf",
            pos=world.Position(20, 24),
            destinations=("bar", "bounties", "depot"),
        ),
        world.TransitStation(
            id="bar", name="The Flare Line", district="NE vent",
            pos=world.Position(100, 20),
            destinations=("spaceport", "bounties", "depot"),
        ),
        world.TransitStation(
            id="bounties", name="Bounty Office", district="SW shelf",
            pos=world.Position(17, 53),
            destinations=("spaceport", "bar", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Depot", district="SE shelf",
            pos=world.Position(100, 53),
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
