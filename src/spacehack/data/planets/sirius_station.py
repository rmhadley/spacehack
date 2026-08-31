"""Sirius Station — The Binary Eye: a solar observatory between two stars.

Perched in the gravity well between Sirius A and Sirius B, this station
studies the binary interaction — solar flares, gravitational tides, and
the exotic physics of a white dwarf orbiting a blue-white giant. The
view from the observation dome is unlike anything else in charted space:
two stars burning through the transparent plating, bathing the deck in
gold light.

Layout (100x70), authored as `sirius_binary_eye`:

  * spaceport NW — door south onto the landing apron.
  * lab east-central — door north onto the observation terrace.
  * The Solar Promenade runs east-west; the observation terrace carries
    the station beacon.
  * Solar collector arrays line the south hull.
  * The observation dome arcs across the north hull, lit gold.
  * Golden solar lamps and a station beacon provide warm light.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import SIRIUS_POPULATION
from .themes import STATION


SPEC = PlanetSpec(
    theme=STATION,
    id="sirius_station",
    name="Binary Station",
    char="#",
    fg=(180, 210, 240),
    description=(
        "A solar research station between Sirius A and B - "
        "The Binary Eye, an observatory bathed in gold light."
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
            label="lab", x_lo=60, x_hi=82, y_lo=28, y_hi=40,
            door_x=71, npc_id="research_officer", door_north=True,
        ),
    ),
    city_layout_id="sirius_binary_eye",
    city_npc_population=SIRIUS_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing bay",
            pos=world.Position(18, 15),
            destinations=("terrace", "lab"),
        ),
        world.TransitStation(
            id="terrace", name="Observation Terrace", district="campus",
            pos=world.Position(50, 25),
            destinations=("spaceport", "lab"),
        ),
        world.TransitStation(
            id="lab", name="Research Lab", district="lab wing",
            pos=world.Position(74, 25),
            destinations=("spaceport", "terrace"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "sirius_spaceport_interior"),
        ("lab", "sirius_lab_interior"),
    ),
    showroom_ships=(
        ("hauler", -6, -2),
        ("cruiser", 0, -2),
    ),
    npc_overrides=(
        (
            "research_officer",
            npc_module.NPC(
                id="research_officer",
                name="Binary Observer",
                guild="lab",
                char="S",
                fg=(150, 220, 240),
                flavor_text=(
                    "Two stars, one orbit, a thousand questions. "
                    "Every day the data tells us something new about "
                    "how binaries live - and how they die."
                ),
            ),
        ),
    ),
    produces=(
        ("research_data", 15),
    ),
    demands=(
        ("food_rations", 10),
        ("medical_supplies", 8),
        ("electronics", 10),
    ),
    tech_level=4,
    mission_tier=2,
)
