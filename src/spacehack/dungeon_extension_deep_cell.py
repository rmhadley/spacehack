"""Deep-cell feature stamping for themed dungeon extensions."""

from __future__ import annotations

from . import landmark, world
from .text import get as _t_get


_INACTIVE_TERMINAL_FLAVOR_KEYS: tuple[str, ...] = tuple(
    f"runtime.prison.dead_terminal_flavor_{_index}"
    for _index in range(1, 6)
)


def _terminal_entity(position: world.Position, flavor_index: int) -> world.Entity:
    """Build one dead terminal with overlay-backed flavor."""
    _flavor_key = _INACTIVE_TERMINAL_FLAVOR_KEYS[
        flavor_index % len(_INACTIVE_TERMINAL_FLAVOR_KEYS)
    ]
    return world.Entity(
        char="=",
        fg=(90, 110, 135),
        pos=position,
        name=_t_get("runtime.prison.dead_terminal_name"),
        interaction_flavor=_t_get(_flavor_key),
    )


def _terminal_cell_ok(game_map, x: int, y: int, occupied, stair_cells) -> bool:
    """Return whether a cell can receive a dead terminal."""
    return (
        (x, y) not in occupied
        and (x, y) not in stair_cells
        and game_map.is_walkable(x, y)
        and game_map.tiles[y][x].kind not in {"claw_scar", "landmark_entrance"}
    )


def stamp_dead_terminals(
    game_map: world.GameMap,
    cells: list[tuple[int, int]],
    *,
    count: int = 5,
) -> None:
    """Scatter static, unpowered terminals across a cell's walkable floor."""
    _stair_cells = {
        (position.x, position.y)
        for position in (
            getattr(game_map, "up_stair_pos", None),
            getattr(game_map, "down_stair_pos", None),
        )
        if position is not None
    }
    _occupied = {(entity.pos.x, entity.pos.y) for entity in game_map.entities}
    _flavor_index = len(game_map.entities)
    _placed = 0
    for _x, _y in cells:
        if _placed >= count:
            break
        if not _terminal_cell_ok(game_map, _x, _y, _occupied, _stair_cells):
            continue
        _position = world.Position(_x, _y)
        _occupied.add((_x, _y))
        game_map.entities.append(_terminal_entity(_position, _flavor_index))
        _flavor_index += 1
        _placed += 1


def _prepare_landmark(game_map, origin, asset):
    """Stamp the authored landmark and preserve its arrival metadata."""
    if game_map.in_bounds(origin.x, origin.y):
        game_map.tiles[origin.y][origin.x] = world.DUNGEON_FLOOR
    _stamp = landmark.stamp_landmark(game_map, asset, origin)
    game_map.landmark_footprint = set(_stamp.footprint)
    if _stamp.arrival is not None:
        game_map.tiles[_stamp.arrival.y][_stamp.arrival.x] = world.STAIRS_UP
    game_map.landmark_interaction_cells = [
        entity.pos for entity in game_map.entities
        if entity.name == "Landmark Terminal"
    ]
    if _stamp.arrival is not None:
        game_map.entry_spawn = _stamp.arrival
        game_map.up_stair_pos = _stamp.arrival
    return _stamp


def _paint_deep_cell_floor(game_map, footprint) -> None:
    """Convert ordinary footprint floor tiles to deep-cell flooring."""
    for _x, _y in footprint:
        _tile = game_map.tiles[_y][_x]
        if _tile.kind == "dungeon_floor":
            game_map.tiles[_y][_x] = world.Tile(
                kind="deep_cell_floor",
                char=_tile.char,
                walkable=_tile.walkable,
                fg=_tile.fg,
                bg=_tile.bg,
                bg_override=_tile.bg_override,
                blocked_message=_tile.blocked_message,
            )


def stamp_deep_cell(
    game_map: world.GameMap,
    origin: world.Position,
    *,
    landmark_variants,
) -> None:
    """Dress a deep cell with an authored landmark and static terminals."""
    from .engine import RNG

    _layout_id = landmark.choose_weighted_variant(landmark_variants, RNG.random())
    _asset = landmark.load_landmark(_layout_id)
    _stamp = _prepare_landmark(game_map, origin, _asset)
    game_map.landmark_variant_id = _layout_id
    _paint_deep_cell_floor(game_map, _stamp.footprint)
    stamp_dead_terminals(
        game_map,
        sorted(_stamp.footprint, key=lambda _cell: (_cell[1], _cell[0])),
    )
