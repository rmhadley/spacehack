"""Compile a JSON ship-interior spec into a ``.layout`` file.

The 6c authoring pipeline (doc 40): the agent authors a JSON spec —
rooms with names/rects/roles/twins, door edges, entry breach/spawn/
exit, console, hull row-spans, crew and loot content — and this tool
renders the ``.layout`` ASCII plus its directives. It REFUSES to emit
an invalid ship: dead doors, disconnected floors, hull leaks (floor
adjacent to border-connected void), asymmetric twin rooms.

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
    """Rooms accept a list or a name-keyed mapping."""
    rooms = spec["rooms"]
    return list(rooms.values()) if isinstance(rooms, dict) else list(rooms)


def _render_grid(spec: dict) -> list[list[str]]:
    """Void-default grid; hull spans close to wall; rooms carve floor."""
    w, h = spec["size"]["w"], spec["size"]["h"]
    grid = [[" "] * w for _ in range(h)]
    for y0, x0, x1 in spec["hull"]["spans"]:
        for x in range(x0, x1 + 1):
            grid[y0][x] = WALL
    for room in _rooms_list(spec):
        x0, y0, x1, y1 = room["rect"]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                grid[y][x] = FLOOR
    for door in spec["doors"]:
        x, y = door["at"]
        grid[y][x] = DOOR
    entry = spec["entry"]
    bx, by = entry["breach"]
    grid[by][bx] = BREACH
    sx, sy = entry["spawn"]
    grid[sy][sx] = SPAWN
    ex, ey = entry["exit"]
    grid[ey][ex] = EXIT
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
    w, h = len(grid[0]), len(grid)
    rooms = _rooms_list(spec)

    # dead doors: both opposite ends must be walkable
    for door in spec["doors"]:
        x, y = door["at"]
        if grid[y][x] != DOOR:
            reasons.append(f"door at ({x},{y}) is not on the grid")
            continue
        if not (
            (_walkable(grid, x - 1, y) and _walkable(grid, x + 1, y))
            or (_walkable(grid, x, y - 1) and _walkable(grid, x, y + 1))
        ):
            between = " or ".join(
                sorted({d["between"][0], d["between"][1]} for d in [door])[0]
            )
            reasons.append(f"door to nowhere at ({x},{y}) [{between}]")

    # reachability: BFS from spawn must cover every walkable cell
    sx, sy = spec["entry"]["spawn"]
    seen: set[tuple[int, int]] = {(sx, sy)}
    queue: deque[tuple[int, int]] = deque([(sx, sy)])
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if _walkable(grid, nx, ny) and (nx, ny) not in seen:
                seen.add((nx, ny))
                queue.append((nx, ny))
    for y in range(h):
        for x in range(w):
            if grid[y][x] in WALKABLE and (x, y) not in seen:
                reasons.append(f"unreachable floor at ({x},{y})")

    # hull seal: no walkable cell touches border-connected void
    void_seen: set[tuple[int, int]] = set()
    queue = deque()
    for x in range(w):
        for y in (0, h - 1):
            if grid[y][x] == " ":
                void_seen.add((x, y))
                queue.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if grid[y][x] == " " and (x, y) not in void_seen:
                void_seen.add((x, y))
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == " " \
                    and (nx, ny) not in void_seen:
                void_seen.add((nx, ny))
                queue.append((nx, ny))
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if grid[y][x] in WALKABLE:
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1),
                               (x + 1, y + 1), (x - 1, y - 1),
                               (x + 1, y - 1), (x - 1, y + 1)):
                    if (nx, ny) in void_seen:
                        reasons.append(
                            f"hull leak: walkable ({x},{y}) opens to space"
                        )
                        break

    # twin symmetry: mirrored rooms must be exact row mirrors
    h1 = h - 1
    for room in rooms:
        twin_name = room.get("twin")
        if not twin_name:
            continue
        twin = next(
            (r for r in rooms if r["name"] == twin_name), None,
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


def _place_markers(grid: list[list[str]], spec: dict) -> tuple[list[str], list[str]]:
    """Write crew/console-adjacent markers into rooms; return the
    ENEMY and LOOT directive lines."""
    by_name = {r["name"]: r for r in _rooms_list(spec)}
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
    enemy_lines, loot_lines = _place_markers(grid, spec)

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
    the door/reachability checks on the parsed tiles."""
    reasons: list[str] = []
    path = Path(path).resolve()
    sys.path.insert(0, str(REPO))
    from src.spacehack import dungeon_layout  # noqa: E402

    load_layout = dungeon_layout.load_layout

    layout_id = path.stem
    try:
        game_map, spawn = load_layout(layout_id, layout_dir=path.parent)
    except Exception as exc:  # noqa: BLE001 - report any parse failure
        return [f"parse failure: {exc}"]
    if spawn is None:
        reasons.append("no spawn ('P') in the layout")
    grid = [
        [tile.kind for tile in row] for row in game_map.tiles
    ]
    walk_kinds = {"dungeon_floor", "dungeon_door", "breach", "exit"}
    w, h = len(grid[0]), len(grid)
    if spawn is not None:
        _origin = (spawn.x, spawn.y)
        seen: set[tuple[int, int]] = {_origin}
        queue: deque = deque([_origin])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] in walk_kinds \
                        and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        for y in range(h):
            for x in range(w):
                if grid[y][x] in walk_kinds and (x, y) not in seen:
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
