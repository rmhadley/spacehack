"""Character screen — level, XP, skills, traits, and ground equipment.

Opened via the C hotkey from city or space mode. Follows the same
modal pattern as :func:`spacehack.menus._ship_menu._run_faction_view`.

TAB cycles between the Stats tab and the Equipment tab.

Design doc: ``docs/design/in_progress/02_DESIGN_XP_LEVELING.md``
"""

from __future__ import annotations

import tcod.console
import tcod.event

from . import ui
from . import message_log
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from .game_context import GameContext
from .hud import _render_xp_bar
from .input_helpers import _try_open_guide


_SKILLS: tuple[str, ...] = ("gunnery", "piloting", "engineering")


def open_character_screen(ctx: GameContext) -> None:
    """Open the Character screen modal."""
    from .menus._ship_menu import ShipMenuAction
    console = make_console()
    _sel: int = 0  # 0=gunnery, 1=piloting, 2=engineering
    _tab: int = 0  # 0=Stats, 1=Equipment

    # Compute XP for next level.
    _level = ctx.player_level
    from .xp import xp_for_level as _xp_for_level, _xp_to_next as _xp_to_next
    _total_for_current = _xp_for_level(_level)
    _needed = _xp_to_next(_level)
    _into_level = max(0, ctx.player_xp - _total_for_current)

    def _render() -> None:
        nonlocal _sel
        console.clear()

        _class_name = ctx.character_info.get("class_name", "").title()
        _title = f"CHARACTER — Level {_level} {_class_name}"

        # Tab bar at the top.
        _tab_labels = ["  Stats  ", "  Equipment  "]
        _tab_str = ""
        for i, _tl in enumerate(_tab_labels):
            if i == _tab:
                _tab_str += f"[{_tl}]"
            else:
                _tab_str += f" {_tl} "
        console.print(
            x=ui.centered_x(_tab_str, SCREEN_WIDTH),
            y=SCREEN_HEIGHT // 6 - 2,
            string=_tab_str,
            fg=ui.COLOR_OPTION_HIGHLIGHT if _tab == 0 else ui.COLOR_OPTION,
        )
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

        if _tab == 0:
            _render_stats(ctx, console, _sel, _level, _into_level, _needed)
        else:
            _render_equipment(ctx, console)

        message_log.render_message_log(
            console, ctx.log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

    def _update(event: tcod.event.Event) -> ShipMenuAction | None:
        """Return IGNORE to keep polling, None to close."""
        nonlocal _sel, _tab
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
            _tab = (_tab + 1) % 2
            _sel = 0
            return ShipMenuAction.IGNORE

        if _tab == 0:
            # Stats tab navigation.
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
        # Equipment tab: no interactive selection needed for now.
        return ShipMenuAction.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)


def _render_stats(
    ctx: GameContext, console: tcod.console.Console,
    _sel: int, _level: int, _into_level: int, _needed: int,
) -> None:
    """Paint the Stats tab (level, XP, skills, traits)."""
    # XP bar — total XP needed includes current threshold + gap to next.
    from .xp import xp_for_level as _xpfl
    _total_for_level = _xpfl(_level)
    _bar = _render_xp_bar(_into_level, _needed, width=20)
    _xp_line = f"XP: {_into_level} / {_total_for_level + _needed}  [{_bar}]  Next: {_needed - _into_level} XP"
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
        _names: list[str] = []
        from .data.traits.core import find_trait as _find_trait
        for _tid in _traits:
            try:
                _names.append(_find_trait(_tid).name)
            except KeyError:
                _names.append(_tid)
        _trait_str = ", ".join(_names)
    elif _level < 20:
        _trait_str = f"(unlock at level 20 — need {20 - _level} more)"
    else:
        _trait_str = "(no traits chosen)"
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
        string="TAB cycle tabs  |  ENTER spend  |  ESC close",
        fg=ui.COLOR_INSTRUCTION,
    )


def _render_equipment(ctx: GameContext, console: tcod.console.Console) -> None:
    """Paint the Equipment tab (ground weapon + armour)."""
    from .data.ground_weapons import find_ground_weapon as _fgw
    from .data.ground_armor import find_ground_armor as _fga

    _y = SCREEN_HEIGHT // 6 + 3

    # Weapon slot.
    _weapon_name = "Fists"
    if ctx.equipped_ground_weapon is not None:
        try:
            _ws = _fgw(ctx.equipped_ground_weapon)
            _weapon_name = _ws.name
        except KeyError:
            _weapon_name = ctx.equipped_ground_weapon
    console.print(
        x=SCREEN_WIDTH // 4,
        y=_y,
        string=f"Weapon: {_weapon_name}",
        fg=ui.COLOR_OPTION_HIGHLIGHT,
    )
    _y += 2

    # Armor slots.
    _armor_slots = ("helmet", "vest", "gloves", "boots")
    _slot_labels = {
        "helmet": "Helmet",
        "vest": "Vest",
        "gloves": "Gloves",
        "boots": "Boots",
    }
    for _slot in _armor_slots:
        _label = _slot_labels.get(_slot, _slot.title())
        _armor_name = "None"
        _aid = ctx.equipped_ground_armor.get(_slot)
        if _aid is not None:
            try:
                _as = _fga(_aid)
                _armor_name = _as.name
            except KeyError:
                _armor_name = _aid
        console.print(
            x=SCREEN_WIDTH // 4,
            y=_y,
            string=f"{_label}: {_armor_name}",
            fg=ui.COLOR_OPTION,
        )
        _y += 1

    _y += 1

    # Ground inventory count.
    _inv_count = len(ctx.ground_inventory)
    console.print(
        x=SCREEN_WIDTH // 4,
        y=_y,
        string=f"Carrying: {_inv_count} item{'s' if _inv_count != 1 else ''}",
        fg=ui.COLOR_VALUE_WHITE,
    )
    _y += 2

    # Hint.
    console.print(
        x=SCREEN_WIDTH // 4,
        y=_y,
        string="TAB cycle tabs  |  Use Armory (A) on city map to manage gear  |  ESC close",
        fg=ui.COLOR_INSTRUCTION,
    )
