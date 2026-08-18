"""GO TO / jump-gate travel, jump animation, and system transition.

Extracted from ``navigation.py`` to keep that module under the 1,000-line
architecture limit. Every function here stays under 40 lines.
"""

from __future__ import annotations

import time
from enum import Enum, auto

from . import animation_timing
from . import main_quest as main_quest_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from . import world
from .data import solar_systems as solar_systems_module
from .engine import MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH
from .framebuffer import FrameBuffer
from .navigation_combat import (
    _check_auto_comms_warning,
    _detect_combat_encounter,
)
from .navigation_spawns import _add_bounty_spawns_to_map
from .time import tick_move

_JUMP_FRAME_S: float = animation_timing.JUMP
_JUMP_RING_CHARS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ('*', (255, 200, 100)),
    ('+', (255, 255, 150)),
    ('o', (255, 255, 200)),
    ('O', (200, 200, 255)),
    ('#', (180, 180, 255)),
)


# ---------------------------------------------------------------------------
# Outcome enums
# ---------------------------------------------------------------------------

class JumpMenuOutcome(Enum):
    """Result of the jump-point-bump dialog (single 'Jump' option).

    Multi-system iteration: when the player bumps a :class:`JumpPoint`
    in space, the dialog offers to jump to the connected system.
    ENTER returns :attr:`JUMP` (drives the system swap + log entries),
    ESC returns :attr:`BACK` (fly past), window-close returns
    :attr:`QUIT`. Single-target in v1 (each gate connects to exactly
    one other system); the data model supports multi-target hubs for
    future iterations.

    Mirror of :class:`PlanetMenuOutcome` so callers can dispatch
    on either enum with identical control flow.
    """
    IGNORE = auto()
    JUMP = auto()
    BACK = auto()
    QUIT = auto()


class GotoOutcome(Enum):
    """Result of the auto-nav (G-key) modal.

    The auto-nav modal animates the ship one cell per frame along a
    Bresenham-or-A* path. Two failure modes that need to flow back
    to the dispatcher distinctly:

    * :attr:`CANCELLED` - player backed out, no path found, or no
      destinations available. The ship is wherever it started (or
      wherever the partial path ended).
    * :attr:`COMPLETED` - ship reached the chosen destination. No
      combat triggered along the way.
    * :attr:`COMBAT` - the ship crossed into an enemy patrol's
      ``detect_radius`` mid-animation and the loop terminated early
      so the dispatcher can invoke combat from the ship's CURRENT
      position (not the original destination). The ``combat_data``
      tuple is ``(enemy_specs, enemy_positions)`` payload.

    Distinguishing :attr:`COMBAT` from the other two is critical:
    before this enum existed, the dispatcher called :func:`_run_goto`
    for its side-effect only and the auto-nav animation happily
    walked the ship right through a pirate patrol, leaving the
    player *inside* an enemy ``detect_radius`` with no combat
    triggered. The fix is to break the animation loop the moment
    a scan returns non-None combat data and surface the encounter
    to the dispatcher so the same combat-invocation path the
    post-move walker uses also fires for auto-nav interrupts.
    """
    CANCELLED = auto()
    COMPLETED = auto()
    COMBAT = auto()


class NavigationOutcome(Enum):
    """Result of the system-map (N) overlay.

    The overlay is read-only - any unknown key returns :attr:`IGNORE`,
    ESC closes the modal silently (:attr:`BACK`), window-close returns
    :attr:`QUIT`. Mirrors :class:`PlanetMenuOutcome` so the dispatcher
    can pattern-match on the outcome without bespoke plumbing.
    """
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


# ---------------------------------------------------------------------------
# Navigation overlay runner
# ---------------------------------------------------------------------------

def _run_navigation(ctx, ship_pos: world.Position) -> NavigationOutcome:
    """Show the system-map overlay in the shared Pygame window."""
    from . import pygame_navigation

    while True:
        outcome = pygame_navigation.run_for_context(ctx.context, ctx, ship_pos)
        if outcome == "GUIDE":
            from .help import _open_context_guide
            _open_context_guide(ctx, "Navigation & Jump Gates")
            continue
        if outcome == "QUIT":
            return NavigationOutcome.QUIT
        return NavigationOutcome.BACK


# ---------------------------------------------------------------------------
# GO TO (auto-nav)
# ---------------------------------------------------------------------------

def _goto_destinations(system) -> list[tuple[str, object]]:
    """Build the ``(label, body)`` destination list for the GO TO picker."""
    destinations: list[tuple[str, object]] = []
    for p in system.planets:
        label = p.name
        if getattr(p, 'sun', False):
            label = f'[Star] {label}'
        destinations.append((label, p))
    for jp in system.jump_points:
        destinations.append((f'[Gate] {jp.name}', jp))
    for st in getattr(system, 'stations', ()) or ():
        destinations.append((f'[Station] {st.name}', st))
    return destinations


def _goto_menu_frames(destinations: list[tuple[str, object]]):
    """Build the GO TO menu frames (one per destination index)."""
    from . import pygame_menu, pygame_ui

    items = tuple(
        pygame_menu.MenuItem(
            label,
            getattr(body, "description", "") or "Plot a course to this destination.",
            f"DEST:{index}",
        )
        for index, (label, body) in enumerate(destinations)
    )
    return tuple(
        pygame_menu.MenuFrame(
            title="GO TO",
            body="Select a destination for auto-navigation.",
            items=items,
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER go", "ESC cancel",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=index,
        )
        for index in range(len(items))
    )


def _run_pygame_goto_menu(
    ctx, destinations: list[tuple[str, object]],
) -> tuple[bool, int | None]:
    """Run the GO TO destination selector through the Pygame worker.

    Returns ``(handled, selected)``. ``handled`` is false only when the
    worker is unavailable, which preserves the strict fallback behavior.
    The parent process keeps destination objects private; the worker
    receives labels/descriptions and returns only an index.
    """
    from . import pygame_menu

    frames = _goto_menu_frames(destinations)
    while True:
        outcome, action, _selected = pygame_menu.run_for_context(
            getattr(ctx, "context", ctx),
            frames,
            caption="spacehack - go to",
        )
        if outcome == "GUIDE":
            from .help import _open_context_guide
            _open_context_guide(ctx, "Navigation & Jump Gates")
            continue
        if outcome in {"BACK", "QUIT"}:
            return True, None
        if outcome != "SELECT":
            return False, None
        prefix, separator, raw_index = action.partition(":")
        if prefix != "DEST" or not separator:
            return False, None
        try:
            selected = int(raw_index)
        except ValueError:
            return False, None
        if not 0 <= selected < len(destinations):
            return False, None
        return True, selected


def _goto_target_cells(ctx, chosen_body, destinations) -> set[tuple[int, int]]:
    """All walkable cells adjacent to ``chosen_body``, clear of other bodies."""
    dirs_8 = [(0, -1), (-1, 0), (1, 0), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]
    target_cells: set[tuple[int, int]] = set()
    for bx in range(chosen_body.pos.x, chosen_body.pos.x + chosen_body.width):
        for by in range(chosen_body.pos.y, chosen_body.pos.y + chosen_body.height):
            for dx, dy in dirs_8:
                nx, ny = (bx + dx, by + dy)
                if (chosen_body.pos.x <= nx < chosen_body.pos.x + chosen_body.width
                        and chosen_body.pos.y <= ny < chosen_body.pos.y + chosen_body.height):
                    continue
                if not ctx.game_map.in_bounds(nx, ny):
                    continue
                if not ctx.game_map.is_walkable(nx, ny):
                    continue
                blocked_by_other = False
                for other in destinations:
                    ob = other[1]
                    if ob is chosen_body:
                        continue
                    if (ob.pos.x <= nx < ob.pos.x + ob.width
                            and ob.pos.y <= ny < ob.pos.y + ob.height):
                        blocked_by_other = True
                        break
                if blocked_by_other:
                    continue
                target_cells.add((nx, ny))
    return target_cells


def _bresenham_line(x0, y0, x1, y1):
    """Yield the cells on the Bresenham line from (x0, y0) to (x1, y1)."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sig_x = 1 if x0 < x1 else -1
    sig_y = 1 if y0 < y1 else -1
    err = dx + dy
    cx, cy = (x0, y0)
    while (cx, cy) != (x1, y1):
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            cx += sig_x
        if e2 <= dx:
            err += dx
            cy += sig_y
        yield (cx, cy)


def _goto_cell_is_passable(ctx, x: int, y: int, chosen_body, destinations) -> bool:
    """True when cell (x, y) is walkable and not inside another body."""
    if not ctx.game_map.in_bounds(x, y):
        return False
    if not ctx.game_map.is_walkable(x, y):
        return False
    for other in destinations:
        ob = other[1]
        if ob is chosen_body:
            continue
        if ob.pos.x <= x < ob.pos.x + ob.width and ob.pos.y <= y < ob.pos.y + ob.height:
            return False
    return True


def _goto_plan_path(ctx, player_entity, chosen_body, destinations, target_cells):
    """Return the auto-nav step list (Bresenham when clear, else A*)."""
    sx, sy = (player_entity.pos.x, player_entity.pos.y)
    target_cx, target_cy = min(
        target_cells, key=lambda tc: max(abs(tc[0] - sx), abs(tc[1] - sy)),
    )
    line_clear = True
    line_path: list[tuple[int, int]] = []
    for lx, ly in _bresenham_line(sx, sy, target_cx, target_cy):
        if (lx, ly) in target_cells:
            line_path.append((lx, ly))
            break
        if not _goto_cell_is_passable(ctx, lx, ly, chosen_body, destinations):
            line_clear = False
            break
        line_path.append((lx, ly))
        if len(line_path) > 500:
            line_clear = False
            break
    if line_clear and line_path:
        line_path.append((target_cx, target_cy))
        return line_path
    return world.find_path(
        (sx, sy), target_cells, ctx.game_map,
        exclude_entity=player_entity,
    )


def _goto_render_step(console: FrameBuffer, ctx, sx: int, sy: int) -> None:
    """Render one auto-nav step frame (world + NPC flashes + HUD)."""
    sys_now = solar_system_module.current_system()
    view_w = solar_system_module.SOL_VIEW_W
    view_h = solar_system_module.SOL_VIEW_H
    cam_x = max(0, min(sx - view_w // 2, sys_now.width - view_w))
    cam_y = max(0, min(sy - view_h // 2, sys_now.height - view_h))
    console.clear()
    world.render_world_view(
        console, ctx.game_map,
        region_x=0, region_y=0, region_w=view_w, region_h=view_h,
        camera_x=cam_x, camera_y=cam_y,
    )
    # Render NPC flash events so merchant despawns decay normally during
    # auto-nav instead of accumulating and bursting at once on resume.
    from .npc_ships import render_npc_flash_events as _rnfe
    _rnfe(console, ctx, cam_x, cam_y, view_w, view_h)
    # Render the ship HUD during auto-nav (fuel, shields, etc.).
    from . import pygame_overlay
    _shield_bubbles = pygame_overlay.shield_bubbles_for_map(
        ctx.game_map,
        camera_x=cam_x,
        camera_y=cam_y,
        region_w=view_w,
        region_h=view_h,
        player_owned_ship=ctx.player_owned_ship,
    )
    pygame_overlay.present_exploration(
        ctx,
        console,
        mode="space",
        location=solar_system_module.current_system().name,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        hud_view_height=view_h,
        shields=_shield_bubbles,
    )


def _goto_poll_cancel(context, duration: float) -> bool:
    """Return True when the player presses a move key during ``duration``."""
    _end = time.monotonic() + duration
    while time.monotonic() < _end:
        for _ev in context.events():
            if _ev.kind == "keydown":
                if _ev.key_name in world.MOVE_KEYS or _ev.key_name in {".", "period"}:
                    return True
        _remaining = _end - time.monotonic()
        if _remaining > 0:
            time.sleep(min(_remaining, 0.01))
    return False


def _goto_step_interrupt(ctx, player_entity):
    """Return an ``(outcome, combat_data)`` interrupt, or ``None`` to continue."""
    _auto_result = _check_auto_comms_warning(
        ctx, player_entity.pos, solar_system_module.current_system(),
    )
    if _auto_result is not None:
        _warned, _attack_data = _auto_result
        ctx.log.add('Auto-nav interrupted - incoming transmission!')
        if _attack_data is not None:
            return (GotoOutcome.COMBAT, _attack_data)
        return (GotoOutcome.CANCELLED, None)
    _encounter = _detect_combat_encounter(
        ctx, player_entity.pos, solar_system_module.current_system(),
    )
    if _encounter is not None:
        ctx.log.add('Auto-nav interrupted - enemies detected!')
        return (GotoOutcome.COMBAT, _encounter)
    return None


def _goto_step(ctx, console, player_entity, sx: int, sy: int):
    """Move one auto-nav step; return ``(outcome, combat_data)`` or ``None``."""
    player_entity.pos = world.Position(sx, sy)
    _goto_render_step(console, ctx, sx, sy)
    if _goto_poll_cancel(ctx.context, animation_timing.AUTO_NAV):
        ctx.log.add('Auto-nav cancelled.')
        return (GotoOutcome.CANCELLED, None)
    _interrupt = _goto_step_interrupt(ctx, player_entity)
    if _interrupt is not None:
        return _interrupt
    from .npc_ships import move_npcs as _mn
    _mn(ctx, ctx.game_map)
    tick_move(ctx)
    return None


def _run_goto(
    ctx, console, player_entity: world.Entity,
) -> tuple[GotoOutcome, tuple[list, list[world.Position]] | None]:
    """Open the GO TO picker and auto-navigate the ship to the chosen body.

    Returns ``(outcome, combat_data)``: ``COMPLETED`` reached the target,
    ``CANCELLED`` backed out / no path, ``COMBAT`` interrupted with the
    ``(specs, positions)`` payload.
    """
    system = solar_system_module.current_system()
    destinations = _goto_destinations(system)
    if not destinations:
        ctx.log.add('There is nothing to navigate to in this system.')
        return (GotoOutcome.CANCELLED, None)
    _pygame_handled, selected = _run_pygame_goto_menu(ctx, destinations)
    if not _pygame_handled or selected is None:
        return (GotoOutcome.CANCELLED, None)
    chosen_body = destinations[selected][1]
    ctx.log.add(
        f"Auto-nav engaged. Plotting course to {getattr(chosen_body, 'name', 'target')}...",
    )
    target_cells = _goto_target_cells(ctx, chosen_body, destinations)
    if not target_cells:
        ctx.log.add('Cannot reach that destination - no adjacent landing zone.')
        return (GotoOutcome.CANCELLED, None)
    steps = _goto_plan_path(ctx, player_entity, chosen_body, destinations, target_cells)
    if steps is None:
        ctx.log.add('Could not find a path to that destination.')
        return (GotoOutcome.CANCELLED, None)
    if not steps:
        ctx.log.add('You are already at the destination.')
        return (GotoOutcome.COMPLETED, None)
    for sx, sy in steps:
        _step_result = _goto_step(ctx, console, player_entity, sx, sy)
        if _step_result is not None:
            return _step_result
    ctx.log.add('Auto-nav complete.')
    return (GotoOutcome.COMPLETED, None)


# ---------------------------------------------------------------------------
# Jump gate dialog
# ---------------------------------------------------------------------------

def _jump_menu_frame(jp, target_system_id: str, fuel, max_fuel):
    """Build the jump-confirmation menu frame."""
    from . import pygame_menu, pygame_ui

    target_system = solar_systems_module.find_solar_system(target_system_id)
    fuel_line = (
        f"Fuel: {fuel} / {max_fuel}  |  Jump cost: {ship_module.JUMP_FUEL_COST}"
        if fuel is not None and max_fuel is not None
        else ""
    )
    body = "\n".join(filter(None, (jp.description or "", fuel_line)))
    return pygame_menu.MenuFrame(
        title=f"JUMP - {jp.name} -> {target_system.name}",
        body=body,
        items=(pygame_menu.MenuItem(
            f"Jump to {target_system.name}",
            "Commit to the system transition.",
            "JUMP",
        ),),
        hints=(pygame_ui.modal_hint(
            "ENTER jump", "ESC fly past", pygame_ui.GUIDE_HINT,
        ),),
        selected=0,
    )


def _run_pygame_jump_menu(ctx, jp, target_system_id: str, fuel, max_fuel):
    """Run the jump confirmation through the Pygame menu worker."""
    from . import pygame_menu

    frame = _jump_menu_frame(jp, target_system_id, fuel, max_fuel)
    while True:
        outcome, action, _selected = pygame_menu.run_for_context(
            getattr(ctx, "context", ctx),
            (frame,),
            caption="spacehack - jump gate",
        )
        if outcome == "GUIDE":
            from .help import _open_context_guide
            _open_context_guide(ctx, "Navigation & Jump Gates")
            continue
        if outcome == "QUIT":
            return JumpMenuOutcome.QUIT
        if outcome == "SELECT" and action == "JUMP":
            return JumpMenuOutcome.JUMP
        return JumpMenuOutcome.BACK


def _run_jump_menu(ctx, jp, target_system_id: str) -> JumpMenuOutcome:
    """Run the jump-point dialog in the shared Pygame window."""
    _fuel: int | None = None
    _max_fuel: int | None = None
    if ctx.player_owned_ship is not None:
        ship_rec = ship_module.find_ship(ctx.player_owned_ship.ship_id)
        _fuel = ctx.player_owned_ship.fuel
        _max_fuel = ship_rec.max_fuel
    from . import pygame_menu
    result = _run_pygame_jump_menu(ctx, jp, target_system_id, _fuel, _max_fuel)
    if result is None:
        raise pygame_menu.PygameMenuUnavailable("Jump menu returned no outcome")
    return result


# ---------------------------------------------------------------------------
# Jump animation + system transition
# ---------------------------------------------------------------------------

def _responsive_sleep(seconds: float) -> None:
    """Sleep for ``seconds`` while polling SDL events.

    Breaks the sleep into ~0.01 s chunks and calls the Pygame event
    queue on each iteration so SDL can process OS-level events (mouse
    moves, window updates, etc.). Without this, macOS shows the
    spinning beach ball during animation loops that block with
    ``time.sleep``.
    """
    end = time.monotonic() + seconds
    import pygame
    while time.monotonic() < end:
        pygame.event.get()
        remaining = end - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, 0.01))


def _jump_camera(cx: int, cy: int):
    """Return ``(cam_x, cam_y, view_w, view_h)`` keeping the jump centre on screen."""
    _view_w = solar_system_module.SOL_VIEW_W
    _view_h = solar_system_module.SOL_VIEW_H
    _sys = solar_system_module.current_system()
    _cam_x = max(0, min(cx - _view_w // 2, _sys.width - _view_w))
    _cam_y = max(0, min(cy - _view_h // 2, _sys.height - _view_h))
    return _cam_x, _cam_y, _view_w, _view_h


def _jump_present_hud(ctx, console, cam_x: int, cam_y: int, view_w: int, view_h: int) -> None:
    """Present the space view with the ship HUD for one jump frame."""
    from . import pygame_overlay
    _shield_bubbles = pygame_overlay.shield_bubbles_for_map(
        ctx.game_map,
        camera_x=cam_x,
        camera_y=cam_y,
        region_w=view_w,
        region_h=view_h,
        player_owned_ship=ctx.player_owned_ship,
    )
    pygame_overlay.present_exploration(
        ctx,
        console,
        mode="space",
        location=solar_system_module.current_system().name,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT,
        shields=_shield_bubbles,
    )


def _jump_draw_rings(
    console,
    cx: int,
    cy: int,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    rings: int,
    ship_char: str,
    ship_fg: tuple[int, int, int],
) -> None:
    """Draw the expanding ring glyphs + brightened ship for one frame."""
    for ring_idx in range(min(rings + 1, len(_JUMP_RING_CHARS))):
        r_char, r_fg = _JUMP_RING_CHARS[ring_idx]
        dist = ring_idx + 1
        for dy in range(-dist, dist + 1):
            for dx in range(-dist, dist + 1):
                if abs(dx) + abs(dy) != dist:
                    continue
                sx = cx + dx - cam_x
                sy = cy + dy - cam_y
                if 0 <= sx < view_w and 0 <= sy < view_h:
                    console.print(x=sx, y=sy, string=r_char, fg=r_fg)
    bright_fg = (
        min(255, ship_fg[0] + rings * 30),
        min(255, ship_fg[1] + rings * 30),
        min(255, ship_fg[2] + rings * 30),
    )
    sx = cx - cam_x
    sy = cy - cam_y
    if 0 <= sx < view_w and 0 <= sy < view_h:
        console.print(x=sx, y=sy, string=ship_char, fg=bright_fg)


def _render_jump_frame(
    ctx,
    console: FrameBuffer,
    *,
    cx: int,
    cy: int,
    rings: int = 0,
    flash_white: bool = False,
    void: bool = False,
    ship_char: str = "",
    ship_fg: tuple[int, int, int] = (255, 255, 255),
) -> None:
    """Render one jump-animation frame (rings, white flash, or void)."""
    _cam_x, _cam_y, _view_w, _view_h = _jump_camera(cx, cy)
    console.clear()
    world.render_world_view(
        console, ctx.game_map,
        region_x=0, region_y=0, region_w=_view_w, region_h=_view_h,
        camera_x=_cam_x, camera_y=_cam_y,
    )
    if void:
        _jump_present_hud(ctx, console, _cam_x, _cam_y, _view_w, _view_h)
        _responsive_sleep(_JUMP_FRAME_S)
        return
    if not flash_white:
        _jump_draw_rings(
            console, cx, cy, _cam_x, _cam_y, _view_w, _view_h,
            rings, ship_char, ship_fg,
        )
    else:
        for fy in range(solar_system_module.SOL_VIEW_H):
            console.print(
                x=0, y=fy,
                string=' ' * solar_system_module.SOL_VIEW_W,
                fg=(255, 255, 255), bg=(255, 255, 255),
            )
    _jump_present_hud(ctx, console, _cam_x, _cam_y, _view_w, _view_h)
    _responsive_sleep(_JUMP_FRAME_S)


def _animate_jump(ctx, console: FrameBuffer, player_entity: world.Entity) -> None:
    """Render a brief 'jump drive' animation before the system swap."""
    cx = player_entity.pos.x + (player_entity.width - 1) // 2
    cy = player_entity.pos.y + (player_entity.height - 1) // 2
    ship_char = player_entity.char
    ship_fg = player_entity.fg
    for rings in range(len(_JUMP_RING_CHARS)):
        _render_jump_frame(
            ctx, console, cx=cx, cy=cy, rings=rings,
            ship_char=ship_char, ship_fg=ship_fg,
        )
    _render_jump_frame(
        ctx, console, cx=cx, cy=cy, flash_white=True,
        ship_char=ship_char, ship_fg=ship_fg,
    )
    _render_jump_frame(
        ctx, console, cx=cx, cy=cy, void=True,
        ship_char=ship_char, ship_fg=ship_fg,
    )


def _arrival_spawn_exclusion(dest_jp) -> set[tuple[int, int]]:
    """Cells around the destination gate that NPC spawns must avoid."""
    from .npc_ships import SPAWN_EXCLUSION_RADIUS as _SER
    _spawn_exclusion: set[tuple[int, int]] = set()
    for _dy in range(-_SER, _SER + 1):
        for _dx in range(-_SER, _SER + 1):
            _spawn_exclusion.add((dest_jp.pos.x + _dx, dest_jp.pos.y + _dy))
    return _spawn_exclusion


def _build_arrival_entity(ship_record, new_pos) -> world.Entity:
    """Build the player's ship entity parked at the destination gate."""
    return world.Entity(
        char=ship_record.char, fg=ship_record.fg, pos=new_pos,
        name=f'Your Ship: {ship_record.name}', ship_id=ship_record.id,
        width=ship_record.width, height=ship_record.height, owned=True,
    )


def _jump_to_system(
    *, ctx, jp, target_system_id: str, target_jp_id: str,
) -> tuple:
    """Jump the player ship from ``jp`` (current gate) to
    ``target_jp_id`` (in :attr:`target_system_id`).

    Returns ``(new_map, new_ship_ent)`` — the freshly built
    :class:`world.GameMap` plus the ship :class:`world.Entity` the
    dispatcher should rebind to as the new ``player``.
    """
    ctx.log.add('Your ship engages the jump drive. Reality blurs.')
    # Reset any NPC auto-comms warning for the outgoing system so the
    # player gets a fresh warning on their next visit.
    _src_id = getattr(solar_system_module.current_system(), 'id', '')
    if _src_id:
        ctx.militia_scanned.clear()
    target_system = solar_system_module.set_current_solar_system(target_system_id)
    new_map = solar_system_module.make_solar_system()
    _add_bounty_spawns_to_map(ctx, new_map, target_system_id)
    # Look up the destination gate FIRST so we can exclude its area
    # from NPC spawns — the player shouldn't arrive surrounded.
    dest_jp = solar_system_module.find_jump_point(target_jp_id, system=target_system)
    from .npc_ships import spawn_npcs as _sn
    _sn(ctx, new_map, target_system_id, player_spawn_exclusion=_arrival_spawn_exclusion(dest_jp))
    ship_record = ship_module.find_ship(ctx.player_owned_ship.ship_id)
    new_pos = solar_system_module.place_jumped_ship(ship_record, dest_jp)
    new_ship_ent = _build_arrival_entity(ship_record, new_pos)
    new_map.entities.append(new_ship_ent)
    ctx.log.add(f'You emerge near {target_system.name}.')
    # Main quest prologue: the garbled transmission fires on the first
    # jump OUT of Sol (see main_quest.maybe_trigger_signal) and arrives
    # as the prologue_signal step's declared incoming-comms overlay.
    if main_quest_module.maybe_trigger_signal(ctx, _src_id):
        main_quest_module.play_scene(ctx, "prologue_signal")
    return (new_map, new_ship_ent)
