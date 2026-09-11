"""City-safe stamping for authored exterior landmark layouts."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from . import landmark, world


@dataclass(frozen=True)
class CityLandmarkStamp:
    """Placement metadata for one authored city landmark."""

    layout_id: str
    origin: world.Position
    footprint: frozenset[tuple[int, int]]
    entrance: world.Position | None = None


@dataclass(frozen=True)
class CityInteriorAsset:
    """Parsed city interior and its player arrival point."""

    layout_id: str
    game_map: world.GameMap
    spawn: world.Position


def door_placement_error(
    exits: list[tuple[int, int]],
    spawn: tuple[int, int] | None,
    height: int,
) -> str | None:
    """Return the P/exit placement violation for one city interior.

    The shared placement rule (doc 45): exactly one exit, on the south
    perimeter — the wall row itself (in-wall doorway) or the walkable
    row just inside it — with the P spawn orthogonally adjacent AND
    inside the perimeter, so the player appears just inside the door
    they came through (never beside it in the wall row). Pure: the
    load-time gate, the layout-editor validator, and the repo audit
    tests all derive their inputs and call this one predicate.
    """
    if len(exits) != 1:
        return f"has {len(exits)} exits, expected exactly one"
    exit_x, exit_y = exits[0]
    if exit_y not in (height - 1, height - 2):
        return (
            f"exit at row {exit_y} of {height} is not on the south perimeter"
        )
    if spawn is None:
        return "has no P spawn"
    spawn_x, spawn_y = spawn
    if abs(spawn_x - exit_x) + abs(spawn_y - exit_y) != 1:
        return (
            f"P at ({spawn_x},{spawn_y}) is not orthogonally adjacent "
            f"to the exit at ({exit_x},{exit_y})"
        )
    if spawn_y >= height - 1:
        return (
            f"P at ({spawn_x},{spawn_y}) sits on the south wall row; "
            "it must sit just inside the door"
        )
    return None


def load_city_interior(layout_id: str) -> CityInteriorAsset:
    """Load a city interior through the shared authored-layout parser."""
    from .dungeon_layout import load_layout

    game_map, spawn = load_layout(
        layout_id,
        layout_dir=landmark._LANDMARK_DIR,
        require_spawn=True,
    )
    if spawn is None:
        raise ValueError(f"City interior {layout_id!r} has no P spawn")
    exits = [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "exit"
    ]
    error = door_placement_error(
        exits, (spawn.x, spawn.y), game_map.height,
    )
    if error is not None:
        raise ValueError(f"City interior {layout_id!r} {error}")
    game_map.entry_spawn = spawn
    game_map.interior_cache_key = f"city:{layout_id}"
    return CityInteriorAsset(layout_id, game_map, spawn)


def _city_tile(tile: world.Tile) -> world.Tile:
    """Return an authored city tile with a readable dark underlay."""
    bg = tuple(max(28, channel) for channel in tile.bg)
    luma = 0.2126 * bg[0] + 0.7152 * bg[1] + 0.0722 * bg[2]
    if luma >= 60:
        return tile
    if luma < 60:
        scale = 60 / max(1.0, luma)
        bg = tuple(min(255, max(28, round(channel * scale) + 1)) for channel in bg)
    return world.Tile(
        kind=tile.kind,
        char=tile.char,
        walkable=tile.walkable,
        fg=tile.fg,
        bg=bg,
        bg_override=tile.bg_override,
        blocked_message=tile.blocked_message,
    )


def _validate_city_asset(game_map, layout_id, origin, asset) -> None:
    """Validate a fixed city landmark placement."""
    if origin.x < 0 or origin.y < 0:
        raise ValueError("city landmark origin must be non-negative")
    if origin.x + asset.width > game_map.width or origin.y + asset.height > game_map.height:
        raise ValueError(f"city landmark {layout_id!r} does not fit at {origin}")


def _copy_city_asset(game_map, origin, asset) -> tuple[set[tuple[int, int]], world.Position | None]:
    """Copy tiles and entities from one parsed city asset."""
    footprint: set[tuple[int, int]] = set()
    entrance: world.Position | None = None
    for y, row in enumerate(asset.tiles):
        for x, tile in enumerate(row):
            position = world.Position(origin.x + x, origin.y + y)
            game_map.tiles[position.y][position.x] = _city_tile(tile)
            footprint.add((position.x, position.y))
            if tile.kind in {"city_building_door", "dungeon_door", "landmark_entrance"}:
                if entrance is not None:
                    raise ValueError("city landmark has multiple entrances")
                entrance = position
    for entity in asset.entities:
        copied = copy.copy(entity)
        copied.pos = world.Position(origin.x + entity.pos.x, origin.y + entity.pos.y)
        game_map.entities.append(copied)
    return footprint, entrance


def stamp_city_landmark(
    game_map: world.GameMap,
    layout_id: str,
    origin: world.Position,
) -> CityLandmarkStamp:
    """Copy one authored landmark at a fixed origin into a city map."""
    asset = landmark.load_landmark(layout_id)
    _validate_city_asset(game_map, layout_id, origin, asset)
    footprint, entrance = _copy_city_asset(game_map, origin, asset)
    return CityLandmarkStamp(
        layout_id=layout_id,
        origin=origin,
        footprint=frozenset(footprint),
        entrance=entrance,
    )


def load_city_landmark(layout_id: str) -> world.GameMap:
    """Load one city asset through the shared landmark loader."""
    return landmark.load_landmark(layout_id)
