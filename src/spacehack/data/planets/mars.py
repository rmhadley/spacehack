"""Mars: humanity's first off-world colony — a sleek, modern terraformed city.

Mars is a 160x100 scrolling city (same size as Earth) with open red dust
between districts and a deliberately engineered high-tech public realm.
The spaceport occupies the southern logistics edge; the civic square and
transit spine organize the dense city north of it.

  * spaceport — southern logistics district.
  * bar — north entertainment district.
  * merchants — west market district.
  * militia — east security district.
  * bounties — civic-services block beside the central square.

Transit network (6 stops): port interchange, civic square, entertainment,
merchant district, security district, and civic services.

Central feature: a formal civic square with a terraforming beacon.

Everything is data on the spec; no builder code is Mars-specific.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import MARS_CITY
from ..city_npcs import MARS_POPULATION


SPEC = PlanetSpec(
    theme=MARS_CITY,
    id="mars",
    name="Mars",
    char="M",
    fg=(200, 50, 50),
    description="A sleek, modern terraformed colony -- humanity's first off-world city.",
    width=160,
    height=100,
    hangar_anchor=world.Position(22, 87),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=10, x_hi=34, y_lo=78, y_hi=85,
            door_x=19, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=101, x_hi=118, y_lo=14, y_hi=20,
            door_x=110, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="merchants",
            x_lo=18, x_hi=37, y_lo=31, y_hi=42,
            door_x=27, npc_id="guild_master",
            door_north=True,
        ),
        world.CityBuilding(
            label="militia",
            x_lo=126, x_hi=157, y_lo=64, y_hi=70,
            door_x=142, npc_id="militia_captain",
        ),
        world.CityBuilding(
            label="bounties",
            x_lo=87, x_hi=105, y_lo=31, y_hi=37,
            door_x=96, npc_id="bounty_master",
        ),
    ),
    city_layout_id="mars_colony",
    city_npc_population=MARS_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="port", name="Port Interchange", district="spaceport",
            pos=world.Position(35, 88),
            destinations=("hub", "bar", "merchants", "militia", "bounties"),
        ),
        world.TransitStation(
            id="hub", name="Civic Square", district="civic",
            pos=world.Position(76, 47),
            destinations=("port", "bar", "merchants", "militia", "bounties"),
        ),
        world.TransitStation(
            id="bar", name="Entertainment District", district="entertainment",
            pos=world.Position(110, 23),
            destinations=("port", "hub", "merchants", "militia", "bounties"),
        ),
        world.TransitStation(
            id="merchants", name="Merchant District", district="market",
            pos=world.Position(42, 32),
            destinations=("port", "hub", "bar", "militia", "bounties"),
        ),
        world.TransitStation(
            id="militia", name="Security District", district="security",
            pos=world.Position(125, 73),
            destinations=("port", "hub", "bar", "merchants", "bounties"),
        ),
        world.TransitStation(
            id="bounties", name="Civic Services", district="civic",
            pos=world.Position(82, 40),
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
        ("scout",   3, 0),
        ("cruiser", 11, 1),
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
