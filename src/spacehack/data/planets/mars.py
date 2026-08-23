"""Mars: humanity's first off-world colony — a sleek, modern terraformed city.

Mars is a 160x100 scrolling city (same size as Earth) with a red/rust
palette but a clean, high-tech feel — colonized with advanced terraforming
tech, no old history.  The spaceport sits at the heart of the city;
buildings radiate outward along hub-and-spoke roads.

  * spaceport — central-left, the colony's landing hub.
  * bar — upper-right, entertainment district.
  * merchants — lower-left, market district.
  * militia — lower-right, military district.
  * bounties — center-right, civic center.

Transit network (6 stops): port hub, market square, bar district,
merchants row, militia HQ, bounty board.

Central feature: a wide market-square plaza between the port and
the bounties district.

Everything is data on the spec; no builder code is Mars-specific.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import MARS
from ..city_npcs import MARS_POPULATION


SPEC = PlanetSpec(
    theme=MARS,
    id="mars",
    name="Mars",
    char="M",
    fg=(200, 50, 50),
    description="A sleek, modern terraformed colony -- humanity's first off-world city.",
    width=160,
    height=100,
    hangar_anchor=world.Position(60, 46),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=50, x_hi=72, y_lo=28, y_hi=40,
            door_x=60, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=110, x_hi=128, y_lo=12, y_hi=20,
            door_x=118, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants",
            x_lo=12, x_hi=30, y_lo=58, y_hi=72,
            door_x=20, npc_id="guild_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="militia",
            x_lo=120, x_hi=155, y_lo=58, y_hi=64,
            door_x=137, npc_id="militia_captain",
        ),
        world.CityBuilding(
            label="bounties",
            x_lo=95, x_hi=112, y_lo=40, y_hi=52,
            door_x=103, npc_id="bounty_master",
        ),
    ),
    city_layout_id="mars_colony",
    city_npc_population=MARS_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="port", name="Spaceport Hub", district="spaceport",
            pos=world.Position(60, 48),
            destinations=("hub", "bar", "merchants", "militia", "bounties"),
        ),
        world.TransitStation(
            id="hub", name="Market Square", district="plaza",
            pos=world.Position(87, 36),
            destinations=("port", "bar", "merchants", "militia", "bounties"),
        ),
        world.TransitStation(
            id="bar", name="Bar District", district="bar",
            pos=world.Position(108, 22),
            destinations=("port", "hub", "merchants", "militia", "bounties"),
        ),
        world.TransitStation(
            id="merchants", name="Merchants Row", district="market",
            pos=world.Position(32, 56),
            destinations=("port", "hub", "bar", "militia", "bounties"),
        ),
        world.TransitStation(
            id="militia", name="Militia HQ", district="military",
            pos=world.Position(118, 56),
            destinations=("port", "hub", "bar", "merchants", "bounties"),
        ),
        world.TransitStation(
            id="bounties", name="Bounty Board", district="civic",
            pos=world.Position(93, 54),
            destinations=("port", "hub", "bar", "merchants", "militia"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "mars_spaceport_interior"),
        ("bar", "mars_bar_interior"),
        ("merchants", "mars_merchants_interior"),
        ("militia", "mars_militia_interior"),
        ("bounties", "mars_bounties_interior"),
    ),
    showroom_ships=(
        ("scout",   3, 2),
        ("cruiser", 11, 4),
    ),
    # Planet-local NPC overrides: Mars-flavoured characters.
    npc_overrides=(
        (
            "barkeep",
            npc_module.NPC(
                id="barkeep",
                name="Mars Barkeep",
                guild="bar",
                char="b",
                fg=(220, 80, 70),
                flavor_text=(
                    "The dust here dries a throat to dust. Sit, drink, "
                    "tell me what you flew in for."
                ),
            ),
        ),
        (
            "guild_master",
            npc_module.NPC(
                id="guild_master",
                name="Trade Marshal",
                guild="merchants",
                char="G",
                fg=(220, 190, 90),
                flavor_text=(
                    "The colony ships ore out and imports everything "
                    "else. A pilot who hauls steady keeps both ends "
                    "of that deal honest."
                ),
            ),
        ),
        (
            "militia_captain",
            npc_module.NPC(
                id="militia_captain",
                name="Mars Patrol",
                guild="militia",
                char="P",
                fg=(180, 100, 110),
                flavor_text=(
                    "Keep your head down out there. The colony is "
                    "small, and the perimeter is wide."
                ),
            ),
        ),
    ),
    produces=(
        ("ore_processed", 40),
    ),
    demands=(
        ("food_rations", 20),
        ("electronics", 15),
        ("luxury_goods", 10),
    ),
    mech_weapons=("light_laser", "heavy_laser", "light_missile"),
    mech_modules=("compact_reactor", "shield_mk1", "expanded_cargo", "armor_plating"),
    armory_weapons=(
        "laser_pistol", "kinetic_pistol", "smg", "shotgun", "laser_rifle",
        "plasma_pistol", "combat_knife", "stun_baton",
    ),
    armory_armor=(
        "light_helmet", "heavy_helmet", "light_vest", "medium_vest",
        "tactical_gloves", "reinforced_gauntlets", "armour_pads",
        "heavy_legs", "combat_boots", "assault_boots",
        "cybernetic_eyes", "cybernetic_arms",
    ),
    tech_level=2,
    mission_tier=1,
    explorable_site_name="signal coordinates",
    dungeon_params=DungeonParams(
        width=120,
        height=90,
        min_room_size=5,
        max_room_size=30,
        room_fill_pct=0.8,
        tile_wall=world.Tile(
            kind="dungeon_wall", char="#", walkable=False,
            fg=(180, 120, 80), bg=(30, 20, 10),
        ),
        tile_floor=world.Tile(
            kind="dungeon_floor", char=".", walkable=True,
            fg=(200, 160, 120), bg=(50, 35, 20),
        ),
        monster_pool=("rock_scavenger", "dust_prowler", "sentry_drone"),
        monster_density=1.2,
        cache_guardian_pool=("sentry_drone",),
        cache_guardian_count=1,
    ),
)
