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


_EXTENSION_KEY_PREFIX = "extension:"


def floor_key(extension_id: str, floor: int) -> str:
    """Return the stable interior-cache key for one extension floor."""
    return f"{_EXTENSION_KEY_PREFIX}{extension_id}:floor:{floor}"


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


def _open_neighbours(game_map, x: int, y: int) -> int:
    """Count walkable 8-neighbours — room cells read 5+, corridors ≤2."""
    return sum(
        1
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
        if (dx or dy)
        and game_map.in_bounds(x + dx, y + dy)
        and game_map.tiles[y + dy][x + dx].walkable
    )


def _hugs_wall(game_map, x: int, y: int) -> bool:
    """Whether an orthogonal neighbour is a wall (a room-edge cell)."""
    return any(
        game_map.in_bounds(x + dx, y + dy)
        and not game_map.tiles[y + dy][x + dx].walkable
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
    )


def _reachable_count(
    game_map: world.GameMap, start, blocked: set[tuple[int, int]],
) -> int:
    """Four-way BFS cell count from ``start`` treating ``blocked`` as
    walls (start excluded from the count)."""
    from collections import deque

    sx, sy = (start.x, start.y) if isinstance(start, world.Position) else start
    seen = {(sx, sy)}
    queue = deque([(sx, sy)])
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nxt = (x + dx, y + dy)
            if (
                nxt in seen
                or nxt in blocked
                or not game_map.in_bounds(*nxt)
                or not game_map.tiles[nxt[1]][nxt[0]].walkable
            ):
                continue
            seen.add(nxt)
            queue.append(nxt)
    return len(seen) - 1


def _cell_strands_nothing(
    game_map: world.GameMap, spawn, blockers: set[tuple[int, int]], cell,
) -> bool:
    """Whether walling ``cell`` strands nothing beyond itself.

    A dormant body may block a cell but never a route: adding it to the
    blocker set must shrink spawn-reachable space by at most the cell
    itself (playtest finding #3 — units in doorways sealed rooms).
    """
    before = _reachable_count(game_map, spawn, blockers)
    after = _reachable_count(game_map, spawn, blockers | {cell})
    return after >= before - 1


def _plugs_passage(
    game_map: world.GameMap, blockers: set[tuple[int, int]], cell,
) -> bool:
    """Whether a body on ``cell`` would fully plug a passage.

    True when ANY two of the cell's open neighbours — the EIGHT-way
    adjacency the player actually moves with — can only reach each
    other THROUGH this cell. Movement is 8-directional with no
    corner-cut rule, so orthogonal-only analysis missed the diagonal
    stair pockets (playtest v4: `#<D# / ##@#` and the F4 landing).
    Dormant units must never seal a passage, even with a detour.
    """
    cx, cy = cell
    open_sides = [
        (cx + dx, cy + dy)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        if (dx or dy)
        and game_map.in_bounds(cx + dx, cy + dy)
        and game_map.tiles[cy + dy][cx + dx].walkable
        and (cx + dx, cy + dy) not in blockers
    ]
    for i, a in enumerate(open_sides):
        for b in open_sides[i + 1:]:
            if not _connected_avoiding(game_map, blockers | {cell}, a, b):
                return True
    return False


def _connected_avoiding(
    game_map: world.GameMap, blocked: set[tuple[int, int]], start, goal,
) -> bool:
    """Eight-way BFS (real movement adjacency): is ``goal`` reachable
    from ``start`` avoiding ``blocked``?"""
    from collections import deque

    if start == goal:
        return True
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not (dx or dy):
                    continue
                nxt = (x + dx, y + dy)
                if nxt == goal:
                    return True
                if (
                    nxt not in seen
                    and nxt not in blocked
                    and game_map.in_bounds(*nxt)
                    and game_map.tiles[nxt[1]][nxt[0]].walkable
                ):
                    seen.add(nxt)
                    queue.append(nxt)
    return False


def _dormant_cell_ok(
    game_map, x: int, y: int, occupied, landmark_cells, spawn, blockers,
) -> bool:
    """Whether a dormant unit may stand on ``(x, y)``.

    Free, walkable, not a stair or landmark cell, open surroundings
    (≥3 — never a 1-wide corridor), and — when ``spawn`` is given —
    walling it strands nothing (existing dormant bodies as walls).
    """
    if (
        not game_map.in_bounds(x, y)
        or not game_map.tiles[y][x].walkable
        or game_map.tiles[y][x].kind in {"stairs_up", "stairs_down"}
        or (x, y) in occupied
        or (x, y) in landmark_cells
        or _open_neighbours(game_map, x, y) < 3
    ):
        return False
    if _plugs_passage(game_map, blockers, (x, y)):
        return False  # never seal a 1-wide passage, bend, or room mouth
    if spawn is None:
        return True
    return _cell_strands_nothing(game_map, spawn, blockers, (x, y))


def _dormant_cells(
    game_map: world.GameMap,
    anchor,
    occupied: set[tuple[int, int]],
    needed: int,
    *,
    spawn=None,
    safe_blockers: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int]]:
    """Nearest safe cells around ``anchor`` for dormant units.

    Preference order (deterministic ring scan, no RNG): room-edge
    cells first, then open cells (both ≥3 open neighbours — never a
    1-wide corridor, never a landmark footprint cell); every candidate
    also passes the strands-nothing reachability check when ``spawn``
    is given. See `_ring_scan_preferred`.
    """
    landmark_cells = set(getattr(game_map, "landmark_footprint", ()) or ())
    blockers = set(safe_blockers or set())

    def _cell_ok(x: int, y: int) -> bool:
        return _dormant_cell_ok(
            game_map, x, y, occupied, landmark_cells, spawn, blockers,
        )

    def _prefer_strict(cell: tuple[int, int]) -> bool:
        return _hugs_wall(game_map, cell[0], cell[1])

    return _ring_scan_preferred(
        game_map, anchor, needed, _cell_ok, _prefer_strict,
    )



def _ring_scan_preferred(
    game_map: world.GameMap,
    anchor,
    needed: int,
    cell_ok,
    prefer_strict,
) -> list[tuple[int, int]]:
    """Ring-scan outward from ``anchor``; strict-preferred, then rest.

    Deterministic ring order (no RNG); stops once ``needed`` strict
    cells are found or the scan saturates, returning up to ``needed``
    cells (strict first).
    """
    fallback: list[tuple[int, int]] = []
    strict: list[tuple[int, int]] = []
    ax, ay = (anchor.x, anchor.y) if isinstance(anchor, world.Position) else anchor
    for _radius in range(max(game_map.width, game_map.height)):
        for _y in range(ay - _radius, ay + _radius + 1):
            for _x in range(ax - _radius, ax + _radius + 1):
                if max(abs(_x - ax), abs(_y - ay)) != _radius or not cell_ok(_x, _y):
                    continue
                if prefer_strict((_x, _y)):
                    strict.append((_x, _y))
                    if len(strict) == needed:
                        return strict
                else:
                    fallback.append((_x, _y))
        if len(strict) + len(fallback) >= needed and _radius >= 2:
            break
    return (strict + fallback)[:needed]

def _spread_extra_anchors(game_map, spawn, count: int) -> list:
    """Anchor cells for lockdown extras: two hold the entry, the rest
    spread at even fractions along the route.

    All-at-the-entry stuffed over half the garrison into one room
    (playtest v3); a spread keeps every floor's ascent contested while
    the door itself stays defended. Deterministic, no RNG.
    """
    if count <= 0:
        return []
    if count <= 2:
        return [spawn] * count
    distances = _walkable_distances(game_map, spawn)
    cells = sorted(distances, key=lambda c: (distances[c], c[1], c[0]))
    anchors = [spawn, spawn]
    spread = count - 2
    for i in range(spread):
        fraction = 0.15 + (0.70 * i / max(1, spread - 1)) if spread > 1 else 0.5
        index = min(len(cells) - 1, max(0, int((len(cells) - 1) * fraction)))
        anchors.append(world.Position(cells[index][0], cells[index][1]))
    return anchors


def _stock_dormant_security(game_map, spec, spawn) -> None:
    """Pre-place every floor's security as dormant units (doc 30).

    Each activation event's ``count`` units stand at room edges near
    its route anchor (they activate when the event fires, instead of
    the event spawning fresh bodies), plus ``lockdown_extras`` reserve
    units around the entry room for the post-download gauntlet. Room-
    edge placement keeps every route walkable — dormant bodies block
    movement but never block a path.
    """
    occupied = {(e.pos.x, e.pos.y) for e in game_map.entities}
    dormant_placed: set[tuple[int, int]] = set()
    for event in spec.activation_events:
        anchor = (game_map.activation_positions or {}).get(event.id)
        if anchor is None:
            continue
        cells = _dormant_cells(
            game_map, anchor, occupied,
            max(0, min(event.count, event.max_count)),
            spawn=spawn, safe_blockers=dormant_placed,
        )
        occupied.update(cells)
        dormant_placed.update(cells)
        _place_dormant_units(
            game_map, event.enemy_id, cells, f"{event.id}_security",
        )
    if spec.lockdown_extras <= 0:
        return
    _stock_lockdown_extras(game_map, spec, spawn, occupied, dormant_placed)


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


# ----- Facility phase: one truth for panels AND dormant security -----
# (docs/design/in_progress/29_DESIGN_PRISON_LIGHTING.md phase 3 and
# 30_DESIGN_PRISON_DORMANT_SECURITY.md phase 3)

_WAKING_EVENT = "prison_floor1_security_alpha"
_RISING_EVENT = "prison_floor1_security_beta"
_EXTRACTED_FLAG = "prison_data_extracted"

# Panel kind per (phase, floor); missing floors take the phase default.
# "rising" deep floors default to normal — power approaches mains as
# the player nears the core.
_PANEL_STATES: dict[str, dict[int, world.Tile]] = {
    "dormant": {},
    "waking": {1: world.PRISON_PANEL_DIM},
    "rising": {
        1: world.PRISON_PANEL_MID,
        2: world.PRISON_PANEL_MID,
        3: world.PRISON_PANEL_MID,
    },
    "lockdown": {},
}
_PANEL_DEFAULTS: dict[str, world.Tile] = {
    "dormant": world.PRISON_PANEL_OFF,
    "waking": world.PRISON_PANEL_OFF,
    "rising": world.PRISON_PANEL_NORMAL,
    "lockdown": world.PRISON_PANEL_ALARM,
}
_PHASE_ORDER = ("dormant", "waking", "rising", "lockdown")


def _stock_lockdown_extras(game_map, spec, spawn, occupied, dormant_placed) -> None:
    """Spread the floor's reserve garrison: two hold the entry door,
    the rest stand at even fractions along the route."""
    enemy_ids = [e.enemy_id for e in spec.activation_events] or ["sentry_drone"]
    per = [enemy_ids[i % len(enemy_ids)] for i in range(spec.lockdown_extras)]
    anchors = _spread_extra_anchors(game_map, spawn, len(per))
    for i, (enemy_id, anchor_pos) in enumerate(zip(per, anchors)):
        cells = _dormant_cells(
            game_map, anchor_pos, occupied, 1,
            spawn=spawn, safe_blockers=dormant_placed,
        )
        occupied.update(cells)
        dormant_placed.update(cells)
        _place_dormant_units(
            game_map, enemy_id, cells, f"lockdown_extras_{spec.floor}_{i}",
        )


def _facility_phase(state) -> str:
    """Pure: derive the facility phase from persisted extension state.

    ``lockdown`` (data extracted) beats everything; otherwise the F1
    power events ratchet dormant → waking → rising. Derived, never
    stored — save/load needs no new state.
    """
    if _EXTRACTED_FLAG in (getattr(state, "state_flags", None) or set()):
        return "lockdown"
    events = getattr(state, "activated_events", None) or set()
    if _RISING_EVENT in events:
        return "rising"
    if _WAKING_EVENT in events:
        return "waking"
    return "dormant"


def _effective_phase(phase: str, floor: int) -> str:
    """Apply the skip rule: entering floor ≥2 counts as at least rising.

    Skipping an F1 power event never stalls the wake-up below (user
    ruling 2026-09-02).
    """
    if floor >= 2 and _PHASE_ORDER.index(phase) < _PHASE_ORDER.index("rising"):
        return "rising"
    return phase


def _panel_kind(phase: str, floor: int) -> world.Tile:
    """The panel tile kind a floor shows in ``phase``."""
    return _PANEL_STATES.get(phase, {}).get(
        floor, _PANEL_DEFAULTS.get(phase, world.PRISON_PANEL_OFF),
    )


def refresh_prison_panels(game_map: world.GameMap, phase: str, floor: int) -> bool:
    """Rewrite every panel tile to its ``phase`` kind; invalidate light.

    Idempotent. Light caches are dropped rather than recomputed: the
    per-step FOV reveal reseeds both from the new tile kinds, and the
    per-frame recompute skips until then. Returns whether any panel
    changed.
    """
    target = _panel_kind(phase, floor)
    changed = False
    for row in game_map.tiles:
        for x, tile in enumerate(row):
            if tile.kind.startswith("prison_panel_") and tile.kind != target.kind:
                row[x] = target
                changed = True
    if changed:
        game_map.light_sources = None
        game_map.light_grid = None
    return changed


def activate_dormant(
    game_map: world.GameMap, *, squad_prefix: str = "",
) -> int:
    """Wake dormant security: recolored, hostile, fighting.

    Flips ``powered_down`` and restores the unit spec's glyph/colour.
    ``squad_prefix`` wakes only that event's squads (ascent events
    whose squads already woke under lockdown simply report zero).
    Returns the number activated (for the spawn/no-deploy log lines).
    """
    from .data.npc_chars import find_npc_char

    count = 0
    for entity in game_map.entities:
        if not getattr(entity, "powered_down", False):
            continue
        if squad_prefix and not entity.squad_id.startswith(squad_prefix):
            continue
        entity.powered_down = False
        try:
            spec = find_npc_char(entity.npc_char_id)
        except KeyError:
            continue
        entity.char = spec.char
        entity.fg = spec.fg
        count += 1
    return count


def apply_lockdown_all_floors(ctx) -> int:
    """The data-extract moment: every floor alarms and everything wakes.

    Applies to the current map and every cached floor of the active
    extension; floors generated later pick the state up at generation
    (phase-gated). Returns the total units awakened.
    """
    state = getattr(ctx, "dungeon_extension", None)
    prefix = f"{floor_key(state.extension_id, '') if state else ''}"
    maps = [ctx.game_map]
    for key, cached in (getattr(ctx, "interiors", None) or {}).items():
        if state and key.startswith(prefix) and cached not in maps:
            maps.append(cached)
    awakened = 0
    for game_map in maps:
        awakened += activate_dormant(game_map)
        refresh_prison_panels(game_map, "lockdown", 0)
    return awakened
