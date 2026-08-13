"""DCSS-style auto-explore for dungeon mode — the ``O`` key.

Press ``O`` inside a derelict or dungeon to walk the player through
unrevealed tiles until:

* something interesting comes into sight (stairs, the exit, a ship
  computer, a cache of supplies, a quest NPC),
* a hostile comes into view (the shared ground-combat tick starts the
  fight and auto-explore stops), or
* the player presses any key to cancel.

Only *newly revealed* interesting content stops the run — things
already in view when ``O`` is pressed are seeded into the known set so
a single press never stalls next to loot the player already spotted.

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
    ("npc_id", "someone"),
)

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


# ---------------------------------------------------------------------------
# Step planning
# ---------------------------------------------------------------------------


def _first_step_toward(_prev, _sx: int, _sy: int, _tx: int, _ty: int) -> tuple[int, int]:
    """Walk the BFS parent chain back to the first step from the start."""
    _cur = (_tx, _ty)
    while _prev[_cur] != (_sx, _sy):
        _cur = _prev[_cur]
    return (_cur[0] - _sx, _cur[1] - _sy)


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
    _visible = game_map.visible
    if _visible is not None and _visible[y][x]:
        return _ent
    return None


def _plan_explore_step(game_map, player_pos):
    """BFS over the reachable region; returns ``(step, blockers)``.

    ``step`` is the first move toward the nearest unrevealed cell, or
    ``None`` when the region is fully revealed. ``blockers`` lists the
    visible solid entities encountered during expansion (nearest
    first) — the only entities that can seal the route, since unseen
    ones are walked through and revealed.
    """
    _seen = game_map.seen
    if _seen is None:
        return None, ()
    _sx, _sy = player_pos.x, player_pos.y
    if not game_map.in_bounds(_sx, _sy):
        return None, ()
    _prev: dict[tuple[int, int], tuple[int, int]] = {}
    _queue: deque[tuple[int, int]] = deque([(_sx, _sy)])
    _visited: set[tuple[int, int]] = {(_sx, _sy)}
    _blockers: list = []
    _blocker_ids: set[int] = set()
    while _queue:
        _cx, _cy = _queue.popleft()
        for _dx, _dy in _NEIGHBORS_8:
            _nx, _ny = _cx + _dx, _cy + _dy
            if not game_map.in_bounds(_nx, _ny) or (_nx, _ny) in _visited:
                continue
            _tile = game_map.tiles[_ny][_nx]
            if not _tile.walkable or _tile.kind in _TRANSITION_KINDS:
                # Unseen wall or transition = fog edge: walk up to the
                # adjacent passable cell (skipped when it is the
                # player's own cell — adjacent cells are always
                # revealed in-game, so this only guards synthetic
                # states).
                if not _seen[_ny][_nx] and (_cx, _cy) != (_sx, _sy):
                    return _first_step_toward(_prev, _sx, _sy, _cx, _cy), _blockers
                continue
            _ent = _visible_blocker(game_map, _nx, _ny)
            if _ent is not None:
                # Visible solid entity — the player knows it is there,
                # so it genuinely seals the route.
                if id(_ent) not in _blocker_ids:
                    _blocker_ids.add(id(_ent))
                    _blockers.append(_ent)
                continue
            _visited.add((_nx, _ny))
            _prev[(_nx, _ny)] = (_cx, _cy)
            if not _seen[_ny][_nx]:
                # Unseen walkable cell — walk toward it directly.
                return _first_step_toward(_prev, _sx, _sy, _nx, _ny), _blockers
            _queue.append((_nx, _ny))
    return None, _blockers


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
    _step, _ = _plan_explore_step(game_map, player_pos)
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
    _step, _blockers = _plan_explore_step(game_map, player_pos)
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
    """Run DCSS-style auto-explore until a stop condition fires.

    Returns one of:

    * ``"DONE"`` — stopped for an interesting sighting, finished
      exploring, or already standing on something interesting.
    * ``"COMBAT"`` — ``post_step_tick`` started a ground fight.
    * ``"DEFEAT"`` — the player died during that fight.
    * ``"CANCELLED"`` — the player pressed a key to abort.

    ``post_step_tick`` is the shared dungeon post-move tick (injected
    to avoid a circular import with ``__main__``); it returns
    ``"DEFEAT"`` / ``"COMBAT"`` / ``None`` like
    ``__main__._dungeon_post_move_tick``. It MUST refresh the
    LOS/visible frame after each step (as the real tick does) — a
    stub that never reveals makes the walk oscillate between two
    unseen cells.
    """
    if game_map.seen is None or game_map.visible is None:
        ctx.log.add("Auto-explore only works inside dungeons.")
        return "DONE"
    _present = present_frame or _default_present_frame
    _standing = interesting_at(game_map, player.pos.x, player.pos.y)
    if _standing:
        ctx.log.add(f"You are standing at {_standing}.")
        return "DONE"
    # Seed the known set with what is already in view so a press never
    # re-stops on content the player has already spotted.
    _known = newly_interesting_positions(game_map, set())
    ctx.log.add("Auto-explore engaged.")
    while True:
        _fresh = newly_interesting_positions(game_map, _known)
        if _fresh:
            _fx, _fy = min(_fresh)
            _label = interesting_at(game_map, _fx, _fy)
            ctx.log.add(f"You notice {_label} and stop.")
            return "DONE"
        _step = next_explore_step(game_map, player.pos)
        if _step is None:
            _blocker = blocking_way_entity(game_map, player.pos)
            if _blocker is not None:
                _label = _blocker_label(_blocker)
                ctx.log.add(
                    f"A {_label} blocks the only way forward."
                    if _label
                    else "Something blocks the only way forward."
                )
                return "DONE"
            ctx.log.add("You have explored every reachable area.")
            return "DONE"
        _dx, _dy = _step
        # Present the current frame and give the player a cancel window
        # (any keydown aborts; the key is swallowed, like _run_goto).
        _present(ctx, console, game_map, map_w=map_w, map_h=map_h, location=location)
        if _poll_cancel_window(ctx):
            return "CANCELLED"
        player.pos = world.Position(player.pos.x + _dx, player.pos.y + _dy)
        _ctrl = post_step_tick(ctx, console, game_map)
        if _ctrl == "DEFEAT":
            return "DEFEAT"
        if _ctrl == "COMBAT":
            return "COMBAT"
