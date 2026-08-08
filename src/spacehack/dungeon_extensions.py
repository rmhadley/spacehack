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


def _generate_floor(extension_id: str, floor: int):
    """Generate one procedural floor and its stable activation anchors."""
    _spec = _floor_spec(extension_id, floor)
    _game_map, _spawn = dungeon.generate_dungeon(_spec.params)
    # The generic generator creates an EXIT at its spawn wall. An extension
    # floor uses an explicit up-connection marker instead.
    _game_map.tiles[_spawn.y][_spawn.x] = world.STAIRS_UP
    _game_map.entry_spawn = _spawn
    _game_map.location_name = _spec.location_name
    _game_map.extension_id = extension_id
    _game_map.extension_floor = floor
    _game_map.extension_entry_id = extension_id
    _game_map.activation_positions = _activation_positions(
        _game_map, _spawn, _spec.activation_events,
    )
    return _game_map, _spawn


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
        _state.event_positions = {
            _event_id: [_position.x, _position.y]
            for _event_id, _position in getattr(
                _game_map, "activation_positions", {},
            ).items()
        }
    else:
        _spawn = getattr(_game_map, "entry_spawn", None)
        if _spawn is None:
            _spawn = _first_walkable(_game_map)
        _cached_positions = getattr(_game_map, "activation_positions", {})
        if _cached_positions:
            _state.event_positions.update({
                _event_id: [_position.x, _position.y]
                if isinstance(_position, world.Position) else [
                    int(_position[0]), int(_position[1]),
                ]
                for _event_id, _position in _cached_positions.items()
                if _event_id not in _state.event_positions
            })
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
    if _ENTRY_FLAVOR_KEY in state.activated_events:
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
    state.activated_events.add(_ENTRY_FLAVOR_KEY)


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
