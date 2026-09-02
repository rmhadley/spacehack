"""Population helpers shared by authored and procedural dungeons."""

from __future__ import annotations

from collections import deque

from . import world
from .dungeon_params import DungeonParams


_SPAWN_CLEAR_RADIUS: int = 5
_SQUAD_SPREAD: int = 3
_MONSTER_TIERS: tuple[tuple[float, int], ...] = (
    (1.0, 16),
    (1.4, 22),
    (1.8, 28),
)


def _room_cells(
    tiles: list[list[world.Tile]],
    width: int,
    height: int,
    mx: int,
    my: int,
    occupied: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Return unoccupied walkable cells in the marker's connected room."""
    visited: set[tuple[int, int]] = {(mx, my)}
    queue: deque[tuple[int, int]] = deque([(mx, my)])
    cells: list[tuple[int, int]] = []
    while queue:
        cx, cy = queue.popleft()
        if (cx, cy) not in occupied:
            cells.append((cx, cy))
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in visited or not (0 <= nx < width and 0 <= ny < height):
                continue
            tile = tiles[ny][nx]
            if not tile.walkable or tile.kind in ("dungeon_door", "breach"):
                continue
            visited.add((nx, ny))
            queue.append((nx, ny))
    return cells


def _scatter_squad(
    entities: list[world.Entity],
    occupied: set[tuple[int, int]],
    *,
    enemy_id: str,
    cells: list[tuple[int, int]],
    count: int,
    squad_id: str,
    char: str,
    fg: tuple[int, int, int],
) -> int:
    """Place up to ``count`` distinct enemy entities and return the count."""
    from .engine import RNG

    if not cells:
        return 0
    RNG.shuffle(cells)
    placed = 0
    for cx, cy in cells:
        if placed >= count:
            break
        if (cx, cy) in occupied:
            continue
        entities.append(world.Entity(
            char=char,
            fg=fg,
            pos=world.Position(cx, cy),
            name="",
            width=1,
            height=1,
            npc_char_id=enemy_id,
            squad_id=squad_id,
        ))
        occupied.add((cx, cy))
        placed += 1
    return placed


def _floor_cells(
    game_map: world.GameMap,
    spawn_pos: world.Position,
) -> tuple[list[tuple[int, int]], set[tuple[int, int]]]:
    """Return eligible floor cells and landmark-protected coordinates."""
    protected = set(getattr(game_map, "landmark_footprint", ()))
    floor: list[tuple[int, int]] = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            tile = game_map.tiles[y][x]
            if not tile.walkable or tile.kind in {"exit", "stairs_up", "stairs_down"}:
                continue
            if (x, y) in protected:
                continue
            if max(abs(x - spawn_pos.x), abs(y - spawn_pos.y)) <= _SPAWN_CLEAR_RADIUS:
                continue
            floor.append((x, y))
    return floor, protected


def _population_target(floor_count: int, density: float, tier: int) -> int:
    """Calculate the tier-scaled monster target with its hard cap."""
    safe_tier = min(max(tier, 1), len(_MONSTER_TIERS))
    multiplier, cap = _MONSTER_TIERS[safe_tier - 1]
    return min(int(floor_count * density * multiplier / 100.0), cap)


def _squad_cells(
    game_map: world.GameMap,
    anchor: tuple[int, int],
    spawn_pos: world.Position,
    occupied: set[tuple[int, int]],
    protected: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Return eligible cells in a small neighborhood around an anchor."""
    ax, ay = anchor
    cells = [anchor]
    for dy in range(-_SQUAD_SPREAD, _SQUAD_SPREAD + 1):
        for dx in range(-_SQUAD_SPREAD, _SQUAD_SPREAD + 1):
            if max(abs(dx), abs(dy)) > _SQUAD_SPREAD or (dx, dy) == (0, 0):
                continue
            nx, ny = ax + dx, ay + dy
            if not (0 <= nx < game_map.width and 0 <= ny < game_map.height):
                continue
            if max(abs(nx - spawn_pos.x), abs(ny - spawn_pos.y)) <= _SPAWN_CLEAR_RADIUS:
                continue
            tile = game_map.tiles[ny][nx]
            if tile.walkable and tile.kind not in {"exit", "stairs_up", "stairs_down"}:
                if (nx, ny) not in occupied and (nx, ny) not in protected:
                    cells.append((nx, ny))
    return cells


def _place_population_anchor(
    game_map: world.GameMap,
    params: DungeonParams,
    spawn_pos: world.Position,
    anchor: tuple[int, int],
    occupied: set[tuple[int, int]],
    protected: set[tuple[int, int]],
    target: int,
    placed: int,
    squad_counter: int,
) -> tuple[int, int]:
    """Try to place one configured monster squad at an anchor."""
    from .data.npc_chars import find_npc_char
    from .engine import RNG

    if placed >= target or anchor in occupied:
        return placed, squad_counter
    enemy_id = RNG.choice(params.monster_pool)
    try:
        spec = find_npc_char(enemy_id)
    except KeyError:
        return placed, squad_counter
    budget = target - placed
    squad_min, squad_max = spec.squad_size
    if budget < squad_min:
        return placed, squad_counter
    squad_size = min(RNG.randint(squad_min, squad_max), budget)
    cells = _squad_cells(game_map, anchor, spawn_pos, occupied, protected)
    squad_id = f"dungeon_{enemy_id}_{squad_counter}"
    placed += _scatter_squad(
        game_map.entities,
        occupied,
        enemy_id=enemy_id,
        cells=cells,
        count=squad_size,
        squad_id=squad_id,
        char=spec.char,
        fg=spec.fg,
    )
    return placed, squad_counter + 1


def populate_dungeon(
    game_map: world.GameMap,
    params: DungeonParams,
    spawn_pos: world.Position,
    *,
    tier: int = 1,
) -> None:
    """Scatter facility panels and persistent monster squads into a
    freshly generated dungeon."""
    if params.panel_tile is not None and params.panel_density > 0:
        _scatter_panels(game_map, params, spawn_pos)
    if not params.monster_pool or params.monster_density <= 0:
        return
    from .engine import RNG

    floor, protected = _floor_cells(game_map, spawn_pos)
    if not floor:
        return
    target = _population_target(len(floor), params.monster_density, tier)
    if target <= 0:
        return
    occupied = {(entity.pos.x, entity.pos.y) for entity in game_map.entities}
    RNG.shuffle(floor)
    placed = 0
    squad_counter = 0
    for anchor in floor:
        placed, squad_counter = _place_population_anchor(
            game_map, params, spawn_pos, anchor, occupied, protected,
            target, placed, squad_counter,
        )
        if placed >= target:
            break


def _scatter_panels(
    game_map: world.GameMap,
    params,
    spawn_pos: world.Position,
) -> int:
    """Scatter ``params.panel_tile`` across eligible floor cells.

    Density is a fraction of eligible cells (the same cell eligibility
    as monster placement), so a 0.02 density reads as sparse fixtures.
    Draws from an ISOLATED stream keyed by the map's cache key: panel
    placement must never perturb the shared :data:`RNG
    <spacehack.engine.RNG>` ordering that later floors (and seeded
    tests) depend on. Returns the number of panels placed.
    """
    from .engine import seeded_rng

    floor, _protected = _floor_cells(game_map, spawn_pos)
    if not floor:
        return 0
    target = max(1, int(len(floor) * params.panel_density))
    rng = seeded_rng(7, getattr(game_map, "interior_cache_key", "") or "panels")
    rng.shuffle(floor)
    placed = 0
    for x, y in floor:
        if placed >= target:
            break
        if game_map.tiles[y][x].kind == "dungeon_floor":
            game_map.tiles[y][x] = params.panel_tile
            placed += 1
    return placed
