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


def _pygame_readonly_enabled() -> bool:
    """Return whether the batched read-only Pygame screens are enabled."""
    from .. import pygame_batch

    return pygame_batch.enabled()


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





def _render_loadout_weapons(console, owned, ship_spec, cy: int) -> int:
    """Render installed weapons and return the next row."""
    from ..data.weapons import find_weapon as _find_weapon

    count = len(owned.weapons)
    ui.paint_text(console, 2, cy, f"WEAPONS  ({count}/{ship_spec.weapon_slots} slots)", fg=ui.COLOR_TITLE)
    cy += 1
    if not count:
        ui.paint_text(console, 4, cy, "(none installed)", fg=ui.COLOR_VALUE_DIM)
        return cy + 2
    for weapon_id in owned.weapons:
        try:
            weapon = _find_weapon(weapon_id)
            line = f"  {weapon.name:<20} dmg:{weapon.damage:>2}  acc:{weapon.accuracy:>2}%  range:{weapon.min_range}-{weapon.max_range}"
        except KeyError:
            line = f"  {weapon_id} (unknown)"
        ui.paint_text(console, 4, cy, line, fg=ui.COLOR_OPTION)
        cy += 1
    return cy + 1


def _render_loadout_modules(console, owned, ship_spec, cy: int) -> int:
    """Render installed modules and return the next row."""
    from ..data.modules import find_module as _find_module

    count = len(owned.modules)
    ui.paint_text(console, 2, cy, f"MODULES  ({count}/{ship_spec.module_slots} slots)", fg=ui.COLOR_TITLE)
    cy += 1
    if not count:
        ui.paint_text(console, 4, cy, "(none installed)", fg=ui.COLOR_VALUE_DIM)
        return cy + 3
    for module_id in owned.modules:
        try:
            module = _find_module(module_id)
            ui.paint_text(console, 4, cy, module.name, fg=ui.COLOR_OPTION)
            ui.paint_text(console, 6, cy + 1, module.description, fg=ui.COLOR_VALUE_DIM)
            cy += 2
        except KeyError:
            ui.paint_text(console, 4, cy, f"{module_id} (unknown)", fg=ui.COLOR_VALUE_DIM)
            cy += 1
    return cy + 2


def render_loadout_view(console, ctx) -> None:
    """Render the read-only loadout view into a supplied console."""
    owned = ctx.player_owned_ship
    if owned is None:
        return
    ship_spec = ship_module.find_ship(owned.ship_id)
    eff_cargo = ship_module.effective_max_cargo(ship_spec, owned)
    console.clear()
    title = f"LOADOUT -- {ship_module.ship_display_name(owned).upper()}"
    cy = ui.screen_header(console, SCREEN_WIDTH, title)
    header = (
        f"Fuel: {owned.fuel}/{ship_spec.max_fuel}  |  "
        f"Hull: {owned.hull_damage_pct}%  |  Cargo: {owned.cargo_used}/{eff_cargo}  |  "
        f"Shields: {_effective_shields(ship_spec, owned)}  |  "
        f"Power: {_effective_power_gen(ship_spec, owned)}  |  "
        f"Speed: {ship_module.effective_speed(ship_spec, owned)}"
    )
    ui.paint_text(console, 2, cy, header, fg=ui.COLOR_VALUE_DIM)
    cy += 2
    ui.paint_rule(console, 2, cy, ui.rule_width(SCREEN_WIDTH))
    cy = _render_loadout_weapons(console, owned, ship_spec, cy + 1)
    cy = _render_loadout_modules(console, owned, ship_spec, cy)
    ui.paint_text(console, 2, cy, "Press ESC to go back.", fg=ui.COLOR_INSTRUCTION)
    message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)


def _run_loadout_view(ctx) -> None:
    """Show the read-only loadout view through the existing tcod modal."""
    if ctx.player_owned_ship is None:
        return
    if _pygame_readonly_enabled():
        from .. import pygame_batch
        try:
            outcome = pygame_batch.run_readonly(lambda console: render_loadout_view(console, ctx))
        except pygame_batch.PygameBatchUnavailable:
            outcome = None
        if outcome is not None:
            if outcome == "GUIDE":
                from ..help import _run_help_guide
                _run_help_guide(ctx)
            return
    console = make_console()

    def _render() -> None:
        render_loadout_view(console, ctx)

    def _update(event: tcod.event.Event) -> ShipMenuAction | None:
        if _try_open_guide(event, ctx):
            return ShipMenuAction.IGNORE
        if isinstance(event, tcod.event.Quit):
            return None
        if isinstance(event, tcod.event.KeyDown) and event.sym in ui._ESCAPE_SYMS:
            return None
        return ShipMenuAction.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


def render_faction_view(console, ctx) -> None:
    """Render faction standings into a supplied console."""
    from ..faction import get_attitude, _ALL_FACTIONS

    zone_colors: dict[str, tuple[int, int, int]] = {
        "enemy": (255, 80, 80), "disliked": (255, 165, 60),
        "neutral": (180, 180, 180), "liked": (100, 200, 255),
        "allied": (100, 255, 130),
    }
    console.clear()
    start_y = ui.screen_header(console, SCREEN_WIDTH, "FACTION STANDINGS")
    for index, faction_id in enumerate(_ALL_FACTIONS):
        reputation = ctx.faction_reputation.get(faction_id, 0)
        attitude = get_attitude(reputation)
        bar = _faction_progress_bar(reputation)
        console.print(
            x=2, y=start_y + index * 3,
            string=f"{faction_id.title().ljust(10)} {reputation:+d}  {bar}  {attitude.title()}",
            fg=zone_colors.get(attitude, (180, 180, 180)),
        )
    console.print(
        x=2, y=start_y + len(_ALL_FACTIONS) * 3 + 2,
        string="ENTER / ESC - back", fg=ui.COLOR_INSTRUCTION,
    )
    message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)


def _faction_progress_bar(rep: int, width: int = 31) -> str:
    """Return the CP437-safe centered faction reputation bar."""
    half = width // 2
    neg_fill = int((abs(rep) / 100) * half) if rep < 0 else 0
    pos_fill = int((rep / 100) * half) if rep >= 0 else 0
    neg_fill = max(0, min(half, neg_fill))
    pos_fill = max(0, min(half, pos_fill))
    left = ["#" if neg_fill >= half - index else "-" for index in range(half)]
    right = ["#" if pos_fill >= index + 1 else "-" for index in range(half)]
    return "".join(left + ["|"] + right)


def _run_faction_view(ctx) -> None:
    """Show faction standings with the existing tcod modal."""
    if _pygame_readonly_enabled():
        from .. import pygame_batch
        try:
            outcome = pygame_batch.run_readonly(lambda console: render_faction_view(console, ctx))
        except pygame_batch.PygameBatchUnavailable:
            outcome = None
        if outcome is not None:
            if outcome == "GUIDE":
                from ..help import _run_help_guide
                _run_help_guide(ctx)
            return
    console = make_console()

    def _render() -> None:
        render_faction_view(console, ctx)

    def _update(event: tcod.event.Event) -> ShipMenuAction | None:
        if _try_open_guide(event, ctx):
            return ShipMenuAction.IGNORE
        if isinstance(event, tcod.event.Quit):
            return None
        if isinstance(event, tcod.event.KeyDown) and (
            event.sym in ui._ESCAPE_SYMS or event.sym in ui._ENTER_SYMS
        ):
            return None
        return ShipMenuAction.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


def _pygame_ship_menu_enabled() -> bool:
    """Return whether the interactive Pygame menu batch is enabled."""
    from .. import pygame_menu

    return pygame_menu.enabled()


def _ship_menu_frames(ctx, ship: ship_module.Ship):
    """Build presentation-only frames for the Pygame ship hub."""
    from .. import pygame_menu

    owned = ctx.player_owned_ship
    if owned is None:
        _body = ship.description
    else:
        _speed = ship_module.effective_speed(ship, owned)
        _body = "\n".join((
            ship.description,
            f"Fuel: {owned.fuel} / {ship.max_fuel}",
            f"Hull: {owned.hull_damage_pct}% damage",
            f"Speed: {_speed}",
            f"Credits: {ctx.stats.credits}$",
        ))
    _items = tuple(
        pygame_menu.MenuItem(label, "", action)
        for label, action in zip(
            SHIP_MENU_OPTIONS,
            ("VIEW", "LOADOUT", "LAUNCH"),
        )
    )
    return tuple(
        pygame_menu.MenuFrame(
            title=f"Your {ship_module.ship_display_name(owned).upper()}",
            body=_body,
            items=_items,
            hints=("ARROW KEYS / j,k navigate - ENTER select - ESC back",),
            selected=index,
        )
        for index in range(len(_items))
    )


def _run_pygame_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction | None:
    """Run one Pygame ship-hub interaction, or return ``None`` for fallback."""
    from .. import pygame_menu

    while True:
        try:
            outcome, action, _selected = pygame_menu.run(
                _ship_menu_frames(ctx, ship),
                caption="spacehack - ship hangar",
            )
        except pygame_menu.PygameMenuUnavailable:
            return None
        if outcome == "GUIDE":
            from ..help import _run_help_guide
            _run_help_guide(ctx)
            continue
        if outcome == "SELECT":
            _actions = {
                "VIEW": ShipMenuAction.VIEW,
                "LOADOUT": ShipMenuAction.LOADOUT,
                "LAUNCH": ShipMenuAction.LAUNCH,
            }
            return _actions.get(action, ShipMenuAction.BACK)
        if outcome == "QUIT":
            return ShipMenuAction.QUIT
        return ShipMenuAction.BACK


def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the hub-menu modal for ``ship``; return the chosen action.

    The menu has 3 options (View Cargo, View Loadout, Launch);
    the highlighted option (initially 0 = View Cargo) is mutated by
    UP / DOWN arrows AND vim ``j`` / ``k`` via
    :func:`_ship_menu_navigate`.
    """
    if _pygame_ship_menu_enabled():
        while True:
            _pygame_action = _run_pygame_ship_menu(ctx, ship)
            if _pygame_action is None:
                break
            if _pygame_action is ShipMenuAction.VIEW:
                from ..trade import open_cargo as _open_cargo
                _open_cargo(ctx)
                continue
            if _pygame_action is ShipMenuAction.LOADOUT:
                _run_loadout_view(ctx)
                continue
            return _pygame_action

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
