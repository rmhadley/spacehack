"""Earth: the player's home planetary city.

Static data only - all behaviour lives in
:func:`spacehack.data.planets.load_planet`. New planets follow the
same shape: a :class:`PlanetSpec` literal at the module scope.

Earth keeps all four globally-cataloged NPCs unchanged so the
mission-by-giver-npc-id flow continues to work today (a mission
tagged for ``barkeep`` still resolves to Bartender on Earth).
"""
from __future__ import annotations

from ... import world
from . import PlanetSpec
from .themes import EARTH


SPEC = PlanetSpec(
    theme=EARTH,
    id="earth",
    name="Earth",
    char="o",
    fg=(130, 195, 230),
    description="Your home - blue oceans, green continents, one moon.",
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
            label="bounties",  x_lo=43, x_hi=57, y_lo=5,  y_hi=15,
            door_x=50, npc_id="bounty_master",
        ),
        world.CityBuilding(
            label="merchants", x_lo=4,  x_hi=24, y_lo=25, y_hi=36,
            door_x=14, npc_id="guild_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="militia",   x_lo=40, x_hi=55, y_lo=26, y_hi=35,
            door_x=47, npc_id="militia_captain",
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("scout",  3, 2),
        ("hauler", 7, 2),
    ),
    npc_overrides=(),    # Earth uses every global NPCS entry verbatim.
    produces=(
        ("electronics", 20),
        ("food_rations", 30),
        ("luxury_goods", 10),
    ),
    demands=(
        ("ore_processed", 25),
        ("machine_parts", 15),
        ("fuel_cells", 20),
    ),
    mech_weapons=("light_laser", "light_missile"),
    mech_modules=("compact_reactor", "shield_mk1", "expanded_cargo"),
    armory_weapons=("laser_pistol", "kinetic_pistol", "shotgun", "combat_knife"),
    armory_armor=("light_helmet", "light_vest", "tactical_gloves", "armour_pads", "combat_boots"),
    tech_level=1,
    # mission_tier=1: Sol is the starter system. Earth's boards only
    # offer tier-1 work; higher-tier jobs come from leaving Sol (T2
    # colonials, T3 hubs, T4 blockade/deep-space ports). Static
    # missions that out-tier Earth no longer pin to it — they float
    # to any matching-tier planet instead.
    mission_tier=1,
)
