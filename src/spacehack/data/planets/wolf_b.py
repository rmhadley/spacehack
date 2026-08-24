"""Wolf 359 b — a dark, airless rock on the frontier of charted space.

The Scab — a pirate-run listening post carved into a cold crater
settlement. The landing clearing was scraped flat by the first
salvage crews; the Salty Grave bar was dug into the southern rock
shelf; cargo containers were stacked into a depot; and antenna masts
were raised on the northern ridge. Nothing was planned — it just
accumulated, like scab tissue over a wound.

Layout (120×80, authored crater outpost):

  * spaceport on the west side, depot on the east.
  * landing pad scraped flat in the gap between them.
  * showcase ships parked on the apron above the pad, terminals below.
  * bar — The Salty Grave — dug into the southern rock shelf.
  * antenna masts on the northern ridge (non-enterable).
  * cave entrance (delve site) in the south-eastern wall.
  * scattered shacks, barrel fires, and scrap heaps throughout.

NPC overrides: the Black-Market Operator (bar) and Frontier Operator
(depot) retain their existing flavour. A small crew of pirates and
scavengers loiter between the pad, the depot, and the bar.
"""
from __future__ import annotations

from ... import world
from ...data import npcs as npc_module
from ...dungeon import DungeonParams
from ..city_npcs import WOLF_B_POPULATION
from . import PlanetSpec
from .themes import PIRATE_OUTPOST


SPEC = PlanetSpec(
    theme=PIRATE_OUTPOST,
    id="wolf_b",
    name="Wolf 359 b",
    char="p",
    fg=(80, 60, 50),
    description="A dark, airless rock - a pirate-run listening post on the frontier. No questions asked.",
    width=120,
    height=80,
    hangar_anchor=world.Position(40, 16),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=10, x_hi=33, y_lo=12, y_hi=22,
            door_x=20, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=14, x_hi=34, y_lo=50, y_hi=58,
            door_x=23, npc_id="wolf_barkeep",
        ),
        world.CityBuilding(
            label="depot",
            x_lo=48, x_hi=67, y_lo=14, y_hi=22,
            door_x=57, npc_id="depot_attendant",
        ),
    ),
    city_layout_id="wolf_crater_settlement",
    city_npc_population=WOLF_B_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Landing Pad", district="centre",
            pos=world.Position(44, 18),
            destinations=("depot", "bar"),
        ),
        world.TransitStation(
            id="depot", name="The Stack", district="east yard",
            pos=world.Position(58, 24),
            destinations=("spaceport", "bar"),
        ),
        world.TransitStation(
            id="bar", name="Salty Grave", district="south shelf",
            pos=world.Position(26, 60),
            destinations=("spaceport", "depot"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "wolf_spaceport_interior"),
        ("bar", "wolf_bar_interior"),
        ("depot", "wolf_depot_interior"),
    ),
    showroom_ships=(
        ("scout",  3, -3),
        ("hauler", 6, -3),
        ("cruiser", 4, -2),
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
                    "operator sizes you up - 'You got something for me, or "
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
    produces=(
        ("weapons_blackmarket", 15),
    ),
    demands=(
        ("food_rations", 12),
        ("fuel_cells", 10),
        ("medical_supplies", 8),
        ("weapons_blackmarket", 10),
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
    # post — quest-tagged rare_earth_metals deep inside.
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
        monster_pool=("ice_worm", "frost_spitter"),
        monster_density=1.5,
        cache_guardian_pool=("assault_drone", "sentry_drone"),
        cache_guardian_count=2,
    ),
)