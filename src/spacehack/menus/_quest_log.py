"""Quest log overlay — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import mission as mission_module
from .. import npc as npc_module
from ..game_context import GameContext
from ..engine import HUD_WIDTH, MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


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


def render_quest_log(console: tcod.console.Console, ctx: GameContext, *, confirm_abandon: bool = False, screen_width: int, screen_height: int) -> None:
    """Paint the city quest-log overlay.

    Two visual states:

      * ``confirm_abandon`` False — shows the active mission's full
        details and the "Press A to abandon. ESC to close." hint.
      * ``confirm_abandon`` True — swaps in "Press ENTER to abandon.
        ESC cancels." for the two-step confirmation.

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


def _run_quest_log(ctx) -> tuple[QuestLogOutcome, mission_module.ActiveMission | None]:
    """Show the city quest-log overlay and apply any state changes.

    Returns ``(outcome, maybe_new_active)``: ``maybe_new_active`` is
    ``None`` when the player confirmed ABANDONED, or the same
    ``ActiveMission`` instance for every other outcome.
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
