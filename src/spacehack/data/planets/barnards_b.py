"""Barnard b — "The Ember Deep", an underground ring-and-spoke mine colony.

Three concentric tunnel rings carved through solid rock radiate from a
central landing shaft.  Buildings are doors carved into the rock face
with inscribed names above them.

Layout (120×100, authored mine colony):

  * Central shaft — landing pad on the elevator deck.
  * Outer ring — spaceport door in the north wall.
  * Mid ring — The Ember cantina and salvage depot doors.
  * 6 radial haulage drifts connecting the three rings.
"""

from __future__ import annotations

from ... import world
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import DESERT
from ..city_npcs import BARNARDS_POPULATION


SPEC = PlanetSpec(
    theme=DESERT,
    id="barnards_b",
    name="Barnard b",
    char="p",
    fg=(150, 100, 100),
    description="A scorched rocky super-Earth - hard ground, hard people.",
    width=120,
    height=100,
    hangar_anchor=world.Position(60, 50),
    buildings=(
        world.CityBuilding(
            label="spaceport",
            x_lo=55, x_hi=65, y_lo=38, y_hi=40,
            door_x=60, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=20, x_hi=22, y_lo=45, y_hi=47,
            door_x=21, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="depot",
            x_lo=97, x_hi=103, y_lo=45, y_hi=47,
            door_x=100, npc_id="depot_attendant",
        ),
    ),
    city_layout_id="barnards_mine_colony",
    city_npc_population=BARNARDS_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="outer ring",
            pos=world.Position(62, 42), serves="barnards_spaceport",
            destinations=("bar", "depot"),
        ),
        world.TransitStation(
            id="bar", name="The Ember", district="mid ring",
            pos=world.Position(28, 50), serves="bar",
            destinations=("spaceport", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Salvage Depot", district="outer ring",
            pos=world.Position(107, 48), serves="barnards_depot",
            destinations=("spaceport", "bar"),
        ),
    ),
    interior_layouts=(
        ("spaceport", "barnards_spaceport_interior"),
        ("bar", "barnards_bar_interior"),
        ("depot", "barnards_depot_interior"),
    ),
    showroom_ships=(
        ("cruiser", 2, -5),
        ("frigate", -6, -5),
    ),
    npc_overrides=(),
    quest_npc_spots=(
        ("old_smuggler", "bar"),
    ),
    produces=(
        ("ore_processed", 35),
    ),
    demands=(
        ("food_rations", 15),
        ("machine_parts", 10),
        ("fuel_cells", 12),
        ("weapons_blackmarket", 8),
    ),
    tech_level=3,
    mission_tier=2,
    explorable_site_name="caves",
    dungeon_params=DungeonParams(
        width=80,
        height=60,
        min_room_size=4,
        max_room_size=14,
        room_fill_pct=0.6,
        tile_wall=world.Tile(
            kind="dungeon_wall", char="#", walkable=False,
            fg=(120, 85, 70), bg=(30, 20, 14),
        ),
        tile_floor=world.Tile(
            kind="dungeon_floor", char=".", walkable=True,
            fg=(210, 150, 95), bg=(65, 38, 20),
        ),
        monster_pool=("rock_scavenger", "dust_prowler"),
        monster_density=1.5,
        cache_guardian_pool=("sentry_drone",),  # leftover Militia watch drone - assault spike pulled (standing ruling)
        cache_guardian_count=1,
    ),
)