#!/usr/bin/env python3
"""Generate survey_a.layout from a script-drawn ship silhouette.

Silhouette-first (the profile IS the design): boundary curves define the
hull, anatomical blocks add nacelles/mast/bridge/pod, then the interior
is carved into rooms by anatomy. The art is SOLID '#' — the carvable
interior is the buried mass (a '#' with '#' on all four rays); the
outer skin stays wall and the void outside the silhouette is emitted as
VOID tiles so the hull outline reads in game. Every marker is
BFS-validated reachable from the player spawn before the file is
written. Regenerate with:
    python3 tools/gen_survey_layout.py
"""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

W, H = 92, 34
SKIN = frozenset("#")


def hull_top(x: int) -> int:
    if x < 8:
        return 12
    if x < 16:
        return 12 - (x - 8) // 2
    if x < 22:
        return 8
    if x < 56:
        return 6
    if x < 68:
        return 6 + (x - 56) // 4
    if x < 80:
        return 8 + (x - 68) // 3
    return 12 + (x - 80)


def hull_bot(x: int) -> int:
    if x < 8:
        return 21
    if x < 16:
        return 21 + (x - 8) // 2
    if x < 22:
        return 25
    if x < 56:
        return 27
    if x < 68:
        return 27 + (x - 56) // 4
    if x < 80:
        return 25 - (x - 68) // 3
    return 21 - (x - 80)


def silhouette() -> list[list[str]]:
    g = [[" "] * W for _ in range(H)]

    def fill(x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                g[y][x] = "#"

    for x in range(4, 86):
        for y in range(hull_top(x), hull_bot(x) + 1):
            g[y][x] = "#"
    fill(60, 2, 66, 5)                  # bridge canopy, lower step
    fill(66, 3, 71, 5)                  # bridge canopy, upper step
    fill(46, 0, 49, 1)                  # mast spire cap
    fill(44, 2, 51, 5)                  # mast tower (hollow base)
    fill(42, 2, 51, 2)                  # upper dish arm
    fill(41, 4, 53, 4)                  # lower dish arm
    for x in range(30, 49):            # ventral galley pod
        depth = 3 if 33 <= x <= 45 else 2
        for y in range(1, depth + 1):
            g[hull_bot(x) + y][x] = "#"
    for n_lo, n_hi in ((9, 12), (20, 23)):   # twin engine nacelles
        fill(2, n_lo, 9, n_hi)
        fill(1, n_lo + 1, 1, n_hi - 1)
        fill(0, n_lo, 0, n_hi)
        fill(10, (n_lo + n_hi) // 2, 13, (n_lo + n_hi) // 2)
    g[16][87] = "#"; g[16][88] = "#"    # nose spar (art already [y][x])
    return g


def buried_mass(art: list[list[str]]) -> list[list[bool]]:
    """Carvable interior = BURIED '#' cells (all four rays hit '#')."""
    def ray_skin(x, y, dx, dy):
        while True:
            x += dx; y += dy
            if not (0 <= x < W and 0 <= y < H):
                return False
            if art[y][x] in SKIN:
                return True

    mass = [[False] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if art[y][x] in SKIN:
                mass[y][x] = all((
                    ray_skin(x, y, 1, 0), ray_skin(x, y, -1, 0),
                    ray_skin(x, y, 0, 1), ray_skin(x, y, 0, -1),
                ))
    return mass


def main() -> int:
    art = silhouette()
    mass = buried_mass(art)
    g = [
        ["#" if (art[y][x] in SKIN or mass[y][x]) else "v" for x in range(W)]
        for y in range(H)
    ]

    def carve(x0, y0, x1, y1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                assert mass[y][x], ("carving skin/void", x, y)
                g[y][x] = "."

    # --- Rooms by anatomy (strictly between walls) ----------------------
    carve(3, 10, 8, 11)     # upper nacelle: engine room
    carve(3, 21, 8, 22)     # lower nacelle: fuel bay
    carve(24, 8, 52, 14)    # chart room (the wide beam's heart)
    carve(58, 8, 68, 13)    # recorder vault, behind the bridge
    carve(74, 13, 80, 18)   # cockpit, inside the nose taper
    carve(34, 28, 44, 28)   # galley, in the pod's deep rows
    carve(45, 3, 50, 4)     # sensor gallery, inside the mast tower
    carve(61, 3, 65, 4)     # bridge, above the vault

    # --- Spine + connectors + doors -------------------------------------
    SPINE = 18
    for x in range(4, 80):
        if mass[SPINE][x]:
            g[SPINE][x] = "."
    for x0, y0, y1 in (
        (5, 13, 19), (12, 15, 17), (38, 15, 28), (63, 14, 17), (78, 17, 17),
        (47, 5, 7),           # mast gallery down through the crown
        (18, 19, 24),          # breach shaft up to the spine
        (30, 7, 17),          # airlock shaft down from the crown
    ):
        for y in range(y0, y1 + 1):
            if mass[y][x0]:
                g[y][x0] = "."
    g[SPINE][9] = "d"    # nacelle bay gate
    g[12][5] = "d"     # engine room drop shaft
    g[20][5] = "d"     # fuel bay riser
    g[SPINE][23] = "d"   # chart room gate
    g[SPINE][69] = "d"   # vault gate
    g[SPINE][78] = "d"   # cockpit gate
    g[27][38] = "d"      # galley hatch
    g[5][47] = "d"       # mast tower door
    g[7][63] = "d"       # bridge ladder
    g[10][2] = "E"; g[11][2] = "E"    # engines in the stern walls
    g[21][2] = "E"; g[22][2] = "E"

    # Airlock collar in the crown wall, opening into the dorsal shaft
    g[hull_top(30)][30] = "a"
    g[hull_top(31)][31] = "a"

    # Breach entry: hole through the hull floor, stub below in the void
    bx = 18
    g[hull_bot(bx)][bx] = "b"
    g[hull_bot(bx) + 1][bx] = "P"
    g[hull_bot(bx) + 2][bx] = ">"

    # --- Role markers ----------------------------------------------------
    for x, y, ch in (
        (5, 10, "1"),                        # engine room salvage
        (5, 21, "4"),                        # fuel bay cargo
        (28, 9, "3"), (48, 13, "3"),        # survey lockers, chart room
        (30, 10, "g"), (44, 12, "g"),       # gunners HOLD the chart room
        (14, 18, "c"), (55, 18, "c"),      # enforcers patrol the spine
        (60, 9, "S"), (66, 12, "S"),        # vault guard pair
        (36, 28, "2"), (42, 28, "2"),      # galley stores
        (46, 3, "m"), (49, 4, "m"),         # parasites in the mast
        (77, 15, "C"),                      # cockpit console
    ):
        assert g[y][x] == ".", (x, y, g[y][x])
        g[y][x] = ch

    # --- Validate: every marker reachable from P --------------------------
    walk = frozenset(".da>bPCE1234cgmS")   # 'v' void is NOT walkable
    start = (18, hull_bot(18) + 1)
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                n = (x + dx, y + dy)
                if n in seen or not (0 <= n[0] < W and 0 <= n[1] < H):
                    continue
                if g[n[1]][n[0]] in walk:
                    seen.add(n)
                    q.append(n)
    need = [(x, y) for y in range(H) for x in range(W) if g[y][x] in "1234cgmSCE>"]
    missing = [p for p in need if p not in seen]
    assert not missing, f"unreachable markers: {missing}"

    out = Path(__file__).resolve().parents[1] / "src/spacehack/data/layouts/survey_a.layout"
    head = """# survey_a.layout — Survey Ship Interior (generated)
#
# GENERATED by tools/gen_survey_layout.py — edit the script, not the
# map. Silhouette-first: hull boundary curves + anatomical blocks
# (twin nacelles, dorsal sensor mast, stepped bridge, ventral galley
# pod, nose light), then the interior carved by anatomy. The consortium
# boarding crew works this wreck: gunners HOLD the chart room, enforcers
# patrol the spine, a guard pair holds the recorder vault, parasites
# nest in the sensor mast. Entry: ventral breach (b) at the stern.
# 'v' tiles are VOID outside the hull; the skin between void and rooms
# reads as the ship's silhouette.

MAP
"""
    tail = '''
ENDMAP

# Tile mappings — glyph -> world.Tile constant name
TILE: # = DUNGEON_WALL
TILE: . = DUNGEON_FLOOR
TILE: d = DUNGEON_DOOR
TILE: a = AIRLOCK
TILE: b = BREACH
TILE: > = EXIT
TILE: v = VOID
TILE: { = HULL_WALL
TILE: } = HULL_WALL
TILE: % = DEBRIS

# Enemy spawn markers — the consortium boarding crew, not generic
# pirates (the chain's antagonist, working the wreck they attacked for).
ENEMY: c = consortium_enforcer@0.7#1-2
ENEMY: g = consortium_gunner@1.0#2-3
ENEMY: S = consortium_enforcer@1.0#2-2
ENEMY: m = hull_parasite@0.35#2-5

# Loot mappings
LOOT: 1 = engine_room
LOOT: 2 = mess_hall
LOOT: 3 = personal_storage
LOOT: 4 = cargo_bay

# Color overrides — civilian survey hull, pale grey-white over navy
COLOUR: # = (140, 145, 150)     # hull/bulkhead — pale civilian grey
COLOUR: { = (140, 145, 150)     # hull bracket — LOS-transparent skin
COLOUR: } = (140, 145, 150)     # hull bracket
COLOUR: . = (205, 205, 200)     # floor — off-white decking
COLOUR: a = (100, 200, 255)     # airlock — cool blue
COLOUR: b = (255, 120, 50)      # breach — hot orange (cut edge)
COLOUR: d = (100, 220, 255)     # door — cyan glow
COLOUR: C = (255, 200, 80)      # cockpit computer — warm gold
COLOUR: E = (180, 200, 220)     # engine — muted blue-white
COLOUR: > = (100, 255, 120)     # exit — bright green arrow
COLOUR: c = (120, 160, 220)     # consortium enforcer — corporate blue
COLOUR: g = (150, 190, 255)     # consortium gunner — pale corporate
COLOUR: m = (175, 140, 190)     # hull parasite — sickly mauve
'''
    body = "\n".join("".join(row) for row in g)
    out.write_text(head + body + tail, encoding="utf-8")
    print(f"wrote {out} ({W}x{H}, {len(need)} markers, all reachable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
