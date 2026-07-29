"""Trait selection modal — shown at level 20 and 30 milestones.

Opened by :func:`spacehack.xp.add_xp` when the player reaches a
milestone.  Presents all qualifying traits (filtered by counters
and not-already-chosen) and lets the player pick one with ENTER.

Design doc: ``docs/design/in_progress/02_DESIGN_XP_LEVELING.md``
"""

from __future__ import annotations

import tcod.console
import tcod.event

from . import ui
from . import message_log
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .game_context import GameContext
from .input_helpers import _try_open_guide
from .xp import _qualifying_traits


def open_trait_selection(ctx: GameContext) -> None:
    """Open the trait selection modal.

    Lists all traits the player qualifies for (via
    :func:`_qualifying_traits`).  If none qualify, logs a message
    and returns without showing the modal — the player can open the
    Character screen later to pick when they do qualify.
    """
    _candidates = _qualifying_traits(ctx)
    if not _candidates:
        ctx.log.add_colored(
            "No qualifying traits available yet — check the Character screen later.",
            message_log.COLOR_IMPORTANT_EVENT,
        )
        return

    from .menus._ship_menu import ShipMenuAction
    console = make_console()
    _sel: int = 0
    _n = len(_candidates)

    def _render() -> None:
        nonlocal _sel
        console.clear()

        _title = f"TRAIT SELECTION — Level {ctx.player_level}"
        console.print(
            x=ui.centered_x(_title, SCREEN_WIDTH),
            y=SCREEN_HEIGHT // 5,
            string=_title,
            fg=ui.COLOR_TITLE,
        )
        _div = "=" * 50
        console.print(
            x=ui.centered_x(_div, SCREEN_WIDTH),
            y=SCREEN_HEIGHT // 5 + 1,
            string=_div,
            fg=ui.COLOR_TITLE,
        )

        _y = SCREEN_HEIGHT // 5 + 3
        for _i, _trait in enumerate(_candidates):
            _is_sel = _i == _sel
            _marker = ">" if _is_sel else " "
            _name_line = f"{_marker} {_trait.name}"
            _fg = ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION
            console.print(
                x=SCREEN_WIDTH // 4,
                y=_y,
                string=_name_line,
                fg=_fg,
            )
            _y += 1
            # Description (dimmer).
            console.print(
                x=SCREEN_WIDTH // 4 + 2,
                y=_y,
                string=_trait.description,
                fg=ui.COLOR_VALUE_DIM,
            )
            _y += 2

        _y += 1
        console.print(
            x=SCREEN_WIDTH // 4,
            y=_y,
            string="TAB cycle  |  ENTER choose",
            fg=ui.COLOR_INSTRUCTION,
        )

        message_log.render_message_log(
            console, ctx.log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

    def _update(event: tcod.event.Event) -> ShipMenuAction | None:
        nonlocal _sel
        if _try_open_guide(event, ctx):
            return ShipMenuAction.IGNORE
        if isinstance(event, tcod.event.Quit):
            return None
        if not isinstance(event, tcod.event.KeyDown):
            return ShipMenuAction.IGNORE
        sym = event.sym
        sym_name: str = getattr(sym, "name", "").lower()
        if sym in ui._ESCAPE_SYMS:
            # Mandatory selection — no deferring.  The player must
            # pick a trait before gameplay resumes.
            return ShipMenuAction.IGNORE
        if sym_name == "tab":
            _sel = (_sel + 1) % _n
            return ShipMenuAction.IGNORE
        if sym in ui._ENTER_SYMS:
            _picked = _candidates[_sel]
            ctx.player_traits.append(_picked.id)
            ctx.log.add_colored(
                f"Trait gained: {_picked.name} — {_picked.description}",
                message_log.COLOR_COMBAT_EVENT,
            )
            return None
        # Up/down also cycles.
        if sym in ui._UP_SYMS or sym_name == "k":
            _sel = (_sel - 1) % _n
            return ShipMenuAction.IGNORE
        if sym in ui._DOWN_SYMS or sym_name == "j":
            _sel = (_sel + 1) % _n
            return ShipMenuAction.IGNORE
        return ShipMenuAction.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
