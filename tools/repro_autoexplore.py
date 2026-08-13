"""Headless repro for the two auto-explore bug reports.

Builds a real derelict layout (scout_a), inits fog, reveals at spawn,
then simulates the auto-explore loop (next_explore_step -> reveal)
until it would stop. Diagnostics:

  * whether walls adjacent to LOS get marked seen (bug 1),
  * when 'explored everything' fires: how many unseen cells remain
    and whether they are reachable under strict BFS rules vs a
    relaxed flood fill (bug 2 — cornering),
  * an ASCII fog frame around the player at the end.
"""
import sys
sys.path.insert(0, '.')
from collections import deque

from src.spacehack import world
from src.spacehack.dungeon import load_layout, init_fog, reveal_around
from src.spacehack.autoexplore import next_explore_step

_TRANSITION_KINDS = frozenset({"stairs_up", "stairs_down", "exit"})
_NEIGHBORS_8 = (
    (0, -1), (-1, 0), (1, 0), (0, 1),
    (-1, -1), (1, -1), (-1, 1), (1, 1),
)


def flood_unseen(game_map, start, *, allow_transitions):
    """Unseen cells reachable from ``start`` under given rules."""
    seen_unseen = set()
    queue = deque([(start.x, start.y)])
    visited = {(start.x, start.y)}
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in _NEIGHBORS_8:
            nx, ny = cx + dx, cy + dy
            if not game_map.in_bounds(nx, ny) or (nx, ny) in visited:
                continue
            tile = game_map.tiles[ny][nx]
            if tile.kind in _TRANSITION_KINDS and not allow_transitions:
                continue
            if not tile.walkable or game_map.blocking_entity_at(nx, ny):
                continue
            visited.add((nx, ny))
            if not game_map.seen[ny][nx]:
                seen_unseen.add((nx, ny))
            queue.append((nx, ny))
    return seen_unseen


def main():
    gm, spawn = load_layout("scout_a")
    init_fog(gm)
    player = world.Entity(char="@", fg=(255, 255, 255),
                          pos=spawn or world.Position(3, 9))
    reveal_around(gm, player.pos, radius=gm.sight_radius)
    print(f"map {gm.width}x{gm.height}, spawn {player.pos}")
    print(f"initial seen cells: {sum(1 for r in gm.seen for v in r if v)}")

    # Bug 1 probe: walls adjacent to the player's LOS — revealed?
    reveal_around(gm, player.pos, radius=gm.sight_radius)
    adj_walls = 0
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            nx, ny = player.pos.x + dx, player.pos.y + dy
            if not gm.in_bounds(nx, ny):
                continue
            if not gm.tiles[ny][nx].walkable and gm.seen[ny][nx]:
                adj_walls += 1
    print(f"non-walkable seen cells within 2 of spawn: {adj_walls}")

    steps = 0
    while steps < 500:
        step = next_explore_step(gm, player.pos)
        if step is None:
            break
        dx, dy = step
        player.pos = world.Position(player.pos.x + dx, player.pos.y + dy)
        reveal_around(gm, player.pos, radius=gm.sight_radius)
        steps += 1

    total = gm.width * gm.height
    unseen = sum(1 for r in gm.seen for v in r if not v)
    print(f"\nsteps taken: {steps}")
    print(f"player ended at {player.pos}")
    print(f"unseen cells remaining: {unseen} / {total}")

    strict = flood_unseen(gm, player.pos, allow_transitions=False)
    relaxed = flood_unseen(gm, player.pos, allow_transitions=True)
    print(f"unseen reachable (strict BFS rules): {len(strict)}")
    print(f"unseen reachable (relaxed, transitions passable): {len(relaxed)}")
    if relaxed and not strict:
        print(">>> CORNERED: transition-tile exclusion hides reachable unseen cells")
        print("    transitions near the frontier:")
        for x, y in sorted(relaxed)[:10]:
            print(f"    ({x},{y}) tile={gm.tiles[y][x].kind}")
    if not relaxed:
        print(">>> genuinely fully explored under relaxed rules")

    # ASCII fog frame around the player (seen=dim tile, unseen=space)
    print("\nASCII frame (40x14 around player; '.'=floor '#'=wall '?'=unseen '@'=player):")
    for y in range(player.pos.y - 7, player.pos.y + 7):
        row = ""
        for x in range(player.pos.x - 20, player.pos.x + 21):
            if not gm.in_bounds(x, y):
                row += " "
                continue
            if (x, y) == (player.pos.x, player.pos.y):
                row += "@"
            elif not gm.seen[y][x]:
                row += "?"
            elif gm.tiles[y][x].walkable:
                row += "."
            else:
                row += "#"
        print(row)


if __name__ == "__main__":
    main()
