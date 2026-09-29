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
        world.CityBuilding(
            label="merchants", x_lo=12, x_hi=34, y_lo=46, y_hi=53,
            door_x=23, npc_id="guild_master",
        ),
        world.CityBuilding(
            label="bounties", x_lo=52, x_hi=70, y_lo=46, y_hi=53,
            door_x=61, npc_id="bounty_master",
        ),
    ),
    city_layout_id="ac2_frostlab",
    city_npc_population=AC2_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="landing bay",
            pos=world.Position(16, 14), serves="ac2_spaceport",
            destinations=("lab", "merchants", "bounties"),
        ),
        world.TransitStation(
            id="lab", name="Research Lab", district="lab terrace",
            pos=world.Position(65, 22), serves="ac2_lab",
            destinations=("spaceport", "merchants", "bounties"),
        ),
        world.TransitStation(
            id="merchants", name="Trade Annex", district="south terrace",
            pos=world.Position(21, 55), serves="ac2_merchants",
            destinations=("lab", "bounties", "spaceport"),
        ),
        world.TransitStation(
            id="bounties", name="Contract Board", district="south terrace",
            pos=world.Position(61, 61), serves="ac2_bounties",
            destinations=("lab", "merchants", "spaceport"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "ac2_spaceport_interior"),
        ("lab", "ac2_lab_interior"),
        ("merchants", "ac2_merchants_interior"),
        ("bounties", "ac2_bounties_interior"),
    ),
    showroom_ships=("hauler", "cruiser",),
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
                    "This binary system is full of new data. We'll be studying this for decades still."
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
    dig_min_floors=2,
    dig_max_floors=4,
    dig_prefixes=('Broad', 'Tall', 'Iron', 'Working', 'Second', 'Amber', 'Sturdy', 'Grain'),
    dig_suffixes=('Terrace', 'Works', 'Gallery', 'Silo', 'Lift', 'Store', 'Vault', 'Square'),
)
