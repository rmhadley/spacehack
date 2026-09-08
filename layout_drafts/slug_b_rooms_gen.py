"""Generate the slug_b rooms-and-doors JSON spec from the blessed rect hull.

Structure-first draft (doc 40 6c): rooms + halls + doors only, no
content pass. Reads layout_drafts/slug_b_rect.txt (USER-BLESSED, never
modified), emits layout_drafts/slug_b_rooms_spec.json for
tools/layout_compile.py wall mode.

Method: paint hull floor + room outlines (quantum-rect walls, clipped
to the hull), auto-seal floors that 8-touch border-connected void,
flood the components, then place doors from the DERIVED adjacency —
a spanning tree (guaranteed connectivity) plus loop extras (paired
combat flow). Ship faces LEFT: breach draft at the stern, C console
in the bow piloting room = the fight-to-the-console walk.
"""

import json
from collections import deque
from pathlib import Path

DRAFTS = Path(__file__).resolve().parent
RECT = DRAFTS / "slug_b_rect.txt"
OUT = DRAFTS / "slug_b_rooms_spec.json"

ROWS = RECT.read_text().rstrip("\n").split("\n")
H, W = len(ROWS), max(len(r) for r in ROWS)

spans = []
for y, row in enumerate(ROWS):
    xs = [x for x, c in enumerate(row) if c == "#"]
    if xs:
        spans.append([y, min(xs), max(xs)])
span_of = {s[0]: (s[1], s[2]) for s in spans}

# rooms in quantum rects (x0,y0)-(x1,y1); pixel walls = rect outline
Q = [(name, x0, y0, x1, y1) for name, x0, y0, x1, y1 in [
    ("gun_spire_up", 0, 7, 5, 8), ("gun_spire_dn", 0, 16, 5, 17),
    ("weapons_up", 6, 7, 11, 11), ("weapons_dn", 6, 13, 11, 17),
    ("battery_up", 57, 7, 64, 9), ("battery_dn", 57, 15, 64, 17),
    ("shields_up", 12, 7, 16, 11), ("shields_dn", 12, 13, 16, 17),
    ("medbay_up", 17, 7, 28, 9), ("medbay_dn", 17, 15, 28, 17),
    ("oxygen_up", 29, 7, 40, 11), ("oxygen_dn", 29, 13, 40, 17),
    ("storage_up", 41, 7, 52, 11), ("storage_dn", 41, 13, 52, 17),
    ("bay_up", 53, 7, 56, 11), ("bay_dn", 53, 13, 56, 17),
    ("sensors_up", 16, 0, 38, 6), ("sensors_dn", 16, 18, 38, 24),
    ("comms_up", 39, 0, 65, 6), ("comms_dn", 39, 18, 65, 24),
    ("piloting", 17, 10, 28, 14),
    ("spine_hall", 29, 12, 56, 12),
    ("engine_core", 57, 10, 65, 14),
]]

grid = [[" "] * W for _ in range(H)]
for y, x0, x1 in spans:
    for x in range(x0, x1 + 1):
        grid[y][x] = "."


segments = []


def clip_h(y, x0, x1):
    if y not in span_of:
        return
    a, b = span_of[y]
    lo, hi = max(x0, a), min(x1, b)
    if lo <= hi:
        for x in range(lo, hi + 1):
            grid[y][x] = "#"
        segments.append([lo, y, hi, y])


def clip_v(x, y0, y1):
    run = None
    for y in range(y0, y1 + 1):
        inside = y in span_of and span_of[y][0] <= x <= span_of[y][1]
        if inside:
            grid[y][x] = "#"
            run = [run[0], y] if run else [y, y]
        elif run:
            segments.append([x, run[0], x, run[1]])
            run = None
    if run:
        segments.append([x, run[0], x, run[1]])


wall_cells = set()
for bx0, by0, bx1, by1 in [(33, 36, 50, 38), (45, 6, 47, 11), (45, 63, 47, 68)]:
    for yy in range(by0, by1 + 1):
        clip_h(yy, bx0, bx1)
for _, qx0, qy0, qx1, qy1 in Q:
    px0, py0, px1, py1 = qx0 * 3, qy0 * 3, qx1 * 3 + 2, qy1 * 3 + 2
    # one-wall convention: only top + left edges — the room below/right
    # draws its own top/left, so adjacent rooms share a single 1px wall
    clip_h(py0, px0, px1)
    clip_v(px0, py0, py1)

# hull auto-seal: floor 8-adjacent to border-connected void becomes wall
void = set()
queue = deque()
for y in range(H):
    for x in (0, W - 1):
        if grid[y][x] == " ":
            void.add((x, y)); queue.append((x, y))
for x in range(W):
    for y in (0, H - 1):
        if grid[y][x] == " ":
            void.add((x, y)); queue.append((x, y))
while queue:
    x, y = queue.popleft()
    for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1),
                   (x+1, y+1), (x-1, y-1), (x+1, y-1), (x-1, y+1)):
        if 0 <= nx < W and 0 <= ny < H and grid[ny][nx] == " " \
                and (nx, ny) not in void:
            void.add((nx, ny)); queue.append((nx, ny))
for y in range(H):
    for x in range(W):
        if grid[y][x] == ".":
            near = any((nx, ny) in void
                       for nx in (x-1, x, x+1) for ny in (y-1, y, y+1))
            if near:
                grid[y][x] = "#"
                wall_cells.add((x, y))
                segments.append([x, y, x, y])

# labels: snap each room's rect center to the nearest FLOOR cell
def snap_floor(px, py):
    best, bd = None, 1 << 30
    for y in range(max(0, py - 40), min(H, py + 41)):
        for x in range(max(0, px - 40), min(W, px + 41)):
            if grid[y][x] == ".":
                d = (x - px) ** 2 + (y - py) ** 2
                if d < bd:
                    best, bd = (x, y), d
    return best


labels = {}
for n, qx0, qy0, qx1, qy1 in Q:
    cx, cy = ((qx0 + qx1) * 3) // 2 + 1, ((qy0 + qy1) * 3) // 2 + 1
    labels[n] = snap_floor(cx, cy)

# components (all doors walled)
walkable = {(x, y) for y in range(H) for x in range(W)
            if grid[y][x] in ".bPC"}
comp_of, comps = {}, []
for cell in sorted(walkable):
    if cell in comp_of:
        continue
    seen = {cell}
    q = deque([cell])
    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
            if (nx, ny) in walkable and (nx, ny) not in seen:
                seen.add((nx, ny)); q.append((nx, ny))
    for c in seen:
        comp_of[c] = len(comps)
    comps.append(seen)

seed_of = {}
for name, (lx, ly) in labels.items():
    assert (lx, ly) in comp_of, f"label {name} off floor ({lx},{ly})"
    comp = comp_of[(lx, ly)]
    assert comp not in seed_of, f"{name} shares a space with {seed_of[comp]}"
    seed_of[comp] = name
assert len(seed_of) == len(comps), (
    f"{len(comps) - len(seed_of)} unlabeled room(s)")
name_of = {i: n for i, n in seed_of.items()}

# adjacency from painted walls: wall cell with floor of two comps
adj = {}
for y in range(H):
    for x in range(W):
        if grid[y][x] != "#":
            continue
        for (ax, ay), (bx, by) in (((x-1, y), (x+1, y)), ((x, y-1), (x, y+1))):
            if (ax, ay) in comp_of and (bx, by) in comp_of \
                    and comp_of[(ax, ay)] != comp_of[(bx, by)]:
                a, b = sorted((comp_of[(ax, ay)], comp_of[(bx, by)]))
                adj.setdefault((a, b), []).append((x, y))


def comp_center(c):
    xs = [x for x, _ in comps[c]]
    ys = [y for _, y in comps[c]]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def pick_door(a, b):
    cands = adj[(a, b)]
    ca, cb = comp_center(a), comp_center(b)
    mx, my = (ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2
    return min(cands, key=lambda c: (c[0] - mx) ** 2 + (c[1] - my) ** 2)


# spanning tree from piloting over the adjacency graph
tree, seen_c = [], {comp_of[labels["piloting"]]}
queue = deque([comp_of[labels["piloting"]]])
while queue:
    c = queue.popleft()
    for (a, b) in adj:
        other = b if a == c else a if b == c else None
        if other is not None and other not in seen_c:
            seen_c.add(other)
            tree.append((a, b))
            queue.append(other)
assert len(seen_c) == len(comps), (
    f"disconnected rooms: {sorted(set(name_of) - seen_c)}")

LOOP_PAIRS = [("medbay_up", "oxygen_up"), ("medbay_dn", "oxygen_dn"),
              ("oxygen_up", "storage_up"), ("oxygen_dn", "storage_dn"),
              ("storage_up", "bay_up"), ("storage_dn", "bay_dn"),
              ("shields_up", "medbay_up"), ("shields_dn", "medbay_dn"),
              ("bay_up", "engine_core"), ("bay_dn", "engine_core"),
              ("weapons_up", "gun_spire_up"), ("weapons_dn", "gun_spire_dn"),
              ("shields_up", "sensors_up"), ("shields_dn", "sensors_dn"),
              ("medbay_up", "comms_up"), ("medbay_dn", "comms_dn"),
              ("bay_up", "battery_up"), ("bay_dn", "battery_dn"),
              ("battery_up", "engine_core"), ("battery_dn", "engine_core"),
              ("spine_hall", "oxygen_up"), ("spine_hall", "oxygen_dn"),
              ("spine_hall", "storage_up"), ("spine_hall", "storage_dn"),
              ("spine_hall", "bay_up"), ("spine_hall", "bay_dn")]
by_name = {name_of[c]: c for c in range(len(comps))}
loop_doors = []
for a, b in LOOP_PAIRS:
    ca, cb = by_name.get(a), by_name.get(b)
    if ca is None or cb is None:
        continue
    if ca == cb:
        continue  # same space — no wall between them
    if (min(ca, cb), max(ca, cb)) in adj:
        loop_doors.append((min(ca, cb), max(ca, cb)))

seen_pairs = set()
doors = []
for a, b in tree + loop_doors:
    key = (min(a, b), max(a, b))
    if key in seen_pairs or key not in adj:
        continue
    seen_pairs.add(key)
    doors.append({"at": list(pick_door(*key)),
                  "between": sorted([name_of[key[0]], name_of[key[1]]])})

xr = span_of[37][1]
spec = {
    "layout_id": "slug_b_rooms",
    "reference": "FTL Slug Cruiser B doors-view (fandom clean render) "
                 "-> trace -> blessed rect hull (slug_b_rect.txt)",
    "size": {"w": W, "h": H},
    "hull": {"spans": spans},
    "walls": True,
    "walls": segments,
    "labels": [{"name": n, "role": "", "at": list(labels[n])}
               for n in sorted(labels)],
    "doors": doors,
    "entry": {"breach": [xr, 37], "spawn": [xr - 4, 37], "exit": [xr - 3, 37]},
    "console": {"pos": [17 * 3 + 2, 37]},
}
OUT.write_text(json.dumps(spec, indent=1))
print(f"wrote {OUT}: {len(comps)} rooms, {len(wall_cells)} wall cells, "
      f"{len(doors)} doors ({len(tree)} tree + {len(seen_pairs) - len(tree)} loops)")
