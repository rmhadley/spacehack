"""AC-III — Ring Refinery: a floating refinery deck in a gas giant's ring plane.

Alpha Centauri III is a ringed gas giant, and the refinery deck floats
in the ring plane — the binary's fuel and machine stop. Ships working
the Proxima and AC lanes put in here to top off tanks and trade
maintenance parts. The ring particle bands drift past the observation
ports, and the flickering neon warning signs light the industrial
corridors amber and red at night.

Layout (100x70), authored as `ac3_ring_refinery`:

  * spaceport NW — door south onto the landing apron.
  * "The Ring Band" bar east — fueler's lounge, door north.
  * The Concourse runs east-west; the concourse plaza carries the
    refinery beacon mid-deck.
  * Fuel tank farm and pipe runs texture the south deck.
  * Ring particle bands rim the east and west edges.
  * Flickering amber/red neon warning signs line the concourse.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import AC3_POPULATION
from .themes import CLOUD_CITY


SPEC = PlanetSpec(
    theme=CLOUD_CITY,
    id="ac_planet_3",
    name="AC-III",
    char="P",
    fg=(210, 145, 100),
    description=(
        "A ringed gas giant in the binary's middle orbit - "
        "Ring Refinery, a floating fuel dock in the ring plane."
    ),
    width=100,
    height=70,
    hangar_anchor=world.Position(22, 23),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=10, x_hi=34, y_lo=6, y_hi=14,
            door_x=22, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=66, x_hi=84, y_lo=52, y_hi=60,
            door_x=75, npc_id="barkeep", door_north=True,
        ),
    ),
    city_layout_id="ac3_ring_refinery",
    city_npc_population=AC3_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing deck",
            pos=world.Position(22, 17), serves="ac3_spaceport",
            destinations=("bar",),
        ),
        world.TransitStation(
            id="bar", name="The Ring Band", district="east end",
            pos=world.Position(73, 50), serves="ac3_bar",
            destinations=("spaceport",),
        ),
    ),
    interior_layouts=(
        ("spaceport", "ac3_spaceport_interior"),
        ("bar", "ac3_bar_interior"),
    ),
    showroom_ships=(
        ("hauler", -6, -2),
        ("cruiser", 0, -2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Ring Hand",
                guild="bar",
                char="b",
                fg=(200, 190, 160),
                flavor_text=(
                    "The rings glitter out the window and the fuel "
                    "pumps hum all night. Long-haulers are the only "
                    "ones who appreciate either."
                ),
            ),
        ),
    ),
    produces=(
        ("fuel_cells", 25),
    ),
    demands=(
        ("food_rations", 12),
        ("machine_parts", 10),
    ),
    tech_level=2,
    mission_tier=2,
)
