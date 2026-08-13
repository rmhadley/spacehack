"""Mars: humanity's first off-world colony - red, dusty, frontier.

Three buildings the player can visit on the first iteration:

  * ``spaceport`` - no NPC; ships for sale inside.
  * ``bar``       - the Mars Barkeep (override of the global ``barkeep``
                    id). Char + flavor are Mars-flavoured so the
                    same ``barkeep`` npc_id reads differently here
                    than on Earth without touching the global
                    :class:`spacehack.data.npcs.NPCS` catalog.
  * ``merchants`` - the Trade Marshal (override of the global
                    ``guild_master`` id) — the colony's commerce hub.
  * ``militia``   - the Mars Patrol (override of the global
                    ``militia_captain`` id). Same pattern as the
                    bar override.

Missions are still tagged via ``giver_npc_id`` - a future-iteration
mission tagged ``barkeep`` would be offered by the Mars Barkeep on
Mars (NPC lookup resolves to the planet-local override) and by the
Earth Bartender when the player accepts the same mission on Earth.
That cross-planet mission life-cycle is future work; this iteration
just adds the data layer so adding new planets is one module away.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import MARS


SPEC = PlanetSpec(
    theme=MARS,
    id="mars",
    name="Mars",
    char="M",
    fg=(200, 50, 50),
    description="A red, dusty world - humanity's first off-world colony.",
    width=60,
    height=40,
    hangar_anchor=world.Position(15, 17),
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
        ("scout",   3, 2),
        ("cruiser", 11, 4),
    ),
    # Planet-local NPC overrides: re-skin the barkeep + militia
    # captain for the red-dust frontier flavour without touching the
    # global NPCS catalog (so Earth keeps its own Bartender + Captain).
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
    # The Mars surface is gated behind the prologue signal, so the
    # explore option reads "Explore signal" rather than a generic
    # "Explore Surface".
    explorable_site_name="signal",
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
        # Desert fauna + signal-ruins security: scavenger packs and
        # prowlers, with sentry + assault drones at the ruins. Tier 1
        # keeps the first-combat dive light.
        monster_pool=("rock_scavenger", "dust_prowler", "sentry_drone", "assault_drone"),
        monster_density=1.2,
        cache_guardian_pool=("sentry_drone",),
        cache_guardian_count=1,
    ),
)
