"""Planet-side menu screens extracted from ``__main__.py``.

Contains the ship-buy dialog, mission-offerings screen, quest log,
ship hangar menu, mechanic terminal, planet-bump dialog, and all
their Outcome enums.
"""

from __future__ import annotations
from enum import Enum, auto
import tcod.console
import tcod.event
from . import ui
from . import world
from . import mission as mission_module
from . import ship as ship_module
from . import hud
from . import message_log
from . import solar_system as solar_system_module
from . import npc as npc_module
from .game_context import GameContext
from .engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .data.classes import find_class
from .input_helpers import _try_open_guide
from .ui import paint_text, format_split_row, render_split_frame


# ---------------------------------------------------------------------------
# Outcome enums
# ---------------------------------------------------------------------------

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


class _MechanicOutcome(Enum):
    """Result of the mechanic-terminal menu."""
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()
    REFUEL = auto()
    REPAIR = auto()
    LOADOUT = auto()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SHIP_MENU_OPTIONS: tuple[str, ...] = ('View Cargo', 'Launch')


# ---------------------------------------------------------------------------
# Ship buy
# ---------------------------------------------------------------------------

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
        if _try_open_guide(event, ctx):
            return ShipBuyOutcome.IGNORE
        return update_ship_buy(event, ship, ctx.stats)
    return ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Mission offerings
# ---------------------------------------------------------------------------

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
        if _try_open_guide(event, ctx):
            return MissionOutcome.IGNORE
        new = _mission_navigate(event, selected, len(offerings))
        if new is not None:
            selected = new
            return MissionOutcome.IGNORE
        return update_mission_offerings(event)
    outcome = ui.Modal(ctx.context, console).run(_render, _update)
    if outcome is MissionOutcome.ACCEPT:
        return (outcome, offerings[selected % len(offerings)])
    return (outcome, None)


# ---------------------------------------------------------------------------
# Quest log
# ---------------------------------------------------------------------------

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
        if _try_open_guide(event, ctx):
            return QuestLogOutcome.IGNORE
        result = update_quest_log(event, confirm_abandon=confirm_abandon)
        if result is QuestLogOutcome.ABANDONED and (not confirm_abandon):
            confirm_abandon = True
            return QuestLogOutcome.IGNORE
        return result
    outcome = ui.Modal(ctx.context, console).run(_render, _update)
    if outcome is QuestLogOutcome.ABANDONED:
        return (outcome, None)
    return (outcome, ctx.player_active_mission)


# ---------------------------------------------------------------------------
# Ship hangar menu
# ---------------------------------------------------------------------------

def render_ship_menu(console: tcod.console.Console, ctx: GameContext, ship: ship_module.Ship, selected: int=0, *, screen_width: int, screen_height: int) -> None:
    """Paint the 2-option hangar ship menu via :func:`ui.render_selectable_list`.

    Clears first so the modal fully replaces the city view; the
    caller re-paints city + HUD + msg log once the modal exits.
    Ship stats (description, fuel, hull, credits) are rendered
    directly above the list so they don't interfere with option
    selection markers.
    """
    console.clear()
    title = f'Your {ship.name.upper()}'
    title_y = screen_height // 6
    console.print(x=ui.centered_x(title, screen_width), y=title_y, string=title, fg=ui.COLOR_TITLE)
    # Render ship stats directly above the options.
    _stat_y = title_y + 2
    if ctx.player_owned_ship is not None:
        _lines = [
            ship.description,
            f'Fuel: {ctx.player_owned_ship.fuel} / {ship.max_fuel}',
            f'Hull: {ctx.player_owned_ship.hull_damage_pct}% damage',
            f'Credits: {ctx.stats.credits}$',
        ]
        for i, _line in enumerate(_lines):
            console.print(x=ui.centered_x(_line, screen_width), y=_stat_y + i, string=_line, fg=ui.COLOR_VALUE_WHITE)
    else:
        console.print(x=ui.centered_x(ship.description, screen_width), y=_stat_y, string=ship.description, fg=ui.COLOR_DESCRIPTION)
    # Options use render_selectable_list with a specific start_y so they
    # appear below the stats.
    _stats_height = 5 if ctx.player_owned_ship is not None else 1
    _list_title_y = _stat_y + _stats_height + 1
    _opt_items = [(opt, "") for opt in SHIP_MENU_OPTIONS]
    ui.render_selectable_list(
        console, screen_width, screen_height,
        title="",
        items=_opt_items,
        selected=selected,
        col_x=screen_width // 3,
        title_y=_list_title_y,
        title_fg=ui.COLOR_TITLE,
        row_spacing=2,
        item_fg_selected=ui.COLOR_OPTION_HIGHLIGHT,
        item_fg_normal=ui.COLOR_OPTION,
        hint='UP/DOWN / j,k navigate - ENTER select - ESC walk away',
    )
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def _ship_menu_navigate(event: tcod.event.Event, selected: int, n: int = 2) -> int | None:
    """If ``event`` drives hangar-menu nav, return the new
    ``selected`` index (modulo ``n`` options).

    Recognises both the standard arrow keys (UP / DOWN; also KP_8 /
    KP_2 via :data:`ui._UP_SYMS` and :data:`ui._DOWN_SYMS`) and
    the vertical vim keys (``j`` down, ``k`` up). Extracted from
    :func:`_run_ship_menu` so the smoke test can exercise the
    wrap-around behaviour without spinning up a real SDL context.

    Returns ``None`` for any event that does NOT drive nav so the
    caller routes through :func:`update_ship_menu` for Enter / ESC
    / Quit handling.
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
        return ShipMenuAction.VIEW if selected == 0 else ShipMenuAction.LAUNCH
    return ShipMenuAction.IGNORE


def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the hub-menu modal for ``ship``; return the chosen action.

    The menu has 2 options (View Cargo, Launch); the highlighted
    option (initially 0 = View Cargo) is mutated by UP / DOWN arrows
    AND vim ``j`` / ``k`` via :func:`_ship_menu_navigate`, and
    maps to a ShipMenuAction via :func:`update_ship_menu` on
    Enter. ``View`` opens the cargo modal; ``Launch`` exits to
    space mode.
    ESC returns ``BACK``; that's a no-op from the caller's point
    of view (the city is already being repainted by the main loop).
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
            from .trade import open_cargo as _open_cargo
            _open_cargo(ctx)
            continue
        return action  # LAUNCH, BACK, or QUIT


# ---------------------------------------------------------------------------
# Mechanic terminal
# ---------------------------------------------------------------------------

def _run_mech_menu(ctx) -> None:
    """Show the mechanic-terminal menu with Refuel + Repair options.

    Refuel buys fuel cells for the player's ship at the standard rate.
    Repair restores hull integrity at a cost based on damage.
    ESC / QUIT returns silently.
    """
    if ctx.player_owned_ship is None:
        ctx.log.add("You need a ship to use the mechanic terminal.")
        return

    console = make_console()
    selected = 0
    owned = ctx.player_owned_ship
    ship_rec = ship_module.find_ship(owned.ship_id)
    _MECH_OPTIONS = ["Refuel", "Repair", "Manage Loadout"]

    def _render() -> None:
        nonlocal selected
        console.clear()
        title_y = SCREEN_HEIGHT // 6
        console.print(x=ui.centered_x("MECHANIC TERMINAL", SCREEN_WIDTH), y=title_y, string="MECHANIC TERMINAL", fg=ui.COLOR_TITLE)
        # Render ship stats directly above the options.
        stat_y = title_y + 2
        _stat_lines = [
            f"Ship: {ship_rec.name}",
            f"Fuel: {owned.fuel} / {ship_rec.max_fuel}  |  Hull: {owned.hull_damage_pct}% damage",
            f"Credits: {ctx.stats.credits}$",
        ]
        for i, _line in enumerate(_stat_lines):
            console.print(x=ui.centered_x(_line, SCREEN_WIDTH), y=stat_y + i, string=_line, fg=ui.COLOR_VALUE_WHITE)
        # Options below stats.
        _opt_items = [(opt, "") for opt in _MECH_OPTIONS]
        _list_title_y = stat_y + len(_stat_lines) + 1
        ui.render_selectable_list(
            console, SCREEN_WIDTH, SCREEN_HEIGHT,
            title="",
            items=_opt_items,
            selected=selected,
            col_x=SCREEN_WIDTH // 4,
            title_y=_list_title_y,
            row_spacing=2,
            item_fg_selected=ui.COLOR_OPTION_HIGHLIGHT,
            item_fg_normal=ui.COLOR_OPTION,
            hint="UP/DOWN / j,k navigate - ENTER select - ESC back",
        )
        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> _MechanicOutcome:
        nonlocal selected
        if _try_open_guide(event, ctx):
            return _MechanicOutcome.IGNORE
        if isinstance(event, tcod.event.Quit):
            return _MechanicOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _MechanicOutcome.IGNORE
        sym = event.sym
        sym_name: str = getattr(sym, 'name', '').lower()
        if sym in ui._UP_SYMS or sym_name == 'k':
            selected = (selected - 1) % len(_MECH_OPTIONS)
            return _MechanicOutcome.IGNORE
        if sym in ui._DOWN_SYMS or sym_name == 'j':
            selected = (selected + 1) % len(_MECH_OPTIONS)
            return _MechanicOutcome.IGNORE
        if sym in ui._ESCAPE_SYMS:
            return _MechanicOutcome.BACK
        if sym in ui._ENTER_SYMS:
            if selected == 0:
                return _MechanicOutcome.REFUEL
            elif selected == 1:
                return _MechanicOutcome.REPAIR
            else:
                return _MechanicOutcome.LOADOUT
        return _MechanicOutcome.IGNORE

    while True:
        action = ui.Modal(ctx.context, console).run(_render, _update)
        if action is _MechanicOutcome.REFUEL:
            buyable = ship_rec.max_fuel - owned.fuel
            if buyable <= 0:
                ctx.log.add("The fuel tank is already full.")
                continue
            affordable = ctx.stats.credits // ship_module.FUEL_COST_PER_UNIT
            if affordable <= 0:
                ctx.log.add("You don't have enough credits to buy fuel.")
                continue
            units = min(buyable, affordable)
            cost = units * ship_module.FUEL_COST_PER_UNIT
            ctx.stats.credits -= cost
            owned.fuel += units
            ctx.log.add(f"Refueled {units} units for {cost}$. Fuel: {owned.fuel} / {ship_rec.max_fuel}.")
            continue
        if action is _MechanicOutcome.REPAIR:
            dmg_pct = owned.hull_damage_pct
            if dmg_pct <= 0:
                ctx.log.add("No repairs needed -- hull integrity is 100%.")
                continue
            repair_cost = int(dmg_pct * ship_rec.price // 100)
            if ctx.stats.credits < repair_cost:
                ctx.log.add(f"Repair would cost {repair_cost}$, but you only have {ctx.stats.credits}$.")
                continue
            ctx.stats.credits -= repair_cost
            owned.hull_damage_pct = 0
            ctx.log.add(f"Repaired hull to 100% for {repair_cost}$.")
            continue
        if action is _MechanicOutcome.LOADOUT:
            _run_loadout_menu(ctx)
            continue
        return  # BACK or QUIT


# ---------------------------------------------------------------------------
# Loadout management
# ---------------------------------------------------------------------------


class _LoadoutOutcome(Enum):
    """Result of the mechanic loadout menu."""
    IGNORE = auto()
    BACK = auto()
    QUIT = auto()


def _run_loadout_menu(ctx) -> None:
    """Show the loadout management split-screen modal.

    Left panel: weapons for sale, divider, modules for sale.
    Right panel: installed weapon slots (or [empty]), divider,
    installed module slots (or [empty]).
    ENTER on left panel = buy + install.  ENTER on right panel
    = sell installed part for 50% back.
    """
    owned = ctx.player_owned_ship
    if owned is None:
        ctx.log.add("You need a ship to manage its loadout.")
        return

    ship_spec = ship_module.find_ship(owned.ship_id)
    from .data.weapons import find_weapon as _fw, list_weapons as _lw
    from .data.modules import find_module as _fm, list_modules as _lm
    from . import ship as _sm

    # Build left-panel catalog (For Sale).
    _weapons_list = sorted(_lw(), key=lambda w: w.price)
    _modules_list = sorted(_lm(), key=lambda m: m.price)

    # Each left-panel item: (name, label, suffix, fg, item_type, item_id)
    _left_items: list[tuple[str, str, str, tuple, str, str | None]] = []
    _left_items.append(("─── WEAPONS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for w in _weapons_list:
        _left_items.append((w.name, f"{w.price:>4}$", "", ui.COLOR_OPTION, "weapon", w.id))
    _left_items.append(("─── MODULES ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for m in _modules_list:
        _left_items.append((m.name, f"{m.price:>4}$", "", ui.COLOR_OPTION, "module", m.id))

    # Build right-panel items (My Ship slots).
    _weapon_slots = _sm._find_weapon_slots(owned, ship_spec)
    _module_slots = _sm._find_module_slots(owned, ship_spec)

    _right_items: list[tuple[str, str, str, tuple, str, str | None]] = []
    for slot_id, _idx in _weapon_slots:
        if slot_id is not None:
            try:
                _spec = _fw(slot_id)
                _sell = _sm._sell_price("weapon", slot_id)
                _right_items.append((_spec.name, f"(sell {_sell}$)", "", ui.COLOR_OPTION, "weapon_slot", slot_id))
            except KeyError:
                _right_items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", None))
        else:
            _right_items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", None))
    _right_items.append(("─── MODULE SLOTS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
    for slot_id, _idx in _module_slots:
        if slot_id is not None:
            try:
                _spec = _fm(slot_id)
                _sell = _sm._sell_price("module", slot_id)
                _right_items.append((_spec.name, f"(sell {_sell}$)", "", ui.COLOR_OPTION, "module_slot", slot_id))
            except KeyError:
                _right_items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "module_slot", None))
        else:
            _right_items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "module_slot", None))

    # Build the display-only row lists for the split-frame renderer.
    def _build_display_rows(items):
        return [(n, l, s, f) for n, l, s, f, _t, _i in items]

    # Helper: rebuild the right panel from current owned state.
    def _rebuild_right() -> None:
        _right_items.clear()
        _right_items.append(("─── WEAPON SLOTS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        for _sid, _sidx in _sm._find_weapon_slots(owned, ship_spec):
            if _sid is not None:
                try:
                    _sp = _fw(_sid)
                    _sv = _sm._sell_price("weapon", _sid)
                    _right_items.append((_sp.name, f"(sell {_sv}$)", "", ui.COLOR_OPTION, "weapon_slot", _sid))
                except KeyError:
                    _right_items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", None))
            else:
                _right_items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "weapon_slot", None))
        _right_items.append(("─── MODULE SLOTS ───", "", "", ui.COLOR_VALUE_DIM, "divider", None))
        for _sid, _sidx in _sm._find_module_slots(owned, ship_spec):
            if _sid is not None:
                try:
                    _sp = _fm(_sid)
                    _sv = _sm._sell_price("module", _sid)
                    _right_items.append((_sp.name, f"(sell {_sv}$)", "", ui.COLOR_OPTION, "module_slot", _sid))
                except KeyError:
                    _right_items.append(("[unknown]", "", "", ui.COLOR_VALUE_DIM, "module_slot", None))
            else:
                _right_items.append(("[empty]", "", "", ui.COLOR_VALUE_DIM, "module_slot", None))

    console = make_console()
    _focus: int = 0  # 0 = left, 1 = right
    _sel: int = 0

    def _render() -> None:
        nonlocal _sel
        _left_display = _build_display_rows(_left_items)
        _right_display = _build_display_rows(_right_items)
        _wpn_label = f"Wpn: {len(owned.weapons)}/{ship_spec.weapon_slots}"
        _mod_label = f"Mod: {len(owned.modules)}/{ship_spec.module_slots}"
        render_split_frame(
            console,
            title="MECHANIC \u2014 SHIP LOADOUT",
            left_label=" For Sale" if _focus == 0 else "  For Sale",
            right_label="\u2502 My Ship" if _focus == 1 else "  My Ship",
            focus=_focus,
            sel=_sel,
            left_rows=_left_display,
            right_rows=_right_display,
            footer_left=f"Credits: {ctx.stats.credits}$",
            footer_right=f"{_wpn_label}  {_mod_label}",
            hint="UP/DOWN navigate  TAB switch panel  ENTER buy/sell  ESC back",
        )

    def _update(event: tcod.event.Event) -> _LoadoutOutcome:
        nonlocal _focus, _sel

        if _try_open_guide(event, ctx):
            return _LoadoutOutcome.IGNORE

        if isinstance(event, tcod.event.Quit):
            return _LoadoutOutcome.QUIT
        if not isinstance(event, tcod.event.KeyDown):
            return _LoadoutOutcome.IGNORE

        sym = event.sym
        sym_name = getattr(sym, "name", "").lower()

        if sym in ui._ESCAPE_SYMS:
            return _LoadoutOutcome.BACK

        # TAB = switch focus.
        if sym_name == "tab":
            _focus = 1 - _focus
            _sel = 0
            return _LoadoutOutcome.IGNORE

        # UP / DOWN navigation (skip dividers).
        is_up = sym in ui._UP_SYMS or sym_name == "k"
        is_down = sym in ui._DOWN_SYMS or sym_name == "j"
        if is_up:
            _items = _left_items if _focus == 0 else _right_items
            if _items:
                _sel = (_sel - 1) % len(_items)
                while _items[_sel][4] == "divider":
                    _sel = (_sel - 1) % len(_items)
            return _LoadoutOutcome.IGNORE
        if is_down:
            _items = _left_items if _focus == 0 else _right_items
            if _items:
                _sel = (_sel + 1) % len(_items)
                while _items[_sel][4] == "divider":
                    _sel = (_sel + 1) % len(_items)
            return _LoadoutOutcome.IGNORE

        # ENTER = buy (left) or sell (right).
        if sym in ui._ENTER_SYMS:
            if _focus == 0:
                # Buy + install.
                if 0 <= _sel < len(_left_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _left_items[_sel]
                    if _itype == "divider":
                        return _LoadoutOutcome.IGNORE
                    if _itype == "weapon":
                        if len(owned.weapons) >= ship_spec.weapon_slots:
                            ctx.log.add("All weapon slots are full. Sell one first.")
                            return _LoadoutOutcome.IGNORE
                        try:
                            ws = _fw(_iid)
                        except KeyError:
                            return _LoadoutOutcome.IGNORE
                        if ctx.stats.credits < ws.price:
                            ctx.log.add(f"Not enough credits to buy {ws.name} ({ws.price}$).")
                            return _LoadoutOutcome.IGNORE
                        if _sm._install_weapon(owned, _iid, ship_spec):
                            ctx.stats.credits -= ws.price
                            ctx.log.add(f"Installed {ws.name} for {ws.price}$.")
                            _rebuild_right()
                    elif _itype == "module":
                        if len(owned.modules) >= ship_spec.module_slots:
                            ctx.log.add("All module slots are full. Sell one first.")
                            return _LoadoutOutcome.IGNORE
                        try:
                            ms = _fm(_iid)
                        except KeyError:
                            return _LoadoutOutcome.IGNORE
                        if ctx.stats.credits < ms.price:
                            ctx.log.add(f"Not enough credits to buy {ms.name} ({ms.price}$).")
                            return _LoadoutOutcome.IGNORE
                        if _sm._install_module(owned, _iid, ship_spec):
                            ctx.stats.credits -= ms.price
                            ctx.log.add(f"Installed {ms.name} for {ms.price}$.")
                            _rebuild_right()
            else:
                # Sell installed part.
                if 0 <= _sel < len(_right_items):
                    _name, _label, _suffix, _fg, _itype, _iid = _right_items[_sel]
                    if _itype == "divider":
                        return _LoadoutOutcome.IGNORE
                    if _iid is None:
                        ctx.log.add("That slot is empty.")
                        return _LoadoutOutcome.IGNORE
                    if _itype == "weapon_slot":
                        _wslots = _sm._find_weapon_slots(owned, ship_spec)
                        _slot_idx = next((si for wi, si in _wslots if wi == _iid), None)
                        if _slot_idx is not None:
                            _price = _sm._sell_price("weapon", _iid)
                            try:
                                _wname = _fw(_iid).name
                            except KeyError:
                                _wname = _iid
                            _sm._remove_weapon(owned, _slot_idx)
                            ctx.stats.credits += _price
                            ctx.log.add(f"Sold {_wname} for {_price}$.")
                            _rebuild_right()
                            _sel = min(_sel, len(_right_items) - 1)
                    elif _itype == "module_slot":
                        _mslots = _sm._find_module_slots(owned, ship_spec)
                        _slot_idx = next((si for mid, si in _mslots if mid == _iid), None)
                        if _slot_idx is not None:
                            _price = _sm._sell_price("module", _iid)
                            try:
                                _mname = _fm(_iid).name
                            except KeyError:
                                _mname = _iid
                            _sm._remove_module(owned, _slot_idx)
                            ctx.stats.credits += _price
                            ctx.log.add(f"Sold {_mname} for {_price}$.")
                            _rebuild_right()
                            _sel = min(_sel, len(_right_items) - 1)
            return _LoadoutOutcome.IGNORE

        return _LoadoutOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


# ---------------------------------------------------------------------------
# Find hangar ship entity
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Planet bump dialog
# ---------------------------------------------------------------------------

def render_planet_menu(console: tcod.console.Console, ctx: GameContext, planet_obj: solar_system_module.Planet, *, screen_width: int=SCREEN_WIDTH, screen_height: int=SCREEN_HEIGHT, has_port: bool=True) -> None:
    """Paint the planet-bump dialog.

    Centered title + description, then a single ``Land`` option
    via :func:`ui.render_selectable_list` (or ``No port`` text
    when ``has_port`` is False).
    """
    console.clear()
    title_y = screen_height // 4
    console.print(x=ui.centered_x(planet_obj.name, screen_width), y=title_y, string=planet_obj.name, fg=ui.COLOR_TITLE)
    desc_y = title_y + 2
    desc_rows = ui.wrap_text(planet_obj.description, screen_width - 4)
    for i, row in enumerate(desc_rows):
        console.print(x=ui.centered_x(row, screen_width), y=desc_y + i, string=row, fg=ui.COLOR_DESCRIPTION)
    _content_bottom = desc_y + max(1, len(desc_rows))
    if has_port:
        ui.render_selectable_list(
            console, screen_width, screen_height,
            title="",
            items=[("Land", "")],
            selected=0,
            title_y=_content_bottom + 1,
            hint="ENTER to land - ESC to fly away",
        )
    else:
        console.print(
            x=ui.centered_x("No port on this world.", screen_width),
            y=_content_bottom + 1,
            string="No port on this world.",
            fg=ui.COLOR_DESCRIPTION,
        )
        console.print(
            x=ui.centered_x("ENTER or ESC to fly past.", screen_width),
            y=_content_bottom + 3,
            string="ENTER or ESC to fly past.",
            fg=ui.COLOR_INSTRUCTION,
        )
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
        if _try_open_guide(event, ctx):
            return PlanetMenuOutcome.IGNORE
        return update_planet_menu(event, has_port=has_port)
    return ui.Modal(ctx.context, console).run(_render, _update)
