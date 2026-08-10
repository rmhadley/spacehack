"""Character screen — level, XP, skills, traits, and ground equipment.

Opened via the C hotkey from city or space mode. TAB cycles between
the Stats tab and the Equipment tab.

The Stats tab shows all 6 skill rows: Gunnery, Piloting, Engineering
(ship skills) and Reflexes, Strength, Stamina (ground stats).
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


_SKILLS: tuple[str, ...] = (
    "gunnery", "piloting", "engineering",
    "reflexes", "strength", "stamina",
)
# One-line general description per skill, shown at the bottom of the
# Stats tab. Kept in sync with the guide's Character & Skills section.
_SKILL_DESCRIPTIONS: dict[str, str] = {
    "gunnery": "+0.5% hit chance per point in space combat",
    "piloting": "AP per turn (3 + Piloting//20) and dodge (cap 60%)",
    "engineering": "shield regen costs -1 power per 20 pts; +1 max power per 5",
    "reflexes": "ranged accuracy and dodge bonus on foot",
    "strength": "melee damage and two-handed weapon efficiency",
    "stamina": "HP pool (20 + Stamina//3) and damage resistance",
}
_ARMOR_SLOTS: tuple[str, ...] = ("head", "body", "hands", "legs", "feet")
_ARMOR_SLOT_LABELS: dict[str, str] = {
    "head": "Head", "body": "Body", "hands": "Hands",
    "legs": "Legs", "feet": "Feet",
}


def _character_frame(ctx: GameContext, tab: int, selected: int):
    """Build a Pygame snapshot for one Character tab."""
    from . import pygame_screen
    from .xp import xp_for_level, _xp_to_next

    level = ctx.player_level
    current_xp = max(0, ctx.player_xp - xp_for_level(level))
    needed = _xp_to_next(level)
    title = f"CHARACTER - Level {level} {ctx.character_info.get('class_name', '').title()}"
    if tab == 0:
        rows = tuple(
            pygame_screen.ScreenRow(
                text=f"{skill.title():<12} {getattr(ctx.stats if index < 3 else ctx.ground_stats, skill, 10):>3}  "
                f"{'[+]' if ctx.player_skill_points > 0 and getattr(ctx.stats if index < 3 else ctx.ground_stats, skill, 10) < 100 else 'MAX' if getattr(ctx.stats if index < 3 else ctx.ground_stats, skill, 10) >= 100 else ''}",
                detail=_SKILL_DESCRIPTIONS[skill],
                action=f"SPEND:{skill}",
            )
            for index, skill in enumerate(_SKILLS)
        )
        body = (
            f"XP: {current_xp} / {needed}    Skill points available: {ctx.player_skill_points}",
            f"Traits: {', '.join(ctx.player_traits) if ctx.player_traits else 'None'}",
        )
        footer = ("UP/DOWN or j/k select   ENTER spend   TAB equipment   ESC close",)
    else:
        rows = tuple(
            pygame_screen.ScreenRow(text=line, selectable=False)
            for line in _equipment_lines(ctx)
        )
        body = ("Your installed ground gear",)
        footer = ("TAB stats   ESC close",)
    return pygame_screen.ScreenFrame(
        title, body, rows, footer, selected,
        tabs=("STATS", "EQUIPMENT"), active_tab=tab,
    )


def _equipment_lines(ctx: GameContext) -> tuple[str, ...]:
    """Return readable equipment snapshot lines."""
    from .data.ground_weapons import find_ground_weapon
    from .data.ground_armor import find_ground_armor

    weapons = list(ctx.equipped_ground_weapons)
    while len(weapons) < 2:
        weapons.append("")
    lines = []
    for index, weapon_id in enumerate(weapons[:2], 1):
        try:
            name = find_ground_weapon(weapon_id).name if weapon_id else "Fists"
        except KeyError:
            name = weapon_id or "Fists"
        lines.append(f"Weapon slot {index}: {name}")
    for slot in _ARMOR_SLOTS:
        item_id = ctx.equipped_ground_armor.get(slot)
        try:
            name = find_ground_armor(item_id).name if item_id else "None"
        except KeyError:
            name = item_id or "None"
        lines.append(f"{_ARMOR_SLOT_LABELS[slot]} armor: {name}")
    return tuple(lines)


def _pygame_character_enabled() -> bool:
    """Return whether the generic Pygame screen worker is enabled."""
    from . import pygame_screen

    return pygame_screen.enabled()


def _run_pygame_character_screen(ctx: GameContext) -> bool | None:
    """Run Character through the shared Pygame screen."""
    from . import pygame_screen
    from .xp import _apply_skill_point

    tab = 0
    selected = 0
    while True:
        outcome, action, selected = pygame_screen.run_for_context(
            ctx.context,
            _character_frame(ctx, tab, selected),
            caption="spacehack - character",
        )
        if outcome == "GUIDE":
            from .help import _open_context_guide
            _open_context_guide(ctx, "Character & Skills")
            continue
        if outcome == "TAB":
            tab = (tab + 1) % 2
            selected = 0
            continue
        if outcome == "SELECT" and tab == 0 and action.startswith("SPEND:"):
            skill = action.split(":", 1)[1]
            if skill not in _SKILLS:
                return None
            _apply_skill_point(ctx, skill)
            continue
        if outcome in {"PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "QUIT":
            raise SystemExit
        return True


def open_character_screen(ctx: GameContext) -> None:
    """Open the Character screen in the shared Pygame window."""
    result = _run_pygame_character_screen(ctx)
    if result is None:
        raise RuntimeError("Character screen returned no outcome")
    return
def _render_stats(
    ctx: GameContext, console: tcod.console.Console,
    _sel: int, _level: int, _into_level: int, _needed: int,
) -> None:
    """Paint the Stats tab (level, XP, all 6 skills, traits)."""
    from .xp import xp_for_level as _xpfl
    _total_for_level = _xpfl(_level)
    _bar = _render_xp_bar(_into_level, _needed, width=20)
    _xp_line = (
        f"XP: {_into_level} / {_total_for_level + _needed}  "
        f"[{_bar}]  Next: {_needed - _into_level} XP"
    )
    _y = 5
    console.print(x=2, y=_y, string=_xp_line, fg=ui.COLOR_VALUE_WHITE)
    _y += 2

    _pts = ctx.player_skill_points
    console.print(
        x=2, y=_y,
        string=f"Skill Points Available: {_pts}",
        fg=ui.COLOR_VALUE_WHITE,
    )
    _y += 2

    n = len(_SKILLS)
    for i in range(n):
        _is_sel = i == _sel
        _marker = ">" if _is_sel else " "
        _skill = _SKILLS[i]

        # Ship skills come from ctx.stats, ground stats from ctx.ground_stats.
        # All six cap at 100.
        if i < 3:
            _val = getattr(ctx.stats, _skill, 0)
        else:
            _val = getattr(ctx.ground_stats, _skill, 10)
        _max_val = 100

        _plus = "[+]" if _pts > 0 and _val < _max_val else "MAX" if _val >= _max_val else "   "
        _line = f"{_marker} {_skill.title():<12} {_val:>3}  {_plus}"
        _fg = ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION
        console.print(x=2, y=_y, string=_line, fg=_fg)
        _y += 2

    _y += 1
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
        _trait_str = f"(unlock at level 20 -- need {20 - _level} more)"
    else:
        _trait_str = "(no traits chosen)"
    console.print(
        x=2, y=_y,
        string=f"Traits: {_trait_str}", fg=ui.COLOR_VALUE_DIM,
    )
    _y += 2
    console.print(
        x=2, y=_y,
        string="TAB cycle tabs  |  ENTER spend  |  ESC close",
        fg=ui.COLOR_INSTRUCTION,
    )

    # Skill reference panel — general description for each of the six
    # skills. The row matching the current selection is highlighted so
    # the description tracks the skill you're about to spend on.
    _panel_y = _y + 2
    ui.paint_rule(console, 2, _panel_y, ui.rule_width(SCREEN_WIDTH))
    _panel_y += 1
    console.print(
        x=2, y=_panel_y,
        string="What each skill does:",
        fg=ui.COLOR_VALUE_DIM,
    )
    _panel_y += 1
    for i, _skill in enumerate(_SKILLS):
        _desc = _SKILL_DESCRIPTIONS.get(_skill, "")
        _row = f"{_skill.title():<12} {_desc}"
        _is_sel = i == _sel
        _fg = ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION
        console.print(x=2, y=_panel_y, string=_row, fg=_fg)
        _panel_y += 1


def _render_equipment(ctx: GameContext, console: tcod.console.Console) -> None:
    """Paint the Equipment tab (weapon slots + armour slots)."""
    from .data.ground_weapons import find_ground_weapon as _fgw
    from .data.ground_armor import find_ground_armor as _fga

    _y = 5

    _weapons = list(ctx.equipped_ground_weapons)
    while len(_weapons) < 2:
        _weapons.append("")
    for i, _wid in enumerate(_weapons):
        _label = f"Weapon Slot {i + 1}: "
        if _wid:
            try:
                _label += _fgw(_wid).name
            except KeyError:
                _label += _wid
        else:
            _label += "Fists"
        console.print(x=2, y=_y, string=_label, fg=ui.COLOR_OPTION_HIGHLIGHT)
        _y += 1
    _y += 1

    for _slot in _ARMOR_SLOTS:
        _slot_label = _ARMOR_SLOT_LABELS.get(_slot, _slot.title())
        _aid = ctx.equipped_ground_armor.get(_slot)
        if _aid:
            try:
                _name = _fga(_aid).name
            except KeyError:
                _name = _aid
        else:
            _name = "None"
        _pad = max(1, 10 - len(_slot_label))
        console.print(x=2, y=_y, string=f"{_slot_label}:{' ' * _pad}{_name}", fg=ui.COLOR_OPTION)
        _y += 1
    _y += 1

    console.print(
        x=2, y=_y,
        string="Use the Armory terminal (A) on the city map to manage gear.",
        fg=ui.COLOR_INSTRUCTION,
    )
