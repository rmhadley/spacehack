"""Diagnose the two auto-explore bug reports against the user's real
autosave: why 'explored everything' fires while the map shows more,
and why boundary walls are not revealed.
"""
import json
import sys
sys.path.insert(0, '.')
from collections import Counter, deque

from src.spacehack import world
from src.spacehack.dungeon import reveal_around
from src.spacehack.saveload import _dungeon_from_dict
from src.spacehack.autoexplore import next_explore_step

_TRANSITION_KINDS = frozenset({"stairs_up", "stairs_down", "exit"})
_NEIGHBORS_8 = (
    (0, -1), (-1, 0), (1, 0), (0, 1),
    (-1, -1), (1, -1), (-1, 1), (1, 1),
)


def flood_unseen(game_map, start, *, allow_transitions):
    """Unseen cells reachable from ``start`` under given rules."""
    reach = set()
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
                reach.add((nx, ny))
            queue.append((nx, ny))
    return reach


def main():
    save = json.load(open("autosave.json"))
    dd = save["dungeon"]
    gm, _ = _dungeon_from_dict(dd)
    gm.seen = [list(row) for row in dd["seen"]]
    gm.visible = [[False] * gm.width for _ in range(gm.height)]
    player = world.Entity(char="@", fg=(255, 255, 255),
                          pos=world.Position(save["player_pos_x"],
                                             save["player_pos_y"]))
    reveal_around(gm, player.pos, radius=gm.sight_radius)

    print(f"map {gm.width}x{gm.height} '{dd.get('location_name')}' "
          f"sight_radius={gm.sight_radius}")
    print(f"player at {player.pos} (entry {dd.get('entry_spawn')})")

    # --- Bug 2: does the BFS say there is nothing to explore? ---
    step = next_explore_step(gm, player.pos)
    print(f"next_explore_step from player: {step}")
    unseen_total = sum(1 for row in gm.seen for v in row if not v)
    print(f"unseen cells total: {unseen_total} / {gm.width * gm.height}")

    strict = flood_unseen(gm, player.pos, allow_transitions=False)
    relaxed = flood_unseen(gm, player.pos, allow_transitions=True)
    print(f"unseen reachable (strict): {len(strict)}")
    print(f"unseen reachable (relaxed): {len(relaxed)}")

    # --- Simulate the FIXED walk: does it explore into the fog and
    # reveal the boundary walls? (BFS + reveal_around loop.) ---
    if step is not None:
        walker = world.Entity(char="@", fg=(255, 255, 255), pos=player.pos)
        walked = 0
        while walked < 3000:
            s = next_explore_step(gm, walker.pos)
            if s is None:
                break
            walker.pos = world.Position(walker.pos.x + s[0], walker.pos.y + s[1])
            reveal_around(gm, walker.pos, radius=gm.sight_radius)
            walked += 1
        unseen_after = sum(1 for row in gm.seen for v in row if not v)
        # Boundary walls: unseen non-walkable cells adjacent to seen
        # walkable cells (the fog-edge walls the run must reveal).
        edge_walls = 0
        for y in range(gm.height):
            for x in range(gm.width):
                if not gm.seen[y][x] or not gm.tiles[y][x].walkable:
                    continue
                for dx, dy in _NEIGHBORS_8:
                    nx, ny = x + dx, y + dy
                    if (gm.in_bounds(nx, ny) and not gm.seen[ny][nx]
                            and not gm.tiles[ny][nx].walkable):
                        edge_walls += 1
                        break
        print(f"\nFIXED walk: {walked} steps, ends at {walker.pos}")
        print(f"unseen cells after: {unseen_after} / {gm.width * gm.height}")
        print(f"unseen boundary walls still adjacent to seen floor: {edge_walls}")

    # --- Bug 1: what kind of unseen cells border the seen region? ---
    boundary = Counter()
    examples = {}
    for y in range(gm.height):
        for x in range(gm.width):
            if not gm.seen[y][x] or not gm.tiles[y][x].walkable:
                continue
            for dx, dy in _NEIGHBORS_8:
                nx, ny = x + dx, y + dy
                if not gm.in_bounds(nx, ny) or gm.seen[ny][nx]:
                    continue
                kind = gm.tiles[ny][nx].kind
                boundary[kind] += 1
                if kind not in examples:
                    examples[kind] = (nx, ny)
    print("\nunseen neighbors of seen walkable cells, by kind:")
    for kind, n in boundary.most_common():
        print(f"  {kind}: {n}  e.g. {examples[kind]}")

    # --- ASCII seen-grid around the player ---
    print("\nASCII frame (46x16; '.'=seen floor '#'=seen wall '?'=unseen '@'=player):")
    for y in range(player.pos.y - 8, player.pos.y + 8):
        row = ""
        for x in range(player.pos.x - 23, player.pos.x + 23):
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
        print(f"  {row}")


if __name__ == "__main__":
    main()
