"""Trace a reference image onto an ASCII silhouette grid (doc 40 6c).

The reference-tracing half of the layout pipeline: crop the ship out
of a doors-view screenshot, level it (rotate), downsample onto the
character grid, threshold ship-vs-space, fill holes, clean spikes,
and optionally mirror into a symmetric hull. The output is the
SILHOUETTE the room pass then subdivides — shape first, rooms second.

    python3 tools/trace_reference.py IMAGE --crop L,T,R,B \
        [--rotate DEG] [--grid W,H] [--mirror] [--out FILE]
"""

from __future__ import annotations

import argparse
from collections import deque

from PIL import Image


def _morph_close(solid: list[list[bool]], times: int) -> list[list[bool]]:
    """Dilate then erode (8-neighborhood) — reattaches hairline breaks
    caused by threshold flicker along anti-aliased hull edges."""
    h, w = len(solid), len(solid[0])

    def neighbors(x, y, source):
        return [source[ny][nx]
                for ny in range(y - 1, y + 2) for nx in range(x - 1, x + 2)
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) != (x, y)]

    for _ in range(times):
        dil = [
            [any(neighbors(x, y, solid)) or solid[y][x] for x in range(w)]
            for y in range(h)
        ]
        solid = [
            [all(neighbors(x, y, dil)) for x in range(w)]
            for y in range(h)
        ]
    return solid


def _seal_diagonal_pinches(solid, gw, gh):
    """The no-diag rule (doc 40 6c): the player moves 8-dir with corner
    cutting legal, so any void cell diagonally between two solid cells
    is a real passage and must seal. Fixpoint: sealing one pinch can
    open its neighbor's diagonal, so loop until none remain. Returns
    the number of cells sealed."""
    sealed = 0
    while True:
        pinches = []
        for y in range(gh):
            for x in range(gw):
                if solid[y][x]:
                    continue
                nw_se = (x - 1 >= 0 and y - 1 >= 0 and solid[y - 1][x - 1]
                         and x + 1 < gw and y + 1 < gh and solid[y + 1][x + 1])
                ne_sw = (x + 1 < gw and y - 1 >= 0 and solid[y - 1][x + 1]
                         and x - 1 >= 0 and y + 1 < gh and solid[y + 1][x - 1])
                if nw_se or ne_sw:
                    pinches.append((x, y))
        if not pinches:
            return sealed
        for x, y in pinches:
            solid[y][x] = True
        sealed += len(pinches)


def _dedent(rows: list[str]) -> list[str]:
    """Strip the COMMON leading void — the leftmost hull column touches
    column 0, every other row keeps its indentation relative to it.
    The shape's left profile survives; the dead margin goes."""
    width = max(len(r) for r in rows)
    g = [r.ljust(width) for r in rows]
    leads = [len(r) - len(r.lstrip()) for r in g if r.strip()]
    common = min(leads) if leads else 0
    return [r[common:].rstrip() for r in g]


def trace(image_path: str, crop: tuple[int, int, int, int], rotate: float,
          grid: tuple[int, int], mirror: bool, threshold_bright: int = 88,
          threshold_red: int = 32, close: int = 0) -> str:
    img = Image.open(image_path).convert("RGB").crop(crop)
    if rotate:
        img = img.rotate(-rotate, expand=True,
                         fillcolor=(20, 8, 16))
    gw, gh = grid
    small = img.resize((gw, gh), Image.BOX)
    px = small.load()

    def is_ship(x, y):
        r, g, b = px[x, y]
        return (r + g + b) / 3 > threshold_bright or r - (g + b) / 2 > threshold_red

    mask = [[is_ship(x, y) for x in range(gw)] for y in range(gh)]

    outside: set = set()
    queue: deque = deque()
    for x in range(gw):
        for y in (0, gh - 1):
            if not mask[y][x]:
                outside.add((x, y)); queue.append((x, y))
    for y in range(gh):
        for x in (0, gw - 1):
            if not mask[y][x] and (x, y) not in outside:
                outside.add((x, y)); queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if 0 <= nx < gw and 0 <= ny < gh and (nx, ny) not in outside \
                    and not mask[ny][nx]:
                outside.add((nx, ny)); queue.append((nx, ny))
    solid = [[(x, y) not in outside for x in range(gw)] for y in range(gh)]
    if close:
        solid = _morph_close(solid, close)

    def neighbors8(x, y):
        return [solid[ny][nx]
                for ny in range(y - 1, y + 2) for nx in range(x - 1, x + 2)
                if 0 <= nx < gw and 0 <= ny < gh and (nx, ny) != (x, y)]

    for _ in range(3):
        new = [row[:] for row in solid]
        for y in range(gh):
            for x in range(gw):
                n = sum(neighbors8(x, y))
                if solid[y][x] and n <= 1:
                    new[y][x] = False
                if not solid[y][x] and n >= 7:
                    new[y][x] = True
        solid = new

    sealed = _seal_diagonal_pinches(solid, gw, gh)
    if sealed:
        print(f"diag pinches sealed: {sealed}", file=sys.stderr)

    comps, seen = [], set()
    for y in range(gh):
        for x in range(gw):
            if solid[y][x] and (x, y) not in seen:
                comp = {(x, y)}
                q = deque([(x, y)])
                while q:
                    cx, cy = q.popleft()
                    for nx, ny in ((cx+1, cy), (cx-1, cy),
                                   (cx, cy+1), (cx, cy-1)):
                        if 0 <= nx < gw and 0 <= ny < gh and solid[ny][nx] \
                                and (nx, ny) not in comp:
                            comp.add((nx, ny)); q.append((nx, ny))
                seen |= comp
                comps.append(comp)
    keep = set()
    if comps:
        biggest = max(len(c) for c in comps)
        threshold = max(8, biggest // 200)  # scale-aware: specks die at 4x
        keep = set().union(*[c for c in comps if len(c) >= threshold])

    if mirror:
        # crop the solid to its bounding box so the mirror seam sits
        # on the ship's true vertical center (rotation margins would
        # otherwise duplicate the hull)
        ys = [y for y in range(gh) for x in range(gw) if (x, y) in keep]
        xs = [x for y in range(gh) for x in range(gw) if (x, y) in keep]
        y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
        cropped = [
            [(x, y) in keep for x in range(x0, x1 + 1)]
            for y in range(y0, y1 + 1)
        ]
        # re-seal on the cropped grid: the crop and the mirror seam can
        # each open new diagonal pinches
        ch, cw = len(cropped), len(cropped[0])
        re_sealed = _seal_diagonal_pinches(cropped, cw, ch)
        if re_sealed:
            print(f"diag pinches re-sealed after crop: {re_sealed}",
                  file=sys.stderr)
        half = (ch + 1) // 2
        rows = [
            "".join("#" if c else " " for c in row)
            for row in cropped[:half]
        ]
        rows += rows[-2::-1] if len(cropped) % 2 == 0 else rows[-1::-1]
    else:
        rows = [
            "".join("#" if (x, y) in keep else " " for x in range(gw))
            for y in range(gh)
        ]
    return "\n".join(_dedent(rows)) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--crop", required=True, help="L,T,R,B pixels")
    parser.add_argument("--rotate", type=float, default=0.0)
    parser.add_argument("--grid", default="62,30", help="W,H cells")
    parser.add_argument("--mirror", action="store_true",
                        help="mirror the top half into a symmetric hull")
    parser.add_argument("--bright", type=int, default=88,
                        help="brightness threshold for ship pixels")
    parser.add_argument("--red", type=int, default=32,
                        help="red-dominance threshold for ship pixels")
    parser.add_argument("--close", type=int, default=0,
                        help="morphological close passes (reattaches "
                        "hairline hull breaks at high resolution)")
    parser.add_argument("--out")
    args = parser.parse_args()
    crop = tuple(int(v) for v in args.crop.split(","))
    grid = tuple(int(v) for v in args.grid.split(","))
    art = trace(args.image, crop, args.rotate, grid, args.mirror,
                threshold_bright=args.bright, threshold_red=args.red,
                close=args.close)
    if args.out:
        open(args.out, "w").write(art)
        print(f"wrote {args.out}")
    else:
        print(art)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
