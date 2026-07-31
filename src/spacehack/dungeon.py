"""Ship interior layout parser.

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
"""

from __future__ import annotations

import pathlib

from . import world


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

    Returns ``(glyph, (r, g, b))`` or ``None`` if the line isn't a
    colour directive.
    """
    line = line.strip()
    if not line.startswith("COLOUR:"):
        return None
    rest = line[7:].strip()
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
) -> tuple[world.GameMap, world.Position]:
    """Parse ``layout_id.layout`` and return ``(game_map, spawn_pos)``.

    ``loot_budget`` is the ship's ``(min_credits, max_credits)`` for
    interior salvage. When provided, up to 4 passes are made through
    all loot rooms to try to spend the rolled budget — some rooms
    naturally end up with multiple loot containers while others get
    none. When ``None`` (default), old guaranteed behavior is used.

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
                    # Create a new tile with the overridden fg
                    # Preserve bracket chars ({/}) so they render as brackets,
                    # not as the HULL_WALL constant's char (which is #).
                    _char = glyph if glyph in ('{', '}') else tile.char
                    tiles[row_idx][col_idx] = world.Tile(
                        kind=tile.kind,
                        char=_char,
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
                if not nt.walkable or nt.kind == 'dungeon_door':
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

    game_map = world.GameMap(
        width=grid_width,
        height=grid_height,
        tiles=tiles,
        entities=entities,
    )

    return (game_map, spawn_pos)


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


def _detect_ground_combat(
    ctx, game_map: world.GameMap, player_pos: world.Position,
) -> list[world.Entity]:
    """Check for hostile NPC chars within detect radius + LOS.

    If any hostile entity spots the player, all entities with the
    same ``squad_id`` within a 20-tile assist radius are pulled into
    combat. Returns a list of hostile entities (may be empty).
    """
    import math as _m
    from .data.npc_chars import find_npc_char as _fnc
    from . import faction as _faction

    _ASSIST_RADIUS = 20

    for _e in game_map.entities:
        if _e is ctx.player:
            continue
        _eid = getattr(_e, 'npc_char_id', '')
        if not _eid:
            continue
        try:
            _spec = _fnc(_eid)
        except KeyError:
            continue
        _rep = ctx.faction_reputation.get(_spec.faction, 0)
        _attitude = _faction.get_attitude(_rep)
        if _attitude not in ("enemy", "disliked"):
            continue
        _dist = _m.hypot(player_pos.x - _e.pos.x, player_pos.y - _e.pos.y)
        if _dist <= 0 or _dist > _spec.detect_radius:
            continue
        _steps = max(abs(_e.pos.x - player_pos.x), abs(_e.pos.y - player_pos.y))
        _los_blocked = False
        for _si in range(1, _steps):
            _t = _si / max(_steps, 1)
            _lx = round(player_pos.x + (_e.pos.x - player_pos.x) * _t)
            _ly = round(player_pos.y + (_e.pos.y - player_pos.y) * _t)
            if game_map.in_bounds(_lx, _ly):
                _tile = game_map.tiles[_ly][_lx]
                if not _tile.walkable:
                    _los_blocked = True
                    break
        if _los_blocked:
            continue

        # Hostile spotted! Find all squad members within assist radius.
        _squad_id = getattr(_e, 'squad_id', '')
        _result = [_e]
        if _squad_id:
            for _oe in game_map.entities:
                if _oe is _e or _oe is ctx.player:
                    continue
                if getattr(_oe, 'squad_id', '') != _squad_id:
                    continue
                if not getattr(_oe, 'npc_char_id', ''):
                    continue
                _od = _m.hypot(
                    player_pos.x - _oe.pos.x, player_pos.y - _oe.pos.y,
                )
                if _od <= _ASSIST_RADIUS:
                    _result.append(_oe)

        # Reveal fog around all combatants — combat is loud,
        # the player would know where enemies are positioned.
        for _ce in _result:
            reveal_around(game_map, _ce.pos, radius=3)

        return _result

    return []
