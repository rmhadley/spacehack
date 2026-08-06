"""Wolf 359 b — a dark, airless rock on the frontier of charted space.

A small listening post — a landing bay, a supply depot, and a
black-market bar that serves as the last rest stop before the
Luyten's Star blockade. Quiet, cold, and utterly dark outside the
station walls.

Layout (40x24, compact):

  * spaceport, NW corner.
  * bar, SW corner — black-market refuge, no questions asked.
  * depot, NE corner — supplies and emergency shelter.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="wolf_b",
    name="Wolf 359 b",
    char="p",
    fg=(80, 60, 50),
    description="A dark, airless rock — a pirate-run listening post on the frontier. No questions asked.",
    width=40,
    height=24,
    hangar_anchor=world.Position(7, 14),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=2,  x_hi=15, y_lo=2,  y_hi=10,
            door_x=8, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=2,  x_hi=17, y_lo=13, y_hi=22,
            door_x=9, npc_id="wolf_barkeep",
        ),
        world.CityBuilding(
            label="depot",
            x_lo=22, x_hi=37, y_lo=8,  y_hi=18,
            door_x=29, npc_id="depot_attendant",
        ),
    ),
    showroom_ships=(
        ("scout",  3, 2),
        ("hauler", 7, 4),
        ("cruiser", 11, 4),
    ),
    npc_overrides=(
        (
            "wolf_barkeep",
            npc_module.NPC(
                id="wolf_barkeep",
                name="Black-Market Operator",
                guild="bar",
                char="B",
                fg=(200, 160, 80),
                flavor_text=(
                    "The lights are low and the patrons don't ask questions. "
                    "A scratched sign above the bar reads NO MILITIA. The "
                    "operator sizes you up — 'You got something for me, or "
                    "are you just thirsty?'"
                ),
            ),
        ),
        (
            "depot_attendant",
            npc_module.NPC(
                id="depot_attendant",
                name="Frontier Operator",
                guild="depot",
                char="A",
                fg=(180, 180, 160),
                flavor_text=(
                    "Pirates run this rock, but they pay in credits like "
                    "anyone else. Fuel's short, smuggler's holds aren't. "
                    "Make it count."
                ),
            ),
        ),
    ),
    produces=(),
    demands=(
        ("food_rations", 12),
        ("fuel_cells", 10),
        ("medical_supplies", 8),
    ),
    # Pirate-run frontier post: the cluster is overrun with pirates
    # (90% pirate_scout / 70% pirate_raider spawn), so the mechanic
    # openly stocks smuggler's holds of every tier — this is where
    # smugglers gear up before running the Luyten's Star blockade.
    # Explicit list (not RNG) so the black-market gear is always here.
    mech_modules=(
        "compact_reactor", "shield_mk1", "expanded_cargo",
        "smuggler_hold_mk1", "smuggler_hold_mk2",
        "smuggler_hold_mk3", "smuggler_hold_mk4",
    ),
    tech_level=2,
    mission_tier=3,
    # Merchant chain delve site (mer_q2_strike): the Guild's abandoned
    # prospecting claim sits in the dark caves beneath the listening
    # post — quest-tagged rare_earth_metals deep inside. Planet-themed
    # tiles (cold dark rock, faint mineral glint on the floor).
    explorable_site_name="caves",
    dungeon_params=DungeonParams(
        width=80,
        height=60,
        min_room_size=4,
        max_room_size=14,
        room_fill_pct=0.6,
        tile_wall=world.Tile(
            kind="dungeon_wall", char="#", walkable=False,
            fg=(95, 105, 120), bg=(22, 26, 32),
        ),
        tile_floor=world.Tile(
            kind="dungeon_floor", char=".", walkable=True,
            fg=(170, 185, 200), bg=(45, 52, 62),
        ),
        # Cold claim caves (merchant chain delve): tier 3 — ice worms +
        # frost spitters, the heaviest dungeon in act 0.
        monster_pool=("ice_worm", "frost_spitter"),
        monster_density=1.5,
        cache_guardian_pool=("assault_drone", "sentry_drone"),
        cache_guardian_count=2,
    ),
)
