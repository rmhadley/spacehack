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
from .data import solar_systems as solar_systems_module
from .data.species import find_species
from .data.classes import find_class
from .data import npcs as npc_module
from . import world
from .engine import (
    HUD_WIDTH,
    MSG_LOG_HEIGHT,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WINDOW_TITLE,
    load_tileset,
    make_console,
    open_terminal,
    seed_rng,
    should_quit,
)


# Bright yellow ship marker used by the navigation overlay. Lives
# here (rather than ui.COLOR_*) because this is the only consumer
# of a yellow-specific marker; if a future iteration adds another
# yellow-on-dark glyph (e.g. ship trail or course line) promote it
# to ui.COLOR_NAV_SHIP.
NAV_SHIP_FG: tuple[int, int, int] = (255, 255, 100)


class Outcome(Enum):
    """What happened at the end of a per-creation-screen loop iteration.

    ``IGNORE`` is the standard "keep polling" signal consumed by
    :meth:`spacehack.ui.Modal.run` -- an update function returns
    :attr:`IGNORE` for events it doesn't act on, and Modal keeps
    rendering + polling. Every other member terminates the modal
    loop and propagates back to the caller.
    """
    IGNORE = auto()   # event wasn't relevant; keep polling
    QUIT = auto()
    BACK = auto()
    CONFIRM = auto()


class ShipBuyOutcome(Enum):
    """What happened during a single ship-buy dialog iteration.

    Differentiates ESC (silent back) from Enter-while-unaffordable
    (caller should log "you cannot afford this"). The BUY outcome
    implies the player can afford the ship.
    """
    IGNORE = auto()         # event doesn't drive a state transition
    BUY = auto()            # Enter pressed AND player can afford
    BACK = auto()           # ESC pressed - silent back
    TOO_EXPENSIVE = auto()  # Enter pressed but player cannot afford
    QUIT = auto()           # window-close


class TalkOutcome(Enum):
    """What happened during a single NPC-talk dialog iteration.

    ESC walks away (BACK); Enter opens the NPC's mission offerings
    (WORK); when the player has an active delivery mission that
    this NPC can fulfil (:data:`Mission.required_cargo_size` > 0
    and giver matches), Enter drives :attr:`DELIVER` instead and
    the dialog paints an extra "> Deliver <title> <" row. Quit
    closes the window; anything else is IGNORE. Mirrors
    ``ShipBuyOutcome`` so a future iteration can grow the dialog
    with more branches (e.g. ``WORK`` -> goods for sale, ``REST``)
    without churning the call site.
    """
    IGNORE = auto()
    BACK = auto()
    WORK = auto()
    DELIVER = auto()
    QUIT = auto()


class ShipMenuAction(Enum):
    """Which sub-modal of the hangar menu the player triggers."""
    IGNORE = auto()         # key is not relevant (mid-options nav)
    VIEW = auto()           # Enter on the "View" option
    REFUEL = auto()         # Enter on "Refuel" (buy fuel)
    SELL = auto()           # Enter on "Sell" (placeholder)
    LAUNCH = auto()         # Enter on "Launch"
    BACK = auto()           # ESC - returns to the city
    QUIT = auto()           # window-close


class ShipViewOutcome(Enum):
    """Result of the ship-stats sub-modal (View option).

    The stats panel is read-only: any key returns to the menu, ESC
    closes the panel directly. Held separately from ShipMenuAction
    so the menu dispatcher stays focused on its 3-option list.
    """
    IGNORE = auto()
    BACK = auto()           # ESC inside the panel -> menu
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


# ---------------------------------------------------------------------------
# Per-creation-screen loops
# ---------------------------------------------------------------------------


def _run_pick(
    context: tcod.context.Context,
    menu: ui.MenuScreen,
) -> tuple[Outcome, str | None]:
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
        return outcome, menu.selected_id
    return outcome, None


def _run_confirm(
    context: tcod.context.Context,
    species_id: str,
    class_id: str,
) -> Outcome:
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


# ---------------------------------------------------------------------------
# Movement dispatch
# ---------------------------------------------------------------------------


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
    sym_name: str = getattr(event.sym, "name", "").lower()
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
    return getattr(event.sym, "name", "") == "Q"


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
    sym_name: str = getattr(event.sym, "name", "")
    return sym_name in ("M", "m")


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
    sym_name: str = getattr(event.sym, "name", "")
    return sym_name in ("G", "g")


# ---------------------------------------------------------------------------
# Navigation overlay (N key in space mode)
# ---------------------------------------------------------------------------
#
# When the player presses ``N`` (or ``n``) while in space mode, this
# overlay replaces the regular per-frame space render and shows the
# ENTIRE solar system at once - the 200x140 ``SOL_W``/``SOL_H`` map
# scaled down to fit the ~80x54 viewport with the player's ship
# position overlay drawn on top. Read-only: any unknown key is
# IGNORE, ESC is BACK (silent close), window-close is QUIT.



def _render_aoi_panel(
    console,
    system,
    ship_pos,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    """Right-side Areas-of-Interest panel for the Map/NAVIGATION overlay.

    Renders a categorised list of Stars / Planets / Jump Points /
    (when present) Stations in the current solar system. Each
    entry shows its local name and Euclidean distance from the
    ship (1 dp, units = big-map cells). Sorted by distance
    within each category for predictable visual order.
    """
    COLOR_STAR = ui.COLOR_TITLE                       # warm gold for stars / sun.
    COLOR_PLANET = ui.COLOR_VALUE_WHITE               # white for planets.
    COLOR_JUMP = ui.COLOR_OPTION_HIGHLIGHT            # gold for jump gates.
    COLOR_STATION = ui.COLOR_OPTION_HIGHLIGHT2        # steel-cyan for stations.

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
        return label[: name_w - 1] + chr(0x2026)

    def _row(label, dist=None):
        if dist is None:
            return fit(label)
        return fit(f"{_clamp_label(label)} - {dist}u")

    def fit(line):
        return line if len(line) <= inner_w else line[: inner_w - 1] + chr(0x2026)

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
        for sys_id, hops in sorted(
            reachable_counts.items(), key=lambda kv: (kv[1], kv[0]),
        ):
            dest_sys = solar_systems_module.find_solar_system(sys_id)
            row_text = f"{dest_sys.name:<{name_w}} - {hops} hop{'s' if hops > 1 else ''}"
            rows.append((fit(row_text), COLOR_JUMP))
        rows.append(('', COLOR_JUMP))
    cx, cy = x + 2, y + 1
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


def render_navigation(
    console: tcod.console.Console,
    *,
    screen_width: int,
    screen_height: int,
    ship_pos: world.Position,
    system=None,
) -> None:
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

    title = f"NAVIGATION - {system.name.upper()} SYSTEM"
    console.print(
        x=ui.centered_x(title, screen_width),
        y=2,
        string=title,
        fg=ui.COLOR_TITLE,
    )

    inner_view_w = screen_width - HUD_WIDTH
    inner_view_h = screen_height - MSG_LOG_HEIGHT
    nav_map_w = 40
    nav_map_h = 30
    map_off_x = (inner_view_w - nav_map_w) // 2
    map_off_y = 4  # below the title at y=2

    sample_x = system.width / nav_map_w
    sample_y = system.height / nav_map_h

    bodies_for_overlay = list(system.planets) + list(system.jump_points)

    cell_step_x = max(1, int(sample_x))
    cell_step_y = max(1, int(sample_y))
    for mini_y in range(nav_map_h):
        by_lo = int(mini_y * sample_y)
        by_hi = (
            int((mini_y + 1) * sample_y)
            if mini_y + 1 < nav_map_h
            else system.height
        )
        for mini_x in range(nav_map_w):
            bx_lo = mini_x * cell_step_x
            bx_hi = bx_lo + cell_step_x

            planet_here = None
            y = by_lo
            while y < by_hi and planet_here is None:
                x = bx_lo
                while x < bx_hi and planet_here is None:
                    if (
                        0 <= x < system.width
                        and 0 <= y < system.height
                    ):
                        for body in bodies_for_overlay:
                            if (
                                body.pos.x <= x < body.pos.x + body.width
                                and body.pos.y <= y < body.pos.y + body.height
                            ):
                                planet_here = body
                                break
                    x += 1
                y += 1

            if planet_here is not None:
                console.print(
                    x=map_off_x + mini_x,
                    y=map_off_y + mini_y,
                    string=planet_here.char,
                    fg=planet_here.fg,
                )
            else:
                console.print(
                    x=map_off_x + mini_x,
                    y=map_off_y + mini_y,
                    string=".",
                    fg=(80, 80, 110),
                )

    ship_mini_x = int(ship_pos.x / sample_x)
    ship_mini_y = int(ship_pos.y / sample_y)
    if 0 <= ship_mini_x < nav_map_w and 0 <= ship_mini_y < nav_map_h:
        console.print(
            x=map_off_x + ship_mini_x,
            y=map_off_y + ship_mini_y,
            string="@",
            fg=NAV_SHIP_FG,
        )

    if hasattr(system, 'stations'):
        aoi_w = 28
        aoi_x = screen_width - aoi_w - 2
        aoi_y = 4
        aoi_h = max(8, screen_height - 12)
        aoi_x = max(0, min(aoi_x, screen_width - aoi_w - 1))
        _render_aoi_panel(
            console, system, ship_pos,
            x=aoi_x, y=aoi_y, width=aoi_w, height=aoi_h,
        )

    foot_y = map_off_y + nav_map_h + 1
    coord_line = f"You are at ({ship_pos.x}, {ship_pos.y})."
    max_w = screen_width - HUD_WIDTH - 2
    if len(coord_line) > max_w:
        coord_line = coord_line[: max_w - 1] + "…"
    console.print(
        x=ui.centered_x(coord_line, screen_width),
        y=foot_y,
        string=coord_line,
        fg=ui.COLOR_VALUE_WHITE,
    )
    hint = "Press ESC to close."
    console.print(
        x=ui.centered_x(hint, screen_width),
        y=foot_y + 2,
        string=hint,
        fg=ui.COLOR_INSTRUCTION,
    )


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


def _run_navigation(
    context: tcod.context.Context,
    ship_pos: world.Position,
) -> NavigationOutcome:
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
        render_navigation(
            console,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
            ship_pos=ship_pos,
        )
    return ui.Modal(context, console).run(_render, update_navigation)


def _handle_combat_encounter(
    console,
    context,
    player_owned_ship: "ship_module.OwnedShip",
    player: world.Entity,
    game_map: world.GameMap,
    log: message_log.MessageLog,
    encounter: tuple[list, list[world.Position]],
) -> str:
    """Invoke combat for a triggered encounter and handle VICTORY/DEFEAT.

    Both the post-move dispatcher and the auto-nav (G-key) interrupt
    route their triggered encounters through this helper so the two
    paths can't drift apart. The helper unpacks
    ``(specs, positions)`` from the encounter payload, calls
    :func:`_combat.run_combat` with the same hard-coded base pilot
    skills (30/30/30) the post-move dispatcher used, and logs the
    VICTORY/DEFEAT outcome identically so the player sees the same
    log lines whether they walked into pirates or flew into them
    via auto-nav.

    Returns the combat result string (``"VICTORY"``, ``"DEFEAT"``,
    ``"FLEE"``) so the caller can decide whether to continue the
    dispatch loop (``VICTORY``/``FLEE``) or terminate (``DEFEAT``).
    """
    from . import combat as _combat
    _nearby_specs, _nearby_positions = encounter
    _ship_cat = ship_module.find_ship(player_owned_ship.ship_id)
    _pilot_skills = {
        "gunnery": 30, "piloting": 30, "engineering": 30,
    }
    _result = _combat.run_combat(
        console, context, _ship_cat,
        player_owned_ship, player.pos,
        _pilot_skills, _nearby_specs, _nearby_positions,
        game_map, log,
    )
    if _result == "VICTORY":
        _names = ", ".join(_sp.name for _sp in _nearby_specs)
        log.add(f"You defeated {_names}!")
    elif _result == "DEFEAT":
        log.add("Your ship is destroyed!")
    return _result


def _detect_combat_encounter(
    player_pos: world.Position,
    game_map: world.GameMap,
    system: object,
) -> tuple[list, list[world.Position]] | None:
    """Run the squad-aware enemy scan and return combat payload, or ``None``.

    Extracted from the post-move dispatcher block so both the normal
    space-walker and the auto-nav animation loop can call the same
    logic. Two-pass design: pass 1 marks alive enemy spawns within
    ``detect_radius`` as triggered (squad or solo), pass 2 builds
    the encounter payload for any spawn whose squad was triggered
    OR whose own position was triggered as a solo. Returns
    ``(specs, positions)`` if any spawn was triggered, else ``None``.

    Function-level ``from .data.enemies import ...`` import avoids a
    top-level circular import on the data module.
    """
    from .data.enemies import find_enemy as _fe
    _enemy_spawns = getattr(system, 'enemies', ()) or ()
    _alive_spawns: list = []
    _triggered_squad_ids: set = set()
    _triggered_solo_positions: set = set()
    for _spawn in _enemy_spawns:
        try:
            _espec = _fe(_spawn.enemy_id)
        except KeyError:
            continue
        _enemy_alive = any(
            _e for _e in game_map.entities
            if not getattr(_e, 'owned', False)
            and _e.pos.x == _spawn.pos.x
            and _e.pos.y == _spawn.pos.y
        )
        if not _enemy_alive:
            continue
        _alive_spawns.append((_spawn, _espec))
        _dist = math.hypot(
            player_pos.x - _spawn.pos.x,
            player_pos.y - _spawn.pos.y,
        )
        if _dist <= _espec.detect_radius:
            if _spawn.squad_id is not None:
                _triggered_squad_ids.add(_spawn.squad_id)
            else:
                _triggered_solo_positions.add(
                    (_spawn.pos.x, _spawn.pos.y)
                )
    _nearby_specs: list = []
    _nearby_positions: list = []
    for _spawn, _espec in _alive_spawns:
        if _spawn.squad_id is not None:
            if _spawn.squad_id in _triggered_squad_ids:
                _nearby_specs.append(_espec)
                _nearby_positions.append(_spawn.pos)
        else:
            if (_spawn.pos.x, _spawn.pos.y) in _triggered_solo_positions:
                _nearby_specs.append(_espec)
                _nearby_positions.append(_spawn.pos)
    if _nearby_specs:
        return _nearby_specs, _nearby_positions
    return None


def _run_goto(
    context: tcod.context.Context,
    game_map: world.GameMap,
    player_entity: world.Entity,
    log: message_log.MessageLog,
) -> tuple[GotoOutcome, tuple[list, list[world.Position]] | None]:
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
      suitable for direct hand-off to ``_combat.run_combat``.

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
    import heapq

    system = solar_system_module.current_system()

    # Build interactable list: (label, body) tuples from the
    # current system. Planets (including suns if present via the
    # 'sun' attr), jump points, and stations are all fair game.
    destinations: list[tuple[str, object]] = []
    for p in system.planets:
        label = p.name
        if getattr(p, 'sun', False):
            label = f"[Star] {label}"
        destinations.append((label, p))
    for jp in system.jump_points:
        destinations.append((f"[Gate] {jp.name}", jp))
    for st in getattr(system, 'stations', ()) or ():
        destinations.append((f"[Station] {st.name}", st))

    if not destinations:
        log.add("There is nothing to navigate to in this system.")
        return (GotoOutcome.CANCELLED, None)

    n = len(destinations)
    selected = 0
    console = make_console()

    while True:
        # Render menu
        console.clear()
        title = "GO TO"
        console.print(
            x=ui.centered_x(title, SCREEN_WIDTH),
            y=SCREEN_HEIGHT // 4,
            string=title,
            fg=ui.COLOR_TITLE,
        )
        list_top = SCREEN_HEIGHT // 4 + 2
        for i, (label, _body) in enumerate(destinations):
            row = list_top + i * 2
            is_selected = (i == selected)
            marker_open = "> " if is_selected else "  "
            marker_close = " <" if is_selected else "  "
            text = f"{marker_open}{label}{marker_close}"
            fg = ui.COLOR_OPTION_HIGHLIGHT if is_selected else ui.COLOR_OPTION
            console.print(
                x=ui.centered_x(text, SCREEN_WIDTH),
                y=row,
                string=text,
                fg=fg,
            )
        hint = "ARROW KEYS / j,k navigate - ENTER go - ESC cancel"
        console.print(
            x=ui.centered_x(hint, SCREEN_WIDTH),
            y=list_top + n * 2 + 1,
            string=hint,
            fg=ui.COLOR_INSTRUCTION,
        )
        message_log.render_message_log(
            console, log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )
        context.present(console)

        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                return (GotoOutcome.CANCELLED, None)
            if not isinstance(event, tcod.event.KeyDown):
                continue
            sym = event.sym
            sym_name: str = getattr(sym, "name", "").lower()
            # Navigate
            if sym in ui._UP_SYMS or sym_name == "k":
                selected = (selected - 1) % n
                break
            if sym in ui._DOWN_SYMS or sym_name == "j":
                selected = (selected + 1) % n
                break
            # ESC -> cancel
            if sym in ui._ESCAPE_SYMS:
                return (GotoOutcome.CANCELLED, None)
            # ENTER -> go!
            if sym in ui._ENTER_SYMS:
                chosen_body = destinations[selected][1]
                log.add(
                    f"Auto-nav engaged. Plotting course to "
                    f"{getattr(chosen_body, 'name', 'target')}..."
                )

                # ---- BFS pathfinding ----
                # Compute all cells adjacent (8-dir) to the body
                # footprint that are walkable + unoccupied.
                dirs_8 = [
                    (-1, -1), (0, -1), (1, -1),
                    (-1,  0),          (1,  0),
                    (-1,  1), (0,  1), (1,  1),
                ]
                target_cells: set[tuple[int, int]] = set()
                for bx in range(chosen_body.pos.x, chosen_body.pos.x + chosen_body.width):
                    for by in range(
                        chosen_body.pos.y,
                        chosen_body.pos.y + chosen_body.height,
                    ):
                        for dx, dy in dirs_8:
                            nx, ny = bx + dx, by + dy
                            # Skip cells still inside the body
                            if (
                                chosen_body.pos.x <= nx
                                < chosen_body.pos.x + chosen_body.width
                                and chosen_body.pos.y <= ny
                                < chosen_body.pos.y + chosen_body.height
                            ):
                                continue
                            if not game_map.in_bounds(nx, ny):
                                continue
                            if not game_map.is_walkable(nx, ny):
                                continue
                            # Exclude cells that are inside another
                            # body's footprint (but allow the chosen
                            # body's own adjacent cells through).
                            blocked_by_other = False
                            for other in destinations:
                                ob = other[1]
                                if ob is chosen_body:
                                    continue
                                if (
                                    ob.pos.x <= nx < ob.pos.x + ob.width
                                    and ob.pos.y <= ny < ob.pos.y + ob.height
                                ):
                                    blocked_by_other = True
                                    break
                            if blocked_by_other:
                                continue
                            target_cells.add((nx, ny))

                if not target_cells:
                    log.add("Cannot reach that destination - no adjacent landing zone.")
                    return (GotoOutcome.CANCELLED, None)

                # ---- Bresenham line (first attempt) ----
                # Draw a straight line from the player's position
                # toward the closest walkable cell adjacent to the
                # target body. If the entire line is clear (no
                # obstacles), use it directly - much more
                # natural-looking than BFS stair-steps.
                start = (player_entity.pos.x, player_entity.pos.y)
                sx, sy = start
                # Pick the target_cell closest to start so the line
                # terminates at a walkable cell (NOT inside the
                # body's unwalkable footprint).
                target_cx, target_cy = min(
                    target_cells,
                    key=lambda tc: max(
                        abs(tc[0] - sx), abs(tc[1] - sy),
                    ),
                )

                def _bresenham_line(x0, y0, x1, y1):
                    """Yield cells on a line from (x0,y0) to (x1,y1),
                    EXCLUDING the start cell. Standard Bresenham's."""
                    dx = abs(x1 - x0)
                    dy = -abs(y1 - y0)
                    sig_x = 1 if x0 < x1 else -1
                    sig_y = 1 if y0 < y1 else -1
                    err = dx + dy
                    cx, cy = x0, y0
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
                    if not game_map.in_bounds(x, y):
                        return False
                    if not game_map.is_walkable(x, y):
                        return False
                    for other in destinations:
                        ob = other[1]
                        if ob is chosen_body:
                            continue
                        if (
                            ob.pos.x <= x < ob.pos.x + ob.width
                            and ob.pos.y <= y < ob.pos.y + ob.height
                        ):
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
                    # Safety: stop if we've gone past the target area
                    if len(line_path) > 500:
                        line_clear = False
                        break

                if line_clear and line_path:
                    # Bresenham path succeeded - natural straight line!
                    # The generator excludes the final target cell, so
                    # append it to complete the path.
                    line_path.append((target_cx, target_cy))
                    steps = line_path
                else:
                    # ---- A* fallback (when line is blocked) ----
                    # Uses Chebyshev heuristic to produce direct,
                    # natural-looking paths around obstacles.
                    def _heuristic(a, b):
                        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

                    def _pick_target():
                        """Return the target_cell closest to start by
                        Chebyshev distance so A* heads the right way."""
                        best = None
                        best_d = 999999
                        for tc in target_cells:
                            d = _heuristic(start, tc)
                            if d < best_d:
                                best_d = d
                                best = tc
                        return best

                    astar_target = _pick_target()
                    if astar_target is None:
                        log.add("Cannot reach that destination - no access.")
                        return (GotoOutcome.CANCELLED, None)

                    # A* with Chebyshev heuristic (8-dir movement)
                    counter = 0
                    open_set = [(0, counter, start)]
                    came_from: dict[tuple[int, int], tuple[int, int] | None] = {}
                    g_score: dict[tuple[int, int], float] = {start: 0}
                    visited: set[tuple[int, int]] = set()

                    found = False
                    target_reached = None
                    max_steps = 50000

                    while open_set and not found:
                        _, _, curr = heapq.heappop(open_set)
                        if curr in visited:
                            continue
                        visited.add(curr)
                        if len(visited) > max_steps:
                            break
                        if curr in target_cells:
                            found = True
                            target_reached = curr
                            break
                        cx, cy = curr
                        for dx, dy in dirs_8:
                            nx, ny = cx + dx, cy + dy
                            npos = (nx, ny)
                            if not game_map.in_bounds(nx, ny):
                                continue
                            if npos not in target_cells:
                                if not game_map.is_walkable(nx, ny):
                                    continue
                                blocker = game_map.entity_at(
                                    nx, ny, exclude=player_entity,
                                )
                                if blocker is not None:
                                    continue
                            tentative_g = g_score.get(curr, 0) + 1
                            if tentative_g < g_score.get(npos, 999999):
                                came_from[npos] = curr
                                g_score[npos] = tentative_g
                                f = tentative_g + _heuristic(npos, astar_target)
                                counter += 1
                                heapq.heappush(open_set, (f, counter, npos))

                    if not found:
                        log.add("Could not find a path to that destination.")
                        return (GotoOutcome.CANCELLED, None)

                    # Reconstruct A* path
                    path: list[tuple[int, int]] = []
                    cur = target_reached
                    while cur is not None:
                        path.append(cur)
                        cur = came_from.get(cur)
                    path.reverse()
                    steps = path[1:]

                if not steps:
                    log.add("You are already at the destination.")
                    return (GotoOutcome.COMPLETED, None)

                # ---- Animate movement ----
                # Move one cell per frame with a short delay so the
                # player sees the ship glide toward the target.
                for sx, sy in steps:
                    # Update player entity position. Position is a
                    # frozen dataclass so we must replace the entire
                    # Position object rather than assigning fields.
                    player_entity.pos = world.Position(sx, sy)

                    # Re-draw the space view with camera centred on
                    # the new position. Reuse the same camera logic
                    # as the main space-mode render in _run_game.
                    sys_now = solar_system_module.current_system()
                    sol_w = sys_now.width
                    sol_h = sys_now.height
                    view_w = solar_system_module.SOL_VIEW_W
                    view_h = solar_system_module.SOL_VIEW_H
                    cam_x = max(
                        0,
                        min(sx - view_w // 2, sol_w - view_w),
                    )
                    cam_y = max(
                        0,
                        min(sy - view_h // 2, sol_h - view_h),
                    )
                    console.clear()
                    world.render_world_view(
                        console, game_map,
                        region_x=0, region_y=0,
                        region_w=view_w, region_h=view_h,
                        camera_x=cam_x, camera_y=cam_y,
                    )
                    # Skip HUD render during the brief animation —
                    # the next full frame in _run_game repaints it
                    # correctly with the real character/stats data.
                    # Only paint the message log so feedback like
                    # "Auto-nav engaged..." is visible.
                    message_log.render_message_log(
                        console, log,
                        screen_width=SCREEN_WIDTH,
                        screen_height=SCREEN_HEIGHT,
                    )
                    context.present(console)
                    _responsive_sleep(0.04)

                    # Combat interrupt: after each step, scan for
                    # nearby enemies. If an enemy is within its
                    # detect_radius, break the animation loop and
                    # surface (GotoOutcome.COMBAT, payload) so the
                    # dispatcher can invoke run_combat from the
                    # ship's CURRENT position. This is the fix for
                    # the bug where the ship silently walked
                    # through a pirate patrol without triggering
                    # combat.
                    _encounter = _detect_combat_encounter(
                        player_entity.pos, game_map,
                        solar_system_module.current_system(),
                    )
                    if _encounter is not None:
                        log.add("Auto-nav interrupted - enemies detected!")
                        return (GotoOutcome.COMBAT, _encounter)

                log.add("Auto-nav complete.")
                return (GotoOutcome.COMPLETED, None)

            # Any other key -> ignore
            continue

def render_jump_menu(
    console: tcod.console.Console,
    jp,
    target_system_id: str,
    log: message_log.MessageLog,
    *,
    screen_width: int,
    screen_height: int,
    current_fuel: int | None = None,
    max_fuel: int | None = None,
    jump_fuel_cost: int = 10,
) -> None:
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

    title = f"JUMP  -  {jp.name}  ->  {target_system.name}"
    title_y = (screen_height // 2) - 4
    console.print(
        x=ui.centered_x(title, screen_width),
        y=title_y,
        string=title,
        fg=ui.COLOR_TITLE,
    )

    desc_lines = ui.wrap_text(jp.description or "", max_width=screen_width - 8)
    for i, line in enumerate(desc_lines[:3]):
        console.print(
            x=ui.centered_x(line, screen_width),
            y=title_y + 2 + i,
            string=line,
            fg=ui.COLOR_DESCRIPTION,
        )

    option_text = f"> Jump to {target_system.name} <"
    option_y = (screen_height // 2) + 1

    # Fuel line (when ``current_fuel`` is not None). Shown
    # between the description and the jump option so the player
    # sees their fuel status at a glance before committing.
    fuel_line_y = option_y - 2
    if current_fuel is not None and max_fuel is not None:
        fuel_str = f"Fuel: {current_fuel} / {max_fuel}  |  Jump cost: {jump_fuel_cost}"
        fuel_color = (
            ui.COLOR_OPTION_HIGHLIGHT if current_fuel >= jump_fuel_cost
            else ui.COLOR_VALUE_DIM
        )
        console.print(
            x=ui.centered_x(fuel_str, screen_width),
            y=fuel_line_y,
            string=fuel_str,
            fg=fuel_color,
        )

    console.print(
        x=ui.centered_x(option_text, screen_width),
        y=option_y,
        string=option_text,
        fg=ui.COLOR_OPTION_HIGHLIGHT,
    )
    hint = "ENTER to jump - ESC to fly past"
    console.print(
        x=ui.centered_x(hint, screen_width),
        y=option_y + 2,
        string=hint,
        fg=ui.COLOR_INSTRUCTION,
    )
    message_log.render_message_log(
        console, log,
        screen_width=screen_width,
        screen_height=screen_height,
    )


def update_jump_menu(
    event: tcod.event.Event,
) -> JumpMenuOutcome:
    """Translate a key into a :class:`JumpMenuOutcome`.

    Mirror of :func:`update_planet_menu`. ESC -> BACK, ENTER
    -> JUMP, Q/WINDOW_CLOSE -> QUIT, everything else -> IGNORE.
    """
    # Use the canonical tcod pattern: event.type == "QUIT" fires
    # only on the window-close event, separate from ESC (which the
    # _ESCAPE_SYMS block below routes to BACK). Mirrors how the
    # engine's should_quit detects the Quit event, but scoped
    # narrowly so ESC doesn't also count as quit here.
    # Use the canonical tcod pattern: ``isinstance`` against
    # ``tcod.event.Quit`` + ``tcod.event.KeyDown`` replaces the
    # now-deprecated ``event.type == "QUIT"/"KEYDOWN"`` strings.
    # Mirrors update_planet_menu. The narrow type checks also
    # keep ESC from being misread as a Quit (engine.should_quit
    # is broader — we want the narrow pattern).
    if isinstance(event, tcod.event.Quit):
        return JumpMenuOutcome.QUIT
    if isinstance(event, tcod.event.KeyDown):
        # ``ui._ESCAPE_SYMS`` / ``ui._ENTER_SYMS`` are KeySym enum
        # tuples (not name strings), so comparing the NAME string
        # would always miss. Mirror update_planet_menu: read the
        # enum member directly and compare against the same enum.
        sym = event.sym
        if sym in ui._ESCAPE_SYMS:
            return JumpMenuOutcome.BACK
        if sym in ui._ENTER_SYMS:
            return JumpMenuOutcome.JUMP
    return JumpMenuOutcome.IGNORE


def _run_jump_menu(
    context: tcod.context.Context,
    jp,
    target_system_id: str,
    log: message_log.MessageLog,
    owned_ship: ship_module.OwnedShip | None = None,
) -> JumpMenuOutcome:
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
    # Resolve fuel info for the dialog if the player has a ship.
    _fuel: int | None = None
    _max_fuel: int | None = None
    if owned_ship is not None:
        ship_rec = ship_module.find_ship(owned_ship.ship_id)
        _fuel = owned_ship.fuel
        _max_fuel = ship_rec.max_fuel
    def _render() -> None:
        render_jump_menu(
            console,
            jp,
            target_system_id,
            log=log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
            current_fuel=_fuel,
            max_fuel=_max_fuel,
            jump_fuel_cost=ship_module.JUMP_FUEL_COST,
        )
    def _update(event) -> JumpMenuOutcome:
        context.convert_event(event)
        return update_jump_menu(event)
    return ui.Modal(context, console).run(_render, _update)


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
        # Drain pending SDL events to keep the window / OS
        # responsive during the animation. Events are silently
        # discarded so they don't burst-fire after the animation
        # ends (better UX than delayed input spikes).
        for _ in tcod.event.get():
            pass
        remaining = end - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, 0.01))


# JUMP_FRAME_S controls per-frame delay. Smaller = faster
# expansion. Fine-tune in 0.02 increments.
_JUMP_FRAME_S: float = 0.06

# Explosion glyphs from interior to exterior. Each frame step
# paints ONE more ring outward so the effect reads as a growing
# bright flash rather than a static starburst.
_JUMP_RING_CHARS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("*", (255, 200, 100)),   # inner core - warm gold
    ("+", (255, 255, 150)),   # ring 1      - bright yellow
    ("o", (255, 255, 200)),   # ring 2      - white-yellow
    ("O", (200, 200, 255)),   # ring 3      - pale blue-white
    ("#", (180, 180, 255)),   # ring 4      - dimmer edge
)


def _animate_jump(
    context: tcod.context.Context,
    console: tcod.console.Console,
    game_map: world.GameMap,
    player_entity: world.Entity,
    character_info,
    stats: hud.HudStats,
    log: message_log.MessageLog,
    *,
    active_mission_text: str = "",
) -> None:
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

    def _render_frame(
        rings: int,
        flash_white: bool = False,
        void: bool = False,
    ) -> None:
        """Render one frame of the animation."""
        console.clear()
        # Draw the solar system map behind the explosion.
        # Use render_world_view (not render_world) because the
        # solar system map (200x140) is larger than the viewport
        # (80x54). Camera coords centre the view on the ship.
        _view_w = solar_system_module.SOL_VIEW_W
        _view_h = solar_system_module.SOL_VIEW_H
        _sys = solar_system_module.current_system()
        _cam_x = max(
            0, min(cx - _view_w // 2, _sys.width - _view_w),
        )
        _cam_y = max(
            0, min(cy - _view_h // 2, _sys.height - _view_h),
        )
        world.render_world_view(
            console,
            game_map,
            region_x=0,
            region_y=0,
            region_w=_view_w,
            region_h=_view_h,
            camera_x=_cam_x,
            camera_y=_cam_y,
        )
        if void:
            # Pure black - skip everything.
            context.present(console)
            _responsive_sleep(frame_s)
            return
        if not flash_white:
            # Draw explosion rings. Map coords must be converted to
            # viewport-relative coords via ``_cam_x`` / ``_cam_y``
            # (render_world_view already shifted the map). Rings
            # use manhattan distance from ship centre.
            for ring_idx in range(min(rings + 1, len(_JUMP_RING_CHARS))):
                r_char, r_fg = _JUMP_RING_CHARS[ring_idx]
                dist = ring_idx + 1  # 1-indexed manhattan radius
                for dy in range(-dist, dist + 1):
                    for dx in range(-dist, dist + 1):
                        if abs(dx) + abs(dy) != dist:
                            continue
                        sx = cx + dx - _cam_x
                        sy = cy + dy - _cam_y
                        if 0 <= sx < _view_w and 0 <= sy < _view_h:
                            console.print(x=sx, y=sy, string=r_char, fg=r_fg)
            # Always paint the ship char at its current brightness
            # on top of the explosion core so the ship "pulses".
            # Convert map coords to viewport-relative coords same
            # as the rings above.
            bright_fg = (
                min(255, ship_fg[0] + rings * 30),
                min(255, ship_fg[1] + rings * 30),
                min(255, ship_fg[2] + rings * 30),
            )
            sx = cx - _cam_x
            sy = cy - _cam_y
            if 0 <= sx < _view_w and 0 <= sy < _view_h:
                console.print(x=sx, y=sy, string=ship_char, fg=bright_fg)
        else:
            # Full white flash - paint every cell visible
            # on the viewport as bright white.
            for fy in range(solar_system_module.SOL_VIEW_H):
                console.print(
                    x=0, y=fy,
                    string=" " * solar_system_module.SOL_VIEW_W,
                    fg=(255, 255, 255),
                    bg=(255, 255, 255),
                )
        # HUD + log on top so the player sees stats throughout.
        hud.render_hud(
            console,
            screen_width=SCREEN_WIDTH,
            hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT,
            character=character_info,
            stats=stats,
            active_mission=active_mission_text or None,
        )
        message_log.render_message_log(
            console,
            log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )
        context.present(console)
        _responsive_sleep(frame_s)

    # Phase 1+2: Expanding explosion rings (5 frames). Each frame
    # adds one more ring outward so the effect reads as a growing
    # bright flash centred on the ship. The first frame shows just
    # the ship with 1 small ring (*), scaling up to 5 rings.
    # Phase 1's original ship-pulsation loop was removed because
    # it drew at map coordinates (not viewport-relative) and the
    # double-present pattern was confusing. The rings provide the
    # same "build up" feel more cleanly.
    for rings in range(len(_JUMP_RING_CHARS)):
        _render_frame(rings=rings, flash_white=False)

    # Phase 3: Full white flash + black void
    _render_frame(rings=0, flash_white=True)
    _render_frame(rings=0, void=True)


def _jump_to_system(
    *,
    jp,
    player_owned_ship,
    log,
    target_system_id: str,
    target_jp_id: str,
) -> tuple:
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
    log.add("Your ship engages the jump drive. Reality blurs.")
    target_system = solar_system_module.set_current_solar_system(target_system_id)

    new_map = solar_system_module.make_solar_system()

    dest_jp = solar_system_module.find_jump_point(
        target_jp_id, system=target_system,
    )
    # ``OwnedShip`` exposes the catalogue key as ``ship_id`` (NOT
    # ``id`` — that name is reserved for the in-game ``Entity.id``
    # used by ``place_docked_ship`` and friends). Looking up
    # ``player_owned_ship.id`` raised AttributeError on the first
    # jump; fix is to thread the correct catalogue key.
    ship_record = ship_module_for_jump.find_ship(player_owned_ship.ship_id)
    new_pos = solar_system_module.place_jumped_ship(ship_record, dest_jp)

    # Append the ship entity to the new map so it RENDERS in
    # space. Without this, ``make_solar_system()`` returns a map
    # with an empty entities list (only stars + planets + jump
    # points); the player would still be able to move (position
    # is updated) but would see no character at their ship-on-map.
    # Mirrors the launch flow in :func:`_launch_to_space` which
    # builds a ``space_player`` entity from the same catalog
    # record + records ``owned=True`` so renderer / collision
    # code paths correctly classify the player's ship.
    new_ship_ent = world.Entity(
        char=ship_record.char,
        fg=ship_record.fg,
        pos=new_pos,
        name=f"Your Ship: {ship_record.name}",
        ship_id=ship_record.id,
        width=ship_record.width,
        height=ship_record.height,
        owned=True,
    )
    new_map.entities.append(new_ship_ent)
    log.add(f"You emerge near {target_system.name}.")

    return new_map, new_ship_ent


# ---------------------------------------------------------------------------
# Ship-buy dialog
# ---------------------------------------------------------------------------



def render_ship_buy(
    console: tcod.console.Console,
    ship: ship_module.Ship,
    stats: hud.HudStats,
    log: message_log.MessageLog,
    *,
    screen_width: int,
    screen_height: int,
) -> None:
    """Paint the centered ship-buy dialog into ``console``.

    Clears first so the dialog fully replaces the city view; the
    caller re-paints city + HUD + msg log once the dialog exits.
    """
    console.clear()

    title = f"A {ship.name.upper()} sits on the showroom floor."
    body = ship.description
    price_line = f"Cost: {ship.price} gold    You have: {stats.gold} gold"
    if stats.gold >= ship.price:
        afford = "Press ENTER to buy it."
    else:
        short = ship.price - stats.gold
        afford = f"You cannot afford it. ({short}g short)"
    back = "Press ESC to walk away."

    # City viewport is screen_width - HUD_WIDTH wide; we use that for
    # any line-length truncation so a long description never paints
    # over the HUD.
    max_w = screen_width - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[: max_w - 1] + "…"

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(
            x=ui.centered_x(text, screen_width),
            y=row,
            string=text,
            fg=fg,
        )

    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    paint(center_y - 4, fit(title), fg=ui.COLOR_TITLE)
    paint(center_y - 1, fit(body), fg=ui.COLOR_DESCRIPTION)
    paint(center_y + 3, fit(price_line), fg=ui.COLOR_VALUE_WHITE if stats.gold >= ship.price else ui.COLOR_VALUE_DIM)
    paint(center_y + 5, fit(afford), fg=ui.COLOR_OPTION_HIGHLIGHT if stats.gold >= ship.price else ui.COLOR_VALUE_DIM)
    paint(center_y + 7, fit(back), fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(
        console, log,
        screen_width=screen_width,
        screen_height=screen_height,
    )


def update_ship_buy(
    event: tcod.event.Event,
    ship: ship_module.Ship,
    stats: hud.HudStats,
) -> ShipBuyOutcome:
    """Map a single event for the ship-buy dialog."""
    if isinstance(event, tcod.event.Quit):
        return ShipBuyOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipBuyOutcome.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return ShipBuyOutcome.BACK
    if sym in ui._ENTER_SYMS:
        return (
            ShipBuyOutcome.BUY
            if stats.gold >= ship.price
            else ShipBuyOutcome.TOO_EXPENSIVE
        )
    return ShipBuyOutcome.IGNORE


def _run_ship_buy(
    context: tcod.context.Context,
    blocker: world.Entity,
    ship: ship_module.Ship,
    stats: hud.HudStats,
    game_map: world.GameMap,
    log: message_log.MessageLog,
) -> ShipBuyOutcome:
    """Show the ship-buy modal for ``ship`` (the entity standing in
    the player's way is ``blocker``). Returns the dialog outcome;
    callers handle the actual purchase (mutating ``stats``, removing
    ``blocker`` from ``game_map.entities``, logging).
    """
    console = make_console()
    def _render() -> None:
        render_ship_buy(
            console, ship, stats, log=log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )
    def _update(event) -> ShipBuyOutcome:
        return update_ship_buy(event, ship, stats)
    return ui.Modal(context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# NPC-talk dialog (flavor-only stub)
# ---------------------------------------------------------------------------


def render_npc_talk(
    console: tcod.console.Console,
    npc: npc_module.NPC,
    log: message_log.MessageLog,
    *,
    screen_width: int,
    screen_height: int,
    deliver_mission: mission_module.Mission | None = None,
    selected: int = 0,
) -> None:
    """Paint the centered NPC-talk dialog into ``console``.

    Layout mirrors :func:`render_ship_buy`: NPC name + guild on
    the top line, flavor text in the middle, a vertically-stacked
    MENU of selectable actions below it (NOT a static "Press
    ENTER..." hint any more), and an ESC hint at the bottom.

    The menu has 1-2 rows depending on ``deliver_mission``:

      * Always: ``"View available work"`` (opens the offerings
        modal at :func:`_run_npc_talk`).
      * When a delivery-mission is in scope: ``"Deliver <title>"``
        as the FIRST row, highlighted by default so Enter on the
        default highlight completes the mission ("common sense"
        behaviour the user explicitly requested).

    ``selected`` is the highlighted index (clamped modulo the
    number of rows by :func:`_run_npc_talk`). ``> ... <`` markers
    match the species / class / mission-offerings / ship-menu
    styles so the player only learns one highlight idiom.

    Clear-first so the modal fully replaces the city view.
    """
    console.clear()

    title = f"{npc.name} ({npc.guild})"
    body = f'"{npc.flavor_text}"'

    max_w = screen_width - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[: max_w - 1] + "…"

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(
            x=ui.centered_x(text, screen_width),
            y=row,
            string=text,
            fg=fg,
        )

    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    paint(center_y - 2, fit(title), fg=ui.COLOR_TITLE)
    paint(center_y + 1, fit(body), fg=ui.COLOR_DESCRIPTION)

    # Build the menu dynamically. The on-screen order is
    # "Deliver <title>" FIRST (when in scope) so the highlighted
    # row at startup is the obvious action — "common sense"
    # Enter completes the mission without arrow-keying. When
    # there is no delivery target, "View available work" is the
    # sole menu row and Enter opens the offerings modal as
    # before. Both rows stay selectable so the player can arrow
    # down to "View available work" even when DELIVER is on top.
    options: list[tuple[str, bool]] = []
    if deliver_mission is not None:
        options.append(("Deliver " + deliver_mission.title, True))
    options.append(("View available work", False))

    n = len(options)
    sel = selected % n
    list_top = center_y + 3
    for i, (label, is_deliver) in enumerate(options):
        row = list_top + i * 2
        is_selected = (i == sel)
        marker_open = "> " if is_selected else "  "
        marker_close = " <" if is_selected else "  "
        text = f"{marker_open}{fit(label)}{marker_close}"
        # Selected row uses the option's own accent - steel-cyan
        # for DELIVER (matches the in-space highlight), pure
        # white for View work. Dim rows get the muted lavender
        # (COLOR_OPTION) so the highlight pop still reads.
        if is_selected:
            fg = ui.COLOR_OPTION_HIGHLIGHT2 if is_deliver else ui.COLOR_OPTION_HIGHLIGHT
        else:
            fg = ui.COLOR_OPTION
        console.print(
            x=ui.centered_x(text, screen_width),
            y=row,
            string=text,
            fg=fg,
        )

    # ESC hint lives below the menu rows so its position adapts
    # automatically to whether the dialog has 1 or 2 options.
    hint = "ARROW KEYS / j,k navigate - ENTER select - ESC walk away."
    hint_row = list_top + n * 2
    if hint_row + 1 <= screen_height - MSG_LOG_HEIGHT:
        paint(hint_row, fit(hint), fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(
        console, log,
        screen_width=screen_width,
        screen_height=screen_height,
    )


def update_npc_talk(event: tcod.event.Event) -> TalkOutcome:
    """Map a single event for the NPC-talk dialog.

    Returns a NAV-AGNOSTIC outcome: ESC -> BACK, Enter -> WORK,
    window-close -> QUIT, anything else -> IGNORE. UP/DOWN /
    j/k nav is handled by :func:`_npc_talk_navigate` (a sibling
    helper used by :func:`_run_npc_talk`) so this function's
    job is purely the dialog-level outcomes.

    Note that ``TalkOutcome.WORK`` is the Enter default here; the
    caller (:func:`_run_npc_talk`) re-maps WORK to
    :attr:`TalkOutcome.DELIVER` when the highlighted option
    happens to be the "Deliver <title>" row. Keeping Enter here
    as a generic "confirm" marker lets the caller own the index-
    to-outcome mapping without the dispatcher hardcoding which
    option is deliverable.
    """
    if isinstance(event, tcod.event.Quit):
        return TalkOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return TalkOutcome.IGNORE
    if event.sym in ui._ENTER_SYMS:
        return TalkOutcome.WORK
    if event.sym in ui._ESCAPE_SYMS:
        return TalkOutcome.BACK
    return TalkOutcome.IGNORE


def _npc_talk_navigate(
    event: tcod.event.Event,
    selected: int,
    n: int,
) -> int | None:
    """If ``event`` drives NPC-talk menu nav, return the new
    ``selected`` index (modulo ``n`` options); otherwise ``None``.

    Recognises both the standard arrow keys (UP / DOWN; also KP_8
    / KP_2 via :data:`ui._UP_SYMS` / :data:`ui._DOWN_SYMS`) and
    the vertical vim keys (`j` down, `k` up). Mirrors
    :func:`_mission_navigate` and :func:`_ship_menu_navigate`
    so all three NPC-facing modals share the same nav idiom -
    one shape the smoke harness can regression-guard.
    """
    if n <= 0:
        return None
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym = event.sym
    sym_name: str = getattr(sym, "name", "").lower()
    if sym in ui._UP_SYMS or sym_name == "k":
        return (selected - 1) % n
    if sym in ui._DOWN_SYMS or sym_name == "j":
        return (selected + 1) % n
    return None


def _run_npc_talk(
    context: tcod.context.Context,
    npc: npc_module.NPC,
    log: message_log.MessageLog,
    *,
    deliver_mission: mission_module.Mission | None = None,
) -> tuple[TalkOutcome, mission_module.Mission | None]:
    """Show the talk modal for ``npc`` and return the chosen outcome.

    Dialog is a vertically-navigable menu with 1-2 selectable
    rows (``Deliver <title>`` first when in scope, then
    ``View available work`` always). The on-screen order has
    DELIVER at index 0 when present so Enter on the default
    highlight completes the mission at the target NPC — "common
    sense" behaviour the user explicitly asked for. Players who
    want to check other missions arrow down to ``View available
    work`` before pressing Enter.

    Logs ``"You chat briefly with X."`` the first time the
    dialog opens so the player has feedback that something
    happened.

    Returns ``(outcome, deliver_mission)``: ``deliver_mission``
    is the same value that was passed in whenever the outcome
    is :attr:`TalkOutcome.DELIVER`, and ``None`` for every other
    outcome so callers don't have to discriminate on the
    outcome enum.
    """
    log.add(f"You chat briefly with {npc.name}.")
    console = make_console()
    selected = 0
    n_options = 1 + (1 if deliver_mission is not None else 0)
    def _render() -> None:
        render_npc_talk(
            console, npc, log=log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
            deliver_mission=deliver_mission,
            selected=selected,
        )
    def _update(event) -> TalkOutcome:
        nonlocal selected
        # Navigation FIRST so UP/DOWN / j/k adjust the highlight
        # before any other key press fires an outcome. Mirrors
        # _run_mission_offerings so the dispatcher shapes line up.
        new = _npc_talk_navigate(event, selected, n_options)
        if new is not None:
            selected = new
            return TalkOutcome.IGNORE
        result = update_npc_talk(event)
        if result is TalkOutcome.IGNORE:
            return TalkOutcome.IGNORE
        if result is TalkOutcome.QUIT:
            return TalkOutcome.QUIT
        if result is TalkOutcome.BACK:
            return TalkOutcome.BACK
        # WORK/DELIVER: the highlighted row decides DELIVER (row 0
        # when a delivery target is in scope) vs WORK (open the
        # offerings modal — row 1, or row 0 when no DELIVER).
        return TalkOutcome.DELIVER if (deliver_mission is not None and selected == 0) else TalkOutcome.WORK
    outcome = ui.Modal(context, console).run(_render, _update)
    # Derive payload from outcome (Modal returns just the enum).
    if outcome is TalkOutcome.DELIVER:
        return outcome, deliver_mission
    return outcome, None


# ---------------------------------------------------------------------------
# Mission offerings + quest log (active-mission view with abandon)
# ---------------------------------------------------------------------------
#
# Two separate modals live here so the per-NPC interaction path
# (open offerings -> accept) and the city-wide quest log path
# (open with Q -> view details -> abandon with confirm) don't tangle.
# The mission catalog lives in :mod:`spacehack.mission`; these
# functions are pure UI + dispatcher.

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


def _offerings_to_menu(
    npc: npc_module.NPC,
    offerings: tuple[mission_module.Mission, ...],
) -> tuple[str, tuple[tuple[str, str], ...], dict[str, str]]:
    """Build an :class:`spacehack.ui.MenuScreen` payload from an
    NPC-mission-list so we can reuse the shared menu primitives.

    ``available_options`` is ``(id, label)`` where label is
    ``"{title} ({reward}gp)"`` so the player sees the reward in
    the listing. ``descriptions`` is the mission body blurb.
    """
    available_options = tuple(
        (str(i), f"{m.title} ({m.reward_gold}gp)")
        for i, m in enumerate(offerings)
    )
    descriptions = {str(i): m.description for i, m in enumerate(offerings)}
    return f"{npc.name} - available work", available_options, descriptions


def render_mission_offerings(
    console: tcod.console.Console,
    npc: npc_module.NPC,
    offerings: tuple[mission_module.Mission, ...],
    selected: int,
    log: message_log.MessageLog,
    *,
    screen_width: int,
    screen_height: int,
) -> None:
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
        return line if len(line) <= max_w else line[: max_w - 1] + "…"

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(
            x=ui.centered_x(text, screen_width),
            y=row,
            string=text,
            fg=fg,
        )

    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    paint(center_y - 6, fit(title), fg=ui.COLOR_TITLE)

    sel = selected % n if n else 0
    list_top = center_y - 4
    for i, (_, label) in enumerate(options):
        row = list_top + i * 2
        is_selected = (i == sel)
        marker = "> " if is_selected else "  "
        end_marker = " <" if is_selected else "  "
        text = f"{marker}{fit(label)}{end_marker}"
        console.print(
            x=ui.centered_x(text, screen_width),
            y=row,
            string=text,
            fg=ui.COLOR_OPTION_HIGHLIGHT if is_selected else ui.COLOR_OPTION,
        )

    desc = descriptions.get(str(sel), "") if descriptions else ""
    desc_rows = ui.wrap_text(desc, max_w)
    desc_start_row = list_top + n * 2 + 1
    for j, line in enumerate(desc_rows):
        paint(desc_start_row + j, line, fg=ui.COLOR_DESCRIPTION)

    # Refresh the bottom hint each render - the selected mission's
    # reward gold/xp and the recommended-class hint both belong here
    # so the player sees context before committing with Enter.
    hint_lines: list[str] = [
        "ARROW KEYS / j,k navigate - ENTER accept - ESC walk away."
    ]
    if offerings:
        picked = offerings[sel]
        hint_lines.append(
            f"Reward: {picked.reward_gold}gp + {picked.reward_xp}xp"
        )
        if picked.recommended_class_id:
            klass = find_class(picked.recommended_class_id)
            hint_lines.append(f"Best suited for: {klass.name}")
        if picked.recommended_ship_min_cargo > 0:
            hint_lines.append(
                f"Ship cargo recommended: {picked.recommended_ship_min_cargo}+"
            )
    for i, line in enumerate(hint_lines):
        paint(
            desc_start_row + max(len(desc_rows), 1) + 1 + i,
            fit(line),
            fg=ui.COLOR_INSTRUCTION,
        )


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


def _mission_navigate(
    event: tcod.event.Event,
    selected: int,
    n: int,
) -> int | None:
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
    sym_name: str = getattr(sym, "name", "").lower()
    if sym in ui._UP_SYMS or sym_name == "k":
        return (selected - 1) % n
    if sym in ui._DOWN_SYMS or sym_name == "j":
        return (selected + 1) % n
    return None


def _run_mission_offerings(
    context: tcod.context.Context,
    npc: npc_module.NPC,
    offerings: tuple[mission_module.Mission, ...],
    log: message_log.MessageLog,
) -> tuple[MissionOutcome, mission_module.Mission | None]:
    """Show the NPC's offerings modal and return the choice.

    Returns ``(MissionOutcome, picked_mission)``: ``picked`` is
    ``None`` whenever the outcome is not ACCEPT. The caller
    (:func:`_run_game`) is responsible for swapping
    ``player_active_mission`` once it sees an ACCEPT.
    """
    console = make_console()
    selected = 0
    def _render() -> None:
        render_mission_offerings(
            console, npc, offerings, selected, log=log,
            screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
        )
    def _update(event) -> MissionOutcome:
        nonlocal selected
        new = _mission_navigate(event, selected, len(offerings))
        if new is not None:
            selected = new
            return MissionOutcome.IGNORE
        return update_mission_offerings(event)
    outcome = ui.Modal(context, console).run(_render, _update)
    # Derive payload from outcome (Modal returns just the enum).
    if outcome is MissionOutcome.ACCEPT:
        return outcome, offerings[selected % len(offerings)]
    return outcome, None


def render_quest_log(
    console: tcod.console.Console,
    active: mission_module.ActiveMission | None,
    log: message_log.MessageLog,
    *,
    confirm_abandon: bool = False,
    screen_width: int,
    screen_height: int,
) -> None:
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
        return line if len(line) <= max_w else line[: max_w - 1] + "…"

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(
            x=ui.centered_x(text, screen_width),
            y=row,
            string=text,
            fg=fg,
        )

    center_y = (screen_height - MSG_LOG_HEIGHT) // 2

    if active is None:
        paint(center_y - 2, fit("QUEST LOG"), fg=ui.COLOR_TITLE)
        paint(center_y + 1, fit("(no active mission)"), fg=ui.COLOR_DESCRIPTION)
        paint(center_y + 5, fit("Press ESC to close."), fg=ui.COLOR_INSTRUCTION)
        message_log.render_message_log(
            console, log,
            screen_width=screen_width,
            screen_height=screen_height,
        )
        return

    mission = mission_module.find_mission(active.mission_id)
    giver = npc_module.find_npc(mission.giver_npc_id)

    paint(center_y - 6, fit("QUEST LOG"), fg=ui.COLOR_TITLE)
    paint(center_y - 3, fit(mission.title.upper()), fg=ui.COLOR_TITLE)
    paint(center_y - 1, fit(f"From: {giver.name} ({giver.guild})"), fg=ui.COLOR_DESCRIPTION)

    # Wrap mission.description onto multiple rows instead of
    # ellipsis-clipping it (the relation between screen_height and
    # the description text drove the user-visible bug). Reward +
    # abandon button anchor relative to the description's last row
    # so the layout scales with text length.
    desc_rows = ui.wrap_text(mission.description, max_w)
    desc_start_row = center_y + 2
    for j, line in enumerate(desc_rows):
        paint(desc_start_row + j, line, fg=ui.COLOR_VALUE_WHITE)

    reward_row = desc_start_row + len(desc_rows) + 1
    paint(
        reward_row,
        fit(f"Reward: {mission.reward_gold}gp + {mission.reward_xp}xp"),
        fg=ui.COLOR_VALUE_WHITE,
    )

    button_row = reward_row + 3
    if confirm_abandon:
        paint(
            button_row,
            fit("Press ENTER to abandon. ESC cancels."),
            fg=ui.COLOR_OPTION_HIGHLIGHT,
        )
    else:
        paint(
            button_row,
            fit("Press A to abandon. ESC to close."),
            fg=ui.COLOR_INSTRUCTION,
        )
    message_log.render_message_log(
        console, log,
        screen_width=screen_width,
        screen_height=screen_height,
    )


def update_quest_log(
    event: tcod.event.Event,
    *,
    confirm_abandon: bool,
) -> QuestLogOutcome:
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
    sym_name: str = getattr(sym, "name", "").lower()
    if sym in ui._ESCAPE_SYMS:
        return QuestLogOutcome.BACK
    if confirm_abandon:
        if sym in ui._ENTER_SYMS:
            return QuestLogOutcome.ABANDONED
        return QuestLogOutcome.IGNORE
    if sym_name == "a":
        return QuestLogOutcome.ABANDONED
    return QuestLogOutcome.IGNORE


def _run_quest_log(
    context: tcod.context.Context,
    active: mission_module.ActiveMission | None,
) -> tuple[QuestLogOutcome, mission_module.ActiveMission | None]:
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
        render_quest_log(
            console, active, log=log,
            confirm_abandon=confirm_abandon,
            screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
        )
    def _update(event) -> QuestLogOutcome:
        nonlocal confirm_abandon
        result = update_quest_log(event, confirm_abandon=confirm_abandon)
        if result is QuestLogOutcome.ABANDONED and not confirm_abandon:
            # First A press: flip into confirm state and re-render.
            confirm_abandon = True
            return QuestLogOutcome.IGNORE
        return result
    outcome = ui.Modal(context, console).run(_render, _update)
    # Derive payload from outcome.
    if outcome is QuestLogOutcome.ABANDONED:
        return outcome, None
    return outcome, active


# ---------------------------------------------------------------------------
# Ship-hangar menu (View / Sell / Launch) + View sub-modal
# ---------------------------------------------------------------------------
#
# The 3-option menu lives in the same centered-modal style as the
# ship-buy and NPC-talk dialogs. ``Sell`` and ``Launch`` are
# placeholders for this iteration (they just log ``"Coming soon."``
# and return BACK) so the wiring matches the future design without
# needing more game logic yet. ``View`` opens a sub-modal that
# reports per-ship stats (cargo, weapons, modules, hull).
#
# The player may or may not own a ship - callers must check before
# opening the modal; if ``owned_ship`` is ``None`` we still draw the
# menu but show a hint instead of stats.

SHIP_MENU_OPTIONS: tuple[str, ...] = ("View", "Refuel", "Sell", "Launch")


# Planet-bump dialog: single "Land" option. ESC closes the modal
# without acting on the planet (the player can keep flying past).
PLANET_MENU_OPTIONS: tuple[str, ...] = ("Land",)


def render_ship_menu(
    console: tcod.console.Console,
    ship: ship_module.Ship,
    owned: ship_module.OwnedShip,
    log: message_log.MessageLog,
    selected: int = 0,
    *,
    screen_width: int,
    screen_height: int,
) -> None:
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

    # Title row: the ship name + its catalogue description.
    title = f"Your {ship.name.upper()}"
    sub = ship.description
    if owned is None:
        sub = "(no ship owned yet)"

    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    console.print(
        x=ui.centered_x(title, screen_width),
        y=center_y - 5,
        string=title,
        fg=ui.COLOR_TITLE,
    )
    console.print(
        x=ui.centered_x(sub, screen_width),
        y=center_y - 3,
        string=sub,
        fg=ui.COLOR_DESCRIPTION,
    )

    # Fuel status line (when ship is owned). Painted after the
    # description so the player sees current fuel / max fuel and
    # the refuel cost per unit at a glance before scrolling the
    # menu. Omitted when ``owned`` is None (no ship yet).
    if owned is not None:
        fuel_str = (
            f"Fuel: {owned.fuel} / {ship.max_fuel}  "
            f"[Refuel: {ship_module.FUEL_COST_PER_UNIT}g/u]"
        )
        console.print(
            x=ui.centered_x(fuel_str, screen_width),
            y=center_y - 1,
            string=fuel_str,
            fg=ui.COLOR_VALUE_WHITE,
        )

    # Vertical spaced option list. The highlight color and the
    # ``>`` / ``<`` markers track ``selected`` so a "wrapped"
    # selection (e.g. selected=-1 mod 3 == 2) lands on Launch and
    # not off-screen.
    list_top = center_y + 1 if owned is not None else center_y - 1
    n = len(SHIP_MENU_OPTIONS)
    sel = selected % n
    for i, label in enumerate(SHIP_MENU_OPTIONS):
        row = list_top + i * 2
        is_selected = (i == sel)
        marker = "> " if is_selected else "  "
        end_marker = " <" if is_selected else "  "
        # Append fuel info to the Refuel label so the
        # player sees quantity + price without needing
        # the message bar (hidden while menu is open).
        if label == "Refuel" and owned is not None:
            label = f"{label} [{owned.fuel}/{ship.max_fuel}]"
        text = f"{marker}{label}{end_marker}"
        console.print(
            x=ui.centered_x(text, screen_width),
            y=row,
            string=text,
            fg=ui.COLOR_OPTION_HIGHLIGHT if is_selected else ui.COLOR_OPTION,
        )

    # Bottom hint row mirrors the other modals.
    console.print(
        x=ui.centered_x("ARROW KEYS / j,k navigate - ENTER select - ESC walk away.",
                        screen_width),
        y=center_y + len(SHIP_MENU_OPTIONS) * 2 + 1,
        string="ARROW KEYS / j,k navigate - ENTER select - ESC walk away.",
        fg=ui.COLOR_INSTRUCTION,
    )
    message_log.render_message_log(
        console, log,
        screen_width=screen_width,
        screen_height=screen_height,
    )


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
    sym_name: str = getattr(sym, "name", "").lower()
    if sym in ui._UP_SYMS or sym_name == "k":
        return (selected - 1) % len(SHIP_MENU_OPTIONS)
    if sym in ui._DOWN_SYMS or sym_name == "j":
        return (selected + 1) % len(SHIP_MENU_OPTIONS)
    return None


def update_ship_menu(
    event: tcod.event.Event,
    selected: int,
) -> ShipMenuAction:
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
        return (
            ShipMenuAction.VIEW
            if selected == 0
            else ShipMenuAction.REFUEL
            if selected == 1
            else ShipMenuAction.SELL
            if selected == 2
            else ShipMenuAction.LAUNCH
        )
    return ShipMenuAction.IGNORE


def render_ship_view(
    console: tcod.console.Console,
    ship: ship_module.Ship,
    owned: ship_module.OwnedShip,
    log: message_log.MessageLog,
    *,
    screen_width: int,
    screen_height: int,
) -> None:
    """Paint the read-only ship-stats panel.

    Reports cargo (used / max), weapons (attached / slots), modules
    (installed / slots), and current hull damage. If ``owned`` is
    ``None`` we still draw the panel so the View option is never
    useless - it shows the catalogue entry instead.
    """
    console.clear()

    title = f"{ship.name.upper()} - DETAILS"
    center_y = (screen_height - MSG_LOG_HEIGHT) // 2
    console.print(
        x=ui.centered_x(title, screen_width),
        y=center_y - 6,
        string=title,
        fg=ui.COLOR_TITLE,
    )

    cargo_used = owned.cargo_used if owned is not None else 0
    weapons_n = len(owned.weapons) if owned is not None else 0
    modules_n = len(owned.modules) if owned is not None else 0
    hull_pct = owned.hull_damage_pct if owned is not None else 0

    cargo_line = f"Cargo: {cargo_used} / {ship.max_cargo}"
    weapons_line = f"Weapons attached: {weapons_n} / {ship.weapon_slots}"
    modules_line = f"Modules installed: {modules_n} / {ship.module_slots}"
    hull_line = f"Hull damage: {hull_pct}%"
    fuel_line = f"Fuel: {owned.fuel} / {ship.max_fuel}"

    lines = (cargo_line, weapons_line, modules_line, hull_line, fuel_line)
    for i, line in enumerate(lines):
        row = center_y - 3 + i * 2
        console.print(
            x=ui.centered_x(line, screen_width),
            y=row,
            string=line,
            fg=ui.COLOR_VALUE_WHITE if owned is not None else ui.COLOR_VALUE_DIM,
        )

    console.print(
        x=ui.centered_x("Press any key to return.", screen_width),
        y=center_y + len(lines) * 2 + 1,
        string="Press any key to return.",
        fg=ui.COLOR_INSTRUCTION,
    )
    message_log.render_message_log(
        console, log,
        screen_width=screen_width,
        screen_height=screen_height,
    )


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


def _run_ship_menu(
    context: tcod.context.Context,
    ship: ship_module.Ship,
    owned: ship_module.OwnedShip,
    stats: hud.HudStats,
    log: message_log.MessageLog,
) -> ShipMenuAction:
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
        render_ship_menu(
            console, ship, owned, log=log, selected=selected,
            screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
        )
    def _update(event) -> ShipMenuAction:
        nonlocal selected
        new = _ship_menu_navigate(event, selected)
        if new is not None:
            selected = new
            return ShipMenuAction.IGNORE
        return update_ship_menu(event, selected)
    while True:
        action = ui.Modal(context, console).run(_render, _update)
        if action is ShipMenuAction.VIEW:
            _run_ship_view(context, ship, owned, log)
            continue
        if action is ShipMenuAction.REFUEL:
            ship_record = ship_module.find_ship(owned.ship_id)
            buyable = ship_record.max_fuel - owned.fuel
            if buyable <= 0:
                log.add("The fuel tank is already full.")
                continue
            affordable = stats.gold // ship_module.FUEL_COST_PER_UNIT
            if affordable <= 0:
                log.add("You don't have enough gold to buy fuel.")
                continue
            units = min(buyable, affordable)
            cost = units * ship_module.FUEL_COST_PER_UNIT
            stats.gold -= cost
            owned.fuel += units
            log.add(
                f"Refueled {units} units for {cost}g. "
                f"Fuel: {owned.fuel} / {ship_record.max_fuel}."
            )
            continue
        return action  # BACK, SELL, LAUNCH, QUIT


def _run_ship_view(
    context: tcod.context.Context,
    ship: ship_module.Ship,
    owned: ship_module.OwnedShip,
    log: message_log.MessageLog,
) -> None:
    """Show the read-only stats panel for ``ship``.

    Stays inside its own loop until the player presses any key
    (so the player has time to read the stats before returning to
    the menu). On Quit the panel closes and returns; on ESC it
    closes faster via a direct BACK return.
    """
    console = make_console()
    def _render() -> None:
        render_ship_view(
            console, ship, owned, log=log,
            screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT,
        )
    def _update(event) -> ShipViewOutcome:
        # Any KeyDown closes the panel (mirrors the original "any
        # key closes" semantic that drove this loop). update_ship_view
        # itself returns QUIT for Quit events and BACK for ESC, so
        # those flow through Modal unchanged.
        if isinstance(event, tcod.event.KeyDown):
            return ShipViewOutcome.BACK
        return update_ship_view(event)
    ui.Modal(context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Space-scene helpers (launch + return animations, scene swap)
# ---------------------------------------------------------------------------


def _find_hangar_ship(
    city_game_map: world.GameMap,
    player_owned_ship: ship_module.OwnedShip | None,
) -> world.Entity | None:
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
    return next(
        (e for e in city_game_map.entities
         if e.owned and e.ship_id == player_owned_ship.ship_id),
        None,
    )


def render_planet_menu(
    console: tcod.console.Console,
    planet_obj: solar_system_module.Planet,
    log: message_log.MessageLog,
    *,
    screen_width: int = SCREEN_WIDTH,
    screen_height: int = SCREEN_HEIGHT,
    has_port: bool = True,
) -> None:
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

    # Title row (planet name)
    title_y = screen_height // 4
    console.print(
        x=ui.centered_x(planet_obj.name, screen_width),
        y=title_y,
        string=planet_obj.name,
        fg=ui.COLOR_TITLE,
    )

    # Body row(s): planet description, wrapped if longer than viewport
    desc_y = title_y + 2
    desc_rows = ui.wrap_text(planet_obj.description, screen_width - 4)
    for i, row in enumerate(desc_rows):
        console.print(
            x=ui.centered_x(row, screen_width),
            y=desc_y + i,
            string=row,
            fg=ui.COLOR_DESCRIPTION,
        )

    # Option row: a single highlighted "Land" cell IF the planet
    # has a landable port; otherwise a lighter "No port on this
    # world." info-line (ENTER still occupies the slot but acts as
    # a closer in update_planet_menu).
    option_y = (screen_height // 2) + 2
    if has_port:
        option_text = "> Land <"
        hint = "ENTER to land - ESC to fly away"
        option_fg = ui.COLOR_OPTION_HIGHLIGHT
        hint_fg = ui.COLOR_INSTRUCTION
    else:
        option_text = "No port on this world."
        hint = "ENTER or ESC to fly past."
        option_fg = ui.COLOR_DESCRIPTION
        hint_fg = ui.COLOR_INSTRUCTION
    console.print(
        x=ui.centered_x(option_text, screen_width),
        y=option_y,
        string=option_text,
        fg=option_fg,
    )
    hint_y = option_y + 2
    console.print(
        x=ui.centered_x(hint, screen_width),
        y=hint_y,
        string=hint,
        fg=hint_fg,
    )
    message_log.render_message_log(
        console, log,
        screen_width=screen_width,
        screen_height=screen_height,
    )


def update_planet_menu(
    event: tcod.event.Event,
    *,
    has_port: bool = True,
) -> PlanetMenuOutcome:
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
        return (
            PlanetMenuOutcome.LAND
            if has_port
            else PlanetMenuOutcome.BACK
        )
    return PlanetMenuOutcome.IGNORE


def _run_planet_menu(
    context: tcod.context.Context,
    planet_obj: solar_system_module.Planet,
    *,
    character_info: dict,
    stats: hud.HudStats,
    log: message_log.MessageLog,
    active_mission_text: str | None,
) -> PlanetMenuOutcome:
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
        render_planet_menu(console, planet_obj, log=log, has_port=has_port)
    def _update(event) -> PlanetMenuOutcome:
        return update_planet_menu(event, has_port=has_port)
    return ui.Modal(context, console).run(_render, _update)


def _animate_ship_to_y(
    context: tcod.context.Context,
    console: tcod.console.Console,
    ship_ent: world.Entity,
    game_map: world.GameMap,
    *,
    character_info: dict,
    stats: hud.HudStats,
    log: message_log.MessageLog,
    active_mission_text: str | None,
    target_y: int,
    frame_seconds: float = 0.08,
) -> None:
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
        # Position is frozen; rebind ship_ent.pos to a fresh Position
        # rather than mutate pos.y in place (would raise FrozenInstanceError).
        ship_ent.pos = world.Position(ship_ent.pos.x, ship_ent.pos.y + direction)
        console.clear()
        world.render_world(
            console,
            game_map,
            region_x=0,
            region_y=0,
            region_w=solar_system_module.SOL_VIEW_W,
            region_h=solar_system_module.SOL_VIEW_H,
        )
        hud.render_hud(
            console,
            screen_width=SCREEN_WIDTH,
            hud_view_height=solar_system_module.SOL_VIEW_H,
            character=character_info,
            stats=stats,
            active_mission=active_mission_text,
        )
        message_log.render_message_log(
            console,
            log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )
        context.present(console)
        _responsive_sleep(frame_seconds)


def _launch_to_space(
    context: tcod.context.Context,
    console: tcod.console.Console,
    city_game_map: world.GameMap,
    hangar_ship_ent: world.Entity,
    ship_obj: ship_module.Ship,
    current_city_id: str,
    city_player: world.Entity,
    *,
    character_info: dict,
    stats: hud.HudStats,
    log: message_log.MessageLog,
    active_mission_text: str | None,
) -> tuple[world.GameMap, world.Entity]:
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
    # Hide the on-foot @ during the launch animation - the
    # player has stepped aboard the ship and is no longer standing
    # on the city surface. Splice the entity out of the city's
    # entity list so ``world.render_world`` doesn't paint two
    # bodies at once. The @ stays spliced out while the player is
    # in space, and gets reattached on land (see :func:`_return_to_city`
    # and the cross-planet LAND branch in :func:`_run_game`).
    if city_player in city_game_map.entities:
        city_game_map.entities.remove(city_player)
    offscreen_y = -(solar_system_module.SOL_VIEW_H // 2) - 1
    if hangar_ship_ent.pos.y > offscreen_y:
        _animate_ship_to_y(
            context, console, hangar_ship_ent, city_game_map,
            character_info=character_info,
            stats=stats,
            log=log,
            active_mission_text=active_mission_text,
            target_y=offscreen_y,
        )
        log.add(f"You launch the {ship_obj.name} into space.")
    space_map = solar_system_module.make_solar_system()
    origin_planet = solar_system_module.find_planet(current_city_id)
    space_player = solar_system_module.place_docked_ship(
        ship_obj, origin_planet,
    )
    space_map.entities.append(space_player)
    return space_map, space_player


def _return_to_city(
    context: tcod.context.Context,
    console: tcod.console.Console,
    hangar_ship_ent: world.Entity,
    city_game_map: world.GameMap,
    city_player_ent: world.Entity,
    *,
    character_info: dict,
    stats: hud.HudStats,
    log: message_log.MessageLog,
    active_mission_text: str | None,
) -> tuple[world.GameMap, world.Entity]:
    """Animate the same ``hangar_ship_ent`` down to :data:`world.HANGAR_ANCHOR`
    and return ``(city_game_map, city_player_entity)``.

    Mirrors :func:`_launch_to_space`: the ship entity is the SAME
    instance that was animated offscreen during launch, so no
    entity-list swap is needed on the city map.
    """
    _animate_ship_to_y(
        context, console, hangar_ship_ent, city_game_map,
        character_info=character_info,
        stats=stats,
        log=log,
        active_mission_text=active_mission_text,
        target_y=world.HANGAR_ANCHOR.y,
    )
    # The ship has docked - the player has stepped off and is
    # standing on the city surface again. Reattach the @ entity
    # so :func:`world.render_world` paints it on the next frame.
    if city_player_ent not in city_game_map.entities:
        city_game_map.entities.append(city_player_ent)
    log.add("You return to Earth and dock at your hangar.")
    return city_game_map, city_player_ent


# ---------------------------------------------------------------------------
# Game (city) loop
# ---------------------------------------------------------------------------


def _run_game(
    context: tcod.context.Context,
    species_id: str,
    class_id: str,
) -> None:
    """Render the small city + HUD + msg log and handle vim movement.

    Walking into a wall logs a short message. Walking into a
    non-interactable entity logs a "bump" message. Walking into
    a ship (at the space port) opens the ship-buy modal; walking
    into a guild NPC opens the flavor-talk modal.
    """
    species = find_species(species_id)
    klass = find_class(class_id)

    CITY_WIDTH, CITY_HEIGHT = 60, 40
    game_map = world.make_city(width=CITY_WIDTH, height=CITY_HEIGHT)
    player = world.Entity(
        char="@",
        fg=(255, 255, 255),
        pos=world.Position(x=CITY_WIDTH // 2, y=CITY_HEIGHT // 2),
        name="Player",
    )
    game_map.entities.append(player)

    stats = character.starting_stats(species_id, class_id)

    log = message_log.MessageLog(capacity=MSG_LOG_HEIGHT)
    log.add(f"You arrive in a quiet Earth city as a {species.name} {klass.name}.")
    log.add("The cobblestones are damp from last night's rain.")
    log.add("Walk with h / j / k / l; diagonals y / u / b / n.")
    log.add("Buildings: North-West space port, South-West merchant guild,")
    log.add("Bar in the plaza, militia + bounty guild on the South-East.")
    log.add("Visit the space port to buy a ship; the guild halls offer work later.")

    # Player-owned ship. None until they buy one at the port.
    # Multiple ships at once are intentionally not supported: the
    # Sell / Launch options of the hangar menu are stubs so we don't
    # need a fleet state yet. When the menu is implemented, this
    # single slot becomes the player's only-active-ship selection.
    player_owned_ship: ship_module.OwnedShip | None = None

    # Player-active mission. None until they accept one at an NPC.
    # Single slot mirrors the single-ship design - the player can
    # only juggle one mission at a time, with the rule "abandon
    # before picking up another" enforced in the dispatcher.
    # Completion / failure outcomes land in a later iteration.
    player_active_mission: mission_module.ActiveMission | None = None

    character_info = {
        "species_name": species.name,
        "class_name": klass.name,
    }

    map_w = SCREEN_WIDTH - HUD_WIDTH
    map_h = SCREEN_HEIGHT - MSG_LOG_HEIGHT
    console = make_console()

    # Scene-mode state. ``current_mode`` toggles between "city" and
    # "space" when the player launches from the city hangar. The
    # render block below uses the current ``game_map`` / ``player``
    # regardless of mode (same render pipeline), and the dispatch
    # block branches on ``current_mode`` for vim movement + ESC
    # behaviour. ``city_game_map`` / ``city_player`` aliases preserve
    # the city scene so the return-from-space branch can swap back
    # cleanly. ``space_game_map`` / ``space_player_entity`` are
    # created lazily on launch (rebuilt fresh each time - cheap
    # enough at ~4320 tiles that caching isn't worth the extra
    # state to manage).
    city_game_map = game_map
    city_player = player
    current_mode: str = "city"
    # The planet id whose game_map / hangar_anchor is active in
    # city mode. Starts as Earth and flips to Mars (or back) when
    # the player lands on a non-Earth planet tile. Drives per-planet
    # routing in the planet-bump dispatch.
    current_city_id: str = "earth"

    while True:
        console.clear()
        # Mode-aware render. City mode centers the small city map
        # inside the viewport (unchanged from the pre-multicell
        # iteration). Space mode is much larger than the viewport
        # (~2.5x wider, ~2.6x taller) so we scroll: camera centers
        # on the ship so the scout stays at the screen-center while
        # planets scroll past, and clamping keeps the viewport on
        # the map (no "you can see past the edge" glitch when the
        # ship nears the map border).
        if current_mode == "space":
            # Multi-system iteration: SOL_W/SOL_H no longer live
            # as module-level constants (they vary per system now
            # and live on each ``SolarSystem.width``/``.height``).
            # Cache ``current_system()`` once so the rebuild-cache
            # path doesn't get re-triggered inside the render call.
            sys_now = solar_system_module.current_system()
            sol_w = sys_now.width
            sol_h = sys_now.height
            view_w = solar_system_module.SOL_VIEW_W
            view_h = solar_system_module.SOL_VIEW_H
            cam_x = max(
                0, min(player.pos.x - view_w // 2, sol_w - view_w),
            )
            cam_y = max(
                0, min(player.pos.y - view_h // 2, sol_h - view_h),
            )
            world.render_world_view(
                console, game_map,
                region_x=0, region_y=0,
                region_w=view_w, region_h=view_h,
                camera_x=cam_x, camera_y=cam_y,
            )
        else:
            world.render_world(
                console,
                game_map,
                region_x=0,
                region_y=0,
                region_w=map_w,
                region_h=map_h,
            )
        # Pre-resolve the active-mission label once per frame so the
        # HUD doesn't have to know about the mission catalog.
        active_mission_text = (
            mission_module.find_mission(player_active_mission.mission_id).title
            if player_active_mission is not None
            else None
        )
        # Resolve ship catalog entry for the space-mode HUD.
        _show_ship_hud = current_mode == "space" and player_owned_ship is not None
        _ship_cat = (
            ship_module.find_ship(player_owned_ship.ship_id)
            if _show_ship_hud else None
        )
        # Location string: planet name in city, system name in space.
        if current_mode == "space":
            _location = solar_system_module.current_system().name
        else:
            _location = current_city_id.replace("_", " ").title()
        hud.render_hud(
            console,
            screen_width=SCREEN_WIDTH,
            hud_view_height=map_h,
            character=character_info,
            stats=stats,
            active_mission=active_mission_text,
            location=_location,
            owned_ship=player_owned_ship if _show_ship_hud else None,
            ship_catalog=_ship_cat,
        )
        message_log.render_message_log(
            console,
            log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )
        context.present(console)
        for event in tcod.event.wait():
            # ESC exits the game from BOTH city and space modes —
            # the user explicitly asked for ESC to remain the
            # canonical quit key. Returning to the city from space
            # is done by the planet-bump dialog on Earth (Land
            # option), not by ESC. Window-close Quit events still
            # exit cleanly from both modes via ``should_quit``.
            if should_quit(event):
                return
            # Q opens the city quest-log overlay (active-mission
            # view + the only path to abandon). Routed BEFORE the
            # vim dispatch so the key's intent is unambiguous even
            # though 'q' isn't a movement letter today.
            if _is_q_press(event):
                outcome, new_active = _run_quest_log(
                    context, player_active_mission,
                )
                if outcome is QuestLogOutcome.QUIT:
                    return
                if outcome is QuestLogOutcome.ABANDONED:
                    if player_active_mission is not None:
                        abandoned = mission_module.find_mission(
                            player_active_mission.mission_id,
                        )
                        log.add(f"You abandoned: {abandoned.title}.")
                        # Release the cargo the mission was holding
                        # back to the hull so abandoning actually
                        # returns the ship to its free capacity.
                        # ``abort_mission`` is a no-op for missions
                        # that didn't load any cargo (most combat /
                        # diplomacy jobs), so the log line stays
                        # short for the common case.
                        mission_module.abort_mission(
                            abandoned, player_owned_ship, log,
                        )
                    player_active_mission = new_active
                # BACK: silent (player just closed the overlay).
                continue
            # M opens the system-map navigation overlay (whole Sol
            # + the player's ship position). Only active in space
            # mode - in city mode M has no defined effect today so
            # we route it through the no-op path. Routed BEFORE the
            # vim dispatch so the key's intent is unambiguous. (M
            # was chosen over N because N is mapped by
            # ``world.VIM_DELTAS`` as the south-east diagonal, so
            # N for nav inadvertently shadowed vim movement in
            # city mode.)
            if current_mode == "space" and _is_m_press(event):
                outcome = _run_navigation(context, player.pos)
                if outcome is NavigationOutcome.QUIT:
                    return
                # BACK / IGNORE fall through; we just painted the
                # overlay one frame and resume the space render.
                continue

            # G key opens the Go To modal (auto-nav) - only in space
            # mode since city mode has no big map to navigate.
            if current_mode == "space" and _is_g_press(event):
                _goto_outcome, _goto_combat = _run_goto(
                    context, game_map, player, log,
                )
                # COMBAT is the new auto-nav interrupt: the
                # animation loop broke early because a step
                # crossed into an enemy detect_radius. Route
                # through the same _handle_combat_encounter
                # helper the post-move dispatcher uses so the
                # two paths can't drift apart (VICTORY/DEFEAT
                # handling, log lines, etc.).
                if (_goto_outcome is GotoOutcome.COMBAT
                        and _goto_combat is not None):
                    _handle_combat_encounter(
                        console, context, player_owned_ship, player,
                        game_map, log, _goto_combat,
                    )
                # After auto-nav we always re-render on the next
                # iteration of the main loop. The ship position was
                # updated in-place on the GameMap so the next frame
                # shows the new location.
                continue
            delta = _vim_action(event)
            if delta is None:
                continue
            dx, dy = delta
            code, blocker = world.try_move(player, game_map, dx, dy)
            # Combat detection: after any move in space, check for nearby enemies.
            # Squad-aware: spawns sharing a non-empty ``squad_id`` form
            # a logical squad, so when ANY alive squad member is within
            # detect_radius of the **player**, ALL alive members of that
            # squad join the encounter (even if some wander beyond the
            # player's radius). Standalone spawns (squad_id=None) still
            # engage by player-proximity only, preserving v1 behaviour.
            # Two passes so pass 2 sees every alive spawn when deciding
            # whether its squad was triggered (was: a single pass that
            # only added spawns within the player's detect_radius, so a
            # patrol whose second scout sat just outside radius only
            # engaged the closer one — see sol_pirate_patrol_1).
            # NOTE: the alive filter below is position-strict against
            # ``_spawn.pos``. That's fine while enemies don't patrol;
            # once patrol movement is added the alive check should
            # pivot to an entity-id or reference match instead.
            if code == "moved" and current_mode == "space" and player_owned_ship is not None:
                # The two-pass squad-aware scan moved to
                # :func:`_detect_combat_encounter` so the auto-nav
                # animation loop can call the same logic each step.
                # The original Python lives in the helper verbatim.
                _encounter = _detect_combat_encounter(
                    player.pos, game_map, solar_system_module.current_system(),
                )
                if _encounter is not None:
                    _handle_combat_encounter(
                        console, context, player_owned_ship, player,
                        game_map, log, _encounter,
                    )
            if code == "wall":
                if current_mode == "space":
                    # In space the "wall" is a planet (sun is too
                    # far to bump into given our ship speeds and the
                    # 80x54 layout). Open the planet dialog so the
                    # player can Land (Earth) or read the stub
                    # message (other planets).
                    target_x = player.pos.x + dx
                    target_y = player.pos.y + dy
                    if game_map.in_bounds(target_x, target_y):
                        # Multi-system iteration: jump points look
                        # like planets at the bump site (both are
                        # walkable=False cell occupants). We check
                        # for jumps FIRST so a gate-bump gets the
                        # jump menu and not the planet menu. The
                        # planet check below still fires for actual
                        # planet-bumps on cells that don't overlap a
                        # gate.
                        # Stations paint LAST in make_solar_system so
                        # they visually overlap any underlying planet
                        # or jump-point cell. Resolve station-bumps
                        # FIRST so a station that visually covers a
                        # planet or gate resolves to the station menu.
                        # Stations route their LAND button to their
                        # city_planet_id (see StationSpec); then the
                        # existing planet elif branch handles
                        # _run_planet_menu + LAND outcome + scene-
                        # swap + hangar-dock unchanged.
                        station_id = solar_system_module.station_id_at(
                            target_x, target_y,
                        )
                        if station_id is None:
                            jp = solar_system_module.jump_point_at(
                                target_x, target_y,
                            )
                            pid = solar_system_module.planet_id_at(
                                target_x, target_y,
                            )
                        else:
                            # Station wins - route via planet branch
                            # without bespoke dispatch. The existing
                            # elif pid is not None branch + the
                            # LAND handler run on pid below.
                            station_for_bump = solar_system_module.find_station(station_id)
                            jp = None
                            pid = station_for_bump.city_planet_id
                        if jp is not None and jp.connects_to:
                            # v1: each gate has exactly one
                            # connects_to entry. Multi-hop hubs in
                            # future iterations would render a list
                            # in the jump menu.
                            target_system_id, target_jp_id = jp.connects_to[0]
                            log.add(f"You approach {jp.name}.")
                            outcome = _run_jump_menu(
                                context, jp, target_system_id, log,
                                owned_ship=player_owned_ship,
                            )
                            if outcome is JumpMenuOutcome.JUMP:
                                # Fuel gate: check the ship has enough
                                # fuel BEFORE jumping. If not, log the
                                # refusal and stay in the current system
                                # without consuming any fuel.
                                ship_record_for_fuel = ship_module.find_ship(
                                    player_owned_ship.ship_id,
                                )
                                if player_owned_ship.fuel < ship_module.JUMP_FUEL_COST:
                                    log.add(
                                        f"Not enough fuel! The jump requires "
                                        f"{ship_module.JUMP_FUEL_COST} units; "
                                        f"you have {player_owned_ship.fuel}."
                                    )
                                    continue
                                player_owned_ship.fuel -= ship_module.JUMP_FUEL_COST
                                log.add(
                                    f"Jump drive engaged. Fuel: "
                                    f"{player_owned_ship.fuel} / "
                                    f"{ship_record_for_fuel.max_fuel}."
                                )
                                # Animate the jump drive sequence
                                # before swapping systems. The
                                # animation renders the current
                                # space view with an expanding
                                # explosion at the ship position.
                                _animate_jump(
                                    context, console, game_map,
                                    player, character_info,
                                    stats, log,
                                    active_mission_text=active_mission_text or "",
                                )
                                # ``_jump_to_system`` returns
                                # ``(new_game_map, new_player)`` — the
                                # BUILT space map + the ship entity the
                                # dispatcher should rebind ``player``
                                # to. Mirrors ``_launch_to_space``'s
                                # ``(space_map, space_player)`` shape
                                # so we can rebind both refs in one
                                # line. Critically: ``player`` must be
                                # the ship entity (NOT just have
                                # ``player.pos`` updated) so that
                                # ``try_move(player, ...)`` advances
                                # the visible ship glyph on the map.
                                new_game_map, player = _jump_to_system(
                                    jp=jp,
                                    player_owned_ship=player_owned_ship,
                                    log=log,
                                    target_system_id=target_system_id,
                                    target_jp_id=target_jp_id,
                                )
                                game_map = new_game_map
                                continue
                            # BACK / IGNORE: fall through to the
                            # planet check below. (If neither jp nor
                            # pid matched we just exit the bump
                            # branch — no-op cell.)
                        elif pid is not None:
                            planet_obj = solar_system_module.find_planet(pid)
                            log.add(f"You approach {planet_obj.name}.")
                            outcome = _run_planet_menu(
                                context, planet_obj,
                                character_info=character_info,
                                stats=stats, log=log,
                                active_mission_text=active_mission_text,
                            )
                            if outcome is PlanetMenuOutcome.LAND and pid == current_city_id:
                                # Already standing on this planet's
                                # surface - no scene swap needed. Just
                                # drive the same return-to-city animation
                                # so the ship appears to dock.
                                hangar_ship = _find_hangar_ship(
                                    city_game_map, player_owned_ship,
                                )
                                if hangar_ship is not None:
                                    game_map, player = _return_to_city(
                                        context, console,
                                        hangar_ship,
                                        city_game_map, city_player,
                                        character_info=character_info,
                                        stats=stats, log=log,
                                        active_mission_text=active_mission_text,
                                    )
                                    current_mode = "city"
                            elif outcome is PlanetMenuOutcome.LAND:
                                # LAND on a DIFFERENT planet - swap
                                # the city game_map, animate the
                                # ship INTO the new planet's hangar,
                                # and reattach the @ so the player
                                # is visible on the new surface.
                                # Symmetric to the Earth launch flow:
                                # the @ is spliced out before any
                                # animation and spliced back once the
                                # ship has docked on the new planet.
                                from .data.planets import (
                                    load_planet as planets_load_planet,
                                    hangar_anchor as planet_hangar_anchor,
                                    has_landable_port as planets_has_landable_port,
                                )
                                # Defensive: ``update_planet_menu``
                                # routes ENTER -> BACK for no-port
                                # planets so this branch is reached
                                # only for landable bodies today, but
                                # a future code path (mod menu,
                                # tutorial skip) could emit LAND
                                # against an unlanded planet. The
                                # helper catches the KeyError so we
                                # log + skip instead of crashing on
                                # an unknown planet id.
                                if not planets_has_landable_port(pid):
                                    log.add(
                                        f"You see no port on {planet_obj.name}."
                                    )
                                    continue
                                if city_player in city_game_map.entities:
                                    city_game_map.entities.remove(city_player)
                                new_city_map = planets_load_planet(pid)
                                new_anchor = planet_hangar_anchor(pid)
                                hangar_ship = _find_hangar_ship(
                                    city_game_map, player_owned_ship,
                                )
                                if hangar_ship is not None:
                                    # Splice the ship OUT of the OLD
                                    # planet's entities list and INTO
                                    # the NEW planet's entities at the
                                    # offscreen position BEFORE the
                                    # descent animation runs. The
                                    # _animate_ship_to_y loop renders
                                    # new_city_map each frame, so the
                                    # ship must be a member of
                                    # new_city_map.entities for the
                                    # descent path to actually paint
                                    # visibly. If the splice happens
                                    # only AFTER the animation returns
                                    # the player sees an instant scene
                                    # swap with no descent animation.
                                    # Defensive splice-OUT: the OLD
                                    # map is orphaned two lines below
                                    # by ``city_game_map = new_city_map``
                                    # so the strip has no visual effect,
                                    # but preserves the read-time
                                    # invariant that the player's owned
                                    # ship lives on whichever
                                    # city_game_map is currently active.
                                    if hangar_ship in city_game_map.entities:
                                        city_game_map.entities.remove(
                                            hangar_ship,
                                        )
                                    hangar_ship.pos = world.Position(
                                        new_anchor.x,
                                        -(solar_system_module.SOL_VIEW_H // 2) - 1,
                                    )
                                    new_city_map.entities.append(
                                        hangar_ship,
                                    )
                                    _animate_ship_to_y(
                                        context, console,
                                        hangar_ship, new_city_map,
                                        character_info=character_info,
                                        stats=stats, log=log,
                                        active_mission_text=active_mission_text,
                                        target_y=new_anchor.y,
                                    )
                                    log.add(
                                        f"You touch down on {planet_obj.name}."
                                    )
                                    if city_player not in new_city_map.entities:
                                        new_city_map.entities.append(city_player)
                                    # Step the @ off the docked ship at
                                    # the new planet's hangar area, one
                                    # cell south of the ship's anchor
                                    # (matches Earth's "outside the
                                    # spaceport, below the door" landing
                                    # convention). Previously the player
                                    # was reset to the map centroid
                                    # which felt like a teleport-spawn
                                    # rather than stepping off a docked
                                    # ship.
                                    city_player.pos = world.Position(
                                        new_anchor.x,
                                        new_anchor.y + 1,
                                    )
                                    city_game_map = new_city_map
                                    game_map = new_city_map
                                    player = city_player
                                    current_city_id = pid
                                    current_mode = "city"
                            # BACK / QUIT fall through to next event.
                            continue
                log.add("A wall blocks your path.")
            elif code == "occupied":
                if blocker.ship_id:
                    ship = ship_module.find_ship(blocker.ship_id)
                    if blocker.owned:
                        # Player's hangar ship - open the menu.
                        result = _run_ship_menu(
                            context, ship, player_owned_ship, stats, log,
                        )
                        # Sell / Launch are stubs this iteration and
                        # return the same enum value the caller
                        # maps to "back to city". View loops inside
                        # _run_ship_menu and never returns.
                        if result is ShipMenuAction.QUIT:
                            return
                        if (
                            result is ShipMenuAction.LAUNCH
                            and player_owned_ship is not None
                        ):
                            # Drive the launch animation and swap
                            # the active scene to the Sol system.
                            # The hangar ship entity is what we
                            # animate up off-screen; it stays in
                            # ``city_game_map.entities`` so a future
                            # ESC-in-space return can walk the SAME
                            # entity back down.
                            hangar_ship = next(
                                (e for e in city_game_map.entities
                                 if e.owned
                                 and e.ship_id == player_owned_ship.ship_id),
                                None,
                            )
                            if hangar_ship is not None:
                                space_game_map, space_player_entity = (
                                    _launch_to_space(
                                        context, console,
                                        city_game_map, hangar_ship, ship,
                                        current_city_id=current_city_id,
                                        city_player=city_player,
                                        character_info=character_info,
                                        stats=stats, log=log,
                                        active_mission_text=active_mission_text,
                                    )
                                )
                                game_map = space_game_map
                                player = space_player_entity
                                current_mode = "space"
                            continue
                        # VIEW/SELL/BACK return to the city
                        # (the message log already shows what
                        # happened for SELL).
                    elif player_owned_ship is not None:
                        # Player already owns a ship - don't open the
                        # buy modal; the catalog is essentially sold
                        # out. Bumping the showroom ship logs a
                        # single line so the player can move on.
                        log.add(
                            "You already have a ship docked in your hangar."
                        )
                    else:
                        # Showroom ship - open the buy modal.
                        result = _run_ship_buy(
                            context, blocker, ship, stats, game_map, log,
                        )
                        if result is ShipBuyOutcome.QUIT:
                            return
                        if result is ShipBuyOutcome.BUY:
                            stats.gold -= ship.price
                            # Repurpose the showroom entity into the
                            # player's hangar ship instead of
                            # allocating a fresh one - keeps the
                            # ship_id + catalog char/fg link
                            # automatically and matches the user's
                            # mental model of ``the ship on the
                            # tarmac is now theirs``.
                            blocker.pos = world.HANGAR_ANCHOR
                            blocker.owned = True
                            blocker.name = f"Your Ship: {ship.name}"
                            player_owned_ship = ship_module.OwnedShip(
                                ship_id=ship.id,
                                weapons=(
                                    "light_laser",
                                    "heavy_laser",
                                    "plasma_cannon",
                                    "light_missile",
                                    "heavy_missile",
                                    "emp_missile",
                                ),
                                modules=("compact_reactor",),
                                fuel=ship.max_fuel,
                                # cargo_used is intentionally NOT
                                # passed here: OwnedShip.__post_init__
                                # derives it from self.weapons so the
                                # cargo HUD and the actual ammo count
                                # can never drift. Passing cargo_used
                                # would raise TypeError now that the
                                # field is init=False.
                            )
                            log.add(
                                f"You bought the {ship.name} for "
                                f"{ship.price}g and parked it in "
                                "your hangar."
                            )
                        elif result is ShipBuyOutcome.TOO_EXPENSIVE:
                            short = ship.price - stats.gold
                            log.add(
                                f"You cannot afford the {ship.name} "
                                f"({short}g short)."
                            )
                        # BACK: silent.
                elif blocker.npc_id:
                    npc_obj = npc_module.find_npc(blocker.npc_id)
                    # The npc_talk dialog gains a "Deliver <title>"
                    # option whenever the player's active mission
                    # is one that actually moves goods (i.e. has a
                    # non-zero ``required_cargo_size``). The current
                    # roster has exactly one such mission —
                    # merchants_supply_run_alpha_centauri — whose
                    # delivery target is the Research Officer at
                    # ac_station. The cargo-cap check on accept is
                    # done inside :func:`mission.try_accept_mission`;
                    # the DELIVER path uses
                    # :func:`mission.complete_mission` to drop the
                    # cargo + grant gold in one place.
                    deliver_mission: mission_module.Mission | None = None
                    if player_active_mission is not None:
                        active_mission_obj = mission_module.find_mission(
                            player_active_mission.mission_id,
                        )
                        # Use is_deliverable_at (NOT just
                        # required_cargo_size > 0) so the Deliver
                        # option only appears at the EXACT NPC on
                        # the EXACT planet this mission targets.
                        # Wrong-planet delivery would silently fire
                        # complete_mission and the player would
                        # lose the cargo without being on the
                        # station they were sent to.
                        if mission_module.is_deliverable_at(
                            active_mission_obj,
                            npc_obj.id,
                            current_city_id,
                        ):
                            deliver_mission = active_mission_obj
                    result, deliver_in_progress = _run_npc_talk(
                        context, npc_obj, log,
                        deliver_mission=deliver_mission,
                    )
                    if result is TalkOutcome.QUIT:
                        return
                    if result is TalkOutcome.DELIVER:
                        if deliver_in_progress is not None:
                            mission_module.complete_mission(
                                deliver_in_progress,
                                player_owned_ship, stats, log,
                            )
                        # DELIVER is terminal here: the active
                        # mission slot must clear AFTER the complete
                        # call so the completion log line lands in
                        # the message log before the HUD re-renders
                        # without an active mission on the next
                        # loop iteration.
                        player_active_mission = None
                    if result is TalkOutcome.WORK:
                        # Single-mission-slot UX: the player must
                        # abandon before they can pick up a new
                        # contract. The dispatcher surfaces a single
                        # hint so they know the path is Q (quest
                        # log) instead of leaving them stuck.
                        if player_active_mission is not None:
                            current = mission_module.find_mission(
                                player_active_mission.mission_id,
                            )
                            giver = npc_module.find_npc(current.giver_npc_id)
                            log.add(
                                f"You already have work from {giver.name}. "
                                "Press Q to view or abandon it."
                            )
                        else:
                            offerings = mission_module.missions_offered_by(
                                npc_obj.id,
                            )
                            if not offerings:
                                log.add(
                                    f"{npc_obj.name} has no work for you "
                                    "right now."
                                )
                            else:
                                outcome, picked = _run_mission_offerings(
                                    context, npc_obj, offerings, log,
                                )
                                if (
                                    outcome is MissionOutcome.ACCEPT
                                    and picked is not None
                                ):
                                    # Cargo-cap check lives in
                                    # mission.try_accept_mission so the
                                    # dispatcher stays focused on
                                    # state transitions. On success
                                    # the helper logs the accept line
                                    # + cargo update; on failure it
                                    # logs the refusal reason and the
                                    # dispatcher leaves
                                    # ``player_active_mission``
                                    # untouched (single-slot UX).
                                    if mission_module.try_accept_mission(
                                        picked, player_owned_ship, log,
                                    ):
                                        player_active_mission = (
                                            mission_module.ActiveMission(
                                                mission_id=picked.id,
                                            )
                                        )
                    # BACK: silent.
                else:
                    log.add(f"You bump into {blocker.name}.")


# ---------------------------------------------------------------------------
# Top-level flow
# ---------------------------------------------------------------------------


def run(context: tcod.context.Context) -> None:
    """Drive the 3 creation screens, then drop into the city game."""
    # Seed the shared game RNG so combat outcomes are reproducible.
    # A future iteration will let the player supply this seed.
    import os
    import struct
    _seed = struct.unpack("I", os.urandom(4))[0]
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


if __name__ == "__main__":
    main()
