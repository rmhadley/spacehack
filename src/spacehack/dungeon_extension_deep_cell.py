"""Deep-cell feature stamping for themed dungeon extensions."""

from __future__ import annotations

from typing import Callable

from . import world


_INACTIVE_TERMINAL_FLAVORS: tuple[str, ...] = (
    "The terminal is dark. Its screen shows nothing.",
    "The terminal is cold to the touch. Long dead.",
    "The terminal's surface is cracked, its power long gone.",
    "The terminal flickers once, then goes dark.",
    "A dead terminal. Whatever powered these, it has been silent for ages.",
)


def stamp_deep_cell(
    game_map: world.GameMap,
    origin: world.Position,
    *,
    feature_cells: Callable,
    stamp_features: Callable,
) -> None:
    """Dress a deep cell: torn doors, dead terminals, and alien flooring.

    The live data terminal is stamped separately through the interaction
    anchor pass; this helper supplies only the atmosphere — torn-out door
    frames along the walls and scattered unpowered terminals as static
    flavor entities.

    ``feature_cells`` / ``stamp_features`` are injected from the extension
    runtime so this module stays a thin, reusable content helper.
    """
    for _y, _row in enumerate(game_map.tiles):
        for _x, _tile in enumerate(_row):
            # Stairs are walkable and must survive the theme pass — the
            # floor conversion never touches connection markers.
            if _tile.walkable and _tile.kind not in ("stairs_up", "stairs_down"):
                game_map.tiles[_y][_x] = world.DEEP_CELL_FLOOR
    _used: set[tuple[int, int]] = set()
    _cells = feature_cells(game_map, origin, adjacent_to_wall=True)
    stamp_features(game_map, _cells, world.TORN_DOOR, 6, _used)
    _dead_cells = feature_cells(game_map, origin)
    _stair_cells = {
        (_position.x, _position.y)
        for _position in (
            getattr(game_map, "up_stair_pos", None),
            getattr(game_map, "down_stair_pos", None),
        )
        if _position is not None
    }
    _flavor_index = len(game_map.entities)
    _placed = 0
    for _x, _y in _dead_cells:
        if _placed >= 5:
            break
        if (_x, _y) in _used or (_x, _y) in _stair_cells:
            continue
        _used.add((_x, _y))
        game_map.entities.append(world.Entity(
            char="=",
            fg=(90, 110, 135),
            pos=world.Position(_x, _y),
            name="Dead Terminal",
            interaction_flavor=_INACTIVE_TERMINAL_FLAVORS[
                _flavor_index % len(_INACTIVE_TERMINAL_FLAVORS)
            ],
        ))
        _flavor_index += 1
        _placed += 1
