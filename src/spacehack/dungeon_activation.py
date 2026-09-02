"""Activation anchors and dormant-security stocking for extensions.

Extracted from ``dungeon_extensions.py`` to keep that module within
the architecture size limit; re-exported there so callers are
unchanged. Owns: walkable-distance anchoring (where activation events
sit on a floor's route) and the pre-placed dormant security units that
those events later activate (docs/design/in_progress/
30_DESIGN_PRISON_DORMANT_SECURITY.md).
"""

from __future__ import annotations

from collections import deque

from . import world


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


_DORMANT_GREY = (110, 110, 110)


def _place_dormant_units(
    game_map: world.GameMap,
    enemy_id: str,
    cells: list[tuple[int, int]],
    squad_id: str,
) -> int:
    """Place dormant (grey, inert) security units on ``cells``.

    Deterministic by construction: cells arrive ring-ordered from
    ``_activation_cells`` and are consumed in order — no RNG draws, so
    seeded generation sequences are untouched.
    """
    from .data.npc_chars import find_npc_char

    try:
        spec = find_npc_char(enemy_id)
    except KeyError:
        return 0
    placed = 0
    for x, y in cells:
        game_map.entities.append(world.Entity(
            char=spec.char,
            fg=_DORMANT_GREY,
            pos=world.Position(x, y),
            name="",
            width=1,
            height=1,
            npc_char_id=enemy_id,
            squad_id=squad_id,
            powered_down=True,
        ))
        placed += 1
    return placed


def _stock_dormant_security(game_map, spec, spawn) -> None:
    """Pre-place every floor's security as dormant units (doc 30).

    Each activation event's ``count`` units stand near its route
    anchor (they activate when the event fires, instead of the event
    spawning fresh bodies), plus ``lockdown_extras`` reserve units near
    the floor entry for the post-download gauntlet.
    """
    occupied = {(e.pos.x, e.pos.y) for e in game_map.entities}
    for event in spec.activation_events:
        anchor = (game_map.activation_positions or {}).get(event.id)
        if anchor is None:
            continue
        cells = _activation_cells(
            game_map, anchor, occupied, max(0, min(event.count, event.max_count)),
        )
        occupied.update(cells)
        _place_dormant_units(
            game_map, event.enemy_id, cells, f"{event.id}_security",
        )
    if spec.lockdown_extras <= 0:
        return
    enemy_ids = [e.enemy_id for e in spec.activation_events] or ["sentry_drone"]
    per = [enemy_ids[i % len(enemy_ids)] for i in range(spec.lockdown_extras)]
    for i, enemy_id in enumerate(per):
        cells = _activation_cells(game_map, spawn, occupied, 1)
        occupied.update(cells)
        _place_dormant_units(
            game_map, enemy_id, cells, f"lockdown_extras_{spec.floor}_{i}",
        )


def _activation_cells(
    game_map: world.GameMap,
    position: world.Position,
    occupied: set[tuple[int, int]],
    needed_count: int,
) -> list[tuple[int, int]]:
    """Find the nearest free floor cells around an activation."""
    _max_radius = max(game_map.width, game_map.height)
    _found: list[tuple[int, int]] = []
    for _radius in range(_max_radius):
        _found.extend(
            (_x, _y)
            for _y in range(position.y - _radius, position.y + _radius + 1)
            for _x in range(position.x - _radius, position.x + _radius + 1)
            if max(abs(_x - position.x), abs(_y - position.y)) == _radius
            and game_map.in_bounds(_x, _y)
            and game_map.tiles[_y][_x].walkable
            and game_map.tiles[_y][_x].kind not in {
                "stairs_up", "stairs_down",
            }
            and (_x, _y) not in occupied
        )
        if len(_found) >= needed_count:
            return _found[:needed_count]
    return _found
