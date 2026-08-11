"""Ship hangar — tabbed modal runner.

One ``pygame_screen`` modal with SHIP / CARGO / LOADOUT tabs for the
player's owned ship while in city mode (the C-screen pattern): TAB
cycles tabs, ENTER launches on the SHIP tab or jettisons a selected
good on the CARGO tab, ESC walks away. Also exports ``_find_hangar_ship``
used by the landing animation code in ``__main__.py``.

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

_HANGAR_TABS: tuple[str, ...] = ("SHIP", "CARGO", "LOADOUT")
"""The single source of truth for the hangar tab names and count."""


def _pygame_readonly_enabled() -> bool:
    """Return whether read-only Pygame screens can render in this runtime."""
    from .. import pygame_screen

    return pygame_screen.enabled()


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


def _loadout_body(ctx, owned, ship_spec) -> tuple[str, ...]:
    """Build the read-only loadout summary lines (the LOADOUT tab body)."""
    return (
        f"Fuel: {owned.fuel}/{ship_spec.max_fuel}",
        f"Hull damage: {owned.hull_damage_pct}%",
        f"Cargo: {owned.cargo_used}/{ship_module.effective_max_cargo(ship_spec, owned)}",
        f"Shields: {_effective_shields(ship_spec, owned)}    "
        f"Power: {_effective_power_gen(ship_spec, owned)}    "
        f"Speed: {ship_module.effective_speed(ship_spec, owned)}",
    )


def _weapon_row(index: int, weapon_id: str):
    """Build one filled weapon-slot row (``Weapon N: <name>``)."""
    from .. import pygame_screen
    from ..data.weapons import find_weapon

    try:
        weapon = find_weapon(weapon_id)
        detail = (
            f"Damage {weapon.damage}   Accuracy {weapon.accuracy}%   "
            f"Range {weapon.min_range}-{weapon.max_range}   "
            f"AP {weapon.ap_cost}   Power {weapon.power_cost}"
        )
        if weapon.slot_type == "missile":
            detail += f"   Ammo {weapon.ammo_capacity}"
        return pygame_screen.ScreenRow(
            f"Weapon {index + 1}: {weapon.name}", detail, selectable=True,
        )
    except KeyError:
        return pygame_screen.ScreenRow(
            f"Weapon {index + 1}: {weapon_id}",
            "Unknown weapon specification", selectable=True,
        )


def _module_row(index: int, module_id: str):
    """Build one filled module-slot row (``Module N: <name>``)."""
    from .. import pygame_screen
    from ..data.modules import find_module

    try:
        module = find_module(module_id)
        return pygame_screen.ScreenRow(
            f"Module {index + 1}: {module.name}",
            module.description, selectable=True,
        )
    except KeyError:
        return pygame_screen.ScreenRow(
            f"Module {index + 1}: {module_id}",
            "Unknown module specification", selectable=True,
        )


def _slot_rows(prefix: str, slot_count: int, installed, make_row) -> tuple:
    """Render every slot in one section: filled slots via ``make_row``,
    empty ones as non-selectable ``[empty slot]`` markers."""
    from .. import pygame_screen

    rows = []
    for index in range(max(slot_count, len(installed))):
        if index < len(installed):
            rows.append(make_row(index, installed[index]))
        else:
            rows.append(pygame_screen.ScreenRow(
                f"{prefix} {index + 1}: [empty slot]",
                f"No {prefix.lower()} installed.", selectable=False,
            ))
    return tuple(rows)


def _loadout_rows(owned, ship_spec):
    """Build the read-only slot rows for the LOADOUT tab.

    Every weapon and module slot is rendered; installed gear fills its
    slot, empty slots read ``[empty slot]`` (non-selectable).
    """
    from .. import pygame_screen

    rows: list = [
        pygame_screen.ScreenRow(
            f"WEAPONS ({len(owned.weapons)}/{ship_spec.weapon_slots} slots)",
            selectable=False,
        ),
    ]
    rows.extend(_slot_rows("Weapon", ship_spec.weapon_slots, owned.weapons, _weapon_row))
    rows.append(pygame_screen.ScreenRow(
        f"MODULES ({len(owned.modules)}/{ship_spec.module_slots} slots)",
        selectable=False,
    ))
    rows.extend(_slot_rows("Module", ship_spec.module_slots, owned.modules, _module_row))
    return tuple(rows)


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
    """Show faction standings with the refreshed Pygame presentation."""
    from .. import pygame_faction

    while True:
        outcome = pygame_faction.run_for_context(ctx.context, ctx)
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            _open_context_guide(ctx, "NPCs & Factions")
            continue
        return


def _pygame_ship_menu_enabled() -> bool:
    """Return whether the tabbed hangar can render in this runtime."""
    from .. import pygame_screen

    return pygame_screen.enabled()


def _launch_row():
    """Build the Launch row that lives at the bottom of the SHIP tab."""
    from .. import pygame_screen

    return pygame_screen.ScreenRow(
        "Launch", "Leave the hangar and enter space.", "LAUNCH",
    )


def _ship_hangar_frame(ctx, ship: ship_module.Ship, tab: int, selected: int):
    """Build one tabbed hangar snapshot (SHIP / CARGO / LOADOUT tabs).

    SHIP shows the at-a-glance stats with the Launch action separated by
    one blank line (EXPERIMENT, decision #6 revision — visible white
    space, not a ton; the blank-line count is a one-line tweak). CARGO
    reuses the shared cargo rows (jettison actions preserved); LOADOUT
    reuses the read-only loadout rows. Launch lives only on the SHIP tab.
    """
    from .. import pygame_screen, pygame_ui
    from ..trade import _cargo_body, _cargo_rows

    owned = ctx.player_owned_ship
    if owned is None:
        return pygame_screen.ScreenFrame(
            "YOUR SHIP", ("No ship equipped.",), (),
            (pygame_ui.modal_hint("ESC back", pygame_ui.GUIDE_HINT),),
        )
    title = f"YOUR {ship_module.ship_display_name(owned).upper()}"
    max_cargo = ship_module.effective_max_cargo(ship, owned)
    if tab == 0:
        body = (
            ship.description,
            "",
            f"Fuel: {owned.fuel} / {ship.max_fuel}",
            f"Hull: {owned.hull_damage_pct}% damage",
            f"Speed: {ship_module.effective_speed(ship, owned)}",
            f"Shields: {_effective_shields(ship, owned)}",
            f"Power: {_effective_power_gen(ship, owned)}",
            f"Cargo: {owned.cargo_used} / {max_cargo}",
            pygame_ui.credits_label(ctx.stats.credits),
            "",
        )
        rows = (_launch_row(),)
        footer = (pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER launch", "TAB cargo",
            "ESC back", pygame_ui.GUIDE_HINT,
        ),)
    elif tab == 1:
        rows = _cargo_rows(owned)
        body = _cargo_body(owned, max_cargo)
        footer = (pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER jettison", "TAB loadout",
            "ESC back", pygame_ui.GUIDE_HINT,
        ),)
    else:
        rows = _loadout_rows(owned, ship)
        body = _loadout_body(ctx, owned, ship)
        footer = (pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "TAB ship", "ESC back", pygame_ui.GUIDE_HINT,
        ),)
    return pygame_screen.ScreenFrame(
        title, body, rows, footer, selected,
        tabs=_HANGAR_TABS, active_tab=tab,
    )


def _run_pygame_ship_hangar(ctx, ship: ship_module.Ship) -> ShipMenuAction | None:
    """Run the tabbed hangar through the shared Pygame screen.

    TAB cycles SHIP → CARGO → LOADOUT → SHIP; ENTER launches from the
    SHIP tab or jettisons a selected good on the CARGO tab; ``?`` reopens
    the guide; ESC walks away.
    """
    from .. import pygame_screen

    tab = 0
    selected = 0
    while True:
        outcome, action, selected = pygame_screen.run_for_context(
            getattr(ctx, "context", ctx),
            _ship_hangar_frame(ctx, ship, tab, selected),
            caption="spacehack - ship hangar",
        )
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            _open_context_guide(ctx, "Ships & Equipment")
            continue
        if outcome == "TAB":
            tab = (tab + 1) % len(_HANGAR_TABS)
            selected = 0
            continue
        if outcome in {"PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "QUIT":
            return ShipMenuAction.QUIT
        if outcome == "SELECT":
            if action == "LAUNCH":
                return ShipMenuAction.LAUNCH
            if tab == 1:
                from ..trade import _apply_jettison
                owned = ctx.player_owned_ship
                if owned is not None and _apply_jettison(ctx, owned, action):
                    continue
            return None
        return ShipMenuAction.BACK


def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the tabbed hangar modal for ``ship``; return the chosen action.

    One tabbed screen (SHIP / CARGO / LOADOUT, the C-screen pattern): no
    nested sub-modals. TAB cycles tabs, ENTER launches on the SHIP tab
    or jettisons on the CARGO tab, ESC walks away.
    """
    return _run_pygame_ship_hangar(ctx, ship)


def _find_hangar_ship(city_game_map: world.GameMap, player_owned_ship: ship_module.OwnedShip | None) -> world.Entity | None:
    """Return the player's owned hangar ship entity in ``city_game_map``."""
    if player_owned_ship is None:
        return None
    return next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
