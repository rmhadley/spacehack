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
}

# Glyphs that place entities rather than tiles.
_ENTITY_GLYPHS: set[str] = {"P", "C", "E"}

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


def load_layout(layout_id: str) -> tuple[world.GameMap, world.Position]:
    """Parse ``layout_id.layout`` and return ``(game_map, spawn_pos)``.

    Raises:
      FileNotFoundError: if the layout file doesn't exist.
      ValueError: if the layout file is malformed.
    """
    path = _LAYOUT_DIR / f"{layout_id}.layout"
    if not path.exists():
        raise FileNotFoundError(f"Layout not found: {path}")

    raw = path.read_text(encoding="utf-8").splitlines()

    # Collect colour overrides: glyph -> (r, g, b)
    colour_overrides: dict[str, tuple[int, int, int]] = {}

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
        if stripped.startswith("#") or not stripped:
            continue  # comment or blank

        if in_map:
            map_lines.append(line)  # preserve leading/trailing whitespace
        elif after_map:
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

    # Build tiles and collect entity placements
    tiles: list[list[world.Tile]] = []
    entities: list[world.Entity] = []
    spawn_pos: world.Position | None = None

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
                    # Cockpit — place as a flavor entity (placeholder)
                    entities.append(world.Entity(
                        char="C", fg=colour_overrides.get("C", (255, 200, 80)),
                        pos=world.Position(col_idx, row_idx),
                        name="Ship Computer", width=1, height=1,
                    ))
                elif ch == "E":
                    # Engine — flavor entity (placeholder for now)
                    entities.append(world.Entity(
                        char="E", fg=colour_overrides.get("E", (180, 200, 220)),
                        pos=world.Position(col_idx, row_idx),
                        name="Engine Terminal", width=1, height=1,
                    ))
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

    # Apply colour overrides to the tiles
    for row_idx in range(grid_height):
        for col_idx in range(grid_width):
            tile = tiles[row_idx][col_idx]
            # Find which glyph was originally at this position
            if col_idx < len(map_lines[row_idx]):
                glyph = map_lines[row_idx][col_idx]
                if glyph in colour_overrides:
                    # Create a new tile with the overridden fg
                    tiles[row_idx][col_idx] = world.Tile(
                        kind=tile.kind,
                        char=tile.char,
                        walkable=tile.walkable,
                        fg=colour_overrides[glyph],
                        bg=tile.bg,
                    )

    game_map = world.GameMap(
        width=grid_width,
        height=grid_height,
        tiles=tiles,
        entities=entities,
    )

    return (game_map, spawn_pos)
