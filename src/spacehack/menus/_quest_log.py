"""Quest log overlay — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
Supports up to 5 active missions with arrow-key navigation.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import mission as mission_module
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


class QuestLogOutcome(Enum):
    """What the player chose in the city quest log.

    ``ABANDONED`` carries the abandoned mission's index back so
    :func:`_run_game` can log a "You abandoned ..." line and
    remove the mission from the list.
    """
    IGNORE = auto()
    BACK = auto()
    ABANDONED = auto()
    QUIT = auto()


def render_quest_log(console: tcod.console.Console, ctx: GameContext, *, selected: int = 0, confirm_abandon: bool = False, screen_width: int, screen_height: int) -> None:
    """Paint the city quest-log overlay.

    Shows a list of up to 5 active missions. Arrow keys navigate,
    Enter to view details (future), A to abandon, ESC to close.
    """
    console.clear()
    missions = ctx.player_active_missions
    max_w = screen_width - HUD_WIDTH - 2

    def fit(line: str) -> str:
        return line if len(line) <= max_w else line[:max_w - 1] + '…'

    def paint(row: int, text: str, *, fg: tuple[int, int, int]) -> None:
        console.print(x=ui.centered_x(text, screen_width), y=row, string=text, fg=fg)

    center_y = (screen_height - MSG_LOG_HEIGHT) // 2

    if not missions:
        paint(center_y - 2, fit('QUEST LOG'), fg=ui.COLOR_TITLE)
        paint(center_y + 1, fit('(no active missions)'), fg=ui.COLOR_DESCRIPTION)
        paint(center_y + 5, fit('Press ESC to close.'), fg=ui.COLOR_INSTRUCTION)
        from .. import message_log
        message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)
        return

    paint(center_y - 8, fit('QUEST LOG'), fg=ui.COLOR_TITLE)
    paint(center_y - 6, fit(f'{len(missions)} / {mission_module.MAX_ACTIVE_MISSIONS} missions'), fg=ui.COLOR_VALUE_DIM)

    list_top = center_y - 4
    for i, am in enumerate(missions):
        row = list_top + i * 2
        is_sel = i == selected
        marker = '> ' if is_sel else '  '
        end_marker = ' <' if is_sel else '  '
        text = f'{marker}{am.title}{end_marker}'
        console.print(
            x=ui.centered_x(text, screen_width), y=row, string=text,
            fg=ui.COLOR_OPTION_HIGHLIGHT if is_sel else ui.COLOR_OPTION,
        )

    # Detail pane for selected mission
    if 0 <= selected < len(missions):
        am = missions[selected]
        detail_top = list_top + len(missions) * 2 + 1

        if am.delivery_target_planet_id:
            _planet_name = am.delivery_target_planet_id
            try:
                from ..data.planets import find_planet_spec as _fps_q
                _planet_name = _fps_q(am.delivery_target_planet_id).name
            except (KeyError, ImportError):
                pass
            _npc_name = ""
            if am.delivery_target_npc_id:
                try:
                    from ..data.npcs import find_npc as _fnpc_q
                    _npc_name = f" ({_fnpc_q(am.delivery_target_npc_id).name})"
                except (KeyError, ImportError):
                    pass
            paint(detail_top, fit(f'Deliver to: {_planet_name}{_npc_name}'), fg=ui.COLOR_VALUE_WHITE)
            detail_top += 1
        paint(detail_top, fit(f'Cargo: {am.required_cargo_size} units'), fg=ui.COLOR_VALUE_WHITE)
        detail_top += 1
        paint(detail_top, fit(f'Reward: {am.reward_credits}$ + {am.reward_xp}xp'), fg=ui.COLOR_VALUE_WHITE)
        detail_top += 1
        if am.time_deadline is not None:
            _d, _m, _y = am.time_deadline
            _total_days = (_y - ctx.time_year) * 360 + (_m - ctx.time_month) * 30 + (_d - ctx.time_day)
            _date_str = f'{_y}{_m:02d}{_d:02d}'
            # Show EXPIRED only when strictly past the deadline.
            # _total_days == 0 means due TODAY — still deliverable at full pay.
            if _total_days >= 0:
                paint(detail_top, fit(f'Due: {_date_str} ({_total_days} days)'), fg=ui.COLOR_OPTION_HIGHLIGHT)
            else:
                paint(detail_top, fit(f'EXPIRED — Due: {_date_str}'), fg=(255, 80, 80))
            detail_top += 1

    button_row = max(list_top + len(missions) * 2 + 8, center_y + 10)
    if confirm_abandon:
        paint(button_row, fit('Press ENTER to abandon. ESC cancels.'), fg=ui.COLOR_OPTION_HIGHLIGHT)
    else:
        paint(button_row, fit('ARROW KEYS navigate - A abandon - ESC close.'), fg=ui.COLOR_INSTRUCTION)

    from .. import message_log
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def update_quest_log(event: tcod.event.Event, *, confirm_abandon: bool) -> QuestLogOutcome:
    """Map a single event for the quest-log overlay.

    Two states:
      * ``confirm_abandon`` False — ESC -> BACK, A -> ABANDONED.
      * ``confirm_abandon`` True — ENTER -> ABANDONED, ESC -> BACK.
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


def _quest_log_navigate(event: tcod.event.Event, selected: int, n: int) -> int | None:
    """If ``event`` drives quest log nav, return the new ``selected`` index."""
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


def _run_quest_log(ctx) -> tuple[QuestLogOutcome, int | None]:
    """Show the city quest-log overlay and return the outcome.

    Returns ``(outcome, abandoned_index)``: ``abandoned_index`` is
    the index of the abandoned mission (for removal from the list),
    or ``None``.
    """
    console = make_console()
    selected = 0
    confirm_abandon = False
    missions = ctx.player_active_missions

    def _render() -> None:
        render_quest_log(console, ctx, selected=selected, confirm_abandon=confirm_abandon, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)

    def _update(event) -> QuestLogOutcome:
        nonlocal selected, confirm_abandon
        if _try_open_guide(event, ctx):
            return QuestLogOutcome.IGNORE
        new = _quest_log_navigate(event, selected, len(missions))
        if new is not None:
            selected = new
            return QuestLogOutcome.IGNORE
        result = update_quest_log(event, confirm_abandon=confirm_abandon)
        if result is QuestLogOutcome.ABANDONED and (not confirm_abandon):
            confirm_abandon = True
            return QuestLogOutcome.IGNORE
        return result

    outcome = ui.Modal(ctx.context, console).run(_render, _update)
    if outcome is QuestLogOutcome.ABANDONED:
        return (outcome, selected)
    return (outcome, None)
