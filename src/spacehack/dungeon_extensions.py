"""Reusable procedural dungeon-extension runtime.

An extension is a persistent, themed dungeon attached to a parent dungeon.
Content definitions live in :mod:`spacehack.data.dungeon_extensions`; this
module owns generation, map caching, connection transitions, and activation
state so future caves, ruins, stations, and prisons share one runtime.
"""

from __future__ import annotations

from collections import deque

from . import dungeon, world
from .game_context import DungeonExtensionState


_EXTENSION_KEY_PREFIX = "extension:"
ALIEN_PRISON_EXTENSION_ID = "mars_alien_prison"
_ENTRY_FLAVOR_KEY = "__entry_flavor__"


def _entry_flavor_key(floor: int) -> str:
    """Return the per-floor key for one-time entry flavor."""
    return f"{_ENTRY_FLAVOR_KEY}:floor:{floor}"


def floor_key(extension_id: str, floor: int) -> str:
    """Return the stable interior-cache key for one extension floor."""
    return f"{_EXTENSION_KEY_PREFIX}{extension_id}:floor:{floor}"


def extension_id_at(game_map: world.GameMap, position: world.Position) -> str | None:
    """Return the extension attached to a parent-dungeon connection."""
    _entry_id = getattr(game_map, "extension_entry_id", "")
    if _entry_id and getattr(game_map.tiles[position.y][position.x], "kind", "") == "stairs_down":
        return _entry_id
    # Migration for Mars surface maps written before entry metadata existed.
    _stairs = getattr(game_map, "mars_stairs_pos", None)
    if _stairs == position and game_map.tiles[position.y][position.x].kind == "stairs_down":
        return ALIEN_PRISON_EXTENSION_ID
    return None


def _floor_spec(extension_id: str, floor: int):
    """Resolve a floor definition from the data catalog."""
    from .data.dungeon_extensions import find_extension

    return find_extension(extension_id).floor(floor)


def _walkable_distances(
    game_map: world.GameMap,
    origin: world.Position,
) -> dict[tuple[int, int], int]:
    """Return cardinal walkable-cell distances from ``origin``."""
    _start = (origin.x, origin.y)
    _dist = {_start: 0}
    _queue: deque[tuple[int, int]] = deque([_start])
    while _queue:
        _x, _y = _queue.popleft()
        for _nx, _ny in (
            (_x + 1, _y), (_x - 1, _y),
            (_x, _y + 1), (_x, _y - 1),
        ):
            if not game_map.in_bounds(_nx, _ny):
                continue
            if (_nx, _ny) in _dist:
                continue
            if not game_map.tiles[_ny][_nx].walkable:
                continue
            _dist[(_nx, _ny)] = _dist[(_x, _y)] + 1
            _queue.append((_nx, _ny))
    return _dist


def _activation_positions(
    game_map: world.GameMap,
    origin: world.Position,
    events,
) -> dict[str, world.Position]:
    """Choose deterministic, increasingly distant trigger cells."""
    _distances = _walkable_distances(game_map, origin)
    _cells = sorted(
        _distances,
        key=lambda _cell: (_distances[_cell], _cell[1], _cell[0]),
    )
    if not _cells:
        return {}
    _positions: dict[str, world.Position] = {}
    _count = len(_cells)
    for _event in events:
        _fraction = min(max(_event.distance_fraction, 0.0), 1.0)
        _index = min(_count - 1, max(0, int((_count - 1) * _fraction)))
        _x, _y = _cells[_index]
        _positions[_event.id] = world.Position(_x, _y)
    return _positions


def _farthest_free_cell(
    game_map: world.GameMap,
    origin: world.Position,
) -> world.Position | None:
    """Return the farthest reachable, unoccupied floor cell from ``origin``."""
    _distances = _walkable_distances(game_map, origin)
    _occupied = {(entity.pos.x, entity.pos.y) for entity in game_map.entities}
    _cells = sorted(
        _distances,
        key=lambda _cell: (-_distances[_cell], _cell[1], _cell[0]),
    )
    for _x, _y in _cells:
        if (_x, _y) not in _occupied and (_x, _y) != (origin.x, origin.y):
            return world.Position(_x, _y)
    return None


def _set_floor_metadata(
    game_map: world.GameMap,
    extension_id: str,
    floor: int,
    spec,
    entry: world.Position,
) -> None:
    """Attach generic extension metadata and connection markers to a floor."""
    game_map.entry_spawn = entry
    game_map.up_stair_pos = entry
    game_map.location_name = spec.location_name
    game_map.extension_id = extension_id
    game_map.extension_floor = floor
    game_map.extension_entry_id = extension_id
    game_map.feature_theme = spec.feature_theme


def _feature_cells(
    game_map: world.GameMap,
    origin: world.Position,
    *,
    adjacent_to_wall: bool = False,
) -> list[tuple[int, int]]:
    """Return deterministic walkable cells suitable for visual features."""
    _distances = _walkable_distances(game_map, origin)
    _cells = sorted(
        _distances,
        key=lambda _cell: (-_distances[_cell], _cell[1], _cell[0]),
    )
    if not adjacent_to_wall:
        return _cells
    return [
        _cell for _cell in _cells
        if any(
            not game_map.is_walkable(_cell[0] + _dx, _cell[1] + _dy)
            for _dx, _dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        )
    ]


def _stamp_features(
    game_map: world.GameMap,
    cells: list[tuple[int, int]],
    tile: world.Tile,
    count: int,
    used: set[tuple[int, int]],
) -> None:
    """Paint up to ``count`` non-stair feature markers."""
    _placed = 0
    for _x, _y in cells:
        if _placed >= count:
            return
        if (_x, _y) in used:
            continue
        if game_map.tiles[_y][_x].kind in {"stairs_up", "stairs_down"}:
            continue
        game_map.tiles[_y][_x] = tile
        used.add((_x, _y))
        _placed += 1


def _stamp_prisoner_quarters(
    game_map: world.GameMap,
    origin: world.Position,
) -> None:
    """Add empty-cell doors and security posts to a quarters floor."""
    _used: set[tuple[int, int]] = set()
    _stamp_features(
        game_map,
        _feature_cells(game_map, origin, adjacent_to_wall=True),
        world.PRISON_CELL_DOOR,
        8,
        _used,
    )
    _stamp_features(
        game_map,
        _feature_cells(game_map, origin),
        world.SECURITY_POST,
        3,
        _used,
    )


def _stamp_defensive_layer(
    game_map: world.GameMap,
    origin: world.Position,
) -> None:
    """Add non-blocking barriers and active security nodes to Floor 3."""
    _used: set[tuple[int, int]] = set()
    _cells = _feature_cells(game_map, origin)
    _stamp_features(game_map, _cells, world.DEFENSE_BARRIER, 5, _used)
    _stamp_features(
        game_map,
        list(reversed(_cells)),
        world.SECURITY_NODE,
        4,
        _used,
    )


_FEATURE_STAMPERS = {
    "prisoner_quarters": _stamp_prisoner_quarters,
    "defensive_layer": _stamp_defensive_layer,
}


def _stamp_floor_features(
    game_map: world.GameMap,
    spec,
    origin: world.Position,
) -> None:
    """Apply a data-selected procedural feature theme to a floor."""
    _feature_stamper = _FEATURE_STAMPERS.get(spec.feature_theme)
    if _feature_stamper is not None:
        _feature_stamper(game_map, origin)


def _generate_floor(extension_id: str, floor: int):
    """Generate one procedural floor and its stable extension anchors."""
    _spec = _floor_spec(extension_id, floor)
    _game_map, _spawn = dungeon.generate_dungeon(_spec.params)
    # The generic generator creates an EXIT at its spawn wall. An extension
    # floor uses an explicit up-connection marker instead.
    _game_map.tiles[_spawn.y][_spawn.x] = world.STAIRS_UP
    _set_floor_metadata(_game_map, extension_id, floor, _spec, _spawn)
    _stamp_floor_features(_game_map, _spec, _spawn)
    # Populate before selecting the deeper connection so the stair tile is
    # guaranteed not to overlap a procedural enemy.
    dungeon.populate_dungeon(_game_map, _spec.params, _spawn)
    if _spec.has_down_stairs:
        _down = _farthest_free_cell(_game_map, _spawn)
        if _down is not None:
            _game_map.tiles[_down.y][_down.x] = world.STAIRS_DOWN
            _game_map.down_stair_pos = _down
    _game_map.activation_positions = _activation_positions(
        _game_map, _spawn, _spec.activation_events,
    )
    return _game_map, _spawn


def _sync_event_positions(
    state: DungeonExtensionState,
    game_map: world.GameMap,
) -> None:
    """Refresh current-floor activation anchors from its cached map."""
    state.event_positions = {
        _event_id: [_position.x, _position.y]
        if isinstance(_position, world.Position) else [
            int(_position[0]), int(_position[1]),
        ]
        for _event_id, _position in getattr(
            game_map, "activation_positions", {},
        ).items()
    }


def _ensure_state(ctx, extension_id: str) -> DungeonExtensionState:
    """Return the current run state, creating a compatible one if needed."""
    _state = ctx.dungeon_extension
    if _state is None or _state.extension_id != extension_id:
        _state = DungeonExtensionState(extension_id=extension_id)
        ctx.dungeon_extension = _state
    return _state


def enter_extension(
    ctx,
    parent_map: world.GameMap,
    parent_player: world.Entity,
    *,
    extension_id: str,
    parent_map_key: str = "",
) -> tuple[world.GameMap, world.Entity]:
    """Enter or re-enter floor 1 from a parent dungeon connection."""
    _state = _ensure_state(ctx, extension_id)
    _state.active = True
    if not parent_map_key:
        parent_map_key = next(
            (
                _key for _key, _cached_map in ctx.interiors.items()
                if _cached_map is parent_map
            ),
            "",
        )
    if not parent_map_key:
        raise ValueError("Dungeon extension parent map is not cached")
    _state.parent_map_key = parent_map_key
    _state.parent_position = parent_player.pos
    _floor = _state.current_floor
    _key = floor_key(extension_id, _floor)
    _game_map = ctx.interiors.get(_key)
    if _game_map is None:
        _game_map, _spawn = _generate_floor(extension_id, _floor)
        ctx.interiors[_key] = _game_map
        _sync_event_positions(_state, _game_map)
    else:
        _ensure_floor_connections(_game_map, extension_id, _floor)
        _spawn = getattr(_game_map, "entry_spawn", None)
        if _spawn is None:
            _spawn = _first_walkable(_game_map)
        _sync_event_positions(_state, _game_map)
    if _spawn is None:
        raise ValueError("Dungeon extension floor has no walkable entry")

    _remove_player(_game_map)
    _remove_player(parent_map)
    _player = _make_player(_spawn)
    _game_map.entities.append(_player)
    ctx.game_map = _game_map
    ctx.player = _player
    if _game_map.seen is None:
        dungeon.init_fog(_game_map)
    dungeon.reveal_around(_game_map, _spawn)
    _show_first_entry_flavor(ctx, _state, _floor)
    return _game_map, _player


def _show_first_entry_flavor(
    ctx,
    state: DungeonExtensionState,
    floor: int,
) -> None:
    """Show and persist a floor's one-time entry flavor, if defined."""
    _flavor_key = _entry_flavor_key(floor)
    if _flavor_key in state.activated_events or (
        floor == 1 and _ENTRY_FLAVOR_KEY in state.activated_events
    ):
        return
    # Lightweight test contexts may omit the terminal context; real
    # GameContext instances always provide it for modal presentation.
    if getattr(ctx, "context", None) is None:
        return
    _flavor = _floor_spec(state.extension_id, floor).entry_flavor
    if _flavor is None:
        return
    from .main_quest import show_gate_popup

    show_gate_popup(
        ctx,
        _flavor.faction_label,
        _flavor.message,
        title=_flavor.title,
    )
    state.activated_events.add(_flavor_key)


def _valid_stair_position(
    game_map: world.GameMap,
    position,
    kind: str,
) -> bool:
    """Return whether metadata points to a matching in-bounds stair tile."""
    return (
        isinstance(position, world.Position)
        and game_map.in_bounds(position.x, position.y)
        and game_map.tiles[position.y][position.x].kind == kind
    )


def _find_stair_position(
    game_map: world.GameMap,
    kind: str,
) -> world.Position | None:
    """Find the first stair tile of ``kind`` in map order."""
    for _y, _row in enumerate(game_map.tiles):
        for _x, _tile in enumerate(_row):
            if _tile.kind == kind:
                return world.Position(_x, _y)
    return None


def _ensure_floor_connections(
    game_map: world.GameMap,
    extension_id: str,
    floor: int,
) -> None:
    """Repair connection metadata on a cached floor from an older save."""
    _spec = _floor_spec(extension_id, floor)
    _entry = getattr(game_map, "entry_spawn", None)
    if not _valid_stair_position(game_map, _entry, "stairs_up"):
        _entry = _find_stair_position(game_map, "stairs_up")
    if _entry is None:
        _entry = getattr(game_map, "up_stair_pos", None)
    if not _valid_stair_position(game_map, _entry, "stairs_up"):
        _entry = _first_walkable(game_map)
    if _entry is None or not game_map.in_bounds(_entry.x, _entry.y):
        return
    if game_map.tiles[_entry.y][_entry.x].kind != "stairs_up":
        game_map.tiles[_entry.y][_entry.x] = world.STAIRS_UP
    _set_floor_metadata(game_map, extension_id, floor, _spec, _entry)
    if not _spec.has_down_stairs:
        return
    _down = getattr(game_map, "down_stair_pos", None)
    if not _valid_stair_position(game_map, _down, "stairs_down"):
        _down = _find_stair_position(game_map, "stairs_down")
    if _valid_stair_position(game_map, _down, "stairs_down"):
        game_map.down_stair_pos = _down
        return
    _down = _farthest_free_cell(game_map, _entry)
    if _down is not None:
        game_map.tiles[_down.y][_down.x] = world.STAIRS_DOWN
        game_map.down_stair_pos = _down


def _connection_position(
    game_map: world.GameMap,
    kind: str,
) -> world.Position | None:
    """Return a validated connection position from metadata or tile scan."""
    _position = getattr(
        game_map,
        "up_stair_pos" if kind == "stairs_up" else "down_stair_pos",
        None,
    )
    if _valid_stair_position(game_map, _position, kind):
        return _position
    return _find_stair_position(game_map, kind)


def _get_or_generate_floor(
    ctx,
    extension_id: str,
    floor: int,
) -> world.GameMap:
    """Return a cached extension floor, generating and caching it if absent."""
    _key = floor_key(extension_id, floor)
    _game_map = ctx.interiors.get(_key)
    if _game_map is None:
        _game_map, _ = _generate_floor(extension_id, floor)
        ctx.interiors[_key] = _game_map
    else:
        _ensure_floor_connections(_game_map, extension_id, floor)
    return _game_map


def transition_floor(
    ctx,
    direction: int,
) -> tuple[world.GameMap, world.Entity]:
    """Move one floor up or down inside the active extension."""
    _state = ctx.dungeon_extension
    if _state is None or not _state.active:
        raise ValueError("No active dungeon extension to traverse")
    if direction not in (-1, 1):
        raise ValueError("Floor transition direction must be -1 or 1")
    _target_floor = _state.current_floor + direction
    if _target_floor < 1:
        raise ValueError("Already at the extension entrance")
    try:
        _target_map = _get_or_generate_floor(
            ctx, _state.extension_id, _target_floor,
        )
    except KeyError:
        raise ValueError("No extension floor at that depth") from None
    _source_map = ctx.game_map
    _ensure_floor_connections(
        _target_map, _state.extension_id, _target_floor,
    )
    _target_kind = "stairs_up" if direction > 0 else "stairs_down"
    _target_pos = _connection_position(_target_map, _target_kind)
    if _target_pos is None:
        raise ValueError("Extension floor connection is unavailable")
    _remove_player(_source_map)
    _remove_player(_target_map)
    _player = _make_player(_target_pos)
    _target_map.entities.append(_player)
    _state.current_floor = _target_floor
    _sync_event_positions(_state, _target_map)
    ctx.game_map = _target_map
    ctx.player = _player
    if _target_map.seen is None:
        dungeon.init_fog(_target_map)
    dungeon.reveal_around(_target_map, _target_pos)
    _show_first_entry_flavor(ctx, _state, _target_floor)
    return _target_map, _player


def leave_extension(
    ctx,
    extension_map: world.GameMap,
) -> tuple[world.GameMap, world.Entity]:
    """Return from the active extension floor to its parent dungeon."""
    _state = ctx.dungeon_extension
    if _state is None or not _state.active:
        raise ValueError("No active dungeon extension to leave")
    _parent_map = ctx.interiors.get(_state.parent_map_key)
    if _parent_map is None:
        raise ValueError("Dungeon extension parent map is unavailable")
    _parent_pos = _state.parent_position or _first_walkable(_parent_map)
    if _parent_pos is None:
        raise ValueError("Dungeon extension parent map has no return position")
    _remove_player(extension_map)
    _remove_player(_parent_map)
    _player = _make_player(_parent_pos)
    _parent_map.entities.append(_player)
    _state.active = False
    ctx.game_map = _parent_map
    ctx.player = _player
    if _parent_map.seen is not None:
        dungeon.reveal_around(_parent_map, _parent_pos)
    return _parent_map, _player


def _make_player(position: world.Position) -> world.Entity:
    """Create the transient player entity used by extension handoffs."""
    return world.Entity(
        char="@", fg=(255, 255, 255), pos=position, name="Player",
    )


def _remove_player(game_map: world.GameMap) -> None:
    """Remove transient player entities from a cached map."""
    game_map.entities[:] = [
        _entity for _entity in game_map.entities if _entity.char != "@"
    ]


def _first_walkable(game_map: world.GameMap) -> world.Position | None:
    """Return the first walkable cell, or ``None`` for an empty map."""
    for _y, _row in enumerate(game_map.tiles):
        for _x, _tile in enumerate(_row):
            if _tile.walkable:
                return world.Position(_x, _y)
    return None


def _event_position(ctx, event_id: str) -> world.Position | None:
    """Resolve an activation anchor from serialized run state."""
    _state = ctx.dungeon_extension
    if _state is None:
        return None
    _raw = _state.event_positions.get(event_id)
    if isinstance(_raw, (list, tuple)) and len(_raw) >= 2:
        return world.Position(int(_raw[0]), int(_raw[1]))
    return None


def _activation_cells(
    game_map: world.GameMap,
    position: world.Position,
    occupied: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Find the nearest ring of free floor cells around an activation."""
    _max_radius = max(game_map.width, game_map.height)
    for _radius in range(_max_radius):
        _cells = [
            (_x, _y)
            for _y in range(position.y - _radius, position.y + _radius + 1)
            for _x in range(position.x - _radius, position.x + _radius + 1)
            if max(abs(_x - position.x), abs(_y - position.y)) == _radius
            and game_map.in_bounds(_x, _y)
            and game_map.tiles[_y][_x].walkable
            and (_x, _y) not in occupied
        ]
        if _cells:
            return _cells
    return []


def _spawn_activation_group(
    game_map: world.GameMap,
    position: world.Position,
    event,
) -> int:
    """Spawn one capped security group around an activation anchor."""
    from .data.npc_chars import find_npc_char

    try:
        _spec = find_npc_char(event.enemy_id)
    except KeyError:
        return 0
    _occupied = {(e.pos.x, e.pos.y) for e in game_map.entities}
    _cells = _activation_cells(game_map, position, _occupied)
    _count = max(0, min(event.count, event.max_count))
    if not _cells or _count == 0:
        return 0
    return dungeon._scatter_squad(
        game_map.entities,
        _occupied,
        enemy_id=event.enemy_id,
        cells=_cells,
        count=_count,
        squad_id=f"{event.id}_security",
        char=_spec.char,
        fg=_spec.fg,
    )


def tick_activation(ctx) -> bool:
    """Activate any reached extension security events once per run.

    Returns ``True`` when at least one event fired. Player-facing flavor is
    intentionally delivered through the existing main-quest gate popup.
    """
    _state = ctx.dungeon_extension
    if _state is None or not _state.active:
        return False
    _spec = _floor_spec(_state.extension_id, _state.current_floor)
    _fired = False
    for _event in _spec.activation_events:
        if _event.id in _state.activated_events:
            continue
        _position = _event_position(ctx, _event.id)
        if _position is None:
            continue
        if max(
            abs(ctx.player.pos.x - _position.x),
            abs(ctx.player.pos.y - _position.y),
        ) > _event.trigger_radius:
            continue
        _spawned = _spawn_activation_group(ctx.game_map, _position, _event)
        if _spawned == 0:
            continue
        _state.activated_events.add(_event.id)
        _fired = True
        from .main_quest import show_gate_popup

        show_gate_popup(
            ctx,
            _event.faction_label,
            _event.message,
            title=_event.title,
        )
        if _spawned:
            ctx.log.add(f"Security systems online: {_spawned} hostile unit(s) activated.")
    return _fired
