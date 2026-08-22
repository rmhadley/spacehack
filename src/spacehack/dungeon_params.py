"""Configuration for procedural dungeon generation."""

from __future__ import annotations

from dataclasses import dataclass

from . import world


@dataclass(frozen=True)
class DungeonParams:
    """Configuration for procedural dungeon generation."""

    width: int = 50
    height: int = 40
    min_room_size: int = 5
    max_room_size: int = 12
    room_fill_pct: float = 0.65
    tile_wall: world.Tile = world.DUNGEON_WALL
    tile_floor: world.Tile = world.DUNGEON_FLOOR
    sight_radius: int = 8
    monster_pool: tuple[str, ...] = ()
    monster_density: float = 0.0
    cache_guardian_pool: tuple[str, ...] = ()
    cache_guardian_count: int = 1
