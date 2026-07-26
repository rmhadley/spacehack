"""Entry point for spacehack.

Run with ``python -m spacehack``.

Flow on a new game:

    species menu  ->  class menu  ->  confirm  ->  game (city + HUD + msg log)
       ^ ESC = quit       ^ ESC = back     ^ ESC = back        ^ ESC = quit

The game screen is a small city + space-port + 4 guild halls.
Movement uses the standard roguelike vim keys
(``h`` / ``j`` / ``k`` / ``l`` for cardinals, ``y`` / ``u`` / ``b`` / ``n``
for diagonals). Walking into a wall logs a short message. Walking
onto a tile holding another entity opens a context dialog:

    * ship at the space port -> ship-buy modal (Enter / ESC)
    * guild NPC -> flavor dialog (ESC to leave)
    * anything else -> "You bump into X" log line
"""
from __future__ import annotations
import time
import math
from enum import Enum, auto
import tcod.console
import tcod.context
import tcod.event
from . import character
from . import hud
from . import message_log
from . import mission as mission_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from . import ui
from .game_context import GameContext
from .data import solar_systems as solar_systems_module
from .data.species import find_species
from .data.classes import find_class
from . import npc as npc_module
from .npc import TalkOutcome, _run_npc_talk
from . import world
from . import combat
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, WINDOW_TITLE, load_tileset, make_console, open_terminal, seed_rng, should_quit
NAV_SHIP_FG: tuple[int, int, int] = (255, 255, 100)

class Outcome(Enum):
    """What happened at the end of a per-creation-screen loop iteration.

    ``IGNORE`` is the standard "keep polling" signal consumed by
    :meth:`spacehack.ui.Modal.run` -- an update function returns
    :attr:`IGNORE` for events it doesn't act on, and Modal keeps
    rendering + polling. Every other member terminates the modal
    loop and propagates back to the caller.
    """
    IGNORE = auto()
    QUIT = auto()
    BACK = auto()
    CONFIRM = auto()

class ShipBuyOutcome(Enum):
    """What happened during a single ship-buy dialog iteration.

    Differentiates ESC (silent back) from Enter-while-unaffordable
    (caller should log "you cannot afford this"). The BUY outcome
    implies the player can afford the ship.
    """
    IGNORE = auto()
    BUY = auto()
    BACK = auto()
    TOO_EXPENSIVE = auto()
    QUIT = auto()

class ShipMenuAction(Enum):
    """Which sub-modal of the hangar menu the player triggers."""
    IGNORE = auto()
    VIEW = auto()
    REFUEL = auto()
    SELL = auto()
    LAUNCH = auto()
    BACK = auto()
    QUIT = auto()

class ShipViewOutcome(Enum):
    """Result of the ship-stats sub-modal (View option).

    The stats panel is read-only: any key returns to the menu, ESC
    closes the panel directly. Held separately from ShipMenuAction
    so the menu dispatcher stays focused on its 3-option list.
    """
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()

class PlanetMenuOutcome(Enum):
    """Result of the planet-bump dialog (single 'Land' option).

    Converted from a one-line stub into the full shape so the
    dispatcher can dispatch on :attr:`LAND` to drive the
    city-return animation when the player bumps Earth. ESC returns
    :attr:`BACK`, window-close returns :attr:`QUIT`.
    """
    IGNORE = auto()
    LAND = auto()
    BACK = auto()
    QUIT = auto()

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

def _run_pick(context: tcod.context.Context, menu: ui.MenuScreen) -> tuple[Outcome, str | None]:
    console = make_console()

    def _render() -> None:
        ui.render_menu(console, menu, SCREEN_WIDTH, SCREEN_HEIGHT)

    def _update(event) -> Outcome:
        if isinstance(event, tcod.event.Quit):
            return Outcome.QUIT
        action = ui.update_menu(menu, event)
        if action is ui.MenuAction.CONFIRM:
            return Outcome.CONFIRM
        if action is ui.MenuAction.BACK:
            return Outcome.BACK
        return Outcome.IGNORE
    outcome = ui.Modal(context, console).run(_render, _update)
    if outcome is Outcome.CONFIRM:
        return (outcome, menu.selected_id)
    return (outcome, None)

def _run_confirm(context: tcod.context.Context, species_id: str, class_id: str) -> Outcome:
    species = find_species(species_id)
    klass = find_class(class_id)
    console = make_console()

    def _render() -> None:
        ui.render_confirm(console, species, klass, SCREEN_WIDTH, SCREEN_HEIGHT)

    def _update(event) -> Outcome:
        if isinstance(event, tcod.event.Quit):
            return Outcome.QUIT
        action = ui.update_confirm(event)
        if action is ui.MenuAction.CONFIRM:
            return Outcome.CONFIRM
        if action is ui.MenuAction.BACK:
            return Outcome.BACK
        return Outcome.IGNORE
    return ui.Modal(context, console).run(_render, _update)

def _vim_action(event: tcod.event.Event) -> tuple[int, int] | None:
    """If ``event`` is a vim-movement KeyDown, return (dx, dy); else None.

    SDL/tcod reports physical letter key presses as UPPERCASE
    ``KeySym`` members (``KeySym.H.name`` is ``"H"``, not ``"h"`` -
    and ``KeySym.h`` is a Python alias whose ``.name`` is also
    ``"H"``). Without ``.lower()`` every press would miss the
    lowercase-keyed dispatch table and the player would not move.

    The ``getattr(..., "name", "")`` belt-and-suspenders means a
    future tcod build that produces an event whose ``sym`` lacks a
    ``.name`` attribute (e.g. an extension-event subclass) falls
    through to an empty string and returns ``None`` instead of
    crashing with AttributeError.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym_name: str = getattr(event.sym, 'name', '').lower()
    return world.VIM_DELTAS.get(sym_name)

def _is_q_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``Q`` key.

    Routes Q through a module-level helper so the smoke test can
    regression-guard the KeySym name lookup. Mirrors
    :func:`_vim_action`'s pattern of being a pure no-side-effect
    helper, so the dispatcher in :func:`_run_game` stays
    declarative. ``getattr(..., "name", "")`` belt-and-suspenders
    against a hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    return getattr(event.sym, 'name', '') == 'Q'

def _is_m_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``M`` key (or its
    lowercase alias).

    Routes M (map / navigation overlay) through a module-level
    helper so the smoke test can regression-guard the KeySym name
    lookup, mirroring :func:`_is_q_press` exactly. Lowercase ``m``
    and uppercase ``M`` both open the system-map overlay; anything
    else returns False so the dispatcher can route through movement
    + planet-bump handlers.

    Why M and not N: the original implementation used ``N``/``n``,
    but ``n`` is in :data:`world.VIM_DELTAS` as a south-east
    diagonal, so the map overlay silently shadowed vim movement in
    city mode and confused the player. ``M``/``m`` is unused by
    vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('M', 'm')

def _is_period_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``.`` key (period).

    Period = wait one turn. In space mode this triggers the same
    post-move tick logic (combat detection, pirate movement, shield
    regen) without actually moving the player ship.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    return getattr(event.sym, 'name', '') == 'PERIOD'


def _is_g_press(event: tcod.event.Event) -> bool:
    """True iff ``event`` is a ``KeyDown`` for the ``G`` key (or its
    lowercase alias).

    Routes G (goto / auto-nav) through a module-level helper so
    the smoke test can regression-guard the KeySym name lookup,
    mirroring :func:`_is_m_press` exactly. Lowercase ``g`` and
    uppercase ``G`` both open the goto-target overlay; anything
    else returns False so the dispatcher can route through
    movement + planet-bump handlers.

    ``G``/``g`` is unused by vim movement so it's a clean pick.
    ``getattr(..., "name", "")`` belt-and-suspenders against a
    hypothetical tcod build whose ``sym`` lacks ``.name``.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return False
    sym_name: str = getattr(event.sym, 'name', '')
    return sym_name in ('G', 'g')

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

def render_navigation(console: tcod.console.Console, ctx: GameContext, *, screen_width: int, screen_height: int, ship_pos: world.Position, system=None) -> None:
    """Paint the current-solar-system navigation overlay.

    Multi-system iteration: the player is in ONE solar system at a
    time, tracked via :data:`spacehack.solar_system.current_solar_system_id`.
    The overlay reads the current system (or an explicit ``system``
    passthrough for tests) and scales it down so the entire map fits
    inside a centered 50x30 mini-map in the city viewport area.

    Clears first so the overlay FULLY replaces the regular per-frame
    space render while the player has it open. Layout::

      * Title at y=2 (centered) shows the current system's name.
      * Mini-map is centered in the city viewport area:
        ``screen_width - HUD_WIDTH`` wide and
        ``screen_height - MSG_LOG_HEIGHT`` tall (default 80x54).
        The mini-map is ``NAV_MAP_W`` x ``NAV_MAP_H`` (40 x 30) so it
        leaves room for the title + footer below the map.
      * Each mini-cell samples ONE rectangular block of the
        ``system.width`` x ``system.height`` map: ``sample_x =
        system.width / NAV_MAP_W`` and the same for Y. Each block is
        checked across every cell in the (planets + jump_points)
        footprint so the small bodies render reliably. The first
        cell matched lights up with the body's char + fg; empty
        void renders as a faint '.' so the map isn't pure black.
      * The ship's position is converted back to mini-coords
        (``ship_pos.x // sample_x``) and painted as '@' on top of
        whatever the body/void paint already wrote there. They paint
        bodies first, ship last — so a ship over a gate cell reads
        as a ship on top.
      * A footer line shows ``You are at (X, Y).`` + an ESC hint.
    """
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
    Mirrors :func:`update_planet_menu`'s shape so the smoke test can
    verify both share the same input idiom.
    """
    if isinstance(event, tcod.event.Quit):
        return NavigationOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return NavigationOutcome.IGNORE
    if event.sym in ui._ESCAPE_SYMS:
        return NavigationOutcome.BACK
    return NavigationOutcome.IGNORE

def _run_navigation(ctx, ship_pos: world.Position) -> NavigationOutcome:
    """Show the system-map overlay and return the outcome.

    The overlay clears ``console`` first, so the regular space-mode
    render is fully replaced while it stays open. The next non-IGNORE
    outcome is returned and the caller (the space-mode dispatcher in
    :func:`_run_game`) routes on it. The caller is responsible for
    re-painting the regular space render on the next frame after
    this function returns - we don't cache or restore state.
    """
    console = make_console()

    def _render() -> None:
        render_navigation(console, ctx, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, ship_pos=ship_pos)
    return ui.Modal(ctx.context, console).run(_render, update_navigation)


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
    from .data.enemies import find_enemy as _fe
    _spawns = ctx.bounty_spawns.get(system_id, [])
    if not _spawns:
        return
    _system = getattr(solar_system_module, 'current_system', lambda: None)()
    for _bs in _spawns:
        try:
            _espec = _fe(_bs.enemy_id)
        except (KeyError, ImportError):
            continue
        game_map.entities.append(world.Entity(
            char=_espec.char,
            fg=_espec.fg,
            pos=_bs.pos,
            name=_espec.name,
            width=1, height=1,
        ))
        if _system is not None:
            _landmark = _nearest_body_name(_bs.pos, _system)
            ctx.log.add(f"Sensor ping: bounty target detected near {_landmark}.")


def _spawn_procedural_pirates(
    ctx, game_map: world.GameMap, system_id: str,
) -> None:
    """Roll for procedural pirate encounters in ``system_id``.

    Each jump / launch consumes a fresh roll from the game's seeded
    RNG (:data:`spacehack.engine.RNG`). If the system's
    ``pirate_chance`` hits, multiple independent groups may spawn --
    each with its own position, squad id (when >1 member), and
    movement id. This produces a mix of squads and solos scattered
    across the system rather than one monolithic squad.
    """
    from . import engine as _engine
    from .data.enemies import find_enemy as _fe
    from .data.solar_systems import find_solar_system as _fss
    try:
        _system = _fss(system_id)
    except KeyError:
        return
    if _system.pirate_chance <= 0.0 or _system.pirate_density <= 0:
        return
    if _engine.RNG.random() >= _system.pirate_chance:
        return
    try:
        _espec = _fe("pirate_scout")
    except (KeyError, ImportError):
        return
    # Build a set of blocked cells (planets, gates, stations, existing entities).
    _blocked: set[tuple[int, int]] = set()
    for _p in _system.planets:
        for _dy in range(_p.height):
            for _dx in range(_p.width):
                _blocked.add((_p.pos.x + _dx, _p.pos.y + _dy))
    for _jp in _system.jump_points:
        for _dy in range(_jp.height):
            for _dx in range(_jp.width):
                _blocked.add((_jp.pos.x + _dx, _jp.pos.y + _dy))
    for _st in getattr(_system, 'stations', ()) or ():
        for _dy in range(_st.height):
            for _dx in range(_st.width):
                _blocked.add((_st.pos.x + _dx, _st.pos.y + _dy))
    for _e in game_map.entities:
        for _dy in range(_e.height):
            for _dx in range(_e.width):
                _blocked.add((_e.pos.x + _dx, _e.pos.y + _dy))

    # Pick a free cell on the map (shared helper for all groups).
    def _pick_centre() -> tuple[int, int] | None:
        for _attempt in range(200):
            _cx = _engine.RNG.randint(10, _system.width - 10)
            _cy = _engine.RNG.randint(10, _system.height - 10)
            if (_cx, _cy) not in _blocked:
                return (_cx, _cy)
        return None

    # Determine how many independent groups spawn this visit.
    # More dangerous systems spawn more groups.
    # Use density-1 so even density 3 systems get 2 groups max.
    _max_groups = max(1, _system.pirate_density - 1)
    _num_groups = _engine.RNG.randint(1, _max_groups)
    # Distribute the total pirate budget across groups.
    # Each group gets at least 1, leftover rounds down.
    _total_budget = _system.pirate_density
    _group_sizes: list[int] = []
    for _g in range(_num_groups):
        _remaining_groups = _num_groups - _g
        _max_for_this = _total_budget - _remaining_groups + 1  # leave at least 1 for each remaining
        if _max_for_this <= 0:
            break
        _size = _engine.RNG.randint(1, min(5, _max_for_this))
        _group_sizes.append(_size)
        _total_budget -= _size
    if not _group_sizes:
        _group_sizes = [1]

    _total_spawned = 0
    _all_spawns: list = []
    _all_procedural: list = []

    for _g_idx, _g_size in enumerate(_group_sizes):
        _centre = _pick_centre()
        if _centre is None:
            continue
        _gcx, _gcy = _centre
        # Squad id only for groups > 1.
        _squad_id: str | None = (
            f"proc_pirates_{system_id}_{_g_idx}_{_engine.RNG.randint(0, 99999)}"
            if _g_size > 1 else None
        )
        # Movement id always non-empty.
        _movement_id: str = _squad_id or f"proc_solo_{system_id}_{_g_idx}_{_engine.RNG.randint(0, 99999)}"

        _group_entities = 0
        for _i in range(_g_size):
            _x = _y = -1
            for _attempt in range(50):
                _x = _gcx + _engine.RNG.randint(-4, 4)
                _y = _gcy + _engine.RNG.randint(-4, 4)
                if (_x, _y) not in _blocked and 0 <= _x < _system.width and 0 <= _y < _system.height:
                    break
            else:
                continue
            _pos = world.Position(_x, _y)
            _blocked.add((_x, _y))
            game_map.entities.append(world.Entity(
                char=_espec.char, fg=_espec.fg, pos=_pos,
                name=_espec.name, width=1, height=1,
                procedural_squad_id=_movement_id,
            ))
            _all_spawns.append(_pos)
            _all_procedural.append((_pos, _squad_id))
            _group_entities += 1
        _total_spawned += _group_entities

    if _all_spawns:
        from .game_context import ProceduralSpawn as _PS
        ctx.procedural_spawns[system_id] = [
            _PS(
                enemy_id="pirate_scout",
                pos=pos,
                squad_id=sid,
            )
            for pos, sid in _all_procedural
        ]
        ctx.log.add(
            f"Sensor ping: {_total_spawned} unknown contact{('s' if _total_spawned != 1 else '')} detected in the area."
        )


def _move_pirates(ctx, game_map: world.GameMap) -> None:
    """Patrol procedural pirate entities toward planets/gates/stations.

    Called after the player moves in space mode. Each pirate
    squad (or solo) picks a planet, gate, or station and
    commits to moving toward it until within 2 cells, then
    picks a new target. Squad members use the A* path
    computed for the squad leader. Members who can move in
    the squad direction do so (stay in formation). Members
    who are blocked try perpendicular slips to navigate
    around obstacles individually (break formation). Cohesion
    pull-back reels stragglers back toward the squad centre.
    """
    from . import engine as _engine
    # Build goal list from the current system's bodies.
    _system = solar_system_module.current_system()
    _goals: list[tuple[int, int]] = []
    def _body_goal(body) -> tuple[int, int] | None:
        _gx = body.pos.x + body.width + 1
        _gy = body.pos.y + body.height // 2
        if 0 <= _gx < _system.width and 0 <= _gy < _system.height:
            return (_gx, _gy)
        return None
    for _p in _system.planets:
        if getattr(_p, 'sun', False):
            continue
        _g = _body_goal(_p)
        if _g is not None:
            _goals.append(_g)
    for _jp in _system.jump_points:
        _g = _body_goal(_jp)
        if _g is not None:
            _goals.append(_g)
    for _st in getattr(_system, 'stations', ()) or ():
        _g = _body_goal(_st)
        if _g is not None:
            _goals.append(_g)
    if not _goals:
        _any_pirates = any(getattr(_e, 'procedural_squad_id', '') != ''
                           for _e in game_map.entities)
        if _any_pirates:
            ctx.log.add('Sensor: pirates have no navigation targets nearby.')
        return
    _pirate_ents = [_e for _e in game_map.entities
                    if not getattr(_e, 'owned', False)
                    and getattr(_e, 'procedural_squad_id', '') != '']
    _squad_map: dict[str, list] = {}
    for _e in _pirate_ents:
        _squad_map.setdefault(_e.procedural_squad_id, []).append(_e)
    for _sid, _members in _squad_map.items():
        if len(_members) == 0:
            continue
        _is_squad = len(_members) > 1
        _leader = _members[0]
        _target = ctx.pirate_targets.get(_sid)
        _lx, _ly = _leader.pos.x, _leader.pos.y
        _dist_to_target = (
            max(abs(_lx - _target[0]), abs(_ly - _target[1]))
            if _target is not None else 999
        )
        # Refresh target when None or within 2 cells.
        if _target is None or _dist_to_target <= 2:
            _candidates = [g for g in _goals if g != _target]
            if not _candidates:
                _candidates = _goals
            _target = _engine.RNG.choice(_candidates)
            ctx.pirate_targets[_sid] = _target
            # Compute A* path from squad leader to the new target cell.
            _end_set: set[tuple[int, int]] = {_target}
            _path = world.find_path(
                (_lx, _ly), _end_set, game_map,
                exclude_entity=_leader,
            )
            ctx.pirate_paths[_sid] = _path or []
        # Move most ticks for consistent progress (80% chance).
        if _engine.RNG.random() >= 0.8:
            continue
        _path = ctx.pirate_paths.get(_sid)
        if not _path:
            continue
        _next = _path[0]
        _dx = _next[0] - _lx
        _dy = _next[1] - _ly
        # Sanity check: path step must be adjacent.
        if abs(_dx) > 1 or abs(_dy) > 1:
            ctx.pirate_paths[_sid] = []
            continue
        # Try the squad direction for each member. Members who can move
        # in the squad direction do so (stay in formation). Members who
        # are blocked try perpendicular slip-around directions to navigate
        # around obstacles individually (break formation). Cohesion
        # pull-back later reels them in.
        _leader_moved = False
        for _m in _members:
            _nx = _m.pos.x + _dx
            _ny = _m.pos.y + _dy
            if (game_map.is_walkable(_nx, _ny)
                    and game_map.entity_at(_nx, _ny, exclude=_m) is None):
                _m.pos = world.Position(_nx, _ny)
                if _m is _leader:
                    _leader_moved = True
            else:
                # Blocked in squad direction — try perpendicular offsets.
                _slipped = False
                if _dx != 0 and _dy != 0:
                    for _sdx, _sdy in [(_dx, 0), (0, _dy)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            _slipped = True
                            break
                elif _dx != 0:
                    for _sdx, _sdy in [(_dx, 1), (_dx, -1)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            _slipped = True
                            break
                else:  # _dy != 0
                    for _sdx, _sdy in [(1, _dy), (-1, _dy)]:
                        _snx = _m.pos.x + _sdx
                        _sny = _m.pos.y + _sdy
                        if (game_map.is_walkable(_snx, _sny)
                                and game_map.entity_at(_snx, _sny, exclude=_m) is None):
                            _m.pos = world.Position(_snx, _sny)
                            _slipped = True
                            break
                # If no slip direction works member stays put (furthest break).
        if _leader_moved:
            ctx.pirate_paths[_sid].pop(0)
        # Squad cohesion: pull stragglers toward centre
        if _is_squad:
            _cx = sum(m.pos.x for m in _members) // len(_members)
            _cy = sum(m.pos.y for m in _members) // len(_members)
            for _m in _members:
                if max(abs(_m.pos.x - _cx), abs(_m.pos.y - _cy)) > 4:
                    _pull_x = _cx + (1 if _m.pos.x < _cx else -1 if _m.pos.x > _cx else 0)
                    _pull_y = _cy + (1 if _m.pos.y < _cy else -1 if _m.pos.y > _cy else 0)
                    if (game_map.is_walkable(_pull_x, _pull_y)
                        and game_map.entity_at(_pull_x, _pull_y, exclude=_m) is None):
                        _m.pos = world.Position(_pull_x, _pull_y)


def _pick_bounty_spawn_pos(system) -> world.Position | None:
    """Return a free-space position in ``system`` for placing a bounty
    target enemy. Prefers a cell near the first non-sun planet, falling
    back to the first jump gate or a centre-of-map position.

    Returns ``None`` if the system has no bodies (shouldn't happen
    with the current data).
    """
    # Try first non-sun planet: offset by (planet.width + 3, 0) cells
    # so the bounty sits east of the planet in clear space.
    for p in system.planets:
        if getattr(p, 'sun', False):
            continue
        sx = p.pos.x + p.width + 3
        sy = p.pos.y + p.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            return world.Position(sx, sy)
    # Fallback: first jump gate
    for jp in system.jump_points:
        sx = jp.pos.x + jp.width + 6
        sy = jp.pos.y + jp.height // 2
        if 0 <= sx < system.width and 0 <= sy < system.height:
            return world.Position(sx, sy)
    # Last resort: centre-ish of the map
    return world.Position(system.width // 2, system.height // 2)


def _remove_bounty_spawn(ctx, spawn_id: str, system_id: str | None) -> None:
    """Remove the bounty spawn with ``spawn_id`` from
    ``ctx.bounty_spawns[system_id]``, and from the current
    ``ctx.game_map.entities`` if the player is in that system.

    No-op if the spawn doesn't exist (e.g. was already removed).
    """
    if system_id is None or system_id not in ctx.bounty_spawns:
        return
    # Snapshot the spawn's position before filtering it out.
    _pos_to_remove = None
    for _bs in ctx.bounty_spawns[system_id]:
        if _bs.spawn_id == spawn_id:
            _pos_to_remove = _bs.pos
            break
    ctx.bounty_spawns[system_id] = [
        _bs for _bs in ctx.bounty_spawns[system_id]
        if _bs.spawn_id != spawn_id
    ]
    if _pos_to_remove is not None:
        # Also remove the matching entity from the game_map if the
        # player is currently in the spawn's system.
        _cur_sys = getattr(solar_system_module.current_system(), 'id', None)
        if _cur_sys == system_id and ctx.game_map is not None:
            _target_entity = None
            for _e in ctx.game_map.entities:
                if not getattr(_e, 'owned', False) and _e.pos == _pos_to_remove:
                    _target_entity = _e
                    break
            if _target_entity is not None:
                try:
                    ctx.game_map.entities.remove(_target_entity)
                except ValueError:
                    pass


def _detect_combat_encounter(ctx, player_pos: world.Position, system: object) -> tuple[list, list[world.Position]] | None:
    """Run the squad-aware enemy scan and return combat payload, or ``None``.

    Extracted from the post-move dispatcher block so both the normal
    space-walker and the auto-nav animation loop can call the same
    logic. Two-pass design: pass 1 marks alive enemy spawns within
    ``detect_radius`` as triggered (squad or solo), pass 2 builds
    the encounter payload for any spawn whose squad was triggered
    OR whose own position was triggered as a solo. Returns
    ``(specs, positions)`` if any spawn was triggered, else ``None``.

    Also checks :attr:`ctx.bounty_spawns` so dynamically-placed
    bounty targets trigger combat the same way as static enemies.

    Function-level ``from .data.enemies import ...`` import avoids a
    top-level circular import on the data module.
    """
    from .data.enemies import find_enemy as _fe
    _enemy_spawns = getattr(system, 'enemies', ()) or ()
    _alive_spawns: list = []
    _triggered_squad_ids: set = set()
    _triggered_solo_positions: set = set()
    # Check static system spawns.
    for _spawn in _enemy_spawns:
        try:
            _espec = _fe(_spawn.enemy_id)
        except KeyError:
            continue
        _enemy_alive = any((_e for _e in ctx.game_map.entities if not getattr(_e, 'owned', False) and _e.pos.x == _spawn.pos.x and (_e.pos.y == _spawn.pos.y)))
        if not _enemy_alive:
            continue
        _alive_spawns.append((_spawn, _espec))
        _dist = math.hypot(player_pos.x - _spawn.pos.x, player_pos.y - _spawn.pos.y)
        if _dist <= _espec.detect_radius:
            if _spawn.squad_id is not None:
                _triggered_squad_ids.add(_spawn.squad_id)
            else:
                _triggered_solo_positions.add((_spawn.pos.x, _spawn.pos.y))
    # Also check bounty spawns (dynamic targets placed on accept).
    _system_id = getattr(system, 'id', '')
    _bounty_spawns = ctx.bounty_spawns.get(_system_id, [])
    for _bs in _bounty_spawns:
        try:
            _espec = _fe(_bs.enemy_id)
        except KeyError:
            continue
        _enemy_alive = any((_e for _e in ctx.game_map.entities if not getattr(_e, 'owned', False) and _e.pos.x == _bs.pos.x and (_e.pos.y == _bs.pos.y)))
        if not _enemy_alive:
            continue
        # Treat bounty spawns as solo (no squad support).
        _alive_spawns.append((_bs, _espec))
        _dist = math.hypot(player_pos.x - _bs.pos.x, player_pos.y - _bs.pos.y)
        if _dist <= _espec.detect_radius:
            _triggered_solo_positions.add((_bs.pos.x, _bs.pos.y))
    # Also check procedural pirates by current entity positions.
    # Don't use ctx.procedural_spawns — those store the original
    # spawn positions. Pirates move, so those positions are stale
    # and combat detection would fail entirely. Instead scan the
    # game_map for unowned entities with a procedural_squad_id tag.
    _procedural_entities = [
        _e for _e in ctx.game_map.entities
        if not getattr(_e, 'owned', False)
        and getattr(_e, 'procedural_squad_id', '') != ''
    ]
    for _pe in _procedural_entities:
        try:
            _espec = _fe("pirate_scout")
        except (KeyError, ImportError):
            continue
        _alive_spawns.append((_pe, _espec))
        _dist = math.hypot(player_pos.x - _pe.pos.x, player_pos.y - _pe.pos.y)
        if _dist <= _espec.detect_radius:
            # All procedural pirates share their movement squad ID
            # (unique per solo, shared per squad). Use it for squad
            # grouping in combat.
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

def _run_goto(ctx, player_entity: world.Entity) -> tuple[GotoOutcome, tuple[list, list[world.Position]] | None]:
    """Open a GO TO modal listing interactable space bodies, then
    auto-navigate the player's ship to a cell adjacent to the chosen
    target using BFS pathfinding + step-by-step animation.

    TODO(P3): intentionally NOT migrated to :class:`spacehack.ui.Modal`.
    The body mixes the menu-pick phase with a Bresenham/A* animation
    phase that calls :func:`_responsive_sleep` between steps + checks
    for combat breakout mid-animation. The Modal helper assumes
    render-wait-return semantics; multi-phase animation doesn't fit.
    Leave as-is until we either generalize Modal to support a
    custom in-loop body or extract the animation into its own
    helper that the post-pick dispatcher calls.

    Returns ``(outcome, combat_data)``:
    * ``(GotoOutcome.COMPLETED, None)`` — the ship reached the
      destination normally.
    * ``(GotoOutcome.CANCELLED, None)`` — player backed out, no
      valid destinations, no path found, or the Bresenham line
      had no walkable cells.
    * ``(GotoOutcome.COMBAT, (specs, positions))`` — the auto-nav
      animation crossed into an enemy patrol's ``detect_radius``
      mid-flight and broke early so the dispatcher can invoke
      combat from the ship's CURRENT position. ``combat_data`` is
      suitable for direct hand-off to ``combat._handle_combat_encounter`` (see combat.py).

    The combat break is the v1-of-fix for the bug where the
    animated ship walked right through a pirate patrol without
    triggering combat. See :class:`GotoOutcome` for the full
    history. The post-step scan uses the same helper
    (:func:`_detect_combat_encounter`) as the regular move
    dispatcher so the two paths can't drift apart.

    The pre-step destination frame still uses the original
    destination so the player can override the encounter with
    ESC if they wish before any further step is animated.
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
        title = 'GO TO'
        console.print(x=ui.centered_x(title, SCREEN_WIDTH), y=SCREEN_HEIGHT // 4, string=title, fg=ui.COLOR_TITLE)
        list_top = SCREEN_HEIGHT // 4 + 2
        for i, (label, _body) in enumerate(destinations):
            row = list_top + i * 2
            is_selected = i == selected
            marker_open = '> ' if is_selected else '  '
            marker_close = ' <' if is_selected else '  '
            text = f'{marker_open}{label}{marker_close}'
            fg = ui.COLOR_OPTION_HIGHLIGHT if is_selected else ui.COLOR_OPTION
            console.print(x=ui.centered_x(text, SCREEN_WIDTH), y=row, string=text, fg=fg)
        hint = 'ARROW KEYS / j,k navigate - ENTER go - ESC cancel'
        console.print(x=ui.centered_x(hint, SCREEN_WIDTH), y=list_top + n * 2 + 1, string=hint, fg=ui.COLOR_INSTRUCTION)
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        ctx.context.present(console)
        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                return (GotoOutcome.CANCELLED, None)
            if not isinstance(event, tcod.event.KeyDown):
                continue
            sym = event.sym
            sym_name: str = getattr(sym, 'name', '').lower()
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
                    """Yield cells on a line from (x0,y0) to (x1,y1),
                    EXCLUDING the start cell. Standard Bresenham's."""
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
                    """True if (x,y) is walkable and not inside
                    another body's footprint (excluding the chosen
                    body)."""
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
                    message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
                    ctx.context.present(console)
                    # Sleep with event polling: movement/period keys abort auto-nav.
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
                    _encounter = _detect_combat_encounter(ctx, player_entity.pos, solar_system_module.current_system())
                    if _encounter is not None:
                        ctx.log.add('Auto-nav interrupted - enemies detected!')
                        return (GotoOutcome.COMBAT, _encounter)
                    # Move pirates one step per auto-nav tick.
                    _move_pirates(ctx, ctx.game_map)
                ctx.log.add('Auto-nav complete.')
                return (GotoOutcome.COMPLETED, None)
            continue

def render_jump_menu(console: tcod.console.Console, ctx: GameContext, jp, target_system_id: str, *, screen_width: int, screen_height: int, current_fuel: int | None=None, max_fuel: int | None=None, jump_fuel_cost: int=10) -> None:
    """Paint the jump-point-bump dialog.

    Centered title (gate name + arrow), fuel info line (when
    ``current_fuel`` is provided), wrapped description, and a
    single highlighted option ``> Jump to <target_system_name> <``
    plus a hint. Mirror of :func:`render_planet_menu`'s shape so
    the two dialogs read as the same UI family.

    The dialog is read-only: there's nothing else to choose
    between in v1 (each gate connects to a single system). A
    future iteration with multi-hop gates would put a list here.

    When ``current_fuel`` is not None the dialog paints a fuel
    status line between the description and the option, e.g.
    ``Fuel: 90 / 100 | Jump cost: 10``. The player can see at a
    glance whether they have enough fuel to jump without having
    to open the ship stats first.
    """
    target_system = solar_systems_module.find_solar_system(target_system_id)
    console.clear()
    title = f'JUMP  -  {jp.name}  ->  {target_system.name}'
    title_y = screen_height // 2 - 4
    console.print(x=ui.centered_x(title, screen_width), y=title_y, string=title, fg=ui.COLOR_TITLE)
    desc_lines = ui.wrap_text(jp.description or '', max_width=screen_width - 8)
    for i, line in enumerate(desc_lines[:3]):
        console.print(x=ui.centered_x(line, screen_width), y=title_y + 2 + i, string=line, fg=ui.COLOR_DESCRIPTION)
    option_text = f'> Jump to {target_system.name} <'
    option_y = screen_height // 2 + 1
    fuel_line_y = option_y - 2
    if current_fuel is not None and max_fuel is not None:
        fuel_str = f'Fuel: {current_fuel} / {max_fuel}  |  Jump cost: {jump_fuel_cost}'
        fuel_color = ui.COLOR_OPTION_HIGHLIGHT if current_fuel >= jump_fuel_cost else ui.COLOR_VALUE_DIM
        console.print(x=ui.centered_x(fuel_str, screen_width), y=fuel_line_y, string=fuel_str, fg=fuel_color)
    console.print(x=ui.centered_x(option_text, screen_width), y=option_y, string=option_text, fg=ui.COLOR_OPTION_HIGHLIGHT)
    hint = 'ENTER to jump - ESC to fly past'
    console.print(x=ui.centered_x(hint, screen_width), y=option_y + 2, string=hint, fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)

def update_jump_menu(event: tcod.event.Event) -> JumpMenuOutcome:
    """Translate a key into a :class:`JumpMenuOutcome`.

    Mirror of :func:`update_planet_menu`. ESC -> BACK, ENTER
    -> JUMP, Q/WINDOW_CLOSE -> QUIT, everything else -> IGNORE.
    """
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
    """Modal loop for the jump-point-bump dialog.

    Renders the frame, polls events through
    :func:`update_jump_menu`, returns on the first
    non-:attr:`JumpMenuOutcome.IGNORE` outcome. Mirrors
    :func:`_run_planet_menu`'s shape so the dispatcher can
    swap between them without bespoke plumbing.

    ``owned_ship`` is optional; when provided the fuel info line
    (fuel / max fuel / jump cost) is shown in the dialog so the
    player sees their fuel status at a glance.
    """
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
        ctx.context.convert_event(event)
        return update_jump_menu(event)
    return ui.Modal(ctx.context, console).run(_render, _update)

def _run_cargo_scan(ctx, planet_id: str) -> None:
    """Check the player's cargo for contraband when landing on a
    planet with a militia presence.

    If the planet has a building labeled ``"militia"`` there is a
    40% chance the militia runs a scan.  When contraband is
    found every contraband crate is confiscated and a fine equal
    to 50% of the goods' total base value is deducted from
    the player's credits.

    Logs the outcome either way so the player understands what
    happened (or didn't happen).
    """
    from .data.trade_goods import find_trade_good as _ftg
    from . import engine as _engine

    owned = ctx.player_owned_ship
    if owned is None:
        return

    # Does this planet have a militia building?
    from .data.planets import find_planet_spec
    try:
        spec = find_planet_spec(planet_id)
    except KeyError:
        return
    _has_militia = any(b.label == "militia" for b in spec.buildings)
    if not _has_militia:
        return

    # Roll against the 40% scan probability.
    if _engine.RNG.random() >= 0.4:
        return

    # Find contraband in cargo.
    _confiscated: list[tuple[str, int, int]] = []  # (good_id, qty, value)
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

    # Confiscate: remove goods and deduct fine.
    _total_fine = 0
    for gid, qty, fine in _confiscated:
        good = _ftg(gid)
        ctx.log.add(f"Contraband {good.name} x{qty} confiscated by militia!")
        _total_fine += fine
        remaining = owned.inventory.get(gid, 0) - qty
        if remaining <= 0:
            if gid in owned.inventory:
                del owned.inventory[gid]
        else:
            owned.inventory[gid] = remaining

    ctx.stats.credits = max(0, ctx.stats.credits - _total_fine)
    ctx.log.add(f"Militia levies a fine of {_total_fine}$ for contraband.")


def _responsive_sleep(seconds: float) -> None:
    """Sleep for ``seconds`` while polling SDL events.

    Breaks the sleep into ~0.01 s chunks and calls
    ``tcod.event.poll()`` on each iteration so SDL can
    process OS-level events (mouse moves, window updates,
    etc.). Without this, macOS shows the spinning beach
    ball during animation loops that block with
    ``time.sleep``.

    The animation timing stays the same — the total delay
    is ``seconds`` regardless of how many poll cycles run.
    """
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for _ in tcod.event.get():
            pass
        remaining = end - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, 0.01))
_JUMP_FRAME_S: float = 0.06
_JUMP_RING_CHARS: tuple[tuple[str, tuple[int, int, int]], ...] = (('*', (255, 200, 100)), ('+', (255, 255, 150)), ('o', (255, 255, 200)), ('O', (200, 200, 255)), ('#', (180, 180, 255)))

def _animate_jump(ctx, console: tcod.console.Console, player_entity: world.Entity, *, active_mission_text: str = '') -> None:
    """Render a brief "jump drive" animation before the system swap.

    Draws the current space view with an expanding bright explosion
    centered on ``player_entity``'s position. The animation has
    three phases:

      1. Ship pulsates brighter (3 frames, increasing brightness)
      2. Explosion expands outward in concentric rings (5 frames,
         each adding one more ring via ``_JUMP_RING_CHARS``)
      3. Full-screen white flash (1 frame) then brief black (1 frame)

    The total run is ~1.2 s, long enough to feel dramatic without
    overstaying its welcome.
    """
    frame_s = _JUMP_FRAME_S
    cx = player_entity.pos.x + (player_entity.width - 1) // 2
    cy = player_entity.pos.y + (player_entity.height - 1) // 2
    ship_char = player_entity.char
    ship_fg = player_entity.fg

    def _render_frame(rings: int, flash_white: bool=False, void: bool=False) -> None:
        """Render one frame of the animation."""
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
        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT, character=ctx.character_info, stats=ctx.stats, active_mission=active_mission_text or None)
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

    v1 ships instant-cut transitions: log "Your ship engages the
    jump drive. Reality blurs.", call
    :func:`solar_system_module.set_current_solar_system` (which
    flips module-level state so all subsequent helpers pick up
    the destination system), build a fresh
    :func:`world.GameMap` for the destination system, place the
    player's owned ship just east of the destination gate (per
    :func:`solar_system_module.place_jumped_ship`), and log
    "You emerge near <destination system>.".

    Also injects any active bounty spawn entities for the target
    system via :func:`_add_bounty_spawns_to_map` so bounty targets
    that were accepted in a different system appear on arrival.

    Returns ``(new_map, new_ship_ent)`` — the freshly built
    :class:`world.GameMap` plus the ship :class:`world.Entity` the
    dispatcher should rebind to as the new ``player``. Mirrors
    :func:`_launch_to_space`'s ``(space_map, space_player)`` shape
    so the dispatcher's existing ``game_map, player = ...``
    rebinds both in one line. Rebinding ``player`` (rather than
    just updating ``player.pos``) is critical because the previous
    attempt left the visible ship entity in ``new_map.entities``
    but kept the dispatcher's ``player`` variable pointing at the
    old city-@ entity; ``try_move(player, ...)'' would advance the
    *@* on a map we no longer render, so the visible ship glyph
    would never move. After this fix, ``player`` IS the ship
    entity and ``player.pos`` mirrors the ship-on-map.
    """
    from . import ship as ship_module_for_jump
    ctx.log.add('Your ship engages the jump drive. Reality blurs.')
    target_system = solar_system_module.set_current_solar_system(target_system_id)
    new_map = solar_system_module.make_solar_system()
    _add_bounty_spawns_to_map(ctx, new_map, target_system_id)
    _spawn_procedural_pirates(ctx, new_map, target_system_id)
    dest_jp = solar_system_module.find_jump_point(target_jp_id, system=target_system)
    ship_record = ship_module_for_jump.find_ship(ctx.player_owned_ship.ship_id)
    new_pos = solar_system_module.place_jumped_ship(ship_record, dest_jp)
    new_ship_ent = world.Entity(char=ship_record.char, fg=ship_record.fg, pos=new_pos, name=f'Your Ship: {ship_record.name}', ship_id=ship_record.id, width=ship_record.width, height=ship_record.height, owned=True)
    new_map.entities.append(new_ship_ent)
    ctx.log.add(f'You emerge near {target_system.name}.')
    return (new_map, new_ship_ent)

def render_ship_buy(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, *, screen_width: int, screen_height: int) -> None:
    """Paint the centered ship-buy dialog into ``console``.

    Clears first so the dialog fully replaces the city view; the
    caller re-paints city + HUD + msg log once the dialog exits.
    """
    console.clear()
    title = f'A {ship.name.upper()} sits on the showroom floor.'
    body = ship.description
    price_line = f'Cost: {ship.price}$    You have: {ctx.stats.credits}$'
    if ctx.stats.credits >= ship.price:
        afford = 'Press ENTER to buy it.'
    else:
        short = ship.price - ctx.stats.credits
        afford = f'You cannot afford it. ({short}$ short)'
    back = 'Press ESC to walk away.'
    max_w = screen_width - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + '…'

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)
    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    paint(center_y - 4, fit(title), fg=ui.COLOR_TITLE)
    paint(center_y - 1, fit(body), fg=ui.COLOR_DESCRIPTION)
    paint(center_y + 3, fit(price_line), fg=ui.COLOR_VALUE_WHITE if ctx.stats.credits >= ship.price else ui.COLOR_VALUE_DIM)
    paint(center_y + 5, fit(afford), fg=ui.COLOR_OPTION_HIGHLIGHT if ctx.stats.credits >= ship.price else ui.COLOR_VALUE_DIM)
    paint(center_y + 7, fit(back), fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)

def update_ship_buy(event: tcod.event.Event, ship: ship_module.Ship, stats: hud.HudStats) -> ShipBuyOutcome:
    """Map a single event for the ship-buy dialog."""
    if isinstance(event, tcod.event.Quit):
        return ShipBuyOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipBuyOutcome.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return ShipBuyOutcome.BACK
    if sym in ui._ENTER_SYMS:
        return ShipBuyOutcome.BUY if stats.credits >= ship.price else ShipBuyOutcome.TOO_EXPENSIVE
    return ShipBuyOutcome.IGNORE

def _run_ship_buy(ctx, blocker: world.Entity, ship: ship_module.Ship) -> ShipBuyOutcome:
    """Show the ship-buy modal for ``ship`` (the entity standing in
    the player's way is ``blocker``). Returns the dialog outcome;
    callers handle the actual purchase (mutating ``stats``, removing
    ``blocker`` from ``game_map.entities``, logging).
    """
    console = make_console()

    def _render() -> None:
        render_ship_buy(console, ctx, ship, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> ShipBuyOutcome:
        return update_ship_buy(event, ship, ctx.stats)
    return ui.Modal(ctx.context, console).run(_render, _update)


class MissionOutcome(Enum):
    """What the player chose in an NPC's mission offering modal.

    ``ACCEPT`` carries the picked :class:`spacehack.mission.Mission`
    back to the caller so :func:`_run_game` can slot it into the
    ``player_active_mission`` single-slot state.
    """
    IGNORE = auto()
    ACCEPT = auto()
    BACK = auto()

class QuestLogOutcome(Enum):
    """What the player chose in the city quest log.

    ``ABANDONED`` carries the abandoned mission's title back so
    :func:`_run_game` can log a "You abandoned ..." line; the
    caller is responsible for clearing ``player_active_mission``
    since this enum doesn't have access to the world state.
    """
    IGNORE = auto()
    BACK = auto()
    ABANDONED = auto()
    QUIT = auto()

def _offerings_to_menu(npc: npc_module.NPC, offerings: tuple[mission_module.Mission, ...]) -> tuple[str, tuple[tuple[str, str], ...], dict[str, str]]:
    """Build an :class:`spacehack.ui.MenuScreen` payload from an
    NPC-mission-list so we can reuse the shared menu primitives.

    ``available_options`` is ``(id, label)`` where label is
    ``"{title} ({reward}gp)"`` so the player sees the reward in
    the listing. ``descriptions`` is the mission body blurb.
    """
    available_options = tuple(((str(i), f'{m.title} ({m.reward_credits}$)') for i, m in enumerate(offerings)))
    descriptions = {str(i): m.description for i, m in enumerate(offerings)}
    return (f'{npc.name} - available work', available_options, descriptions)

def render_mission_offerings(console: tcod.console.Console, ctx: GameContext, npc: npc_module.NPC, offerings: tuple[mission_module.Mission, ...], selected: int, *, screen_width: int, screen_height: int) -> None:
    """Paint the NPC's available missions as a centered menu.

    ``selected`` is the index of the highlighted option (clamped
    by caller-supplied modulo wrap, so any int is safe). The list
    of missions themselves lives in :mod:`spacehack.mission`.
    """
    console.clear()
    title, options, descriptions = _offerings_to_menu(npc, offerings)
    n = len(options)
    max_w = screen_width - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + '…'

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)
    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    paint(center_y - 6, fit(title), fg=ui.COLOR_TITLE)
    sel = selected % n if n else 0
    list_top = center_y - 4
    for i, (_, label) in enumerate(options):
        row = list_top + i * 2
        is_selected = i == sel
        marker = '> ' if is_selected else '  '
        end_marker = ' <' if is_selected else '  '
        text = f'{marker}{fit(label)}{end_marker}'
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=ui.COLOR_OPTION_HIGHLIGHT if is_selected else ui.COLOR_OPTION)
    desc = descriptions.get(str(sel), '') if descriptions else ''
    desc_rows = ui.wrap_text(desc, max_w)
    desc_start_row = list_top + n * 2 + 1
    for j, line in enumerate(desc_rows):
        paint(desc_start_row + j, line, fg=ui.COLOR_DESCRIPTION)
    hint_lines: list[str] = ['ARROW KEYS / j,k navigate - ENTER accept - ESC walk away.']
    if offerings:
        picked = offerings[sel]
        hint_lines.append(f'Reward: {picked.reward_credits}$ + {picked.reward_xp}xp')
        if picked.recommended_class_id:
            klass = find_class(picked.recommended_class_id)
            hint_lines.append(f'Best suited for: {klass.name}')
        if picked.recommended_ship_min_cargo > 0:
            hint_lines.append(f'Ship cargo recommended: {picked.recommended_ship_min_cargo}+')
    for i, line in enumerate(hint_lines):
        paint(desc_start_row + max(len(desc_rows), 1) + 1 + i, fit(line), fg=ui.COLOR_INSTRUCTION)

def update_mission_offerings(event: tcod.event.Event) -> MissionOutcome:
    """Map a single event for the offerings modal.

    Pure dispatcher: UP/DOWN navigation is handled by the caller
    (it owns the ``selected`` int via :func:`_mission_navigate`,
    which mirrors :func:`_ship_menu_navigate` so the smoke test
    can verify both share the same input idiom). Enter -> ACCEPT,
    ESC -> BACK, anything else -> IGNORE.
    """
    if isinstance(event, tcod.event.Quit):
        return MissionOutcome.BACK
    if not isinstance(event, tcod.event.KeyDown):
        return MissionOutcome.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return MissionOutcome.BACK
    if sym in ui._ENTER_SYMS:
        return MissionOutcome.ACCEPT
    return MissionOutcome.IGNORE

def _mission_navigate(event: tcod.event.Event, selected: int, n: int) -> int | None:
    """If ``event`` drives offerings-menu nav, return the new
    ``selected`` index (modulo ``n`` options). Returns ``None``
    for non-nav events so the caller routes through
    :func:`update_mission_offerings`. Mirrors
    :func:`_ship_menu_navigate` so the keyboard idioms stay
    consistent across modals.
    """
    if n <= 0:
        return None
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym = event.sym
    sym_name: str = getattr(sym, 'name', '').lower()
    if sym in ui._UP_SYMS or sym_name == 'k':
        return (selected - 1) % n
    if sym in ui._DOWN_SYMS or sym_name == 'j':
        return (selected + 1) % n
    return None

def _run_mission_offerings(ctx, npc: npc_module.NPC, offerings: tuple[mission_module.Mission, ...]) -> tuple[MissionOutcome, mission_module.Mission | None]:
    """Show the NPC's offerings modal and return the choice.

    Returns ``(MissionOutcome, picked_mission)``: ``picked`` is
    ``None`` whenever the outcome is not ACCEPT. The caller
    (:func:`_run_game`) is responsible for swapping
    ``player_active_mission`` once it sees an ACCEPT.
    """
    console = make_console()
    selected = 0

    def _render() -> None:
        render_mission_offerings(console, ctx, npc, offerings, selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> MissionOutcome:
        nonlocal selected
        new = _mission_navigate(event, selected, len(offerings))
        if new is not None:
            selected = new
            return MissionOutcome.IGNORE
        return update_mission_offerings(event)
    outcome = ui.Modal(ctx.context, console).run(_render, _update)
    if outcome is MissionOutcome.ACCEPT:
        return (outcome, offerings[selected % len(offerings)])
    return (outcome, None)

def render_quest_log(console: tcod.console.Console, ctx: GameContext, *, confirm_abandon: bool=False, screen_width: int, screen_height: int) -> None:
    """Paint the city quest-log overlay.

    Two visual states:

      * ``confirm_abandon`` False - shows the active mission's full
        details and the "Press A to abandon. ESC to close." hint.
      * ``confirm_abandon`` True - swaps in "Press ENTER to abandon.
        ESC cancels." so the player has a single-step confirmation
        only when committing to abandon (not when viewing). The
        two-step pattern keeps the cost of a stray keypress low.

    If there is no active mission, draws "(no active mission)" + ESC
    hint and the abandon confirmation is irrelevant.
    """
    console.clear()
    max_w = screen_width - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + '…'

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)
    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    if ctx.player_active_mission is None:
        paint(center_y - 2, fit('QUEST LOG'), fg=ui.COLOR_TITLE)
        paint(center_y + 1, fit('(no active mission)'), fg=ui.COLOR_DESCRIPTION)
        paint(center_y + 5, fit('Press ESC to close.'), fg=ui.COLOR_INSTRUCTION)
        message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)
        return
    mission = mission_module.find_mission(ctx.player_active_mission.mission_id)
    giver = npc_module.find_npc(mission.giver_npc_id)
    paint(center_y - 6, fit('QUEST LOG'), fg=ui.COLOR_TITLE)
    paint(center_y - 3, fit(mission.title.upper()), fg=ui.COLOR_TITLE)
    paint(center_y - 1, fit(f'From: {giver.name} ({giver.guild})'), fg=ui.COLOR_DESCRIPTION)
    desc_rows = ui.wrap_text(mission.description, max_w)
    desc_start_row = center_y + 2
    for j, line in enumerate(desc_rows):
        paint(desc_start_row + j, line, fg=ui.COLOR_VALUE_WHITE)
    reward_row = desc_start_row + len(desc_rows) + 1
    paint(reward_row, fit(f'Reward: {mission.reward_credits}$ + {mission.reward_xp}xp'), fg=ui.COLOR_VALUE_WHITE)
    button_row = reward_row + 3
    if confirm_abandon:
        paint(button_row, fit('Press ENTER to abandon. ESC cancels.'), fg=ui.COLOR_OPTION_HIGHLIGHT)
    else:
        paint(button_row, fit('Press A to abandon. ESC to close.'), fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)

def update_quest_log(event: tcod.event.Event, *, confirm_abandon: bool) -> QuestLogOutcome:
    """Map a single event for the quest-log overlay.

    Two states - when ``confirm_abandon`` is False, only ESC and A
    do anything (ESC -> BACK, A -> ABANDONED so the caller can
    clear ``player_active_mission`` in one place). When
    ``confirm_abandon`` is True, ENTER confirms (ABANDONED), ESC
    cancels (BACK). Quit exits early as QUIT regardless of state.

    The render + this dispatcher own the 2-step state internally;
    no state escapes the modal, so the new HUD-styling rules don't
    rely on player_active_mission state outside :func:`_run_game`.
    """
    if isinstance(event, tcod.event.Quit):
        return QuestLogOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return QuestLogOutcome.IGNORE
    sym = event.sym
    sym_name: str = getattr(sym, 'name', '').lower()
    if sym in ui._ESCAPE_SYMS:
        return QuestLogOutcome.BACK
    if confirm_abandon:
        if sym in ui._ENTER_SYMS:
            return QuestLogOutcome.ABANDONED
        return QuestLogOutcome.IGNORE
    if sym_name == 'a':
        return QuestLogOutcome.ABANDONED
    return QuestLogOutcome.IGNORE

def _run_quest_log(ctx) -> tuple[QuestLogOutcome, mission_module.ActiveMission | None]:
    """Show the city quest-log overlay and apply any state changes.

    Returns ``(outcome, maybe_new_active)``: ``maybe_new_active`` is
    ``None`` when the player confirmed ABANDONED (so the caller
    wipes its own copy), or it points back at the same
    ``ActiveMission`` instance for every other outcome. Decoupling
    the assignment this way means the caller's bookkeeping is the
    ONE place where ``player_active_mission`` is mutated.
    """
    console = make_console()
    confirm_abandon = False

    def _render() -> None:
        render_quest_log(console, ctx, confirm_abandon=confirm_abandon, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> QuestLogOutcome:
        nonlocal confirm_abandon
        result = update_quest_log(event, confirm_abandon=confirm_abandon)
        if result is QuestLogOutcome.ABANDONED and (not confirm_abandon):
            confirm_abandon = True
            return QuestLogOutcome.IGNORE
        return result
    outcome = ui.Modal(ctx.context, console).run(_render, _update)
    if outcome is QuestLogOutcome.ABANDONED:
        return (outcome, None)
    return (outcome, ctx.player_active_mission)
SHIP_MENU_OPTIONS: tuple[str, ...] = ('View', 'Refuel', 'Sell', 'Launch')
PLANET_MENU_OPTIONS: tuple[str, ...] = ('Land',)

def render_ship_menu(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, selected: int=0, *, screen_width: int, screen_height: int) -> None:
    """Paint the centered 3-option hangar menu into ``console``.

    ``selected`` is the index of the highlighted option (clamped by
    :func:`_ship_menu_navigate`'s modulo wrap, so callers can pass
    any int and the renderer will handle the wrap). Clears first
    so the modal fully replaces the city view; the caller re-paints
    city + HUD + msg log once the modal exits. Options are wrapped
    in ``>`` / ``<`` markers so the selected option reads the same
    way as the species / class menus (consistency so the player
    only learns one highlight idiom).
    """
    console.clear()
    title = f'Your {ship.name.upper()}'
    sub = ship.description
    if ctx.player_owned_ship is None:
        sub = '(no ship owned yet)'
    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    console.print(x=ui.centered_x(title, screen_width), y=center_y - 5, string=title, fg=ui.COLOR_TITLE)
    console.print(x=ui.centered_x(sub, screen_width), y=center_y - 3, string=sub, fg=ui.COLOR_DESCRIPTION)
    if ctx.player_owned_ship is not None:
        fuel_str = f'Fuel: {ctx.player_owned_ship.fuel} / {ship.max_fuel}  [Refuel: {ship_module.FUEL_COST_PER_UNIT}$/u]'
        console.print(x=ui.centered_x(fuel_str, screen_width), y=center_y - 1, string=fuel_str, fg=ui.COLOR_VALUE_WHITE)
    list_top = center_y + 1 if ctx.player_owned_ship is not None else center_y - 1
    n = len(SHIP_MENU_OPTIONS)
    sel = selected % n
    for i, label in enumerate(SHIP_MENU_OPTIONS):
        row = list_top + i * 2
        is_selected = i == sel
        marker = '> ' if is_selected else '  '
        end_marker = ' <' if is_selected else '  '
        if label == 'Refuel' and ctx.player_owned_ship is not None:
            label = f'{label} [{ctx.player_owned_ship.fuel}/{ship.max_fuel}]'
        text = f'{marker}{label}{end_marker}'
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=ui.COLOR_OPTION_HIGHLIGHT if is_selected else ui.COLOR_OPTION)
    console.print(x=ui.centered_x('ARROW KEYS / j,k navigate - ENTER select - ESC walk away.', screen_width), y=center_y + len(SHIP_MENU_OPTIONS) * 2 + 1, string='ARROW KEYS / j,k navigate - ENTER select - ESC walk away.', fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)

def _ship_menu_navigate(event: tcod.event.Event, selected: int) -> int | None:
    """If ``event`` drives hangar-menu nav, return the new
    ``selected`` index (modulo :data:`SHIP_MENU_OPTIONS` length).

    Recognises both the standard arrow keys (UP / DOWN; also KP_8 /
    KP_2 via :data:`ui._UP_SYMS` and :data:`ui._DOWN_SYMS`) and
    the vertical vim keys (``j`` down, ``k`` up). Extracted from
    :func:`_run_ship_menu` so the smoke test can exercise the
    wrap-around behaviour without spinning up a real SDL context.

    Returns ``None`` for any event that does NOT drive nav so the
    caller routes through :func:`update_ship_menu` for Enter / ESC
    / Quit handling.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym = event.sym
    sym_name: str = getattr(sym, 'name', '').lower()
    if sym in ui._UP_SYMS or sym_name == 'k':
        return (selected - 1) % len(SHIP_MENU_OPTIONS)
    if sym in ui._DOWN_SYMS or sym_name == 'j':
        return (selected + 1) % len(SHIP_MENU_OPTIONS)
    return None

def update_ship_menu(event: tcod.event.Event, selected: int) -> ShipMenuAction:
    """Map a single event for the hangar menu.

    Pure dispatcher: UP/DOWN navigation is handled by the caller
    (it owns the ``selected`` int so this function stays
    referentially transparent). ESC returns BACK, Enter triggers
    the action corresponding to ``selected``, anything else is
    IGNORE.
    """
    if isinstance(event, tcod.event.Quit):
        return ShipMenuAction.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipMenuAction.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return ShipMenuAction.BACK
    if sym in ui._ENTER_SYMS:
        return ShipMenuAction.VIEW if selected == 0 else ShipMenuAction.REFUEL if selected == 1 else ShipMenuAction.SELL if selected == 2 else ShipMenuAction.LAUNCH
    return ShipMenuAction.IGNORE

def render_ship_view(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, *, screen_width: int, screen_height: int) -> None:
    """Paint the read-only ship-stats panel.

    Reports cargo (used / max), weapons (attached / slots), modules
    (installed / slots), and current hull damage. If ``owned`` is
    ``None`` we still draw the panel so the View option is never
    useless - it shows the catalogue entry instead.
    """
    console.clear()
    title = f'{ship.name.upper()} - DETAILS'
    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    console.print(x=ui.centered_x(title, screen_width), y=center_y - 6, string=title, fg=ui.COLOR_TITLE)
    cargo_used = ctx.player_owned_ship.cargo_used if ctx.player_owned_ship is not None else 0
    weapons_n = len(ctx.player_owned_ship.weapons) if ctx.player_owned_ship is not None else 0
    modules_n = len(ctx.player_owned_ship.modules) if ctx.player_owned_ship is not None else 0
    hull_pct = ctx.player_owned_ship.hull_damage_pct if ctx.player_owned_ship is not None else 0
    cargo_line = f'Cargo: {cargo_used} / {ship.max_cargo}'
    weapons_line = f'Weapons attached: {weapons_n} / {ship.weapon_slots}'
    modules_line = f'Modules installed: {modules_n} / {ship.module_slots}'
    hull_line = f'Hull damage: {hull_pct}%'
    fuel_line = f'Fuel: {ctx.player_owned_ship.fuel} / {ship.max_fuel}'
    lines = (cargo_line, weapons_line, modules_line, hull_line, fuel_line)
    for i, line in enumerate(lines):
        row = center_y - 3 + i * 2
        console.print(x=ui.centered_x(line, screen_width), y=row, string=line, fg=ui.COLOR_VALUE_WHITE if ctx.player_owned_ship is not None else ui.COLOR_VALUE_DIM)
    console.print(x=ui.centered_x('Press any key to return.', screen_width), y=center_y + len(lines) * 2 + 1, string='Press any key to return.', fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)

def update_ship_view(event: tcod.event.Event) -> ShipViewOutcome:
    """Map a single event for the ship-stats sub-modal.

    Any key closes the panel: ESC and Quit exit early so the caller
    can react, every other event returns ``IGNORE`` and the caller's
    loop drains the same way.
    """
    if isinstance(event, tcod.event.Quit):
        return ShipViewOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipViewOutcome.IGNORE
    if event.sym in ui._ESCAPE_SYMS:
        return ShipViewOutcome.BACK
    return ShipViewOutcome.IGNORE

def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the hub-menu modal for ``ship``; return the chosen action.

    The menu has 4 options arranged vertically; the highlighted
    option (initially 0 = ``View``) is mutated by UP / DOWN arrows
    AND vim ``j`` / ``k`` via :func:`_ship_menu_navigate`, and
    maps to a ShipMenuAction via :func:`update_ship_menu` on
    Enter. ``View`` opens a sub-modal; ``Refuel`` buys fuel;
    ``Sell`` and ``Launch`` log a stub message for this iteration.
    ESC returns ``BACK``; that's a no-op from the caller's point
    of view (the city is already being repainted by the main loop).

    ``stats`` is the player's :class:`hud.HudStats` (gold is read
    and mutated by the REFUEL handler).
    """
    console = make_console()
    selected = 0

    def _render() -> None:
        render_ship_menu(console, ctx, ship, selected=selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> ShipMenuAction:
        nonlocal selected
        new = _ship_menu_navigate(event, selected)
        if new is not None:
            selected = new
            return ShipMenuAction.IGNORE
        return update_ship_menu(event, selected)
    while True:
        action = ui.Modal(ctx.context, console).run(_render, _update)
        if action is ShipMenuAction.VIEW:
            _run_ship_view(ctx, ship)
            continue
        if action is ShipMenuAction.REFUEL:
            ship_record = ship_module.find_ship(ctx.player_owned_ship.ship_id)
            buyable = ship_record.max_fuel - ctx.player_owned_ship.fuel
            if buyable <= 0:
                ctx.log.add('The fuel tank is already full.')
                continue
            affordable = ctx.stats.credits // ship_module.FUEL_COST_PER_UNIT
            if affordable <= 0:
                ctx.log.add("You don't have enough credits to buy fuel.")
                continue
            units = min(buyable, affordable)
            cost = units * ship_module.FUEL_COST_PER_UNIT
            ctx.stats.credits -= cost
            ctx.player_owned_ship.fuel += units
            ctx.log.add(f'Refueled {units} units for {cost}$. Fuel: {ctx.player_owned_ship.fuel} / {ship_record.max_fuel}.')
            continue
        return action

def _run_ship_view(ctx, ship: ship_module.Ship) -> None:
    """Show the read-only stats panel for ``ship``.

    Stays inside its own loop until the player presses any key
    (so the player has time to read the stats before returning to
    the menu). On Quit the panel closes and returns; on ESC it
    closes faster via a direct BACK return.
    """
    console = make_console()

    def _render() -> None:
        render_ship_view(console, ctx, ship, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> ShipViewOutcome:
        if isinstance(event, tcod.event.KeyDown):
            return ShipViewOutcome.BACK
        return update_ship_view(event)
    ui.Modal(ctx.context, console).run(_render, _update)

def _find_hangar_ship(city_game_map: world.GameMap, player_owned_ship: ship_module.OwnedShip | None) -> world.Entity | None:
    """Return the player's owned hangar ship entity in ``city_game_map``.

    Used by the launch-and-land dispatcher branches to drive the
    city<->space animations without mutating the city's entity
    list. Returns ``None`` if the player has no owned ship (the
    branches then no-op gracefully - the dispatcher never reaches
    them without an owned ship because the ship-buy modal gates
    that). The scan is O(len(entities)) but the city entity list
    is small (<10 entities), so the cost is negligible.
    """
    if player_owned_ship is None:
        return None
    return next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)

def render_planet_menu(console: tcod.console.Console, ctx: GameContext, planet_obj: solar_system_module.Planet, *, screen_width: int=SCREEN_WIDTH, screen_height: int=SCREEN_HEIGHT, has_port: bool=True) -> None:
    """Paint the planet-bump dialog.

    Layout: planet name centered near the top of the viewport,
    planet description (wrapped if needed) below, then a single
    option + hint row, then a control hint. Mimics the visual
    language of :func:`render_ship_menu` so the player recognises
    the modal pattern.

    When ``has_port`` is True (the planet is in the data registry
    AND its spec has a spaceport-labeled building) the option row
    shows a single highlighted ``> Land <`` cell. Otherwise the
    row shows an info-only ``No port on this world.`` cell in
    :attr:`ui.COLOR_DESCRIPTION` and the hint reads
    ``ENTER or ESC to fly past.`` -- :func:`update_planet_menu`
    routes ENTER to :attr:`PlanetMenuOutcome.BACK` in that case
    so the caller's LAND dispatch can't fire.
    """
    console.clear()
    title_y = screen_height // 4
    console.print(x=ui.centered_x(planet_obj.name, screen_width), y=title_y, string=planet_obj.name, fg=ui.COLOR_TITLE)
    desc_y = title_y + 2
    desc_rows = ui.wrap_text(planet_obj.description, screen_width - 4)
    for i, row in enumerate(desc_rows):
        console.print(x=ui.centered_x(row, screen_width), y=desc_y + i, string=row, fg=ui.COLOR_DESCRIPTION)
    option_y = screen_height // 2 + 2
    if has_port:
        option_text = '> Land <'
        hint = 'ENTER to land - ESC to fly away'
        option_fg = ui.COLOR_OPTION_HIGHLIGHT
        hint_fg = ui.COLOR_INSTRUCTION
    else:
        option_text = 'No port on this world.'
        hint = 'ENTER or ESC to fly past.'
        option_fg = ui.COLOR_DESCRIPTION
        hint_fg = ui.COLOR_INSTRUCTION
    console.print(x=ui.centered_x(option_text, screen_width), y=option_y, string=option_text, fg=option_fg)
    hint_y = option_y + 2
    console.print(x=ui.centered_x(hint, screen_width), y=hint_y, string=hint, fg=hint_fg)
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)

def update_planet_menu(event: tcod.event.Event, *, has_port: bool=True) -> PlanetMenuOutcome:
    """Map a single key event for the planet-bump dialog.

    ENTER -> :attr:`PlanetMenuOutcome.LAND` if ``has_port`` else
    :attr:`PlanetMenuOutcome.BACK` (no Land option means ENTER
    acts as ESC and skips the cross-planet LAND dispatch in the
    caller -- this is the user's "Remove the land option on
    planets that don't have a port" requirement). ESC always
    returns :attr:`PlanetMenuOutcome.BACK`. Window-close returns
    :attr:`PlanetMenuOutcome.QUIT`. Anything else returns
    :attr:`IGNORE` so the caller drains the event.
    """
    if isinstance(event, tcod.event.Quit):
        return PlanetMenuOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return PlanetMenuOutcome.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return PlanetMenuOutcome.BACK
    if sym in ui._ENTER_SYMS:
        return PlanetMenuOutcome.LAND if has_port else PlanetMenuOutcome.BACK
    return PlanetMenuOutcome.IGNORE

def _run_planet_menu(ctx, planet_obj: solar_system_module.Planet, *, active_mission_text: str | None) -> PlanetMenuOutcome:
    """Show the planet-bump modal for ``planet_obj``; return the chosen outcome.

    The ``Land`` option only appears if the planet has a registered
    port -- see :func:`spacehack.data.planets.has_landable_port`.
    When the planet has no port (e.g. Mercury / Venus / Jupiter /
    Saturn / Uranus / Neptune) the modal still shows so the player
    gets feedback that they bumped something, but ENTER closes the
    modal rather than triggering the cross-planet LAND dispatch.
    This keeps the player safe from the old ``KeyError: 'saturn'``
    crash that fired when ENTER-on-Saturn tried to load a missing
    :func:`spacehack.data.planets.load_planet` entry.

    Loops :func:`render_planet_menu` + :func:`update_planet_menu`
    until an event yields a non-:attr:`IGNORE` outcome. The HUD is
    not repainted inside this loop - the player has already
    approached the planet and the dialog is the only thing on
    screen for this turn. Callers wire :attr:`LAND` to the city
    return animation when ``planet_obj.id == "earth"``.
    """
    from .data.planets import has_landable_port
    has_port = has_landable_port(planet_obj.id)
    console = make_console()

    def _render() -> None:
        render_planet_menu(console, ctx, planet_obj, has_port=has_port)

    def _update(event) -> PlanetMenuOutcome:
        return update_planet_menu(event, has_port=has_port)
    return ui.Modal(ctx.context, console).run(_render, _update)

def _animate_ship_to_y(ctx, console: tcod.console.Console, ship_ent: world.Entity, game_map: world.GameMap, *, target_y: int, frame_seconds: float = 0.08) -> None:
    """Walk ``ship_ent.pos.y`` one cell per frame toward ``target_y``.

    Each frame paints ``game_map`` (plus HUD + msg log) around the
    moving ship and calls :meth:`tcod.context.Context.present`. Direction
    is determined by the sign of ``target_y - ship_ent.pos.y``: negative
    walks north (off-screen above), positive walks south. After this
    returns, ``ship_ent.pos.y == target_y``.

    Used by both launch (target offscreen above) and return-to-city
    (target :data:`world.HANGAR_ANCHOR`). ``frame_seconds`` is the
    per-frame sleep; 0.08 reads as a brisk but visible glide.
    """
    direction = -1 if ship_ent.pos.y > target_y else 1
    while ship_ent.pos.y != target_y:
        ship_ent.pos = world.Position(ship_ent.pos.x, ship_ent.pos.y + direction)
        console.clear()
        world.render_world(console, game_map, region_x=0, region_y=0, region_w=solar_system_module.SOL_VIEW_W, region_h=solar_system_module.SOL_VIEW_H)
        _am = ctx.player_active_mission
        _active_mission_text = (
            mission_module.find_mission(_am.mission_id).title if _am is not None else ''
        )
        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=solar_system_module.SOL_VIEW_H, character=ctx.character_info, stats=ctx.stats, active_mission=_active_mission_text)
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        ctx.context.present(console)
        _responsive_sleep(frame_seconds)

def _launch_to_space(ctx, console: tcod.console.Console, city_game_map: world.GameMap, hangar_ship_ent: world.Entity, ship_obj: ship_module.Ship, current_city_id: str, city_player: world.Entity) -> tuple[world.GameMap, world.Entity]:
    """Animate ``hangar_ship_ent`` off the top of the city viewport and
    return ``(space_game_map, space_player_entity)``.

    The hangar ship is moved offscreen via :func:`_animate_ship_to_y`
    but kept in ``city_game_map.entities`` so the future return
    animation walks the SAME entity back to HANGAR_ANCHOR (no need
    to splice a new entity into/out of the city's entity list).

    The returned ``space_game_map`` is freshly built via
    :func:`solar_system_module.make_solar_system` and has the
    player-ship Entity docked at ``current_city_id`` (whatever
    planet the player just launched from) via
    :func:`solar_system_module.place_docked_ship`. Previously this
    argument was hardcoded to ``"earth"`` which sent Mars-launched
    players into Earth orbit instead of Mars.
    """
    if city_player in city_game_map.entities:
        city_game_map.entities.remove(city_player)
    offscreen_y = -(solar_system_module.SOL_VIEW_H // 2) - 1
    if hangar_ship_ent.pos.y > offscreen_y:
        _animate_ship_to_y(ctx, console, hangar_ship_ent, city_game_map, target_y=offscreen_y)
        ctx.log.add(f'You launch the {ship_obj.name} into space.')
    space_map = solar_system_module.make_solar_system()
    _add_bounty_spawns_to_map(ctx, space_map, solar_system_module.current_solar_system_id)
    _spawn_procedural_pirates(ctx, space_map, solar_system_module.current_solar_system_id)
    origin_planet = solar_system_module.find_planet(current_city_id)
    space_player = solar_system_module.place_docked_ship(ship_obj, origin_planet)
    space_map.entities.append(space_player)
    return (space_map, space_player)

def _return_to_city(ctx, console: tcod.console.Console, hangar_ship_ent: world.Entity, city_game_map: world.GameMap, city_player_ent: world.Entity) -> tuple[world.GameMap, world.Entity]:
    """Animate the same ``hangar_ship_ent`` down to :data:`world.HANGAR_ANCHOR`
    and return ``(city_game_map, city_player_entity)``.

    Mirrors :func:`_launch_to_space`: the ship entity is the SAME
    instance that was animated offscreen during launch, so no
    entity-list swap is needed on the city map.
    """
    _animate_ship_to_y(ctx, console, hangar_ship_ent, city_game_map, target_y=world.HANGAR_ANCHOR.y)
    if city_player_ent not in city_game_map.entities:
        city_game_map.entities.append(city_player_ent)
    ctx.log.add('You return to Earth and dock at your hangar.')
    return (city_game_map, city_player_ent)

def _run_game(context: tcod.context.Context, species_id: str, class_id: str) -> None:
    """Render the small city + HUD + msg log and handle vim movement.

    Walking into a wall logs a short message. Walking into a
    non-interactable entity logs a "bump" message. Walking into
    a ship (at the space port) opens the ship-buy modal; walking
    into a guild NPC opens the flavor-talk modal.
    """
    species = find_species(species_id)
    klass = find_class(class_id)
    CITY_WIDTH, CITY_HEIGHT = (60, 40)
    game_map = world.make_city(width=CITY_WIDTH, height=CITY_HEIGHT)
    player = world.Entity(char='@', fg=(255, 255, 255), pos=world.Position(x=CITY_WIDTH // 2, y=CITY_HEIGHT // 2), name='Player')
    game_map.entities.append(player)
    stats = character.starting_stats(species_id, class_id)
    log = message_log.MessageLog(capacity=MSG_LOG_HEIGHT)
    log.add(f'You arrive in a quiet Earth city as a {species.name} {klass.name}.')
    log.add("The cobblestones are damp from last night's rain.")
    log.add('Walk with h / j / k / l; diagonals y / u / b / n.')
    log.add('Buildings: North-West space port, South-West merchant guild,')
    log.add('Bar in the plaza, militia + bounty guild on the South-East.')
    log.add('Visit the space port to buy a ship; the guild halls offer work later.')
    player_owned_ship: ship_module.OwnedShip | None = None
    player_active_mission: mission_module.ActiveMission | None = None
    character_info = {'species_id': species_id, 'species_name': species.name, 'class_id': class_id, 'class_name': klass.name}
    ctx = GameContext(context=context, character_info=character_info, log=log, game_map=game_map, player=player, stats=stats, player_owned_ship=player_owned_ship, player_active_mission=player_active_mission)
    map_w = SCREEN_WIDTH - HUD_WIDTH
    map_h = SCREEN_HEIGHT - MSG_LOG_HEIGHT
    console = make_console()
    city_game_map = game_map
    city_player = player
    current_mode: str = 'city'
    current_city_id: str = 'earth'
    while True:
        console.clear()
        if current_mode == 'space':
            sys_now = solar_system_module.current_system()
            sol_w = sys_now.width
            sol_h = sys_now.height
            view_w = solar_system_module.SOL_VIEW_W
            view_h = solar_system_module.SOL_VIEW_H
            cam_x = max(0, min(player.pos.x - view_w // 2, sol_w - view_w))
            cam_y = max(0, min(player.pos.y - view_h // 2, sol_h - view_h))
            world.render_world_view(console, game_map, region_x=0, region_y=0, region_w=view_w, region_h=view_h, camera_x=cam_x, camera_y=cam_y)
        else:
            world.render_world(console, game_map, region_x=0, region_y=0, region_w=map_w, region_h=map_h)
        active_mission_text = mission_module.find_mission(player_active_mission.mission_id).title if player_active_mission is not None else None
        _show_ship_hud = current_mode == 'space' and player_owned_ship is not None
        _ship_cat = ship_module.find_ship(ctx.player_owned_ship.ship_id) if _show_ship_hud else None
        if current_mode == 'space':
            _location = solar_system_module.current_system().name
        else:
            _location = current_city_id.replace('_', ' ').title()
        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=map_h, character=character_info, stats=stats, active_mission=active_mission_text, location=_location, owned_ship=player_owned_ship if _show_ship_hud else None, ship_catalog=_ship_cat)
        message_log.render_message_log(console, log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        ctx.context.present(console)
        for event in tcod.event.wait():
            if should_quit(event):
                return
            if _is_q_press(event):
                outcome, new_active = _run_quest_log(ctx)
                if outcome is QuestLogOutcome.QUIT:
                    return
                if outcome is QuestLogOutcome.ABANDONED:
                    if player_active_mission is not None:
                        abandoned = mission_module.find_mission(player_active_mission.mission_id)
                        log.add(f'You abandoned: {abandoned.title}.')
                        mission_module.abort_mission(abandoned, player_owned_ship, log)
                        # Remove any bounty spawn associated with this mission.
                        if player_active_mission.bounty_spawn_id is not None:
                            _remove_bounty_spawn(
                                ctx,
                                player_active_mission.bounty_spawn_id,
                                abandoned.target_system_id,
                            )
                    player_active_mission = new_active
                    ctx.player_active_mission = new_active
                continue
            if current_mode == 'space' and _is_m_press(event):
                outcome = _run_navigation(ctx, player.pos)
                if outcome is NavigationOutcome.QUIT:
                    return
                continue
            if current_mode == 'space' and _is_g_press(event):
                _goto_outcome, _goto_combat = _run_goto(ctx, player)
                if _goto_outcome is GotoOutcome.COMBAT and _goto_combat is not None:
                    combat._handle_combat_encounter(ctx, console, _goto_combat)
                    # Sync local mission state — _handle_combat_encounter
                    # may have cleared ctx.player_active_mission (bounty
                    # auto-complete) but the local copy is stale.
                    player_active_mission = ctx.player_active_mission
                continue
            # Period = wait one turn (space mode: pirates move, shields regen).
            if _is_period_press(event):
                if current_mode == 'space' and (player_owned_ship is not None):
                    _encounter = _detect_combat_encounter(ctx, player.pos, solar_system_module.current_system())
                    if _encounter is not None:
                        combat._handle_combat_encounter(ctx, console, _encounter)
                        player_active_mission = ctx.player_active_mission
                    _move_pirates(ctx, game_map)
                ctx.log.add('You wait.')
                continue

            delta = _vim_action(event)
            if delta is None:
                continue
            dx, dy = delta
            code, blocker = world.try_move(player, game_map, dx, dy)
            if code == 'moved' and current_mode == 'space' and (player_owned_ship is not None):
                _encounter = _detect_combat_encounter(ctx, player.pos, solar_system_module.current_system())
                if _encounter is not None:
                    combat._handle_combat_encounter(ctx, console, _encounter)
                    # Sync local mission state after combat.
                    player_active_mission = ctx.player_active_mission
                # Move procedural pirates after the player moves.
                _move_pirates(ctx, game_map)
            if code == 'wall':
                if current_mode == 'space':
                    target_x = player.pos.x + dx
                    target_y = player.pos.y + dy
                    if game_map.in_bounds(target_x, target_y):
                        station_id = solar_system_module.station_id_at(target_x, target_y)
                        if station_id is None:
                            jp = solar_system_module.jump_point_at(target_x, target_y)
                            pid = solar_system_module.planet_id_at(target_x, target_y)
                        else:
                            station_for_bump = solar_system_module.find_station(station_id)
                            jp = None
                            pid = station_for_bump.city_planet_id
                        if jp is not None and jp.connects_to:
                            target_system_id, target_jp_id = jp.connects_to[0]
                            log.add(f'You approach {jp.name}.')
                            outcome = _run_jump_menu(ctx, jp, target_system_id)
                            if outcome is JumpMenuOutcome.JUMP:
                                ship_record_for_fuel = ship_module.find_ship(player_owned_ship.ship_id)
                                if player_owned_ship.fuel < ship_module.JUMP_FUEL_COST:
                                    log.add(f'Not enough fuel! The jump requires {ship_module.JUMP_FUEL_COST} units; you have {player_owned_ship.fuel}.')
                                    continue
                                player_owned_ship.fuel -= ship_module.JUMP_FUEL_COST
                                log.add(f'Jump drive engaged. Fuel: {player_owned_ship.fuel} / {ship_record_for_fuel.max_fuel}.')
                                _animate_jump(ctx, console, ctx.player, active_mission_text=active_mission_text or '')
                                new_game_map, player = _jump_to_system(ctx=ctx, jp=jp, target_system_id=target_system_id, target_jp_id=target_jp_id)
                                game_map = new_game_map
                                ctx.game_map = game_map
                                ctx.player = player
                                continue
                        elif pid is not None:
                            planet_obj = solar_system_module.find_planet(pid)
                            log.add(f'You approach {planet_obj.name}.')
                            outcome = _run_planet_menu(ctx, planet_obj, active_mission_text=active_mission_text)
                            if outcome is PlanetMenuOutcome.LAND and pid == current_city_id:
                                hangar_ship = _find_hangar_ship(city_game_map, player_owned_ship)
                                if hangar_ship is not None:
                                    game_map, player = _return_to_city(ctx, console, hangar_ship, city_game_map, city_player)
                                    current_mode = 'city'
                            elif outcome is PlanetMenuOutcome.LAND:
                                from .data.planets import load_planet as planets_load_planet, hangar_anchor as planet_hangar_anchor, has_landable_port as planets_has_landable_port
                                if not planets_has_landable_port(pid):
                                    log.add(f'You see no port on {planet_obj.name}.')
                                    continue
                                # Cargo scan: militia check + contraband confiscation.
                                _run_cargo_scan(ctx, pid)
                                if city_player in city_game_map.entities:
                                    city_game_map.entities.remove(city_player)
                                new_city_map = planets_load_planet(pid)
                                new_anchor = planet_hangar_anchor(pid)
                                hangar_ship = _find_hangar_ship(city_game_map, player_owned_ship)
                                if hangar_ship is not None:
                                    if hangar_ship in city_game_map.entities:
                                        city_game_map.entities.remove(hangar_ship)
                                    hangar_ship.pos = world.Position(new_anchor.x, -(solar_system_module.SOL_VIEW_H // 2) - 1)
                                    new_city_map.entities.append(hangar_ship)
                                    _animate_ship_to_y(ctx, console, hangar_ship, new_city_map, target_y=new_anchor.y)
                                    log.add(f'You touch down on {planet_obj.name}.')
                                    if city_player not in new_city_map.entities:
                                        new_city_map.entities.append(city_player)
                                    city_player.pos = world.Position(new_anchor.x, new_anchor.y + 1)
                                    city_game_map = new_city_map
                                    game_map = new_city_map
                                    player = city_player
                                    ctx.game_map = game_map
                                    ctx.player = player
                                    current_city_id = pid
                                    current_mode = 'city'
                            continue
                log.add('A wall blocks your path.')
            elif code == 'occupied':
                if blocker.ship_id:
                    ship = ship_module.find_ship(blocker.ship_id)
                    if blocker.owned:
                        result = _run_ship_menu(ctx, ship)
                        if result is ShipMenuAction.QUIT:
                            return
                        if result is ShipMenuAction.LAUNCH and player_owned_ship is not None:
                            hangar_ship = next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
                            if hangar_ship is not None:
                                space_game_map, space_player_entity = _launch_to_space(ctx, console, city_game_map, hangar_ship, ship, current_city_id=current_city_id, city_player=city_player)
                                game_map = space_game_map
                                player = space_player_entity
                                ctx.game_map = game_map
                                ctx.player = player
                                current_mode = 'space'
                            continue
                    elif player_owned_ship is not None:
                        log.add('You already have a ship docked in your hangar.')
                    else:
                        result = _run_ship_buy(ctx, blocker, ship)
                        if result is ShipBuyOutcome.QUIT:
                            return
                        if result is ShipBuyOutcome.BUY:
                            stats.credits -= ship.price
                            blocker.pos = world.HANGAR_ANCHOR
                            blocker.owned = True
                            blocker.name = f'Your Ship: {ship.name}'
                            player_owned_ship = ship_module.OwnedShip(ship_id=ship.id, weapons=('light_laser', 'heavy_laser', 'plasma_cannon', 'light_missile', 'heavy_missile', 'emp_missile'), modules=('compact_reactor', 'shield_mk1'), fuel=ship.max_fuel)
                            ctx.player_owned_ship = player_owned_ship
                            log.add(f'You bought the {ship.name} for {ship.price}$ and parked it in your hangar.')
                        elif result is ShipBuyOutcome.TOO_EXPENSIVE:
                            short = ship.price - stats.credits
                            log.add(f'You cannot afford the {ship.name} ({short}$ short).')
                elif blocker.trade_terminal:
                    from .trade import open_trade as _open_trade
                    _open_trade(ctx, current_city_id)
                elif blocker.npc_id:
                    npc_obj = npc_module.find_npc(blocker.npc_id)
                    deliver_mission: mission_module.Mission | None = None
                    if player_active_mission is not None:
                        active_mission_obj = mission_module.find_mission(player_active_mission.mission_id)
                        if mission_module.is_deliverable_at(active_mission_obj, npc_obj.id, current_city_id):
                            deliver_mission = active_mission_obj
                    result, deliver_in_progress = _run_npc_talk(ctx, npc_obj, deliver_mission=deliver_mission)
                    if result is TalkOutcome.QUIT:
                        return
                    if result is TalkOutcome.DELIVER:
                        if deliver_in_progress is not None:
                            mission_module.complete_mission(deliver_in_progress, player_owned_ship, stats, log)
                        player_active_mission = None
                        ctx.player_active_mission = None
                    if result is TalkOutcome.WORK:
                        if player_active_mission is not None:
                            current = mission_module.find_mission(player_active_mission.mission_id)
                            giver = npc_module.find_npc(current.giver_npc_id)
                            log.add(f'You already have work from {giver.name}. Press Q to view or abandon it.')
                        else:
                            offerings = mission_module.missions_offered_by(npc_obj.id)
                            if not offerings:
                                log.add(f'{npc_obj.name} has no work for you right now.')
                            else:
                                outcome, picked = _run_mission_offerings(ctx, npc_obj, offerings)
                                if outcome is MissionOutcome.ACCEPT and picked is not None:
                                        if mission_module.try_accept_mission(picked, player_owned_ship, log):
                                            _bounty_spawn_id: str | None = None
                                            if picked.target_enemy_id is not None and picked.target_system_id is not None:
                                                # Generate a unique spawn id for this bounty target.
                                                _bounty_spawn_id = f"bounty_{picked.id}_{int(time.time())}"
                                                try:
                                                    _target_sys = solar_systems_module.find_solar_system(picked.target_system_id)
                                                    _spawn_pos = _pick_bounty_spawn_pos(_target_sys)
                                                    if _spawn_pos is not None:
                                                        from .game_context import BountySpawn
                                                        _bs = BountySpawn(
                                                            spawn_id=_bounty_spawn_id,
                                                            enemy_id=picked.target_enemy_id,
                                                            pos=_spawn_pos,
                                                        )
                                                        if picked.target_system_id not in ctx.bounty_spawns:
                                                            ctx.bounty_spawns[picked.target_system_id] = []
                                                        ctx.bounty_spawns[picked.target_system_id].append(_bs)
                                                        # If player is already in the target system, add the
                                                        # entity to the current game_map immediately.
                                                        if solar_system_module.current_solar_system_id == picked.target_system_id:
                                                            _add_bounty_spawns_to_map(ctx, ctx.game_map, picked.target_system_id)
                                                        log.add(f"Bounty target marked in {_target_sys.name}.")
                                                except KeyError:
                                                    pass
                                            player_active_mission = mission_module.ActiveMission(
                                                mission_id=picked.id,
                                                bounty_spawn_id=_bounty_spawn_id,
                                            )
                                            ctx.player_active_mission = player_active_mission
                else:
                    log.add(f'You bump into {blocker.name}.')

def run(context: tcod.context.Context) -> None:
    """Drive the 3 creation screens, then drop into the city game."""
    import os
    import struct
    _seed = struct.unpack('I', os.urandom(4))[0]
    seed_rng(_seed)
    while True:
        outcome, species_id = _run_pick(context, ui.species_menu())
        if outcome in (Outcome.QUIT, Outcome.BACK):
            return
        outcome, class_id = _run_pick(context, ui.class_menu())
        if outcome is Outcome.QUIT:
            return
        if outcome is Outcome.BACK:
            continue
        outcome = _run_confirm(context, species_id, class_id)
        if outcome is Outcome.QUIT:
            return
        if outcome is Outcome.BACK:
            continue
        _run_game(context, species_id, class_id)
        return

def main() -> None:
    """Top-level entry: load assets, open window, then run the flow."""
    tileset = load_tileset()
    with open_terminal(tileset) as context:
        run(context)
if __name__ == '__main__':
    main()
