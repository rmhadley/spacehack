"""Procyon c — a cold icy body on the outer edge of the Procyon system.

A small research outpost drills through kilometres of ice to study
the ancient core samples. The station is cramped, quiet, and always
cold. Tunnels connect a small landing bay to a research lab staffed
by a lone science officer.

Layout (40x24, compact like the Science Port):

  * spaceport, NW corner.
  * lab, NE corner — research officer studies ice-core samples.

No NPC overrides — reuses the global ``research_officer`` catalog
entry (the same officer type as the Alpha Centauri Science Port,
but with the frozen-outpost context).
"""
from __future__ import annotations

from ... import world
from ...dungeon import DungeonParams
from . import PlanetSpec
from .themes import ICE


SPEC = PlanetSpec(
    theme=ICE,
    id="proc_planet_2",
    name="Procyon c",
    char="P",
    fg=(190, 200, 215),
    description="An icy body on Procyon's outer reach — a quiet research outpost.",
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
        ("scout",   3, 2),
        ("cruiser", 11, 4),
    ),
    npc_overrides=(),
    produces=(
        ("research_data", 10),
    ),
    demands=(
        ("food_rations", 8),
        ("fuel_cells", 10),
    ),
    tech_level=2,
    mission_tier=2,
    # Lab chain delve site (lab_q2_reference): the sealed research
    # cache holds the reference resonance dataset in the ice caves
    # beneath the outpost. Planet-themed tiles (deep ice blue).
    explorable_site_name="caves",
    dungeon_params=DungeonParams(
        width=80,
        height=60,
        min_room_size=4,
        max_room_size=14,
        room_fill_pct=0.6,
        tile_wall=world.Tile(
            kind="dungeon_wall", char="#", walkable=False,
            fg=(120, 150, 195), bg=(25, 35, 55),
        ),
        tile_floor=world.Tile(
            kind="dungeon_floor", char=".", walkable=True,
            fg=(200, 220, 245), bg=(55, 70, 95),
        ),
        # Deep ice caves (lab chain delve): tier 2 — worms + spitters.
        monster_pool=("ice_worm", "frost_spitter"),
        monster_density=1.6,
    ),
)
