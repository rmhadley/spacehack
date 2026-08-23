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
    width=160,
    height=100,
    hangar_anchor=world.Position(25, 27),
    buildings=(
        world.CityBuilding(
            label="spaceport", x_lo=12, x_hi=36, y_lo=12, y_hi=19,
            door_x=25, npc_id="",
        ),
        world.CityBuilding(
            label="bar", x_lo=112, x_hi=126, y_lo=10, y_hi=16,
            door_x=119, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="bounties", x_lo=120, x_hi=138, y_lo=58, y_hi=65,
            door_x=129, npc_id="bounty_master",
        ),
        world.CityBuilding(
            label="merchants", x_lo=12, x_hi=34, y_lo=62, y_hi=69,
            door_x=23, npc_id="guild_master",
        ),
        world.CityBuilding(
            label="militia", x_lo=54, x_hi=74, y_lo=70, y_hi=76,
            door_x=64, npc_id="militia_captain",
        ),
    ),
    city_layout_id="earth_river_coast",
    transit_stations=(
        # Central hub on the civic plaza, plus a stop beside each core
        # building. The network is fully connected so the player can ride
        # directly between districts; every stop sits on walkable ground.
        world.TransitStation(
            id="port", name="Spaceport", district="spaceport",
            pos=world.Position(37, 26),
            destinations=("hub", "bar", "bounties", "merchants", "militia"),
        ),
        world.TransitStation(
            id="hub", name="Central Hub", district="civic",
            pos=world.Position(71, 52),
            destinations=("port", "bar", "bounties", "merchants", "militia"),
        ),
        world.TransitStation(
            id="bar", name="Bar District", district="waterfront",
            pos=world.Position(111, 17),
            destinations=("port", "hub", "bounties", "merchants", "militia"),
        ),
        world.TransitStation(
            id="bounties", name="Bounty Guild", district="waterfront",
            pos=world.Position(128, 77),
            destinations=("port", "hub", "bar", "merchants", "militia"),
        ),
        world.TransitStation(
            id="merchants", name="Merchant Hall", district="market",
            pos=world.Position(23, 77),
            destinations=("port", "hub", "bar", "bounties", "militia"),
        ),
        world.TransitStation(
            id="militia", name="Militia Center", district="civic",
            pos=world.Position(65, 77),
            destinations=("port", "hub", "bar", "bounties", "merchants"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "earth_city_spaceport_interior"),
        ("bar", "earth_city_bar_interior"),
        ("bounties", "earth_city_bounties_interior"),
        ("merchants", "earth_city_merchants_interior"),
        ("militia", "earth_city_militia_interior"),
    ),
    showroom_ships=(
        ("scout", 4, 3),
        ("hauler", 10, 3),
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
