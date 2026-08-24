"""Barnard b — "The Ember Deep", an underground ring-and-spoke mine colony.

Three concentric tunnel rings carved through solid rock radiate from a
central landing shaft.  Buildings are doors cut into the rock wall with
inscribed names above them — no rectangle structures.

Layout (120×100, authored mine colony):

  * Central shaft — landing pad on the elevator deck.
  * Outer ring — spaceport door in the north wall.
  * Mid ring — The Ember cantina door, depot door.
  * Inner ring — storage alcoves.
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
            x_lo=42, x_hi=44, y_lo=0, y_hi=2,
            door_x=43, npc_id="",
        ),
        world.CityBuilding(
            label="bar",
            x_lo=20, x_hi=22, y_lo=47, y_hi=49,
            door_x=21, npc_id="barkeep",
        ),
        world.CityBuilding(
            label="depot",
            x_lo=99, x_hi=101, y_lo=47, y_hi=49,
            door_x=100, npc_id="depot_attendant",
        ),
    ),
    city_layout_id="barnards_mine_colony",
    city_npc_population=BARNARDS_POPULATION,
    transit_stations=(
        world.TransitStation(
            id="spaceport", name="Spaceport", district="outer ring",
            pos=world.Position(43, 7),
            destinations=("bar", "depot"),
        ),
        world.TransitStation(
            id="bar", name="The Ember", district="mid ring",
            pos=world.Position(18, 50),
            destinations=("spaceport", "depot"),
        ),
        world.TransitStation(
            id="depot", name="Salvage Depot", district="outer ring",
            pos=world.Position(102, 50),
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
    # The Act 0 old_smuggler stands in the bar (additively) only while
    # bar_q2_proof / bar_q3_rigparts / bar_q4_blackmarket are live —
    # see spawn_quest_npcs.
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
    # Bar chain delve site (bar_q3_rigparts): the old smuggler's lost
    # job went wrong in the cave network under the mining outpost —
    # the rig's power cell is still there. Planet-themed tiles
    # (burnt dust rock + ember-charred floor).
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
        # Hot rocky caves beneath the mining outpost (bar chain delve):
        # tier 2 — scavengers + prowlers, denser than the tier 1 sites.
        monster_pool=("rock_scavenger", "dust_prowler"),
        monster_density=1.5,
        cache_guardian_pool=("assault_drone",),
        cache_guardian_count=1,
    ),
)