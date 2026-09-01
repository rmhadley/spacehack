"""Barnard c — the Skimmer Deck, an atmospheric helium-3 mining platform.

A cold gas giant orbiting Barnard's Star: it has no surface. Its
settlement is an industrial deck hung in the upper cloud bands,
siphoning helium-3 and rare volatiles for the frontier routes. Quiet,
cold, and a long way from anywhere.

Layout (110x72, authored skimmer deck):

  * One east-west service spine crosses mid-deck; two north-south road
    connectors tie the west landing apron and the eastern bar frontage
    to the spine.
  * The deck is sheared, not rectangular: the southwest corner is cut
    away in steps to the storm, rim-plated at the new edge.
  * Landing operations (west): quiet blank apron around the hangar
    berth; the spaceport hull sits north of the apron, door south.
  * Bar district (east): The Deep Freeze, door south onto a sidewalk
    spur meeting the spine.
  * Industrial character: an eleven-tank He-3 farm on the southeast
    deck, a painted He-3 pipeline run with valve manifolds, two
    skimmer cradles flanking the siphon inlet, gantry trusses along
    the north void edge, and a cloud inlet cut into the southern rim.
"""

from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from .themes import ICE
from ..city_npcs import BARNARDS_C_POPULATION


SPEC = PlanetSpec(
    theme=ICE,
    id="barnards_c",
    name="Barnard c",
    char="P",
    fg=(120, 150, 200),
    description=(
        "A cold gas giant on the frontier - a helium-3 mining "
        "deck in its upper bands."
    ),
    width=110,
    height=72,
    hangar_anchor=world.Position(18, 48),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=22, x_hi=42, y_lo=27, y_hi=34,
            door_x=32, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=86, x_hi=104, y_lo=12, y_hi=19,
            door_x=95, npc_id="barkeep",
        ),
    ),
    city_layout_id="barnards_c_atmo_deck",
    city_npc_population=BARNARDS_C_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing field",
            pos=world.Position(27, 41), serves="barnards_c_spaceport",
            destinations=("deep_freeze",),
        ),
        world.TransitStation(
            id="deep_freeze", name="Deep Freeze", district="bar quarter",
            pos=world.Position(92, 21), serves="barnards_c_bar",
            destinations=("spaceport",),
        ),
    ),
    interior_layouts=(
        ("spaceport", "barnards_c_spaceport_interior"),
        ("bar", "barnards_c_bar_interior"),
    ),
    showroom_ships=(
        ("hauler", -4, -3),
    ),
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Ice Skimmer",
                guild="bar",
                char="b",
                fg=(170, 200, 230),
                flavor_text=(
                    "The pumps never stop and the cold gets in "
                    "your bones. A hot drink and a contract are "
                    "the only two things that help out here."
                ),
            ),
        ),
    ),
    produces=(
        ("fuel_cells", 15),
    ),
    demands=(
        ("food_rations", 8),
        ("medical_supplies", 6),
    ),
    tech_level=2,
    mission_tier=2,
)
