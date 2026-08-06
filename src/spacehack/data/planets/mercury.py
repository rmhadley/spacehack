"""Mercury — a scorched rocky world, closest to Sol.

A small solar research station studies the sun from the best vantage
point in the system. The station is heavily shielded and cooled —
without protection, the surface heat would melt a ship in minutes.

Layout (40x24, compact):

  * spaceport, NW corner.
  * lab, NE corner — solar observatory.
"""
from __future__ import annotations

from ... import world
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import DESERT


SPEC = PlanetSpec(
    theme=DESERT,
    id="mercury",
    name="Mercury",
    char="m",
    fg=(180, 175, 165),
    description="A scorched rocky world — closest to Sol, home to a solar research station.",
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
            label="lab",
            x_lo=22, x_hi=37, y_lo=8,  y_hi=18,
            door_x=29, npc_id="research_officer",
        ),
    ),
    showroom_ships=(
        ("scout", 3, 2),
    ),
    npc_overrides=(),
    produces=(
        ("research_data", 10),
    ),
    demands=(
        ("food_rations", 10),
        ("electronics", 8),
        ("fuel_cells", 15),
    ),
    tech_level=1,
    # Militia chain delve site (mil_q2_cache): the classified requisition
    # cache sits deep in the scorched cave system under the research
    # station. Same BSP generator as the Mars surface — planet-themed
    # tiles (charred dark rock + ember floor).
    explorable_site_name="caves",
    dungeon_params=DungeonParams(
        width=80,
        height=60,
        min_room_size=4,
        max_room_size=14,
        room_fill_pct=0.6,
        tile_wall=world.Tile(
            kind="dungeon_wall", char="#", walkable=False,
            fg=(110, 90, 80), bg=(25, 18, 12),
        ),
        tile_floor=world.Tile(
            kind="dungeon_floor", char=".", walkable=True,
            fg=(200, 140, 90), bg=(60, 35, 18),
        ),
        # Scorched-cave fauna: scavenger packs + faster prowlers.
        monster_pool=("rock_scavenger", "dust_prowler"),
        monster_density=1.5,
        cache_guardian_pool=("assault_drone",),
        cache_guardian_count=1,
    ),
)
