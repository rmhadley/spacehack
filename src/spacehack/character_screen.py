"""Character screen — level, XP, skills, traits.

Opened via the C hotkey from city or space mode. Follows the same
modal pattern as :func:`spacehack.menus._ship_menu._run_faction_view`.

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


_SKILLS: tuple[str, ...] = ("gunnery", "piloting", "engineering")


def _xp_bar(current: int, needed: int, width: int = 20) -> str:
    """Return a compact XP progress bar using CP437-safe chars.

    ``#`` = filled, ``-`` = empty.  ``current`` is XP earned this
    level; ``needed`` is total XP to reach the next level.
    """
    if needed <= 0:
        return "#" * width
    filled = max(0, min(width, current * width // needed))
    return "#" * filled + "-" * (width - filled)


def open_character_screen(ctx: GameContext) -> None:
    """Open the Character screen modal."""
    from .menus._ship_menu import ShipMenuAction
    console = make_console()
    _sel: int = 0  # 0=gunnery, 1=piloting, 2=engineering

    # Compute XP for next level (50 + (level+1)*20).
    _level = ctx.player_level
    _needed = 50 + (_level + 1) * 20
    from .xp import xp_for_level as _xp_for_level
    _total_for_current = _xp_for_level(_level)
    _into_level = ctx.player_xp - _total_for_current

    def _render() -> None:
        nonlocal _sel
        console.clear()

        _class_name = ctx.character_info.get("class_name", "").title()
        _title = f"CHARACTER — Level {_level} {_class_name}"
        console.print(
            x=ui.centered_x(_title, SCREEN_WIDTH),
            y=SCREEN_HEIGHT // 6,
            string=_title,
            fg=ui.COLOR_TITLE,
        )
        _div = "=" * 50
        console.print(
            x=ui.centered_x(_div, SCREEN_WIDTH),
            y=SCREEN_HEIGHT // 6 + 1,
            string=_div,
            fg=ui.COLOR_TITLE,
        )

        # XP bar.
        _bar = _xp_bar(_into_level, _needed)
        _xp_line = f"XP: {_into_level} / {_total_for_current + _needed}  [{_bar}]  Next: {_needed - _into_level} XP"
        _y = SCREEN_HEIGHT // 6 + 3
        console.print(
            x=SCREEN_WIDTH // 4,
            y=_y,
            string=_xp_line,
            fg=ui.COLOR_VALUE_WHITE,
        )
        _y += 2

        # Skill points available.
        _pts = ctx.player_skill_points
        console.print(
            x=SCREEN_WIDTH // 4,
            y=_y,
            string=f"Skill Points Available: {_pts}",
            fg=ui.COLOR_VALUE_WHITE,
        )
        _y += 2

        # Skill rows.
        for _i, _skill in enumerate(_SKILLS):
            _val = getattr(ctx.stats, _skill, 0)
            _is_sel = _i == _sel
            _marker = ">" if _is_sel else " "
            _plus = "[+]" if _pts > 0 and _val < 100 else "MAX" if _val >= 100 else "   "
            _line = f"{_marker} {_skill.title():<12} {_val:>3}  {_plus}"
            _fg = ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION
            console.print(
                x=SCREEN_WIDTH // 4,
                y=_y,
                string=_line,
                fg=_fg,
            )
            _y += 2

        _y += 1

        # Traits.
        _traits = ctx.player_traits
        if _traits:
            _trait_str = ", ".join(t.title().replace("_", " ") for t in _traits)
        elif _level < 20:
            _trait_str = f"(unlock at level 20 — need {20 - _level} more)"
        else:
            _trait_str = "(none chosen — open Character screen at a milestone to pick)"
        console.print(
            x=SCREEN_WIDTH // 4,
            y=_y,
            string=f"Traits: {_trait_str}",
            fg=ui.COLOR_VALUE_DIM,
        )
        _y += 2

        # Hint.
        console.print(
            x=SCREEN_WIDTH // 4,
            y=_y,
            string="TAB cycle  |  ENTER spend  |  ESC close",
            fg=ui.COLOR_INSTRUCTION,
        )

        message_log.render_message_log(
            console, ctx.log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

    def _update(event: tcod.event.Event) -> ShipMenuAction | None:
        """Return IGNORE to keep polling, None to close."""
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
            return None
        if sym_name == "tab":
            _sel = (_sel + 1) % len(_SKILLS)
            return ShipMenuAction.IGNORE
        if sym in ui._ENTER_SYMS:
            from .xp import _apply_skill_point
            _apply_skill_point(ctx, _SKILLS[_sel])
            return ShipMenuAction.IGNORE
        # Up/down also cycles.
        if sym in ui._UP_SYMS or sym_name == "k":
            _sel = (_sel - 1) % len(_SKILLS)
            return ShipMenuAction.IGNORE
        if sym in ui._DOWN_SYMS or sym_name == "j":
            _sel = (_sel + 1) % len(_SKILLS)
            return ShipMenuAction.IGNORE
        return ShipMenuAction.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
