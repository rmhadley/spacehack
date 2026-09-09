"""Content pass on the user-polished atlas deck -> freightliner_crew.

Reads layout_drafts/atlas_rooms.layout (the polished rooms+doors map,
untouched) and writes layout_drafts/freightliner_crew.layout with crew
and loot markers + ENEMY/LOOT/COLOUR directives appended. Consortium
crew per the hauler_crew precedent (merchant deck); scaled up for the
biggest deck in the corpus. Walls/doors/airlocks are never modified.
"""

from collections import deque

SRC = 'layout_drafts/atlas_rooms.layout'
OUT = 'layout_drafts/freightliner_crew.layout'

text = open(SRC).read()
i0 = text.index('MAP\n') + 4
i1 = text.index('ENDMAP\n')
rows = text[i0:i1].rstrip('\n').split('\n')
H, W = len(rows), max(len(r) for r in rows)
g = [list(r.ljust(W)) for r in rows]

floor = {(x, y) for y in range(H) for x in range(W)
         if g[y][x] == '.'}
comp_of, comps = {}, []
for cell in sorted(floor):
    if cell in comp_of:
        continue
    seen, q = {cell}, deque([cell])
    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
            if (nx, ny) in floor and (nx, ny) not in seen:
                seen.add((nx, ny)); q.append((nx, ny))
    for c in seen:
        comp_of[c] = len(comps)
    comps.append(seen)


def bbox(c):
    xs = [x for x, _ in c]
    ys = [y for _, y in c]
    return min(xs), min(ys), max(xs), max(ys), len(c)


def pick(pred, n):
    hits = [c for c in comps if pred(*bbox(c))]
    assert len(hits) == n, f'wanted {n}, got {len(hits)}: {[bbox(c) for c in hits]}'
    return hits


# --- room identification (structural, verified against the polished map) ---
spine     = pick(lambda a, b, c, d, n: n > 1500, 1)[0]
eng       = pick(lambda a, b, c, d, n: a < 45 and 500 < n < 700, 1)[0]
aft_holds = pick(lambda a, b, c, d, n: a <= 45 and 700 < n < 800, 2)
holds     = sorted(pick(lambda a, b, c, d, n: 550 < n < 650, 8),
                   key=lambda c: (bbox(c)[1] > 40, bbox(c)[0]))
quarters  = pick(lambda a, b, c, d, n: a < 45 and 350 < n < 400, 2)
cpos = next((x, y) for y in range(H) for x in range(W) if g[y][x] == 'C')
console = [c for c in comps
           if any(abs(x-cpos[0]) <= 1 and abs(y-cpos[1]) <= 1
                  for x, y in c)]
assert len(console) == 1
console = console[0]
wings     = pick(lambda a, b, c, d, n: 135 < n < 145 and (b < 20 or d > 50), 2)
bow_ends  = pick(lambda a, b, c, d, n: 135 < n < 145 and 25 < b < 47, 2)
approach  = pick(lambda a, b, c, d, n: 110 < n < 120, 2)
pods      = pick(lambda a, b, c, d, n: 35 < n < 42 and 28 < b and d < 44, 8)
seams     = pick(lambda a, b, c, d, n: n < 35 and (b < 10 or b > 62), 4)

used = set()
stamps = []


def place(glyph, comp, anchor=None):
    a0, b0, a1, b1, _ = bbox(comp)
    tx, ty = anchor or ((a0 + a1) // 2, (b0 + b1) // 2)

    def openish(p):
        x, y = p
        return all(0 <= y+dy < H and 0 <= x+dx < W
                   and g[y+dy][x+dx] == '.' for dx in (-1, 0, 1)
                   for dy in (-1, 0, 1))

    cands = sorted((p for p in comp if p not in used and g[p[1]][p[0]] == '.'),
                   key=lambda p: (p[0]-tx)**2 + (p[1]-ty)**2)
    for p in cands:
        if openish(p):
            used.add(p)
            stamps.append((glyph, *p))
            return
    assert cands, f'no free cell for {glyph!r} in {bbox(comp)}'
    p = cands[0]
    used.add(p)
    stamps.append((glyph, *p))


# --- crew: consortium honor guard + container-stack watches + vermin ---
place('n', console)                       # cockpit anchor @1.0
place('k', console)                       # second cockpit guard
for c in bow_ends:
    place('u', c)                         # bow watch officers
for c in wings:
    place('f', c)                         # wing gunners
place('j', approach[0])                   # approach corridor watch
place('f', spine, anchor=(70, 36))        # spine patrols, spread
place('f', spine, anchor=(210, 36))
place('g', spine, anchor=(140, 36))
place('q', spine, anchor=(255, 36))       # lone sentry drone
place('k', eng)                           # engineering watch
for c in quarters:
    place('h', c)                         # aft compartment sentries
for c in aft_holds:
    place('k', c)                         # aft hold guards
for c in holds[:6]:                       # container stack (skip the
    place('f' if bbox(c)[1] > 40 else 'k', c)  # two bow-nearest holds)
for c in (pods[0], pods[3], pods[5]):     # mid-band pod nests
    place('m', c)
place('o', pods[1])
for c in seams:                           # vermin in the hull seams
    place('m' if bbox(c)[0] < 100 else 'o', c)

# --- loot: the container stack pays in cargo ---
for c in aft_holds + holds:
    place('1', c)                         # cargo_bay across the stack
place('1', spine, anchor=(100, 36))
place('1', spine, anchor=(190, 36))
for c in (console, wings[0], bow_ends[0], quarters[0], quarters[1]):
    place('2', c)                         # personal_storage
place('3', eng, anchor=(20, 36))          # engine_room
place('3', eng, anchor=(35, 30))
place('4', spine, anchor=(60, 36))        # mess_hall
place('4', spine, anchor=(240, 36))

for glyph, x, y in stamps:
    assert g[y][x] == '.', (glyph, x, y)
    g[y][x] = glyph

directives = '''
# Crew — varied spawns: 30 stamps, 10 profiles. The cockpit honor
# guard is the guaranteed anchor; everything else rolls per visit.
ENEMY: n = consortium_enforcer@1.0#2-3
ENEMY: u = consortium_gunner@0.5#1-2
ENEMY: k = consortium_enforcer@0.45#1-2
ENEMY: f = consortium_gunner@0.45#1-2
ENEMY: g = consortium_gunner@0.4#1-2
ENEMY: j = consortium_enforcer@0.3#1-1
ENEMY: h = consortium_enforcer@0.35#1-1
ENEMY: m = hull_parasite@0.15#2-4
ENEMY: o = hull_parasite@0.2#1-2
ENEMY: q = sentry_drone@0.25#1-2

# Loot mappings — the container stack pays in cargo
LOOT: 1 = cargo_bay
LOOT: 2 = personal_storage
LOOT: 3 = engine_room
LOOT: 4 = mess_hall

# Color overrides
COLOUR: # = (120, 130, 150)
COLOUR: . = (200, 200, 210)
COLOUR: d = (100, 220, 255)
COLOUR: a = (100, 200, 255)
COLOUR: b = (200, 120, 90)
COLOUR: C = (255, 200, 80)
COLOUR: > = (100, 255, 120)
COLOUR: n = (220, 150, 80)
COLOUR: u = (200, 110, 80)
COLOUR: k = (220, 150, 80)
COLOUR: f = (200, 110, 80)
COLOUR: g = (200, 110, 80)
COLOUR: j = (220, 150, 80)
COLOUR: h = (220, 150, 80)
COLOUR: m = (175, 140, 190)
COLOUR: o = (175, 140, 190)
COLOUR: q = (150, 230, 255)
'''

header = ('# freightliner_crew.layout — atlas superfreighter deck '
          '(Starsector Atlas reference)\n'
          '# content pass on the user-polished atlas_rooms.layout; '
          'walls/doors never touched\n')
out = header + 'MAP\n' + '\n'.join(''.join(r) for r in g) + '\nENDMAP\n'
tile = ('# Tile mappings\n'
        'TILE: # = DUNGEON_WALL\nTILE: . = DUNGEON_FLOOR\n'
        'TILE: d = DUNGEON_DOOR\nTILE: a = AIRLOCK\n'
        'TILE: b = BREACH\nTILE: > = EXIT\n')
open(OUT, 'w').write(out + tile + directives)
print(f'wrote {OUT}: {len(stamps)} markers '
      f'({sum(1 for s in stamps if not s[0].isdigit())} crew, '
      f'{sum(1 for s in stamps if s[0].isdigit())} loot)')
