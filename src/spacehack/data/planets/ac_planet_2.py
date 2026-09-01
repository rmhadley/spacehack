"""AC-II — Frostlab: an ice research outpost on the outer rim of the binary.

The outer rim of the Alpha Centauri binary is dark and cold — the
perfect vantage for long-baseline stellar interferometry. Frostlab
grew from a single observation dome into a small campus: a landing bay
carved into the ice, a research lab at the heart of the complex, and
frozen meltwater channels and crevasses that frame the station like
glacial terrain. The lab's cyan-lit interior glow spills out onto the
snow at night.

Layout (100x70), authored as `ac2_frostlab`:

  * spaceport NW — door south onto the landing apron.
  * lab east-central — door west onto the campus quad.
  * The Spine (north-south) connects the port to the lab terrace.
  * A frozen meltwater channel crosses the map with one bridge.
  * Sastrugi ridges and crevasses give the ice texture.
  * Cyan lab lamps and a campus beacon provide cold light.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from . import PlanetSpec
from ..city_npcs import AC2_POPULATION
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="ac_planet_2",
    name="AC-II",
    char="p",
    fg=(190, 200, 220),
    description=(
        "An icy body on the outer rim of the binary - "
        "Frostlab, a frozen research outpost."
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
    city_layout_id="ac2_frostlab",
    city_npc_population=AC2_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing bay",
            pos=world.Position(16, 14), serves="ac2_spaceport",
            destinations=("lab",),
        ),
        world.TransitStation(
            id="lab", name="Research Lab", district="lab terrace",
            pos=world.Position(65, 22), serves="ac2_lab",
            destinations=("spaceport",),
        ),
    ),
    interior_layouts=(
        ("spaceport", "ac2_spaceport_interior"),
        ("lab", "ac2_lab_interior"),
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
        ("research_data", 10),
    ),
    demands=(
        ("food_rations", 10),
        ("fuel_cells", 12),
    ),
    tech_level=2,
    mission_tier=2,
)
