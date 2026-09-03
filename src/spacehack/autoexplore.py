"""DCSS-style auto-explore (``O``) and go-to (``G``) for dungeon mode.

Press ``O`` inside a derelict or dungeon to walk the player through
unrevealed tiles until:

* something interesting comes into sight (stairs, the exit, a ship
  computer, a cache of supplies, a quest NPC),
* a hostile comes into view (the shared ground-combat tick starts the
  fight and auto-explore stops), or
* the player presses any key to cancel.

Press ``G`` to pick a *discovered* destination (stairs, the exit, a
ship computer, a quest console/door, an NPC) and auto-walk to it with
the same step machinery — stopping at newly-visible interesting
content, when combat starts, or on any keypress. The walker stops
8-adjacent to the target, never on top of it.

Only *newly revealed* interesting content stops the run — things
already in view when ``O``/``G`` is pressed are seeded into the known
set so a single press never stalls next to loot the player already
spotted.

An entity the player cannot currently see never seals the route:
pathing treats solid entities outside the current LOS frame as
passable, so a monster camping a doorway in the dark is revealed by
walking toward it (the shared tick then starts LOS-based ground
combat). Only visible solid entities block — and if one sits in the
only exit, the run stops with ``A <name> blocks the only way
forward.``

The decision helpers (``interesting_at``, ``newly_interesting_positions``,
``next_explore_step``) are pure and testable without Pygame; the thin
``run_auto_explore`` loop owns presentation + interruption, mirroring
``navigation._run_goto``'s step-and-poll pattern. ``post_step_tick``
and ``present_frame`` are injected so tests run headless.
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from . import world
from .animation_timing import AUTO_EXPLORE

# ---------------------------------------------------------------------------
# Interesting content
# ---------------------------------------------------------------------------

# Tiles the player should decide about themselves: auto-explore never
# steps onto them and never routes through them, so the run ends
# beside them. Derived from ``_TILE_LABELS`` so the two tables cannot
# drift apart.
#
# NOTE: ``breach`` is deliberately NOT here. In derelict layouts the
# entry shaft the player spawns in is made of walkable ``breach``
# tiles — excluding them sealed the player at spawn (auto-explore
# reported 'everything explored' while the whole ship was dark). The
# leave-transition is the ``exit`` tile; breach tiles are ordinary
# passable floor.
_TILE_LABELS = {
    "stairs_up": "a stairway up",
    "stairs_down": "a stairway down",
    "exit": "the exit",
}
_TRANSITION_KINDS = frozenset(_TILE_LABELS)

# Entity flags that should stop auto-explore, with a short label for
# the stop message. Table-driven per the state-tables guardrail.
_ENTITY_INTEREST_FLAGS = (
    ("loot_data", "a cache of supplies"),
    ("computer_terminal", "a ship computer"),
    ("main_quest_console", "a strange console"),
    ("main_quest_door", "a sealed door"),
    # Extension interactions (the prison's engineering console and
    # data terminal, future cave/station consoles) — GOTO could target
    # them but auto-explore never stopped for them (playtest v4).
    ("dungeon_interaction", "an interactive console"),
    ("npc_id", "someone"),
)

# ---------------------------------------------------------------------------
# Go-to targets (the G key)
# ---------------------------------------------------------------------------

# Discovered destinations for the GO TO picker, keyed like the
# interesting-content tables above (tile kind / entity flag -> picker
# title). Loot caches are deliberately absent: O handles pickup, and a
# dungeon can hold twenty caches — the picker would drown in them.
_GOTO_TILE_TITLES = {
    "stairs_up": "Stairs up",
    "stairs_down": "Stairs down",
    "exit": "Exit",
}
_GOTO_ENTITY_TITLES = {
    "computer_terminal": "Ship computer",
    "main_quest_console": "Quest console",
    "main_quest_door": "Sealed door",
    "npc_id": "NPC",
    "dungeon_interaction": "Console",
}


@dataclass(frozen=True)
class GotoTarget:
    """One discovered goto destination.

    ``title`` is the picker row; ``label`` is the prose form used in
    log messages (resolved via :func:`interesting_at`, the single
    source of prose truth); ``description`` feeds the picker hint.
    """

    title: str
    label: str
    x: int
    y: int
    description: str = "Walk to this destination."


def _add_entity_goto_titles(game_map, seen, found) -> None:
    """Merge seen interactable entities into the goto target map.

    Interactions sit ON their connection tile by design (the deep
    elevator occupies the down-stair cell it gates) — the interaction's
    own name is the truth and OVERRIDES the tile title ("Deep
    Elevator", not "Stairs down"). Other entity flags only fill
    otherwise-untitled cells.
    """
    for entity in game_map.entities:
        if not seen[entity.pos.y][entity.pos.x]:
            continue
        if getattr(entity, "dungeon_interaction", ""):
            found[(entity.pos.x, entity.pos.y)] = entity.name or "Console"
            continue
        for _flag, _title in _GOTO_ENTITY_TITLES.items():
            if getattr(entity, _flag, None):
                found.setdefault((entity.pos.x, entity.pos.y), _title)
                break


def goto_targets(game_map, player_pos) -> list[GotoTarget]:
    """Discovered (seen) goto destinations, nearest first.

    Transition tiles (stairs/exit) plus interactable entities
    (computers, quest consoles/doors, NPCs, interaction tiles) whose
    cells are in the player's seen memory. Loot caches are excluded
    (auto-explore handles pickup). Returns ``[]`` without a fog grid.
    """
    _seen = game_map.seen
    if _seen is None:
        return []
    _found: dict[tuple[int, int], str] = {}
    for _y, _row in enumerate(_seen):
        for _x, _on in enumerate(_row):
            if not _on:
                continue
            _title = _GOTO_TILE_TITLES.get(game_map.tiles[_y][_x].kind)
            if _title is not None:
                _found[(_x, _y)] = _title
    _add_entity_goto_titles(game_map, _seen, _found)
    _sx, _sy = player_pos.x, player_pos.y
    _targets = [
        GotoTarget(
            title=_title,
            label=interesting_at(game_map, _x, _y) or _title,
            x=_x,
            y=_y,
        )
        for (_x, _y), _title in _found.items()
    ]
    _targets.sort(key=lambda _t: max(abs(_t.x - _sx), abs(_t.y - _sy)))
    return _targets

_NEIGHBORS_8 = (
    (0, -1), (-1, 0), (1, 0), (0, 1),
    (-1, -1), (1, -1), (-1, 1), (1, 1),
)


def interesting_at(game_map, x: int, y: int) -> str | None:
    """Return a short label for interesting content at ``(x, y)``, else
    ``None``.

    Interesting = transition tiles (stairs/exit) plus interactable
    or loot entities (terminals, quest NPCs, supply caches).
    """
    if not game_map.in_bounds(x, y):
        return None
    _label = _TILE_LABELS.get(game_map.tiles[y][x].kind)
    if _label is not None:
        return _label
    for _e in game_map.entities:
        if not (_e.pos.x <= x < _e.pos.x + _e.width):
            continue
        if not (_e.pos.y <= y < _e.pos.y + _e.height):
            continue
        for _flag, _elabel in _ENTITY_INTEREST_FLAGS:
            if getattr(_e, _flag, None):
                return _elabel
    return None


def newly_interesting_positions(
    game_map,
    known: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """Interesting cells in the current LOS frame not already in
    ``known``.

    Scans ``game_map.visible``, so only content actually on screen
    counts. Returns an empty set when the map has no fog grid.
    """
    _visible = game_map.visible
    if _visible is None:
        return set()
    _fresh: set[tuple[int, int]] = set()
    for _y, _row in enumerate(_visible):
        for _x, _on in enumerate(_row):
            if not _on or (_x, _y) in known:
                continue
            if interesting_at(game_map, _x, _y):
                _fresh.add((_x, _y))
    return _fresh


def _ignored_positions(game_map) -> set[tuple[int, int]]:
    """Return the map-owned memory of interesting cells already presented."""
    _memory = getattr(game_map, "autoexplore_ignored", None)
    if _memory is None:
        _memory = set()
        game_map.autoexplore_ignored = _memory
    return _memory


def _seed_known_interesting(game_map) -> set[tuple[int, int]]:
    """Merge persistent memory with interesting content currently in view."""
    _known = set(_ignored_positions(game_map))
    _fresh = newly_interesting_positions(game_map, _known)
    _ignored_positions(game_map).update(_fresh)
    _known.update(_fresh)
    return _known


def _remember_fresh(game_map, known, fresh: set[tuple[int, int]]) -> None:
    """Persist newly presented content and keep the current walk's set aligned."""
    if not fresh:
        return
    _ignored_positions(game_map).update(fresh)
    known.update(fresh)


# ---------------------------------------------------------------------------
# Step planning
# ---------------------------------------------------------------------------


def _first_step_toward(_prev, _sx: int, _sy: int, _tx: int, _ty: int) -> tuple[int, int]:
    """Walk the BFS parent chain back to the first step from the start."""
    _cur = (_tx, _ty)
    while _prev[_cur] != (_sx, _sy):
        _cur = _prev[_cur]
    return (_cur[0] - _sx, _cur[1] - _sy)


def _adjacent(pos, tx: int, ty: int) -> bool:
    """Chebyshev adjacency — within one cell of ``(tx, ty)``."""
    return max(abs(pos.x - tx), abs(pos.y - ty)) <= 1


def _visible_blocker(game_map, x: int, y: int, *, exclude=None):
    """Blocking entity at ``(x, y)`` the player can currently see, else
    ``None``.

    The player only knows about entities rendered in the current LOS
    frame. An enemy standing in a dark corridor cannot seal the route:
    auto-explore walks toward it and combat starts the moment it comes
    into view (ground combat is LOS-based). ``exclude`` skips one
    entity (used when re-flooding from a blocker's own cell).

    Note the asymmetry with the main BFS: a missing ``seen`` grid
    aborts planning entirely, while a missing ``visible`` grid falls
    back to *passable* here — ``run_auto_explore`` guards both grids,
    so this only ever fires in synthetic states.
    """
    _ent = game_map.blocking_entity_at(x, y, exclude=exclude)
    if _ent is None:
        return None
    if getattr(_ent, "powered_down", False):
        # Dormant security never moves and never triggers the
        # reveal-then-fight flow, so "walk toward it to reveal it"
        # oscillates forever. It seals routes permanently — placement
        # invariants guarantee it strands nothing (doc 30).
        return _ent
    _visible = game_map.visible
    if _visible is not None and _visible[y][x]:
        return _ent
    return None


def _bfs_goal_step(prev, start, current, target):
    """Return the first step when a goto BFS reaches its goal ring."""
    if target is None or current == start:
        return None
    if max(abs(current[0] - target[0]), abs(current[1] - target[1])) > 1:
        return None
    return _first_step_toward(prev, start[0], start[1], *current)


def _visit_bfs_neighbors(
    game_map, current, start, target, seen, prev, visited, queue, blockers,
    blocker_ids,
):
    """Visit one BFS cell and return a step when it reaches a goal."""
    _cx, _cy = current
    for _dx, _dy in _NEIGHBORS_8:
        _nx, _ny = _cx + _dx, _cy + _dy
        if not game_map.in_bounds(_nx, _ny) or (_nx, _ny) in visited:
            continue
        _tile = game_map.tiles[_ny][_nx]
        if not _tile.walkable or _tile.kind in _TRANSITION_KINDS:
            if target is None and not seen[_ny][_nx] and current != start:
                return _first_step_toward(
                    prev, start[0], start[1], current[0], current[1],
                )
            continue
        _ent = _visible_blocker(game_map, _nx, _ny)
        if _ent is not None:
            if target is None and id(_ent) not in blocker_ids:
                blocker_ids.add(id(_ent))
                blockers.append(_ent)
            continue
        visited.add((_nx, _ny))
        prev[(_nx, _ny)] = current
        if target is None and not seen[_ny][_nx]:
            return _first_step_toward(prev, *start, _nx, _ny)
        queue.append((_nx, _ny))
    return None


def _bfs_step(game_map, start, target):
    """Run the shared explore/goto BFS and return its step plus blockers."""
    _seen = game_map.seen
    _prev = {}
    _queue = deque([start])
    _visited = {start}
    _blockers = []
    _blocker_ids = set()
    while _queue:
        _current = _queue.popleft()
        _goal = _bfs_goal_step(_prev, start, _current, target)
        if _goal is not None:
            return _goal, _blockers
        _step = _visit_bfs_neighbors(
            game_map, _current, start, target, _seen, _prev, _visited,
            _queue, _blockers, _blocker_ids,
        )
        if _step is not None:
            return _step, _blockers
    return None, _blockers


def _plan_step(game_map, player_pos, *, target=None):
    """Return the first shared-BFS step and visible blockers."""
    if game_map.seen is None:
        return None, ()
    _start = (player_pos.x, player_pos.y)
    if not game_map.in_bounds(*_start):
        return None, ()
    return _bfs_step(game_map, _start, target)


def next_explore_step(game_map, player_pos) -> tuple[int, int] | None:
    """First step toward the nearest unrevealed cell, or ``None``.

    BFS over passable cells (walkable, unblocked by solid entities
    the player can SEE — loot never blocks, and an entity outside the
    current LOS frame cannot seal the route because walking toward it
    reveals it). The target is any UNSEEN cell — floor, wall, or
    transition — so the run advances to the fog edge and reveals it: a
    room's boundary walls sit just beyond LOS and must be walked up
    to, otherwise the run reports 'everything explored' while the map
    is still dark. Transition tiles (stairs/exit) are never stepped
    on, but an unseen one is walked toward so it can be spotted.
    Returns ``(dx, dy)`` relative to ``player_pos``.

    ``None`` means every reachable cell, and every cell adjacent to
    the explored region, has been revealed.
    """
    _step, _ = _plan_step(game_map, player_pos)
    return _step


def next_goto_step(game_map, player_pos, tx: int, ty: int) -> tuple[int, int] | None:
    """First step toward a cell adjacent to ``(tx, ty)``, or ``None``.

    Goto mode of the shared BFS: same passability as auto-explore
    (visible solid entities seal, unseen ones are walked through and
    revealed, transitions are never entered — the walker always stops
    BESIDE a stairway or console). ``None`` means the player is
    already adjacent (the caller announces arrival) or no path exists.
    """
    if _adjacent(player_pos, tx, ty):
        return None
    _step, _ = _plan_step(game_map, player_pos, target=(tx, ty))
    return _step


def _flood_opens_unseen(game_map, x: int, y: int, *, exclude) -> bool:
    """True if flooding from ``(x, y)`` (treating ``exclude`` as
    passable) reaches at least one unseen cell.

    Models the question "if this entity were not standing there, could
    the player reach unexplored territory?" — the test that separates
    a genuine way-blocker from an incidental visible entity inside a
    wall-sealed room.
    """
    _seen = game_map.seen
    if _seen is None:
        return False
    _queue: deque[tuple[int, int]] = deque([(x, y)])
    _visited: set[tuple[int, int]] = {(x, y)}
    while _queue:
        _cx, _cy = _queue.popleft()
        for _dx, _dy in _NEIGHBORS_8:
            _nx, _ny = _cx + _dx, _cy + _dy
            if not game_map.in_bounds(_nx, _ny) or (_nx, _ny) in _visited:
                continue
            _tile = game_map.tiles[_ny][_nx]
            if not _tile.walkable or _tile.kind in _TRANSITION_KINDS:
                continue
            if _visible_blocker(game_map, _nx, _ny, exclude=exclude):
                continue
            _visited.add((_nx, _ny))
            if not _seen[_ny][_nx]:
                return True
            _queue.append((_nx, _ny))
    return False


def blocking_way_entity(game_map, player_pos):
    """Visible blocking entity sealing the only route to unseen
    territory, or ``None``.

    Called when ``next_explore_step`` returns ``None``: a visible
    entity may still be standing in the region's only exit (e.g. a
    monster camped in a doorway the player can see). Returns the
    nearest such entity whose own cell, if passable, floods to at
    least one unseen cell — a wall-sealed room with an incidental
    terminal inside does not qualify.
    """
    _step, _blockers = _plan_step(game_map, player_pos)
    if _step is not None:
        return None
    for _ent in _blockers:
        _bx, _by = _ent.pos.x, _ent.pos.y
        if not game_map.in_bounds(_bx, _by):
            continue
        if not game_map.tiles[_by][_bx].walkable:
            continue  # embedded in a wall — not a passage
        if _flood_opens_unseen(game_map, _bx, _by, exclude=_ent):
            return _ent
    return None


def _blocker_label(_e) -> str | None:
    """Display name for a blocking entity, lowercased for log prose."""
    if getattr(_e, "npc_char_id", ""):
        try:
            from .data.npc_chars import find_npc_char
            return find_npc_char(_e.npc_char_id).name.lower()
        except (ImportError, KeyError):
            pass
    return _e.name or None


# ---------------------------------------------------------------------------
# The auto-explore loop
# ---------------------------------------------------------------------------


def _default_present_frame(ctx, console, game_map, *, map_w, map_h, location) -> None:
    """Render one dungeon frame with the shared Pygame overlay —
    identical camera + viewport handling to the main loop's dungeon
    branch.

    Note: centers on ``ctx.player``, which the loop mutates in place
    via its ``player`` parameter — the caller must keep them the same
    object (``__main__`` does), or pass ``present_frame`` explicitly.
    """
    from . import pygame_overlay
    from .engine import SCREEN_HEIGHT, SCREEN_WIDTH

    cam_x, cam_y, rx, ry = world.camera_for_view(
        game_map, ctx.player.pos, region_w=map_w, region_h=map_h,
    )
    console.clear()
    world.render_world_view(
        console, game_map,
        region_x=rx, region_y=ry, region_w=map_w, region_h=map_h,
        camera_x=cam_x, camera_y=cam_y,
    )
    pygame_overlay.present_exploration(
        ctx,
        console,
        mode="dungeon",
        location=location,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        hud_view_height=map_h,
    )


def _poll_cancel_window(ctx) -> bool:
    """True if any keydown arrives during the per-step delay window."""
    _end = time.monotonic() + AUTO_EXPLORE
    while time.monotonic() < _end:
        for _ev in ctx.context.events():
            if getattr(_ev, "kind", "") == "keydown":
                return True
    return False


def _step_present_poll_move(
    ctx,
    console,
    game_map,
    player,
    present,
    map_w: int,
    map_h: int,
    location: str,
    dx: int,
    dy: int,
    post_step_tick,
) -> str | None:
    """One auto-walk step shared by auto-explore and go-to: present the
    frame, poll the cancel window (any keydown aborts; the key is
    swallowed, like ``_run_goto``), move the player, then run the
    post-step tick.

    Returns ``"CANCELLED"`` / ``"DEFEAT"`` / ``"COMBAT"`` or ``None``
    (no stop). ``post_step_tick`` MUST refresh the LOS/visible frame.
    """
    present(ctx, console, game_map, map_w=map_w, map_h=map_h, location=location)
    if _poll_cancel_window(ctx):
        return "CANCELLED"
    player.pos = world.Position(player.pos.x + dx, player.pos.y + dy)
    return post_step_tick(ctx, console, game_map)


def _stop_if_fresh(ctx, game_map, known) -> str | None:
    """Log the first newly-visible interesting sighting and return
    ``"DONE"``, or ``None`` when nothing fresh is on screen.

    Shared by auto-explore and go-to: both walks interrupt on content
    that just came into view (the currently-visible set is seeded into
    ``known`` before the loop).
    """
    _fresh = newly_interesting_positions(game_map, known)
    if _fresh:
        _remember_fresh(game_map, known, _fresh)
        _fx, _fy = min(_fresh)
        _label = interesting_at(game_map, _fx, _fy)
        ctx.log.add(f"You notice {_label} and stop.")
        return "DONE"
    return None


def _explore_finish(ctx, game_map, player):
    """Return a terminal result when exploration has no next step."""
    _blocker = blocking_way_entity(game_map, player.pos)
    if _blocker is not None:
        _label = _blocker_label(_blocker)
        ctx.log.add(
            f"A {_label} blocks the only way forward."
            if _label else "Something blocks the only way forward."
        )
    else:
        ctx.log.add("You have explored every reachable area.")
    return "DONE"


def _run_explore_loop(
    ctx, console, game_map, player, present, post_step_tick,
    map_w, map_h, location, known,
):
    """Walk until memory, combat, cancellation, or exhaustion stops us."""
    while True:
        if _stop_if_fresh(ctx, game_map, known) is not None:
            return "DONE"
        _step = next_explore_step(game_map, player.pos)
        if _step is None:
            return _explore_finish(ctx, game_map, player)
        _ctrl = _step_present_poll_move(
            ctx, console, game_map, player, present,
            map_w, map_h, location, *_step, post_step_tick,
        )
        if _ctrl is not None:
            return _ctrl


def run_auto_explore(
    ctx,
    console,
    game_map,
    player,
    *,
    post_step_tick,
    map_w: int,
    map_h: int,
    location: str = "Derelict Ship",
    present_frame=None,
) -> str:
    """Run DCSS-style auto-explore until a stop condition fires."""
    if game_map.seen is None or game_map.visible is None:
        ctx.log.add("Auto-explore only works inside dungeons.")
        return "DONE"
    _present = present_frame or _default_present_frame
    _standing_pos = (player.pos.x, player.pos.y)
    _standing = interesting_at(game_map, *_standing_pos)
    _memory = _ignored_positions(game_map)
    if _standing and _standing_pos not in _memory:
        _memory.add(_standing_pos)
        ctx.log.add(f"You are standing at {_standing}.")
        return "DONE"
    _known = _seed_known_interesting(game_map)
    ctx.log.add("Auto-explore engaged.")
    return _run_explore_loop(
        ctx, console, game_map, player, _present, post_step_tick,
        map_w, map_h, location, _known,
    )


# ---------------------------------------------------------------------------
# Go-to (the G key)
# ---------------------------------------------------------------------------


def _run_goto_loop(
    ctx, console, game_map, player, target, present, post_step_tick,
    map_w, map_h, location, known,
):
    """Walk to a target while sharing auto-explore interruption rules."""
    while True:
        if _adjacent(player.pos, target.x, target.y):
            ctx.log.add(f"You arrive at {target.label}.")
            return "DONE"
        if _stop_if_fresh(ctx, game_map, known) is not None:
            return "DONE"
        _step = next_goto_step(game_map, player.pos, target.x, target.y)
        if _step is None:
            ctx.log.add(f"Cannot reach {target.label}.")
            return "DONE"
        _ctrl = _step_present_poll_move(
            ctx, console, game_map, player, present,
            map_w, map_h, location, *_step, post_step_tick,
        )
        if _ctrl is not None:
            return _ctrl


def run_goto(
    ctx,
    console,
    game_map,
    player,
    *,
    target: GotoTarget,
    post_step_tick,
    map_w: int,
    map_h: int,
    location: str = "Derelict Ship",
    present_frame=None,
) -> str:
    """Auto-walk to a discovered target with shared stop semantics."""
    if game_map.seen is None or game_map.visible is None:
        ctx.log.add("Go to only works inside dungeons.")
        return "DONE"
    _present = present_frame or _default_present_frame
    _known = _seed_known_interesting(game_map)
    _known.add((target.x, target.y))
    ctx.log.add(f"Auto-nav engaged. Walking to {target.label}...")
    return _run_goto_loop(
        ctx, console, game_map, player, target, _present, post_step_tick,
        map_w, map_h, location, _known,
    )


def run_dungeon_goto(
    ctx,
    console,
    game_map,
    player,
    *,
    post_step_tick,
    map_w: int,
    map_h: int,
    location: str = "Derelict Ship",
    present_frame=None,
) -> str:
    """The ``G`` key: pick a discovered target, then auto-walk to it.

    Opens the shared GO TO picker (``navigation._run_pygame_goto_menu``)
    listing :func:`goto_targets` nearest-first, then hands off to
    :func:`run_goto`. Backing out of the picker, or having nothing
    discovered, returns ``"DONE"`` with a log line.
    """
    _targets = goto_targets(game_map, player.pos)
    if not _targets:
        ctx.log.add("You have not discovered anything to go to.")
        return "DONE"
    from .navigation import _run_pygame_goto_menu

    _handled, _selected = _run_pygame_goto_menu(
        ctx, [(t.title, t) for t in _targets],
    )
    if not _handled or _selected is None:
        return "DONE"
    return run_goto(
        ctx, console, game_map, player,
        target=_targets[_selected],
        post_step_tick=post_step_tick,
        map_w=map_w, map_h=map_h,
        location=location, present_frame=present_frame,
    )
