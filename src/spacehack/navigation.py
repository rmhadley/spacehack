"""Navigation, jump, and space-map helpers extracted from ``__main__.py``.

Contains the GO TO screen, jump gate dialog, navigation overlay,
jump animation, system transition, AOI panel, and combat encounter
detection.
"""

from __future__ import annotations
import time
import math
from enum import Enum, auto
import tcod.console
import tcod.event
from . import ui
from . import world
from . import hud
from . import message_log
from . import mission as mission_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from .game_context import GameContext
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .data import solar_systems as solar_systems_module
from .data.npc_ships import find_npc_ship
from .input_helpers import _try_open_guide
from .time import tick_move, format_date


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NAV_SHIP_FG: tuple[int, int, int] = (255, 255, 100)
_JUMP_FRAME_S: float = 0.06
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
# AOI panel
# ---------------------------------------------------------------------------

def _render_aoi_panel(console, system, ship_pos, *, x: int, y: int, width: int, height: int) -> None:
    """Right-side Areas-of-Interest panel for the Map/NAVIGATION overlay.

    Renders a categorised list of Stars / Planets / Jump Points /
    (when present) Stations in the current solar system. Each
    entry shows its local name and Euclidean distance from the
    ship (1 dp, units = big-map cells). Sorted by distance
    within each category for predictable visual order.
    """
    COLOR_STAR = ui.COLOR_TITLE
    COLOR_PLANET = ui.COLOR_VALUE_WHITE
    COLOR_JUMP = ui.COLOR_OPTION_HIGHLIGHT
    COLOR_STATION = ui.COLOR_OPTION_HIGHLIGHT2
    inner_w = max(0, width - 4)
    SUFFIX_W = 10
    name_w = max(4, inner_w - SUFFIX_W)

    def _dist(body) -> float:
        cx = body.pos.x + (getattr(body, 'width', 1) - 1) / 2.0
        cy = body.pos.y + (getattr(body, 'height', 1) - 1) / 2.0
        return round(math.hypot(cx - ship_pos.x, cy - ship_pos.y), 1)

    def _clamp_label(label: str) -> str:
        if len(label) <= name_w:
            return label
        return label[:name_w - 1] + chr(8230)

    def _row(label, dist=None):
        if dist is None:
            return fit(label)
        return fit(f'{_clamp_label(label)} - {dist}u')

    def fit(line):
        return line if len(line) <= inner_w else line[:inner_w - 1] + chr(8230)
    rows = []
    rows.append(('AREAS OF INTEREST', ui.COLOR_TITLE))
    rows.append(('', ui.COLOR_VALUE_DIM))
    stars = [p for p in system.planets if getattr(p, 'sun', False)]
    if stars:
        rows.append(('Stars', COLOR_STAR))
        for p in stars:
            rows.append((_row(p.name, _dist(p)), COLOR_STAR))
        rows.append(('', COLOR_STAR))
    planets = [p for p in system.planets if not getattr(p, 'sun', False)]
    if planets:
        rows.append(('Planets', COLOR_PLANET))
        for p in sorted(planets, key=_dist):
            rows.append((_row(p.name, _dist(p)), COLOR_PLANET))
        rows.append(('', COLOR_PLANET))
    if system.jump_points:
        rows.append(('Jump Points', COLOR_JUMP))
        for jp in sorted(system.jump_points, key=_dist):
            rows.append((_row(jp.name, _dist(jp)), COLOR_JUMP))
        rows.append(('', COLOR_JUMP))
    stations = list(getattr(system, 'stations', ()) or ())
    if stations:
        rows.append(('Stations', COLOR_STATION))
        for st in sorted(stations, key=_dist):
            rows.append((_row(st.name, _dist(st)), COLOR_STATION))
        rows.append(('', COLOR_STATION))
    reachable_counts = solar_systems_module.reachable_system_ids(system.id)
    if reachable_counts:
        rows.append(('Reachable Systems', COLOR_JUMP))
        for sys_id, hops in sorted(reachable_counts.items(), key=lambda kv: (kv[1], kv[0])):
            dest_sys = solar_systems_module.find_solar_system(sys_id)
            row_text = f"{dest_sys.name:<{name_w}} - {hops} hop{('s' if hops > 1 else '')}"
            rows.append((fit(row_text), COLOR_JUMP))
        rows.append(('', COLOR_JUMP))
    cx, cy = (x + 2, y + 1)
    for label, fg in rows:
        if cy >= y + height - 2:
            break
        if not label:
            cy += 1
            continue
        console.print(x=cx, y=cy, string=label, fg=fg)
        cy += 1
    rect = (x + 1, y + 1, max(0, width - 2), max(0, height - 2))
    ui.paint_rect_border(console, rect, fg=ui.COLOR_VALUE_DIM)


# ---------------------------------------------------------------------------
# Navigation overlay
# ---------------------------------------------------------------------------

def render_navigation(console: tcod.console.Console, ctx: GameContext, *, screen_width: int, screen_height: int, ship_pos: world.Position, system=None) -> None:
    """Paint the current-solar-system navigation overlay."""
    console.clear()
    if system is None:
        system = solar_system_module.current_system()
    title = f'NAVIGATION - {system.name.upper()} SYSTEM'
    console.print(x=ui.centered_x(title, screen_width), y=2, string=title, fg=ui.COLOR_TITLE)
    inner_view_w = screen_width - HUD_WIDTH
    inner_view_h = screen_height - MSG_LOG_HEIGHT
    nav_map_w = 40
    nav_map_h = 30
    map_off_x = (inner_view_w - nav_map_w) // 2
    map_off_y = 4
    sample_x = system.width / nav_map_w
    sample_y = system.height / nav_map_h
    bodies_for_overlay = list(system.planets) + list(system.jump_points)
    cell_step_x = max(1, int(sample_x))
    cell_step_y = max(1, int(sample_y))
    for mini_y in range(nav_map_h):
        by_lo = int(mini_y * sample_y)
        by_hi = int((mini_y + 1) * sample_y) if mini_y + 1 < nav_map_h else system.height
        for mini_x in range(nav_map_w):
            bx_lo = mini_x * cell_step_x
            bx_hi = bx_lo + cell_step_x
            planet_here = None
            y = by_lo
            while y < by_hi and planet_here is None:
                x = bx_lo
                while x < bx_hi and planet_here is None:
                    if 0 <= x < system.width and 0 <= y < system.height:
                        for body in bodies_for_overlay:
                            if body.pos.x <= x < body.pos.x + body.width and body.pos.y <= y < body.pos.y + body.height:
                                planet_here = body
                                break
                    x += 1
                y += 1
            if planet_here is not None:
                console.print(x=map_off_x + mini_x, y=map_off_y + mini_y, string=planet_here.char, fg=planet_here.fg)
            else:
                console.print(x=map_off_x + mini_x, y=map_off_y + mini_y, string='.', fg=(80, 80, 110))
    ship_mini_x = int(ship_pos.x / sample_x)
    ship_mini_y = int(ship_pos.y / sample_y)
    if 0 <= ship_mini_x < nav_map_w and 0 <= ship_mini_y < nav_map_h:
        console.print(x=map_off_x + ship_mini_x, y=map_off_y + ship_mini_y, string='@', fg=NAV_SHIP_FG)
    if hasattr(system, 'stations'):
        aoi_w = 28
        aoi_x = screen_width - aoi_w - 2
        aoi_y = 4
        aoi_h = max(8, screen_height - 12)
        aoi_x = max(0, min(aoi_x, screen_width - aoi_w - 1))
        _render_aoi_panel(console, system, ship_pos, x=aoi_x, y=aoi_y, width=aoi_w, height=aoi_h)
    foot_y = map_off_y + nav_map_h + 1
    coord_line = f'You are at ({ship_pos.x}, {ship_pos.y}).'
    max_w = screen_width - HUD_WIDTH - 2
    if len(coord_line) > max_w:
        coord_line = coord_line[:max_w - 1] + '…'
    console.print(x=ui.centered_x(coord_line, screen_width), y=foot_y, string=coord_line, fg=ui.COLOR_VALUE_WHITE)
    hint = 'Press ESC to close.'
    console.print(x=ui.centered_x(hint, screen_width), y=foot_y + 2, string=hint, fg=ui.COLOR_INSTRUCTION)


def update_navigation(event: tcod.event.Event) -> NavigationOutcome:
    """Map a single event for the navigation overlay.

    Read-only modal: ESC closes (:attr:`BACK`), Quit exits
    (:attr:`QUIT`), everything else is :attr:`IGNORE` so the loop
    returns and the dispatcher can route the next event normally.
    """
    if isinstance(event, tcod.event.Quit):
        return NavigationOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return NavigationOutcome.IGNORE
    if event.sym in ui._ESCAPE_SYMS:
        return NavigationOutcome.BACK
    return NavigationOutcome.IGNORE


def _run_navigation(ctx, ship_pos: world.Position) -> NavigationOutcome:
    """Show the system-map overlay and return the outcome."""
    console = make_console()

    def _render() -> None:
        render_navigation(console, ctx, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, ship_pos=ship_pos)

    def _update(event) -> NavigationOutcome:
        if _try_open_guide(event, ctx):
            return NavigationOutcome.IGNORE
        return update_navigation(event)
    return ui.Modal(ctx.context, console).run(_render, _update)


def _nearest_body_name(pos: world.Position, system) -> str:
    """Return the name of the nearest named body (planet, gate, or
    station) to ``pos`` in ``system``. Fallbacks to "unknown location".
    """
    best_name = "unknown location"
    best_dist = 999999
    for p in system.planets:
        cx = p.pos.x + p.width // 2
        cy = p.pos.y + p.height // 2
        d = max(abs(pos.x - cx), abs(pos.y - cy))
        if d < best_dist:
            best_dist = d
            best_name = p.name
    for jp in system.jump_points:
        cx = jp.pos.x + jp.width // 2
        cy = jp.pos.y + jp.height // 2
        d = max(abs(pos.x - cx), abs(pos.y - cy))
        if d < best_dist:
            best_dist = d
            best_name = jp.name
    for st in getattr(system, 'stations', ()) or ():
        cx = st.pos.x + st.width // 2
        cy = st.pos.y + st.height // 2
        d = max(abs(pos.x - cx), abs(pos.y - cy))
        if d < best_dist:
            best_dist = d
            best_name = st.name
    return best_name


# ---------------------------------------------------------------------------
# Bounty spawn helpers (needed by jump/system transition)
# ---------------------------------------------------------------------------

def _add_bounty_spawns_to_map(
    ctx, game_map: world.GameMap, system_id: str,
) -> None:
    """Add bounty-target enemy entities from ``ctx.bounty_spawns`` to
    ``game_map.entities`` for system ``system_id``.

    Called after :func:`solar_system_module.make_solar_system` so
    dynamically-spawned bounty targets appear on the map alongside
    the system's static enemies. Logs a sensor ping with the nearest
    landmark so the player knows where to look. No-op when the system
    has no active bounty spawns.
    """
    _spawns = ctx.bounty_spawns.get(system_id, [])
    if not _spawns:
        return
    _system = getattr(solar_system_module, 'current_system', lambda: None)()
    for _bs in _spawns:
        try:
            _espec = find_npc_ship(_bs.enemy_id)
        except (KeyError, ImportError):
            continue
        game_map.entities.append(world.Entity(
            char=_espec.char,
            fg=_espec.fg,
            pos=_bs.pos,
            name=_espec.name,
            width=1, height=1,
            npc_ship_id=_bs.enemy_id,
        ))
        if _system is not None:
            _landmark = _nearest_body_name(_bs.pos, _system)
            ctx.log.add_colored(f"Sensor ping: bounty target detected near {_landmark}.",
                                message_log.COLOR_IMPORTANT_EVENT)


# ---------------------------------------------------------------------------
# Combat encounter detection
# ---------------------------------------------------------------------------

def _detect_combat_encounter(ctx, player_pos: world.Position, system: object) -> tuple[list, list[world.Position]] | None:
    """Run the squad-aware enemy scan and return combat payload, or ``None``.

    Two-pass design: pass 1 marks alive enemy spawns within
    ``detect_radius`` as triggered (squad or solo), pass 2 builds
    the encounter payload for any spawn whose squad was triggered
    OR whose own position was triggered as a solo. Returns
    ``(specs, positions)`` if any spawn was triggered, else ``None``.

    Also checks :attr:`ctx.bounty_spawns` so dynamically-placed
    bounty targets trigger combat the same way as static enemies.
    """
    _enemy_spawns = getattr(system, 'enemies', ()) or ()
    _alive_spawns: list = []
    _triggered_squad_ids: set = set()
    _triggered_solo_positions: set = set()
    # Check static system spawns.
    for _spawn in _enemy_spawns:
        try:
            _espec = find_npc_ship(_spawn.enemy_id)
        except KeyError:
            continue
        _enemy_alive = any((_e for _e in ctx.game_map.entities if not getattr(_e, 'owned', False) and _e.pos.x == _spawn.pos.x and (_e.pos.y == _spawn.pos.y)))
        if not _enemy_alive:
            continue
        _alive_spawns.append((_spawn, _espec))
        _dist = math.hypot(player_pos.x - _spawn.pos.x, player_pos.y - _spawn.pos.y)
        if _dist > 0 and _dist <= _espec.detect_radius:
            if _spawn.squad_id is not None:
                _triggered_squad_ids.add(_spawn.squad_id)
            else:
                _triggered_solo_positions.add((_spawn.pos.x, _spawn.pos.y))
    # Also check bounty spawns (dynamic targets placed on accept).
    _system_id = getattr(system, 'id', '')
    _bounty_spawns = ctx.bounty_spawns.get(_system_id, [])
    for _bs in _bounty_spawns:
        try:
            _espec = find_npc_ship(_bs.enemy_id)
        except KeyError:
            continue
        _enemy_alive = any((_e for _e in ctx.game_map.entities if not getattr(_e, 'owned', False) and _e.pos.x == _bs.pos.x and (_e.pos.y == _bs.pos.y)))
        if not _enemy_alive:
            continue
        _alive_spawns.append((_bs, _espec))
        _dist = math.hypot(player_pos.x - _bs.pos.x, player_pos.y - _bs.pos.y)
        if _dist > 0 and _dist <= _espec.detect_radius:
            _triggered_solo_positions.add((_bs.pos.x, _bs.pos.y))
    # Also check procedural NPCs by current entity positions.
    _procedural_entities = [
        _e for _e in ctx.game_map.entities
        if not getattr(_e, 'owned', False)
        and getattr(_e, 'procedural_squad_id', '') != ''
    ]
    for _pe in _procedural_entities:
        _pid = getattr(_pe, 'npc_ship_id', '') or "pirate_scout"
        try:
            _espec = find_npc_ship(_pid)
        except (KeyError, ImportError):
            continue
        _alive_spawns.append((_pe, _espec))
        _dist = math.hypot(player_pos.x - _pe.pos.x, player_pos.y - _pe.pos.y)
        if _dist > 0 and _dist <= _espec.detect_radius:
            _triggered_squad_ids.add(_pe.procedural_squad_id)
    _nearby_specs: list = []
    _nearby_positions: list = []
    for _spawn, _espec in _alive_spawns:
        _sq = getattr(_spawn, 'squad_id', None) or getattr(_spawn, 'procedural_squad_id', None)
        if _sq is not None:
            if _sq in _triggered_squad_ids:
                _nearby_specs.append(_espec)
                _nearby_positions.append(_spawn.pos)
        elif (_spawn.pos.x, _spawn.pos.y) in _triggered_solo_positions:
            _nearby_specs.append(_espec)
            _nearby_positions.append(_spawn.pos)
    if _nearby_specs:
        return (_nearby_specs, _nearby_positions)
    return None


# ---------------------------------------------------------------------------
# NPC auto-comms warning (before combat triggers)
# ---------------------------------------------------------------------------

def _check_auto_comms_warning(ctx, player_pos, system) -> tuple[bool, object] | None:
    """Check if any NPC with ``comms_warning_range > 0`` is within range.

    If a qualifying NPC is found and the player has NOT already been
    warned in this system, opens the comms panel and marks the system
    as warned. Returns:

      * ``(True, attack_data_or_None)`` -- warning was issued.
        ``attack_data`` is ``(specs, positions)`` if the player
        chose **Attack** from the comms, or ``None`` if they closed
        the comms or chose another option.
      * ``None`` -- no qualifying NPC within range (or already
        warned). Callers should continue normally.

    Warning range must be larger than ``detect_radius`` on the same
    NPC spec so the player gets a chance to turn back before combat
    triggers.
    """
    _sys_id = getattr(system, 'id', '')
    if not _sys_id:
        return None
    if _sys_id in ctx.militia_warned_systems:
        return None

    for _e in ctx.game_map.entities:
        if getattr(_e, 'owned', False):
            continue
        _pid = getattr(_e, 'npc_ship_id', '')
        if not _pid:
            continue
        try:
            _spec = find_npc_ship(_pid)
        except (KeyError, ImportError):
            continue
        _warn_range = getattr(_spec, 'comms_warning_range', 0)
        if _warn_range <= 0:
            continue
        _dist = math.hypot(
            player_pos.x - _e.pos.x,
            player_pos.y - _e.pos.y,
        )
        if 0 < _dist <= _warn_range:
            ctx.militia_warned_systems.add(_sys_id)
            # Open the existing comms panel so the player sees the
            # hailing ship and can choose to turn back, attack, or
            # interact further.
            from .comms import open_comms as _open_comms
            _attack_data = _open_comms(ctx, player_pos)
            return (True, _attack_data)
    return None


# ---------------------------------------------------------------------------
# GO TO (auto-nav)
# ---------------------------------------------------------------------------

def _run_goto(ctx, player_entity: world.Entity) -> tuple[GotoOutcome, tuple[list, list[world.Position]] | None]:
    """Open a GO TO modal listing interactable space bodies, then
    auto-navigate the player's ship to a cell adjacent to the chosen
    target using BFS pathfinding + step-by-step animation.

    Returns ``(outcome, combat_data)``:
    * ``(GotoOutcome.COMPLETED, None)`` — reached destination.
    * ``(GotoOutcome.CANCELLED, None)`` — backed out or no path.
    * ``(GotoOutcome.COMBAT, (specs, positions))`` — interrupted by combat.
    """
    system = solar_system_module.current_system()
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
    if not destinations:
        ctx.log.add('There is nothing to navigate to in this system.')
        return (GotoOutcome.CANCELLED, None)
    n = len(destinations)
    selected = 0
    console = make_console()
    while True:
        console.clear()
        _goto_items = [(label, "") for label, _body in destinations]
        ui.render_selectable_list(
            console, SCREEN_WIDTH, SCREEN_HEIGHT,
            title="GO TO",
            items=_goto_items,
            selected=selected,
            hint='ARROW KEYS / j,k navigate - ENTER go - ESC cancel',
        )
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        ctx.context.present(console)
        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                return (GotoOutcome.CANCELLED, None)
            if not isinstance(event, tcod.event.KeyDown):
                continue
            sym = event.sym
            sym_name: str = getattr(sym, 'name', '').lower()
            if _try_open_guide(event, ctx):
                continue
            if sym in ui._UP_SYMS or sym_name == 'k':
                selected = (selected - 1) % n
                break
            if sym in ui._DOWN_SYMS or sym_name == 'j':
                selected = (selected + 1) % n
                break
            if sym in ui._ESCAPE_SYMS:
                return (GotoOutcome.CANCELLED, None)
            if sym in ui._ENTER_SYMS:
                chosen_body = destinations[selected][1]
                ctx.log.add(f"Auto-nav engaged. Plotting course to {getattr(chosen_body, 'name', 'target')}...")
                dirs_8 = [(0, -1), (-1, 0), (1, 0), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]
                target_cells: set[tuple[int, int]] = set()
                for bx in range(chosen_body.pos.x, chosen_body.pos.x + chosen_body.width):
                    for by in range(chosen_body.pos.y, chosen_body.pos.y + chosen_body.height):
                        for dx, dy in dirs_8:
                            nx, ny = (bx + dx, by + dy)
                            if chosen_body.pos.x <= nx < chosen_body.pos.x + chosen_body.width and chosen_body.pos.y <= ny < chosen_body.pos.y + chosen_body.height:
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
                                if ob.pos.x <= nx < ob.pos.x + ob.width and ob.pos.y <= ny < ob.pos.y + ob.height:
                                    blocked_by_other = True
                                    break
                            if blocked_by_other:
                                continue
                            target_cells.add((nx, ny))
                if not target_cells:
                    ctx.log.add('Cannot reach that destination - no adjacent landing zone.')
                    return (GotoOutcome.CANCELLED, None)
                start = (player_entity.pos.x, player_entity.pos.y)
                sx, sy = start
                target_cx, target_cy = min(target_cells, key=lambda tc: max(abs(tc[0] - sx), abs(tc[1] - sy)))

                def _bresenham_line(x0, y0, x1, y1):
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

                def _cell_is_passable(x, y):
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
                line_clear = True
                line_path: list[tuple[int, int]] = []
                for lx, ly in _bresenham_line(sx, sy, target_cx, target_cy):
                    if (lx, ly) in target_cells:
                        line_path.append((lx, ly))
                        break
                    if not _cell_is_passable(lx, ly):
                        line_clear = False
                        break
                    line_path.append((lx, ly))
                    if len(line_path) > 500:
                        line_clear = False
                        break
                if line_clear and line_path:
                    line_path.append((target_cx, target_cy))
                    steps = line_path
                else:
                    steps = world.find_path(
                        start, target_cells, ctx.game_map,
                        exclude_entity=player_entity,
                    )
                    if steps is None:
                        ctx.log.add('Could not find a path to that destination.')
                        return (GotoOutcome.CANCELLED, None)
                if not steps:
                    ctx.log.add('You are already at the destination.')
                    return (GotoOutcome.COMPLETED, None)
                for sx, sy in steps:
                    player_entity.pos = world.Position(sx, sy)
                    sys_now = solar_system_module.current_system()
                    sol_w = sys_now.width
                    sol_h = sys_now.height
                    view_w = solar_system_module.SOL_VIEW_W
                    view_h = solar_system_module.SOL_VIEW_H
                    cam_x = max(0, min(sx - view_w // 2, sol_w - view_w))
                    cam_y = max(0, min(sy - view_h // 2, sol_h - view_h))
                    console.clear()
                    world.render_world_view(console, ctx.game_map, region_x=0, region_y=0, region_w=view_w, region_h=view_h, camera_x=cam_x, camera_y=cam_y)
                    # Render ship HUD during auto-nav so the player sees fuel, shields, etc.
                    _ship_cat = ship_module.find_ship(ctx.player_owned_ship.ship_id) if ctx.player_owned_ship is not None else None
                    hud.render_hud(
                        console,
                        screen_width=SCREEN_WIDTH,
                        hud_view_height=view_h,
                        character=ctx.character_info,
                        stats=ctx.stats,
                        location=solar_system_module.current_system().name,
                        owned_ship=ctx.player_owned_ship,
                        ship_catalog=_ship_cat,
                        date_str=format_date(ctx),
                    )
                    message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
                    ctx.context.present(console)
                    _aborted = False
                    _end = time.monotonic() + 0.04
                    while time.monotonic() < _end:
                        for _ev in tcod.event.get():
                            if isinstance(_ev, tcod.event.KeyDown):
                                _name = getattr(_ev.sym, 'name', '').lower()
                                if _name in world.VIM_DELTAS or _name == 'period':
                                    _aborted = True
                                    break
                        if _aborted:
                            break
                        _remaining = _end - time.monotonic()
                        if _remaining > 0:
                            time.sleep(min(_remaining, 0.01))
                    if _aborted:
                        ctx.log.add('Auto-nav cancelled.')
                        return (GotoOutcome.CANCELLED, None)
                    _auto_result = _check_auto_comms_warning(ctx, player_entity.pos, solar_system_module.current_system())
                    if _auto_result is not None:
                        _warned, _attack_data = _auto_result
                        ctx.log.add('Auto-nav interrupted - incoming transmission!')
                        if _attack_data is not None:
                            return (GotoOutcome.COMBAT, _attack_data)
                        return (GotoOutcome.CANCELLED, None)
                    _encounter = _detect_combat_encounter(ctx, player_entity.pos, solar_system_module.current_system())
                    if _encounter is not None:
                        ctx.log.add('Auto-nav interrupted - enemies detected!')
                        return (GotoOutcome.COMBAT, _encounter)
                    from .npc_ships import move_npcs as _mn
                    _mn(ctx, ctx.game_map)
                    tick_move(ctx)
                ctx.log.add('Auto-nav complete.')
                return (GotoOutcome.COMPLETED, None)
            continue


# ---------------------------------------------------------------------------
# Jump gate dialog
# ---------------------------------------------------------------------------

def render_jump_menu(console: tcod.console.Console, ctx: GameContext, jp, target_system_id: str, *, screen_width: int, screen_height: int, current_fuel: int | None=None, max_fuel: int | None=None, jump_fuel_cost: int=10) -> None:
    """Paint the jump-point-bump dialog."""
    target_system = solar_systems_module.find_solar_system(target_system_id)
    console.clear()
    title = f'JUMP  -  {jp.name}  ->  {target_system.name}'
    title_y = screen_height // 2 - 4
    console.print(x=ui.centered_x(title, screen_width), y=title_y, string=title, fg=ui.COLOR_TITLE)
    desc_lines = ui.wrap_text(jp.description or '', max_width=screen_width - 8)
    _content_bottom = title_y + 2 + len(desc_lines[:3])
    for i, line in enumerate(desc_lines[:3]):
        console.print(x=ui.centered_x(line, screen_width), y=title_y + 2 + i, string=line, fg=ui.COLOR_DESCRIPTION)
    _list_y = _content_bottom + 1
    if current_fuel is not None and max_fuel is not None:
        fuel_str = f'Fuel: {current_fuel} / {max_fuel}  |  Jump cost: {jump_fuel_cost}'
        console.print(x=ui.centered_x(fuel_str, screen_width), y=_content_bottom + 1, string=fuel_str, fg=ui.COLOR_OPTION_HIGHLIGHT if current_fuel >= jump_fuel_cost else ui.COLOR_VALUE_DIM)
        _list_y = _content_bottom + 3
    ui.render_selectable_list(
        console, screen_width, screen_height,
        title="",
        items=[(f"Jump to {target_system.name}", "")],
        selected=0,
        title_y=_list_y,
        hint="ENTER to jump - ESC to fly past",
    )
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def update_jump_menu(event: tcod.event.Event) -> JumpMenuOutcome:
    """Translate a key into a :class:`JumpMenuOutcome`."""
    if isinstance(event, tcod.event.Quit):
        return JumpMenuOutcome.QUIT
    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym
        if sym in ui._ESCAPE_SYMS:
            return JumpMenuOutcome.BACK
        if sym in ui._ENTER_SYMS:
            return JumpMenuOutcome.JUMP
    return JumpMenuOutcome.IGNORE


def _run_jump_menu(ctx, jp, target_system_id: str) -> JumpMenuOutcome:
    """Modal loop for the jump-point-bump dialog."""
    from . import engine
    console = engine.make_console()
    _fuel: int | None = None
    _max_fuel: int | None = None
    if ctx.player_owned_ship is not None:
        ship_rec = ship_module.find_ship(ctx.player_owned_ship.ship_id)
        _fuel = ctx.player_owned_ship.fuel
        _max_fuel = ship_rec.max_fuel

    def _render() -> None:
        render_jump_menu(console, ctx, jp, target_system_id, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, current_fuel=_fuel, max_fuel=_max_fuel, jump_fuel_cost=ship_module.JUMP_FUEL_COST)

    def _update(event) -> JumpMenuOutcome:
        if _try_open_guide(event, ctx):
            return JumpMenuOutcome.IGNORE
        ctx.context.convert_event(event)
        return update_jump_menu(event)
    return ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Cargo scan
# ---------------------------------------------------------------------------

def _run_cargo_scan(ctx, planet_id: str) -> None:
    """Check the player's cargo for contraband when landing on a
    planet with a militia presence.

    If the planet has a building labeled ``"militia"`` there is a
    40% chance the militia runs a scan.  When contraband is
    found every contraband crate is confiscated and a fine equal
    to 50% of the goods' total base value is deducted from
    the player's credits.
    """
    from .data.trade_goods import find_trade_good as _ftg
    from . import engine as _engine

    owned = ctx.player_owned_ship
    if owned is None:
        return

    from .data.planets import find_planet_spec
    try:
        spec = find_planet_spec(planet_id)
    except KeyError:
        return
    _has_militia = any(b.label == "militia" for b in spec.buildings)
    if not _has_militia:
        return

    if _engine.RNG.random() >= 0.4:
        return

    _confiscated: list[tuple[str, int, int]] = []
    for gid, qty in list(owned.inventory.items()):
        try:
            good = _ftg(gid)
        except KeyError:
            continue
        if good.category == "contraband":
            _fine = good.base_price * qty // 2
            _confiscated.append((gid, qty, _fine))

    if not _confiscated:
        ctx.log.add("Militia scans your cargo \u2014 clean.")
        return

    _total_fine = 0
    for gid, qty, fine in _confiscated:
        good = _ftg(gid)
        ctx.log.add_colored(f"Contraband {good.name} x{qty} confiscated by militia!",
                            message_log.COLOR_IMPORTANT_EVENT)
        _total_fine += fine
        remaining = owned.inventory.get(gid, 0) - qty
        if remaining <= 0:
            if gid in owned.inventory:
                del owned.inventory[gid]
        else:
            owned.inventory[gid] = remaining

    ctx.stats.credits = max(0, ctx.stats.credits - _total_fine)
    ctx.log.add_colored(f"Militia levies a fine of {_total_fine}$ for contraband.",
                        message_log.COLOR_IMPORTANT_EVENT)


# ---------------------------------------------------------------------------
# Jump animation + system transition
# ---------------------------------------------------------------------------

def _responsive_sleep(seconds: float) -> None:
    """Sleep for ``seconds`` while polling SDL events.

    Breaks the sleep into ~0.01 s chunks and calls
    ``tcod.event.poll()`` on each iteration so SDL can
    process OS-level events (mouse moves, window updates,
    etc.). Without this, macOS shows the spinning beach
    ball during animation loops that block with
    ``time.sleep``.
    """
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for _ in tcod.event.get():
            pass
        remaining = end - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, 0.01))


def _animate_jump(ctx, console: tcod.console.Console, player_entity: world.Entity) -> None:
    """Render a brief "jump drive" animation before the system swap.

    Draws the current space view with an expanding bright explosion
    centered on ``player_entity``'s position.
    """
    frame_s = _JUMP_FRAME_S
    cx = player_entity.pos.x + (player_entity.width - 1) // 2
    cy = player_entity.pos.y + (player_entity.height - 1) // 2
    ship_char = player_entity.char
    ship_fg = player_entity.fg

    def _render_frame(rings: int, flash_white: bool=False, void: bool=False) -> None:
        console.clear()
        _view_w = solar_system_module.SOL_VIEW_W
        _view_h = solar_system_module.SOL_VIEW_H
        _sys = solar_system_module.current_system()
        _cam_x = max(0, min(cx - _view_w // 2, _sys.width - _view_w))
        _cam_y = max(0, min(cy - _view_h // 2, _sys.height - _view_h))
        world.render_world_view(console, ctx.game_map, region_x=0, region_y=0, region_w=_view_w, region_h=_view_h, camera_x=_cam_x, camera_y=_cam_y)
        if void:
            ctx.context.present(console)
            _responsive_sleep(frame_s)
            return
        if not flash_white:
            for ring_idx in range(min(rings + 1, len(_JUMP_RING_CHARS))):
                r_char, r_fg = _JUMP_RING_CHARS[ring_idx]
                dist = ring_idx + 1
                for dy in range(-dist, dist + 1):
                    for dx in range(-dist, dist + 1):
                        if abs(dx) + abs(dy) != dist:
                            continue
                        sx = cx + dx - _cam_x
                        sy = cy + dy - _cam_y
                        if 0 <= sx < _view_w and 0 <= sy < _view_h:
                            console.print(x=sx, y=sy, string=r_char, fg=r_fg)
            bright_fg = (min(255, ship_fg[0] + rings * 30), min(255, ship_fg[1] + rings * 30), min(255, ship_fg[2] + rings * 30))
            sx = cx - _cam_x
            sy = cy - _cam_y
            if 0 <= sx < _view_w and 0 <= sy < _view_h:
                console.print(x=sx, y=sy, string=ship_char, fg=bright_fg)
        else:
            for fy in range(solar_system_module.SOL_VIEW_H):
                console.print(x=0, y=fy, string=' ' * solar_system_module.SOL_VIEW_W, fg=(255, 255, 255), bg=(255, 255, 255))
        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT, character=ctx.character_info, stats=ctx.stats, location=solar_system_module.current_system().name, owned_ship=ctx.player_owned_ship, ship_catalog=ship_module.find_ship(ctx.player_owned_ship.ship_id) if ctx.player_owned_ship is not None else None, date_str=format_date(ctx))
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        ctx.context.present(console)
        _responsive_sleep(frame_s)
    for rings in range(len(_JUMP_RING_CHARS)):
        _render_frame(rings=rings, flash_white=False)
    _render_frame(rings=0, flash_white=True)
    _render_frame(rings=0, void=True)


def _jump_to_system(*, ctx, jp, target_system_id: str, target_jp_id: str) -> tuple:
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
        ctx.militia_warned_systems.discard(_src_id)
    target_system = solar_system_module.set_current_solar_system(target_system_id)
    new_map = solar_system_module.make_solar_system()
    _add_bounty_spawns_to_map(ctx, new_map, target_system_id)
    from .npc_ships import spawn_npcs as _sn
    _sn(ctx, new_map, target_system_id)
    dest_jp = solar_system_module.find_jump_point(target_jp_id, system=target_system)
    ship_record = ship_module.find_ship(ctx.player_owned_ship.ship_id)
    new_pos = solar_system_module.place_jumped_ship(ship_record, dest_jp)
    new_ship_ent = world.Entity(char=ship_record.char, fg=ship_record.fg, pos=new_pos, name=f'Your Ship: {ship_record.name}', ship_id=ship_record.id, width=ship_record.width, height=ship_record.height, owned=True)
    new_map.entities.append(new_ship_ent)
    ctx.log.add(f'You emerge near {target_system.name}.')
    return (new_map, new_ship_ent)
