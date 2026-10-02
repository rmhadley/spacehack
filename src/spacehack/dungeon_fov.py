"""Fog-of-war and line-of-sight behavior for dungeon maps."""

from __future__ import annotations

from collections import deque

from . import world


DUNGEON_SIGHT_RADIUS: int = 8
# The powered state's sensor range: derelicts earn it at the power
# console; a live capture interior starts here (the power is on).
POWERED_SIGHT_RADIUS: int = 20


def init_fog(game_map: world.GameMap) -> None:
    """Initialize fog-of-war on a map before player control."""
    game_map.seen = [
        [False for _ in range(game_map.width)]
        for _ in range(game_map.height)
    ]
    game_map.visible = [
        [False for _ in range(game_map.width)]
        for _ in range(game_map.height)
    ]
    game_map.sight_radius = DUNGEON_SIGHT_RADIUS


def cell_in_sight(game_map: world.GameMap, x: int, y: int,
                  from_x: int | None = None, from_y: int | None = None) -> bool:
    """The ONE ground combat sight predicate (2026-10-02 ruling —
    the 09-02 "aggro is exactly what the player sees" finding
    completed): a cell is in sight when the fog grid says so; maps
    without a grid fall back to the direct sight ray from
    (from_x, from_y). Ground fire, the ground AI (mutual sight — a
    cell the player sees is a cell that can see them), and aggro all
    read THIS, so what engages is always shootable and never the
    reverse. Callers MUST pass from-coords: a missing from on a
    grid-less map reads True (there is no honest default)."""
    _visible = getattr(game_map, "visible", None)
    if _visible is not None:
        return _visible[y][x]
    if from_x is None or from_y is None:
        return True
    return has_sight_ray(game_map, from_x, from_y, x, y)


def _ray_cells(ox: int, oy: int, dx: int, dy: int):
    """The rounded-ray sample cells from (ox, oy) toward (dx, dy)
    (excluding the origin) — the ONE trace geometry :func:`_cast_ray`
    reveals along and :func:`has_sight_ray` tests; the pair must never
    drift apart."""
    _steps = max(abs(dx), abs(dy))
    if _steps == 0:
        return
    for _step in range(1, _steps + 1):
        _f = _step / _steps
        yield round(ox + dx * _f), round(oy + dy * _f)


def has_sight_ray(game_map: world.GameMap, from_x: int, from_y: int,
                  to_x: int, to_y: int) -> bool:
    """The player-sight geometry as a queryable predicate: the SAME
    rounded-ray trace :func:`_cast_ray` walks. The grid-less FALLBACK
    for ground sight reads (2026-10-02 unification: aggro and fire
    share the fog grid, which is the primary predicate — see
    :func:`cell_in_sight`; on maps without a grid this trace stands
    in, where Bresenham disagreed with the FOV at corners).
    Direction-symmetric where Bresenham was not. Notably NOT the
    transit rule: a cell the FOV marks visible via a ray aimed past
    it may still fail this DIRECT trace — grid-bearing callers must
    read the grid, not this."""
    for _sx, _sy in _ray_cells(from_x, from_y, to_x - from_x, to_y - from_y):
        if (_sx, _sy) == (to_x, to_y):
            return True
        if not game_map.in_bounds(_sx, _sy):
            return False
        _tile = game_map.tiles[_sy][_sx]
        if not _tile.walkable and _tile.kind != "hull_wall":
            return False
        if _tile.kind == "dungeon_door":
            return False
    return True


def _cast_ray(game_map: world.GameMap, ox: int, oy: int, dx: int, dy: int) -> None:
    """Reveal one ray, stopping at solid walls and closed doors."""
    for sx, sy in _ray_cells(ox, oy, dx, dy):
        if not game_map.in_bounds(sx, sy):
            return
        game_map.seen[sy][sx] = True
        if game_map.visible is not None:
            game_map.visible[sy][sx] = True
        tile = game_map.tiles[sy][sx]
        if not tile.walkable and tile.kind != "hull_wall":
            return
        if tile.kind == "dungeon_door":
            return


def _hull_wall_cells(game_map: world.GameMap) -> list[tuple[int, int]]:
    """The map's hull-wall cells, derived once and cached on the map
    (replace_tile invalidates) — the per-reveal kind scan was O(map)."""
    if game_map.hull_wall_cells is None:
        game_map.hull_wall_cells = [
            (x, y)
            for y in range(game_map.height)
            for x in range(game_map.width)
            if game_map.tiles[y][x].kind == "hull_wall"
        ]
    return game_map.hull_wall_cells


def _propagate_flags(game_map: world.GameMap, flags: list[list[bool]]) -> None:
    """Propagate a visibility flag through connected hull-wall groups."""
    width, height = game_map.width, game_map.height
    seeds = [
        (x, y)
        for x, y in _hull_wall_cells(game_map)
        if flags[y][x]
    ]
    visited: set[tuple[int, int]] = set()
    for seed in seeds:
        if seed in visited:
            continue
        group: list[tuple[int, int]] = []
        queue = deque([seed])
        visited.add(seed)
        while queue:
            current = queue.popleft()
            group.append(current)
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                neighbor = (current[0] + dx, current[1] + dy)
                if not (0 <= neighbor[0] < width and 0 <= neighbor[1] < height):
                    continue
                if neighbor in visited:
                    continue
                if game_map.tiles[neighbor[1]][neighbor[0]].kind != "hull_wall":
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        if any(flags[y][x] for x, y in group):
            for x, y in group:
                flags[y][x] = True


def _propagate_hull_groups(game_map: world.GameMap) -> None:
    """Apply hull-group visibility to remembered and current-LOS grids."""
    if game_map.seen is None:
        return
    _propagate_flags(game_map, game_map.seen)
    if game_map.visible is not None:
        _propagate_flags(game_map, game_map.visible)


def _clear_visible(game_map: world.GameMap) -> None:
    """Reset or create the current line-of-sight grid."""
    if game_map.visible is None:
        game_map.visible = [
            [False for _ in range(game_map.width)]
            for _ in range(game_map.height)
        ]
        return
    for row in game_map.visible:
        for index in range(len(row)):
            row[index] = False


def _cast_visible_rays(
    game_map: world.GameMap,
    pos: world.Position,
    radius: int,
) -> None:
    """Cast all rays within the requested Chebyshev radius."""
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if max(abs(dx), abs(dy)) <= radius and (dx or dy):
                _cast_ray(game_map, pos.x, pos.y, dx, dy)


def _static_light_sources(game_map: world.GameMap) -> list:
    """The map's static light sources, derived once and cached on the
    map (replace_tile invalidates) — the per-reveal tile scan was
    O(map) on big interiors."""
    if game_map.light_sources is None:
        from .lighting import collect_light_sources

        game_map.light_sources = collect_light_sources(game_map)
    return game_map.light_sources


def _lit_cells_in_visible(game_map: world.GameMap) -> list[tuple[int, int]]:
    """Return currently-visible cells whose tile kind emits light.

    Intersects the cached source list with ``visible`` — same cells
    the old full-map scan found, at O(sources).
    """
    if game_map.visible is None:
        return []
    return [
        (source.x, source.y)
        for source in _static_light_sources(game_map)
        if game_map.visible[source.y][source.x]
    ]


def _reveal_lit_sources(game_map: world.GameMap) -> None:
    """Extend sight near currently-visible light sources.

    For each lit cell in the current LOS, cast short rays (the source's
    light radius) so a glow-fungus patch reveals a bubble of cells
    beyond the player's base sight radius. This is the gameplay hook:
    light extends the player's sight near lit features.

    Opaque emitters (e.g. the undulating alien door) only glow — they
    never extend sight through themselves, or a sealed chamber beyond
    the emitter would be revealed by its own glow.

    2026-10-02: glow-revealed cells are FIREABLE — aggro and fire both
    read the visible grid now, so a hostile the fungus lights around a
    corner is engaged AND shootable (the shot's beam is the one
    cosmetic casualty: it may graze the corner wall). The alternative
    (bubbling glow cells down to seen-only) was built and reverted: it
    broke the 09-02 ruling's own batch ("aggro is EXACTLY what the
    player sees" — glow included) and the ruled balance rows."""
    from .data.lighting import light_spec_for_kind

    for sx, sy in _lit_cells_in_visible(game_map):
        tile = game_map.tiles[sy][sx]
        spec = light_spec_for_kind(tile.kind)
        if spec is None:
            continue
        if not tile.walkable and tile.kind != "hull_wall":
            continue
        for dy in range(-spec.radius, spec.radius + 1):
            for dx in range(-spec.radius, spec.radius + 1):
                if max(abs(dx), abs(dy)) > spec.radius or (dx == 0 and dy == 0):
                    continue
                _cast_ray(game_map, sx, sy, dx, dy)


def reveal_around(
    game_map: world.GameMap,
    pos: world.Position,
    radius: int = DUNGEON_SIGHT_RADIUS,
) -> None:
    """Recompute current LOS and grow permanent visibility around ``pos``.

    After the normal FOV cast, light sources within the player's sight
    extend visibility into nearby dark cells (e.g. glow fungus
    illuminating a corridor beyond the base radius). The light grid is
    also recomputed so lit cells tint their neighbours.
    """
    if game_map.seen is None:
        return
    _clear_visible(game_map)
    if game_map.in_bounds(pos.x, pos.y):
        game_map.seen[pos.y][pos.x] = True
        game_map.visible[pos.y][pos.x] = True
    _cast_visible_rays(game_map, pos, radius)
    _reveal_lit_sources(game_map)
    _propagate_hull_groups(game_map)
    _seed_dungeon_light_grid(game_map)


def _seed_dungeon_light_grid(game_map: world.GameMap) -> None:
    """Recompute the light grid, masked to currently-visible cells.

    Dungeon light is fog-gated: only cells in the current LOS are
    tinted, so light never reveals cells through the fog. Sources
    outside the visible area don't contribute (their light is zeroed).
    Sources are cached on ``light_sources`` so the render loop's
    per-frame recompute can animate flickering dungeon sources (e.g.
    the pulsing alien door) without rescanning tiles.
    """
    from .lighting import mask_grid_to_visible, propagate_light

    sources = _static_light_sources(game_map)
    if not sources:
        game_map.light_grid = None
        return
    grid = propagate_light(
        game_map.width, game_map.height, sources,
        occluder=lambda x, y: not game_map.tiles[y][x].walkable,
    )
    mask_grid_to_visible(game_map, grid)
    game_map.light_grid = grid
