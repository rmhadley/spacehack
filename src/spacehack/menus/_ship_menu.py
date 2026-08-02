"""Ship hangar menu — render, update, and modal runner.

Provides the ``View Cargo`` / ``View Loadout`` / ``Launch`` options
for the player's owned ship while in city mode. Also exports
``_find_hangar_ship`` used by the landing animation code in
``__main__.py``.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import world
from .. import ship as ship_module
from .. import message_log
from ..game_context import GameContext
from ..engine import MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


class ShipMenuAction(Enum):
    """Which sub-modal of the hangar menu the player triggers."""
    IGNORE = auto()
    VIEW = auto()
    LOADOUT = auto()
    REFUEL = auto()
    SELL = auto()
    LAUNCH = auto()
    BACK = auto()
    QUIT = auto()


SHIP_MENU_OPTIONS: tuple[str, ...] = ('View Cargo', 'View Loadout', 'Launch')


def render_ship_menu(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, selected: int = 0, *, screen_width: int, screen_height: int) -> None:
    """Paint the hangar ship menu via :func:`ui.render_selectable_list`.

    Clears first so the modal fully replaces the city view; the
    caller re-paints city + HUD + msg log once the modal exits.
    Ship stats (description, fuel, hull, credits) are rendered
    directly above the list.
    """
    console.clear()
    _disp = ship_module.ship_display_name(ctx.player_owned_ship)
    title = f'Your {_disp.upper()}'
    _stat_y = ui.screen_header(console, screen_width, title)
    _stat_col = 2
    if ctx.player_owned_ship is not None:
        _eff_spd = ship_module.effective_speed(ship, ctx.player_owned_ship)
        _lines = [
            ship.description,
            f'Fuel: {ctx.player_owned_ship.fuel} / {ship.max_fuel}',
            f'Hull: {ctx.player_owned_ship.hull_damage_pct}% damage',
            f'Speed: {_eff_spd}',
            f'Credits: {ctx.stats.credits}$',
        ]
        for i, _line in enumerate(_lines):
            console.print(x=_stat_col, y=_stat_y + i, string=_line, fg=ui.COLOR_VALUE_WHITE)
    else:
        console.print(x=_stat_col, y=_stat_y, string=ship.description, fg=ui.COLOR_DESCRIPTION)
    _stats_height = 6 if ctx.player_owned_ship is not None else 1
    _list_title_y = _stat_y + _stats_height + 1
    _opt_items = [(opt, "") for opt in SHIP_MENU_OPTIONS]
    ui.render_selectable_list(
        console, screen_width, screen_height,
        title="",
        items=_opt_items,
        selected=selected,
        col_x=2,
        title_y=_list_title_y,
        title_fg=ui.COLOR_TITLE,
        row_spacing=2,
        item_fg_selected=ui.COLOR_OPTION_HIGHLIGHT,
        item_fg_normal=ui.COLOR_OPTION,
        hint='UP/DOWN / j,k navigate - ENTER select - ESC walk away',
    )
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def _ship_menu_navigate(event: tcod.event.Event, selected: int, n: int = 3) -> int | None:
    """If ``event`` drives hangar-menu nav, return the new
    ``selected`` index (modulo ``n`` options).

    Recognises both arrow keys and vim ``j`` / ``k``.
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


def update_ship_menu(event: tcod.event.Event, selected: int) -> ShipMenuAction:
    """Map a single event for the hangar menu.

    ESC -> BACK, Enter -> action (index 0=Cargo, 1=Loadout, 2=Launch),
    Quit -> QUIT.
    """
    if isinstance(event, tcod.event.Quit):
        return ShipMenuAction.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return ShipMenuAction.IGNORE
    sym = event.sym
    if sym in ui._ESCAPE_SYMS:
        return ShipMenuAction.BACK
    if sym in ui._ENTER_SYMS:
        if selected == 0:
            return ShipMenuAction.VIEW
        elif selected == 1:
            return ShipMenuAction.LOADOUT
        else:
            return ShipMenuAction.LAUNCH
    return ShipMenuAction.IGNORE


# ---------------------------------------------------------------------------
# Effective-stat helpers (sums base + module bonuses)
# ---------------------------------------------------------------------------


def _effective_shields(ship_spec, owned) -> int:
    """Sum base shield max + all module max_shield_bonuses."""
    from ..data.modules import find_module as _fm
    total = ship_spec.base_shield_max
    for mid in getattr(owned, 'modules', ()) or ():
        try:
            total += _fm(mid).max_shield_bonus
        except KeyError:
            pass
    return total


def _effective_power_gen(ship_spec, owned) -> int:
    """Sum base power gen + all module power_gen_bonuses."""
    from ..data.modules import find_module as _fm
    total = ship_spec.base_power_gen
    for mid in getattr(owned, 'modules', ()) or ():
        try:
            total += _fm(mid).power_gen_bonus
        except KeyError:
            pass
    return max(0, total)





def _run_loadout_view(ctx) -> None:
    """Show a read-only view of the player's ship loadout.

    All displayed stats reflect module bonuses (shields, power,
    cargo are base + module bonuses).
    """
    owned = ctx.player_owned_ship
    if owned is None:
        return
    ship_spec = ship_module.find_ship(owned.ship_id)
    console = make_console()

    from ..ui import paint_text

    # Pre-compute effective stats with module bonuses.
    eff_shields = _effective_shields(ship_spec, owned)
    eff_power = _effective_power_gen(ship_spec, owned)
    eff_cargo = ship_module.effective_max_cargo(ship_spec, owned)

    def _render() -> None:
        console.clear()
        from ..data.weapons import find_weapon as _fw
        from ..data.modules import find_module as _fm

        # Title + header rule (unified screen header)
        title_text = f"LOADOUT \u2014 {ship_module.ship_display_name(owned).upper()}"
        cy = ui.screen_header(console, SCREEN_WIDTH, title_text)

        # Ship stats header — effective values with module bonuses.
        eff_spd = ship_module.effective_speed(ship_spec, owned)
        header = (
            f"Fuel: {owned.fuel}/{ship_spec.max_fuel}  |  "
            f"Hull: {owned.hull_damage_pct}%  |  "
            f"Cargo: {owned.cargo_used}/{eff_cargo}  |  "
            f"Shields: {eff_shields}  |  "
            f"Power: {eff_power}  |  "
            f"Speed: {eff_spd}"
        )
        paint_text(console, 2, cy, header, fg=ui.COLOR_VALUE_DIM)
        cy += 2

        # Section rule
        ui.paint_rule(console, 2, cy, ui.rule_width(SCREEN_WIDTH))
        cy += 1

        # Weapons section
        wpn_count = len(owned.weapons)
        paint_text(console, 2, cy, f"WEAPONS  ({wpn_count}/{ship_spec.weapon_slots} slots)", fg=ui.COLOR_TITLE)
        cy += 1
        if wpn_count == 0:
            paint_text(console, 4, cy, "(none installed)", fg=ui.COLOR_VALUE_DIM)
            cy += 1
        else:
            for wid in owned.weapons:
                try:
                    ws = _fw(wid)
                    line = f"  {ws.name:<20} dmg:{ws.damage:>2}  acc:{ws.accuracy:>2}%  range:{ws.min_range}-{ws.max_range}"
                except KeyError:
                    line = f"  {wid} (unknown)"
                paint_text(console, 4, cy, line, fg=ui.COLOR_OPTION)
                cy += 1

        cy += 1

        # Modules section
        mod_count = len(owned.modules)
        paint_text(console, 2, cy, f"MODULES  ({mod_count}/{ship_spec.module_slots} slots)", fg=ui.COLOR_TITLE)
        cy += 1
        if mod_count == 0:
            paint_text(console, 4, cy, "(none installed)", fg=ui.COLOR_VALUE_DIM)
            cy += 1
        else:
            for mid in owned.modules:
                try:
                    ms = _fm(mid)
                    paint_text(console, 4, cy, ms.name, fg=ui.COLOR_OPTION)
                    cy += 1
                    paint_text(console, 6, cy, ms.description, fg=ui.COLOR_VALUE_DIM)
                    cy += 1
                except KeyError:
                    paint_text(console, 4, cy, f"{mid} (unknown)", fg=ui.COLOR_VALUE_DIM)
                    cy += 1

        # Hint
        cy += 2
        paint_text(console, 2, cy, "Press ESC to go back.", fg=ui.COLOR_INSTRUCTION)
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event: tcod.event.Event) -> ShipMenuAction | None:
        """Return IGNORE to keep polling, None to close."""
        if _try_open_guide(event, ctx):
            return ShipMenuAction.IGNORE
        if isinstance(event, tcod.event.Quit):
            return None
        if not isinstance(event, tcod.event.KeyDown):
            return ShipMenuAction.IGNORE
        if event.sym in ui._ESCAPE_SYMS:
            return None
        return ShipMenuAction.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


def _run_faction_view(ctx) -> None:
    """Show faction standings with progress bars."""
    from ..faction import get_attitude, _ALL_FACTIONS
    console = make_console()

    _ZONE_COLORS: dict[str, tuple[int, int, int]] = {
        "enemy": (255, 80, 80),       # red
        "disliked": (255, 165, 60),    # orange
        "neutral": (180, 180, 180),    # grey
        "liked": (100, 200, 255),      # blue
        "allied": (100, 255, 130),     # green
    }

    def _progress_bar(rep: int, width: int = 31) -> str:
        """Return a centered bar with | at 0, negative filling left
        with =, positive filling right with =. Unfilled space uses -
        so the layout is visible even if colour is lost."""
        half = width // 2
        if rep < 0:
            neg_fill = int((abs(rep) / 100) * half)
            pos_fill = 0
        else:
            neg_fill = 0
            pos_fill = int((rep / 100) * half)
        neg_fill = max(0, min(half, neg_fill))
        pos_fill = max(0, min(half, pos_fill))
        # Build from leftmost to rightmost character-by-character.
        chars: list[str] = []
        for _i in range(half):
            _pos_from_centre = half - _i
            if neg_fill >= _pos_from_centre:
                chars.append("#")
            else:
                chars.append("-")
        chars.append("|")
        for _i in range(half):
            if pos_fill >= _i + 1:
                chars.append("#")
            else:
                chars.append("-")
        return "".join(chars)

    def _render() -> None:
        console.clear()
        # Title + header rule (unified screen header)
        _start_y = ui.screen_header(console, SCREEN_WIDTH, "FACTION STANDINGS")
        for _i, _faction in enumerate(_ALL_FACTIONS):
            _rep = ctx.faction_reputation.get(_faction, 0)
            _attitude = get_attitude(_rep)
            _bar = _progress_bar(_rep)
            _color = _ZONE_COLORS.get(_attitude, (180, 180, 180))
            _y = _start_y + _i * 3

            # Faction name (left-aligned, fixed width)
            _name = _faction.title().ljust(10)
            # Score (right-aligned, 5 chars for ±NNN)
            _score = f"{_rep:+d}".rjust(5)
            # Progress bar
            _line = f"{_name} {_score}  {_bar}  {_attitude.title()}"
            console.print(
                x=2,
                y=_y,
                string=_line,
                fg=_color,
            )

        # Hint
        _hint_y = _start_y + len(_ALL_FACTIONS) * 3 + 2
        console.print(
            x=2,
            y=_hint_y,
            string="ENTER / ESC — back",
            fg=ui.COLOR_INSTRUCTION,
        )

        message_log.render_message_log(
            console, ctx.log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

    def _update(event: tcod.event.Event) -> ShipMenuAction | None:
        if _try_open_guide(event, ctx):
            return ShipMenuAction.IGNORE
        if isinstance(event, tcod.event.Quit):
            return None
        if not isinstance(event, tcod.event.KeyDown):
            return ShipMenuAction.IGNORE
        if event.sym in ui._ESCAPE_SYMS or event.sym in ui._ENTER_SYMS:
            return None
        return ShipMenuAction.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the hub-menu modal for ``ship``; return the chosen action.

    The menu has 3 options (View Cargo, View Loadout, Launch);
    the highlighted option (initially 0 = View Cargo) is mutated by
    UP / DOWN arrows AND vim ``j`` / ``k`` via
    :func:`_ship_menu_navigate`.
    """
    console = make_console()
    selected = 0
    n = len(SHIP_MENU_OPTIONS)

    def _render() -> None:
        render_ship_menu(console, ctx, ship, selected=selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> ShipMenuAction:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return ShipMenuAction.IGNORE
        new = _ship_menu_navigate(event, selected, n)
        if new is not None:
            selected = new
            return ShipMenuAction.IGNORE
        return update_ship_menu(event, selected)
    while True:
        action = ui.Modal(ctx.context, console).run(_render, _update)
        if action is ShipMenuAction.VIEW:
            from ..trade import open_cargo as _open_cargo
            _open_cargo(ctx)
            continue
        if action is ShipMenuAction.LOADOUT:
            _run_loadout_view(ctx)
            continue
        return action  # LAUNCH, BACK, or QUIT


def _find_hangar_ship(city_game_map: world.GameMap, player_owned_ship: ship_module.OwnedShip | None) -> world.Entity | None:
    """Return the player's owned hangar ship entity in ``city_game_map``."""
    if player_owned_ship is None:
        return None
    return next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
