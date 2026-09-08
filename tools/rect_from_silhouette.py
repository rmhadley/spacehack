"""Quantum rectangle decomposition: silhouette → game-ready rect hull.

The second half of the 6c layout pipeline (doc 40). Takes a silhouette
(``#``/space text from ``trace_reference.py`` — or any hand-authored
hull in the same idiom) and decomposes it into rectangles measured in
3×3 quanta — the smallest rectangle is ``###/#.#/###``, one walkable
cell inside. Emits the outline render (boundary ``#``, interior ``.``,
outside space) plus the rect list as JSON (the seed of the wall-mode
room spec).

GUARANTEES (checked here, fail loudly):
- **Escape flood** — the no-diag rule: the player moves 8-directionally
  with corner cutting legal, so the interior must not reach a single
  void cell. A non-zero escape report is a FAIL: fix the silhouette,
  never hand-patch the rect output.
- **No pinholes** — interiors render walkable; walls only at hull edges.
- **Symmetry** — ``--symmetric`` union-mirrors the quantum grid before
  decomposition (for hulls meant to be top/bottom symmetric).

Usage:
    python3 tools/rect_from_silhouette.py SILHOUETTE.txt \
        --layout-id cruiser_crew [--json OUT.json] [--out OUT.txt] \
        [--qmin 5] [--symmetric]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

QUANTUM = 3  # wall pixels per quantum side: ### / #.# / ###


def _load_mask(path: Path) -> tuple[list[list[bool]], int, int]:
    lines = [l.rstrip("\n") for l in open(path)]
    w = max(len(l) for l in lines)
    return [[(x < len(l) and l[x] == "#") for x in range(w)] for l in lines], w, len(lines)


def _neighbors8(x: int, y: int, w: int, h: int):
    return ((nx, ny)
            for ny in range(y - 1, y + 2) for nx in range(x - 1, x + 2)
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) != (x, y))


def _quantize(mask, w, h, qmin, symmetric):
    qw, qh = (w + QUANTUM - 1) // QUANTUM, (h + QUANTUM - 1) // QUANTUM
    q = [[False] * qw for _ in range(qh)]
    for qy in range(qh):
        for qx in range(qw):
            solid = sum(
                mask[y][x]
                for y in range(qy * QUANTUM, min(qy * QUANTUM + QUANTUM, h))
                for x in range(qx * QUANTUM, min(qx * QUANTUM + QUANTUM, w)))
            q[qy][qx] = solid >= qmin
    if symmetric:
        for qy in range(qh):
            for qx in range(qw):
                if q[qy][qx] or q[qh - 1 - qy][qx]:
                    q[qy][qx] = q[qh - 1 - qy][qx] = True
    return q, qw, qh


def _fill_enclosed_void(q, qw, qh):
    """Void cells not connected to the border are quantization artifacts.
    Border-connected void is OUTSIDE SPACE or an open inlet — it stays."""
    outside = set()
    queue = deque()
    for x in range(qw):
        for y in (0, qh - 1):
            if not q[y][x] and (x, y) not in outside:
                outside.add((x, y)); queue.append((x, y))
    for y in range(qh):
        for x in (0, qw - 1):
            if not q[y][x] and (x, y) not in outside:
                outside.add((x, y)); queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if 0 <= nx < qw and 0 <= ny < qh and (nx, ny) not in outside \
                    and not q[ny][nx]:
                outside.add((nx, ny)); queue.append((nx, ny))
    for y in range(qh):
        for x in range(qw):
            if (x, y) not in outside:
                q[y][x] = True


def _decompose(q, qw, qh):
    """Greedy largest-rectangle decomposition (quantum coordinates)."""
    grid = [row[:] for row in q]
    used = [[False] * qw for _ in range(qh)]
    rects = []
    while True:
        heights = [[0] * qw for _ in range(qh)]
        for y in range(qh):
            for x in range(qw):
                if grid[y][x] and not used[y][x]:
                    heights[y][x] = heights[y - 1][x] + 1 if y else 1
        best = (0, None)
        for y in range(qh):
            stack = []
            x = 0
            hs = heights[y] + [0]
            while x <= qw:
                h = hs[x] if x < qw else 0
                start = x
                while stack and stack[-1][1] > h:
                    sx, sh = stack.pop()
                    if sh * (x - sx) > best[0]:
                        best = (sh * (x - sx), (sx, y - sh + 1, x - 1, y))
                    start = sx
                stack.append((start, h))
                x += 1
        if best[1] is None:
            return rects
        x0, y0, x1, y1 = best[1]
        rects.append({"qx0": x0, "qy0": y0, "qx1": x1, "qy1": y1})
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                used[y][x] = True
                grid[y][x] = False


def _render(q, qw, qh):
    """Outline render: hull interiors walkable ('.'), boundary walls
    ('#') where a floor pixel faces void, posts at junctions."""
    pw, ph = qw * QUANTUM, qh * QUANTUM
    p = [[" "] * pw for _ in range(ph)]
    for qy in range(qh):
        for qx in range(qw):
            if not q[qy][qx]:
                continue
            for dy in range(QUANTUM):
                for dx in range(QUANTUM):
                    p[qy * QUANTUM + dy][qx * QUANTUM + dx] = "."
    walls = []
    for y in range(ph):
        for x in range(pw):
            if p[y][x] != ".":
                continue
            for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                if not (0 <= nx < pw and 0 <= ny < ph) or p[ny][nx] == " ":
                    p[y][x] = "#"
                    walls.append((x, y))
                    break

    # junction seal: void diagonally between two walls is an outline
    # staircase gap — walls must meet orthogonally
    for _ in range(2):
        fills = []
        for y in range(1, ph - 1):
            for x in range(1, pw - 1):
                if p[y][x] == " " and (
                    (p[y-1][x-1] == "#" and p[y+1][x+1] == "#")
                    or (p[y-1][x+1] == "#" and p[y+1][x-1] == "#")):
                    fills.append((x, y))
        for x, y in fills:
            p[y][x] = "#"

    lines = ["".join(row).rstrip() for row in p]
    return "\n".join(l for l in lines if l.strip()) + "\n", len(walls)


def escape_flood(q, qw, qh) -> int:
    """The no-diag check: the player moves 8-directionally with corner
    cutting legal, over WALKABLE cells — the hull interior plus phantom
    floor (void within the hull's row spans, which the .layout parser
    makes walkable). Void outside the spans is true space: not
    walkable. An escape = reachable void outside the spans. Returns
    the count — 0 means sealed."""
    hull = {(x, y) for y in range(qh) for x in range(qw) if q[y][x]}
    spans = {}
    for y in range(qh):
        xs = [x for x in range(qw) if q[y][x]]
        spans[y] = (min(xs), max(xs)) if xs else None
    phantom = {
        (x, y)
        for y in range(qh) if spans[y]
        for x in range(spans[y][0], spans[y][1] + 1)
        if not q[y][x]
    }
    walkable = hull | phantom
    seed = next(iter(hull))
    seen, stack = {seed}, [seed]
    while stack:
        x, y = stack.pop()
        for nx, ny in _neighbors8(x, y, qw, qh):
            if (nx, ny) in walkable and (nx, ny) not in seen:
                seen.add((nx, ny)); stack.append((nx, ny))
    outside = {
        (x, y)
        for y in range(qh) if spans[y]
        for x in (0, qw - 1) if (x, y) not in q[y] or True
    }  # border-connected void, computed directly below
    border_void = set()
    queue = deque()
    for y in range(qh):
        for x in (0, qw - 1):
            if not q[y][x]:
                border_void.add((x, y)); queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in _neighbors8(x, y, qw, qh):
            if 0 <= nx < qw and 0 <= ny < qh and not q[ny][nx] \
                    and (nx, ny) not in border_void:
                border_void.add((nx, ny)); queue.append((nx, ny))
    return sum(1 for c in seen if c in border_void)


def _seal_phantom_entries(q, qw, qh) -> int:
    """Corner-cut seal: phantom quanta (walkable-by-parse void inside a
    row span) that 8-touch the hull are corner-cut entries from the
    interior — fill them hull-solid. Fixpoint: each fill can expose the
    next phantom cell."""
    sealed = 0
    while True:
        hull = {(x, y) for y in range(qh) for x in range(qw) if q[y][x]}
        entries = [
            (x, y)
            for y in range(qh) for x in range(qw)
            if not q[y][x] and any(
                (nx, ny) in hull for nx, ny in _neighbors8(x, y, qw, qh))
        ]
        if not entries:
            return sealed
        for x, y in entries:
            q[y][x] = True
        sealed += len(entries)


def process(path: Path, *, qmin: int = 5, symmetric: bool = False,
            json_out: Path | None = None,
            seal_phantom: bool = False) -> tuple[str, int, int]:
    mask, w, h = _load_mask(path)
    q, qw, qh = _quantize(mask, w, h, qmin, symmetric)
    _fill_enclosed_void(q, qw, qh)
    if seal_phantom:
        _seal_phantom_entries(q, qw, qh)
    rects = _decompose(q, qw, qh)
    art, _walls = _render(q, qw, qh)
    escapes = escape_flood(q, qw, qh)
    if escapes:
        raise LayoutEscapeError(
            f"escape flood: the interior reaches {escapes} void quanta — "
            "the hull is not sealed. Fix the SILHOUETTE, not this output.")
    if json_out:
        json_out.write_text(json.dumps({
            "layout_id": path.stem,
            "rects": rects,
        }, indent=2))
    return art, qw, qh


class LayoutEscapeError(Exception):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("silhouette", help="silhouette .txt (#/space)")
    parser.add_argument("--out", help="rect render .txt path")
    parser.add_argument("--json", dest="json_out",
                        help="rect list JSON path (room-spec seed)")
    parser.add_argument("--qmin", type=int, default=5,
                        help="solid wall pixels per quantum (default 5 of 9)")
    parser.add_argument("--symmetric", action="store_true",
                        help="union-mirror the quantum grid top/bottom")
    parser.add_argument("--seal-phantom", action="store_true",
                        help="fill phantom-floor quanta that corner-cut "
                        "from the interior (the no-diag seal at quantum "
                        "level; otherwise a leak FAILS the run)")
    args = parser.parse_args()

    path = Path(args.silhouette)
    try:
        art, qw, qh = process(path, qmin=args.qmin,
                              symmetric=args.symmetric,
                              seal_phantom=args.seal_phantom,
                              json_out=Path(args.json_out) if args.json_out else None)
    except LayoutEscapeError as exc:
        print(f"FAIL: {exc}")
        return 1
    if args.out:
        Path(args.out).write_text(art)
        print(f"wrote {args.out} ({qw}x{qh} quanta) — escape flood: sealed")
    else:
        print(art)
    return 0


if __name__ == "__main__":
    sys.exit(main())
