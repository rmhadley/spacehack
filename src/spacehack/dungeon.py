"""Ship interior layout parser and procedural dungeon generator.

Reads ``.layout`` files from ``data/layouts/`` and builds a
:class:`world.GameMap` with tiles, entities, and the player
spawn position.

Layout format (DCSS-inspired):
  - ``#`` comments
  - ``MAP`` / ``ENDMAP`` delimit the ASCII grid
  - ``TILE: X = type`` maps a glyph to a tile or entity kind
  - ``COLOUR: X = (R, G, B)`` overrides the tile's fg color

The parser finds the hull boundary per row (first/last non-space
character). Everything between boundaries is interior; everything
before/after is void.

For planet surface dungeons, :func:`generate_dungeon` uses BSP
room-and-corridor generation instead of hand-authored layouts.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass

from . import world


# ---------------------------------------------------------------------------
# Dungeon generation parameters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DungeonParams:
    """Configuration for procedural dungeon generation.

    Attributes:
        width / height:            Map dimensions in cells.
        min_room_size / max_room_size:  Room interior dimension range.
        room_fill_pct:             Fraction of the leaf region (0-1)
                                   that the room fills.  Lower = smaller
                                   rooms in larger wall-gaps → sparse
                                   layout with long corridors.
        tile_wall:                 Tile used for walls (default
                                   :data:`world.DUNGEON_WALL`).
        tile_floor:                Tile used for floors + corridors
                                   (default :data:`world.DUNGEON_FLOOR`).
        sight_radius:              Fog-of-war reveal radius.
    """
    width: int = 50
    height: int = 40
    min_room_size: int = 5
    max_room_size: int = 12
    room_fill_pct: float = 0.65
    tile_wall: world.Tile = world.DUNGEON_WALL
    tile_floor: world.Tile = world.DUNGEON_FLOOR
    sight_radius: int = 4


# Sight radius for dungeon fog of war (Chebyshev distance).
DUNGEON_SIGHT_RADIUS: int = 4

# Maximum passes through loot markers when spending a ship's budget.
# Multiple passes let some rooms end up with more than one loot
# container (e.g. engine room has both fuel cells AND machine parts).
_LOOT_MAX_PASSES: int = 4


def init_fog(game_map: world.GameMap) -> None:
    """Initialize fog-of-war ``seen`` array on ``game_map`` (all unseen).

    Call after loading a layout and before the player takes control.
    All cells start unrevealed.
    """
    game_map.seen = [
        [False for _ in range(game_map.width)]
        for _ in range(game_map.height)
    ]
    game_map.sight_radius = DUNGEON_SIGHT_RADIUS


def _cast_ray(game_map: world.GameMap, ox: int, oy: int, dx: int, dy: int) -> None:
    """Cast a single ray from ``(ox, oy)`` by ``(dx, dy)`` steps.

    Reveals each cell along the ray. Stops when hitting a wall
    (non-walkable tile) — the wall itself is revealed but nothing
    beyond it. ``hull_wall`` tiles are transparent to FOV (they
    block movement but not sight), so rays pass through structural
    hull groups like ``{#}`` and ``{##}``.
    """
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        return
    # Skip step 0 (origin cell) so standing ON a door doesn't block
    # your own vision — only doors you look THROUGH block.
    for step in range(1, steps + 1):
        t = step / steps
        sx = round(ox + dx * t)
        sy = round(oy + dy * t)
        if not game_map.in_bounds(sx, sy):
            return
        game_map.seen[sy][sx] = True
        # Stop at solid walls and closed doors, but NOT hull_wall
        # (structural hull groups are transparent to FOV)
        _tile = game_map.tiles[sy][sx]
        if not _tile.walkable and _tile.kind != 'hull_wall':
            return
        if _tile.kind == 'dungeon_door':
            return


def _propagate_hull_groups(game_map: world.GameMap) -> None:
    """Propagate visibility through adjacent ``hull_wall`` cells.

    After FOV rays reveal individual cells, any hull_wall cell that
    was hit by a ray propagates its ``seen`` state to all connected
    hull_wall cells (4-directional). This makes structural hull
    groups like ``{##}`` always fully visible together — if any
    cell in the group is seen, all are seen.
    """
    if game_map.seen is None:
        return
    w, h = game_map.width, game_map.height
    # Find all hull_wall cells that are already seen (seed cells)
    _seeds: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if game_map.tiles[y][x].kind == 'hull_wall' and game_map.seen[y][x]:
                _seeds.append((x, y))
    if not _seeds:
        return
    # BFS from each seed through adjacent hull_wall cells
    from collections import deque
    _visited: set[tuple[int, int]] = set()
    _queue: deque[tuple[int, int]] = deque()
    for sx, sy in _seeds:
        if (sx, sy) not in _visited:
            # Collect one connected group
            _group: list[tuple[int, int]] = []
            _queue.append((sx, sy))
            _visited.add((sx, sy))
            while _queue:
                cx, cy = _queue.popleft()
                _group.append((cx, cy))
                for ndx, ndy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                    nx, ny = cx + ndx, cy + ndy
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in _visited:
                        if game_map.tiles[ny][nx].kind == 'hull_wall':
                            _visited.add((nx, ny))
                            _queue.append((nx, ny))
            # If any cell in this group is seen, all are seen
            if any(game_map.seen[gy][gx] for gx, gy in _group):
                for gx, gy in _group:
                    game_map.seen[gy][gx] = True


def reveal_around(game_map: world.GameMap, pos: world.Position, radius: int = DUNGEON_SIGHT_RADIUS) -> None:
    """Reveal cells in line-of-sight from ``pos`` within ``radius``.

    Casts rays to every cell within Chebyshev distance ``radius``.
    Walls block vision — cells behind walls stay hidden.
    After rays, hull wall groups (``{##}``) propagate visibility:
    if any cell in a group is seen, all connected hull wall cells
    are revealed.
    No-op if the map has no fog (``seen`` is ``None``).
    """
    if game_map.seen is None:
        return
    # Always reveal the player's own cell
    if game_map.in_bounds(pos.x, pos.y):
        game_map.seen[pos.y][pos.x] = True
    # Cast rays to all cells within radius
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if max(abs(dx), abs(dy)) > radius:
                continue
            if dx == 0 and dy == 0:
                continue
            _cast_ray(game_map, pos.x, pos.y, dx, dy)
    # Propagate visibility through hull wall groups
    _propagate_hull_groups(game_map)


# Loot pools per room type — (good_id, min_qty, max_qty)
# Defined in code so we can RNG-pick from appropriate trade goods.
_LOOT_POOLS: dict[str, list[tuple[str, int, int]]] = {
    "engine_room": [
        ("machine_parts",  1, 2),
        ("fuel_cells",     1, 2),
        ("ship_components", 1, 1),
    ],
    "mess_hall": [
        ("food_rations",    1, 3),
        ("medical_supplies", 1, 2),
        ("luxury_goods",    1, 1),
    ],
    "personal_storage": [
        ("luxury_goods",   1, 1),
        ("electronics",     1, 2),
        ("research_data",   1, 1),
    ],
    "cargo_bay": [
        ("ore_processed",   2, 5),
        ("machine_parts",   1, 3),
        ("textiles",        1, 3),
    ],
}

# Map-like: glyph -> (tile, is_entity_marker)
# tile=None means the glyph places an entity, not a tile
_GLYPH_TILES: dict[str, world.Tile] = {
    "#": world.DUNGEON_WALL,
    ".": world.DUNGEON_FLOOR,
    "d": world.DUNGEON_DOOR,
    "a": world.AIRLOCK,
    "b": world.BREACH,
    "C": world.COCKPIT,
    "E": world.ENGINE_TILE,
    "%": world.DEBRIS,
    ">": world.EXIT,
    "{": world.HULL_WALL,
    "}": world.HULL_WALL,
}

# Enemy spawn glyphs — placed as NPC char entities, rendered as floor.
# Using distinct glyphs so they don't conflict with engine (E) or other markers.
_ENEMY_GLYPHS: set[str] = {"r", "R", "S"}

# Glyphs that place entities rather than tiles.
_ENTITY_GLYPHS: set[str] = {"P", "C", "E"} | _ENEMY_GLYPHS

_LAYOUT_DIR = pathlib.Path(__file__).parent / "data" / "layouts"


def _parse_colour(line: str) -> tuple[str, tuple[int, int, int]] | None:
    """Parse a ``COLOUR: X = (R, G, B)`` line.

    Trailing ``#`` comments are stripped (the ``(R, G, B)`` tuple is
    decimal, so ``#`` can never appear inside it).

    Returns ``(glyph, (r, g, b))`` or ``None`` if the line isn't a
    colour directive.
    """
    line = line.strip()
    if not line.startswith("COLOUR:"):
        return None
    rest = line[7:].strip()
    if "#" in rest:
        rest = rest.split("#", 1)[0].strip()
    if "=" not in rest:
        return None
    glyph_part, rgb_part = rest.split("=", 1)
    glyph = glyph_part.strip()
    # Parse (R, G, B)
    rgb_str = rgb_part.strip().strip("()")
    parts = [p.strip() for p in rgb_str.split(",")]
    if len(parts) != 3:
        return None
    try:
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    return (glyph, (r, g, b))


def load_layout(
    layout_id: str,
    *,
    loot_budget: tuple[int, int] | None = None,
    component_good_id: str | None = None,
    component_mission_id: str | None = None,
) -> tuple[world.GameMap, world.Position]:
    """Parse ``layout_id.layout`` and return ``(game_map, spawn_pos)``.

    ``loot_budget`` is the ship's ``(min_credits, max_credits)`` for
    interior salvage. When provided, up to 4 passes are made through
    all loot rooms to try to spend the rolled budget — some rooms
    naturally end up with multiple loot containers while others get
    none. When ``None`` (default), old guaranteed behavior is used.

    ``component_good_id`` + ``component_mission_id`` (salvage missions):
    when both set, ONE loot-marker room is RNG-picked and the
    mission-tagged ``%`` component entity (``heist_mission`` +
    ``heist_mission_id``) is placed in it. Placement is decided at
    layout-build time, so it persists via the caller's interior cache.

    Raises:
      FileNotFoundError: if the layout file doesn't exist.
      ValueError: if the layout file is malformed.
    """
    path = _LAYOUT_DIR / f"{layout_id}.layout"
    if not path.exists():
        raise FileNotFoundError(f"Layout not found: {path}")

    raw = path.read_text(encoding="utf-8").splitlines()

    # Collect colour overrides, loot zone mappings, and enemy spawn directives
    colour_overrides: dict[str, tuple[int, int, int]] = {}
    loot_zones: dict[str, str] = {}  # glyph -> room_type
    enemy_spawn_specs: dict[str, tuple[str, float, int, int]] = {}  # glyph -> (enemy_id, spawn_chance, squad_min, squad_max)

    # --- Parse MAP section ---
    map_lines: list[str] = []
    in_map = False
    after_map = False

    for line in raw:
        stripped = line.strip()

        if stripped == "MAP":
            in_map = True
            continue
        if stripped == "ENDMAP":
            in_map = False
            after_map = True
            continue

        if in_map:
            map_lines.append(line)  # preserve leading/trailing whitespace
            continue  # skip comment/blank filter — inside MAP data

        if stripped.startswith("#") or not stripped:
            continue  # comment or blank (outside MAP)

        if after_map:
            # Parse LOOT directives
            if stripped.startswith("LOOT:"):
                rest = stripped[5:].strip()
                if "=" in rest:
                    glyph_part, room_part = rest.split("=", 1)
                    glyph = glyph_part.strip()
                    room_type = room_part.strip()
                    loot_zones[glyph] = room_type
                continue
            # Parse ENEMY directives:  ENEMY: r = pirate_raider@0.6
            # Squad notation:           ENEMY: S = pirate_raider@1.0#3-3
            if stripped.startswith("ENEMY:"):
                rest = stripped[6:].strip()
                if "=" in rest:
                    glyph_part, spec_part = rest.split("=", 1)
                    glyph = glyph_part.strip()
                    spec_str = spec_part.strip()
                    squad_min, squad_max = 1, 1
                    # Parse squad suffix: #min-max (e.g. #3-3 or #2-5)
                    if "#" in spec_str:
                        spec_str, squad_str = spec_str.rsplit("#", 1)
                        if "-" in squad_str:
                            parts = squad_str.split("-")
                            try:
                                squad_min = int(parts[0])
                                squad_max = int(parts[1])
                            except ValueError:
                                pass
                        else:
                            try:
                                squad_min = squad_max = int(squad_str)
                            except ValueError:
                                pass
                    if "@" in spec_str:
                        enemy_id, chance_str = spec_str.rsplit("@", 1)
                        try:
                            chance = float(chance_str)
                        except ValueError:
                            chance = 1.0
                    else:
                        enemy_id = spec_str
                        chance = 1.0
                    enemy_spawn_specs[glyph] = (enemy_id.strip(), chance, squad_min, squad_max)
                continue
            # Parse TILE and COLOUR directives
            if stripped.startswith("TILE:"):
                continue  # TILE directives describe the glyphs, parser uses hardcoded mapping
            colour_result = _parse_colour(line)
            if colour_result is not None:
                glyph, rgb = colour_result
                colour_overrides[glyph] = rgb

    if not map_lines:
        raise ValueError(f"Layout {layout_id!r} has no MAP section")

    # Determine grid dimensions from max line length
    grid_height = len(map_lines)
    grid_width = max(len(line) for line in map_lines)

    # Pad all lines to the same width
    map_lines = [line.ljust(grid_width) for line in map_lines]

    # Build tiles and collect entity placements + loot marker positions + enemy markers
    tiles: list[list[world.Tile]] = []
    entities: list[world.Entity] = []
    spawn_pos: world.Position | None = None
    loot_markers: list[tuple[str, int, int]] = []  # (room_type, x, y)
    enemy_markers: list[tuple[str, int, int]] = []  # (glyph, x, y) — deferred scatter after tile build

    for row_idx, line in enumerate(map_lines):
        tile_row: list[world.Tile] = []
        for col_idx, ch in enumerate(line):
            # Determine if this cell is inside the hull boundary
            # Find first/last non-space on this line
            first_nonspace = next(
                (i for i, c in enumerate(line) if c != " "),
                0,
            )
            last_nonspace = max(
                (i for i, c in enumerate(line) if c != " "),
                default=0,
            )

            if col_idx < first_nonspace or col_idx > last_nonspace:
                # Outside hull — void
                tile_row.append(world.VOID)
                continue

            if ch == " ":
                # Space inside hull = floor
                tile_row.append(world.DUNGEON_FLOOR)
                continue

            if ch in _ENTITY_GLYPHS:
                # Entity marker — place underlying floor tile + optional entity
                tile_row.append(world.DUNGEON_FLOOR)
                if ch == "P":
                    if spawn_pos is not None:
                        raise ValueError(
                            f"Multiple spawn points in {layout_id!r} "
                            f"(found at ({col_idx},{row_idx}) and "
                            f"({spawn_pos.x},{spawn_pos.y}))"
                        )
                    spawn_pos = world.Position(col_idx, row_idx)
                elif ch == "C":
                    # Cockpit computer — interactable terminal
                    entities.append(world.Entity(
                        char="C", fg=colour_overrides.get("C", (255, 200, 80)),
                        pos=world.Position(col_idx, row_idx),
                        name="Ship Computer", width=1, height=1,
                        computer_terminal=True,
                    ))
                elif ch == "E":
                    # Engine — flavor entity (placeholder)
                    entities.append(world.Entity(
                        char="E", fg=colour_overrides.get("E", (180, 200, 220)),
                        pos=world.Position(col_idx, row_idx),
                        name="Engine Terminal", width=1, height=1,
                    ))
                elif ch in enemy_spawn_specs:
                    # Enemy marker — defer spawn to scatter pass (like loot)
                    enemy_markers.append((ch, col_idx, row_idx))
                continue

            # Loot marker — treat as floor, record position for flood-fill
            if ch in loot_zones:
                tile_row.append(world.DUNGEON_FLOOR)
                loot_markers.append((loot_zones[ch], col_idx, row_idx))
                continue

            # Look up glyph in tile map
            tile = _GLYPH_TILES.get(ch)
            if tile is None:
                # Unknown glyph — treat as void (safety)
                tile = world.VOID
            tile_row.append(tile)

        tiles.append(tile_row)

    if spawn_pos is None:
        raise ValueError(f"Layout {layout_id!r} has no player spawn marker (P)")

    # --- Convert {…} hull wall groups: replace # between { and } with HULL_WALL ---
    # This makes structural hull sections transparent to FOV while still
    # blocking movement — the { } brackets mark a group where visibility
    # is shared: if any cell in the group is seen, all are seen.
    # MUST read raw glyph from map_lines, not tile.char (HULL_WALL has char='#').
    for row_idx in range(grid_height):
        _in_group = False
        for col_idx in range(grid_width):
            _glyph = map_lines[row_idx][col_idx]
            tile = tiles[row_idx][col_idx]
            if tile.kind == 'hull_wall' and _glyph in ('{', '}'):
                _in_group = not _in_group  # toggle on { and }
                continue
            # # between { and } → convert to HULL_WALL
            if _in_group and tile.kind == 'dungeon_wall':
                tiles[row_idx][col_idx] = world.HULL_WALL

    # Apply colour overrides to the tiles
    for row_idx in range(grid_height):
        for col_idx in range(grid_width):
            tile = tiles[row_idx][col_idx]
            # Find which glyph was originally at this position
            if col_idx < len(map_lines[row_idx]):
                glyph = map_lines[row_idx][col_idx]
                if glyph in colour_overrides:
                    # Create a new tile with the overridden fg.
                    # Bracket chars ({/}) are layout grouping markers —
                    # always render them using HULL_WALL's char (#), not
                    # the bracket glyph.
                    tiles[row_idx][col_idx] = world.Tile(
                        kind=tile.kind,
                        char=tile.char,
                        walkable=tile.walkable,
                        fg=colour_overrides[glyph],
                        bg=tile.bg,
                    )

    # --- Shared room flood-fill helper (reused by enemy scatter + loot scatter) ---
    from collections import deque
    from .engine import RNG as _RNG
    from .data.trade_goods import find_trade_good as _find_good

    def _flood_room(mx: int, my: int) -> list[tuple[int, int]]:
        """BFS from (mx, my) through walkable cells. Returns unoccupied cells.

        Walls and doors stop room expansion. Already-occupied positions
        (by entities) are excluded from the returned cell list.
        """
        _occupied = {(e.pos.x, e.pos.y) for e in entities}
        visited: set[tuple[int, int]] = {(mx, my)}
        queue: deque[tuple[int, int]] = deque([(mx, my)])
        room_cells: list[tuple[int, int]] = []
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) not in _occupied:
                room_cells.append((cx, cy))
            for ndx, ndy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                nx, ny = cx + ndx, cy + ndy
                if (nx, ny) in visited:
                    continue
                if not (0 <= nx < grid_width and 0 <= ny < grid_height):
                    continue
                nt = tiles[ny][nx]
                # Breach tiles are the hull entry — interior spawns
                # (enemies/loot) must not cross them into the entry
                # shaft outside the ship.
                if not nt.walkable or nt.kind in ('dungeon_door', 'breach'):
                    continue
                visited.add((nx, ny))
                queue.append((nx, ny))
        return room_cells

    # --- Scatter-spawn enemies via room flood-fill ---
    _squad_counter = 0
    for glyph, mx, my in enemy_markers:
        if glyph not in enemy_spawn_specs:
            continue
        _eid, _chance, _smin, _smax = enemy_spawn_specs[glyph]
        if _RNG.random() >= _chance:
            continue
        _squad_size = _RNG.randint(_smin, _smax)
        _cells = _flood_room(mx, my)
        if not _cells:
            _cells = [(mx, my)]
        _RNG.shuffle(_cells)
        _squad_id = f"{layout_id}_{glyph}_{_squad_counter}"
        _squad_counter += 1
        for _i in range(min(_squad_size, len(_cells))):
            _cx, _cy = _cells[_i]
            entities.append(world.Entity(
                char=glyph,
                fg=colour_overrides.get(glyph, (255, 100, 100)),
                pos=world.Position(_cx, _cy),
                name="",
                width=1, height=1,
                npc_char_id=_eid,
                squad_id=_squad_id,
            ))

    # --- Scatter loot via flood-fill ---
    # If no budget provided, fall back to old guaranteed behavior
    # (loot_budget is (0, 0) for non-boardable ships)
    _has_budget = loot_budget is not None and loot_budget[1] > 0

    if _has_budget:
        _total_budget = _RNG.randint(loot_budget[0], loot_budget[1])
        _remaining = _total_budget

    for _loot_pass in range(_LOOT_MAX_PASSES if _has_budget else 1):
        _anything_placed_this_pass = False

        for room_type, mx, my in loot_markers:
            pool = _LOOT_POOLS.get(room_type, [])
            if not pool:
                continue

            room_cells = _flood_room(mx, my)
            if not room_cells:
                continue

            # Pick a random cell (different each pass since _occupied
            # grows with each placed loot container)
            cx, cy = room_cells[_RNG.randint(0, len(room_cells) - 1)]

            if _has_budget:
                # Find an affordable good from the room's pool
                _pool_indices = list(range(len(pool)))
                _RNG.shuffle(_pool_indices)
                _placed = False
                for _pi in _pool_indices:
                    good_id, min_qty, max_qty = pool[_pi]
                    try:
                        _good = _find_good(good_id)
                    except KeyError:
                        continue
                    _qty = _RNG.randint(min_qty, max_qty)
                    _value = _good.base_price * _qty
                    if _value <= _remaining:
                        entities.append(world.Entity(
                            char="%",
                            fg=colour_overrides.get("%", (180, 220, 140)),
                            pos=world.Position(cx, cy),
                            name="Salvage Container",
                            width=1, height=1,
                            loot_data={"good_id": good_id, "quantity": _qty},
                        ))
                        _remaining -= _value
                        _placed = True
                        _anything_placed_this_pass = True
                        break
                # Nothing affordable — room stays empty this pass
            else:
                # Old guaranteed behavior (single pass)
                good_id, min_qty, max_qty = pool[_RNG.randint(0, len(pool) - 1)]
                qty = _RNG.randint(min_qty, max_qty)
                entities.append(world.Entity(
                    char="%",
                    fg=colour_overrides.get("%", (180, 220, 140)),
                    pos=world.Position(cx, cy),
                    name="Salvage Container",
                    width=1, height=1,
                    loot_data={"good_id": good_id, "quantity": qty},
                ))

        # Budget mode: early exit if nothing was placed this pass
        if _has_budget and not _anything_placed_this_pass:
            break

    # --- Salvage mission component: RNG-pick one loot room, place the
    # mission-tagged % there. Runs only when a mission owns this wreck
    # (first board — the caller caches the map, so placement persists).
    if component_good_id is not None and component_mission_id is not None and loot_markers:
        _ci = _RNG.randint(0, len(loot_markers) - 1)
        _room_type, _cmx, _cmy = loot_markers[_ci]
        _ccells = _flood_room(_cmx, _cmy)
        if not _ccells:
            _ccells = [(_cmx, _cmy)]
        _cx, _cy = _ccells[_RNG.randint(0, len(_ccells) - 1)]
        _comp = world.Entity(
            char='%',
            fg=(255, 215, 0),   # mission gold — distinct from dull-brass debris
            pos=world.Position(_cx, _cy),
            name=f"Mission Component: {component_good_id.replace('_', ' ').title()}",
            width=1, height=1,
            loot_data={"good_id": component_good_id, "quantity": 1},
        )
        # Mission-specific flags — read by trade.open_loot_pickup via
        # getattr, same pattern as the intercept loot entity.
        _comp.heist_mission = True
        _comp.heist_mission_id = component_mission_id
        entities.append(_comp)

    game_map = world.GameMap(
        width=grid_width,
        height=grid_height,
        tiles=tiles,
        entities=entities,
    )

    return (game_map, spawn_pos)


def generate_dungeon(
    params: DungeonParams,
) -> tuple[world.GameMap, world.Position]:
    """Generate a procedural dungeon using BSP room-and-corridor.

    Recursively splits the map with binary space partition, carves
    rooms in leaf regions, and connects sibling rooms with L-shaped
    corridors. Uses the run's seeded :data:`engine.RNG` so the same
    seed produces identical layouts.

    Args:
        params: :class:`DungeonParams` controlling dimensions,
                room sizes, and tile theming.

    Returns:
        ``(game_map, spawn_pos)`` — same shape as
        :func:`load_layout` so the EXPLORE handler works with
        either path.
    """
    from .engine import RNG

    w, h = params.width, params.height

    # Fill with wall tiles.
    tiles: list[list[world.Tile]] = [
        [params.tile_wall for _ in range(w)] for _ in range(h)
    ]

    # BSP split — recursively carve rooms and corridors.
    _center = _bsp_split(tiles, 0, 0, w, h, RNG, params)

    # Spawn = exit (standard roguelike).  The BSP midpoint can land on
    # a wall when rooms are sparse — walk outward to find a real floor.
    spawn_pos = _find_walkable_near(tiles, _center[0], _center[1])

    game_map = world.GameMap(width=w, height=h, tiles=tiles, entities=[])
    game_map.sight_radius = params.sight_radius

    return game_map, spawn_pos


# ---------------------------------------------------------------------------
# BSP helpers
# ---------------------------------------------------------------------------

def _bsp_split(
    tiles: list[list[world.Tile]],
    x: int, y: int,
    w: int, h: int,
    rng,
    params: DungeonParams,
) -> tuple[int, int]:
    """Recursively split region into rooms connected by corridors.

    Returns the center ``(cx, cy)`` of the carved area so parent
    splits can connect sibling halves.
    """
    # BSP splits until leaves are big enough that rooms (scaled by
    # fill_pct) have meaningful wall-space around them for corridors.
    _leaf_min = int(params.max_room_size / params.room_fill_pct) + 2
    _can_h = w >= _leaf_min
    _can_v = h >= _leaf_min

    if not _can_h and not _can_v:
        return _carve_room(tiles, x, y, w, h, rng, params)

    # Decide split direction: prefer the longer axis.
    if _can_h and _can_v:
        _horizontal = w > h
    else:
        _horizontal = _can_h

    # Minimum half must be big enough for a room + wall borders.
    _half_min = int(params.max_room_size / params.room_fill_pct) // 2 + 1
    if _horizontal:
        _split = rng.randint(
            max(params.min_room_size + 1, _half_min),
            w - max(params.min_room_size + 1, _half_min),
        )
        c1 = _bsp_split(tiles, x, y, _split, h, rng, params)
        c2 = _bsp_split(tiles, x + _split, y, w - _split, h, rng, params)
    else:
        _split = rng.randint(
            max(params.min_room_size + 1, _half_min),
            h - max(params.min_room_size + 1, _half_min),
        )
        c1 = _bsp_split(tiles, x, y, w, _split, rng, params)
        c2 = _bsp_split(tiles, x, y + _split, w, h - _split, rng, params)

    # Connect sibling halves with an L-shaped corridor.  Return the
    # corner (always on the path) so higher-level corridors reliably
    # intersect lower-level ones — the mathematical midpoint isn't
    # guaranteed to be on an L-shaped path.
    return _carve_corridor(tiles, c1[0], c1[1], c2[0], c2[1], rng, params)


def _carve_room(
    tiles: list[list[world.Tile]],
    x: int, y: int,
    w: int, h: int,
    rng,
    params: DungeonParams,
) -> tuple[int, int]:
    """Carve a room inside the region, leaving a 1-tile wall border.

    Returns the room centre for corridor connections.
    """
    # Need at least 1 tile of wall border on each side → region
    # must be ≥ (min_room_size + 2) in both axes for a proper room.
    _need_w = params.min_room_size + 2
    _need_h = params.min_room_size + 2
    if w < _need_w or h < _need_h:
        # Region too small — carve as much floor as possible.
        _floor_w = max(1, w - 2)
        _floor_h = max(1, h - 2)
        _fx = x + max(0, (w - _floor_w) // 2)
        _fy = y + max(0, (h - _floor_h) // 2)
        for _ry2 in range(_fy, _fy + _floor_h):
            for _rx2 in range(_fx, _fx + _floor_w):
                tiles[_ry2][_rx2] = params.tile_floor
        return (_fx + _floor_w // 2, _fy + _floor_h // 2)

    # Scale room max size by fill_pct so rooms leave wall-space
    # around them → corridors are visible and traversable.
    _avail_w = int((w - 2) * params.room_fill_pct)
    _avail_h = int((h - 2) * params.room_fill_pct)
    _avail_w = min(params.max_room_size, max(params.min_room_size, _avail_w))
    _avail_h = min(params.max_room_size, max(params.min_room_size, _avail_h))

    _rw = rng.randint(params.min_room_size, _avail_w)
    _rh = rng.randint(params.min_room_size, _avail_h)

    _rx = x + rng.randint(1, max(1, w - _rw - 1))
    _ry = y + rng.randint(1, max(1, h - _rh - 1))

    for _ry2 in range(_ry, _ry + _rh):
        for _rx2 in range(_rx, _rx + _rw):
            tiles[_ry2][_rx2] = params.tile_floor

    return (_rx + _rw // 2, _ry + _rh // 2)


def _carve_corridor(
    tiles: list[list[world.Tile]],
    x1: int, y1: int,
    x2: int, y2: int,
    rng,
    params: DungeonParams,
) -> tuple[int, int]:
    """Carve an L-shaped corridor between two points.

    Returns the corner ``(cx, cy)`` where the two legs meet —
    guaranteed to be on the corridor path.  Callers use this instead
    of the mathematical midpoint so higher-level corridors reliably
    intersect lower-level ones.
    """
    _h = len(tiles)
    _w = len(tiles[0]) if _h > 0 else 0

    if rng.random() < 0.5:
        # Horizontal leg, then vertical.
        for _x in range(min(x1, x2), max(x1, x2) + 1):
            if 0 <= y1 < _h and 0 <= _x < _w:
                if tiles[y1][_x].kind == 'dungeon_wall':
                    tiles[y1][_x] = params.tile_floor
        for _y in range(min(y1, y2), max(y1, y2) + 1):
            if 0 <= _y < _h and 0 <= x2 < _w:
                if tiles[_y][x2].kind == 'dungeon_wall':
                    tiles[_y][x2] = params.tile_floor
        return (x2, y1)
    else:
        # Vertical leg, then horizontal.
        for _y in range(min(y1, y2), max(y1, y2) + 1):
            if 0 <= _y < _h and 0 <= x1 < _w:
                if tiles[_y][x1].kind == 'dungeon_wall':
                    tiles[_y][x1] = params.tile_floor
        for _x in range(min(x1, x2), max(x1, x2) + 1):
            if 0 <= y2 < _h and 0 <= _x < _w:
                if tiles[y2][_x].kind == 'dungeon_wall':
                    tiles[y2][_x] = params.tile_floor
        return (x1, y2)


def _find_walkable_near(
    tiles: list[list[world.Tile]],
    cx: int, cy: int,
) -> world.Position:
    """Find a wall tile adjacent to floor near ``(cx, cy)`` and carve
    the exit into it (classic roguelike exit-alcove).

    Spirals outward from the midpoint, looking for a wall cell that
    has at least one walkable neighbour.  This embeds the ``>`` in a
    wall rather than on a corridor floor where it would block travel.
    """
    _h = len(tiles)
    _w = len(tiles[0]) if _h > 0 else 0

    _neighbour_dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]

    def _has_floor_neighbour(tx: int, ty: int) -> bool:
        for _ndx, _ndy in _neighbour_dirs:
            _nx, _ny = tx + _ndx, ty + _ndy
            if 0 <= _nx < _w and 0 <= _ny < _h:
                if tiles[_ny][_nx].walkable:
                    return True
        return False

    for _r in range(max(_w, _h)):
        for _dx in range(-_r, _r + 1):
            for _dy in range(-_r, _r + 1):
                if max(abs(_dx), abs(_dy)) != _r:
                    continue
                _tx, _ty = cx + _dx, cy + _dy
                if 0 <= _tx < _w and 0 <= _ty < _h:
                    if not tiles[_ty][_tx].walkable and _has_floor_neighbour(_tx, _ty):
                        tiles[_ty][_tx] = world.EXIT
                        return world.Position(_tx, _ty)
    # Fallback: scan entire map for a wall cell next to floor.
    for _y in range(_h):
        for _x in range(_w):
            if not tiles[_y][_x].walkable and _has_floor_neighbour(_x, _y):
                tiles[_y][_x] = world.EXIT
                return world.Position(_x, _y)
    # Last resort: place EXIT on any walkable tile.
    for _y in range(_h):
        for _x in range(_w):
            if tiles[_y][_x].walkable:
                tiles[_y][_x] = world.EXIT
                return world.Position(_x, _y)
    return world.Position(cx, cy)


def animate_breach(
    ctx,
    console: tcod.console.Console,
    game_map: world.GameMap,
    player_pos: world.Position,
    *,
    region_w: int,
    region_h: int,
) -> None:
    """Play a breach explosion animation.

    All tiles with ``kind='breach'`` start as
    :data:`world.DUNGEON_WALL`. A brief flash/crack animation plays
    along the line from ``player_pos`` toward each breach, then the
    breach tile is revealed.
    """
    from .navigation import _responsive_sleep
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH

    # Find breach positions
    breach_positions: list[world.Position] = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            if game_map.tiles[y][x].kind == 'breach':
                breach_positions.append(world.Position(x, y))

    if not breach_positions:
        return

    # Store originals and replace breach tiles with walls
    orig_tiles: dict[tuple[int, int], world.Tile] = {}
    for bp in breach_positions:
        key = (bp.x, bp.y)
        orig_tiles[key] = game_map.tiles[bp.y][bp.x]
        game_map.tiles[bp.y][bp.x] = world.DUNGEON_WALL

    frame_s = 0.08
    off_x = (region_w - game_map.width) // 2
    off_y = (region_h - game_map.height) // 2

    def _render_frame(sparks: list[tuple[int, int, str, tuple[int, int, int]]]) -> None:
        """Render one frame: clear, draw map, overlay sparks, present."""
        console.clear()
        world.render_world(
            console, game_map,
            region_x=0, region_y=0,
            region_w=region_w, region_h=region_h,
        )
        for (sx, sy, ch, fg) in sparks:
            if 0 <= sx < game_map.width and 0 <= sy < game_map.height:
                console.print(x=off_x + sx, y=off_y + sy, string=ch, fg=fg)
        ctx.context.present(console)
        _responsive_sleep(frame_s)

    # --- Animation sequence: explosion travels FROM each breach INTO the ship ---

    # Compute direction "into the ship" (away from player, beyond the breach)
    # and build per-frame spark sets that expand further into the ship
    frames_sparks: list[set[tuple[int, int]]] = [set() for _ in range(4)]
    for bp in breach_positions:
        # Direction from player to breach (this IS into the ship, away from player)
        dx = bp.x - player_pos.x
        dy = bp.y - player_pos.y
        steps = max(abs(dx), abs(dy))
        if steps == 0:
            steps = 1
        step_dx = dx / steps
        step_dy = dy / steps
        # Spark cells: starting AT the breach, going deeper in the same direction
        for depth in range(4):
            cx = round(bp.x + step_dx * depth)
            cy = round(bp.y + step_dy * depth)
            for f in range(depth, 4):
                frames_sparks[f].add((cx, cy))

    _spark_colors = [
        (255, 200, 100),  # gold spark
        (255, 160, 60),   # orange glow
        (255, 120, 40),   # red-hot
        (255, 255, 255),  # white flash
    ]
    _spark_chars = ['*', '+', 'o', '#']

    for frame_idx in range(4):
        _render_frame([
            (x, y, _spark_chars[frame_idx], _spark_colors[frame_idx])
            for x, y in frames_sparks[frame_idx]
        ])

    # Final frame: restore breach tiles (wall blown open -> X)
    for bp in breach_positions:
        key = (bp.x, bp.y)
        game_map.tiles[bp.y][bp.x] = orig_tiles[key]

    # Brief reveal frame
    _render_frame([])


