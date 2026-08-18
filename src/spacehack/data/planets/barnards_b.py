"""Barnard b — a scorched rocky mining outpost on the edge of charted space.

Hot, dusty, and rough-and-tumble. The bar doubles as a cantina for
off-duty miners; the salvage depot buys scrap from pilots who push
too deep and come back with more holes than they left with.

Layout (60x40, same as Earth/Mars):

  * spaceport building, NW corner (same footprint as Earth).
  * bar (cantina) building, NE corner — "The Ember" cantina.
  * salvage depot building, southern row — buys salvaged ship parts.

Building NPCs: the bar keeps its barkeep and the salvage depot its
attendant (both resolve through the global catalog). The Act 0
``old_smuggler`` stands in the bar ADDITIVELY (``quest_npc_spots``)
while the bar chain needs him — the proof run through the power-cell
handover — then leaves.
"""
from __future__ import annotations

from ... import world
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="barnards_b",
    name="Barnard b",
    char="p",
    fg=(150, 100, 100),
    description="A scorched rocky super-Earth - hard ground, hard people.",
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
            label="depot",     x_lo=40, x_hi=55, y_lo=26, y_hi=35,
            door_x=47, npc_id="depot_attendant",
            door_north=True,
        ),
    ),
    showroom_ships=(
        ("cruiser", 11, 4),
        ("frigate", 15, 2),
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
