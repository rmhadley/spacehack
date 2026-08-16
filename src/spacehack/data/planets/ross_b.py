"""Ross 154 b — Ember, the pirate town at the end of the Sirius arm.

Ross 154 is a flare star: violent eruptions that scramble scanners
and blind patrols. Nothing official exists this far out, and the
flares are why — the federation's eyes glaze over, so the pirates
who elbowed their way past Sirius built a town here instead of
getting caught.

Ashfall is the system's lawless heart. It burns hot, drinks cheap,
and pays top credit for guns and anything that survived a flare:
rare earths fused and forged by stellar fire.

Layout (60x40), mirroring the frontier hubs:

  * spaceport, NW corner.
  * bar, NE corner — "The Flare Line" cantina.
  * bounty office, SW — the same guild desk as everywhere, at
    the same end of a lot of barrels.
  * depot, SE — old miners' tanks, still full.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="ross_b",
    name="Ember",
    char="p",
    fg=(200, 90, 50),
    description="Ashfall - a pirate town on a flare-scorched world at the end of the arm.",
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
)