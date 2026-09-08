"""Generate the Atlas superfreighter rooms-and-doors spec.

Cargo superfreighter structure draft: a central spine hall on the
user's true midpoint (H=72, spine floor rows 35-36 between symmetric
walls), the container stack as 8 large hold rooms in four bands
(top/mid-up/mid-dn/bottom x fore/aft), command bow-right with the C
console, engineering aft-left. Reads layout_drafts/atlas_rect.txt
(USER-BLESSED, never modified), emits atlas_rooms_spec.json.
Boundary carry-through: the rect's '#' runs emit as wall segments.
"""

import json
from collections import deque
from pathlib import Path

DRAFTS = Path(__file__).resolve().parent
RECT = DRAFTS / "atlas_rect.txt"
OUT = DRAFTS / "atlas_rooms_spec.json"

ROWS = RECT.read_text().rstrip("\n").split("\n")
H, W = len(ROWS), max(len(r) for r in ROWS)
MIRROR = H - 1  # 71

spans = []
for y, row in enumerate(ROWS):
    xs = [x for x, c in enumerate(row) if c == "#"]
    if xs:
        spans.append([y, min(xs), max(xs)])
span_of = {s[0]: (s[1], s[2]) for s in spans}

segments = []
grid = [[" "] * W for _ in range(H)]
for y, x0, x1 in spans:
    for x in range(x0, x1 + 1):
        grid[y][x] = "."

# the blessed outline IS the boundary wall — carry it through verbatim
for y, row in enumerate(ROWS):
    run = None
    for x in range(W + 1):
        solid = x < len(row) and row[x] == "#"
        if solid:
            run = [run[0], x] if run else [x, x]
        elif run:
            for xx in range(run[0], run[1] + 1):
                grid[y][xx] = "#"
            segments.append([run[0], y, run[1], y])
            run = None


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


# rooms: (name, x0, y0, x1, y1) — mirror pairs satisfy y0+y1 = 71
Q = [
    ("hold_top_fore", 46, 0, 160, 11), ("hold_top_aft", 160, 0, 290, 11),
    ("hold_up_fore", 46, 12, 118, 33), ("hold_up_aft", 118, 12, 200, 33),
    ("hold_dn_fore", 46, 38, 118, 59), ("hold_dn_aft", 118, 38, 200, 59),
    ("hold_bot_fore", 46, 60, 160, 71), ("hold_bot_aft", 160, 60, 290, 71),
    ("hold_aft_up", 4, 12, 45, 23), ("hold_aft_dn", 4, 48, 45, 59),
    ("spine_hall", 46, 34, 199, 37),
    ("command", 200, 24, 296, 47),
    ("engineering", 0, 24, 45, 47),
]

for _, x0, y0, x1, y1 in Q:
    # mirror-symmetric one-wall: dn rooms (y0 >= 36) draw top+left,
    # up rooms (y1 <= 35) draw bottom+left, self-mirror rooms both
    if y1 <= 35:
        clip_h(y1, x0, x1)
        clip_v(x0, y0, y1)
    elif y0 >= 36:
        clip_h(y0, x0, x1)
        clip_v(x0, y0, y1)
    else:
        clip_h(y0, x0, x1)
        clip_h(y1, x0, x1)
        clip_v(x0, y0, y1)

# auto-seal: floor 8-adjacent to border-connected void -> wall
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
        if grid[y][x] == "." and any(
                (nx, ny) in void
                for nx in (x-1, x, x+1) for ny in (y-1, y, y+1)):
            grid[y][x] = "#"
            segments.append([x, y, x, y])


def snap_floor(px, py):
    best, bd = None, 1 << 30
    for y in range(max(0, py - 80), min(H, py + 81)):
        for x in range(max(0, px - 80), min(W, px + 81)):
            if grid[y][x] == ".":
                d = (x - px) ** 2 + (y - py) ** 2
                if d < bd:
                    best, bd = (x, y), d
    return best


labels = {}
for n, x0, y0, x1, y1 in Q:
    labels[n] = snap_floor((x0 + x1) // 2, (y0 + y1) // 2)

walkable = {(x, y) for y in range(H) for x in range(W)
            if grid[y][x] in ".bPC"}
comp_of, comps = {}, []
for cell in sorted(walkable):
    if cell in comp_of:
        continue
    seen = {cell}; q2 = deque([cell])
    while q2:
        cx, cy = q2.popleft()
        for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
            if (nx, ny) in walkable and (nx, ny) not in seen:
                seen.add((nx, ny)); q2.append((nx, ny))
    for c in seen:
        comp_of[c] = len(comps)
    comps.append(seen)

seed_of = {}
for name, cell in labels.items():
    assert cell in comp_of, f"label {name} off floor {cell}"
    comp = comp_of[cell]
    assert comp not in seed_of, f"{name} shares a space with {seed_of[comp]}"
    seed_of[comp] = name
assert len(seed_of) == len(comps), (
    f"{len(comps) - len(seed_of)} unlabeled room(s)")
name_of = {i: n for i, n in seed_of.items()}

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


tree, seen_c = [], {comp_of[labels["spine_hall"]]}
queue = deque([comp_of[labels["spine_hall"]]])
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

# loop doors: circulation chains along each hold band
by_name = {name_of[c]: c for c in range(len(comps))}
LOOP_PAIRS = [("hold_up_fore", "hold_up_aft"), ("hold_dn_fore", "hold_dn_aft"),
              ("hold_top_fore", "hold_top_aft"), ("hold_bot_fore", "hold_bot_aft"),
              ("engineering", "hold_dn_fore"), ("command", "hold_up_aft")]
loop_doors = []
for a, b in LOOP_PAIRS:
    ca, cb = by_name[a], by_name[b]
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

spec = {
    "layout_id": "atlas_rooms",
    "reference": "Starsector Atlas superfreighter sprite (user-picked "
                 "freighter reference) -> trace -> blessed rect",
    "size": {"w": W, "h": H},
    "hull": {"spans": spans},
    "walls": True,
    "walls": segments,
    "labels": [{"name": n, "role": "", "at": list(labels[n])}
               for n in sorted(labels)],
    "doors": doors,
    # entry draft: breach through the aft hull below engineering;
    # the user's polish owns the final point
    "entry": {"breach": [2, 60], "spawn": [5, 60], "exit": [8, 60]},
    "console": {"pos": [285, 36]},
}
OUT.write_text(json.dumps(spec, indent=1))
print(f"wrote {OUT}: {len(comps)} rooms, {len(segments)} wall segs, "
      f"{len(doors)} doors")
