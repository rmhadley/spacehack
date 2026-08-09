"""Deep-cell feature stamping for themed dungeon extensions."""

from __future__ import annotations


from . import landmark, world


_INACTIVE_TERMINAL_FLAVORS: tuple[str, ...] = (
    "The terminal is dark. Its screen shows nothing.",
    "The terminal is cold to the touch. Long dead.",
    "The terminal's surface is cracked, its power long gone.",
    "The terminal flickers once, then goes dark.",
    "A dead terminal. Whatever powered these, it has been silent for ages.",
)


def stamp_dead_terminals(
    game_map: world.GameMap,
    cells: list[tuple[int, int]],
    *,
    count: int = 5,
) -> None:
    """Scatter static, unpowered terminals across a cell's walkable floor."""
    _stair_cells = {
        (_position.x, _position.y)
        for _position in (
            getattr(game_map, "up_stair_pos", None),
            getattr(game_map, "down_stair_pos", None),
        )
        if _position is not None
    }
    _occupied = {(entity.pos.x, entity.pos.y) for entity in game_map.entities}
    _flavor_index = len(game_map.entities)
    _placed = 0
    for _x, _y in cells:
        if _placed >= count:
            break
        if (_x, _y) in _occupied or (_x, _y) in _stair_cells:
            continue
        if (
            not game_map.is_walkable(_x, _y)
            or game_map.tiles[_y][_x].kind in {"claw_scar", "landmark_entrance"}
        ):
            continue
        _occupied.add((_x, _y))
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


def stamp_deep_cell(
    game_map: world.GameMap,
    origin: world.Position,
    *,
    landmark_variants,
) -> None:
    """Dress a deep cell: torn doors, dead terminals, and alien flooring.

    The live data terminal is stamped separately through the interaction
    anchor pass; this helper supplies only the atmosphere — torn-out door
    frames along the walls and scattered unpowered terminals as static
    flavor entities.

    Landmark selection is supplied by the floor data so this module stays a
    thin, reusable content helper.
    """
    from .engine import RNG

    _layout_id = landmark.choose_weighted_variant(
        landmark_variants,
        RNG.random(),
    )
    _asset = landmark.load_landmark(_layout_id)
    # The procedural spawn is only a temporary placement anchor. The
    # authored arrival marker becomes the real elevator landing, so remove
    # the temporary stair before stamping to avoid duplicate up-connections.
    if game_map.in_bounds(origin.x, origin.y):
        game_map.tiles[origin.y][origin.x] = world.DUNGEON_FLOOR
    _stamp = landmark.stamp_landmark(game_map, _asset, origin)
    game_map.landmark_footprint = set(_stamp.footprint)
    # The authored landmark owns the elevator arrival. Reassert the
    # connection after stamping so a bridge footprint can never hide it.
    if _stamp.arrival is not None:
        game_map.tiles[_stamp.arrival.y][_stamp.arrival.x] = world.STAIRS_UP
    game_map.landmark_variant_id = _layout_id
    game_map.landmark_interaction_cells = [
        _entity.pos for _entity in game_map.entities
        if _entity.name == "Landmark Terminal"
    ]
    if _stamp.arrival is not None:
        game_map.entry_spawn = _stamp.arrival
        game_map.up_stair_pos = _stamp.arrival
    for _x, _y in _stamp.footprint:
        _tile = game_map.tiles[_y][_x]
        if _tile.kind == "dungeon_floor":
            game_map.tiles[_y][_x] = world.Tile(
                kind="deep_cell_floor",
                char=_tile.char,
                walkable=_tile.walkable,
                fg=_tile.fg,
                bg=_tile.bg,
                bg_override=_tile.bg_override,
            )
    stamp_dead_terminals(
        game_map,
        sorted(_stamp.footprint, key=lambda _cell: (_cell[1], _cell[0])),
    )
