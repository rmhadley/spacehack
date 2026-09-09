"""Compile a JSON ship-interior spec into a ``.layout`` file.

The 6c authoring pipeline (doc 40): the agent authors a JSON spec and
this tool renders the ``.layout`` ASCII plus its directives. It
REFUSES to emit an invalid ship: dead doors, disconnected floors,
hull leaks (floor adjacent to border-connected void), asymmetric
twins, doors that open into open floor.

Two authoring modes:
- **rooms** — room rectangles; everything else is wall. Doors are
  validated against the rects.
- **walls** — the hull envelope starts as open floor; the spec's wall
  SEGMENTS divide it; rooms are DERIVED as the connected components
  and named by ``labels`` (one per room). This is the vim-like mode:
  you draw walls, the tool finds the rooms. A door is legal only in
  a wall that separates two labeled rooms.

``.layout`` is the canonical format; the JSON is an authoring
intermediary only, and recompiling never overwrites a hand-polished
file unless ``--force`` is given.

Usage:
    python3 tools/layout_compile.py spec.json [--out FILE] [--force]
    python3 tools/layout_compile.py --check FILE.layout
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

WALL, FLOOR, DOOR = "#", ".", "d"
BREACH, SPAWN, EXIT, CONSOLE = "b", "P", ">", "C"
WALKABLE = {FLOOR, DOOR, BREACH, SPAWN, EXIT, CONSOLE}
ENEMY_GLYPHS = "rRsSwWxXzZ"  # assigned to crew specs in order
LOOT_GLYPHS = "123456789"

TILE_LINES = [
    "TILE: # = DUNGEON_WALL",
    "TILE: . = DUNGEON_FLOOR",
    "TILE: d = DUNGEON_DOOR",
    "TILE: b = BREACH",
    "TILE: > = EXIT",
]
COLOUR_LINES = [
    "COLOUR: # = (120, 130, 150)",
    "COLOUR: b = (200, 120, 90)",
]


class LayoutSpecError(Exception):
    """The spec is invalid; the message lists every reason found."""

    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def _rooms_list(spec: dict) -> list[dict]:
    """Rooms accept a list or a name-keyed mapping (rect mode)."""
    rooms = spec.get("rooms", [])
    return list(rooms.values()) if isinstance(rooms, dict) else list(rooms)


def _neighbors(x: int, y: int):
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def _flood(grid: list[list[str]], x: int, y: int,
           open_cells: set[tuple[int, int]]) -> set:
    """One 8-connected component of open cells containing (x, y).

    8-connected because the player moves 8-directionally with corner
    cutting legal (world.try_move checks only the target tile): cells
    joined diagonally are one operational space."""
    seen = {(x, y)}
    queue = deque([(x, y)])
    while queue:
        cx, cy = queue.popleft()
        for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1),
                       (cx+1, cy+1), (cx-1, cy-1), (cx+1, cy-1), (cx-1, cy+1)):
            if (nx, ny) in open_cells and (nx, ny) not in seen:
                seen.add((nx, ny))
                queue.append((nx, ny))
    return seen


def _derive_rooms(spec: dict, grid: list[list[str]]) -> list[dict]:
    """Wall mode: derive rooms as connected floor components and name
    them from ``labels`` (one label per room, exactly). Raises
    LayoutSpecError when labels and rooms don't correspond."""
    w, h = len(grid[0]), len(grid)
    walkable = {
        (x, y)
        for y in range(h) for x in range(w)
        if grid[y][x] in WALKABLE
    }
    comps: list[set] = []
    comp_of: dict[tuple[int, int], int] = {}
    for cell in sorted(walkable):
        if cell in comp_of:
            continue
        comp = len(comps)
        seen = _flood(grid, *cell, walkable)
        for c in seen:
            comp_of[c] = comp
        comps.append(seen)

    named: dict[int, dict] = {}
    reasons: list[str] = []
    for label in spec["labels"]:
        x, y = label["at"]
        if (x, y) not in comp_of:
            reasons.append(
                f"label {label['name']} at ({x},{y}) is on no floor")
            continue
        comp = comp_of[(x, y)]
        if comp in named:
            reasons.append(
                f"rooms {named[comp]['name']} and {label['name']} share "
                f"one space ({x},{y}) — a wall is missing")
            continue
        named[comp] = label
    unlabeled = [i for i in range(len(comps)) if i not in named]
    if unlabeled:
        sample = sorted(comps[unlabeled[0]])[0]
        reasons.append(
            f"{len(unlabeled)} room(s) carry no label "
            f"(first at {sample}) — every space needs a name")
    if reasons:
        raise LayoutSpecError(reasons)

    derived = []
    for comp_id, cells in enumerate(comps):
        label = named[comp_id]
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        derived.append({
            "name": label["name"],
            "role": label.get("role", ""),
            "rect": [min(xs), min(ys), max(xs), max(ys)],
        })
    return derived


def _render_grid(spec: dict) -> list[list[str]]:
    """Void-default grid; hull spans close to wall; rooms carve floor
    (rect mode) or walls divide open floor (wall mode)."""
    w, h = spec["size"]["w"], spec["size"]["h"]
    grid = [[" "] * w for _ in range(h)]
    for y, x0, x1 in spec["hull"]["spans"]:
        for x in range(x0, x1 + 1):
            grid[y][x] = FLOOR if spec.get("walls") else WALL
    if not spec.get("walls"):
        for room in _rooms_list(spec):
            x0, y0, x1, y1 = room["rect"]
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    grid[y][x] = FLOOR
    else:
        for seg in spec["walls"]:
            x0, y0, x1, y1 = seg
            if y0 == y1:
                for x in range(min(x0, x1), max(x0, x1) + 1):
                    grid[y0][x] = WALL
            elif x0 == x1:
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    grid[y][x0] = WALL
            else:
                raise LayoutSpecError([f"diagonal wall segment {seg}"])
    for door in spec["doors"]:
        x, y = door["at"]
        grid[y][x] = DOOR
    entry = spec["entry"]
    for key, glyph in (("breach", BREACH), ("spawn", SPAWN), ("exit", EXIT)):
        x, y = entry[key]
        grid[y][x] = glyph
    console = spec.get("console")
    if console:
        cx, cy = console["pos"]
        grid[cy][cx] = CONSOLE
    return grid


def _walkable(grid: list[list[str]], x: int, y: int) -> bool:
    return (
        0 <= y < len(grid)
        and 0 <= x < len(grid[0])
        and grid[y][x] in WALKABLE
    )


def _validate(spec: dict, grid: list[list[str]]) -> list[str]:
    """Every emit-blocking check; returns the reason list."""
    reasons: list[str] = []
    h = len(grid)
    wall_mode = bool(spec.get("walls"))

    # dead doors: both opposite ends must be walkable; in wall mode a
    # door must also SEPARATE two labeled rooms — a door into open
    # floor (mid-room) is a structural error
    for door in spec["doors"]:
        x, y = door["at"]
        if grid[y][x] != DOOR:
            reasons.append(f"door at ({x},{y}) is not on the grid")
            continue
        if not (
            (_walkable(grid, x - 1, y) and _walkable(grid, x + 1, y))
            or (_walkable(grid, x, y - 1) and _walkable(grid, x, y + 1))
        ):
            reasons.append(
                f"door to nowhere at ({x},{y}) "
                f"[{door['between'][0]} / {door['between'][1]}]"
            )
            continue
        if wall_mode and not _separates_rooms(spec, grid, x, y):
            reasons.append(
                f"door at ({x},{y}) opens into one open space — "
                "doors belong in walls between two rooms"
            )

    # reachability: BFS from spawn must cover every walkable cell
    sx, sy = spec["entry"]["spawn"]
    open_cells = {
        (x, y)
        for y in range(h) for x in range(len(grid[0]))
        if grid[y][x] in WALKABLE
    }
    seen = _flood(grid, sx, sy, open_cells)
    for cell in sorted(open_cells - seen):
        reasons.append(f"unreachable floor at {cell}")

    # hull seal: no walkable cell touches border-connected void
    void: set[tuple[int, int]] = set()
    queue: deque = deque()
    for y in range(h):
        for x in (0, len(grid[0]) - 1):
            if grid[y][x] == " ":
                void.add((x, y))
                queue.append((x, y))
    for x in range(len(grid[0])):
        for y in (0, h - 1):
            if grid[y][x] == " " and (x, y) not in void:
                void.add((x, y))
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in _neighbors(x, y):
            if 0 <= nx < len(grid[0]) and 0 <= ny < h \
                    and grid[ny][nx] == " " and (nx, ny) not in void:
                void.add((nx, ny))
                queue.append((nx, ny))
    for y in range(1, h - 1):
        for x in range(1, len(grid[0]) - 1):
            # the breach and exit are the sanctioned holes to space
            if grid[y][x] in WALKABLE and grid[y][x] not in (BREACH, EXIT):
                for nx, ny in (
                    (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1),
                    (x + 1, y + 1), (x - 1, y - 1),
                    (x + 1, y - 1), (x - 1, y + 1),
                ):
                    if (nx, ny) in void:
                        reasons.append(
                            f"hull leak: walkable ({x},{y}) opens to space"
                        )
                        break

    # twin symmetry: mirrored rooms must be exact row mirrors
    h1 = h - 1
    for room in _rooms_list(spec):
        twin_name = room.get("twin")
        if not twin_name:
            continue
        twin = next(
            (r for r in _rooms_list(spec) if r["name"] == twin_name), None,
        )
        if twin is None:
            reasons.append(f"twin {twin_name} of {room['name']} missing")
            continue
        ax0, ay0, ax1, ay1 = room["rect"]
        bx0, by0, bx1, by1 = twin["rect"]
        if (ax0, ax1) != (bx0, bx1) or (ay0, ay1) != (h1 - by1, h1 - by0):
            reasons.append(
                f"twin asymmetry: {room['name']} vs {twin_name}"
            )
    return reasons


def _separates_rooms(spec: dict, grid: list[list[str]], x: int, y: int) -> bool:
    """Wall mode: with ALL doors treated as wall, do this door's two
    ends touch two DIFFERENT derived rooms? A legal door joins two
    spaces; a niche door opens back into its own."""
    probe = dict(spec, doors=[])
    probe_grid = [
        [WALL if c == DOOR else c for c in row] for row in grid
    ]
    try:
        _derive_rooms(probe, probe_grid)
    except LayoutSpecError:
        return False  # the walled world itself doesn't derive
    walk = {
        (xx, yy)
        for yy in range(len(probe_grid))
        for xx in range(len(probe_grid[0]))
        if probe_grid[yy][xx] in WALKABLE
    }
    ends = [
        (xx, yy) for xx, yy in ((x - 1, y), (x + 1, y))
        if (xx, yy) in walk
    ] or [
        (xx, yy) for xx, yy in ((x, y - 1), (x, y + 1))
        if (xx, yy) in walk
    ]
    if len(ends) < 2:
        return False
    return ends[1] not in _flood(probe_grid, *ends[0], walk)


def _place_markers(
    grid: list[list[str]], spec: dict, rooms: list[dict],
) -> tuple[list[str], list[str]]:
    """Write crew and loot markers into rooms; return the ENEMY and
    LOOT directive lines."""
    by_name = {r["name"]: r for r in rooms}
    enemy_lines: list[str] = []
    loot_lines: list[str] = []
    glyph_iter = iter(ENEMY_GLYPHS)
    loot_iter = iter(LOOT_GLYPHS)

    for crew in spec.get("content", {}).get("crew", []):
        glyph = next(glyph_iter)
        room = by_name[crew["room"]]
        x0, y0, x1, y1 = room["rect"]
        placed = 0
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if grid[y][x] == FLOOR and placed < 8:
                    grid[y][x] = glyph
                    placed += 1
        count = crew.get("count", "1")
        enemy_lines.append(f"ENEMY: {glyph} = {crew['spec']}@1.0#{count}")

    for loot in spec.get("content", {}).get("loot", []):
        digit = next(loot_iter)
        room = by_name[loot["room"]]
        x0, y0, x1, y1 = room["rect"]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if grid[y][x] == FLOOR:
                    grid[y][x] = digit
                    break
            else:
                continue
            break
        loot_lines.append(f"LOOT: {digit} = {loot['table']}")

    return enemy_lines, loot_lines


def compile_spec(spec: dict) -> str:
    """Render the JSON spec to ``.layout`` text; raises
    LayoutSpecError listing every reason when invalid."""
    grid = _render_grid(spec)
    reasons = _validate(spec, grid)
    if reasons:
        raise LayoutSpecError(reasons)
    if spec.get("walls"):
        # rooms are the enclosed spaces: derive with ALL doors walled
        # (the doors are the connections between them, not part of one)
        walled = [
            [WALL if c == DOOR else c for c in row] for row in grid
        ]
        rooms = _derive_rooms(spec, walled)
    else:
        rooms = _rooms_list(spec)
    enemy_lines, loot_lines = _place_markers(grid, spec, rooms)

    rows = ["".join(row) for row in grid]  # keep void spaces: no rstrip
    lines = [
        f"# {spec['layout_id']}.layout — generated by tools/layout_compile.py",
        f"# reference: {spec.get('reference', 'unspecified')}",
        "MAP",
        *rows,
        "ENDMAP",
        "",
        "# Tile mappings",
        *TILE_LINES,
        "",
        *enemy_lines,
        "",
        *loot_lines,
        "",
        "# Color overrides",
        *COLOUR_LINES,
    ]
    return "\n".join(lines) + "\n"


def check_layout(path: Path) -> list[str]:
    """Validate an existing ``.layout`` through the real parser plus
    the reachability checks on the parsed tiles. Unreachable FLOOR
    counts only where the author placed a glyph — in-span spaces are
    padding-invented floor (authored-void notches in hand decks), not
    an authoring error."""
    reasons: list[str] = []
    path = Path(path).resolve()
    sys.path.insert(0, str(REPO))
    from src.spacehack import dungeon_layout  # noqa: E402
    from src.spacehack import layout_format  # noqa: E402

    load_layout = dungeon_layout.load_layout

    layout_id = path.stem
    try:
        game_map, spawn = load_layout(layout_id, layout_dir=path.parent)
    except Exception as exc:  # noqa: BLE001 - report any parse failure
        return [f"parse failure: {exc}"]
    if spawn is None:
        reasons.append("no spawn ('P') in the layout")
    authored = layout_format.parse_layout_file(path).map_lines
    grid = [
        [tile for tile in row] for row in game_map.tiles
    ]
    # walkable = whatever the parse built, not a hardcoded kind list —
    # authored decks use airlock/hull kinds the compile flow never emits
    w, h = len(grid[0]), len(grid)
    if spawn is not None:
        origin = (spawn.x, spawn.y)
        open_cells = {
            (x, y)
            for y in range(h) for x in range(w)
            if grid[y][x].walkable
        }
        seen = _flood(grid, *origin, open_cells)
        for x, y in sorted(open_cells - seen):
            if authored[y][x] == " ":
                continue  # padding-invented floor under an authored void
            reasons.append(f"unreachable floor at ({x},{y})")
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", nargs="?", help="JSON spec path")
    parser.add_argument("--out", help="output .layout path")
    parser.add_argument("--force", action="store_true",
                        help="overwrite an existing hand-polished file")
    parser.add_argument("--check", help="validate an existing .layout")
    args = parser.parse_args()

    if args.check:
        reasons = check_layout(Path(args.check))
        if reasons:
            for reason in reasons:
                print(f"FAIL: {reason}")
            return 1
        print(f"PASS: {args.check}")
        return 0

    if not args.spec:
        parser.error("a JSON spec (or --check) is required")
    spec = json.loads(Path(args.spec).read_text())
    try:
        text = compile_spec(spec)
    except LayoutSpecError as exc:
        for reason in exc.reasons:
            print(f"FAIL: {reason}")
        return 1
    out = Path(args.out) if args.out else (
        REPO / "src" / "spacehack" / "data" / "layouts"
        / f"{spec['layout_id']}.layout"
    )
    if out.exists() and not args.force:
        print(f"REFUSED: {out} exists (hand edits?) — pass --force to overwrite")
        return 1
    out.write_text(text)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
