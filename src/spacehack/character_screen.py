"""Character screen — level, XP, skills, traits, and ground equipment.

Opened via the C hotkey from city or space mode. TAB cycles between
the Stats tab and the Equipment tab.

The Stats tab shows all 6 skill rows: Gunnery, Piloting, Engineering
(ship skills) and Reflexes, Strength, Stamina (ground stats).
"""

from __future__ import annotations

from .game_context import GameContext

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
    from . import pygame_screen, pygame_ui
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
        footer = (pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER spend", "TAB equipment",
            "ESC close", pygame_ui.GUIDE_HINT,
        ),)
    else:
        rows = _equipment_rows(ctx)
        body = ("Your equipped ground gear",)
        footer = (pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "TAB stats", "ESC close",
            pygame_ui.GUIDE_HINT,
        ),)
    return pygame_screen.ScreenFrame(
        title, body, rows, footer, selected,
        tabs=("STATS", "EQUIPMENT"), active_tab=tab,
    )

def _equipment_rows(ctx: GameContext) -> tuple:
    """Build Equipment-tab rows mirroring the hangar LOADOUT tab.

    Filled slots are selectable rows whose detail pane carries the
    weapon / armor stats; empty slots are non-selectable ``Fists`` /
    ``None`` placeholders. A frame with no gear at all is entirely
    informational, which :mod:`pygame_screen` renders as a capped list.
    """
    from . import pygame_screen
    from .data.ground_weapons import find_ground_weapon
    from .data.ground_armor import find_ground_armor

    rows: list = []
    weapons = list(ctx.equipped_ground_weapons)
    while len(weapons) < 2:
        weapons.append("")
    first_weapon_is_two_handed = False
    if weapons[0]:
        try:
            first_weapon_is_two_handed = find_ground_weapon(weapons[0]).hands == 2
        except KeyError:
            pass
    for index, weapon_id in enumerate(weapons[:2], 1):
        label = f"Weapon slot {index}"
        if index == 2 and first_weapon_is_two_handed:
            rows.append(pygame_screen.ScreenRow(
                f"{label}: --- (occupied by 2H)", "", selectable=False,
            ))
            continue
        if weapon_id:
            try:
                spec = find_ground_weapon(weapon_id)
                detail = (
                    f"Damage {spec.damage}   Accuracy {spec.accuracy}%   "
                    f"Range {spec.min_range}-{spec.max_range}   AP {spec.ap_cost}"
                )
                if spec.ammo_capacity > 0:
                    detail += f"   Ammo {spec.ammo_capacity}"
                rows.append(pygame_screen.ScreenRow(
                    f"{label}: {spec.name}", detail, selectable=True,
                ))
                continue
            except KeyError:
                pass
        rows.append(pygame_screen.ScreenRow(
            f"{label}: Fists", "", selectable=False,
        ))
    for slot in _ARMOR_SLOTS:
        item_id = ctx.equipped_ground_armor.get(slot)
        label = f"{_ARMOR_SLOT_LABELS[slot]} armor"
        if item_id:
            try:
                spec = find_ground_armor(item_id)
                rows.append(pygame_screen.ScreenRow(
                    f"{label}: {spec.name}",
                    f"Defense {spec.defense}   {spec.description}",
                    selectable=True,
                ))
                continue
            except KeyError:
                pass
        rows.append(pygame_screen.ScreenRow(
            f"{label}: None", "", selectable=False,
        ))
    return tuple(rows)

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
        if outcome == "SELECT":
            if tab == 0 and action.startswith("SPEND:"):
                skill = action.split(":", 1)[1]
                if skill not in _SKILLS:
                    return None
                _apply_skill_point(ctx, skill)
            continue  # read-only rows: ENTER keeps the screen open
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
