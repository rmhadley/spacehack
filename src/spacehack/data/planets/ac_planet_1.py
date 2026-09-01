"""AC-I — The Claim: a scorched prospecting boomtown on a binary-blasted rock.

Alpha Centauri A pours white light onto a hot, dust-scoured rock where
two suns mean double the heat. The town grew from a strike-camp into a
permanent claim: one main drag (Prospect Avenue) running east from the
landing apron, the assayer's bar at its east end, and claim stakes, ore
piles, and wind-blasted shacks scattered across the hardpan. At night
the sodium-vapor lamps along the avenue cast amber pools across the
dust, and every prospector's shadow has two edges.

Layout (100x70), authored as `ac1_the_claim`:

  * spaceport NW — door south onto the landing apron.
  * "The Claim" bar east — assayer's cantina, door north onto the avenue.
  * Prospect Avenue runs east-west; the crossroads plaza carries the
    town beacon mid-avenue.
  * Claim stakes and ore piles texture the south hardpan; shanty shacks
    and sun-blasted boulders scatter the north.
  * Sodium-vapor lamp posts line the avenue with amber light.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import AC1_POPULATION
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="ac_planet_1",
    name="AC-I",
    char="p",
    fg=(180, 165, 130),
    description=(
        "A scorched rocky world in the binary's inner belt - "
        "The Claim, a prospecting boomtown under two suns."
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
            label="bar", x_lo=68, x_hi=85, y_lo=52, y_hi=57,
            door_x=75, npc_id="barkeep", door_north=False,
        ),
    ),
    city_layout_id="ac1_the_claim",
    city_npc_population=AC1_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing apron",
            pos=world.Position(18, 15), serves="ac1_spaceport",
            destinations=("bar"),
        ),
        world.TransitStation(
            id="bar", name="The Claim", district="east end",
            pos=world.Position(75, 60), serves="ac1_bar",
            destinations=("spaceport"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "ac1_spaceport_interior"),
        ("bar", "ac1_bar_interior"),
    ),
    showroom_ships=(
        ("scout", -6, -2),
        ("hauler", 0, -2),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Claim Staker",
                guild="bar",
                char="b",
                fg=(210, 150, 80),
                flavor_text=(
                    "Two suns, one hot rock, and a hundred ways "
                    "to go broke. Sit down, pilot - everyone here "
                    "has a story, and most of them end in ore."
                ),
            ),
        ),
    ),
    produces=(
        ("ore_processed", 15),
    ),
    demands=(
        ("food_rations", 8),
        ("fuel_cells", 10),
    ),
    tech_level=1,
    mission_tier=1,
)
